"""Pinned, fail-closed offline inference over causal public FORCE observations.

Each prediction consumes exactly one prefix through the existing bounded
CurveWindowBuilder. No label, coordinate, confidence, future timestamp or world
API is part of this interface. Model weights are JSON, never pickle/code.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import struct
import sys
import time

from ai_pc.model.curve_input import (
    CONTRACT_DESIGN_COMMIT, CONTRACT_ID, CONTRACT_REQUIREMENTS_SHA256,
    CONTRACT_REVISION, CONTRACT_SOURCE_COMMIT, CurveInputError, CurveObservation,
    CurveScaler, CurveWindowBuilder, PROFILE_ID,
)

SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_RECORD_BYTES = 16384
MAX_RECORDS = 100000
FIXED_PREPROCESSING_SHA256 = "cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef"
FIXED_CURVE_BUILDER_SHA256 = "c017729a2d5717ff2bbf5a6c591320519c415ac10068b4cee19b3136913d848c"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class PackageError(ValueError):
    """Rejected input/artifact or unavailable prerequisite with explicit code."""

    def __init__(self, code, message, *, blocked=False):
        super().__init__(message)
        self.code = code
        self.blocked = blocked


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PackageError("schema_invalid", "duplicate JSON field %r" % key)
        value[key] = item
    return value


def _invalid_constant(value):
    raise PackageError("schema_invalid", "nonfinite JSON constant %s is forbidden" % value)


def strict_json(data):
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise PackageError("schema_invalid", "invalid UTF-8 JSON: %s" % exc) from exc


def validate_sha(value, field):
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise PackageError("hash_invalid", "%s must be 64 lowercase hex characters" % field)
    return value


def read_pinned(path, expected, *, missing_code="asset_missing", limit=None):
    validate_sha(expected, "expected SHA256")
    try:
        with Path(path).open("rb") as stream:
            data = stream.read() if limit is None else stream.read(limit + 1)
    except FileNotFoundError as exc:
        raise PackageError(missing_code, "%s is absent" % path, blocked=True) from exc
    except OSError as exc:
        raise PackageError("asset_unreadable", "%s cannot be read: %s" % (path, exc)) from exc
    if limit is not None and len(data) > limit:
        raise PackageError("input_limit", "input exceeds %d bytes" % limit)
    if sha256(data) != expected:
        raise PackageError("hash_mismatch", "%s does not match its externally supplied SHA256" % path)
    return data


def load_public_input(path, expected_sha256):
    """Return validated immutable observations and exact byte prefixes.

    The source-domain flag is a binding declaration, not proof that arbitrary
    callers supplied real observations. Source evidence is separately pinned.
    No input field for timestamps, depth, labels or truth is accepted.
    """
    data = read_pinned(path, expected_sha256, missing_code="input_missing", limit=MAX_INPUT_BYTES)
    rows = data.splitlines(keepends=True)
    if not rows or len(rows) > MAX_RECORDS:
        raise PackageError("input_limit", "input must contain 1..%d JSONL records" % MAX_RECORDS)
    observations = []
    digests = []
    prefix = hashlib.sha256()
    binding = None
    for index, line in enumerate(rows):
        if not line.strip() or len(line) > MAX_RECORD_BYTES:
            raise PackageError("schema_invalid", "record %d is empty or exceeds %d bytes" % (index, MAX_RECORD_BYTES))
        try:
            observation = CurveObservation.from_mapping(strict_json(line))
        except CurveInputError as exc:
            raise PackageError("schema_invalid", "record %d: %s" % (index, exc)) from exc
        if observation.binding.source_domain != "geo_replay":
            raise PackageError("source_domain_blocked", "this trained package supports only public FORCE geo_replay")
        if observation.binding.preprocessing_sha256 != FIXED_PREPROCESSING_SHA256:
            raise PackageError("binding_invalid", "observation scaler pin differs from frozen FORCE preprocessing")
        if binding is None:
            binding = observation.binding
        if binding != observation.binding:
            raise PackageError("binding_invalid", "record %d changes run/source/profile/scaler binding" % index)
        observations.append(observation)
        prefix.update(line)
        digests.append(prefix.hexdigest())
    return tuple(observations), tuple(digests), data


def causal_windows(observations, scaler):
    """Fresh run on every invocation; yields immutable exact existing windows."""
    if not observations:
        raise PackageError("schema_invalid", "empty observations")
    builder = CurveWindowBuilder(scaler=scaler, binding=observations[0].binding)
    for observation in observations:
        try:
            builder.observe(observation)
        except CurveInputError as exc:
            raise PackageError("schema_invalid", str(exc)) from exc
        yield builder.snapshot()


def _reference(manifest_path, manifest, field):
    reference = manifest.get(field)
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise PackageError("manifest_invalid", "%s reference must contain exactly path/sha256" % field)
    relative = reference["path"]
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or ":" in relative or "\\" in relative or "\x00" in relative):
        raise PackageError("manifest_invalid", "%s path must be relative to the manifest" % field)
    validate_sha(reference["sha256"], field + ".sha256")
    return Path(manifest_path).resolve().parent / relative


def _select_device(torch, requested):
    if requested == "cpu":
        return "cpu", platform.processor() or "CPU"
    if requested != "hip":
        raise PackageError("device_invalid", "device must be cpu or hip")
    if not torch.version.hip or not torch.cuda.is_available():
        raise PackageError("hip_unavailable", "explicit HIP requested but this runtime has no usable HIP device; no CPU fallback", blocked=True)
    return "cuda:0", torch.cuda.get_device_name(0)


def _tensor(torch, window, device):
    tensor = torch.tensor(window.to_model_input(), dtype=torch.float32, device=device)
    if tuple(tensor.shape) != (1, 8, 128, 1) or not bool(torch.isfinite(tensor).all()):
        raise PackageError("feature_invalid", "float32 model input must be finite [1,8,128,1]")
    # Canonical actual model dtype, little endian C-order, independent of host.
    packed = struct.pack("<1024f", *tensor.detach().cpu().reshape(-1).tolist())
    return tensor, sha256(packed)


def _predict(torch, model, tensor):
    logits = model(tensor)
    if tuple(logits.shape) != (1, 12) or not bool(torch.isfinite(logits).all()):
        raise PackageError("model_output_invalid", "model must return finite [1,12] logits")
    probabilities = torch.softmax(logits, dim=1).detach().cpu().tolist()[0]
    if len(probabilities) != 12 or any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise PackageError("model_output_invalid", "invalid class probabilities")
    if abs(sum(probabilities) - 1.0) > 1e-5:
        raise PackageError("model_output_invalid", "class probabilities do not sum to one")
    return probabilities


def execute(*, manifest_path, expected_manifest_sha256, input_path,
            expected_input_sha256, profile=PROFILE_ID, device="cpu", threads=4,
            benchmark_repetitions=0):
    """Compute one offline result. Never opens output, services or transport."""
    compute_start = time.perf_counter_ns()
    if profile != PROFILE_ID:
        if profile == "sim_em_v2":
            raise PackageError("sim_em_model_missing", "sim_em_v2 trained model and fitted scales are absent; FORCE is not remapped to sensor/water observations", blocked=True)
        raise PackageError("profile_invalid", "unsupported profile")
    if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 4:
        raise PackageError("threads_invalid", "threads must be 1..4")
    if isinstance(benchmark_repetitions, bool) or not isinstance(benchmark_repetitions, int) or not 0 <= benchmark_repetitions <= 100:
        raise PackageError("benchmark_invalid", "benchmark repetitions must be 0..100")
    manifest_bytes = read_pinned(manifest_path, expected_manifest_sha256, missing_code="model_missing", limit=2 * 1024 * 1024)
    manifest = strict_json(manifest_bytes)
    if not isinstance(manifest, dict):
        raise PackageError("manifest_invalid", "model manifest must be an object")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise PackageError("manifest_invalid", "model manifest schema_version must be exact integer 1")
    if manifest.get("profile_id") != PROFILE_ID or manifest.get("source_domain") != "geo_replay":
        raise PackageError("manifest_invalid", "model manifest is not the FORCE geo_replay profile")
    input_start = time.perf_counter_ns()
    observations, prefix_digests, input_bytes = load_public_input(input_path, expected_input_sha256)
    input_validation_ns = time.perf_counter_ns() - input_start
    scaler_start = time.perf_counter_ns()
    curve_source = Path(sys.modules[CurveWindowBuilder.__module__].__file__)
    read_pinned(curve_source, FIXED_CURVE_BUILDER_SHA256)
    # JSON/schema/binding checks precede model loading. Sequence history is
    # validated by the existing builder as prefixes are consumed below.
    preprocessing_path = _reference(manifest_path, manifest, "preprocessing")
    product_root = curve_source.resolve().parents[2]
    if preprocessing_path.resolve() != (product_root / "data/preprocessing.json").resolve():
        raise PackageError("manifest_invalid", "scaler reference must resolve to the fixed product preprocessing path")
    if manifest["preprocessing"]["sha256"] != FIXED_PREPROCESSING_SHA256:
        raise PackageError("manifest_invalid", "model scaler is not the frozen FORCE scaler")
    preprocessing_bytes = read_pinned(preprocessing_path, FIXED_PREPROCESSING_SHA256)
    scaler = CurveScaler.from_document_bytes(preprocessing_bytes, expected_sha256=FIXED_PREPROCESSING_SHA256)
    scaler_load_ns = time.perf_counter_ns() - scaler_start
    asset_start = time.perf_counter_ns()
    for field in ("graph", "weights", "label_schema"):
        asset_path = _reference(manifest_path, manifest, field)
        if field in ("graph", "weights"):
            if asset_path.resolve().parent != Path(manifest_path).resolve().parent:
                raise PackageError("manifest_invalid", "graph/weights must be direct manifest siblings")
        elif asset_path.resolve() != (product_root / "data/label_schema.json").resolve():
            raise PackageError("manifest_invalid", "label schema must resolve to the fixed product path")
        read_pinned(asset_path, manifest[field]["sha256"],
                    missing_code="model_missing" if field in ("graph", "weights") else "asset_missing")
    model_asset_preflight_ns = time.perf_counter_ns() - asset_start
    # Keep only the current 128-slot window. No collection of prior tensors or
    # future features is constructed; only final JSON prediction records grow.
    windows = causal_windows(observations, scaler)
    import_start = time.perf_counter_ns()
    try:
        import torch
        from ai_pc.model.force_cnn import load_frozen_model
    except (ImportError, ModuleNotFoundError) as exc:
        raise PackageError("model_missing", "trained model/runtime dependency is unavailable: %s" % exc, blocked=True) from exc
    runtime_import_ns = time.perf_counter_ns() - import_start
    actual_device, device_name = _select_device(torch, device)
    torch.set_num_threads(threads)
    torch.use_deterministic_algorithms(True)
    load_start = time.perf_counter_ns()
    try:
        model, loaded_manifest = load_frozen_model(manifest_path, expected_manifest_sha256, device=actual_device)
    except FileNotFoundError as exc:
        raise PackageError("model_missing", "model asset absent: %s" % exc, blocked=True) from exc
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise PackageError("model_invalid", str(exc)) from exc
    if loaded_manifest != manifest:
        raise PackageError("manifest_invalid", "loader returned a different manifest")
    model.eval()
    load_ns = time.perf_counter_ns() - load_start
    predictions = []
    prediction_ns = []
    feature_build_ns = []
    final_tensor = None
    with torch.inference_mode():
        window_iterator = iter(windows)
        for index in range(len(observations)):
            feature_start = time.perf_counter_ns()
            window = next(window_iterator)
            tensor, feature_sha = _tensor(torch, window, actual_device)
            feature_build_ns.append(time.perf_counter_ns() - feature_start)
            if device == "hip":
                torch.cuda.synchronize()
            start = time.perf_counter_ns()
            probabilities = _predict(torch, model, tensor)
            if device == "hip":
                torch.cuda.synchronize()
            prediction_ns.append(time.perf_counter_ns() - start)
            metadata = asdict(window.metadata)
            predictions.append({
                "record_index": index,
                "input_prefix_sha256": prefix_digests[index],
                "model_manifest_sha256": expected_manifest_sha256,
                "feature_tensor_sha256": feature_sha,
                "feature_tensor_encoding": "float32-little-endian-C-order-[1,8,128,1]",
                "binding": metadata.pop("binding"),
                "window": metadata,
                "latest_valid_masks": [channel[-1] for channel in window.features[4:]],
                "probabilities": probabilities,
                "predicted_class_index": max(range(12), key=probabilities.__getitem__),
                "movement_authorized": False,
            })
            final_tensor = tensor
        observed_prefix_total_ns = time.perf_counter_ns() - compute_start
        timings = []
        for _ in range(benchmark_repetitions):
            if device == "hip":
                torch.cuda.synchronize()
            start = time.perf_counter_ns()
            _predict(torch, model, final_tensor)
            if device == "hip":
                torch.cuda.synchronize()
            timings.append(time.perf_counter_ns() - start)
    artifact_pins = {field: manifest[field]["sha256"] for field in ("graph", "weights", "preprocessing", "label_schema")}
    return {
        "schema_version": SCHEMA_VERSION, "status": "completed",
        "task_id": "DEEPEYE-IMPLEMENTATION-20261014", "task_version": 1,
        "contract": {"id": CONTRACT_ID, "revision": CONTRACT_REVISION,
                     "source_commit": CONTRACT_SOURCE_COMMIT,
                     "requirements_sha256": CONTRACT_REQUIREMENTS_SHA256,
                     "design_commit": CONTRACT_DESIGN_COMMIT},
        "profile_id": PROFILE_ID, "source_domain": "geo_replay",
        "scope": "Offline learned public FORCE lithology inference only; no sim_em water/obstacle model, map, planner, control, runtime or physical acceptance",
        "model_id": manifest.get("model_id"), "class_order": manifest["class_order"],
        "pins": {"model_manifest_sha256": expected_manifest_sha256,
                 "public_input_sha256": sha256(input_bytes),
                 "runner_source_sha256": sha256(Path(__file__).read_bytes()),
                 "curve_builder_source_sha256": sha256(curve_source.read_bytes()),
                 **artifact_pins},
        "runtime": {"python": platform.python_version(), "torch": torch.__version__,
                    "requested_device": device, "actual_device": actual_device,
                    "device_name": device_name, "hip_version": torch.version.hip,
                    "threads": torch.get_num_threads(), "deterministic_algorithms": True},
        "predictions": predictions,
        "timing": {"clock": "perf_counter_ns", "model_load_ns": load_ns,
                   "input_read_hash_json_schema_ns": input_validation_ns,
                   "scaler_builder_source_validation_and_load_ns": scaler_load_ns,
                   "runtime_import_ns": runtime_import_ns,
                   "model_asset_preflight_ns": model_asset_preflight_ns,
                   "prefix_window_tensor_and_hash_ns": feature_build_ns,
                   "preprocessing_total_ns": scaler_load_ns + sum(feature_build_ns),
                   "prefix_forward_ns": prediction_ns,
                   "prefix_forward_total_ns": sum(prediction_ns),
                   "observed_prefix_package_total_ns": observed_prefix_total_ns,
                   "package_compute_total_including_benchmark_ns": time.perf_counter_ns() - compute_start,
                   "stage_scope": "input validation includes file read/hash/JSON/schema; preprocessing includes scaler/builder source validation/load plus window/tensor/hash; forwards include softmax/finite checks/host probabilities; package totals include import/model load/record assembly, exclude JSON serialization/output I/O",
                   "benchmark_repetitions": benchmark_repetitions,
                   "benchmark_scope": "repeated final-tensor forward, softmax, finite checks and host probability materialization; excludes input construction, model load and training",
                   "benchmark_forward_ns": timings,
                   "benchmark_median_ns": statistics.median(timings) if timings else None},
        "movement_authorized": False, "motion_bytes": None,
        "A_format_adoption": "not_adopted", "formal_acceptance": "not_run",
    }


def _output_is_fresh(path):
    # lexists rejects a broken symlink too. The final exclusive create remains
    # authoritative if another writer creates the file after this early check.
    if os.path.lexists(path):
        raise PackageError("output_exists", "output must be a new file; existing paths/aliases are not overwritten")
    if not Path(path).parent.is_dir():
        raise PackageError("output_invalid", "output parent directory must already exist")


def write_exclusive(path, data):
    try:
        with open(path, "xb") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise PackageError("output_exists", "output already exists; nothing was overwritten") from exc
    except OSError as exc:
        raise PackageError("output_invalid", str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default=PROFILE_ID)
    parser.add_argument("--device", choices=("cpu", "hip"), default="cpu")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--benchmark-repetitions", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        _output_is_fresh(args.output)
        result = execute(manifest_path=args.manifest,
                         expected_manifest_sha256=args.expected_manifest_sha256,
                         input_path=args.input, expected_input_sha256=args.expected_input_sha256,
                         profile=args.profile, device=args.device, threads=args.threads,
                         benchmark_repetitions=args.benchmark_repetitions)
        encoded = canonical_json(result) + b"\n"
        write_exclusive(args.output, encoded)
    except (PackageError, CurveInputError, RuntimeError) as exc:
        blocked = isinstance(exc, PackageError) and exc.blocked
        result = {"schema_version": SCHEMA_VERSION, "status": "blocked" if blocked else "failed",
                  "code": getattr(exc, "code", "runtime_error" if isinstance(exc, RuntimeError) else "schema_invalid"), "detail": str(exc),
                  "movement_authorized": False, "motion_bytes": None,
                  "formal_acceptance": "not_run"}
        sys.stdout.buffer.write(canonical_json(result) + b"\n")
        return 2 if blocked else 1
    sys.stdout.buffer.write(encoded)
    return 0

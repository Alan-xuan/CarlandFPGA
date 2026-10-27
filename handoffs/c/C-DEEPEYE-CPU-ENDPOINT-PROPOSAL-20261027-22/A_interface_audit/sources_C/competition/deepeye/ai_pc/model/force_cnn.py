"""Fixed FORCE-only CPU CNN and hash-bound, non-executable JSON checkpoint loader.

This learned offline public-lithology component has no motion, scene, water-risk,
board or sim_em_v2 interface. The caller supplies an externally pinned manifest
SHA256. JSON files cannot select Python classes, operators or arbitrary imports.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import torch
from torch import nn

MODEL_ID = "force-cnn-cpu-v1-20261024"
PROFILE_ID = "force_curve_v1"
PREPROCESSING_SHA256 = "cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef"
LABEL_SCHEMA_SHA256 = "0913ff5a59085b47802a9902f23a836f4fa1129700de8e6593840416f4d7beed"
CLASS_ORDER = (30000, 65030, 65000, 80000, 74000, 70000, 70032, 88000, 86000, 99000, 90000, 93000)
GRAPH = [
    {"name": "conv1", "op": "Conv2D", "in_channels": 8, "out_channels": 16, "kernel": [5, 1], "padding": [2, 0]},
    {"name": "relu1", "op": "ReLU"},
    {"name": "pool1", "op": "AvgPool2D", "kernel": [4, 1], "stride": [4, 1]},
    {"name": "conv2", "op": "Conv2D", "in_channels": 16, "out_channels": 24, "kernel": [5, 1], "padding": [2, 0]},
    {"name": "relu2", "op": "ReLU"},
    {"name": "pool2", "op": "AvgPool2D", "kernel": [4, 1], "stride": [4, 1]},
    {"name": "flatten", "op": "Flatten", "start_dim": 1},
    {"name": "head", "op": "Gemm", "in_features": 192, "out_features": 12},
]
_HERE = Path(__file__).resolve().parent
_PRODUCT = _HERE.parents[1]


class FrozenModelError(ValueError):
    """Refused frozen model identity, graph, paths or finite tensor values."""


class ForceCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(8, 16, (5, 1), padding=(2, 0))
        self.relu1 = nn.ReLU()
        self.pool1 = nn.AvgPool2d((4, 1), (4, 1))
        self.conv2 = nn.Conv2d(16, 24, (5, 1), padding=(2, 0))
        self.relu2 = nn.ReLU()
        self.pool2 = nn.AvgPool2d((4, 1), (4, 1))
        self.flatten = nn.Flatten(1)
        self.head = nn.Linear(192, 12)

    def forward(self, values):
        if values.ndim != 4 or tuple(values.shape[1:]) != (8, 128, 1):
            raise FrozenModelError("expected N x 8 x 128 x 1 input")
        values = self.pool1(self.relu1(self.conv1(values)))
        values = self.pool2(self.relu2(self.conv2(values)))
        return self.head(self.flatten(values))


def build_model():
    """Construct the one declared graph; initialization is never a model artifact."""
    return ForceCNN()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _typed_equal(left, right):
    """JSON structural equality without bool/int or float/int aliases."""
    if type(left) is not type(right):
        return False
    if isinstance(right, dict):
        return set(left) == set(right) and all(_typed_equal(left[key], value) for key, value in right.items())
    if isinstance(right, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FrozenModelError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _json(path, expected, limit=2 * 1024 * 1024):
    if not _hex(expected):
        raise FrozenModelError("expected externally pinned lowercase SHA256")
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(limit + 1)
    except OSError as exc:
        raise FrozenModelError("unreadable JSON artifact: " + str(path)) from exc
    if len(raw) > limit or hashlib.sha256(raw).hexdigest() != expected:
        raise FrozenModelError("artifact size or SHA256 mismatch: " + str(path))
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda value: (_ for _ in ()).throw(FrozenModelError("nonfinite JSON constant")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise FrozenModelError("malformed JSON artifact") from exc


def _reference(base, entry, fixed_path=None):
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
        raise FrozenModelError("artifact reference must contain only path and sha256")
    if not isinstance(entry["path"], str) or not _hex(entry["sha256"]):
        raise FrozenModelError("invalid artifact reference")
    relative = Path(entry["path"])
    if relative.is_absolute() or ":" in entry["path"] or "\\" in entry["path"]:
        raise FrozenModelError("artifact reference must use portable relative paths")
    resolved = (base / relative).resolve()
    if fixed_path is None:
        if resolved.parent != base.resolve():
            raise FrozenModelError("graph/weights must be direct manifest siblings")
    elif resolved != fixed_path.resolve():
        raise FrozenModelError("unexpected fixed source/data path")
    return resolved


def load_frozen_model(manifest_path, expected_manifest_sha256, device="cpu"):
    """Load the fixed graph from finite JSON tensors after verifying all pins.

    CPU is the default. Explicit GPU/HIP eligibility is the runner's responsibility;
    this function accepts normal torch.device strings without selecting a backend.
    """
    manifest_path = Path(manifest_path).resolve()
    manifest = _json(manifest_path, expected_manifest_sha256)
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise FrozenModelError("unsupported model manifest schema")
    required = {"schema_version", "model_id", "profile_id", "source_domain", "input_shape", "class_order", "graph", "weights", "preprocessing", "label_schema", "training", "scope"}
    if set(manifest) != required or not isinstance(manifest["training"], dict) or not isinstance(manifest["scope"], dict):
        raise FrozenModelError("manifest requires the exact declared fields and metadata objects")
    if (manifest.get("model_id"), manifest.get("profile_id"), manifest.get("source_domain")) != (MODEL_ID, PROFILE_ID, "geo_replay"):
        raise FrozenModelError("model/domain/profile binding mismatch")
    if not _typed_equal(manifest.get("input_shape"), ["N", 8, 128, 1]) or not _typed_equal(manifest.get("class_order"), list(CLASS_ORDER)):
        raise FrozenModelError("input or official class order mismatch")
    base = manifest_path.parent
    graph = _json(_reference(base, manifest["graph"]), manifest["graph"]["sha256"])
    graph_keys = {"format", "input_shape", "output_shape", "layers", "parameters", "source"}
    if not isinstance(graph, dict) or set(graph) != graph_keys or graph["format"] != "fixed-force-cnn-graph-v1" or type(graph["parameters"]) is not int or graph["parameters"] != 4916:
        raise FrozenModelError("unsupported fixed graph metadata")
    if not _typed_equal(graph.get("layers"), GRAPH) or not _typed_equal(graph.get("input_shape"), ["N", 8, 128, 1]) or not _typed_equal(graph.get("output_shape"), ["N", 12]):
        raise FrozenModelError("graph differs from fixed implementation")
    source_path = _reference(base, graph["source"], _HERE / "force_cnn.py")
    if sha256_file(source_path) != graph["source"]["sha256"]:
        raise FrozenModelError("model source SHA256 mismatch")
    for key, name, fixed_sha in (("preprocessing", "preprocessing.json", PREPROCESSING_SHA256), ("label_schema", "label_schema.json", LABEL_SCHEMA_SHA256)):
        path = _reference(base, manifest[key], _PRODUCT / "data" / name)
        if manifest[key]["sha256"] != fixed_sha:
            raise FrozenModelError("frozen data pin mismatch")
        document = _json(path, fixed_sha)
        if key == "label_schema" and [item["source_code"] for item in document["classes"]] != list(CLASS_ORDER):
            raise FrozenModelError("label schema class order differs")
    model = build_model()
    encoded = _json(_reference(base, manifest["weights"]), manifest["weights"]["sha256"])
    if not isinstance(encoded, dict) or set(encoded) != {"format", "tensors"} or encoded["format"] != "finite-float32-state-dict-json-v1":
        raise FrozenModelError("unsupported weights format")
    expected = model.state_dict()
    tensors = encoded["tensors"]
    if not isinstance(tensors, dict) or set(tensors) != set(expected):
        raise FrozenModelError("unexpected state_dict keys")
    state = {}
    for name, template in expected.items():
        record = tensors[name]
        if not isinstance(record, dict) or set(record) != {"shape", "values"} or not _typed_equal(record["shape"], list(template.shape)):
            raise FrozenModelError("tensor shape mismatch: " + name)
        values = record["values"]
        if not isinstance(values, list) or len(values) != template.numel():
            raise FrozenModelError("invalid tensor values: " + name)
        try:
            valid = all(type(value) in (int, float) and math.isfinite(value) for value in values)
        except OverflowError:
            valid = False
        if not valid:
            raise FrozenModelError("invalid tensor values: " + name)
        tensor = torch.tensor(values, dtype=torch.float32).reshape(template.shape)
        if not bool(torch.isfinite(tensor).all()):
            raise FrozenModelError("float32 overflow: " + name)
        state[name] = tensor
    model.load_state_dict(state, strict=True)
    model.to(torch.device(device)).eval()
    return model, manifest


def export_weights(model, path):
    """Write a non-executable, CPU float32 JSON state dict; used after training."""
    records = {}
    for name, tensor in model.state_dict().items():
        values = tensor.detach().cpu().float()
        if not bool(torch.isfinite(values).all()):
            raise FrozenModelError("refuse nonfinite trained weights")
        records[name] = {"shape": list(values.shape), "values": values.flatten().tolist()}
    document = {"format": "finite-float32-state-dict-json-v1", "tensors": records}
    Path(path).write_text(json.dumps(document, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")

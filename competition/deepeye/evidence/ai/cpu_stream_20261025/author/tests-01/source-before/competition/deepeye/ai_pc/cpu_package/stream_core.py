"""Synchronous bounded transactional FORCE CPU inference, without transport.

Only the fixed learned JSON model/scaler are loaded. Observations arrive as one
raw record per call. C session/epoch identifiers are local bookkeeping, never
A BOOT, capture, observation age, clock, grant or control authority.
"""
from contextlib import contextmanager
import copy
from dataclasses import dataclass, replace
import hashlib
from pathlib import Path
import threading
from typing import NamedTuple

from ai_pc.cpu_package import runner as _runner
from ai_pc.model.curve_input import CurveBinding, CurveInputError, CurveObservation, CurveScaler, CurveWindowBuilder

FIXED_MANIFEST_SHA256 = "0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959"
FIXED_RUNNER_SHA256 = "92114790259b7e35e8bf7b1a0519f0e3f68da52729d08b5b9862c992deae70af"
FIXED_MODEL_SOURCE_SHA256 = "5003427e1ac01e50b612d8f4f9c674c7df352b3942a5cc39978e23bdfbdb1260"
MAX_IDENTIFIER = (1 << 32) - 1
PROFILE_ID = "force_curve_v1"
SOURCE_DOMAIN = "geo_replay"
_HARD = (16384, 8192, 128, 65536, 64 * 1024 * 1024, 1024)
__all__ = ["FrozenForceStream", "StreamLimits", "StreamError", "SessionToken", "StreamResult",
           "StreamState", "EndReceipt", "FIXED_MANIFEST_SHA256"]


class StreamError(ValueError):
    """Bounded rejection; exceptions never imply an accepted observation."""
    def __init__(self, code, detail, *, blocked=False):
        self.code = code
        self.blocked = blocked
        super().__init__(str(detail)[:256])


def _integer(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise StreamError("bounds_invalid", name + " must be an exact bounded integer")
    return value


def _text(value, name, maximum):
    if type(value) is not str or not value:
        raise StreamError("binding_invalid", name + " must be a nonempty exact string")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise StreamError("binding_invalid", name + " is not valid UTF-8") from exc
    if size > maximum:
        raise StreamError("binding_invalid", name + " exceeds UTF-8 byte bound")
    return value


@dataclass(frozen=True)
class StreamLimits:
    """Only reductions of fixed hard limits; counters/bytes are object lifetime."""
    max_record_bytes: int = _HARD[0]
    max_output_bytes: int = _HARD[1]
    max_binding_bytes: int = _HARD[2]
    max_deliveries: int = _HARD[3]
    max_total_bytes: int = _HARD[4]
    max_sessions: int = _HARD[5]

    def __post_init__(self):
        for name, maximum in zip(self.__dataclass_fields__, _HARD):
            _integer(getattr(self, name), name, 512 if name == "max_output_bytes" else 1, maximum)


class Binding(NamedTuple):
    run_id: str
    source_domain: str
    profile_id: str
    preprocessing_sha256: str


class SessionToken(NamedTuple):
    generation: int
    epoch: int
    binding: Binding


class WindowMetadata(NamedTuple):
    latest_sequence: int
    filled_slots: int
    missing_slots: int
    dropped_oldest: int
    accepted_observations: int
    idempotent_repeats: int


class StreamResult(NamedTuple):
    generation: int
    epoch: int
    delivery_index: int
    sequence: int
    binding: Binding
    metadata: WindowMetadata
    latest_valid_masks: tuple
    probabilities: tuple
    predicted_class_index: int
    predicted_source_code: int
    class_order: tuple
    feature_tensor_sha256: str
    feature_tensor_encoding: str
    input_prefix_sha256: str
    session_bytes: int
    artifact_pins: tuple
    encoded: bytes

    @property
    def movement_authorized(self):
        return False

    @property
    def motion_bytes(self):
        return None


class StreamState(NamedTuple):
    active_generation: object
    active_epoch: object
    highest_generation: int
    highest_epoch: int
    sessions_started: int
    lifecycle_transitions: int
    lifetime_deliveries: int
    lifetime_bytes: int
    session_deliveries: int
    session_bytes: int
    prefix_sha256: object
    latest_result_sha256: object


class EndReceipt(NamedTuple):
    generation: int
    epoch: int
    session_deliveries: int
    session_bytes: int
    input_prefix_sha256: str
    encoded: bytes

    @property
    def movement_authorized(self):
        return False


@dataclass(frozen=True)
class _Active:
    token: SessionToken
    builder: object
    prefix: object
    deliveries: int = 0
    total_bytes: int = 0
    latest: object = None


@dataclass(frozen=True)
class _Committed:
    active: object = None
    highest_generation: int = 0
    highest_epoch: int = -1
    sessions_started: int = 0
    transitions: int = 0
    deliveries: int = 0
    total_bytes: int = 0


def _encode(payload, maximum):
    raw = _runner.canonical_json(payload) + b"\n"
    if len(raw) > maximum:
        raise StreamError("output_limit", "bounded result serialization exceeds max_output_bytes")
    return raw


def _result_payload(result):
    return {"schema_version": 1, "scope": "C synchronous offline FORCE lithology stream; no A format adoption or runtime authority",
            "generation": result.generation, "epoch": result.epoch,
            "delivery_index": result.delivery_index, "sequence": result.sequence,
            "binding": result.binding._asdict(), "window": result.metadata._asdict(),
            "latest_valid_masks": result.latest_valid_masks, "probabilities": result.probabilities,
            "predicted_class_index": result.predicted_class_index,
            "predicted_source_code": result.predicted_source_code, "class_order": result.class_order,
            "feature_tensor_sha256": result.feature_tensor_sha256,
            "feature_tensor_encoding": result.feature_tensor_encoding,
            "input_prefix_sha256": result.input_prefix_sha256, "session_bytes": result.session_bytes,
            "artifact_pins": dict(result.artifact_pins), "movement_authorized": False,
            "motion_bytes": None, "formal_acceptance": "incomplete"}


class FrozenForceStream:
    """One fixed model/scaler; transactional bounded active128 history.

    No public method accepts a model, callback, external result, file of
    observations, clock, output path or transport. The object is synchronous;
    a local nonblocking lock rejects overlapping/reentrant operations.
    """
    __slots__ = ("__lock", "__limits", "__model", "__torch", "__scaler", "__class_order", "__pins", "__committed")

    def __init__(self, manifest_path=None, expected_manifest_sha256=FIXED_MANIFEST_SHA256, *,
                 profile=PROFILE_ID, device="cpu", limits=None):
        if type(profile) is not str or profile != PROFILE_ID:
            if type(profile) is str and profile == "sim_em_v2":
                raise StreamError("sim_em_model_missing", "trained sim_em_v2 model/scales absent; FORCE is not remapped", blocked=True)
            raise StreamError("profile_invalid", "only force_curve_v1 is supported")
        if type(device) is not str or device != "cpu":
            raise StreamError("device_invalid", "this core is explicit CPU only; no fallback")
        if type(expected_manifest_sha256) is not str or expected_manifest_sha256 != FIXED_MANIFEST_SHA256:
            raise StreamError("hash_mismatch", "only the original fixed learned model manifest is allowed")
        if limits is None:
            limits = StreamLimits()
        if type(limits) is not StreamLimits:
            raise StreamError("bounds_invalid", "limits must be immutable StreamLimits")
        limits = replace(limits)  # detach even the caller's frozen configuration object
        self.__lock = threading.Lock()
        self.__limits = limits
        product = Path(__file__).resolve().parents[2]
        if manifest_path is None:
            manifest_path = product / "ai_pc/cpu_model/force_v1/model_manifest.json"
        if type(manifest_path) not in (str, type(Path())):
            raise StreamError("manifest_invalid", "manifest_path must be an exact string or native Path")
        try:
            _runner.read_pinned(Path(_runner.__file__), FIXED_RUNNER_SHA256)
            _runner.read_pinned(product / "ai_pc/model/curve_input.py", _runner.FIXED_CURVE_BUILDER_SHA256)
            _runner.read_pinned(product / "ai_pc/model/force_cnn.py", FIXED_MODEL_SOURCE_SHA256)
            raw_manifest = _runner.read_pinned(manifest_path, FIXED_MANIFEST_SHA256, missing_code="model_missing", limit=2 * 1024 * 1024)
            manifest = _runner.strict_json(raw_manifest)
            for field in ("graph", "weights", "preprocessing", "label_schema"):
                path = _runner._reference(manifest_path, manifest, field)
                _runner.read_pinned(path, manifest[field]["sha256"], missing_code="model_missing" if field in ("graph", "weights") else "asset_missing")
            preprocessing = _runner.read_pinned(product / "data/preprocessing.json", _runner.FIXED_PREPROCESSING_SHA256)
            self.__scaler = CurveScaler.from_document_bytes(preprocessing, expected_sha256=_runner.FIXED_PREPROCESSING_SHA256)
            import torch
            from ai_pc.model.force_cnn import load_frozen_model
            torch.set_num_threads(4)
            torch.use_deterministic_algorithms(True)
            self.__model, loaded = load_frozen_model(manifest_path, FIXED_MANIFEST_SHA256, device="cpu")
            if loaded != manifest:
                raise StreamError("model_invalid", "loader manifest differs from verified snapshot")
            self.__model.eval()
            self.__torch = torch
        except StreamError:
            raise
        except _runner.PackageError as exc:
            raise StreamError(exc.code, str(exc), blocked=exc.blocked) from exc
        except (ImportError, ModuleNotFoundError, FileNotFoundError) as exc:
            raise StreamError("model_missing", str(exc), blocked=True) from exc
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise StreamError("model_invalid", str(exc)) from exc
        self.__class_order = tuple(manifest["class_order"])
        self.__pins = tuple(sorted({"model_manifest_sha256": FIXED_MANIFEST_SHA256,
                                    "runner_source_sha256": FIXED_RUNNER_SHA256,
                                    "builder_source_sha256": _runner.FIXED_CURVE_BUILDER_SHA256,
                                    "model_source_sha256": FIXED_MODEL_SOURCE_SHA256,
                                    **{field: manifest[field]["sha256"] for field in ("graph", "weights", "preprocessing", "label_schema")}}.items()))
        self.__committed = _Committed()

    @contextmanager
    def __guard(self):
        if not self.__lock.acquire(blocking=False):
            raise StreamError("busy", "synchronous operation already active; reentry/concurrency rejected")
        try:
            yield
        finally:
            self.__lock.release()

    def __active(self, token):
        active = self.__committed.active
        if active is None:
            raise StreamError("inactive_session", "explicit start_session required")
        if token is not active.token:
            raise StreamError("stale_session", "token must be the exact active token returned by this object")
        return active

    def start_session(self, *, generation, epoch, run_id):
        with self.__guard():
            state = self.__committed
            if state.active is not None:
                raise StreamError("active_session", "end the active session explicitly before starting another")
            _integer(generation, "generation", 1, MAX_IDENTIFIER)
            _integer(epoch, "epoch", 0, MAX_IDENTIFIER)
            if generation <= state.highest_generation or epoch <= state.highest_epoch:
                raise StreamError("stale_session", "both generation and epoch must increase strictly; no wrap/reuse")
            if state.sessions_started >= self.__limits.max_sessions or state.transitions >= 2 * self.__limits.max_sessions:
                raise StreamError("lifecycle_limit", "object lifetime session/transition limit reached")
            run_id = _text(run_id, "run_id", self.__limits.max_binding_bytes)
            binding = Binding(run_id, SOURCE_DOMAIN, PROFILE_ID, _runner.FIXED_PREPROCESSING_SHA256)
            token = SessionToken(generation, epoch, binding)
            builder = CurveWindowBuilder(scaler=self.__scaler,
                                         binding=CurveBinding(run_id=run_id, source_domain=SOURCE_DOMAIN,
                                                              preprocessing_sha256=_runner.FIXED_PREPROCESSING_SHA256,
                                                              profile_id=PROFILE_ID))
            active = _Active(token, builder, hashlib.sha256())
            self.__committed = replace(state, active=active, highest_generation=generation,
                                       highest_epoch=epoch, sessions_started=state.sessions_started + 1,
                                       transitions=state.transitions + 1)
            return token

    def end_session(self, token):
        with self.__guard():
            active = self.__active(token)
            state = self.__committed
            if state.transitions >= 2 * self.__limits.max_sessions:
                raise StreamError("lifecycle_limit", "object lifetime transition limit reached")
            payload = {"generation": token.generation, "epoch": token.epoch,
                       "session_deliveries": active.deliveries, "session_bytes": active.total_bytes,
                       "input_prefix_sha256": active.prefix.hexdigest(), "movement_authorized": False,
                       "scope": "C local end receipt; not A lifecycle or stop acknowledgement"}
            encoded = _encode(payload, self.__limits.max_output_bytes)
            receipt = EndReceipt(token.generation, token.epoch, active.deliveries,
                                 active.total_bytes, active.prefix.hexdigest(), encoded)
            self.__committed = replace(state, active=None, transitions=state.transitions + 1)
            return receipt

    def observe(self, token, raw):
        with self.__guard():
            active = self.__active(token)
            state = self.__committed
            limits = self.__limits
            if type(raw) is not bytes or not 1 <= len(raw) <= limits.max_record_bytes:
                raise StreamError("record_limit", "one immutable nonempty bounded raw bytes record required")
            if state.deliveries >= limits.max_deliveries or state.total_bytes + len(raw) > limits.max_total_bytes:
                raise StreamError("stream_limit", "object lifetime delivery/raw-byte limit reached")
            try:
                observation = CurveObservation.from_mapping(_runner.strict_json(raw))
                _text(observation.binding.run_id, "run_id", limits.max_binding_bytes)
                if observation.binding != active.builder.binding:
                    raise StreamError("binding_invalid", "run/source/profile/preprocessing must match the explicitly active session")
                # Pinned builder fields other than the bounded deque are frozen
                # objects, immutable tuples or scalar counters. Never mutate the
                # committed deque, hash or counter values during trial work.
                trial = copy.copy(active.builder)
                trial._slots = active.builder._slots.copy()
                trial.observe(observation)
                window = trial.snapshot()
                duplicate = window.metadata.accepted_observations == active.builder._accepted
                if duplicate:
                    if active.latest is None:
                        raise StreamError("internal_invalid", "duplicate without an earlier committed result")
                    probabilities = active.latest.probabilities
                    feature_sha = active.latest.feature_tensor_sha256
                else:
                    with self.__torch.inference_mode():
                        tensor, feature_sha = _runner._tensor(self.__torch, window, "cpu")
                        probabilities = tuple(_runner._predict(self.__torch, self.__model, tensor))
                metadata = WindowMetadata(window.metadata.latest_sequence, window.metadata.filled_slots,
                                          window.metadata.missing_slots, window.metadata.dropped_oldest,
                                          window.metadata.accepted_observations, window.metadata.idempotent_repeats)
                prefix = active.prefix.copy()
                prefix.update(raw)  # exact accepted delivery bytes, including whitespace/newline
                predicted = max(range(12), key=probabilities.__getitem__)
                result = StreamResult(token.generation, token.epoch, active.deliveries,
                                      observation.sequence, token.binding, metadata,
                                      tuple(channel[-1] for channel in window.features[4:]), probabilities,
                                      predicted, self.__class_order[predicted], self.__class_order,
                                      feature_sha, "float32-little-endian-C-order-[1,8,128,1]",
                                      prefix.hexdigest(), active.total_bytes + len(raw), self.__pins, b"")
                encoded = _encode(_result_payload(result), limits.max_output_bytes)
                result = result._replace(encoded=encoded)
                new_active = _Active(active.token, trial, prefix, active.deliveries + 1,
                                     active.total_bytes + len(raw), result)
                committed = replace(state, active=new_active, deliveries=state.deliveries + 1,
                                    total_bytes=state.total_bytes + len(raw))
            except StreamError:
                raise
            except _runner.PackageError as exc:
                raise StreamError(exc.code, str(exc), blocked=exc.blocked) from exc
            except CurveInputError as exc:
                raise StreamError("schema_invalid", str(exc)) from exc
            except (RuntimeError, ValueError, TypeError, OverflowError, KeyError) as exc:
                raise StreamError("transaction_failed", str(exc)) from exc
            self.__committed = committed  # the sole observation-state commit
            return result

    def latest_result(self, token):
        with self.__guard():
            return self.__active(token).latest

    def state(self):
        with self.__guard():
            state = self.__committed
            active = state.active
            return StreamState(active.token.generation if active else None,
                               active.token.epoch if active else None,
                               state.highest_generation, state.highest_epoch,
                               state.sessions_started, state.transitions, state.deliveries, state.total_bytes,
                               active.deliveries if active else 0, active.total_bytes if active else 0,
                               active.prefix.hexdigest() if active else None,
                               hashlib.sha256(active.latest.encoded).hexdigest() if active and active.latest else None)

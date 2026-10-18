"""Bounded, non-authorizing A-revision-1 model_candidate -> motion_request adapter.

The only serialized output is the exact A request whitelist. Opaque mailbox
payloads MUST pass ``submit``; a mailbox result is not a validated target. This
helper does no I/O, clock reading, quantization, grant construction or hardware
access. It accepts already quantized integer targets and checks them again.

One instance has one immutable, already negotiated seven-field context and one
session lifetime. Candidate IDs are global to that session, never C generation
ordinals. The caller must maintain one allocator/instance and must not recreate
it to reset high-water marks in an existing session. STOP also consumes an ID.
Command sequence exhaustion requires a new session; it never wraps.

``register_observation`` records a trusted bridge's *sent* TELEM mapping, not an
observation inferred from model output. sent_ordinal, wire sample sequence and
extended acquisition tick are distinct. Tick wrapping is explicit; seq16 wrap
requires a new session. Registration is structural, not source authentication.

For motion the caller must inject a trusted ``RuntimeVerifier``. It must verify
the actual measured clock/anchor/holdover records, authenticated BOOT/source
provenance, source and model process liveness, and applicable link/slot gates
against the entire immutable ``RuntimeCheck`` on EVERY call. A hash, number or
boolean cannot substitute for that verification. No verifier is installed by
default. Missing/failing verification returns blocked with no motion bytes.
The transport owner must act on ``must_stop``; ``safe_stop`` is available with
no observation or runtime proof. A's schema/ACL/world authority still validates
and decides execution. Every result has movement_authorized=False.

Original issue, sample interval and expiry are kept in the returned audit,
outside A's request bytes. Candidate replay is rejected, so a retry cannot
renew them. This request-stage expiry is only an upper bound; A's HIL capture
and remaining-TTL checks can tighten it, never extend it.

Verifier callbacks may call public methods, including safety STOP. Every new
observation, valid candidate retirement or valid STOP replaces a constant-size
state-generation token. A submit whose verifier observed a newer generation
returns blocked without emitting its older request or reverting newer state.
Reads, exact observation duplicates and rejected malformed calls do not replace
that token. Verifier-visible context, observation and timing are detached audit
snapshots; retaining or forcibly mutating them cannot rewrite broker state or
the original timing returned in a decision. This remains a single-owner helper,
not a synchronization primitive for concurrent threads.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, localcontext
from hashlib import sha256
import json
import re
from typing import Protocol

MAX_MESSAGE_BYTES = 16384
MAX_NESTING_DEPTH = 16
MAX_OBSERVATIONS = 4
INT63_MAX = (1 << 63) - 1
UINT64_MAX = (1 << 64) - 1
NS_PER_MS = 1_000_000
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_CONTEXT_KEYS = frozenset(("session", "config_epoch", "boot_sha256",
                           "transport_profile_id", "source_id", "topology_id",
                           "acquisition_profile_id"))
_CANDIDATE_KEYS = frozenset(("schema_version", "context", "kind", "candidate_id",
                             "model_sha256", "observation",
                             "completed_monotonic_ns", "target"))
_TARGET_KEYS = frozenset(("action", "yaw_q", "pitch_q", "speed_code", "duration_ms"))


class MotionRequestError(ValueError):
    """Invalid input, replay, clock regression or context mismatch; emits nothing."""


class RuntimeBlocked(ValueError):
    """Trusted runtime verifier could not prove the required runtime gates."""


def _integer(value, name, maximum=INT63_MAX, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise MotionRequestError(f"{name} must be integer {minimum}..{maximum}")
    return value


def _object(value, keys, name):
    if type(value) is not dict or value.keys() != keys:
        raise MotionRequestError(f"{name} must have exactly the allowed keys")
    return value


def _hex(value, name):
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise MotionRequestError(f"{name} must be lowercase SHA256 hex")
    return value


@dataclass(frozen=True)
class HostContext:
    session: int
    config_epoch: int
    boot_sha256: str
    transport_profile_id: int
    source_id: int
    topology_id: int
    acquisition_profile_id: int

    def __post_init__(self):
        _integer(self.session, "session", (1 << 32) - 1)
        _integer(self.config_epoch, "config_epoch", 255)
        _hex(self.boot_sha256, "boot_sha256")
        _integer(self.transport_profile_id, "transport_profile_id", 2, 1)
        _integer(self.source_id, "source_id", 4, 1)
        _integer(self.topology_id, "topology_id", 3, 1)
        _integer(self.acquisition_profile_id, "acquisition_profile_id", 3, 1)

    @classmethod
    def from_mapping(cls, document):
        return cls(**_object(document, _CONTEXT_KEYS, "context"))

    def as_dict(self):
        HostContext.__post_init__(self)
        return {name: getattr(self, name) for name in _CONTEXT_KEYS}


@dataclass(frozen=True)
class SentObservation:
    """Immutable bridge mapping; native EM time is deliberately not represented.

    sample_sequence is the extended wire header sequence, NOT sent_ordinal.
    In revision 1 it must still fit uint16 (new session before sequence wrap).
    sample_tick_ms and anchor_tick_ms are extended same-session board ticks;
    their signed separation must be strictly less than the uint32 half range.
    The trusted verifier must independently establish the anchor and interval.
    """
    context: HostContext
    sent_ordinal: int
    sample_sequence: int
    sample_tick_ms: int
    anchor_tick_ms: int
    sample_lower_ns: int
    sample_upper_ns: int

    def __post_init__(self):
        if type(self.context) is not HostContext:
            raise MotionRequestError("observation needs a HostContext")
        HostContext.__post_init__(self.context)
        _integer(self.sent_ordinal, "sent_ordinal", UINT64_MAX)
        _integer(self.sample_sequence, "sample_sequence", UINT64_MAX)
        if self.sample_sequence > 65535:
            raise MotionRequestError("sample sequence exhausted: new session required")
        _integer(self.sample_tick_ms, "sample_tick_ms", UINT64_MAX)
        _integer(self.anchor_tick_ms, "anchor_tick_ms", UINT64_MAX)
        if abs(self.sample_tick_ms - self.anchor_tick_ms) >= 1 << 31:
            raise MotionRequestError("sample/anchor tick separation is ambiguous")
        _integer(self.sample_lower_ns, "sample_lower_ns")
        _integer(self.sample_upper_ns, "sample_upper_ns")
        if self.sample_lower_ns > self.sample_upper_ns:
            raise MotionRequestError("sample interval is reversed")

    @property
    def wire_tick_ms(self):
        return self.sample_tick_ms & 0xFFFFFFFF

    @property
    def wire_observed_seq(self):
        return self.sample_sequence  # checked; never sent_ordinal % 65536

    def key(self):
        SentObservation.__post_init__(self)
        return {"context": HostContext.as_dict(self.context), "observed_seq": self.wire_observed_seq}


def _observation_copy(observation):
    """Retain/return detached frozen values, never a caller's mutable alias."""
    SentObservation.__post_init__(observation)
    return SentObservation(HostContext.from_mapping(HostContext.as_dict(observation.context)),
                           observation.sent_ordinal, observation.sample_sequence,
                           observation.sample_tick_ms, observation.anchor_tick_ms,
                           observation.sample_lower_ns, observation.sample_upper_ns)


@dataclass(frozen=True)
class OriginalTiming:
    first_issue_ns: int
    original_duration_ms: int
    sample_lower_ns: int
    sample_upper_ns: int
    deadline_ns: int


@dataclass(frozen=True)
class RuntimeCheck:
    context: HostContext
    observation: SentObservation
    candidate_id: int
    model_sha256: str
    completed_ns: int
    now_ns: int
    target: tuple[int, int, int, int, int]  # action,yaw,pitch,speed,duration
    timing: OriginalTiming


class RuntimeVerifier(Protocol):
    def verify_motion(self, check: RuntimeCheck) -> None:
        """Verify actual runtime evidence or raise; no truth/oracle inputs."""
        ...


@dataclass(frozen=True)
class RequestDecision:
    request_bytes: bytes | None
    must_stop: bool
    reason: str
    candidate_id: int | None
    command_seq: int | None
    candidate_sha256: str | None = None
    timing: OriginalTiming | None = None

    @property
    def movement_authorized(self):
        return False


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MotionRequestError("duplicate JSON key")
        result[key] = value
    return result


def _forbidden_number(_):
    raise MotionRequestError("only integer JSON numbers are accepted")


def _parse(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MESSAGE_BYTES:
        raise MotionRequestError("candidate must be bounded immutable JSON bytes")
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (123, 91):
            depth += 1
            if depth > MAX_NESTING_DEPTH:
                raise MotionRequestError("candidate nesting exceeds bound")
        elif byte in (125, 93):
            depth -= 1
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_float=_forbidden_number,
                              parse_constant=_forbidden_number)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise MotionRequestError("invalid strict candidate JSON") from error
    return _object(document, _CANDIDATE_KEYS, "model_candidate")


def _target(document, profile):
    target = _object(document, _TARGET_KEYS, "target")
    action = _integer(target["action"], "action", 1)
    yaw = _integer(target["yaw_q"], "yaw_q", 15000, -15000)
    pitch = _integer(target["pitch_q"], "pitch_q", 15000, -15000)
    speed = _integer(target["speed_code"], "speed_code", 20)
    duration = _integer(target["duration_ms"], "duration_ms", 3000 if profile == 1 else 12000)
    if action == 0:
        if any((yaw, pitch, speed, duration)):
            raise MotionRequestError("STOP requires every target field zero")
    elif duration == 0:
        raise MotionRequestError("SET_TARGET requires positive duration")
    # Independent integer check of A's postquantization combined-curvature ROM.
    with localcontext() as decimal_context:
        decimal_context.prec = 48
        pi = Decimal("3.14159265358979323846264338327950288419716939937510")
        step = Decimal("0.0125") if profile == 1 else Decimal("0.0001")
        limit = int(((speed * step * 180000 / (2 * pi)) ** 2)
                    .to_integral_value(rounding=ROUND_FLOOR))
    if yaw * yaw + pitch * pitch > limit:
        raise MotionRequestError("postquantization combined curvature exceeds limit")
    return (action, yaw, pitch, speed, duration)


class MotionRequestAdapter:
    """Single-session, single-owner adapter; at most four observation records.

    Strict input errors raise without returning request bytes. A valid candidate
    is retired even when blocked, so neither late verification nor retry can
    revive it. STOP is the only output possible without runtime verification.
    """
    def __init__(self, *, context: HostContext, verifier: RuntimeVerifier | None = None):
        if type(context) is not HostContext:
            raise MotionRequestError("adapter needs exact HostContext")
        HostContext.__post_init__(context)
        self._context = context
        self._context_snapshot = tuple(sorted(HostContext.as_dict(context).items()))
        self._verifier = verifier
        self._observations = deque(maxlen=MAX_OBSERVATIONS)
        self._observation_high = None
        self._candidate_high = -1
        self._next_command_seq = 0
        self._last_now_ns = None
        # Identity tokens do not wrap and need no per-operation history ledger.
        self._state_generation = object()

    @property
    def context(self):
        self._validate_context()
        return HostContext.from_mapping(HostContext.as_dict(self._context))

    @property
    def retained_observations(self):
        self._validate_context()
        return tuple(_observation_copy(item) for item in self._observations)

    def _validate_context(self):
        HostContext.__post_init__(self._context)
        if tuple(sorted(HostContext.as_dict(self._context).items())) != self._context_snapshot:
            raise MotionRequestError("negotiated context was mutated")

    def register_observation(self, observation: SentObservation):
        self._validate_context()
        if type(observation) is not SentObservation:
            raise MotionRequestError("expected SentObservation")
        # Recheck even a forged/mutated frozen dataclass at the public boundary.
        SentObservation.__post_init__(observation)
        if observation.context != self._context:
            raise MotionRequestError("observation context mismatch")
        for retained in self._observations:
            if observation == retained:
                return
        previous = self._observation_high
        if previous is not None and (
            observation.sent_ordinal <= previous.sent_ordinal
            or observation.sample_sequence <= previous.sample_sequence
            or observation.sample_tick_ms <= previous.sample_tick_ms
            or observation.sample_lower_ns < previous.sample_lower_ns
            or observation.anchor_tick_ms < previous.anchor_tick_ms
        ):
            raise MotionRequestError("observation identity/tick/anchor regression")
        snapshot = _observation_copy(observation)
        self._observations.append(snapshot)
        self._observation_high = snapshot
        self._state_generation = object()

    def _clock(self, now_ns):
        now = _integer(now_ns, "now_ns")
        if self._last_now_ns is not None and now < self._last_now_ns:
            raise MotionRequestError("host monotonic clock regressed")
        return now

    def _blocked(self, reason, candidate_id=None, digest=None, timing=None):
        return RequestDecision(None, True, reason, candidate_id, None, digest, timing)

    def _emit(self, candidate_id, observation, issue_ns, target, digest=None, timing=None):
        self._validate_context()
        if self._next_command_seq > 65535:
            return self._blocked("command_sequence_exhausted:new_session_required",
                                 candidate_id, digest, timing)
        sequence = self._next_command_seq
        document = {"schema_version": 1, "context": HostContext.as_dict(self._context),
                    "kind": "motion_request", "candidate_id": candidate_id,
                    "command_seq": sequence, "observation": observation,
                    "host_issue_monotonic_ns": issue_ns,
                    "target": dict(zip(("action", "yaw_q", "pitch_q", "speed_code",
                                        "duration_ms"), target))}
        raw = json.dumps(document, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
        self._next_command_seq += 1
        return RequestDecision(raw, target[0] == 0, "stop" if target[0] == 0 else "request",
                               candidate_id, sequence, digest, timing)

    def submit(self, candidate_bytes: bytes, *, host_issue_ns: int, now_ns: int):
        """Validate, retire and project one candidate. Never accepts opaque objects.

        host_issue_ns is the ORIGINAL planned first issue, not a refreshed retry
        time. completed <= issue <= now. Late calls retain this issue and expire
        at the original deadline. This API is not a transport retry API.
        """
        self._validate_context()
        now = self._clock(now_ns)
        issue = _integer(host_issue_ns, "host_issue_ns")
        document = _parse(candidate_bytes)
        if type(document["schema_version"]) is not int or document["schema_version"] != 1:
            raise MotionRequestError("unsupported schema_version")
        if document["kind"] != "model_candidate":
            raise MotionRequestError("expected model_candidate")
        context = HostContext.from_mapping(document["context"])
        if context != self._context:
            raise MotionRequestError("candidate context mismatch")
        identity = _integer(document["candidate_id"], "candidate_id")
        if identity <= self._candidate_high:
            raise MotionRequestError("candidate identity reused or regressed")
        model_hash = _hex(document["model_sha256"], "model_sha256")
        completed = _integer(document["completed_monotonic_ns"], "completed_monotonic_ns")
        if not completed <= issue <= now:
            raise MotionRequestError("require completed <= original issue <= now")
        target = _target(document["target"], context.transport_profile_id)
        observation_key = document["observation"]
        if observation_key is not None:
            _object(observation_key, frozenset(("context", "observed_seq")), "observation")
            nested = HostContext.from_mapping(observation_key["context"])
            if nested != context:
                raise MotionRequestError("nested observation context mismatch")
            _integer(observation_key["observed_seq"], "observed_seq", 65535)
        if target[0] == 1 and observation_key is None:
            raise MotionRequestError("SET_TARGET needs a same-context observation")
        self._last_now_ns = now
        self._candidate_high = identity
        # Retirement is meaningful even if this valid candidate is later blocked.
        self._state_generation = object()
        digest = sha256(candidate_bytes).hexdigest()
        if target[0] == 0:
            return self._emit(identity, observation_key, issue, target, digest)
        observation = next((item for item in self._observations
                            if item.wire_observed_seq == observation_key["observed_seq"]), None)
        if observation is None:
            return self._blocked("observation_missing_or_retired", identity, digest)
        if observation.sample_lower_ns > completed:
            return self._blocked("completion_precedes_sample", identity, digest)
        age_cap = 1_500_000_000 if context.transport_profile_id == 1 else 12_000_000_000
        deadline = min(issue + target[4] * NS_PER_MS, observation.sample_lower_ns + age_cap)
        if deadline > INT63_MAX:
            return self._blocked("original_deadline_unrepresentable", identity, digest)
        timing = OriginalTiming(issue, target[4], observation.sample_lower_ns,
                                observation.sample_upper_ns, deadline)
        if now >= deadline:
            return self._blocked("original_deadline_expired", identity, digest, timing)
        if self._verifier is None:
            return self._blocked("runtime_verifier_missing", identity, digest, timing)
        check_timing = OriginalTiming(timing.first_issue_ns, timing.original_duration_ms,
                                      timing.sample_lower_ns, timing.sample_upper_ns,
                                      timing.deadline_ns)
        check_context = HostContext.from_mapping(HostContext.as_dict(context))
        check = RuntimeCheck(check_context, _observation_copy(observation), identity,
                             model_hash, completed, now, target, check_timing)
        generation = self._state_generation
        verified = False
        try:
            verified = self._verifier.verify_motion(check) is None
        except Exception:
            pass
        # A callback may emit STOP, retire a newer candidate (even a blocked one),
        # or replace observation history. Never emit the stale outer operation.
        if self._state_generation is not generation:
            return self._blocked("superseded_during_verification", identity, digest, timing)
        if not verified:
            return self._blocked("runtime_evidence_unverified", identity, digest, timing)
        return self._emit(identity, observation.key(), issue, target, digest, timing)

    def safe_stop(self, *, now_ns: int):
        """Fresh all-zero STOP with null observation, independent of stale mailboxes."""
        self._validate_context()
        now = self._clock(now_ns)
        self._last_now_ns = now
        # Keep STOP callable during verification, including exhaustion outcomes.
        self._state_generation = object()
        if self._candidate_high == INT63_MAX:
            return self._blocked("candidate_identity_exhausted:new_session_required")
        self._candidate_high += 1
        return self._emit(self._candidate_high, None, now, (0, 0, 0, 0, 0))

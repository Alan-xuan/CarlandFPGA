"""C05 bounded latest-completed command mailbox for the PC control broker.

Frozen decisions implemented here (director broker-foundation-plan.json):

* The mailbox retains at most one latest-completed candidate, ordered by the
  caller-assigned ``sent_ordinal`` of the sent TELEM observation it
  references and then by its generation ordinal - never by completion
  arrival.  A result for an older observation cannot overwrite a newer
  completed result; a stale late completion is ignored.
* A candidate references one of at most four retained legal sent TELEM
  observations of the exact run/session/profile/epoch binding.  Observation
  identity is the full reference: the mandatory immutable uint64
  ``sent_ordinal`` (caller-host monotonic identity, not a new A wire field),
  the diagnostic string id, the sample tick and the sample-time lower bound.
  Newly registered observations must strictly increase that ordinal; an
  exact active duplicate is idempotent and any evicted ordinal never
  re-registers (no wrap or restart within a binding).  Diagnostic ids may
  recur only after eviction, with a strictly greater ordinal and tick, as a
  distinct reference.  Sample ticks must strictly increase and sample-time
  lower bounds must not regress; sequence wrap needs a new session.  An old
  reference or candidate still fails.
* The ordering high-water key (sent ordinal, generation ordinal), its
  payload digest and completion metadata persist independent of the pending
  candidate's lifetime: a smaller key is always stale, including after
  consumption, expiry or eviction, an identical redelivery never requeues a
  consumed or dropped candidate, and the same key with a different payload
  digest is an error.  While the candidate is pending an identical
  duplicate may retain the earliest valid completion; a higher generation
  of a still-retained observation is a new candidate and never renews
  observation age.  Payloads are immutable opaque bytes: no truth fields,
  no scene access, no clock reads.
* Consumption requires the candidate to have completed by the absolute slot
  deadline supplied by the scheduler and the referenced observation to still
  be within its age limit at consumption (expired at age >= limit, measured
  from the referenced sample-time lower bound).  The caller supplied
  ``age_limit_ns`` may only tighten the frozen profile bound: it must be
  strictly positive and must not exceed the frozen
  ``observation_age_limit_ns`` of the bound profile, so no caller argument
  can silently widen the frozen age cap.  A candidate that missed the
  current slot deadline is retained for the next legitimate slot while it
  stays fresh; an aged-out, evicted or missing candidate yields no
  consumption.  A grant authorises a slot only and never renews observation
  age; returning a candidate is NOT permission to move -
  ``Consumption.movement_authorized`` is always False, and current slot
  grants plus independent motion authorisation live outside this pure
  helper.
* Consumption keeps one constant-size caller-clock high-water scalar.  Every
  structurally valid consume call (nonnegative integer ``consumed_at_ns``
  and ``slot_deadline_ns``, valid caller age cap) must not regress below the
  greatest previously accepted consume clock; equality is allowed.  The new
  clock is recorded before the pending candidate is inspected, so empty,
  evicted, aged-out, missed-slot and future-completion outcomes establish
  the observed clock too.  Malformed arguments change no state; a regressed
  clock raises :class:`BrokerError` and preserves the pending candidate, the
  high-water ordering state and the retained history.  No clock is ever read
  internally, no per-call history is kept, nothing resets implicitly and a
  different binding needs a new mailbox; a future completion may still be
  retried at an equal or later valid clock, never earlier.
* Consumption is fail closed in two documented forms.  Clock-inconsistent
  inputs raise :class:`BrokerError`: a consume clock regressing below the
  last accepted consume clock or below the referenced sample-time lower
  bound, a completion in the future relative to the consumed time, or a
  completion before the referenced sample-time lower bound.  Scheduling
  outcomes without a usable result return a :class:`Consumption` with no
  candidate and ``reason != CONSUME_OK`` (empty, evicted, aged-out,
  completed after the slot deadline).  A completion later than the consumed
  time is never returned.
* ``sample_tick_ms`` is the TELEM last-included ADC sample tick of its
  aggregation window.  The native EM acquisition time is not present in the
  legal bytes and is never accepted or invented here.

This module performs no I/O: no clock reads, no network, no board access.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256

from ai_pc.control_broker.deadlines import (
    BrokerError,
    PROFILE_LIMITS,
    require_nonneg_int,
    require_uint64,
)

__all__ = [
    "MAX_SENT_OBSERVATIONS",
    "OFFER_ACCEPTED",
    "OFFER_DUPLICATE_IGNORED",
    "OFFER_STALE_IGNORED",
    "CONSUME_OK",
    "CONSUME_EMPTY",
    "CONSUME_COMPLETED_AFTER_SLOT_DEADLINE",
    "CONSUME_OBSERVATION_AGE_EXCEEDED",
    "CONSUME_OBSERVATION_EVICTED",
    "BrokerBinding",
    "ObservationRef",
    "Candidate",
    "Consumption",
    "ControlMailbox",
]

MAX_SENT_OBSERVATIONS = 4

OFFER_ACCEPTED = "accepted"
OFFER_DUPLICATE_IGNORED = "duplicate_ignored"
OFFER_STALE_IGNORED = "stale_ignored"

CONSUME_OK = "ok"
CONSUME_EMPTY = "empty"
CONSUME_COMPLETED_AFTER_SLOT_DEADLINE = "completed_after_slot_deadline"
CONSUME_OBSERVATION_AGE_EXCEEDED = "observation_age_exceeded"
CONSUME_OBSERVATION_EVICTED = "observation_evicted"


@dataclass(frozen=True)
class BrokerBinding:
    """Exact run/session/profile/epoch binding of one broker session."""

    run_id: str
    session_id: str
    profile: str
    epoch: int

    def validate(self) -> None:
        """Reject non-conforming or forged binding identifiers."""
        for name in ("run_id", "session_id", "profile"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise BrokerError(f"binding {name} must be a non-empty string")
        if (
            isinstance(self.epoch, bool)
            or not isinstance(self.epoch, int)
            or self.epoch < 0
        ):
            raise BrokerError("binding epoch must be a non-negative integer")
        if self.profile not in PROFILE_LIMITS:
            raise BrokerError(
                f"binding profile {self.profile!r} is not a frozen profile name"
            )


@dataclass(frozen=True)
class ObservationRef:
    """One sent TELEM observation reference.

    ``sample_tick_ms`` is the last included ADC sample tick of the
    aggregation window; ``sample_time_lower_ns`` is the conservative
    earliest possible acquisition time of that sample on the caller's
    monotonic clock.  The native EM acquisition time is unknown and is not
    representable here.

    ``sent_ordinal`` is the mandatory immutable uint64 caller-host
    monotonic identity of the sent observation (not a new A wire field).  It
    must strictly increase per registration, exactly identifies an active
    duplicate and can never re-register an evicted ordinal.
    """

    observation_id: str
    sample_tick_ms: int
    sample_time_lower_ns: int
    sent_ordinal: int

    def validate(self) -> None:
        if not isinstance(self.observation_id, str) or not self.observation_id:
            raise BrokerError("observation_id must be a non-empty string")
        require_nonneg_int(self.sample_tick_ms, "sample_tick_ms")
        require_nonneg_int(self.sample_time_lower_ns, "sample_time_lower_ns")
        require_uint64(self.sent_ordinal, "sent_ordinal")


@dataclass(frozen=True)
class Candidate:
    """One completed candidate result bound to one sent observation.

    ``payload`` is immutable opaque bytes (for example serialized model
    output); the digest is derived from the payload, never supplied.
    ``completed_at_ns`` is the completion instant on the caller's monotonic
    clock and only ever used to compare against a scheduler slot deadline.
    """

    binding: BrokerBinding
    observation: ObservationRef
    generation_ordinal: int
    payload: bytes
    completed_at_ns: int

    def validate(self) -> None:
        """Reject forged or inconsistent candidate inputs."""
        if not isinstance(self.binding, BrokerBinding):
            raise BrokerError("candidate binding must be a BrokerBinding")
        self.binding.validate()
        if not isinstance(self.observation, ObservationRef):
            raise BrokerError("candidate observation must be an ObservationRef")
        self.observation.validate()
        require_nonneg_int(self.generation_ordinal, "generation_ordinal")
        if not isinstance(self.payload, bytes):
            raise BrokerError("candidate payload must be immutable bytes")
        if not self.payload:
            raise BrokerError("candidate payload must be non-empty bytes")
        require_nonneg_int(self.completed_at_ns, "completed_at_ns")
        if self.completed_at_ns < self.observation.sample_time_lower_ns:
            raise BrokerError(
                "candidate completion precedes the referenced sample-time "
                "lower bound"
            )

    @property
    def payload_digest(self) -> str:
        """SHA-256 hex digest of the opaque payload bytes."""
        return sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class Consumption:
    """Result of one consumption attempt for one scheduler slot.

    ``candidate`` is present only when ``reason`` is ``CONSUME_OK``.
    ``movement_authorized`` is always False: a returned candidate is not
    permission to move, and a slot grant never renews observation age.
    """

    candidate: Candidate | None
    reason: str
    consumed_at_ns: int
    slot_deadline_ns: int
    observation_age_ns: int | None
    movement_authorized: bool = False


class ControlMailbox:
    """Bounded single-candidate mailbox bound to one exact broker session.

    The candidate ordering key is ``(sent ordinal of the referenced sent
    observation, generation ordinal)``.  The ordering high-water key, its
    payload digest and completion metadata persist beyond the pending
    candidate's lifetime, so a smaller key is always stale (also after
    consumption, expiry or eviction) and an identical redelivery never
    requeues a consumed or dropped candidate.  Consumption is fail-closed:
    it returns the candidate only when the clock inputs agree, the candidate
    completed by the supplied slot deadline and its referenced observation
    is still within the caller-supplied age limit, which may only tighten
    the frozen profile age cap.  One constant-size caller-clock high-water
    scalar rejects any structurally valid consume clock that regresses
    below the greatest accepted one (equality allowed); malformed arguments
    change no state.
    """

    def __init__(self, *, binding: BrokerBinding) -> None:
        if not isinstance(binding, BrokerBinding):
            raise BrokerError("mailbox binding must be a BrokerBinding")
        binding.validate()
        self._binding = binding
        self._observations: deque[ObservationRef] = deque()
        self._registered: dict[int, ObservationRef] = {}
        self._sent_ordinal_high_water: int | None = None
        self._high_water_key: tuple[int, int] | None = None
        self._high_water_digest: str | None = None
        self._high_water_completed_at_ns: int | None = None
        self._pending: Candidate | None = None
        self._pending_key: tuple[int, int] | None = None
        self._last_consumed_now_ns: int | None = None

    @property
    def binding(self) -> BrokerBinding:
        """The exact binding this mailbox accepts."""
        return self._binding

    @property
    def pending(self) -> Candidate | None:
        """The currently retained latest-completed candidate, if any."""
        return self._pending

    @property
    def observation_ids(self) -> tuple[str, ...]:
        """Observation ids in the retained bounded history, oldest first."""
        return tuple(
            observation.observation_id for observation in self._observations
        )

    @property
    def observation_ordinals(self) -> tuple[int, ...]:
        """Sent ordinals in the retained bounded history, oldest first."""
        return tuple(
            observation.sent_ordinal for observation in self._observations
        )

    @property
    def high_water_key(self) -> tuple[int, int] | None:
        """Persisted ordering high-water key, if any offer was accepted."""
        return self._high_water_key

    @property
    def high_water_digest(self) -> str | None:
        """Payload digest of the persisted high-water offer, if any."""
        return self._high_water_digest

    @property
    def high_water_completed_at_ns(self) -> int | None:
        """Completion metadata of the persisted high-water offer, if any."""
        return self._high_water_completed_at_ns

    @property
    def last_consumed_now_ns(self) -> int | None:
        """Greatest accepted consume clock: the constant-size high-water scalar."""
        return self._last_consumed_now_ns

    def register_sent_observation(self, observation: ObservationRef) -> int:
        """Register one legally sent TELEM observation; return its sent ordinal.

        Re-registering the identical reference is idempotent and returns the
        same sent ordinal.  A newly registered observation must carry a
        strictly greater ``sent_ordinal`` than every registration before it,
        so an evicted ordinal never re-registers (no wrap or restart within
        one binding); a still-retained sent ordinal only accepts the exact
        same reference, and a diagnostic id still in the retained history
        only accepts that same reference.  Non-increasing sample ticks
        (sequence wrap) or a regressed sample-time lower bound raise
        :class:`BrokerError`.
        """
        if not isinstance(observation, ObservationRef):
            raise BrokerError("observation must be an ObservationRef")
        observation.validate()
        ordinal = observation.sent_ordinal
        retained = self._registered.get(ordinal)
        if retained is not None:
            if retained == observation:
                return ordinal
            raise BrokerError(
                f"sent ordinal {ordinal} is registered with a different "
                "reference"
            )
        if (
            self._sent_ordinal_high_water is not None
            and ordinal <= self._sent_ordinal_high_water
        ):
            raise BrokerError(
                f"sent ordinal {ordinal} does not increase on "
                f"{self._sent_ordinal_high_water}; an evicted ordinal never "
                "re-registers and wrap or restart needs a new binding"
            )
        for item in self._observations:
            if item.observation_id == observation.observation_id:
                raise BrokerError(
                    f"diagnostic observation id "
                    f"{observation.observation_id!r} is still retained; reuse "
                    "needs eviction first and a strictly greater ordinal and "
                    "tick"
                )
        if self._observations:
            tail = self._observations[-1]
            if observation.sample_tick_ms <= tail.sample_tick_ms:
                raise BrokerError(
                    "sample ticks must strictly increase; sequence wrap is not "
                    "supported and requires a new session"
                )
            if observation.sample_time_lower_ns < tail.sample_time_lower_ns:
                raise BrokerError("sample-time lower bound must not regress")
        self._observations.append(observation)
        self._registered[ordinal] = observation
        self._sent_ordinal_high_water = ordinal
        while len(self._observations) > MAX_SENT_OBSERVATIONS:
            evicted = self._observations.popleft()
            del self._registered[evicted.sent_ordinal]
        return ordinal

    def offer(self, candidate: Candidate) -> str:
        """Offer one completed candidate; return the offer outcome string.

        The ordering high-water key persists beyond the pending candidate's
        lifetime: a smaller key is stale even after consumption, expiry or
        eviction; an identical redelivery of the high-water key never
        requeues a consumed or dropped candidate; the same key with a
        different payload digest is a contract error.  While the candidate
        is pending an identical duplicate keeps the earliest valid
        completion, and a higher generation of a still-retained observation
        is accepted as a new candidate.
        """
        if not isinstance(candidate, Candidate):
            raise BrokerError("candidate must be a Candidate")
        candidate.validate()
        if candidate.binding != self._binding:
            raise BrokerError("candidate binding does not match the mailbox binding")
        observation = candidate.observation
        registered = self._registered.get(observation.sent_ordinal)
        if registered is None:
            raise BrokerError(
                "candidate references an observation outside the retained sent "
                "history"
            )
        if registered != observation:
            raise BrokerError(
                "candidate observation fields do not match the registered sent "
                "observation"
            )
        key = (observation.sent_ordinal, candidate.generation_ordinal)
        digest = candidate.payload_digest
        high_water = self._high_water_key
        if high_water is not None and key < high_water:
            return OFFER_STALE_IGNORED
        if high_water is not None and key == high_water:
            if digest != self._high_water_digest:
                raise BrokerError(
                    "same ordering key with a different payload digest"
                )
            pending = self._pending
            if pending is not None and self._pending_key == key:
                if candidate.completed_at_ns < pending.completed_at_ns:
                    self._pending = candidate
                    self._high_water_completed_at_ns = candidate.completed_at_ns
            return OFFER_DUPLICATE_IGNORED
        self._pending = candidate
        self._pending_key = key
        self._high_water_key = key
        self._high_water_digest = digest
        self._high_water_completed_at_ns = candidate.completed_at_ns
        return OFFER_ACCEPTED

    def consume(
        self,
        *,
        consumed_at_ns: object,
        slot_deadline_ns: object,
        age_limit_ns: object,
    ) -> Consumption:
        """Try to consume the retained candidate for one scheduler slot.

        Returns a :class:`Consumption` whose ``reason`` explains the outcome.
        A candidate that missed this slot deadline is retained for the next
        legitimate slot while it stays fresh; an aged-out or evicted
        candidate is dropped and never returned.  Clock-inconsistent inputs
        (a consume clock that regresses below the greatest previously
        accepted consume clock, a consumed time before the referenced
        sample-time lower bound, or a completion in the future relative to
        the consumed time) raise :class:`BrokerError`; either way no
        candidate is returned.  The caller age limit must be positive and
        may only tighten the frozen profile observation age cap; malformed
        arguments raise without changing any state.  The returned candidate
        is not movement permission.
        """
        now = require_nonneg_int(consumed_at_ns, "consumed_at_ns")
        slot = require_nonneg_int(slot_deadline_ns, "slot_deadline_ns")
        age_limit = require_nonneg_int(age_limit_ns, "age_limit_ns")
        if age_limit <= 0:
            raise BrokerError("age_limit_ns must be > 0")
        profile_cap = PROFILE_LIMITS[
            self._binding.profile
        ].observation_age_limit_ns
        if age_limit > profile_cap:
            raise BrokerError(
                f"age_limit_ns {age_limit} exceeds the frozen "
                f"{self._binding.profile!r} observation age cap "
                f"{profile_cap}"
            )
        last_now = self._last_consumed_now_ns
        if last_now is not None and now < last_now:
            raise BrokerError(
                f"consumed_at_ns {now} regresses below the last accepted "
                f"consume clock {last_now}; a valid consume clock never "
                "decreases"
            )
        self._last_consumed_now_ns = now
        candidate = self._pending
        if candidate is None:
            return Consumption(None, CONSUME_EMPTY, now, slot, None)
        observation = candidate.observation
        if self._registered.get(observation.sent_ordinal) != observation:
            self._drop_pending()
            return Consumption(None, CONSUME_OBSERVATION_EVICTED, now, slot, None)
        sample_lower = observation.sample_time_lower_ns
        if now < sample_lower:
            raise BrokerError(
                "consumed_at_ns regresses below the observation sample-time "
                "lower bound"
            )
        if candidate.completed_at_ns < sample_lower:
            raise BrokerError(
                "candidate completion precedes the referenced sample-time "
                "lower bound"
            )
        if candidate.completed_at_ns > now:
            raise BrokerError(
                "candidate completion is in the future relative to "
                "consumed_at_ns"
            )
        age = now - sample_lower
        if age >= age_limit:
            self._drop_pending()
            return Consumption(
                None, CONSUME_OBSERVATION_AGE_EXCEEDED, now, slot, age
            )
        if candidate.completed_at_ns > slot:
            return Consumption(
                None, CONSUME_COMPLETED_AFTER_SLOT_DEADLINE, now, slot, age
            )
        self._drop_pending()
        return Consumption(candidate, CONSUME_OK, now, slot, age)

    def _drop_pending(self) -> None:
        self._pending = None
        self._pending_key = None

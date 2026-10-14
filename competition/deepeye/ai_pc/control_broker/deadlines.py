"""C05 execution deadline arithmetic for the PC control broker (pure).

Frozen decisions implemented here (director broker-foundation-plan.json):

* All arithmetic uses nonnegative integer nanoseconds from one caller
  established monotonic clock.  ``bool``, ``float``, negative values and
  inconsistent orderings (receipt before first send) are rejected.
* HIL deadline = min(first_send + original_ttl, receipt + max(0,
  current_remaining_ttl - serialized_frame_duration - usb_processing_upper
  bound - clock_error_upper_bound), referenced_sample_time_lower +
  profile_age_limit, any_previous_deadline).  Repeated ACK/STATE never
  resets first_send or the original TTL, so a computed deadline can only
  stay equal or shrink.
* PC_DIRECT deadline = min(first_host_issue + requested_duration,
  referenced_sample_time_lower + profile_age_limit, any_previous_deadline).
  No board motion ACK is required or fabricated here; a separate execution
  authority must still check link state, session, heartbeat, model
  availability and legal actions every physics step.
* Profile maximum TTL is FAST 3 s / STRESS 12 s; observation age caps are
  FAST 1.5 s / STRESS 12 s.  PC_DIRECT host command duration uses the same
  profile caps.
* When no ACK has been received yet (receipt absent) the receipt term does
  not exist and the deadline is bounded by first_send + original_ttl.  When
  a receipt is supplied, every subtraction bound must also be supplied;
  unknown clock/USB/remaining-TTL/serialization bounds produce a stop
  decision, never an assumed zero uncertainty.
* At ``now >= deadline`` the lease is expired.
* ``referenced_sample_time_lower_ns`` is the conservative earliest possible
  acquisition time of the referenced TELEM sample (last included ADC sample
  tick of its aggregation window).  The native EM sample time is not present
  in legal bytes and never enters this API; no raw debug or authority
  timestamps are accepted.
* A future sample lower bound is a contract error: the referenced sample must
  already exist, so ``referenced_sample_time_lower_ns`` must be <=
  ``first_send_ns`` (HIL) / ``first_host_issue_ns`` (PC_DIRECT).
* ``LeaseDeadline`` min-term names are mode-scoped audit labels: HIL requires
  ``first_send_plus_original_ttl`` and ``sample_lower_plus_age_limit`` and
  allows only ``receipt_plus_remaining_budget`` and ``previous_deadline``;
  PC_DIRECT requires ``first_host_issue_plus_requested_duration`` and
  ``sample_lower_plus_age_limit`` and allows only ``previous_deadline``.
  Unknown, missing, cross-mode and duplicate names are rejected, so an audit
  label can never stand in for a missing bound.  Matching this audit
  structure is not cryptographic provenance and is never movement
  authorization: a separate execution authority must still check link
  state, session, heartbeat, model availability and legal actions.
* ``PROFILE_LIMITS`` is exported as a read-only mapping, ``LeaseDeadline``
  validates itself on construction and on every ``expired_at`` call, and
  broker bindings accept only frozen profile names, so a malformed or
  mutated dataclass cannot bypass the frozen checks.

This module performs no I/O: no clock reads, no network, no board access.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "NS_PER_MS",
    "UINT64_MAX",
    "HIL_MODE",
    "PC_DIRECT_MODE",
    "ProfileLimits",
    "PROFILE_LIMITS",
    "BrokerError",
    "profile_limits",
    "require_nonneg_int",
    "require_uint64",
    "LeaseDeadline",
    "hil_deadline",
    "pc_direct_deadline",
]

NS_PER_MS = 1_000_000
UINT64_MAX = (1 << 64) - 1

HIL_MODE = "HIL_PC_FPGA"
PC_DIRECT_MODE = "PC_DIRECT"


class BrokerError(ValueError):
    """Raised when broker inputs violate the frozen C05 contract."""


@dataclass(frozen=True)
class ProfileLimits:
    """Frozen per-profile caps used by every deadline computation."""

    max_ttl_ns: int
    observation_age_limit_ns: int


PROFILE_LIMITS: Mapping[str, ProfileLimits] = MappingProxyType(
    {
        "fast_9600": ProfileLimits(
            max_ttl_ns=3_000_000_000,
            observation_age_limit_ns=1_500_000_000,
        ),
        "stress_300": ProfileLimits(
            max_ttl_ns=12_000_000_000,
            observation_age_limit_ns=12_000_000_000,
        ),
    }
)


def profile_limits(profile: object) -> ProfileLimits:
    """Return the frozen caps for ``profile``; unknown profiles stop."""
    if not isinstance(profile, str) or profile not in PROFILE_LIMITS:
        raise BrokerError(f"unknown profile {profile!r}")
    return PROFILE_LIMITS[profile]


def require_nonneg_int(value: object, what: str) -> int:
    """Return ``value`` as a nonnegative int, rejecting bool/float/negative."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BrokerError(f"{what} must be a non-negative integer, got {value!r}")
    return value


def require_uint64(value: object, what: str) -> int:
    """Return ``value`` as an unsigned 64-bit int, rejecting bool/float/range."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > UINT64_MAX
    ):
        raise BrokerError(f"{what} must be a uint64 integer, got {value!r}")
    return value


@dataclass(frozen=True)
class LeaseDeadline:
    """One computed execution deadline for a single broker decision.

    ``must_stop`` is True when the inputs cannot bound the deadline (unknown
    clock/USB/serialization/remaining-TTL bounds); such a decision stops the
    mode and carries no deadline.  Otherwise ``deadline_ns`` is the absolute
    monotonic deadline and ``terms_ns`` records every named min-term for
    audit.  ``expired_at`` is the only expiry predicate: at
    ``now >= deadline`` the lease is expired, and a stop decision is expired
    at every instant.
    ``terms_ns`` names are mode-scoped audit labels, not cryptographic
    provenance and never movement authorization: HIL requires
    ``first_send_plus_original_ttl`` and ``sample_lower_plus_age_limit``
    (optional ``receipt_plus_remaining_budget``, ``previous_deadline``);
    PC_DIRECT requires ``first_host_issue_plus_requested_duration`` and
    ``sample_lower_plus_age_limit`` (optional ``previous_deadline`` only).
    """

    mode: str
    deadline_ns: int | None
    must_stop: bool
    stop_reason: str | None
    terms_ns: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Reject a malformed or internally inconsistent decision.

        Validates the mode, the stop state, exact nonnegative integers, the
        mode-scoped audit term names, the named min-term values and the
        minimum rule.  Called on construction and again from ``expired_at``
        so a mutated instance cannot bypass the frozen checks.
        """
        if self.mode not in (HIL_MODE, PC_DIRECT_MODE):
            raise BrokerError(f"unknown deadline mode {self.mode!r}")
        if not isinstance(self.must_stop, bool):
            raise BrokerError("must_stop must be a bool")
        if self.must_stop:
            if self.deadline_ns is not None:
                raise BrokerError("a stop decision must not carry a deadline")
            if not isinstance(self.stop_reason, str) or not self.stop_reason:
                raise BrokerError("a stop decision must carry a non-empty reason")
            if self.terms_ns != ():
                raise BrokerError("a stop decision must not carry min terms")
            return
        require_nonneg_int(self.deadline_ns, "deadline_ns")
        if self.stop_reason is not None:
            raise BrokerError("a non-stop decision must not carry a stop reason")
        terms = self.terms_ns
        if not isinstance(terms, tuple) or not terms:
            raise BrokerError("a non-stop decision must carry min terms")
        if self.mode == HIL_MODE:
            mandatory = (
                "first_send_plus_original_ttl",
                "sample_lower_plus_age_limit",
            )
            optional = ("receipt_plus_remaining_budget", "previous_deadline")
        else:
            mandatory = (
                "first_host_issue_plus_requested_duration",
                "sample_lower_plus_age_limit",
            )
            optional = ("previous_deadline",)
        allowed = frozenset(mandatory + optional)
        names: set[str] = set()
        values: list[int] = []
        for item in terms:
            if not isinstance(item, tuple) or len(item) != 2:
                raise BrokerError("every min term must be a (name, value) pair")
            name, value = item
            if not isinstance(name, str) or not name:
                raise BrokerError("min term names must be non-empty strings")
            if name not in allowed:
                raise BrokerError(
                    f"min term {name!r} is not a legal {self.mode!r} audit "
                    f"label; allowed: {sorted(allowed)}"
                )
            if name in names:
                raise BrokerError(f"duplicate min term name {name!r}")
            names.add(name)
            values.append(require_nonneg_int(value, f"min term {name!r}"))
        missing = [name for name in mandatory if name not in names]
        if missing:
            raise BrokerError(
                f"non-stop {self.mode!r} decision is missing mandatory min "
                f"terms {missing}"
            )
        if self.deadline_ns != min(values):
            raise BrokerError("deadline_ns must equal the minimum of terms_ns")

    def expired_at(self, now_ns: object) -> bool:
        """True when the lease must already be stopped at ``now_ns``."""
        self.validate()
        now = require_nonneg_int(now_ns, "now_ns")
        if self.must_stop:
            return True
        return now >= self.deadline_ns


def hil_deadline(
    *,
    first_send_ns: object,
    original_ttl_ns: object,
    referenced_sample_time_lower_ns: object,
    profile: object,
    receipt_ns: object | None = None,
    current_remaining_ttl_ns: object | None = None,
    serialized_frame_duration_ns: object | None = None,
    usb_processing_upper_bound_ns: object | None = None,
    clock_error_upper_bound_ns: object | None = None,
    previous_deadline_ns: object | None = None,
) -> LeaseDeadline:
    """Compute the HIL_PC_FPGA deadline for one command/session step.

    ``first_send_ns`` and ``original_ttl_ns`` are immutable caller
    provenance: repeated ACK/STATE deliveries must pass the original values
    again, and ``previous_deadline_ns`` lets the caller chain so a computed
    deadline can never extend.  With no receipt the deadline is bounded by
    first send plus the original TTL.  With a receipt, the conservative
    remaining budget subtracts the serialized frame duration, the USB
    processing upper bound and the host clock error upper bound (never below
    zero); any of those bounds being unknown produces a stop decision.  The
    referenced sample lower bound plus the profile observation age limit
    always applies.
    """
    limits = profile_limits(profile)
    first = require_nonneg_int(first_send_ns, "first_send_ns")
    ttl = require_nonneg_int(original_ttl_ns, "original_ttl_ns")
    if ttl > limits.max_ttl_ns:
        raise BrokerError(
            f"original_ttl_ns {ttl} exceeds the {profile!r} profile cap "
            f"{limits.max_ttl_ns}"
        )
    sample_lower = require_nonneg_int(
        referenced_sample_time_lower_ns, "referenced_sample_time_lower_ns"
    )
    if sample_lower > first:
        raise BrokerError(
            "referenced_sample_time_lower_ns is after first_send_ns; a sample "
            "that does not exist yet cannot ground a command"
        )
    previous = None
    if previous_deadline_ns is not None:
        previous = require_nonneg_int(previous_deadline_ns, "previous_deadline_ns")

    first_term = first + ttl
    age_term = sample_lower + limits.observation_age_limit_ns

    if receipt_ns is None:
        if any(
            value is not None
            for value in (
                current_remaining_ttl_ns,
                serialized_frame_duration_ns,
                usb_processing_upper_bound_ns,
                clock_error_upper_bound_ns,
            )
        ):
            raise BrokerError(
                "receipt-derived bounds must be absent when no receipt is supplied"
            )
        terms: list[tuple[str, int]] = [
            ("first_send_plus_original_ttl", first_term),
            ("sample_lower_plus_age_limit", age_term),
        ]
    else:
        receipt = require_nonneg_int(receipt_ns, "receipt_ns")
        if receipt < first:
            raise BrokerError("receipt_ns precedes first_send_ns")
        unknown = [
            name
            for name, value in (
                ("current_remaining_ttl_ns", current_remaining_ttl_ns),
                ("serialized_frame_duration_ns", serialized_frame_duration_ns),
                ("usb_processing_upper_bound_ns", usb_processing_upper_bound_ns),
                ("clock_error_upper_bound_ns", clock_error_upper_bound_ns),
            )
            if value is None
        ]
        if unknown:
            return LeaseDeadline(
                mode=HIL_MODE,
                deadline_ns=None,
                must_stop=True,
                stop_reason="unknown_bounds:" + ",".join(unknown),
                terms_ns=(),
            )
        remaining = require_nonneg_int(
            current_remaining_ttl_ns, "current_remaining_ttl_ns"
        )
        if remaining > limits.max_ttl_ns:
            raise BrokerError(
                f"current_remaining_ttl_ns {remaining} exceeds the {profile!r} "
                f"profile cap {limits.max_ttl_ns}"
            )
        serialized = require_nonneg_int(
            serialized_frame_duration_ns, "serialized_frame_duration_ns"
        )
        usb = require_nonneg_int(
            usb_processing_upper_bound_ns, "usb_processing_upper_bound_ns"
        )
        clock = require_nonneg_int(
            clock_error_upper_bound_ns, "clock_error_upper_bound_ns"
        )
        budget = max(0, remaining - serialized - usb - clock)
        terms = [
            ("first_send_plus_original_ttl", first_term),
            ("receipt_plus_remaining_budget", receipt + budget),
            ("sample_lower_plus_age_limit", age_term),
        ]
    if previous is not None:
        terms.append(("previous_deadline", previous))
    deadline = min(value for _, value in terms)
    return LeaseDeadline(
        mode=HIL_MODE,
        deadline_ns=deadline,
        must_stop=False,
        stop_reason=None,
        terms_ns=tuple(terms),
    )


def pc_direct_deadline(
    *,
    first_host_issue_ns: object,
    requested_duration_ns: object,
    referenced_sample_time_lower_ns: object,
    profile: object,
    previous_deadline_ns: object | None = None,
) -> LeaseDeadline:
    """Compute the PC_DIRECT deadline for one host command step.

    PC_DIRECT has no board motion ACK: nothing here requires or fabricates
    one.  The deadline is bounded by the first host issue plus the requested
    duration (capped by the profile), the referenced sample lower bound plus
    the profile observation age limit, and any previous deadline.  The
    separate execution authority must still check link state, session,
    heartbeat, model availability and legal actions every physics step.
    """
    limits = profile_limits(profile)
    first = require_nonneg_int(first_host_issue_ns, "first_host_issue_ns")
    duration = require_nonneg_int(requested_duration_ns, "requested_duration_ns")
    if duration > limits.max_ttl_ns:
        raise BrokerError(
            f"requested_duration_ns {duration} exceeds the {profile!r} profile "
            f"cap {limits.max_ttl_ns}"
        )
    sample_lower = require_nonneg_int(
        referenced_sample_time_lower_ns, "referenced_sample_time_lower_ns"
    )
    if sample_lower > first:
        raise BrokerError(
            "referenced_sample_time_lower_ns is after first_host_issue_ns; a "
            "sample that does not exist yet cannot ground a command"
        )
    terms: list[tuple[str, int]] = [
        ("first_host_issue_plus_requested_duration", first + duration),
        (
            "sample_lower_plus_age_limit",
            sample_lower + limits.observation_age_limit_ns,
        ),
    ]
    if previous_deadline_ns is not None:
        terms.append(
            (
                "previous_deadline",
                require_nonneg_int(previous_deadline_ns, "previous_deadline_ns"),
            )
        )
    deadline = min(value for _, value in terms)
    return LeaseDeadline(
        mode=PC_DIRECT_MODE,
        deadline_ns=deadline,
        must_stop=False,
        stop_reason=None,
        terms_ns=tuple(terms),
    )

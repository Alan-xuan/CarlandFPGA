"""Pure host-clock arithmetic reference (revision 1).

Implements only the bounded integer arithmetic frozen in
``competition/deepeye/docs/host_timing_contract.md`` for
DEEPEYE-IMPLEMENTATION-20261014/v1.  This module is a reference: it produces
intervals and refuse behaviours, nothing else.

It supplies NO measurement authenticity, NO oscillator/USB/baud calibration,
NO physical capture validation and NO motion permission.  Callers may only
use values that come from an independently verified measurement record bound
to operation_id, request_hash, tested_commit, transport profile and tool/board
evidence.  A caller-supplied boolean or literal is not measurement
authentication, and runtime code must separately verify provenance before any
executable grant.  All arithmetic is integer-only and every delay/error term
rounds upward.

Native 20Hz EM update time is intentionally NOT inferred here; held bits and
tick interpolation do not identify that update time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

NS_PER_MS = 1_000_000
PPM_SCALE = 1_000_000
UINT32_MOD = 1 << 32
UINT32_MAX = UINT32_MOD - 1
HALF_RANGE_MS = 1 << 31
MAX_ANCHOR_AGE_NS = (HALF_RANGE_MS - 1) * NS_PER_MS
ADC_SAMPLE_PERIOD_NOMINAL_NS = 10_000_000
FAST_OBSERVATION_AGE_CAP_NS = 1_500 * NS_PER_MS
STRESS_OBSERVATION_AGE_CAP_NS = 12_000 * NS_PER_MS

_HEX_DIGITS = frozenset("0123456789abcdef")


def _strict_int(value, name, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("%s must be an int (bool rejected), got %r" % (name, type(value).__name__))
    if minimum is not None and value < minimum:
        raise ValueError("%s=%d is below minimum %d" % (name, value, minimum))
    if maximum is not None and value > maximum:
        raise ValueError("%s=%d is above maximum %d" % (name, value, maximum))
    return value


def _require_uint32(value, name):
    return _strict_int(value, name, minimum=0, maximum=UINT32_MAX)


def _require_full_boot_sha256(value, name):
    if not isinstance(value, str):
        raise TypeError("%s must be a 64-character lowercase hex string, got %r" % (name, type(value).__name__))
    if len(value) != 64 or any(ch not in _HEX_DIGITS for ch in value):
        raise ValueError("%s must be exactly 64 lowercase hex characters" % name)
    return value


@dataclass(frozen=True)
class Interval:
    """Closed host-time interval [lo_ns, hi_ns] in monotonic nanoseconds."""

    lo_ns: int
    hi_ns: int

    def __post_init__(self):
        _strict_int(self.lo_ns, "Interval.lo_ns", minimum=0)
        _strict_int(self.hi_ns, "Interval.hi_ns", minimum=0)
        if self.lo_ns > self.hi_ns:
            raise ValueError("empty interval: lo_ns=%d > hi_ns=%d" % (self.lo_ns, self.hi_ns))


@dataclass(frozen=True)
class ClockBounds:
    """Measured clock/transport bounds; all fields are required and non-default.

    ``rate_error_ppm`` is the host-relative-rate bound p: for a tick separation
    delta_ns, |actual_elapsed_host_ns - delta_ns| <= ceil(abs(delta_ns)*p/1e6).
    It is NOT an unconverted crystal tolerance in board seconds.
    """

    total_delay_lower_ns: int
    total_delay_upper_ns: int
    tick_quantum_upper_ns: int
    rate_error_ppm: int
    max_anchor_age_ns: int

    def __post_init__(self):
        _strict_int(self.total_delay_lower_ns, "total_delay_lower_ns", minimum=0)
        _strict_int(self.total_delay_upper_ns, "total_delay_upper_ns", minimum=0)
        if self.total_delay_lower_ns > self.total_delay_upper_ns:
            raise ValueError("total_delay_lower_ns exceeds total_delay_upper_ns")
        _strict_int(self.tick_quantum_upper_ns, "tick_quantum_upper_ns", minimum=1)
        _strict_int(self.rate_error_ppm, "rate_error_ppm", minimum=0, maximum=PPM_SCALE - 1)
        _strict_int(self.max_anchor_age_ns, "max_anchor_age_ns", minimum=1, maximum=MAX_ANCHOR_AGE_NS)
        quantum_floor = PPM_SCALE + self.rate_error_ppm
        if self.tick_quantum_upper_ns < quantum_floor:
            raise ValueError(
                "tick_quantum_upper_ns=%d below required floor %d (= ceil(1e6*(1+ppm/1e6)))"
                % (self.tick_quantum_upper_ns, quantum_floor)
            )


@dataclass(frozen=True)
class Anchor:
    """Validated same-session anchor with derived fields that cannot be forged.

    ``derived_interval`` and ``valid_until`` are declared with init=False and are
    recomputed inside __post_init__ from the raw inputs, so no constructor or
    keyword can supply a claimed interval or expiry.
    """

    session: int
    boot_sha256: str
    tick_ms: int
    receipt_interval: Interval
    bounds: ClockBounds
    derived_interval: Interval = field(init=False)
    valid_until: int = field(init=False)

    def __post_init__(self):
        _require_uint32(self.session, "session")
        _require_full_boot_sha256(self.boot_sha256, "boot_sha256")
        _require_uint32(self.tick_ms, "tick_ms")
        if not isinstance(self.receipt_interval, Interval):
            raise TypeError("receipt_interval must be an Interval")
        if not isinstance(self.bounds, ClockBounds):
            raise TypeError("bounds must be a ClockBounds")
        bounds = self.bounds
        receipt = self.receipt_interval
        anchor_hi = receipt.hi_ns - bounds.total_delay_lower_ns
        if anchor_hi < 0:
            raise ValueError("anchor upper bound negative: receipt precedes the measured delay bounds")
        anchor_lo = receipt.lo_ns - bounds.total_delay_upper_ns - bounds.tick_quantum_upper_ns
        if anchor_lo < 0:
            anchor_lo = 0
        if anchor_lo > anchor_hi:
            raise ValueError("empty anchor interval")
        object.__setattr__(self, "derived_interval", Interval(anchor_lo, anchor_hi))
        object.__setattr__(self, "valid_until", receipt.lo_ns + bounds.max_anchor_age_ns)


def make_anchor(session, boot_sha256, tick_ms, receipt_lo_ns, receipt_hi_ns, bounds):
    """Build an Anchor from measured inputs; all validation lives in Anchor."""
    receipt = Interval(receipt_lo_ns, receipt_hi_ns)
    return Anchor(
        session=session,
        boot_sha256=boot_sha256,
        tick_ms=tick_ms,
        receipt_interval=receipt,
        bounds=bounds,
    )


def map_tick(anchor, session, boot_sha256, tick_ms, now_ns):
    """Map a board tick to its bounded host acquisition interval.

    Requires explicit same session and full BOOT hash, a monotonic host
    ``now_ns`` inside [receipt.hi_ns, anchor.valid_until], and no wall-clock
    timestamps.  The signed nearest-uint32 delta is used; exactly half-range
    (2^31 ms) separation is ambiguous and rejected.
    """
    if not isinstance(anchor, Anchor):
        raise TypeError("anchor must be an Anchor")
    _require_uint32(session, "session")
    _require_full_boot_sha256(boot_sha256, "boot_sha256")
    _require_uint32(tick_ms, "tick_ms")
    _strict_int(now_ns, "now_ns", minimum=0)
    if session != anchor.session:
        raise ValueError("session mismatch: %d != anchor session %d" % (session, anchor.session))
    if boot_sha256 != anchor.boot_sha256:
        raise ValueError("boot profile mismatch: full BOOT sha256 differs from anchor")
    receipt = anchor.receipt_interval
    if now_ns < receipt.hi_ns:
        raise ValueError("clock regression: now_ns precedes receipt availability")
    if now_ns > anchor.valid_until:
        raise ValueError("anchor expired: now_ns beyond earliest receipt + bounded age")
    raw_separation = (tick_ms - anchor.tick_ms) % UINT32_MOD
    if raw_separation == HALF_RANGE_MS:
        raise ValueError("ambiguous half-wrap: exact 2^31 ms separation is rejected")
    delta_ms = raw_separation - UINT32_MOD if raw_separation > HALF_RANGE_MS else raw_separation
    delta_ns = delta_ms * NS_PER_MS
    span = abs(delta_ns)
    rate_error_ns = (span * anchor.bounds.rate_error_ppm + PPM_SCALE - 1) // PPM_SCALE
    anchor_lo = anchor.derived_interval.lo_ns
    anchor_hi = anchor.derived_interval.hi_ns
    sample_lo = anchor_lo + delta_ns - rate_error_ns
    if sample_lo < 0:
        sample_lo = 0
    sample_hi = anchor_hi + delta_ns + rate_error_ns + anchor.bounds.tick_quantum_upper_ns
    if sample_hi < 0:
        raise ValueError("negative sample upper bound: sample precedes the monotonic epoch")
    if sample_lo > sample_hi:
        raise ValueError("empty sample interval")
    if sample_lo > now_ns:
        raise ValueError("sample lower bound in the future relative to now_ns; use sample_lo only for age checks")
    return Interval(sample_lo, sample_hi)


def adc_window_nominal_span_ns(sample_count):
    """First-to-last nominal span (N-1)*10ms at 100 samples/channel/second.

    This is NOT the frame receipt time and NOT N*10ms.
    """
    count = _strict_int(sample_count, "sample_count", minimum=1)
    return (count - 1) * ADC_SAMPLE_PERIOD_NOMINAL_NS


def adc_first_sample_interval(last_sample_interval, sample_count, period_lower_ns, period_upper_ns):
    """Derive the first-sample acquisition interval from the last-sample one.

    ``sample_count`` must be the actual number of received samples: the helper
    never fills, interpolates or conceals missing samples, and quality/source
    faults remain the caller's explicit responsibility.  Period bounds are
    measured sample-period bounds in nanoseconds.
    """
    if not isinstance(last_sample_interval, Interval):
        raise TypeError("last_sample_interval must be an Interval")
    count = _strict_int(sample_count, "sample_count", minimum=1)
    period_lo = _strict_int(period_lower_ns, "period_lower_ns", minimum=1)
    period_hi = _strict_int(period_upper_ns, "period_upper_ns", minimum=1)
    if period_lo > period_hi:
        raise ValueError("period_lower_ns exceeds period_upper_ns")
    steps = count - 1
    first_hi = last_sample_interval.hi_ns - steps * period_lo
    if first_hi < 0:
        raise ValueError("derived first-sample upper bound is negative")
    first_lo = last_sample_interval.lo_ns - steps * period_hi
    if first_lo < 0:
        first_lo = 0
    return Interval(first_lo, first_hi)

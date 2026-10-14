"""C-side validation of legal quantized 3D motion primitives (pure, stdlib only).

Authority boundaries
--------------------
Every function is pure: explicit scalar inputs, explicit outputs, no mutable
state, no scene-truth access, no collision or swept-volume check, no planning
search, no world authority and no FPGA register write. The world, the FPGA and
the runtime broker must independently re-validate any accepted primitive before
execution. Passing this gate is not a product-card result, not a collision
proof and not a physical observation.

Frozen semantics (taskbook_final.md CONTROL3D section plus simulation contract)
------------------------------------------------------------------------------
- profile "fast_9600": speed_code 0..20, target v = speed_code * 0.0125 m/s.
- profile "stress_300": speed_code 0..20, target v = speed_code * 0.0001 m/s.
- yaw_q and pitch_q are signed integer codes in unit 0.001 deg/s, each in
  -15000..15000. A candidate is accepted iff
  yaw_q^2 + pitch_q^2 <= floor((v * 180000 / (2 * pi))^2); out-of-bounds
  candidates are rejected, never clipped.
- zero target speed requires both angular codes to be zero, so a zero-speed
  command cannot turn in place.
- curvature per axis: k = q * pi / (180000 * v) in rad per metre; the runtime
  applies omega(t) = v_actual(t) * k with v_actual in [0, 0.25], so zero speed
  has exactly zero rotation and there is no reverse, sideways or pivot motion.
- v_actual approaches the target under |dv/dt| <= 0.25 m/s^2.

Threshold ROM method (recorded)
-------------------------------
PI_DIGITS_60 is pi truncated at 60 decimal digits (fixed literal, never
rounded up). CURVATURE_THRESHOLD_SQUARED stores floor() of the squared bound,
precomputed with Decimal contexts at precision 80. Tests re-derive all entries
from pi computed independently by the Machin arctan series at 170 significant
digits, require identical integer floors and record that every squared bound
stays more than 0.01 away from an integer, so the floor is unambiguous and the
truncated literal cannot shift it. Intermediate quantities fit 64-bit integers
(largest threshold ~ 5.13e7).
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, localcontext
import math
from types import MappingProxyType

__all__ = [
    "SPEED_CODE_MIN",
    "SPEED_CODE_MAX",
    "Q_CODE_MIN",
    "Q_CODE_MAX",
    "MAX_SPEED_M_S",
    "MAX_ACCEL_M_S2",
    "PI_DIGITS_60",
    "CURVATURE_THRESHOLD_SQUARED",
    "PrimitiveRejected",
    "MotionPrimitive",
    "target_speed_m_s",
    "curvature_threshold_squared",
    "validate_primitive",
    "reference_angular_rate_deg_s",
    "angular_rate_rad_s",
    "step_speed_m_s",
]

SPEED_CODE_MIN = 0
SPEED_CODE_MAX = 20
Q_CODE_MIN = -15000
Q_CODE_MAX = 15000
MAX_SPEED_M_S = 0.25
MAX_ACCEL_M_S2 = 0.25

_SPEED_STEP = MappingProxyType(
    {
        "fast_9600": Decimal("0.0125"),
        "stress_300": Decimal("0.0001"),
    }
)

PI_DIGITS_60 = "3.141592653589793238462643383279502884197169399375105820974944"
_PI = Decimal(PI_DIGITS_60)


def _threshold_table():
    table = {}
    with localcontext() as context:
        context.prec = 80
        for profile, step in _SPEED_STEP.items():
            row = []
            for code in range(SPEED_CODE_MIN, SPEED_CODE_MAX + 1):
                bound = Decimal(code) * step * Decimal(180000) / (2 * _PI)
                squared = bound * bound
                row.append(int(squared.to_integral_value(rounding=ROUND_FLOOR)))
            table[profile] = tuple(row)
    return table


CURVATURE_THRESHOLD_SQUARED = MappingProxyType(_threshold_table())


class PrimitiveRejected(ValueError):
    """A candidate primitive is illegal; it is reported, never clipped."""


@dataclass(frozen=True)
class MotionPrimitive:
    """Immutable validated primitive; explicitly not an authorization token."""

    profile: str
    speed_code: int
    yaw_q: int
    pitch_q: int
    target_speed_m_s: float
    curvature_yaw_per_m: float
    curvature_pitch_per_m: float


def _require_profile(profile):
    if type(profile) is not str or profile not in _SPEED_STEP:
        raise PrimitiveRejected("profile must be exact string fast_9600 or stress_300")


def _require_speed_code(speed_code):
    if type(speed_code) is not int or not SPEED_CODE_MIN <= speed_code <= SPEED_CODE_MAX:
        raise PrimitiveRejected("speed_code must be an integer 0..20")


def _require_q_code(value, name):
    if type(value) is not int or not Q_CODE_MIN <= value <= Q_CODE_MAX:
        raise PrimitiveRejected(name + " must be an integer in -15000..15000")


def _require_finite_real(value, name, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PrimitiveRejected(name + " must be a real number")
    if value < 0.0 or value > maximum or not math.isfinite(value):
        raise PrimitiveRejected(name + " must be finite and within 0.." + str(maximum))


def _target_speed(profile, speed_code):
    # A caller's Decimal precision must not change the wire speed mapping.
    with localcontext() as context:
        context.prec = 80
        return float(_SPEED_STEP[profile] * speed_code)


def target_speed_m_s(profile, speed_code):
    """Profile speed code to target speed in m/s (float), or reject."""
    _require_profile(profile)
    _require_speed_code(speed_code)
    return _target_speed(profile, speed_code)


def curvature_threshold_squared(profile, speed_code):
    """Conservative integer ROM entry floor((v*180000/(2*pi))^2)."""
    _require_profile(profile)
    _require_speed_code(speed_code)
    return CURVATURE_THRESHOLD_SQUARED[profile][speed_code]


def validate_primitive(profile, speed_code, yaw_q, pitch_q):
    """Validate one candidate primitive; raise PrimitiveRejected if illegal."""
    _require_profile(profile)
    _require_speed_code(speed_code)
    _require_q_code(yaw_q, "yaw_q")
    _require_q_code(pitch_q, "pitch_q")
    if speed_code == 0 and (yaw_q != 0 or pitch_q != 0):
        raise PrimitiveRejected(
            "zero target speed requires both angular codes zero; in-place turn rejected"
        )
    limit = CURVATURE_THRESHOLD_SQUARED[profile][speed_code]
    combined = yaw_q * yaw_q + pitch_q * pitch_q
    if combined > limit:
        raise PrimitiveRejected(
            "yaw_q^2 + pitch_q^2 = "
            + str(combined)
            + " exceeds conservative limit "
            + str(limit)
            + " for this profile and speed code; rejected, not clipped"
        )
    target = _target_speed(profile, speed_code)
    if target == 0.0:
        curvature_yaw = 0.0
        curvature_pitch = 0.0
    else:
        scale = math.pi / (180000.0 * target)
        curvature_yaw = yaw_q * scale
        curvature_pitch = pitch_q * scale
    return MotionPrimitive(
        profile,
        speed_code,
        yaw_q,
        pitch_q,
        target,
        curvature_yaw,
        curvature_pitch,
    )


def reference_angular_rate_deg_s(q_units):
    """Wire code q (unit 0.001 deg/s) to its target-speed reference in deg/s."""
    _require_q_code(q_units, "q_units")
    return q_units * 0.001


def angular_rate_rad_s(primitive, actual_speed_m_s):
    """omega = v_actual * k per axis in rad/s; exact (0.0, 0.0) when v = 0."""
    if not isinstance(primitive, MotionPrimitive):
        raise PrimitiveRejected("primitive must be a MotionPrimitive from validate_primitive")
    canonical = validate_primitive(
        primitive.profile, primitive.speed_code, primitive.yaw_q, primitive.pitch_q
    )
    for field in ("target_speed_m_s", "curvature_yaw_per_m", "curvature_pitch_per_m"):
        supplied = getattr(primitive, field)
        if type(supplied) is not float or not math.isfinite(supplied) or supplied != getattr(canonical, field):
            raise PrimitiveRejected("primitive derived fields do not match validated wire codes")
    _require_finite_real(actual_speed_m_s, "actual_speed_m_s", MAX_SPEED_M_S)
    if actual_speed_m_s == 0:
        return (0.0, 0.0)
    return (
        actual_speed_m_s * canonical.curvature_yaw_per_m,
        actual_speed_m_s * canonical.curvature_pitch_per_m,
    )


def step_speed_m_s(actual_speed_m_s, target_speed_m_s, dt_s):
    """One acceleration-limited scalar step; never overshoots the target."""
    _require_finite_real(actual_speed_m_s, "actual_speed_m_s", MAX_SPEED_M_S)
    _require_finite_real(target_speed_m_s, "target_speed_m_s", MAX_SPEED_M_S)
    try:
        finite_dt = math.isfinite(dt_s)
    except (TypeError, OverflowError):
        finite_dt = False
    if (
        isinstance(dt_s, bool)
        or not isinstance(dt_s, (int, float))
        or not finite_dt
        or dt_s <= 0.0
    ):
        raise PrimitiveRejected("dt_s must be a finite positive number of seconds")
    delta = target_speed_m_s - actual_speed_m_s
    bound = MAX_ACCEL_M_S2 * dt_s
    if abs(delta) <= bound:
        return float(target_speed_m_s)
    if delta > 0.0:
        return actual_speed_m_s + bound
    return actual_speed_m_s - bound

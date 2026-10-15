"""ABI3 quantized curvature reference; no collision or authorization oracle.

All inputs are controller-visible scalars. This module neither reads scene truth
nor executes a trajectory. World authority and FPGA must enforce the same vectors
independently, alongside observation age, actual capture and mode-specific leases.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext, ROUND_FLOOR
import math

SPEED_STEP = {'fast_9600': Decimal('0.0125'), 'stress_300': Decimal('0.0001')}
PI = Decimal('3.14159265358979323846264338327950288419716939937510')


def _make_rom():
    with localcontext() as context:
        context.prec = 48
        return {name: tuple(int(((Decimal(code)*step*180000/(2*PI))**2)
                                .to_integral_value(rounding=ROUND_FLOOR))
                            for code in range(21))
                for name, step in SPEED_STEP.items()}


CURVATURE_LIMIT_SQUARED = _make_rom()


def curvature_limit_squared(profile: str, speed_code: int) -> int:
    if not isinstance(profile,str) or profile not in SPEED_STEP:
        raise ValueError('unknown motion profile')
    if type(speed_code) is not int or not 0 <= speed_code <= 20:
        raise ValueError('speed code must be integer 0..20')
    return CURVATURE_LIMIT_SQUARED[profile][speed_code]


def _finite_nonnegative(value, maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError('invalid finite nonnegative motion scalar')


@dataclass(frozen=True)
class MotionCommand:
    profile: str
    target_speed_m_s: float
    curvature_yaw_per_m: float
    curvature_pitch_per_m: float
    max_speed_m_s: float

    def angular_rates(self, actual_speed_m_s: float) -> tuple[float,float]:
        """Actual yaw/pitch radians/s, both zero when actual speed reaches zero."""
        _finite_nonnegative(actual_speed_m_s,self.max_speed_m_s)
        return (actual_speed_m_s*self.curvature_yaw_per_m,
                actual_speed_m_s*self.curvature_pitch_per_m)


def validate(profile: str, speed_code: int, yaw_q: int, pitch_q: int) -> MotionCommand:
    limit = curvature_limit_squared(profile,speed_code)
    for value in (yaw_q,pitch_q):
        if type(value) is not int or not -15000 <= value <= 15000:
            raise ValueError('angular code outside integer +/-15000 range')
    # Python integers are unbounded. Hardware implementations use >=64 bits.
    if yaw_q*yaw_q + pitch_q*pitch_q > limit:
        raise ValueError('quantized combined curvature exceeds 0.5 per metre')
    target = float(SPEED_STEP[profile]*speed_code)
    if target == 0:
        # The zero ROM entry already requires both codes to be zero.
        yaw_curvature = pitch_curvature = 0.0
    else:
        yaw_curvature = yaw_q*math.pi/(180000*target)
        pitch_curvature = pitch_q*math.pi/(180000*target)
    return MotionCommand(profile,target,yaw_curvature,pitch_curvature,float(SPEED_STEP[profile]*20))


def step_speed(actual_m_s: float, target_m_s: float, dt_s: float) -> float:
    """Reference acceleration step, 0.25 m/s2 at 100 Hz or finer substeps.

    This computes a scalar only. It cannot establish that a swept body or its
    braking tail is collision-free or authorize advancing the simulated world.
    """
    _finite_nonnegative(actual_m_s,.25)
    _finite_nonnegative(target_m_s,.25)
    if isinstance(dt_s,bool) or not isinstance(dt_s,(int,float)) or not math.isfinite(dt_s) or not 0 < dt_s <= .01:
        raise ValueError('physical substep must be positive and at most 10 ms')
    bound = .25*dt_s
    delta = target_m_s-actual_m_s
    if abs(delta) <= bound:
        return target_m_s
    return actual_m_s + math.copysign(bound,delta)

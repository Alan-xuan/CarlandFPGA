"""Bounded software-fixture 3D candidate rollouts, without execution authority.

All dynamics use the unchanged kinematics module. Constant body curvature is
integrated analytically in travelled length, including acceleration saturation.
There is no map, scene, learning, wire, controller, gate or arrival interface.
"""
from dataclasses import dataclass
import hashlib
import itertools
import json
import math
import re

from .kinematics import (PrimitiveRejected, angular_rate_rad_s,
                         step_speed_m_s, target_speed_m_s, validate_primitive)

SOURCE_DOMAIN = "software_fixture"
DT_S = 0.01
MAX_ROTATION_RAD = math.pi / 3600.0  # 0.05 degree
MAX_COMMANDS = 8
MAX_CANDIDATES = 32
MAX_SUBSTEPS = 8192
MAX_GRID_COMBINATIONS = 512
MAX_COORDINATE_M = 1000.0
_HORIZON = {"fast_9600": 300, "stress_300": 1200}


class TrajectoryError(ValueError):
    """Invalid/bounded input, rejected without clipping."""


def finite(value, name, low, high):
    if type(value) not in (int, float):
        raise TrajectoryError(name + " must be an exact int or finite float, never bool")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise TrajectoryError(name + " is outside the finite domain") from exc
    if not math.isfinite(result) or not low <= result <= high:
        raise TrajectoryError(name + " outside finite bounds")
    if type(value) is int and result != value:
        raise TrajectoryError(name + " cannot be converted losslessly")
    return 0.0 if result == 0.0 else result


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise TrajectoryError(name + " must be an exact bounded integer")
    return value


def sequence(value, name, low, high):
    if type(value) not in (tuple, list) or not low <= len(value) <= high:
        raise TrajectoryError(name + " must be a bounded list/tuple")
    return tuple(value)


def digest(value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def scale(a, value):
    return tuple(x * value for x in a)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def quaternion_multiply(a, b):
    av, bv = a[:3], b[:3]
    xyz = add(add(scale(bv, a[3]), scale(av, b[3])), cross(av, bv))
    return xyz + (a[3] * b[3] - sum(x * y for x, y in zip(av, bv)),)


def rotate(q, vector):
    t = scale(cross(q[:3], vector), 2.0)
    return add(vector, add(scale(t, q[3]), cross(q[:3], t)))


@dataclass(frozen=True)
class Pose3:
    position: tuple
    quaternion_xyzw: tuple

    def __post_init__(self):
        p = sequence(self.position, "position", 3, 3)
        p = tuple(finite(v, "position", -MAX_COORDINATE_M, MAX_COORDINATE_M) for v in p)
        q = sequence(self.quaternion_xyzw, "quaternion_xyzw", 4, 4)
        q = tuple(finite(v, "quaternion_xyzw", -1.0, 1.0) for v in q)
        if abs(sum(v * v for v in q) - 1.0) > 1e-12:
            raise TrajectoryError("quaternion must already be normalized; input is never normalized silently")
        # q and -q represent the same attitude; choose one canonical sign.
        sign_value = q[3] if q[3] else next((v for v in q[:3] if v), 1.0)
        if sign_value < 0:
            q = tuple(-v if v else 0.0 for v in q)
        object.__setattr__(self, "position", p)
        object.__setattr__(self, "quaternion_xyzw", q)


@dataclass(frozen=True)
class Command:
    profile: str
    speed_code: int
    yaw_q: int
    pitch_q: int
    duration_ticks: int

    def __post_init__(self):
        try:
            validate_primitive(self.profile, self.speed_code, self.yaw_q, self.pitch_q)
        except PrimitiveRejected as exc:
            raise TrajectoryError(str(exc)) from exc
        integer(self.duration_ticks, "duration_ticks", 1, _HORIZON[self.profile])

    def primitive(self):
        return validate_primitive(self.profile, self.speed_code, self.yaw_q, self.pitch_q)

    def canonical(self):
        return (self.profile, self.speed_code, self.yaw_q, self.pitch_q, self.duration_ticks)


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    commands: tuple
    source_domain: str = SOURCE_DOMAIN

    def __post_init__(self):
        if type(self.candidate_id) is not str or re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", self.candidate_id) is None:
            raise TrajectoryError("candidate_id must be 1..64 simple identifier characters")
        if type(self.source_domain) is not str or self.source_domain != SOURCE_DOMAIN:
            raise TrajectoryError("only explicit software_fixture candidates are supported")
        commands = sequence(self.commands, "commands", 1, MAX_COMMANDS)
        if any(type(c) is not Command for c in commands):
            raise TrajectoryError("commands must contain validated Command instances")
        if any(c.profile != commands[0].profile for c in commands):
            raise TrajectoryError("one candidate must use one profile; mode changes belong to runtime")
        if sum(c.duration_ticks for c in commands) > _HORIZON[commands[0].profile]:
            raise TrajectoryError("cumulative profile horizon exceeded")
        object.__setattr__(self, "commands", commands)

    def canonical(self):
        return (self.candidate_id, self.source_domain, tuple(c.canonical() for c in self.commands))


@dataclass(frozen=True)
class CandidateSet:
    status: str
    candidates: tuple
    rejected_codes: tuple
    input_digest: str
    movement_authorized: bool = False


def generate_candidates(*, profile, speed_codes, yaw_codes, pitch_codes,
                        duration_ticks, max_candidates=MAX_CANDIDATES,
                        source_domain=SOURCE_DOMAIN):
    """Deterministic legal 3D fan; rejected curvature combinations are explicit.

    Codes outside wire ranges are malformed input. In-range Cartesian tuples
    that violate the combined curvature/zero-speed rule are recorded rejected.
    Exceeding the legal-candidate budget returns no partial candidate set.
    """
    if source_domain != SOURCE_DOMAIN or type(source_domain) is not str:
        raise TrajectoryError("only explicit software_fixture candidate generation")
    try:
        target_speed_m_s(profile, 0)
    except PrimitiveRejected as exc:
        raise TrajectoryError(str(exc)) from exc
    integer(duration_ticks, "duration_ticks", 1, _HORIZON[profile])
    integer(max_candidates, "max_candidates", 0, MAX_CANDIDATES)
    codes = []
    for name, values, lo, hi in (("speed_codes", speed_codes, 0, 20),
                                ("yaw_codes", yaw_codes, -15000, 15000),
                                ("pitch_codes", pitch_codes, -15000, 15000)):
        entries = sequence(values, name, 1, 21)
        entries = tuple(integer(v, name, lo, hi) for v in entries)
        if len(set(entries)) != len(entries):
            raise TrajectoryError(name + " contains duplicate codes")
        codes.append(tuple(sorted(entries)))
    if math.prod(map(len, codes)) > MAX_GRID_COMBINATIONS:
        raise TrajectoryError("candidate Cartesian grid exceeds bounded combinations")
    input_digest = digest((profile, codes, duration_ticks, source_domain, max_candidates))
    accepted, rejected = [], []
    for speed, yaw, pitch in itertools.product(*codes):
        try:
            command = Command(profile, speed, yaw, pitch, duration_ticks)
        except TrajectoryError:
            rejected.append((speed, yaw, pitch))
            continue
        if len(accepted) >= max_candidates:
            return CandidateSet("budget_exhausted", (), tuple(rejected), input_digest)
        name = "s%d_y%d_p%d" % (speed, yaw, pitch)
        accepted.append(Candidate(name, (command,)))
    return CandidateSet("completed", tuple(accepted), tuple(rejected), input_digest)


@dataclass(frozen=True)
class Sample:
    time_s: float
    pose: Pose3
    speed_m_s: float
    travelled_m: float
    interval_travel_m: float
    interval_rotation_rad: float
    command_index: int


@dataclass(frozen=True)
class Trajectory:
    status: str
    samples: tuple
    input_digest: str
    substeps_used: int
    movement_authorized: bool = False


def integrate_speed(actual_speed, target, dt):
    """Exact integral of the declared bounded acceleration until target hit."""
    actual_speed = finite(actual_speed, "actual_speed", 0.0, 0.25)
    target = finite(target, "target", 0.0, 0.25)
    dt = finite(dt, "dt", 0.0, DT_S)
    if dt == 0.0:
        raise TrajectoryError("dt must be positive")
    final = step_speed_m_s(actual_speed, target, dt)
    difference = target - actual_speed
    if difference == 0:
        return final, actual_speed * dt
    hit = min(dt, abs(difference) / 0.25)
    acceleration = math.copysign(0.25, difference)
    distance = actual_speed * hit + 0.5 * acceleration * hit * hit + target * (dt - hit)
    return final, distance


def _advance(pose, primitive, distance):
    # local +Z is forward; body angular curvature is (-pitch, yaw, 0).
    u = (-primitive.curvature_pitch_per_m, primitive.curvature_yaw_per_m, 0.0)
    k = math.hypot(u[0], u[1])
    theta = k * distance
    if k == 0.0:
        displacement = (0.0, 0.0, distance)
        dq = (0.0, 0.0, 0.0, 1.0)
    else:
        axis = scale(u, 1.0 / k)
        displacement = add((0.0, 0.0, math.sin(theta) / k),
                           scale(cross(axis, (0.0, 0.0, 1.0)), 2.0 * math.sin(theta / 2.0) ** 2 / k))
        dq = scale(axis, math.sin(theta / 2.0)) + (math.cos(theta / 2.0),)
    q = quaternion_multiply(pose.quaternion_xyzw, dq)  # body-side RIGHT multiply
    qnorm = math.sqrt(sum(value * value for value in q))
    q = tuple(value / qnorm for value in q)  # computed-state roundoff only
    return Pose3(add(pose.position, rotate(pose.quaternion_xyzw, displacement)), q), theta


def rollout_candidate(start_pose, initial_speed_m_s, candidate, *, max_substeps=MAX_SUBSTEPS):
    if type(start_pose) is not Pose3 or type(candidate) is not Candidate:
        raise TrajectoryError("start_pose/Candidate exact immutable types required")
    integer(max_substeps, "max_substeps", 0, MAX_SUBSTEPS)
    speed = finite(initial_speed_m_s, "initial_speed_m_s", 0.0,
                   target_speed_m_s(candidate.commands[0].profile, 20))
    input_digest = digest((start_pose.position, start_pose.quaternion_xyzw, speed,
                           candidate.canonical(), max_substeps))
    pose, travelled, elapsed = start_pose, 0.0, 0.0
    samples = [Sample(0.0, pose, speed, 0.0, 0.0, 0.0, 0)]
    used = 0
    for command_index, command in enumerate(candidate.commands):
        primitive = command.primitive()
        for _ in range(command.duration_ticks):
            yaw, pitch = angular_rate_rad_s(primitive, max(speed, primitive.target_speed_m_s))
            subdivisions = max(1, math.ceil(math.hypot(yaw, pitch) * DT_S / MAX_ROTATION_RAD))
            if used + subdivisions > max_substeps:
                return Trajectory("budget_exhausted", (), input_digest, used)
            dt = DT_S / subdivisions
            for _ in range(subdivisions):
                speed, distance = integrate_speed(speed, primitive.target_speed_m_s, dt)
                pose, theta = _advance(pose, primitive, distance)
                if theta > MAX_ROTATION_RAD + 1e-15:
                    raise TrajectoryError("internal rotation-subdivision bound violated")
                travelled += distance
                elapsed += dt
                used += 1
                samples.append(Sample(elapsed, pose, speed, travelled, distance, theta, command_index))
    return Trajectory("completed", tuple(samples), input_digest, used)


def rollout_candidates(start_pose, initial_speed_m_s, candidates, *, max_total_substeps=MAX_SUBSTEPS):
    """Shared deterministic budget; incomplete batch has no partial trajectories."""
    candidates = sequence(candidates, "candidates", 1, MAX_CANDIDATES)
    if any(type(c) is not Candidate for c in candidates):
        raise TrajectoryError("candidates must be Candidate instances")
    if len({c.candidate_id for c in candidates}) != len(candidates):
        raise TrajectoryError("duplicate candidate identifier")
    integer(max_total_substeps, "max_total_substeps", 0, MAX_SUBSTEPS)
    results, used = [], 0
    for candidate in sorted(candidates, key=lambda c: c.candidate_id):
        result = rollout_candidate(start_pose, initial_speed_m_s, candidate,
                                   max_substeps=max_total_substeps - used)
        used += result.substeps_used
        if result.status != "completed":
            return ("budget_exhausted", (), used)
        results.append((candidate.candidate_id, result))
    return ("completed", tuple(results), used)

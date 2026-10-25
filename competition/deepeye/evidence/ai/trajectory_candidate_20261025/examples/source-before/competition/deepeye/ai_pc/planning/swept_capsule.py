"""Conservative continuous whole-capsule checks on explicit software fixtures.

The bounding-box support deliberately over-encloses a capsule chord cast,
rotation, arc departure and caller initial pose uncertainty. Only one explicit
free region containing the entire support proves fixture-clear. Missing or
union-only coverage is unknown; no engine/world/physical permission is issued.
"""
from dataclasses import dataclass, field
import math

from .trajectory_candidates import (Candidate, Pose3, SOURCE_DOMAIN, TrajectoryError,
                                    digest, finite, integer, rotate, rollout_candidate,
                                    sequence, MAX_SUBSTEPS)

HALF_AXIS_M = 0.40
RADIUS_M = 0.12
R_BODY_M = 0.52
BASELINE_MARGIN_M = 0.0005
MAX_REGIONS = 128
MAX_GEOMETRY_CHECKS = 1000000
__all__ = ["Box", "Region", "FixtureMap", "Uncertainty", "SweptSupport", "SweepResult", "check_candidate"]


@dataclass(frozen=True)
class Box:
    lower: tuple
    upper: tuple

    def __post_init__(self):
        lower = tuple(finite(v, "box lower", -1e6, 1e6) for v in sequence(self.lower, "box lower", 3, 3))
        upper = tuple(finite(v, "box upper", -1e6, 1e6) for v in sequence(self.upper, "box upper", 3, 3))
        if any(lo >= hi for lo, hi in zip(lower, upper)):
            raise TrajectoryError("boxes require strictly positive extent on every axis")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


@dataclass(frozen=True)
class Region:
    region_id: str
    kind: str
    box: Box

    def __post_init__(self):
        if type(self.region_id) is not str or not 1 <= len(self.region_id) <= 64:
            raise TrajectoryError("bounded region_id required")
        if type(self.kind) is not str or self.kind not in ("occupied", "unknown", "free"):
            raise TrajectoryError("region kind must be occupied/unknown/free")
        if type(self.box) is not Box:
            raise TrajectoryError("region box must be an immutable Box")


@dataclass(frozen=True)
class FixtureMap:
    cube: Box
    regions: tuple = ()
    source_domain: str = SOURCE_DOMAIN

    def __post_init__(self):
        if type(self.source_domain) is not str or self.source_domain != SOURCE_DOMAIN:
            raise TrajectoryError("map must explicitly be software_fixture")
        if type(self.cube) is not Box:
            raise TrajectoryError("cube must be Box")
        widths = tuple(hi - lo for lo, hi in zip(self.cube.lower, self.cube.upper))
        if max(widths) - min(widths) > 1e-12:
            raise TrajectoryError("boundary must be a cube with equal extents")
        regions = sequence(self.regions, "regions", 0, MAX_REGIONS)
        if any(type(r) is not Region for r in regions) or len({r.region_id for r in regions}) != len(regions):
            raise TrajectoryError("regions must be immutable Region instances with unique IDs")
        object.__setattr__(self, "regions", tuple(sorted(regions, key=lambda r: r.region_id)))

    def canonical(self):
        return (self.source_domain, self.cube.lower, self.cube.upper,
                tuple((r.region_id, r.kind, r.box.lower, r.box.upper) for r in self.regions))


@dataclass(frozen=True)
class Uncertainty:
    initial_position_m: float = 0.0
    initial_orientation_rad: float = 0.0
    extra_numeric_m: float = 1e-6
    occupancy_inflation_m: float = 0.0

    def __post_init__(self):
        for name, lo, hi in (("initial_position_m", 0.0, 10.0),
                             ("initial_orientation_rad", 0.0, math.pi),
                             ("extra_numeric_m", 1e-6, 0.01),
                             ("occupancy_inflation_m", 0.0, 10.0)):
            object.__setattr__(self, name, finite(getattr(self, name), name, lo, hi))


@dataclass(frozen=True)
class SweptSupport:
    lower: tuple
    upper: tuple
    interval_index: int
    rotation_margin_m: float
    translation_arc_margin_m: float
    uncertainty_margin_m: float
    numeric_margin_m: float


@dataclass(frozen=True)
class SweepResult:
    status: str
    fixture_digest: str
    input_digest: str
    substeps_used: int
    geometry_checks_used: int
    blocking_interval: object
    blocking_region: object
    supports: tuple
    movement_authorized: bool = field(default=False, init=False)


def _support(start, end, index, uncertainty):
    forward = rotate(start.pose.quaternion_xyzw, (0.0, 0.0, 1.0))
    points = tuple(tuple(center[i] + sign * HALF_AXIS_M * forward[i] for i in range(3))
                   for center in (start.pose.position, end.pose.position) for sign in (-1.0, 1.0))
    rotation = max(BASELINE_MARGIN_M, 2.0 * R_BODY_M * math.sin(end.interval_rotation_rad / 2.0))
    # Every arc point is <= travelled length from the chord's initial endpoint.
    # This intentionally loose bound is valid without a sagitta approximation.
    arc = end.interval_travel_m if index else 0.0
    initial_error = (uncertainty.initial_position_m
                     + 2.0 * (R_BODY_M + end.travelled_m) * math.sin(uncertainty.initial_orientation_rad / 2.0))
    magnitude = max(1.0, *(abs(v) for point in points for v in point))
    # Positive declared numeric allowance plus accumulated engineering reserve,
    # coordinate ULP reserve and outward-rounded final bounds; see the document.
    numeric = uncertainty.extra_numeric_m + (index + 1) * 1e-8 + 32.0 * math.ulp(magnitude)
    expansion = RADIUS_M + rotation + arc + initial_error + numeric
    lower = tuple(math.nextafter(min(p[i] for p in points) - expansion, -math.inf) for i in range(3))
    upper = tuple(math.nextafter(max(p[i] for p in points) + expansion, math.inf) for i in range(3))
    return SweptSupport(lower, upper, index, rotation, arc, initial_error, numeric)


def _intersects(support, box, inflation=0.0):
    # Closed occupied/unknown regions: tangency is contact, never clear.
    return all(support.upper[i] >= math.nextafter(box.lower[i] - inflation, -math.inf)
               and support.lower[i] <= math.nextafter(box.upper[i] + inflation, math.inf) for i in range(3))


def _strict_inside(support, box):
    return all(box.lower[i] < support.lower[i] and support.upper[i] < box.upper[i] for i in range(3))


def _covered(support, box):
    return all(box.lower[i] <= support.lower[i] and support.upper[i] <= box.upper[i] for i in range(3))


def check_candidate(start_pose, initial_speed_m_s, candidate, fixture_map, *,
                    uncertainty=None, max_substeps=MAX_SUBSTEPS,
                    max_geometry_checks=MAX_GEOMETRY_CHECKS):
    """Integrate canonical inputs internally; never accepts forged sample arrays.

    AABB false positives and unknowns are intentional. Initial overlap is
    checked separately; every subsequent support encloses a full interval.
    Budget exhaustion returns no supports, never a partial clear result.
    """
    if type(start_pose) is not Pose3 or type(candidate) is not Candidate or type(fixture_map) is not FixtureMap:
        raise TrajectoryError("exact Pose3/Candidate/FixtureMap inputs required")
    if uncertainty is None:
        uncertainty = Uncertainty()
    if type(uncertainty) is not Uncertainty:
        raise TrajectoryError("uncertainty must be immutable Uncertainty")
    integer(max_geometry_checks, "max_geometry_checks", 0, MAX_GEOMETRY_CHECKS)
    trajectory = rollout_candidate(start_pose, initial_speed_m_s, candidate, max_substeps=max_substeps)
    fixture_digest = digest(fixture_map.canonical())
    input_digest = digest((trajectory.input_digest, fixture_digest,
                           (uncertainty.initial_position_m, uncertainty.initial_orientation_rad,
                            uncertainty.extra_numeric_m, uncertainty.occupancy_inflation_m), max_geometry_checks))
    used = 0
    supports = []

    def result(status, interval=None, region=None):
        retained = () if status == "budget_exhausted" else tuple(supports)
        return SweepResult(status, fixture_digest, input_digest, trajectory.substeps_used,
                           used, interval, region, retained)

    if trajectory.status != "completed":
        return result("budget_exhausted")
    for index, end in enumerate(trajectory.samples):
        start = trajectory.samples[max(0, index - 1)]
        support = _support(start, end, index, uncertainty)
        supports.append(support)
        if used >= max_geometry_checks:
            return result("budget_exhausted")
        used += 1
        if not _strict_inside(support, fixture_map.cube):
            return result("conservative_boundary_overlap", index, "closed_cube")
        for kind in ("occupied", "unknown", "free"):
            found_free = False
            for region in fixture_map.regions:
                if region.kind != kind:
                    continue
                if used >= max_geometry_checks:
                    return result("budget_exhausted")
                used += 1
                if kind == "free":
                    if _covered(support, region.box):
                        found_free = True
                        break
                elif _intersects(support, region.box,
                                 uncertainty.occupancy_inflation_m if kind == "occupied" else 0.0):
                    return result("conservative_" + kind + "_overlap", index, region.region_id)
            if kind == "free" and not found_free:
                return result("unknown_missing_coverage", index, "missing_full_support_free_coverage")
    return result("clear_for_supplied_fixture")

"""New conservative whole-body fixture sweep checks (no real map or board)."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from ai_pc.planning.trajectory_candidates import Candidate, Command, Pose3, TrajectoryError, rollout_candidate
from ai_pc.planning.swept_capsule import Box, FixtureMap, Region, Uncertainty, check_candidate

IDENTITY = (0, 0, 0, 1)
CUBE = Box((-2, -2, -2), (2, 2, 2))
FREE = Region("free", "free", CUBE)


def candidate(ticks=1, yaw=0, pitch=0):
    return Candidate("test", (Command("fast_9600", 20, yaw, pitch, ticks),))


def fixture(*regions, cube=CUBE):
    return FixtureMap(cube, (FREE,) + regions)


def tiny_region(name, center, half=1e-7, kind="occupied"):
    return Region(name, kind, Box(tuple(v - half for v in center), tuple(v + half for v in center)))


def point_segment_distance(point, a, b):
    direction = tuple(y - x for x, y in zip(a, b))
    length2 = sum(v * v for v in direction)
    t = max(0.0, min(1.0, sum((point[i] - a[i]) * direction[i] for i in range(3)) / length2))
    return math.sqrt(sum((point[i] - a[i] - t * direction[i]) ** 2 for i in range(3)))


class SweepTests(unittest.TestCase):
    def test_nonempty3d_clear_requires_full_free_support(self):
        result = check_candidate(Pose3((0, 0, 0), IDENTITY), .25,
                                 candidate(100, 4000, 3000), fixture())
        self.assertEqual(result.status, "clear_for_supplied_fixture")
        self.assertGreater(len(result.supports), 100)
        self.assertFalse(result.movement_authorized)
        self.assertTrue(all(s.rotation_margin_m >= .0005 and s.numeric_margin_m > 0 for s in result.supports))

    def test_missing_partial_and_union_only_free_coverage_are_unknown(self):
        pose = Pose3((0, 0, 0), IDENTITY)
        maps = [FixtureMap(CUBE), FixtureMap(CUBE, (Region("tip-only", "free", Box((-.2, -.2, .3), (.2, .2, .6))),)),
                FixtureMap(CUBE, (Region("left", "free", Box((-2, -2, -2), (0, 2, 2))),
                                  Region("right", "free", Box((0, -2, -2), (2, 2, 2)))))]
        for value in maps:
            result = check_candidate(pose, .25, candidate(), value)
            self.assertEqual(result.status, "unknown_missing_coverage")
            self.assertFalse(result.movement_authorized)

    def test_explicit_unknown_and_occupied_override_covering_free(self):
        for kind in ("unknown", "occupied"):
            result = check_candidate(Pose3((0, 0, 0), IDENTITY), .25, candidate(),
                                     fixture(tiny_region("obstacle", (0, 0, 0), kind=kind)))
            self.assertEqual(result.status, "conservative_" + kind + "_overlap")
            self.assertEqual(result.blocking_interval, 0)

    def test_initial_side_and_tail_contact_detected_separately(self):
        for point in ((0, 0, -.5), (.119, 0, 0), (0, 0, .5)):
            result = check_candidate(Pose3((0, 0, 0), IDENTITY), .25, candidate(), fixture(tiny_region("contact", point)))
            self.assertEqual(result.status, "conservative_occupied_overlap")
            self.assertEqual(result.blocking_interval, 0)

    def test_closed_cube_and_real_tangency_have_no_gate_exemption(self):
        cube = Box((-1, -1, -1), (1, 1, 1))
        value = FixtureMap(cube, (Region("allfree", "free", cube),))
        for pose in (Pose3((0, 0, .48), IDENTITY), Pose3((.88, 0, 0), IDENTITY)):
            result = check_candidate(pose, .25, candidate(), value)
            self.assertEqual(result.status, "conservative_boundary_overlap")
        tangent = Region("tangent", "occupied", Box((.12, -.01, -.01), (.13, .01, .01)))
        result = check_candidate(Pose3((0, 0, 0), IDENTITY), .25, candidate(), fixture(tangent))
        self.assertEqual(result.status, "conservative_occupied_overlap")

    def test_thin_layer_between_rollout_endpoints_rejected(self):
        # Independent exact mid-arc pose + outer capsule surface. This point is
        # outside both actual start/end capsules, yet lies on the mid capsule.
        k = 7000 * math.pi / (180000 * .25)
        def pose_at(seconds):
            angle = k * .25 * seconds
            p = ((1 - math.cos(angle)) / k, 0, math.sin(angle) / k)
            forward = (math.sin(angle), 0, math.cos(angle))
            return p, forward
        p, f = pose_at(1.5)
        normal = (-f[2], 0, f[0])
        point = tuple(p[i] + .4 * f[i] + .119999 * normal[i] for i in range(3))
        for seconds in (0, 3):
            center, axis = pose_at(seconds)
            a = tuple(center[i] - .4 * axis[i] for i in range(3))
            b = tuple(center[i] + .4 * axis[i] for i in range(3))
            self.assertGreater(point_segment_distance(point, a, b), .1201)
        result = check_candidate(Pose3((0, 0, 0), IDENTITY), .25,
                                 candidate(300, 7000), fixture(tiny_region("thin", point, 1e-8)))
        self.assertEqual(result.status, "conservative_occupied_overlap")
        self.assertGreater(result.blocking_interval, 0)
        self.assertLess(result.blocking_interval, result.substeps_used)

    def test_continuous_support_encloses_independent_interior_capsule_points(self):
        yaw, pitch = 4000, 3000
        kx, ky = -pitch * math.pi / (180000 * .25), yaw * math.pi / (180000 * .25)
        k = math.hypot(kx, ky)
        result = check_candidate(Pose3((0, 0, 0), IDENTITY), .25,
                                 candidate(20, yaw, pitch), fixture())
        self.assertEqual(result.status, "clear_for_supplied_fixture")
        # Reference Rodrigues formulas at interior fractions, independent of
        # the production quaternion/arc/inflation helper functions.
        previous_t = 0.0
        samples = rollout_candidate(Pose3((0, 0, 0), IDENTITY), .25, candidate(20, yaw, pitch)).samples
        for support, sample in zip(result.supports[1:], samples[1:]):
            for fraction in (.01, .25, .5, .75, .99):
                t = previous_t + fraction * (sample.time_s - previous_t)
                theta = k * .25 * t
                center = (ky * (1 - math.cos(theta)) / (k * k),
                          -kx * (1 - math.cos(theta)) / (k * k), math.sin(theta) / k)
                forward = (ky / k * math.sin(theta), -kx / k * math.sin(theta), math.cos(theta))
                for sign in (-1, 1):
                    for axis in range(3):
                        for radial in (-.12, .12):
                            point = [center[i] + sign * .4 * forward[i] for i in range(3)]
                            point[axis] += radial  # sphere around each end
                            self.assertTrue(all(support.lower[i] <= point[i] <= support.upper[i] for i in range(3)))
            previous_t = sample.time_s

    def test_whole_support_uncertainty_and_occupancy_inflation_monotonic(self):
        map_value = fixture(tiny_region("near-side", (.16, 0, 0), .001))
        pose = Pose3((0, 0, 0), IDENTITY)
        base = check_candidate(pose, .25, candidate(10), map_value)
        self.assertEqual(base.status, "clear_for_supplied_fixture")
        for name, values in (("initial_position_m", (0.0, .01, .04, .08)),
                              ("initial_orientation_rad", (0.0, .01, .1, .2)),
                              ("occupancy_inflation_m", (0.0, .01, .04, .08))):
            seen_nonclear = False
            for value in values:
                result = check_candidate(pose, .25, candidate(10), map_value, uncertainty=Uncertainty(**{name: value}))
                if seen_nonclear:
                    self.assertNotEqual(result.status, "clear_for_supplied_fixture")
                seen_nonclear |= result.status != "clear_for_supplied_fixture"
            self.assertTrue(seen_nonclear)

    def test_initial_angular_uncertainty_includes_travel_displacement(self):
        result = check_candidate(Pose3((0, 0, 0), IDENTITY), .25, candidate(100), fixture(),
                                 uncertainty=Uncertainty(initial_orientation_rad=.1))
        self.assertEqual(result.status, "clear_for_supplied_fixture")
        self.assertAlmostEqual(result.supports[-1].uncertainty_margin_m,
                               2 * (.52 + .25) * math.sin(.05), places=12)
        self.assertGreater(result.supports[-1].uncertainty_margin_m, result.supports[0].uncertainty_margin_m)

    def test_budgets_are_deterministic_and_never_partial_clear(self):
        pose, c, m = Pose3((0, 0, 0), IDENTITY), candidate(), fixture()
        for kwargs in ({"max_substeps": 0}, {"max_geometry_checks": 0}, {"max_geometry_checks": 3}):
            first = check_candidate(pose, .25, c, m, **kwargs)
            self.assertEqual(first, check_candidate(pose, .25, c, m, **kwargs))
            self.assertEqual((first.status, first.supports), ("budget_exhausted", ()))
            self.assertFalse(first.movement_authorized)
        complete = check_candidate(pose, .25, c, m, max_geometry_checks=4)
        self.assertEqual(complete.status, "clear_for_supplied_fixture")
        self.assertEqual(complete.geometry_checks_used, 4)

    def test_map_pose_and_output_aliases_are_immutable_and_digests_stable(self):
        lo, hi = [-2, -2, -2], [2, 2, 2]
        cube = Box(lo, hi)
        regions = [Region("z", "free", cube), tiny_region("a", (.8, .8, .8), kind="unknown")]
        m1 = FixtureMap(cube, regions)
        m2 = FixtureMap(cube, list(reversed(regions)))
        first = check_candidate(Pose3((0, 0, 0), IDENTITY), .25, candidate(), m1)
        lo[0], hi[0] = 100, 101
        regions.clear()
        self.assertEqual(first, check_candidate(Pose3((0, 0, 0), IDENTITY), .25, candidate(), m2))
        with self.assertRaises((AttributeError, TypeError)):
            first.supports[0].lower[0] = 0

    def test_all_uncertainty_and_map_inputs_finite_bounded_explicit(self):
        for kwargs in ({"initial_position_m": True}, {"initial_position_m": -1},
                       {"initial_orientation_rad": math.pi + .01}, {"extra_numeric_m": 0},
                       {"occupancy_inflation_m": float("nan")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TrajectoryError):
                Uncertainty(**kwargs)
        for kwargs in ({"source_domain": "sensor_live"}, {"source_domain": True}):
            with self.assertRaises(TrajectoryError):
                FixtureMap(CUBE, **kwargs)
        with self.assertRaises(TrajectoryError):
            Box((0, 0, 0), (1, 0, 1))
        with self.assertRaises(TrajectoryError):
            FixtureMap(Box((0, 0, 0), (1, 2, 1)))


if __name__ == "__main__":
    unittest.main(verbosity=2)

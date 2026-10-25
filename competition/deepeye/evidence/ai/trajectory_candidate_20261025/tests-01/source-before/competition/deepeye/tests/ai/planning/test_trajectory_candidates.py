"""New trajectory-only checks with independent closed-form expectations."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from ai_pc.planning.trajectory_candidates import (
    Candidate, Command, MAX_ROTATION_RAD, Pose3, TrajectoryError,
    generate_candidates, integrate_speed, rollout_candidate, rollout_candidates,
)

IDENTITY = (0.0, 0.0, 0.0, 1.0)


def command(speed=20, yaw=0, pitch=0, ticks=100, profile="fast_9600"):
    return Command(profile, speed, yaw, pitch, ticks)


def rollout(commands, speed=0.25, pose=None, **kwargs):
    return rollout_candidate(pose or Pose3((0, 0, 0), IDENTITY), speed,
                             Candidate("test", tuple(commands)), **kwargs)


def analytic_arc(yaw, pitch, speed, seconds):
    # Independent wire-to-curvature reference, no production helper imports.
    ky = yaw * math.pi / (180000 * speed)
    kp = pitch * math.pi / (180000 * speed)
    k = math.sqrt(ky * ky + kp * kp)
    length = speed * seconds
    if k == 0:
        return (0.0, 0.0, length), IDENTITY
    theta = k * length
    return ((ky * (1 - math.cos(theta)) / (k * k),
             kp * (1 - math.cos(theta)) / (k * k), math.sin(theta) / k),
            (-kp / k * math.sin(theta / 2), ky / k * math.sin(theta / 2),
             0.0, math.cos(theta / 2)))


class TrajectoryTests(unittest.TestCase):
    def assertVectorAlmost(self, actual, expected, places=11):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=places)

    def test_real_nonempty_combined_3d_candidate_fan(self):
        fan = generate_candidates(profile="fast_9600", speed_codes=[20],
                                  yaw_codes=[4000, 0, -4000], pitch_codes=[3000, 0, -3000],
                                  duration_ticks=100)
        self.assertEqual(fan.status, "completed")
        self.assertEqual(len(fan.candidates), 9)
        self.assertFalse(fan.movement_authorized)
        candidate = next(c for c in fan.candidates if c.commands[0].yaw_q == 4000 and c.commands[0].pitch_q == 3000)
        end = rollout_candidate(Pose3((0, 0, 0), IDENTITY), 0.25, candidate).samples[-1].pose.position
        self.assertTrue(all(value > 0 for value in end))

    def test_straight_and_combined_curvature_independent_analytic(self):
        for yaw, pitch in ((0, 0), (4000, 3000), (-4000, 3000), (4000, -3000), (0, 7000)):
            with self.subTest(yaw=yaw, pitch=pitch):
                actual = rollout([command(yaw=yaw, pitch=pitch, ticks=200)])
                position, quaternion = analytic_arc(yaw, pitch, .25, 2.0)
                self.assertEqual(actual.status, "completed")
                self.assertVectorAlmost(actual.samples[-1].pose.position, position)
                self.assertVectorAlmost(actual.samples[-1].pose.quaternion_xyzw, quaternion)
                self.assertAlmostEqual(actual.samples[-1].travelled_m, .5, places=12)

    def test_yaw_pitch_signs_and_body_right_global_rotation(self):
        angle = math.pi / 2
        pose = Pose3((1, 2, 3), (0, 0, math.sin(angle / 2), math.cos(angle / 2)))
        for yaw, pitch in ((6000, 0), (0, 6000), (4000, 3000)):
            local, q = analytic_arc(yaw, pitch, .25, 1)
            actual = rollout([command(yaw=yaw, pitch=pitch)], pose=pose).samples[-1].pose
            # Rz(90): local x->world y, local y->world -x.
            self.assertVectorAlmost(actual.position, (1 - local[1], 2 + local[0], 3 + local[2]))
            s, c = math.sin(angle / 2), math.cos(angle / 2)
            expected_q = (c * q[0] - s * q[1], c * q[1] + s * q[0], s * q[3], c * q[3])
            self.assertVectorAlmost(actual.quaternion_xyzw, expected_q)

    def test_distinct_body_primitive_sequence_is_non_coplanar(self):
        actual = rollout([command(yaw=6000), command(pitch=6000)])
        a = actual.samples[50].pose.position
        b = actual.samples[150].pose.position
        c = actual.samples[-1].pose.position
        determinant = (a[0] * (b[1] * c[2] - b[2] * c[1])
                       - a[1] * (b[0] * c[2] - b[2] * c[0])
                       + a[2] * (b[0] * c[1] - b[1] * c[0]))
        self.assertGreater(abs(determinant), 1e-7)
        self.assertNotEqual(actual.samples[-1].pose.quaternion_xyzw[2], 0.0)

    def test_acceleration_distance_includes_target_hit_inside_step(self):
        end_speed, distance = integrate_speed(.001, .002, .01)
        self.assertEqual(end_speed, .002)
        self.assertAlmostEqual(distance, .000018, places=15)
        end_speed, distance = integrate_speed(.001, 0.0, .01)
        self.assertEqual(end_speed, 0.0)
        self.assertAlmostEqual(distance, .000002, places=15)
        accelerated = rollout([command(ticks=300)], speed=0)
        self.assertAlmostEqual(accelerated.samples[-1].travelled_m, .625, places=11)
        self.assertAlmostEqual(accelerated.samples[-1].pose.position[2], .625, places=11)

    def test_acceleration_curved_arc_uses_integrated_length(self):
        actual = rollout([command(yaw=4000, pitch=3000, ticks=100)], speed=0)
        # 1 second at a=.25 from rest: L=.125. Equivalent arc at .25 for .5s.
        expected_p, expected_q = analytic_arc(4000, 3000, .25, .5)
        self.assertVectorAlmost(actual.samples[-1].pose.position, expected_p)
        self.assertVectorAlmost(actual.samples[-1].pose.quaternion_xyzw, expected_q)
        self.assertEqual(actual.samples[0].speed_m_s, 0.0)

    def test_zero_and_braking_never_pivot_or_reverse(self):
        pose = Pose3((0, 0, 0), (.5, .5, .5, .5))
        for initial in (0.0, .001, .25):
            actual = rollout([command(speed=0)], speed=initial, pose=pose)
            self.assertTrue(all(s.pose.quaternion_xyzw == pose.quaternion_xyzw for s in actual.samples))
            self.assertTrue(all(s.speed_m_s >= 0 for s in actual.samples))
            self.assertEqual(actual.samples[-1].speed_m_s, 0.0)
        with self.assertRaises(TrajectoryError):
            command(speed=0, yaw=1)

    def test_nominal100hz_rotation_substeps_and_acceleration_bounds(self):
        actual = rollout([command(yaw=7000, ticks=300)], speed=0)
        self.assertGreater(actual.substeps_used, 300)
        for a, b in zip(actual.samples, actual.samples[1:]):
            dt = b.time_s - a.time_s
            self.assertGreater(dt, 0)
            self.assertLessEqual(dt, .01 + 1e-12)
            self.assertLessEqual(b.interval_rotation_rad, MAX_ROTATION_RAD + 1e-15)
            self.assertLessEqual(abs(b.speed_m_s - a.speed_m_s), .25 * dt + 1e-12)
        self.assertAlmostEqual(actual.samples[-1].time_s, 3.0, places=11)

    def test_stress_speed_and_cumulative_single_profile_horizon(self):
        actual = rollout([command(speed=20, yaw=40, pitch=30, ticks=1200, profile="stress_300")], speed=.002)
        self.assertAlmostEqual(actual.samples[-1].travelled_m, .024, places=12)
        self.assertTrue(all(s.speed_m_s <= .002 for s in actual.samples))
        with self.assertRaises(TrajectoryError):
            rollout([command(profile="stress_300")], speed=.00201)
        with self.assertRaises(TrajectoryError):
            Candidate("mixed", (command(ticks=1), command(ticks=1, profile="stress_300")))
        with self.assertRaises(TrajectoryError):
            Candidate("long", (command(ticks=200), command(ticks=101)))

    def test_immutable_aliases_and_quaternion_sign_canonical_digest(self):
        position, q = [0, 0, 0], [0, 0, 0, 1]
        pose = Pose3(position, q)
        commands = [command(ticks=1)]
        candidate = Candidate("one", commands)
        expected = rollout_candidate(pose, .25, candidate)
        position[0], q[0] = 99, 1
        commands.append(command(ticks=1))
        self.assertEqual(expected, rollout_candidate(pose, .25, candidate))
        negative = rollout_candidate(Pose3((0, 0, 0), (0, 0, 0, -1)), .25, candidate)
        self.assertEqual(expected, negative)

    def test_deterministic_sorted_generation_and_explicit_rejections(self):
        a = generate_candidates(profile="fast_9600", speed_codes=[20, 0], yaw_codes=[1, 0], pitch_codes=[0], duration_ticks=1)
        b = generate_candidates(profile="fast_9600", speed_codes=[0, 20], yaw_codes=[0, 1], pitch_codes=[0], duration_ticks=1)
        self.assertEqual(a, b)
        self.assertIn((0, 1, 0), a.rejected_codes)
        exhausted = generate_candidates(profile="fast_9600", speed_codes=[20], yaw_codes=[1, 0], pitch_codes=[0], duration_ticks=1, max_candidates=1)
        self.assertEqual(exhausted.status, "budget_exhausted")
        self.assertEqual(exhausted.candidates, ())

    def test_budget_exhaustion_never_returns_partial_rollouts(self):
        c1, c2 = Candidate("a", (command(ticks=2),)), Candidate("b", (command(ticks=2),))
        pose = Pose3((0, 0, 0), IDENTITY)
        limited = rollout_candidate(pose, .25, c1, max_substeps=1)
        self.assertEqual((limited.status, limited.samples), ("budget_exhausted", ()))
        limited_batch = rollout_candidates(pose, .25, [c2, c1], max_total_substeps=3)
        self.assertEqual(limited_batch[:2], ("budget_exhausted", ()))
        self.assertEqual(rollout_candidates(pose, .25, [c2, c1], max_total_substeps=4),
                         rollout_candidates(pose, .25, [c1, c2], max_total_substeps=4))

    def test_bad_numeric_codes_shapes_and_unbounded_inputs_rejected(self):
        for position, quaternion in (((True, 0, 0), IDENTITY), ((float("nan"), 0, 0), IDENTITY),
                                     ((0, 0, 0), (0, 0, 0, 2)), ((0, 0, 0), (0, 0, float("inf"), 1))):
            with self.subTest(position=position, quaternion=quaternion), self.assertRaises(TrajectoryError):
                Pose3(position, quaternion)
        for kwargs in ({"yaw": True}, {"yaw": 15001}, {"speed": 21}, {"ticks": True}, {"ticks": 301}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TrajectoryError):
                command(**kwargs)
        for value in (0, -.1, .02, float("nan"), True):
            with self.subTest(dt=value), self.assertRaises(TrajectoryError):
                integrate_speed(0, .25, value)
        with self.assertRaises(TrajectoryError):
            Candidate("bad", (command(),), source_domain="sensor_live")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Fixture and boundary tests for ai_pc/planning/kinematics.py.

Software-only evidence: integer ROM agreement with an independently computed
high-precision pi (Machin arctan series), boundary accept/reject vectors,
zero-speed rule, scalar acceleration steps and invalid numeric types. These
tests are not collision checks, not planning search, not board measurements
and not acceptance of any product card.

Regenerate the fixture document with:
    python test_kinematics.py --regen-fixtures
"""

import dataclasses
import importlib.util
import json
import math
import ast
import sys
import unittest
from decimal import Decimal, ROUND_FLOOR, localcontext
from pathlib import Path

sys.dont_write_bytecode = True

_HERE = Path(__file__).resolve().parent
_VECTORS_PATH = _HERE / "kinematics_vectors.json"
_MODULE_PATH = _HERE.parents[2] / "ai_pc" / "planning" / "kinematics.py"

_RAW_STEPS = {"fast_9600": Decimal("0.0125"), "stress_300": Decimal("0.0001")}


def _load_module():
    spec = importlib.util.spec_from_file_location("deepeye_kinematics", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


kinematics = _load_module()


def _machin_pi():
    with localcontext() as context:
        context.prec = 190

        def atan_reciprocal(n):
            total = Decimal(0)
            power = Decimal(n)
            k = 0
            cutoff = Decimal(1).scaleb(-170)
            while True:
                term = Decimal(1) / (Decimal(2 * k + 1) * power)
                if k % 2 == 0:
                    total = total + term
                else:
                    total = total - term
                if term < cutoff:
                    return total
                k += 1
                power = power * n * n

        return Decimal(16) * atan_reciprocal(5) - Decimal(4) * atan_reciprocal(239)


def _independent_thresholds():
    pi = _machin_pi()
    table = {}
    margins = []
    with localcontext() as context:
        context.prec = 160
        for profile, step in _RAW_STEPS.items():
            row = []
            for code in range(kinematics.SPEED_CODE_MAX + 1):
                bound = Decimal(code) * step * Decimal(180000) / (2 * pi)
                squared = bound * bound
                floor_value = int(squared.to_integral_value(rounding=ROUND_FLOOR))
                if code > 0:
                    margins.append(squared - floor_value)
                row.append(floor_value)
            table[profile] = tuple(row)
    return pi, table, min(margins)


def _build_fixture_document():
    pi, expected, margin = _independent_thresholds()
    module_table = kinematics.CURVATURE_THRESHOLD_SQUARED
    for profile in _RAW_STEPS:
        if tuple(expected[profile]) != tuple(module_table[profile]):
            raise RuntimeError("module ROM disagrees with independent pi for " + profile)
    if margin <= Decimal("0.01"):
        raise RuntimeError("squared bound too close to an integer boundary")
    profiles = {}
    for profile, step in _RAW_STEPS.items():
        codes = []
        for code in range(kinematics.SPEED_CODE_MAX + 1):
            limit = expected[profile][code]
            axis = math.isqrt(limit)
            diag = math.isqrt(limit // 2)
            if axis + 1 > kinematics.Q_CODE_MAX or diag + 1 > kinematics.Q_CODE_MAX:
                raise RuntimeError("boundary vector outside code range")
            if axis * axis > limit or (axis + 1) * (axis + 1) <= limit:
                raise RuntimeError("axis boundary construction failed")
            if 2 * diag * diag > limit or 2 * (diag + 1) * (diag + 1) <= limit:
                raise RuntimeError("diagonal boundary construction failed")
            codes.append(
                {
                    "code": code,
                    "target_m_s": float(step * code),
                    "threshold": limit,
                    "axis_legal": [axis, 0],
                    "axis_reject": [axis + 1, 0],
                    "diag_legal": [diag, diag],
                    "diag_reject": [diag + 1, diag + 1],
                }
            )
        profiles[profile] = {"step_m_s": str(step), "codes": codes}
    with localcontext() as context:
        context.prec = 60
        samples = []
        for profile, code, yaw_q, pitch_q in (
            ("fast_9600", 20, 1000, -2000),
            ("stress_300", 20, 57, 0),
            ("stress_300", 20, 40, 40),
        ):
            v = _RAW_STEPS[profile] * code
            k_yaw = Decimal(yaw_q) * pi / (Decimal(180000) * v)
            k_pitch = Decimal(pitch_q) * pi / (Decimal(180000) * v)
            samples.append(
                {
                    "profile": profile,
                    "speed_code": code,
                    "yaw_q": yaw_q,
                    "pitch_q": pitch_q,
                    "curvature_yaw_per_m": str(k_yaw),
                    "curvature_pitch_per_m": str(k_pitch),
                    "reference_rate_yaw_deg_s": float(yaw_q) * 0.001,
                    "reference_rate_pitch_deg_s": float(pitch_q) * 0.001,
                }
            )
    return {
        "schema": 1,
        "kind": "deepeye-c-kinematics-fixtures",
        "task_id": "DEEPEYE-C-PLANNER-EXEC-20261015",
        "work_id": "C-finite-curvature-quantized-foundation-v1",
        "module": "ai_pc/planning/kinematics.py",
        "method": {
            "threshold_rule": "floor((speed_code * step_m_s * 180000 / (2 * pi))^2)",
            "module_pi_truncated_decimal_digits": 60,
            "independent_pi": "Machin arctan series, Decimal context precision 190",
            "independent_recursion_context_precision": 160,
            "min_squared_bound_distance_to_integer_nonzero_codes": str(margin),
            "conservatism_note": (
                "module literal is truncated pi (<= true pi); entries re-derived with"
                " independent high-precision pi give identical floors; margin > 0.01"
            ),
        },
        "profiles": profiles,
        "stress_300_code_20_required_vectors": {
            "threshold": expected["stress_300"][20],
            "legal": [[57, 0], [-57, 0], [40, 40], [40, -40]],
            "reject": [[58, 0], [0, -58], [41, 41], [-41, 41]],
        },
        "curvature_samples": samples,
        "speed_step_chains": {
            "acceleration": {
                "actual_m_s": 0.0,
                "target_m_s": 0.25,
                "dt_s": 0.01,
                "step_bound_m_s": 0.0025,
                "max_steps": 120,
                "expected_final_m_s": 0.25,
            },
            "deceleration": {
                "actual_m_s": 0.25,
                "target_m_s": 0.0,
                "dt_s": 0.01,
                "step_bound_m_s": 0.0025,
                "max_steps": 120,
                "expected_final_m_s": 0.0,
            },
        },
        "invalid_input_tokens": [
            "true",
            "false",
            "float 1.0",
            "float nan",
            "float inf",
            "float -inf",
            "string token",
            "none",
            "complex 1+0j",
            "int beyond +-15000",
            "speed_code -1 or 21",
        ],
    }


def _regen_fixtures():
    document = _build_fixture_document()
    _VECTORS_PATH.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print("fixtures written:", _VECTORS_PATH)
    print("bytes:", _VECTORS_PATH.stat().st_size)


class KinematicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with _VECTORS_PATH.open(encoding="utf-8") as handle:
            cls.vectors = json.load(handle)

    def test_constructed_or_replaced_primitives_cannot_bypass_wire_validation(self):
        valid = kinematics.validate_primitive("stress_300", 20, 40, 40)
        for changes in (
            {"curvature_yaw_per_m": float("inf")},
            {"curvature_pitch_per_m": float("nan")},
            {"curvature_yaw_per_m": 100.0},
            {"target_speed_m_s": 0.25},
            {"yaw_q": 58},
            {"speed_code": 0},
            {"profile": "unknown"},
        ):
            for speed in (0.0, 0.002):
                with self.subTest(changes=changes, speed=speed):
                    with self.assertRaises(kinematics.PrimitiveRejected):
                        kinematics.angular_rate_rad_s(dataclasses.replace(valid, **changes), speed)
        with self.assertRaises(kinematics.PrimitiveRejected):
            kinematics.angular_rate_rad_s(valid, 10 ** 1000)
        with self.assertRaises(kinematics.PrimitiveRejected):
            kinematics.step_speed_m_s(0.0, 0.002, 10 ** 1000)

    def test_caller_decimal_context_cannot_change_profile_speed(self):
        expected = kinematics.validate_primitive("fast_9600", 19, 6803, 0)
        with localcontext() as context:
            context.prec = 2
            actual = kinematics.validate_primitive("fast_9600", 19, 6803, 0)
            self.assertEqual(actual, expected)
            self.assertEqual(kinematics.target_speed_m_s("fast_9600", 19), 0.2375)
            self.assertEqual(kinematics.angular_rate_rad_s(actual, 0.2375),
                             kinematics.angular_rate_rad_s(expected, 0.2375))

    def test_required_stress_code_20_vectors(self):
        limit = kinematics.curvature_threshold_squared("stress_300", 20)
        self.assertEqual(limit, 3282)
        self.assertLessEqual(57 * 57, limit)
        self.assertGreater(58 * 58, limit)
        self.assertLessEqual(40 * 40 + 40 * 40, limit)
        self.assertGreater(41 * 41 + 41 * 41, limit)
        for yaw_q, pitch_q in ((57, 0), (-57, 0), (40, 40), (40, -40)):
            primitive = kinematics.validate_primitive("stress_300", 20, yaw_q, pitch_q)
            self.assertEqual(primitive.target_speed_m_s, 0.002)
        for yaw_q, pitch_q in ((58, 0), (0, -58), (41, 41), (-41, 41)):
            with self.assertRaises(kinematics.PrimitiveRejected):
                kinematics.validate_primitive("stress_300", 20, yaw_q, pitch_q)

    def test_rom_matches_independent_machin_pi(self):
        pi, expected, margin = _independent_thresholds()
        self.assertEqual(str(pi)[: len(kinematics.PI_DIGITS_60)], kinematics.PI_DIGITS_60)
        for profile in _RAW_STEPS:
            self.assertEqual(
                tuple(expected[profile]),
                tuple(kinematics.CURVATURE_THRESHOLD_SQUARED[profile]),
            )
        self.assertGreater(margin, Decimal("0.01"))
        self.assertEqual(kinematics.curvature_threshold_squared("fast_9600", 0), 0)
        self.assertEqual(kinematics.curvature_threshold_squared("stress_300", 20), 3282)
        self.assertEqual(
            kinematics.curvature_threshold_squared("fast_9600", 20),
            expected["fast_9600"][20],
        )

    def test_every_profile_and_speed_code_boundaries(self):
        for profile, block in self.vectors["profiles"].items():
            self.assertEqual(len(block["codes"]), 21)
            for entry in block["codes"]:
                code = entry["code"]
                self.assertEqual(
                    kinematics.target_speed_m_s(profile, code), entry["target_m_s"]
                )
                self.assertEqual(
                    kinematics.curvature_threshold_squared(profile, code),
                    entry["threshold"],
                )
                legal_axis = entry["axis_legal"]
                reject_axis = entry["axis_reject"]
                legal_diag = entry["diag_legal"]
                reject_diag = entry["diag_reject"]
                for key in ("axis_legal", "axis_reject", "diag_legal", "diag_reject"):
                    for component in entry[key]:
                        self.assertLessEqual(abs(component), 15000)
                self.assertLessEqual(
                    legal_axis[0] ** 2 + legal_axis[1] ** 2, entry["threshold"]
                )
                self.assertGreater(
                    reject_axis[0] ** 2 + reject_axis[1] ** 2, entry["threshold"]
                )
                self.assertLessEqual(
                    legal_diag[0] ** 2 + legal_diag[1] ** 2, entry["threshold"]
                )
                self.assertGreater(
                    reject_diag[0] ** 2 + reject_diag[1] ** 2, entry["threshold"]
                )
                primitive = kinematics.validate_primitive(profile, code, *legal_axis)
                self.assertEqual(primitive.speed_code, code)
                kinematics.validate_primitive(profile, code, *legal_diag)
                with self.assertRaises(kinematics.PrimitiveRejected):
                    kinematics.validate_primitive(profile, code, *reject_axis)
                with self.assertRaises(kinematics.PrimitiveRejected):
                    kinematics.validate_primitive(profile, code, *reject_diag)

    def test_fixture_document_matches_recomputation(self):
        self.assertEqual(self.vectors, _build_fixture_document())

    def test_zero_target_speed_requires_zero_angular_codes(self):
        for profile in ("fast_9600", "stress_300"):
            primitive = kinematics.validate_primitive(profile, 0, 0, 0)
            self.assertEqual(primitive.target_speed_m_s, 0.0)
            self.assertEqual(primitive.curvature_yaw_per_m, 0.0)
            self.assertEqual(primitive.curvature_pitch_per_m, 0.0)
            self.assertEqual(kinematics.angular_rate_rad_s(primitive, 0.0), (0.0, 0.0))
            self.assertEqual(kinematics.angular_rate_rad_s(primitive, 0.25), (0.0, 0.0))
            for yaw_q, pitch_q in ((1, 0), (0, -1), (1, 1), (-1, 0)):
                with self.assertRaises(kinematics.PrimitiveRejected):
                    kinematics.validate_primitive(profile, 0, yaw_q, pitch_q)

    def test_axis_vs_diagonal_bounds(self):
        for profile in ("fast_9600", "stress_300"):
            for code in range(21):
                limit = kinematics.curvature_threshold_squared(profile, code)
                axis = math.isqrt(limit)
                diag = math.isqrt(limit // 2)
                kinematics.validate_primitive(profile, code, axis, 0)
                kinematics.validate_primitive(profile, code, 0, -axis)
                kinematics.validate_primitive(profile, code, diag, -diag)
                with self.assertRaises(kinematics.PrimitiveRejected):
                    kinematics.validate_primitive(profile, code, axis + 1, 0)
                with self.assertRaises(kinematics.PrimitiveRejected):
                    kinematics.validate_primitive(profile, code, 0, -(axis + 1))
                with self.assertRaises(kinematics.PrimitiveRejected):
                    kinematics.validate_primitive(profile, code, diag + 1, -(diag + 1))

    def test_invalid_numeric_types_rejected(self):
        bad_profiles = (1, None, True, "FAST_9600", "fast_9600 ", b"fast_9600")
        bad_codes = (True, 20.0, -1, 21, "5", None, float("nan"), float("inf"))
        bad_q = (
            True,
            False,
            1.0,
            float("nan"),
            float("inf"),
            float("-inf"),
            "0",
            None,
            15001,
            -15001,
            1 + 0j,
        )
        for profile in bad_profiles:
            with self.assertRaises(ValueError):
                kinematics.validate_primitive(profile, 1, 0, 0)
            with self.assertRaises(ValueError):
                kinematics.target_speed_m_s(profile, 1)
            with self.assertRaises(ValueError):
                kinematics.curvature_threshold_squared(profile, 1)
        for code in bad_codes:
            with self.assertRaises(ValueError):
                kinematics.validate_primitive("fast_9600", code, 0, 0)
            with self.assertRaises(ValueError):
                kinematics.target_speed_m_s("fast_9600", code)
        for value in bad_q:
            with self.assertRaises(ValueError):
                kinematics.validate_primitive("fast_9600", 1, value, 0)
            with self.assertRaises(ValueError):
                kinematics.validate_primitive("fast_9600", 1, 0, value)
            with self.assertRaises(ValueError):
                kinematics.reference_angular_rate_deg_s(value)

    def test_reject_not_clip_out_of_range_candidates(self):
        with self.assertRaises(kinematics.PrimitiveRejected):
            kinematics.validate_primitive("fast_9600", 21, 0, 0)
        with self.assertRaises(kinematics.PrimitiveRejected):
            kinematics.validate_primitive("fast_9600", 20, 15001, 0)
        with self.assertRaises(kinematics.PrimitiveRejected):
            kinematics.validate_primitive("stress_300", 20, 58, 0)
        with self.assertRaises(kinematics.PrimitiveRejected):
            kinematics.step_speed_m_s(0.0, 0.26, 0.01)
        with self.assertRaises(kinematics.PrimitiveRejected):
            kinematics.step_speed_m_s(0.2500001, 0.0, 0.01)

    def test_acceleration_and_deceleration_bounds(self):
        speed = 0.0
        steps = 0
        while speed != 0.25 and steps < 200:
            next_speed = kinematics.step_speed_m_s(speed, 0.25, 0.01)
            self.assertGreaterEqual(next_speed, speed)
            self.assertLessEqual(next_speed - speed, 0.0025 + 1e-12)
            speed = next_speed
            steps += 1
        self.assertEqual(speed, 0.25)
        self.assertLessEqual(steps, 101)
        steps = 0
        while speed != 0.0 and steps < 200:
            next_speed = kinematics.step_speed_m_s(speed, 0.0, 0.01)
            self.assertLessEqual(next_speed, speed)
            self.assertLessEqual(speed - next_speed, 0.0025 + 1e-12)
            speed = next_speed
            steps += 1
        self.assertEqual(speed, 0.0)
        self.assertLessEqual(steps, 101)
        self.assertEqual(kinematics.step_speed_m_s(0.0, 0.25, 1.0), 0.25)
        self.assertEqual(kinematics.step_speed_m_s(0.249, 0.25, 0.01), 0.25)
        self.assertAlmostEqual(
            kinematics.step_speed_m_s(0.25, 0.0, 0.001), 0.24975, places=12
        )
        chain = self.vectors["speed_step_chains"]["acceleration"]
        speed = chain["actual_m_s"]
        for _ in range(chain["max_steps"]):
            speed = kinematics.step_speed_m_s(speed, chain["target_m_s"], chain["dt_s"])
        self.assertEqual(speed, chain["expected_final_m_s"])
        chain = self.vectors["speed_step_chains"]["deceleration"]
        speed = chain["actual_m_s"]
        for _ in range(chain["max_steps"]):
            speed = kinematics.step_speed_m_s(speed, chain["target_m_s"], chain["dt_s"])
        self.assertEqual(speed, chain["expected_final_m_s"])

    def test_angular_rates_follow_actual_speed_and_stop_at_zero(self):
        primitive = kinematics.validate_primitive("fast_9600", 20, 1000, -2000)
        self.assertAlmostEqual(primitive.curvature_yaw_per_m, math.pi / 45.0, places=12)
        self.assertAlmostEqual(
            primitive.curvature_pitch_per_m, -2.0 * math.pi / 45.0, places=12
        )
        yaw, pitch = kinematics.angular_rate_rad_s(primitive, 0.25)
        self.assertAlmostEqual(yaw, math.radians(1.0), places=12)
        self.assertAlmostEqual(pitch, math.radians(-2.0), places=12)
        half_yaw, half_pitch = kinematics.angular_rate_rad_s(primitive, 0.125)
        self.assertAlmostEqual(half_yaw, yaw / 2.0, places=12)
        self.assertAlmostEqual(half_pitch, pitch / 2.0, places=12)
        self.assertEqual(kinematics.angular_rate_rad_s(primitive, 0.0), (0.0, 0.0))
        self.assertEqual(kinematics.angular_rate_rad_s(primitive, 0), (0.0, 0.0))
        for actual in (-0.001, float("nan"), float("inf"), True, 0.2500001, "0.1", None):
            with self.assertRaises(ValueError):
                kinematics.angular_rate_rad_s(primitive, actual)

    def test_curvature_samples_match_high_precision(self):
        for sample in self.vectors["curvature_samples"]:
            primitive = kinematics.validate_primitive(
                sample["profile"],
                sample["speed_code"],
                sample["yaw_q"],
                sample["pitch_q"],
            )
            expected_yaw = float(Decimal(sample["curvature_yaw_per_m"]))
            expected_pitch = float(Decimal(sample["curvature_pitch_per_m"]))
            self.assertAlmostEqual(
                primitive.curvature_yaw_per_m,
                expected_yaw,
                delta=abs(expected_yaw) * 1e-12 + 1e-15,
            )
            self.assertAlmostEqual(
                primitive.curvature_pitch_per_m,
                expected_pitch,
                delta=abs(expected_pitch) * 1e-12 + 1e-15,
            )
            rates = kinematics.angular_rate_rad_s(primitive, primitive.target_speed_m_s)
            expected_rate = math.radians(
                0.001 * math.hypot(sample["yaw_q"], sample["pitch_q"])
            )
            self.assertAlmostEqual(
                math.hypot(*rates), expected_rate, delta=expected_rate * 1e-12 + 1e-15
            )
            self.assertAlmostEqual(
                kinematics.reference_angular_rate_deg_s(sample["yaw_q"]),
                sample["reference_rate_yaw_deg_s"],
                places=12,
            )
            self.assertAlmostEqual(
                kinematics.reference_angular_rate_deg_s(sample["pitch_q"]),
                sample["reference_rate_pitch_deg_s"],
                places=12,
            )

    def test_step_speed_rejects_bad_dt_and_bad_scalars(self):
        good = 0.1
        for dt in (0, -0.001, float("nan"), float("inf"), True, False, "0.01", None):
            with self.assertRaises(ValueError):
                kinematics.step_speed_m_s(good, 0.2, dt)
        for value in (-0.001, float("nan"), float("inf"), float("-inf"), True, 0.26, "0.1", None):
            with self.assertRaises(ValueError):
                kinematics.step_speed_m_s(value, 0.2, 0.01)
            with self.assertRaises(ValueError):
                kinematics.step_speed_m_s(good, value, 0.01)

    def test_dependency_free_source_imports(self):
        source = _MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
        self.assertLessEqual(names, {"dataclasses", "decimal", "math", "types"})
        self.assertNotIn("open(", source)
        self.assertNotIn("os.", source)

    def test_frozen_output_and_64bit_envelope(self):
        first = kinematics.validate_primitive("fast_9600", 20, 1000, -2000)
        second = kinematics.validate_primitive("fast_9600", 20, 1000, -2000)
        self.assertEqual(first, second)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.yaw_q = 0
        maxima = [max(row) for row in kinematics.CURVATURE_THRESHOLD_SQUARED.values()]
        self.assertLess(max(maxima), 2 ** 63)
        combined_max = 2 * kinematics.Q_CODE_MAX * kinematics.Q_CODE_MAX
        self.assertLess(combined_max, 2 ** 63)
        self.assertEqual(len(kinematics.CURVATURE_THRESHOLD_SQUARED["fast_9600"]), 21)
        self.assertEqual(len(kinematics.CURVATURE_THRESHOLD_SQUARED["stress_300"]), 21)


if __name__ == "__main__":
    if "--regen-fixtures" in sys.argv[1:]:
        _regen_fixtures()
    else:
        unittest.main(verbosity=2)

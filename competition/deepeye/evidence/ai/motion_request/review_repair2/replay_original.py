"""Replay the preserved RED tests against preserved original source in-process.

Does not overwrite current source or old logs. Exit1 is the expected unsafe
original result; it is not a passing safety assertion.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[3]
sys.path.insert(0, str(PRODUCT))
name = "ai_pc.control_broker.motion_request"
spec = importlib.util.spec_from_file_location(name, HERE / "pre_repair/motion_request.py")
original = importlib.util.module_from_spec(spec)
sys.modules[name] = original
spec.loader.exec_module(original)
spec = importlib.util.spec_from_file_location("repair2_red_tests", HERE / "red_test_motion_request.py")
tests = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tests
spec.loader.exec_module(tests)
suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.VerifierReentrancyTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)

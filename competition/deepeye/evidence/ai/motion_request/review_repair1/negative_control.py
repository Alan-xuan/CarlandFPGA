"""Run new mutation/overflow regressions against the preserved rejected source.

Expected process exit is 1. It changes only this process's imported module table;
it does not modify either source file or imply a current production test failure.
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
rejected = importlib.util.module_from_spec(spec)
sys.modules[name] = rejected
spec.loader.exec_module(rejected)
spec = importlib.util.spec_from_file_location("repair1_new_tests",
    PRODUCT / "tests/ai/control_broker/test_motion_request.py")
tests = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tests
spec.loader.exec_module(tests)
suite = unittest.TestSuite(tests.RuntimeBoundaryTests(name) for name in (
    "test_mutated_context_and_shadowed_validation_cannot_emit_invalid_context",
    "test_observation_class_validation_and_detached_sample_snapshots",
    "test_deadline_signed63_overflow_blocks_without_fabricating_timing"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)

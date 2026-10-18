"""Qualify candidate and historical verifier checks without changing pins."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
TEST = Path("tests/ai/data_model/test_verify_data.py")
PIN_DEPENDENT = (
    "CliOutputProtectionTests.test_output_allows_legitimate_report_path",
    "RealPinnedDataTests.test_force_offline_without_archive_is_blocked_not_usage_error",
    "RealPinnedDataTests.test_real_default_full_scope_is_blocked_exit_2",
    "RealPinnedDataTests.test_real_missing_archive_blocked_and_wrong_archive_failed",
)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def unaffected():
    spec = importlib.util.spec_from_file_location("candidate_verifier_tests", PRODUCT / TEST)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    print("Candidate check; historical-pin expectation failures excluded explicitly:")
    for name in PIN_DEPENDENT:
        print("  " + name)
    suite = unittest.TestSuite(
        test for test in flatten(unittest.defaultTestLoader.loadTestsFromModule(module))
        if test.id().split(".", 1)[1] not in PIN_DEPENDENT
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return int(not result.wasSuccessful())


def historical():
    if os.environ.get("DEEPEYE_FORCE_ARCHIVE"):
        raise RuntimeError("historical compatibility check requires the archive override unset")
    manifest = json.loads((HERE / "original_sha256.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="verify_data_historical_compat_") as directory:
        copied = Path(directory) / "product"
        copied.mkdir()
        for relative in (*manifest["untouched_artifacts"], "data/force_inventory.py",
                         "data/force_preprocess.py", str(TEST)):
            destination = copied / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = HERE / "original" / relative if relative in (
                "data/force_inventory.py", "data/force_preprocess.py"
            ) else PRODUCT / relative
            shutil.copyfile(source, destination)
        for relative, record in manifest["untouched_artifacts"].items():
            assert hashlib.sha256((copied / relative).read_bytes()).hexdigest() == record["sha256"]
        for relative in ("data/force_inventory.py", "data/force_preprocess.py"):
            assert hashlib.sha256((copied / relative).read_bytes()).hexdigest() == manifest[
                "original_sources"
            ][relative]["sha256"]
        print("HISTORICAL source compatibility only: original parser snapshots, unchanged pins/data, repaired verifier test.", flush=True)
        print("This does not establish production verification for repaired parser sources.", flush=True)
        return subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(copied / TEST)], cwd=copied
        ).returncode


if __name__ == "__main__":
    mode = sys.argv[1]
    raise SystemExit({"unaffected": unaffected, "historical": historical}[mode]())

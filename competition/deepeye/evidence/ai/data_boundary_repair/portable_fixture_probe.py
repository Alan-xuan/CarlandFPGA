"""Assert the hardlink test puts its source and alias in one fixture tree.

This deterministic layout probe reproduces the portability defect on C's
single available volume. B's actual WinError 17 is preserved separately in
review6197806056.stdout.txt; this probe does not claim a second physical volume.
"""

import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
PRODUCT = Path(__file__).resolve().parents[3]
test_path = PRODUCT / "tests/ai/data_model/test_verify_data.py"
spec = importlib.util.spec_from_file_location("portable_test_target", test_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
real_link = os.link


def fixture_only_link(source, alias, *args, **kwargs):
    source, alias = Path(source).resolve(), Path(alias).resolve()
    print("hardlink source:", source)
    print("hardlink alias:", alias)
    if not source.is_relative_to(alias.parent):
        raise AssertionError("hardlink source is outside alias's copied temporary product tree")
    return real_link(source, alias, *args, **kwargs)


suite = unittest.TestSuite([
    module.CliOutputProtectionTests("test_output_rejects_hardlink_alias_of_pinned_input")
])
with mock.patch.object(module.os, "link", side_effect=fixture_only_link):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())

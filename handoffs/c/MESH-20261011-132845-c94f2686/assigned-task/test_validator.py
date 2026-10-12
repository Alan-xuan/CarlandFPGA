#!/usr/bin/env python3
"""Unit tests for the bounded offline fixture validator (standard library only).

Coverage: valid fixture accept; task_version missing / negative / zero / bool
/ string / float rejects; task_id missing / empty / non-string; owner and
direction missing and wrong; extra fields allowed; non-object roots;
malformed JSON files; missing files; CLI exit codes (0 accept, 1 reject,
2 usage) and stream contents.
"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import validator  # noqa: E402  (module lives next to this test file)

VALID_FIXTURE = os.path.join(HERE, "fixtures", "valid.json")
MISSING_VERSION_FIXTURE = os.path.join(HERE, "fixtures", "missing-version.json")
NEGATIVE_VERSION_FIXTURE = os.path.join(HERE, "fixtures", "negative-version.json")

VALID_TASK_ID = "MESH-20261011-132845-c94f2686-C-git-handoff"


def base_fixture():
    return {
        "task_id": VALID_TASK_ID,
        "task_version": 1,
        "owner": "C/Astra-C",
        "direction": "A->C",
    }


def write_temp_json(text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8", newline=""
    )
    handle.write(text)
    handle.close()
    return handle.name


class FixtureValidationTests(unittest.TestCase):
    def test_fixture_dict_accepts(self):
        ok, reason = validator.validate_fixture(base_fixture())
        self.assertTrue(ok, reason)

    def test_valid_fixture_file_accepts(self):
        ok, reason = validator.validate_file(VALID_FIXTURE)
        self.assertTrue(ok, reason)

    def test_extra_fields_allowed(self):
        fixture = base_fixture()
        fixture["extra"] = {"anything": [1, 2, 3]}
        fixture["note"] = "extra fields are allowed and ignored"
        ok, reason = validator.validate_fixture(fixture)
        self.assertTrue(ok, reason)

    def test_missing_version_fixture_file_rejects(self):
        ok, reason = validator.validate_file(MISSING_VERSION_FIXTURE)
        self.assertFalse(ok)
        self.assertIn("task_version", reason)

    def test_negative_version_fixture_file_rejects(self):
        ok, reason = validator.validate_file(NEGATIVE_VERSION_FIXTURE)
        self.assertFalse(ok)
        self.assertIn("positive integer", reason)

    def test_missing_version_rejects(self):
        fixture = base_fixture()
        del fixture["task_version"]
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("missing required field 'task_version'", reason)

    def test_negative_version_rejects(self):
        fixture = base_fixture()
        fixture["task_version"] = -1
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("positive integer", reason)

    def test_zero_version_rejects(self):
        fixture = base_fixture()
        fixture["task_version"] = 0
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("positive integer", reason)

    def test_bool_true_version_rejects(self):
        fixture = base_fixture()
        fixture["task_version"] = True
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("bool", reason)

    def test_bool_false_version_rejects(self):
        fixture = base_fixture()
        fixture["task_version"] = False
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("bool", reason)

    def test_string_version_rejects(self):
        fixture = base_fixture()
        fixture["task_version"] = "1"
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("integer", reason)

    def test_float_version_rejects(self):
        fixture = base_fixture()
        fixture["task_version"] = 1.0
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)

    def test_missing_task_id_rejects(self):
        fixture = base_fixture()
        del fixture["task_id"]
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("task_id", reason)

    def test_empty_or_whitespace_task_id_rejects(self):
        for value in ("", "   "):
            fixture = base_fixture()
            fixture["task_id"] = value
            ok, reason = validator.validate_fixture(fixture)
            self.assertFalse(ok, "task_id %r was accepted" % value)
            self.assertIn("nonempty", reason)

    def test_non_string_task_id_rejects(self):
        fixture = base_fixture()
        fixture["task_id"] = 123
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("string", reason)

    def test_missing_owner_rejects(self):
        fixture = base_fixture()
        del fixture["owner"]
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("owner", reason)

    def test_wrong_owner_rejects(self):
        fixture = base_fixture()
        fixture["owner"] = "A/Astra-A"
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("owner", reason)

    def test_missing_direction_rejects(self):
        fixture = base_fixture()
        del fixture["direction"]
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("direction", reason)

    def test_wrong_direction_rejects(self):
        fixture = base_fixture()
        fixture["direction"] = "C->A"
        ok, reason = validator.validate_fixture(fixture)
        self.assertFalse(ok)
        self.assertIn("direction", reason)

    def test_non_object_roots_reject(self):
        for value in ([], ["task_id"], "text", 7, 1.5, None, True):
            ok, reason = validator.validate_fixture(value)
            self.assertFalse(ok, "root %r was accepted" % (value,))
            self.assertIn("JSON object", reason)

    def test_malformed_json_file_rejects(self):
        path = write_temp_json('{"task_id": "x", ')
        try:
            ok, reason = validator.validate_file(path)
        finally:
            os.unlink(path)
        self.assertFalse(ok)
        self.assertIn("malformed JSON", reason)

    def test_non_object_json_file_rejects(self):
        path = write_temp_json("[1, 2, 3]")
        try:
            ok, reason = validator.validate_file(path)
        finally:
            os.unlink(path)
        self.assertFalse(ok)
        self.assertIn("JSON object", reason)

    def test_missing_file_rejects(self):
        ok, reason = validator.validate_file(os.path.join(HERE, "fixtures", "does-not-exist.json"))
        self.assertFalse(ok)
        self.assertIn("file not found", reason)


class ValidatorCliTests(unittest.TestCase):
    def run_cli(self, *args):
        command = [sys.executable, os.path.join(HERE, "validator.py")] + list(args)
        return subprocess.run(
            command,
            cwd=HERE,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_cli_accepts_valid_fixture(self):
        proc = self.run_cli(VALID_FIXTURE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ACCEPT", proc.stdout)

    def test_cli_rejects_missing_version_with_reason(self):
        proc = self.run_cli(MISSING_VERSION_FIXTURE)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("REJECT", proc.stderr)
        self.assertIn("task_version", proc.stderr)

    def test_cli_rejects_negative_version_with_reason(self):
        proc = self.run_cli(NEGATIVE_VERSION_FIXTURE)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("REJECT", proc.stderr)
        self.assertIn("positive integer", proc.stderr)

    def test_cli_rejects_malformed_json(self):
        path = write_temp_json('{"task_id": ')
        try:
            proc = self.run_cli(path)
        finally:
            os.unlink(path)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("malformed JSON", proc.stderr)

    def test_cli_usage_error_exits_2(self):
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage", proc.stderr)


if __name__ == "__main__":
    unittest.main()

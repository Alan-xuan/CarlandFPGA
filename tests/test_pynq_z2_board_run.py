"""Board transport regressions found during the first live PYNQ-Z2 run."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills/pynq-z2-single-node/scripts/board_run.py"


def board_run():
    spec = importlib.util.spec_from_file_location("pynq_board_run", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BoardRunTests(unittest.TestCase):
    def test_serial_reply_ignores_echoed_end_marker(self):
        transport = board_run()
        raw = (
            b"printf '__CFL_BEGIN_abc__'; ip -6 addr; printf '__CFL_END_abc__:0'\r\r\n"
            b"\x1b[?2004l\r__CFL_BEGIN_abc__\r\r\n"
            b"eth0 inet6 fe80::200:5ff:fe6b:1f5/64 scope link\r\r\n"
            b"__CFL_END_abc__:0\r\r\n"
        )
        status, output = transport.parse_serial_result(raw, "abc")
        self.assertEqual(status, 0)
        self.assertEqual(output, "eth0 inet6 fe80::200:5ff:fe6b:1f5/64 scope link")

    def test_serial_reply_requires_executed_end_marker(self):
        transport = board_run()
        raw = (
            b"printf '__CFL_BEGIN_abc__'; printf '__CFL_END_abc__:0'\r\r\n"
            b"__CFL_BEGIN_abc__\r\r\npartial output\r\r\n"
        )
        with self.assertRaisesRegex(ValueError, "end marker"):
            transport.parse_serial_result(raw, "abc")

    def test_link_local_address_comes_from_board_eth0_output(self):
        transport = board_run()
        result = transport.parse_link_local(
            "3: eth0 inet6 192.0.2.1/64 scope global\n"
            "3: eth0 inet6 fe80::200:5ff:fe6b:1f5/64 scope link\n"
        )
        self.assertEqual(result, "fe80::200:5ff:fe6b:1f5")

    def test_upload_hash_mismatch_blocks_execution(self):
        transport = board_run()
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            transport.verify_remote_hash(b"expected\n", "0" * 64 + "  /tmp/probe.py")

    def test_explicit_interpreter_must_import_pynq(self):
        transport = board_run()
        with mock.patch.object(transport, "_ssh", side_effect=RuntimeError("import failed")):
            with self.assertRaisesRegex(RuntimeError, "PYNQ interpreter"):
                transport._board_python(["ssh"], "/usr/bin/python3")

    def test_execution_timeout_keeps_partial_output_and_unknown_state(self):
        transport = board_run()
        timeout = subprocess.TimeoutExpired(
            cmd=["ssh"], timeout=1, output=b"partial result\n", stderr=b"still running\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(transport.subprocess, "run", side_effect=timeout), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "state unknown"):
                    transport.execute_and_record(
                        ["ssh"], "python3 /tmp/probe.py", 1, Path(temp),
                        {"script_sha256": "a" * 64},
                    )
            evidence = next(Path(temp).iterdir())
            record = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(record["timed_out"])
            self.assertIsNone(record["exit_code"])
            self.assertEqual((evidence / "stdout.log").read_bytes(), b"partial result\n")
            self.assertEqual((evidence / "stderr.log").read_bytes(), b"still running\n")


if __name__ == "__main__":
    unittest.main()

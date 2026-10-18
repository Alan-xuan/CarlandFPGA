"""Unit tests for data/force_inventory.py using synthetic mini ZIPs in TemporaryDirectory.

Software-only evidence for the streaming FORCE LAS inventory: bounded-memory
line splitting across chunk boundaries, CRLF/CRCRLF/lone-CR handling, exact
column counts, finite numeric parsing, NULL-sentinel versus valid negative
values, member hashing, archive hash precheck, unsafe paths, unsupported WRAP,
duplicate UWI refusal and the CLI contract. These tests are not a data source,
not a model evaluation and not product-card acceptance.
"""

import ast
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

_HERE = Path(__file__).resolve().parent
_MODULE_PATH = _HERE.parents[2] / "data" / "force_inventory.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("deepeye_force_inventory", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


force_inventory = _load_module()

BASE_HEADER = [
    "# synthetic LAS for unit tests",
    "#==================================================================",
    "~Version information",
    "VERS.   2.0:",
    "WRAP.   NO:",
    "#==================================================================",
    "~Well",
    "STRT .m      0.0 :",
    "STOP .m      2.0 :",
    "STEP .m      1.0 :",
    "NULL .        -999.25 :",
    "WELL.  TEST-1 : WELL",
    "UWI.   TEST-1 : UNIQUE WELL ID",
    "#==================================================================",
    "~Curve",
    "DEPT .m : DEPTH",
    "FORCE_2020_LITHOFACIES_CONFIDENCE ._ : FORCE_2020_LITHOFACIES_CONFIDENCE",
    "FORCE_2020_LITHOFACIES_LITHOLOGY ._ : FORCE_2020_LITHOFACIES_LITHOLOGY",
    "GR .gAPI : GAMMA RAY",
    "~Parameter",
    "MUD . 1.2 : MUD WEIGHT",
    "~Ascii",
]
BASE_ROWS = [
    "0.0 2 30000 -999.25",
    "1.0 1 65030 55.5",
    "2.0 -999.25 -999.25 -0.5",
]


def _las_bytes(rows=None, header=None, terminator="\r\n"):
    lines = list(BASE_HEADER if header is None else header)
    if rows is None:
        rows = BASE_ROWS
    return (terminator.join(lines + list(rows)) + terminator).encode("ascii")


def _header_with(**replacements):
    header = list(BASE_HEADER)
    for old, new in replacements.items():
        header = [line.replace(old, new) for line in header]
    return header


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    return path


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _md5_file(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _inventory(path, **kwargs):
    return force_inventory.inventory_archive(
        str(path), os.path.getsize(path), _sha256_file(path), **kwargs
    )


class ForceInventoryTests(unittest.TestCase):
    def test_conflicting_critical_headers_are_rejected(self):
        replacements = {
            "VERS": ("2.0", "1.2"),
            "WRAP": ("NO", "YES"),
            "UWI": ("TEST-1", "9/9-9"),
            "NULL": ("-999.25", "-123"),
        }
        for key, (original, conflicting) in replacements.items():
            for reverse in (False, True):
                header = list(BASE_HEADER)
                index = next(i for i, line in enumerate(header)
                             if line.partition(".")[0].strip().upper() == key)
                first, second = ((conflicting, original) if reverse
                                 else (original, conflicting))
                header[index:index + 1] = [
                    "%s. %s:" % (key, first),
                    "%s. %s:" % (key.lower(), second),
                ]
                raw = _las_bytes(header=header)
                with self.subTest(key=key, reverse=reverse):
                    with self.assertRaises(force_inventory.LasInventoryError) as caught:
                        force_inventory.inventory_las_member(
                            io.BytesIO(raw), "conflict.las", len(raw), chunk_bytes=7
                        )
                    self.assertIn("conflicting duplicate " + key, str(caught.exception))
                    self.assertEqual(caught.exception.member, "conflict.las")
                    self.assertEqual(caught.exception.line, index + 2)

    def test_critical_headers_after_ascii_marker_are_rejected(self):
        values = {"VERS": ("2.0", "1.2"), "WRAP": ("NO", "YES"),
                  "UWI": ("TEST-1", "9/9-9"), "NULL": ("-999.25", "-123")}
        for key, alternatives in values.items():
            section = "~Version" if key in ("VERS", "WRAP") else "~Well"
            for value in alternatives:
                for after_rows in (False, True):
                    for marker in ("~A", "~Ascii"):
                        for terminator in ("\n", "\r\n"):
                            header = list(BASE_HEADER[:-1]) + [marker]
                            lines = header + (BASE_ROWS if after_rows else [])
                            lines += [section, "%s. %s:" % (key.lower(), value)]
                            offending_line = len(lines)
                            lines += [marker] + ([] if after_rows else BASE_ROWS)
                            raw = (terminator.join(lines) + terminator).encode("ascii")
                            with self.subTest(key=key, value=value, after_rows=after_rows,
                                              marker=marker, terminator=repr(terminator)):
                                with self.assertRaises(force_inventory.LasInventoryError) as caught:
                                    force_inventory.inventory_las_member(
                                        io.BytesIO(raw), "late.las", len(raw), chunk_bytes=1
                                    )
                                self.assertIn(key + " header after ASCII data section",
                                              str(caught.exception))
                                self.assertEqual(caught.exception.member, "late.las")
                                self.assertEqual(caught.exception.line, offending_line)

    def test_identical_critical_headers_before_ascii_are_allowed(self):
        header = []
        for line in BASE_HEADER:
            header.append(line)
            if line.partition(".")[0].strip().upper() in ("VERS", "WRAP", "UWI", "NULL"):
                header.append(line)
        raw = _las_bytes(header=header)
        record = force_inventory.inventory_las_member(
            io.BytesIO(raw), "identical.las", len(raw), chunk_bytes=7
        )
        self.assertEqual(record["uwi"], "TEST-1")
        self.assertEqual(record["null_value"], -999.25)
        self.assertEqual(record["rows"], len(BASE_ROWS))
        self.assertEqual(record["curves"][3]["null_count"], 1)

    def test_nonfinite_null_sentinel_is_rejected(self):
        for value in ("nan", "inf", "-inf", "1e999"):
            raw = _las_bytes(header=_header_with(**{"-999.25": value}))
            with self.subTest(value=value):
                with self.assertRaises(force_inventory.LasInventoryError):
                    force_inventory.inventory_las_member(io.BytesIO(raw), "fixture.las", len(raw))

    def test_plain_stream_cannot_claim_zip_crc(self):
        raw = _las_bytes()
        result = force_inventory.inventory_las_member(io.BytesIO(raw), "fixture.las", len(raw))
        self.assertIsNone(result["crc_verified"])
        with self.assertRaises(force_inventory.LasInventoryError):
            force_inventory.inventory_las_member(io.BytesIO(raw), "fixture.las", len(raw) + 1)

    def test_ambiguous_curve_names_are_rejected(self):
        raw = _las_bytes(header=_header_with(**{"GR .gAPI": "DEPT .gAPI"}))
        with self.assertRaises(force_inventory.LasInventoryError):
            force_inventory.inventory_las_member(io.BytesIO(raw), "fixture.las", len(raw))

    def test_invalid_chunk_sizes_are_rejected(self):
        for value in (0, -1, True, 1.0):
            with self.assertRaises(force_inventory.LasInventoryError):
                list(force_inventory.iter_las_lines(io.BytesIO(b"a\n"), value))

    def test_empty_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_zip(os.path.join(tmp, "empty.zip"), [])
            with self.assertRaises(force_inventory.LasInventoryError):
                _inventory(path)

    def test_parse_section_line_real_formats(self):
        cases = [
            ("UWI.   15/9-13   : UNIQUE WELL ID", ("UWI", "", "15/9-13", "UNIQUE WELL ID")),
            ("STRT .m      25.000000000 :", ("STRT", "m", "25.000000000", "")),
            ("DEPT .m                   : DEPTH", ("DEPT", "m", "", "DEPTH")),
            (
                "FORCE_2020_LITHOFACIES_CONFIDENCE ._ : FORCE_2020_LITHOFACIES_CONFIDENCE",
                ("FORCE_2020_LITHOFACIES_CONFIDENCE", "_", "", "FORCE_2020_LITHOFACIES_CONFIDENCE"),
            ),
            ("VERS.   2.0:", ("VERS", "", "2.0", "")),
            ("WRAP.   NO:", ("WRAP", "", "NO", "")),
        ]
        for line, expected in cases:
            self.assertEqual(force_inventory.parse_section_line(line), expected)

    def test_iter_las_lines_terminator_and_boundary_handling(self):
        data = b"a\r\nb\rc\nd\r\r\ne"
        expected = [b"a", b"b", b"c", b"d", b"", b"e"]
        self.assertEqual(list(force_inventory.iter_las_lines(io.BytesIO(data), 1 << 20)), expected)
        for chunk in (1, 2, 3, 5, 7):
            self.assertEqual(list(force_inventory.iter_las_lines(io.BytesIO(data), chunk)), expected)
        blob = b"\r\r\nx"
        self.assertEqual(list(force_inventory.iter_las_lines(io.BytesIO(blob), 1)), [b"", b"", b"x"])

    def test_good_well_inventory_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = _write_zip(
                os.path.join(tmp, "good.zip"),
                [("dir/TEST-1.las", _las_bytes())],
            )
            document = _inventory(archive)
        record = document["wells"][0]
        self.assertEqual(record["uwi"], "TEST-1")
        self.assertEqual(record["well"], "TEST-1")
        self.assertEqual(record["rows"], 3)
        self.assertEqual(record["vers"], "2.0")
        self.assertEqual(record["wrap"], "NO")
        self.assertEqual(record["null_value"], -999.25)
        self.assertTrue(record["crc_verified"])
        self.assertEqual(record["blank_lines"], 0)
        self.assertEqual(record["comment_lines"], 4)
        self.assertEqual(
            record["depth"],
            {
                "mnemonic": "DEPT",
                "unit": "m",
                "count": 3,
                "null_count": 0,
                "min": 0.0,
                "max": 2.0,
                "increasing_steps": 2,
                "duplicate_steps": 0,
                "decreasing_steps": 0,
                "step_min": 1.0,
                "step_max": 1.0,
                "monotonic_nondecreasing": True,
            },
        )
        self.assertEqual(record["curves"][3]["mnemonic"], "GR")
        self.assertEqual(record["curves"][3]["count"], 3)
        self.assertEqual(record["curves"][3]["null_count"], 1)
        self.assertEqual(record["curves"][3]["nonmissing_count"], 2)
        self.assertEqual(
            record["lithology_code_histogram"]["values"],
            {"30000": 1, "65030": 1, "-999.25": 1},
        )
        self.assertEqual(
            record["lithology_confidence_histogram"]["values"],
            {"2": 1, "1": 1, "-999.25": 1},
        )
        self.assertTrue(record["lithology_code_histogram"]["present"])
        self.assertEqual(document["summary"]["members"], 1)
        self.assertEqual(document["summary"]["rows_total"], 3)
        self.assertEqual(document["summary"]["duplicate_uwi"], 0)

    def test_member_sha_and_size_match_raw_member(self):
        raw = _las_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            archive = _write_zip(os.path.join(tmp, "sha.zip"), [("dir/one.las", raw)])
            document = _inventory(archive)
        record = document["wells"][0]
        self.assertEqual(record["member"], "dir/one.las")
        self.assertEqual(record["member_size_bytes"], len(raw))
        self.assertEqual(record["member_sha256"], hashlib.sha256(raw).hexdigest())

    def test_crcrlf_and_cr_only_terminators(self):
        plain = force_inventory.inventory_las_member(
            io.BytesIO(_las_bytes()), "x/y.las", len(_las_bytes())
        )
        crcrlf_bytes = _las_bytes(terminator="\r\r\n")
        crcrlf = force_inventory.inventory_las_member(
            io.BytesIO(crcrlf_bytes), "x/y.las", len(crcrlf_bytes)
        )
        cr_bytes = _las_bytes(terminator="\r")
        cr_only = force_inventory.inventory_las_member(
            io.BytesIO(cr_bytes), "x/y.las", len(cr_bytes)
        )
        self.assertEqual(crcrlf["rows"], plain["rows"])
        self.assertEqual(crcrlf["depth"], plain["depth"])
        self.assertGreater(crcrlf["blank_lines"], 0)
        self.assertEqual(cr_only["rows"], plain["rows"])
        self.assertEqual(cr_only["depth"], plain["depth"])
        self.assertEqual(cr_only["blank_lines"], 0)
        tiny = force_inventory.inventory_las_member(
            io.BytesIO(crcrlf_bytes), "x/y.las", len(crcrlf_bytes), 3
        )
        self.assertEqual(tiny["rows"], plain["rows"])
        self.assertEqual(tiny["depth"], plain["depth"])
        self.assertEqual(tiny["member_sha256"], crcrlf["member_sha256"])

    def test_malformed_numeric_fails_with_member_and_line(self):
        rows = list(BASE_ROWS[:1]) + ["1.0 1 BAD 55.5"]
        data = _las_bytes(rows=rows)
        expected_line = len(BASE_HEADER) + 2
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(data), "dir/bad.las", len(data))
        error = caught.exception
        self.assertEqual(error.member, "dir/bad.las")
        self.assertEqual(error.line, expected_line)
        self.assertIn("non-numeric", str(error))
        self.assertIn("line=" + str(expected_line), str(error))

    def test_row_column_count_mismatch_fails(self):
        rows = list(BASE_ROWS[:1]) + ["1.0 1 65030"]
        data = _las_bytes(rows=rows)
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(data), "dir/bad.las", len(data))
        self.assertEqual(caught.exception.line, len(BASE_HEADER) + 2)
        self.assertIn("row has 3 values for 4 curves", str(caught.exception))

    def test_non_ascii_byte_fails(self):
        data = _las_bytes().replace(b"55.5", b"5\xc3\xa95")
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(data), "dir/bad.las", len(data))
        self.assertIn("non-ASCII", str(caught.exception))
        self.assertEqual(caught.exception.member, "dir/bad.las")

    def test_unsafe_member_paths_refused(self):
        bad_names = ("../evil.las", "/abs.las", "C:/x.las", "dir//empty.las", "note.txt", "dir/")
        for name in bad_names:
            with tempfile.TemporaryDirectory() as tmp:
                archive = _write_zip(os.path.join(tmp, "p.zip"), [(name, _las_bytes())])
                with self.assertRaises(force_inventory.LasInventoryError) as caught:
                    _inventory(archive)
                message = str(caught.exception)
                self.assertTrue("unsafe" in message or "unsupported" in message, message)
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory._check_member_path("a\\b.las")
        self.assertIn("unsafe", str(caught.exception))

    def test_wrap_yes_and_version_refusals(self):
        wrap_yes = _las_bytes(header=_header_with(**{"WRAP.   NO:": "WRAP.   YES:"}))
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(wrap_yes), "dir/w.las", len(wrap_yes))
        self.assertIn("WRAP", str(caught.exception))
        header = [line for line in BASE_HEADER if not line.startswith("WRAP.")]
        no_wrap = _las_bytes(header=header)
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(no_wrap), "dir/w.las", len(no_wrap))
        self.assertIn("WRAP", str(caught.exception))
        vers3 = _las_bytes(header=_header_with(**{"VERS.   2.0:": "VERS.   3.0:"}))
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(vers3), "dir/w.las", len(vers3))
        self.assertIn("version", str(caught.exception))

    def test_missing_null_or_uwi_refused(self):
        header = [line for line in BASE_HEADER if not line.startswith("NULL")]
        no_null = _las_bytes(header=header)
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(no_null), "dir/w.las", len(no_null))
        self.assertIn("NULL", str(caught.exception))
        header = [
            line for line in BASE_HEADER if not line.startswith("UWI")
        ]
        no_uwi = _las_bytes(header=header)
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(no_uwi), "dir/w.las", len(no_uwi))
        self.assertIn("UWI", str(caught.exception))

    def test_zero_data_rows_refused(self):
        data = _las_bytes(rows=[])
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(data), "dir/w.las", len(data))
        self.assertIn("no ASCII data rows", str(caught.exception))

    def test_curve_section_after_data_refused(self):
        lines = list(BASE_HEADER) + list(BASE_ROWS) + ["~Curve", "EXTRA .m : EXTRA"]
        data = ("\r\n".join(lines) + "\r\n").encode("ascii")
        with self.assertRaises(force_inventory.LasInventoryError) as caught:
            force_inventory.inventory_las_member(io.BytesIO(data), "dir/w.las", len(data))
        self.assertIn("curve definition after ASCII data rows", str(caught.exception))

    def test_null_sentinel_versus_valid_negative(self):
        rows = [
            "0.0 1 30000 -999.25",
            "1.0 -999.250000 65030 -0.5",
            "2.0 3 99000 -12.75",
        ]
        data = _las_bytes(rows=rows)
        record = force_inventory.inventory_las_member(io.BytesIO(data), "dir/n.las", len(data))
        self.assertEqual(record["curves"][1]["null_count"], 1)
        self.assertEqual(record["curves"][1]["nonmissing_count"], 2)
        self.assertEqual(record["curves"][3]["null_count"], 1)
        self.assertEqual(record["curves"][3]["nonmissing_count"], 2)
        self.assertEqual(
            record["lithology_code_histogram"]["values"],
            {"30000": 1, "65030": 1, "99000": 1},
        )
        self.assertEqual(
            record["lithology_confidence_histogram"]["values"],
            {"1": 1, "-999.25": 1, "3": 1},
        )

    def test_duplicate_uwi_refused_and_distinct_pass(self):
        first = _las_bytes(header=_header_with(**{"TEST-1": "DUP"}))
        second = _las_bytes(header=_header_with(**{"TEST-1": "TEST-2"}))
        duplicate = _las_bytes(header=_header_with(**{"TEST-1": "DUP"}))
        with tempfile.TemporaryDirectory() as tmp:
            archive = _write_zip(
                os.path.join(tmp, "dup.zip"),
                [("dir/a.las", first), ("dir/b.las", duplicate)],
            )
            with self.assertRaises(force_inventory.LasInventoryError) as caught:
                _inventory(archive)
            message = str(caught.exception)
            self.assertIn("duplicate UWI", message)
            self.assertIn("dir/a.las", message)
            self.assertIn("dir/b.las", message)
            archive = _write_zip(
                os.path.join(tmp, "ok.zip"),
                [("dir/a.las", first), ("dir/b.las", second)],
            )
            document = _inventory(archive)
        self.assertEqual(document["summary"]["members"], 2)

    def test_archive_hash_precheck(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = _write_zip(os.path.join(tmp, "h.zip"), [("dir/a.las", _las_bytes())])
            size = os.path.getsize(archive)
            digest = _sha256_file(archive)
            with self.assertRaises(force_inventory.LasInventoryError) as caught:
                force_inventory.inventory_archive(str(archive), size, "0" * 64)
            self.assertIn("sha256", str(caught.exception))
            with self.assertRaises(force_inventory.LasInventoryError) as caught:
                force_inventory.inventory_archive(str(archive), size + 1, digest)
            self.assertIn("size", str(caught.exception))
            with self.assertRaises(force_inventory.LasInventoryError) as caught:
                force_inventory.inventory_archive(str(archive), size, digest, "0" * 32)
            self.assertIn("md5", str(caught.exception))
            document = force_inventory.inventory_archive(
                str(archive), size, digest, _md5_file(archive)
            )
        self.assertEqual(document["summary"]["members"], 1)
        self.assertEqual(document["provenance"]["archive_sha256"], digest)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = _write_zip(
                os.path.join(tmp, "cli.zip"),
                [
                    ("dir/a.las", _las_bytes()),
                    ("dir/b.las", _las_bytes(header=_header_with(**{"TEST-1": "TEST-2"}))),
                ],
            )
            out = os.path.join(tmp, "out.json")
            command = [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                str(_MODULE_PATH),
                "--zip",
                str(archive),
                "--sha256",
                _sha256_file(archive),
                "--bytes",
                str(os.path.getsize(archive)),
                "--out",
                out,
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(document["summary"]["members"], 2)
            self.assertEqual(document["provenance"]["doi"], "10.5281/zenodo.4351156")
            self.assertEqual(
                document["provenance"]["archive_sha256"], _sha256_file(archive)
            )
            out_bad = os.path.join(tmp, "bad.json")
            command_bad = list(command)
            command_bad[command_bad.index("--sha256") + 1] = "0" * 64
            command_bad[command_bad.index("--out") + 1] = out_bad
            result_bad = subprocess.run(command_bad, capture_output=True, text=True)
            self.assertNotEqual(result_bad.returncode, 0)
            self.assertIn("sha256", result_bad.stderr)
            self.assertFalse(os.path.exists(out_bad))

    def test_dependency_free_imports(self):
        source = _MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
        self.assertLessEqual(
            names, {"argparse", "datetime", "hashlib", "json", "math", "os", "sys", "zipfile"}
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

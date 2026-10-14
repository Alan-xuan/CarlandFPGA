"""Portable unit tests for scan_train_curves.py (synthetic fixtures only).

These tests never touch the real FORCE archive, the frozen splits, any
private controller state, credentials or the network.  Every fixture is a
small in-memory LAS member plus a temporary synthetic product tree that
reuses the accepted product modules read-only (data/force_inventory.py,
data/grouping.py, ai_pc/model/curve_input.py).

The accepted product tree is found through DEEPEYE_PRODUCT_DIR or the default
repository-relative path; helper source exists only in scan_train_curves.py
and this file.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_train_curves as scan  # noqa: E402

PRODUCT_SRC = Path(
    os.environ.get("DEEPEYE_PRODUCT_DIR")
    or (
        Path(__file__).resolve().parents[4]
        / ".local"
        / "deepeye-implementation-c"
        / "competition"
        / "deepeye"
    )
)
if not (PRODUCT_SRC / "ai_pc" / "model" / "curve_input.py").is_file():
    raise AssertionError(
        "accepted product tree not found at %s (set DEEPEYE_PRODUCT_DIR)" % PRODUCT_SRC
    )

CURVES_FULL = [("DEPT", "m"), ("GR", "gAPI"), ("RHOB", "g/cm3"), ("NPHI", "m3/m3"), ("RDEP", "ohm.m")]
CURVES_OPAQUE = CURVES_FULL + [("LABEL", ""), ("CONF", "")]
UNITS = {"GR": "gAPI", "RHOB": "g/cm3", "NPHI": "m3/m3", "RDEP": "ohm.m"}
TRANSFORMS = {
    "GR": "identity-v1",
    "RHOB": "identity-v1",
    "NPHI": "identity-v1",
    "RDEP": "log10-positive-v1",
}
# power-of-two scales keep variance/std/sqrt consistency exact in the
# accepted curve_input document validation.
STANDARD_STATS = {
    "GR": (60.0, 4.0),
    "RHOB": (2.5, 0.5),
    "NPHI": (0.25, 0.0625),
    "RDEP": (0.5, 0.25),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def las_bytes(curves, rows, vers="2.0", wrap="NO", null="-999.25", uwi="U-1", well="W-1", eol="\n"):
    lines = [
        "~Version information",
        "VERS. %s : version" % vers,
        "WRAP. %s : wrap" % wrap,
        "~Well information",
        "UWI . %s : uwi" % uwi,
        "WELL. %s : well" % well,
    ]
    if null is not None:
        lines.append("NULL. %s : null" % null)
    lines.append("~Curve information")
    for mnemonic, unit in curves:
        lines.append("%s.%s : %s curve" % (mnemonic, unit, mnemonic))
    lines.append("~ASCII")
    for tokens in rows:
        lines.append("   ".join(tokens))
    return (eol.join(lines) + eol).encode("ascii")


def full_row(index, gr="60", rhob="2.5", nphi="0.25", rdep="10.0", depth=None):
    return [str(index if depth is None else depth), gr, rhob, nphi, rdep]


def build_zip(path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


def write_product(root, splits_doc, wells_doc, preproc_doc):
    root = Path(root)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "ai_pc" / "model").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PRODUCT_SRC / "data" / "force_inventory.py", root / "data" / "force_inventory.py")
    shutil.copyfile(PRODUCT_SRC / "data" / "grouping.py", root / "data" / "grouping.py")
    shutil.copyfile(PRODUCT_SRC / "ai_pc" / "model" / "curve_input.py", root / "ai_pc" / "model" / "curve_input.py")
    for name, doc in (
        ("splits.json", splits_doc),
        ("force_wells.json", wells_doc),
        ("preprocessing.json", preproc_doc),
    ):
        (root / "data" / name).write_bytes(json.dumps(doc, indent=1).encode("utf-8"))


def channel_entry(name, mean, scale, counts, valid_samples=None):
    valid = counts["valid"] if valid_samples is None else valid_samples
    return {
        "name": name,
        "unit": UNITS[name],
        "transform_version": TRANSFORMS[name],
        "counts": dict(counts),
        "valid_samples": valid,
        "mean": mean,
        "variance": scale * scale,
        "std": scale,
        "zero_variance": False,
        "effective_scale": scale,
    }


def preprocessing_doc(channels, fitting_wells=None, grouping_validation=None):
    return {
        "kind": "deepeye-force-preprocess",
        "schema": 1,
        "contract": {
            "id": "DEEPEYE-HUMAN-LOCK-20261014",
            "revision": 1,
            "source_commit": scan.CONTRACT_SOURCE,
            "requirements_sha256": scan.REQUIREMENTS_SHA,
            "design_commit": scan.DESIGN_COMMIT,
        },
        "software_only": True,
        "product_card_c01": "not_run",
        "algorithm": {"name": "c01-preprocess-welford-v1", "channel_order": list(scan.CHANNELS)},
        "channels": channels,
        "fitting_wells": fitting_wells or [],
        "grouping_validation": grouping_validation,
    }


def wells_document(records):
    return {"wells": records}


def well_record(member, data, rows, uwi, curves_stats):
    return {
        "member": member,
        "member_size_bytes": len(data),
        "member_sha256": sha(data),
        "rows": rows,
        "crc_verified": True,
        "uwi": uwi,
        "well": uwi,
        "curves": curves_stats,
    }


def curve_stats(rows, null_by_channel=None):
    null_by_channel = null_by_channel or {}
    stats = [{"mnemonic": "DEPT", "unit": "m", "count": rows, "null_count": 0, "nonmissing_count": rows}]
    for name in scan.CHANNELS:
        nulls = null_by_channel.get(name, 0)
        stats.append(
            {
                "mnemonic": name,
                "unit": UNITS[name],
                "count": rows,
                "null_count": nulls,
                "nonmissing_count": rows - nulls,
            }
        )
    return stats


def split_row(row_id, member, data, split, root_id=None):
    return {
        "row_id": row_id,
        "source_domain": "synthetic_fixture",
        "root_id": root_id or row_id,
        "well_id": row_id,
        "member": member,
        "member_sha256": sha(data),
        "split": split,
        "derived_from": None,
    }


def expectations_for(zip_path, prod, train_wells, train_parents, train_rows):
    return scan.Expectations(
        label="synthetic_fixture",
        archive_sha256=sha(Path(zip_path).read_bytes()),
        archive_bytes=os.path.getsize(zip_path),
        splits_sha256=sha((Path(prod) / "data" / "splits.json").read_bytes()),
        wells_sha256=sha((Path(prod) / "data" / "force_wells.json").read_bytes()),
        preprocessing_sha256=sha((Path(prod) / "data" / "preprocessing.json").read_bytes()),
        train_wells=train_wells,
        train_parents=train_parents,
        train_rows=train_rows,
        source_domain="synthetic_fixture",
    )


class BaseCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="train_curve_scan_test_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def make_world(self, members, splits_doc, wells_doc, preproc_doc, train_wells, train_parents, train_rows):
        self._world_count = getattr(self, "_world_count", 0) + 1
        base = self.root / ("world_%d" % self._world_count)
        base.mkdir(parents=True, exist_ok=True)
        zip_path = base / "fixture.zip"
        build_zip(zip_path, members)
        prod = base / "product"
        write_product(prod, splits_doc, wells_doc, preproc_doc)
        exp = expectations_for(zip_path, prod, train_wells, train_parents, train_rows)
        return zip_path, prod, exp

    def run_world(self, world, **kwargs):
        zip_path, prod, exp = world
        return scan.run_audit(str(zip_path), str(prod), expectations=exp, **kwargs)

    @staticmethod
    def well(payload, member):
        for record in payload["wells"]:
            if record["member"] == member:
                return record
        raise AssertionError("member %r missing from payload" % member)


def standard_world(case):
    """3 train members (A: max run 127; B: 128-run starting at 5; C: run at 0)
    plus one validation member V that must never be opened."""
    rows_a = [full_row(i, gr=("-999.25" if i == 127 else "60")) for i in range(130)]
    rows_b = [full_row(i, gr=("-999.25" if (i < 5 or i >= 133) else "60")) for i in range(140)]
    rows_c = [full_row(i) for i in range(130)]
    rows_v = [full_row(i) for i in range(20)]
    members = {
        "Train/A.las": las_bytes(CURVES_FULL, rows_a, uwi="A-1"),
        "Train/B.las": las_bytes(CURVES_FULL, rows_b, uwi="B-1"),
        "Train/C.las": las_bytes(CURVES_FULL, rows_c, uwi="C-1"),
        "Train/V.las": las_bytes(CURVES_FULL, rows_v, uwi="V-1"),
    }
    wells = [
        well_record("Train/A.las", members["Train/A.las"], 130, "A-1", curve_stats(130, {"GR": 1})),
        well_record("Train/B.las", members["Train/B.las"], 140, "B-1", curve_stats(140, {"GR": 12})),
        well_record("Train/C.las", members["Train/C.las"], 130, "C-1", curve_stats(130)),
        well_record("Train/V.las", members["Train/V.las"], 20, "V-1", curve_stats(20)),
    ]
    splits = {
        "rows": [
            split_row("A-1", "Train/A.las", members["Train/A.las"], "train"),
            split_row("B-1", "Train/B.las", members["Train/B.las"], "train"),
            split_row("C-1", "Train/C.las", members["Train/C.las"], "train"),
            split_row("V-1", "Train/V.las", members["Train/V.las"], "validation"),
        ],
        "well_counts": {"train": 3, "validation": 1},
        "group_counts": {"train": 3, "validation": 1},
    }
    pre = preprocessing_doc(
        channels=[
            channel_entry("GR", 60.0, 4.0, {"valid": 387, "null": 13, "nonpositive": 0, "absent": 0}),
            channel_entry("RHOB", 2.5, 0.5, {"valid": 400, "null": 0, "nonpositive": 0, "absent": 0}),
            channel_entry("NPHI", 0.25, 0.0625, {"valid": 400, "null": 0, "nonpositive": 0, "absent": 0}),
            channel_entry("RDEP", 0.5, 0.25, {"valid": 400, "null": 0, "nonpositive": 0, "absent": 0}),
        ],
        fitting_wells=[
            {"member": "Train/A.las", "member_sha256": sha(members["Train/A.las"]), "uwi": "A-1", "well": "A-1", "rows": 130, "crc_verified": True},
            {"member": "Train/B.las", "member_sha256": sha(members["Train/B.las"]), "uwi": "B-1", "well": "B-1", "rows": 140, "crc_verified": True},
            {"member": "Train/C.las", "member_sha256": sha(members["Train/C.las"]), "uwi": "C-1", "well": "C-1", "rows": 130, "crc_verified": True},
        ],
        grouping_validation={"rows": 4, "root_count": 4, "split_rows": {"train": 3, "validation": 1}},
    )
    return case.make_world(members, splits, wells_document(wells), pre, 3, 3, 400)

def single_world(case, member, data, rows, curves_stats, counts, stats=None, eol_note=None):
    """One-member train-only world with matching synthetic metadata."""
    stats = stats or STANDARD_STATS
    members = {member: data}
    wells = [well_record(member, data, rows, "U-1", curves_stats)]
    splits = {
        "rows": [split_row("U-1", member, data, "train")],
        "well_counts": {"train": 1},
        "group_counts": {"train": 1},
    }
    pre = preprocessing_doc(
        channels=[
            channel_entry(name, stats[name][0], stats[name][1], counts[name])
            for name in scan.CHANNELS
        ],
        fitting_wells=[
            {"member": member, "member_sha256": sha(data), "uwi": "U-1", "well": "U-1", "rows": rows, "crc_verified": True}
        ],
    )
    return case.make_world(members, splits, wells_document(wells), pre, 1, 1, rows)


class StandardTests(BaseCase):
    def test_standard_fixture_selection_replay_and_guard(self):
        payload = self.run_world(standard_world(self))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["wells"]), 3)
        a = self.well(payload, "Train/A.las")
        b = self.well(payload, "Train/B.las")
        c = self.well(payload, "Train/C.las")
        self.assertIsNone(a["first_run_start"])
        self.assertEqual(a["max_run_len"], 127)
        self.assertEqual(b["first_run_start"], 5)
        self.assertEqual(b["max_run_len"], 128)
        self.assertEqual(c["first_run_start"], 0)
        self.assertEqual(c["max_run_len"], 130)
        selection = payload["selection"]
        self.assertTrue(selection["found"])
        self.assertEqual(selection["member"], "Train/B.las")
        self.assertEqual(selection["start_row"], 5)
        replay = payload["replay"]
        self.assertEqual(replay["mismatches"], 0)
        self.assertEqual(replay["overall_max_abs_error"], 0.0)
        self.assertEqual(replay["final_window_max_abs_error"], 0.0)
        self.assertEqual(replay["windows_compared"], 128)
        self.assertEqual(replay["final_window_values"], 1024)
        self.assertEqual(replay["total_values_compared"], 128 * 1024)
        self.assertEqual((replay["sequence_first"], replay["sequence_last"]), (5, 132))
        expected_input = "\n".join(
            "%d|%r|%r|%r|%r" % (index, 60.0, 2.5, 0.25, 10.0) for index in range(5, 133)
        )
        self.assertEqual(replay["input_sha256"], sha(expected_input.encode("utf-8")))
        self.assertEqual(replay["expected_output_sha256"], replay["actual_output_sha256"])
        guard = payload["guard"]
        self.assertEqual(guard["open_calls"], 4)
        self.assertEqual(guard["distinct_members"], 3)
        self.assertEqual(guard["heldout_open_attempts"], 0)
        self.assertEqual(guard["heldout_open_attempt_names"], [])
        self.assertEqual(
            sorted(guard["opened_members_in_order"]),
            ["Train/A.las", "Train/B.las", "Train/B.las", "Train/C.las"],
        )
        aggregate = payload["aggregate"]
        self.assertEqual(aggregate["GR"]["effectivevalid"], 387)
        self.assertEqual(aggregate["GR"]["null"], 13)
        self.assertEqual(aggregate["RHOB"]["effectivevalid"], 400)
        for name, row in payload["reconciliation"].items():
            self.assertTrue(row["valid_match"], name)
            self.assertTrue(row["null_plus_nonfinite_match"], name)
            self.assertTrue(row["nonpositive_match"], name)
            self.assertTrue(row["absent_match"], name)
        instrumentation = payload["parse_instrumentation"]
        self.assertEqual(instrumentation["selected_numeric_parse_attempts"], 4 * 400)
        self.assertEqual(instrumentation["nonselected_numeric_parse_attempts"], 0)
        self.assertEqual(payload["split_crosscheck"]["recorded_preprocessing_grouping_validation_reproduced"], True)

    def test_no_run_reports_limitation_without_replay(self):
        rows = [full_row(i, gr=("-999.25" if i in (0, 128) else "60")) for i in range(130)]
        data = las_bytes(CURVES_FULL, rows)
        world = single_world(
            self,
            "Solo.las",
            data,
            130,
            curve_stats(130, {"GR": 2}),
            {"GR": {"valid": 128, "null": 2, "nonpositive": 0, "absent": 0},
             "RHOB": {"valid": 130, "null": 0, "nonpositive": 0, "absent": 0},
             "NPHI": {"valid": 130, "null": 0, "nonpositive": 0, "absent": 0},
             "RDEP": {"valid": 130, "null": 0, "nonpositive": 0, "absent": 0}},
        )
        payload = self.run_world(world)
        self.assertFalse(payload["selection"]["found"])
        self.assertIsNone(payload["selection"]["member"])
        self.assertIsNone(payload["replay"])
        self.assertEqual(payload["guard"]["open_calls"], 1)
        self.assertEqual(payload["guard"]["distinct_members"], 1)

    def test_crlf_crcrlf_and_blank_lines_do_not_change_counts(self):
        rows = [full_row(i) for i in range(140)]
        counts = {name: {"valid": 140, "null": 0, "nonpositive": 0, "absent": 0} for name in scan.CHANNELS}
        worlds = []
        for eol in ("\n", "\r\n", "\r\r\n"):
            data = las_bytes(CURVES_FULL, rows, eol=eol)
            worlds.append(single_world(self, "Eol.las", data, 140, curve_stats(140), counts, eol_note=eol))
        payloads = [self.run_world(world) for world in worlds]
        aggregates = [payload["aggregate"] for payload in payloads]
        self.assertEqual(aggregates[0], aggregates[1])
        self.assertEqual(aggregates[0], aggregates[2])
        for payload in payloads:
            self.assertEqual(payload["wells"][0]["rows"], 140)

    def test_null_sentinel_and_negative_values(self):
        rows = []
        for index in range(10):
            gr = "-999.25" if index < 2 else "60"
            rhob = "-5.0" if index == 2 else "2.5"  # finite negative is valid for RHOB
            rows.append(full_row(index, gr=gr, rhob=rhob))
        data = las_bytes(CURVES_FULL, rows)
        world = single_world(
            self,
            "Null.las",
            data,
            10,
            curve_stats(10, {"GR": 2}),
            {"GR": {"valid": 8, "null": 2, "nonpositive": 0, "absent": 0},
             "RHOB": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "NPHI": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "RDEP": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0}},
        )
        payload = self.run_world(world)
        gr = self.well(payload, "Null.las")["channels"]["GR"]
        rhob = self.well(payload, "Null.las")["channels"]["RHOB"]
        self.assertEqual((gr["null"], gr["effectivevalid"]), (2, 8))
        self.assertEqual((rhob["rawvalid"], rhob["effectivevalid"], rhob["null"]), (10, 10, 0))
        self.assertTrue(payload["reconciliation"]["RHOB"]["valid_match"])

    def test_rdep_nonpositive_is_missing_for_log10_policy(self):
        rows = []
        for index in range(10):
            rdep = {0: "0.0", 1: "-1.0"}.get(index, "10.0")
            rows.append(full_row(index, rdep=rdep))
        data = las_bytes(CURVES_FULL, rows)
        world = single_world(
            self,
            "Rdep.las",
            data,
            10,
            curve_stats(10),
            {"GR": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "RHOB": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "NPHI": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "RDEP": {"valid": 8, "null": 0, "nonpositive": 2, "absent": 0}},
        )
        payload = self.run_world(world)
        rdep = self.well(payload, "Rdep.las")["channels"]["RDEP"]
        self.assertEqual((rdep["rawvalid"], rdep["effectivevalid"], rdep["nonpositive"]), (10, 8, 2))
        self.assertTrue(payload["reconciliation"]["RDEP"]["nonpositive_match"])
        self.assertEqual(self.well(payload, "Rdep.las")["all4_rows"], 8)

    def test_nonfinite_tokens_are_counted_missing(self):
        rows = []
        for index in range(10):
            gr = {0: "nan", 1: "inf", 2: "-inf"}.get(index, "60")
            rows.append(full_row(index, gr=gr))
        data = las_bytes(CURVES_FULL, rows)
        nonfinite_stats = curve_stats(10)
        for entry in nonfinite_stats:
            if entry["mnemonic"] == "GR":
                entry["nonmissing_count"] = 7
        world = single_world(
            self,
            "Nonfinite.las",
            data,
            10,
            nonfinite_stats,
            {"GR": {"valid": 7, "null": 3, "nonpositive": 0, "absent": 0},
             "RHOB": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "NPHI": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "RDEP": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0}},
        )
        payload = self.run_world(world)
        gr = self.well(payload, "Nonfinite.las")["channels"]["GR"]
        self.assertEqual((gr["nonfinite"], gr["null"], gr["effectivevalid"]), (3, 0, 7))
        reconciliation = payload["reconciliation"]["GR"]
        self.assertTrue(reconciliation["null_plus_nonfinite_match"])
        self.assertFalse(reconciliation["null_match"])

    def test_absent_channel_is_all_masked_with_explicit_counts(self):
        curves = [("DEPT", "m"), ("GR", "gAPI"), ("RHOB", "g/cm3"), ("RDEP", "ohm.m")]
        rows = [[str(index), "60", "2.5", "10.0"] for index in range(10)]
        present_stats = [
            {"mnemonic": "DEPT", "unit": "m", "count": 10, "null_count": 0, "nonmissing_count": 10},
            {"mnemonic": "GR", "unit": "gAPI", "count": 10, "null_count": 0, "nonmissing_count": 10},
            {"mnemonic": "RHOB", "unit": "g/cm3", "count": 10, "null_count": 0, "nonmissing_count": 10},
            {"mnemonic": "RDEP", "unit": "ohm.m", "count": 10, "null_count": 0, "nonmissing_count": 10},
        ]
        data = las_bytes(curves, rows)
        world = single_world(
            self,
            "Absent.las",
            data,
            10,
            present_stats,
            {"GR": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "RHOB": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0},
             "NPHI": {"valid": 0, "null": 0, "nonpositive": 0, "absent": 10},
             "RDEP": {"valid": 10, "null": 0, "nonpositive": 0, "absent": 0}},
        )
        payload = self.run_world(world)
        nphi = self.well(payload, "Absent.las")["channels"]["NPHI"]
        self.assertEqual((nphi["present"], nphi["absent_rows"], nphi["effectivevalid"]), (False, 10, 0))
        self.assertEqual(self.well(payload, "Absent.las")["all4_rows"], 0)
        self.assertTrue(payload["reconciliation"]["NPHI"]["absent_match"])

    def test_opaque_nonselected_columns_are_never_parsed(self):
        opaque_rows = []
        numeric_rows = []
        for index in range(8):
            opaque_rows.append(full_row(index, depth="not-a-depth") + ["litho_A", "??"])
            numeric_rows.append(full_row(index, depth=str(index)) + ["0.5", "1"])
        opaque = single_world(
            self,
            "Opaque.las",
            las_bytes(CURVES_OPAQUE, opaque_rows),
            8,
            curve_stats(8),
            {name: {"valid": 8, "null": 0, "nonpositive": 0, "absent": 0} for name in scan.CHANNELS},
        )
        numeric = single_world(
            self,
            "Opaque.las",
            las_bytes(CURVES_OPAQUE, numeric_rows),
            8,
            curve_stats(8),
            {name: {"valid": 8, "null": 0, "nonpositive": 0, "absent": 0} for name in scan.CHANNELS},
        )
        opaque_payload = self.run_world(opaque)
        numeric_payload = self.run_world(numeric)
        self.assertEqual(opaque_payload["aggregate"], numeric_payload["aggregate"])
        self.assertEqual(opaque_payload["parse_instrumentation"]["nonselected_numeric_parse_attempts"], 0)
        self.assertEqual(opaque_payload["parse_instrumentation"]["selected_numeric_parse_attempts"], 4 * 8)
        self.assertEqual(opaque_payload["wells"][0]["channels"], numeric_payload["wells"][0]["channels"])

def retarget(exp, **changes):
    values = {name: getattr(exp, name) for name in exp.__dataclass_fields__}
    values.update(changes)
    return scan.Expectations(**values)


def full_counts(valid, null=0, nonpositive=0, absent=0):
    return {
        name: {"valid": valid, "null": null, "nonpositive": nonpositive, "absent": absent}
        for name in scan.CHANNELS
    }


def doctored_world(case, member, data, actual_rows, declared_rows, counts,
                   record_sha=None, split_sha=None, record_size=None, fitting="auto"):
    """Single-member world whose metadata can deliberately disagree with the member."""
    actual = sha(data)
    record_sha = actual if record_sha is None else record_sha
    split_sha = actual if split_sha is None else split_sha
    members = {member: data}
    record = {
        "member": member,
        "member_size_bytes": len(data) if record_size is None else record_size,
        "member_sha256": record_sha,
        "rows": declared_rows,
        "crc_verified": True,
        "uwi": "U-1",
        "well": "U-1",
        "curves": curve_stats(declared_rows),
    }
    split_entry = split_row("U-1", member, data, "train")
    split_entry["member_sha256"] = split_sha
    splits = {
        "rows": [split_entry],
        "well_counts": {"train": 1},
        "group_counts": {"train": 1},
    }
    if fitting == "auto":
        fitting = [
            {"member": member, "member_sha256": record_sha, "uwi": "U-1",
             "well": "U-1", "rows": actual_rows, "crc_verified": True}
        ]
    pre = preprocessing_doc(
        channels=[
            channel_entry(name, STANDARD_STATS[name][0], STANDARD_STATS[name][1], counts[name])
            for name in scan.CHANNELS
        ],
        fitting_wells=fitting,
    )
    return case.make_world(members, splits, wells_document([record]), pre, 1, 1, declared_rows)


class MalformedLasTests(BaseCase):
    def single(self, data, rows, counts=None):
        return single_world(self, "Mal.las", data, rows, curve_stats(rows), counts or full_counts(rows))

    def test_malformed_numeric_in_selected_column_fails(self):
        rows = [full_row(index) for index in range(10)]
        rows[3] = full_row(3, gr="60x")
        world = self.single(las_bytes(CURVES_FULL, rows), 10)
        with self.assertRaisesRegex(scan.AuditError, "malformed numeric token '60x' in selected GR column"):
            self.run_world(world)
        for column in ("rhob", "nphi", "rdep"):
            bad_rows = [full_row(index) for index in range(6)]
            bad_rows[2] = full_row(2, **{column: "bad"})
            world = self.single(las_bytes(CURVES_FULL, bad_rows), 6)
            with self.assertRaisesRegex(scan.AuditError, "in selected %s column" % column.upper()):
                self.run_world(world)

    def test_wrong_row_token_count_fails(self):
        rows = [full_row(index) for index in range(10)]
        rows[5] = full_row(5) + ["0"]
        world = self.single(las_bytes(CURVES_FULL, rows), 10)
        with self.assertRaisesRegex(scan.AuditError, "row has 6 values for 5 curves"):
            self.run_world(world)

    def test_wrong_las_version_fails(self):
        rows = [full_row(index) for index in range(6)]
        world = self.single(las_bytes(CURVES_FULL, rows, vers="1.2"), 6)
        with self.assertRaisesRegex(scan.AuditError, "unsupported LAS version"):
            self.run_world(world)

    def test_wrap_yes_fails(self):
        rows = [full_row(index) for index in range(6)]
        world = self.single(las_bytes(CURVES_FULL, rows, wrap="YES"), 6)
        with self.assertRaisesRegex(scan.AuditError, "unsupported WRAP"):
            self.run_world(world)

    def test_duplicate_curve_mnemonic_fails(self):
        curves = CURVES_FULL + [("GR", "gAPI")]
        rows = [full_row(index) + ["60"] for index in range(6)]
        world = self.single(las_bytes(curves, rows), 6)
        with self.assertRaisesRegex(scan.AuditError, "duplicate curve mnemonic 'GR'"):
            self.run_world(world)

    def test_missing_null_sentinel_fails(self):
        rows = [full_row(index) for index in range(6)]
        world = self.single(las_bytes(CURVES_FULL, rows, null=None), 6)
        with self.assertRaisesRegex(scan.AuditError, "NULL sentinel missing before data section"):
            self.run_world(world)


class GuardUnitTests(BaseCase):
    def test_guarded_zip_allows_train_and_blocks_heldout(self):
        zip_path = self.root / "guard.zip"
        data = las_bytes(CURVES_FULL, [full_row(0)])
        build_zip(zip_path, {"Train/A.las": data, "Train/V.las": data})
        journal = scan.OpenJournal()
        with scan.GuardedZip(str(zip_path), allowed=["Train/A.las"], journal=journal) as zf:
            with zf.open("Train/A.las") as stream:
                self.assertEqual(stream.read(), data)
            with self.assertRaises(scan.GuardViolation):
                zf.open("Train/V.las")
        self.assertEqual(journal.opened, ["Train/A.las"])
        self.assertEqual(journal.heldout_attempts, ["Train/V.las"])
        self.assertTrue(issubclass(scan.GuardViolation, scan.AuditError))

    def test_guarded_zip_is_read_only_and_rejects_write_modes(self):
        zip_path = self.root / "guard2.zip"
        data = las_bytes(CURVES_FULL, [full_row(0)])
        build_zip(zip_path, {"Train/A.las": data})
        journal = scan.OpenJournal()
        with self.assertRaises(ValueError):
            scan.GuardedZip(str(zip_path), mode="w", allowed=["Train/A.las"], journal=journal)
        with scan.GuardedZip(str(zip_path), allowed=["Train/A.las"], journal=journal) as zf:
            with self.assertRaises(ValueError):
                zf.open("Train/A.las", mode="w")


class RunLogicTests(unittest.TestCase):
    def test_first_run_reaching_edges(self):
        self.assertEqual(scan.first_run_reaching(b""), (None, 0))
        self.assertEqual(scan.first_run_reaching(b"\x01" * 127), (None, 127))
        self.assertEqual(scan.first_run_reaching(b"\x01" * 128), (0, 128))
        self.assertEqual(scan.first_run_reaching(b"\x01" * 129), (0, 129))
        self.assertEqual(scan.first_run_reaching(b"\x01" * 127 + b"\x00"), (None, 127))
        self.assertEqual(scan.first_run_reaching(b"\x00" + b"\x01" * 128), (1, 128))
        self.assertEqual(scan.first_run_reaching(b"\x01" * 3 + b"\x00" * 5 + b"\x01" * 128), (8, 128))
        self.assertEqual(scan.first_run_reaching(b"\x00\x01\x01", length=3), (None, 2))
        self.assertEqual(scan.first_run_reaching(b"\x00\x01\x01\x01", length=3), (1, 3))
        self.assertEqual(scan.first_run_reaching(b"\x01\x00\x01\x01\x01", length=3), (2, 3))


class RejectionTests(BaseCase):
    def good_member(self):
        return las_bytes(CURVES_FULL, [full_row(index) for index in range(10)])

    def test_archive_bytes_and_sha_mismatch_rejected(self):
        data = self.good_member()
        world = single_world(self, "Rej.las", data, 10, curve_stats(10), full_counts(10))
        zip_path, prod, exp = world
        forged = retarget(exp, archive_bytes=exp.archive_bytes + 1)
        with self.assertRaisesRegex(scan.AuditError, "archive identity mismatch"):
            scan.run_audit(str(zip_path), str(prod), expectations=forged)
        forged = retarget(exp, archive_sha256="0" * 64)
        with self.assertRaisesRegex(scan.AuditError, "archive identity mismatch"):
            scan.run_audit(str(zip_path), str(prod), expectations=forged)

    def test_production_labelled_tampered_expectations_refused(self):
        data = self.good_member()
        world = single_world(self, "Rej.las", data, 10, curve_stats(10), full_counts(10))
        zip_path, prod, exp = world
        forged = retarget(exp, label=scan.PRODUCTION_EXPECTATIONS.label, train_rows=exp.train_rows + 1)
        with self.assertRaisesRegex(scan.AuditError, "refusing a production-labelled"):
            scan.run_audit(str(zip_path), str(prod), expectations=forged)

    def test_splits_and_preprocessing_pin_mismatch_rejected(self):
        data = self.good_member()
        world = single_world(self, "Rej.las", data, 10, curve_stats(10), full_counts(10))
        zip_path, prod, exp = world
        forged = retarget(exp, splits_sha256="f" * 64)
        with self.assertRaisesRegex(scan.AuditError, "splits\\.json sha256"):
            scan.run_audit(str(zip_path), str(prod), expectations=forged)
        forged = retarget(exp, preprocessing_sha256="f" * 64)
        with self.assertRaisesRegex(scan.AuditError, "preprocessing\\.json sha256"):
            scan.run_audit(str(zip_path), str(prod), expectations=forged)
        forged = retarget(exp, wells_sha256="f" * 64)
        with self.assertRaisesRegex(scan.AuditError, "force_wells\\.json sha256"):
            scan.run_audit(str(zip_path), str(prod), expectations=forged)

    def test_member_size_mismatch_rejected(self):
        data = self.good_member()
        world = doctored_world(self, "Size.las", data, 10, 10, full_counts(10), record_size=len(data) + 1)
        with self.assertRaisesRegex(scan.AuditError, "member size mismatch for Size.las"):
            self.run_world(world)

    def test_inventory_splits_sha_mismatch_rejected(self):
        data = self.good_member()
        world = doctored_world(self, "ShaA.las", data, 10, 10, full_counts(10),
                               record_sha=sha(data + b"x"), split_sha=sha(data))
        with self.assertRaisesRegex(scan.AuditError, "member sha mismatch between splits and inventory"):
            self.run_world(world)

    def test_decompressed_member_sha_mismatch_rejected(self):
        data = self.good_member()
        forged_sha = sha(data + b"x")
        world = doctored_world(self, "ShaB.las", data, 10, 10, full_counts(10),
                               record_sha=forged_sha, split_sha=forged_sha)
        with self.assertRaisesRegex(scan.AuditError, "member uncompressed sha256 mismatch for ShaB.las"):
            self.run_world(world)

    def test_rowcount_mismatch_rejected(self):
        data = self.good_member()
        world = doctored_world(self, "Count.las", data, 10, 11, full_counts(11))
        with self.assertRaisesRegex(scan.AuditError, "member rowcount mismatch for Count.las"):
            self.run_world(world)

    def test_fitting_wells_set_mismatch_rejected(self):
        data = self.good_member()
        world = doctored_world(self, "Fit.las", data, 10, 10, full_counts(10), fitting=[])
        with self.assertRaisesRegex(scan.AuditError, "preprocessing fitting_wells set does not equal"):
            self.run_world(world)

    def test_fitting_wells_sha_mismatch_rejected(self):
        data = self.good_member()
        fitting = [{"member": "Fit2.las", "member_sha256": sha(data + b"y"), "uwi": "U-1",
                    "well": "U-1", "rows": 10, "crc_verified": True}]
        world = doctored_world(self, "Fit2.las", data, 10, 10, full_counts(10), fitting=fitting)
        with self.assertRaisesRegex(scan.AuditError, "fitting_wells sha mismatch for Fit2.las"):
            self.run_world(world)

    def test_cross_split_parent_grouping_rejected(self):
        member_a = "Train/Ga.las"
        member_v = "Train/Gv.las"
        data_a = las_bytes(CURVES_FULL, [full_row(index) for index in range(10)])
        data_v = las_bytes(CURVES_FULL, [full_row(index) for index in range(20)])
        members = {member_a: data_a, member_v: data_v}
        splits = {
            "rows": [
                split_row("G-1", member_a, data_a, "train", root_id="P-9"),
                split_row("G-2", member_v, data_v, "validation", root_id="P-9"),
            ],
            "well_counts": {"train": 1, "validation": 1},
            "group_counts": {"train": 1, "validation": 1},
        }
        wells = wells_document([well_record(member_a, data_a, 10, "G-1", curve_stats(10))])
        pre = preprocessing_doc(
            channels=[
                channel_entry(name, STANDARD_STATS[name][0], STANDARD_STATS[name][1], full_counts(10)[name])
                for name in scan.CHANNELS
            ],
            fitting_wells=[
                {"member": member_a, "member_sha256": sha(data_a), "uwi": "G-1",
                 "well": "G-1", "rows": 10, "crc_verified": True}
            ],
        )
        world = self.make_world(members, splits, wells, pre, 1, 1, 10)
        with self.assertRaisesRegex(scan.AuditError, "grouping validation failed"):
            self.run_world(world)


if __name__ == "__main__":
    unittest.main(verbosity=2)
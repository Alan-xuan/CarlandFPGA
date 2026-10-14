"""Independent tests for data.grouping (C01 foundation).

Negative coverage: derivatives crossing splits, root groups crossing splits,
duplicate row ids, unknown parents, cycles, missing identities/splits and
domain independence.  These are caller-supplied assignment tables; no
licensed dataset is read, downloaded or hashed here.
"""

import sys
import unittest
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from data.grouping import (  # noqa: E402
    SPLITS,
    SplitAssignmentError,
    SplitValidationReport,
    validate_split_assignments,
)


def row(row_id, domain="force", root=None, split="train", derived_from=None):
    entry = {
        "row_id": row_id,
        "source_domain": domain,
        "root_id": root or row_id,
        "split": split,
    }
    if derived_from is not None:
        entry["derived_from"] = derived_from
    return entry


class SplitAssignmentValidationTests(unittest.TestCase):
    def codes(self, rows, **kwargs):
        with self.assertRaises(SplitAssignmentError) as ctx:
            validate_split_assignments(rows, **kwargs)
        return [violation.code for violation in ctx.exception.violations]

    def test_valid_assignment_report(self):
        rows = [
            row("force-w1-raw", root="w1", split="train"),
            row("force-w1-aug", root="w1", split="train", derived_from="force-w1-raw"),
            row("force-w2-raw", root="w2", split="validation"),
            row("force-w3-raw", root="w3", split="test"),
            row("sim-r1-frame", domain="sim_em_v2", root="r1", split="test"),
            row("sim-r1-aug", domain="sim_em_v2", root="r1", split="test", derived_from="sim-r1-frame"),
        ]
        report = validate_split_assignments(rows)
        self.assertIsInstance(report, SplitValidationReport)
        self.assertEqual(report.rows, 6)
        self.assertEqual(report.root_count, 4)
        self.assertEqual(report.split_rows, {"train": 2, "validation": 1, "test": 3})
        force = report.domains["force"]
        self.assertEqual(force.rows, 4)
        self.assertEqual(force.roots, 3)
        self.assertEqual(force.derivatives, 1)
        self.assertEqual(force.root_splits, {"w1": "train", "w2": "validation", "w3": "test"})
        sim = report.domains["sim_em_v2"]
        self.assertEqual(sim.roots, 1)
        self.assertEqual(sim.root_splits, {"r1": "test"})
        self.assertEqual(SPLITS, ("train", "validation", "test"))

    def test_derivative_crossing_sets_rejected(self):
        rows = [
            row("w1-raw", root="w1", split="train"),
            row("w1-aug-test", root="w1", split="test", derived_from="w1-raw"),
            row("w1-aug", root="w1", split="train", derived_from="w1-raw"),
        ]
        self.assertIn("cross_split_root", self.codes(rows))

    def test_derivative_root_mismatch_rejected(self):
        rows = [
            row("w1-raw", root="w1", split="train"),
            row("w2-raw", root="w2", split="train"),
            row("w1-aug", root="w1", split="train", derived_from="w2-raw"),
        ]
        self.assertIn("derivative_root_mismatch", self.codes(rows))

    def test_derivative_domain_mismatch_rejected(self):
        rows = [
            row("sim-aug", domain="sim_em_v2", root="w1", split="train", derived_from="w1-raw"),
            row("w1-raw", domain="force", root="w1", split="train"),
        ]
        self.assertIn("derivative_domain_mismatch", self.codes(rows))

    def test_derivative_cycles_rejected(self):
        rows = [
            row("a", root="w1", split="train", derived_from="b"),
            row("b", root="w1", split="train", derived_from="a"),
        ]
        self.assertIn("derivative_cycle", self.codes(rows))
        self.assertIn(
            "derivative_cycle",
            self.codes([row("x", root="w1", split="train", derived_from="x")]),
        )

    def test_unknown_parent_rejected(self):
        rows = [row("w1-aug", root="w1", split="train", derived_from="missing-row")]
        self.assertIn("unknown_parent", self.codes(rows))

    def test_duplicate_row_id_rejected(self):
        rows = [
            row("dup", root="w1", split="train"),
            row("dup", root="w1", split="train"),
        ]
        self.assertIn("duplicate_row_id", self.codes(rows))

    def test_missing_identity_and_split_rejected(self):
        rows = [
            {"row_id": "no-root", "source_domain": "force", "split": "train"},
            {"row_id": "no-split", "source_domain": "force", "root_id": "w9"},
            row("bad-split", root="w9", split="holdout"),
            {"source_domain": "force", "root_id": "w9", "split": "train"},
            {"row_id": "bad-parent", "source_domain": "force", "root_id": "w9", "split": "train", "derived_from": ""},
        ]
        codes = self.codes(rows)
        self.assertIn("missing_identity", codes)
        self.assertIn("missing_split", codes)
        self.assertIn("invalid_split", codes)

    def test_same_root_id_in_two_domains_is_independent(self):
        rows = [
            row("force-w1", domain="force", root="shared-id", split="train"),
            row("sim-s1", domain="sim_em_v2", root="shared-id", split="test"),
        ]
        report = validate_split_assignments(rows)
        self.assertEqual(report.domains["force"].root_splits["shared-id"], "train")
        self.assertEqual(report.domains["sim_em_v2"].root_splits["shared-id"], "test")

    def test_all_violations_reported_together(self):
        rows = [
            row("dup", root="w1", split="train"),
            row("dup", root="w1", split="train"),
            row("w1-other", root="w1", split="test"),
            row("w2-aug", root="w2", split="train", derived_from="ghost"),
        ]
        codes = set(self.codes(rows))
        self.assertTrue(
            {"duplicate_row_id", "cross_split_root", "unknown_parent"} <= codes
        )

    def test_splits_argument_is_validated(self):
        with self.assertRaises(ValueError):
            validate_split_assignments([], splits=())
        with self.assertRaises(ValueError):
            validate_split_assignments([], splits=("train", "train"))
        report = validate_split_assignments(
            [row("w1", root="w1", split="holdout")], splits=("holdout",)
        )
        self.assertEqual(report.split_rows, {"holdout": 1})

    def test_empty_table_is_accepted(self):
        report = validate_split_assignments([])
        self.assertEqual(report.rows, 0)
        self.assertEqual(report.root_count, 0)
        self.assertEqual(report.domains, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)

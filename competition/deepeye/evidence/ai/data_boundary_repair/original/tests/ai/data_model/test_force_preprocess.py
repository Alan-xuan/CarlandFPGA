"""Unit tests for data/force_preprocess.py with synthetic mini LAS scenes.

Software-only evidence for the bounded C01 train-only preprocessing fitter:
provenance-aware hash verification before ingest, train-only decompression,
held-out invariance, strict row parsing with member/line failures, LAS NULL
versus valid negatives, RDEP log10 with nonpositive masking, absent/constant
channel handling, Welford population statistics, deterministic split row
order, the output document provenance and the CLI exit contract.  Everything
here uses synthetic archives and manifests inside TemporaryDirectory; these
tests are not a data source, not a model evaluation and not product-card
acceptance (C01 stays not_run).
"""

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True

_HERE = Path(__file__).resolve().parent
_MODULE_PATH = _HERE.parents[2] / "data" / "force_preprocess.py"

_CONTRACT = {
    "id": "DEEPEYE-HUMAN-LOCK-20261014",
    "revision": 1,
    "source_commit": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
    "requirements_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
}
CURVE_ORDER = ["GR", "RHOB", "NPHI", "RDEP"]
_DEFAULT_CURVES = [
    ("DEPT", "m"),
    ("FORCE_2020_LITHOFACIES_CONFIDENCE", "_"),
    ("FORCE_2020_LITHOFACIES_LITHOLOGY", "_"),
    ("GR", "gAPI"),
    ("RHOB", "g/cm3"),
    ("NPHI", "m3/m3"),
    ("RDEP", "ohm.m"),
]
_SPLIT_NAMES = ("train", "validation", "test")
_DEFAULT_SOURCE_DOMAIN = "synthetic_unit_test"


def _normalise_split_spec(spec):
    """Accept (split, root[, derived_from]) tuples or full mapping specs."""
    if isinstance(spec, dict):
        return {
            "split": spec["split"],
            "root": spec["root"],
            "derived_from": spec.get("derived_from"),
            "row_id": spec.get("row_id"),
            "source_domain": spec.get("source_domain", _DEFAULT_SOURCE_DOMAIN),
        }
    split_name = spec[0]
    root_id = spec[1]
    derived_from = spec[2] if len(spec) > 2 else None
    return {
        "split": split_name,
        "root": root_id,
        "derived_from": derived_from,
        "row_id": None,
        "source_domain": _DEFAULT_SOURCE_DOMAIN,
    }


def _load_module():
    spec = importlib.util.spec_from_file_location("deepeye_force_preprocess", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


force_preprocess = _load_module()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _las_bytes(curves, rows, uwi, well=None, vers="2.0", wrap="NO", null_text="-999.25",
               terminator="\r\n"):
    lines = [
        "# synthetic LAS for preprocessing unit tests",
        "~Version information",
        "VERS.   %s:" % vers,
        "WRAP.   %s:" % wrap,
        "~Well",
        "NULL .        %s :" % null_text,
        "WELL.  %s : WELL" % (well if well is not None else uwi),
        "UWI.   %s : UNIQUE WELL ID" % uwi,
        "~Curve",
    ]
    for mnemonic, unit in curves:
        lines.append("%s .%s : %s" % (mnemonic, unit, mnemonic))
    lines.append("~Ascii")
    lines.extend(rows)
    return (terminator.join(lines) + terminator).encode("ascii")


class _Scene:
    """Synthetic mini archive plus inventory/splits/policy/label manifests."""

    def __init__(self, root, wells, split_map, curve_order=None, contract=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.wells = wells
        self.split_map = {
            member: _normalise_split_spec(spec) for member, spec in split_map.items()
        }
        self.curve_order = list(curve_order if curve_order is not None else CURVE_ORDER)
        self.contract = dict(contract if contract is not None else _CONTRACT)
        missing = set(wells) - set(self.split_map)
        extra = set(self.split_map) - set(wells)
        assert not missing and not extra, (missing, extra)
        self.zip_path = self.root / "mini.zip"
        self.inventory_path = self.root / "inventory.json"
        self.splits_path = self.root / "splits.json"
        self.policy_path = self.root / "split_policy.json"
        self.label_path = self.root / "label_schema.json"
        self._write_zip()
        self._write_policy()
        self._write_label()
        self._derive_inventory()
        self._rebuild_splits()

    def member_bytes(self, member):
        with zipfile.ZipFile(self.zip_path) as archive:
            return archive.read(member)

    def _write_zip(self):
        with zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for member, spec in self.wells.items():
                archive.writestr(
                    member,
                    _las_bytes(
                        spec.get("curves", _DEFAULT_CURVES),
                        spec["rows"],
                        spec["uwi"],
                        well=spec.get("well"),
                        vers=spec.get("vers", "2.0"),
                        wrap=spec.get("wrap", "NO"),
                        null_text=spec.get("null_text", "-999.25"),
                        terminator=spec.get("terminator", "\r\n"),
                    ),
                )

    def rewrite_member_bytes(self, member, data):
        with zipfile.ZipFile(self.zip_path) as archive:
            members = [
                (info.filename, archive.read(info.filename))
                for info in archive.infolist()
            ]
        with zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in members:
                archive.writestr(name, data if name == member else content)
        self._rebuild_splits()

    def _write_policy(self):
        document = {
            "schema": 1,
            "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
            "contract": self.contract,
            "preprocessing": {"curve_order": self.curve_order},
        }
        self.policy_path.write_text(json.dumps(document), encoding="utf-8")

    def _write_label(self):
        document = {
            "schema": 1,
            "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
            "contract": self.contract,
            "input_curve_order": self.curve_order,
            "classes": [{"index": 0, "name": "Sandstone"}],
        }
        self.label_path.write_text(json.dumps(document), encoding="utf-8")

    def _derive_inventory(self):
        wells = []
        for member, spec in self.wells.items():
            data = self.member_bytes(member)
            curves = spec.get("curves", _DEFAULT_CURVES)
            wells.append(
                {
                    "member": member,
                    "member_size_bytes": len(data),
                    "member_sha256": hashlib.sha256(data).hexdigest(),
                    "crc_verified": True,
                    "rows": len(spec["rows"]),
                    "uwi": spec["uwi"],
                    "well": spec.get("well") or spec["uwi"],
                    "null_value": float(spec.get("null_text", "-999.25")),
                    "vers": spec.get("vers", "2.0"),
                    "wrap": spec.get("wrap", "NO"),
                    "curves": [
                        {"mnemonic": mnemonic, "unit": unit}
                        for mnemonic, unit in curves
                    ],
                }
            )
        document = {
            "schema": 1,
            "kind": "deepeye-force-las-inventory",
            "wells": wells,
        }
        self.inventory_path.write_text(
            json.dumps(document, indent=2), encoding="utf-8"
        )

    def load_inventory(self):
        return json.loads(self.inventory_path.read_text(encoding="utf-8"))

    def save_inventory(self, document):
        self.inventory_path.write_text(
            json.dumps(document, indent=2), encoding="utf-8"
        )

    def load_splits(self):
        return json.loads(self.splits_path.read_text(encoding="utf-8"))

    def save_splits(self, document):
        self.splits_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    def expected_counts(self):
        wells = Counter()
        groups = {name: set() for name in _SPLIT_NAMES}
        for spec in self.split_map.values():
            wells[spec["split"]] += 1
            groups[spec["split"]].add((spec["source_domain"], spec["root"]))
        return {
            "well_counts": {name: wells[name] for name in _SPLIT_NAMES},
            "group_counts": {name: len(groups[name]) for name in _SPLIT_NAMES},
        }

    def _rebuild_splits(self):
        inventory = self.load_inventory()
        by_member = {record["member"]: record for record in inventory["wells"]}
        rows = []
        for member, spec in self.split_map.items():
            record = by_member[member]
            rows.append(
                {
                    "row_id": spec["row_id"] or record["uwi"],
                    "source_domain": spec["source_domain"],
                    "root_id": spec["root"],
                    "well_id": record["uwi"],
                    "member": member,
                    "member_sha256": record["member_sha256"],
                    "split": spec["split"],
                    "derived_from": spec["derived_from"],
                }
            )
        counts = self.expected_counts()
        document = {
            "schema": 1,
            "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
            "contract": self.contract,
            "policy_sha256": _sha256_file(self.policy_path),
            "label_schema_sha256": _sha256_file(self.label_path),
            "inventory_sha256": _sha256_file(self.inventory_path),
            "source_archive_sha256": _sha256_file(self.zip_path),
            "well_counts": counts["well_counts"],
            "group_counts": counts["group_counts"],
            "rows": rows,
        }
        self.save_splits(document)

    def fit(self, **overrides):
        counts = self.expected_counts()
        kwargs = {
            "archive_path": str(self.zip_path),
            "inventory_path": str(self.inventory_path),
            "splits_path": str(self.splits_path),
            "policy_path": str(self.policy_path),
            "label_path": str(self.label_path),
            "expected_archive_bytes": os.path.getsize(self.zip_path),
            "expected_archive_sha256": _sha256_file(self.zip_path),
            "expected_inventory_sha256": _sha256_file(self.inventory_path),
            "expected_splits_sha256": _sha256_file(self.splits_path),
            "expected_well_counts": counts["well_counts"],
            "expected_group_counts": counts["group_counts"],
        }
        kwargs.update(overrides)
        return force_preprocess.fit_preprocessing(**kwargs)

    def write_expectations(self, path, **overrides):
        counts = self.expected_counts()
        document = {
            "archive_bytes": os.path.getsize(self.zip_path),
            "archive_sha256": _sha256_file(self.zip_path),
            "inventory_sha256": _sha256_file(self.inventory_path),
            "splits_sha256": _sha256_file(self.splits_path),
            "well_counts": counts["well_counts"],
            "group_counts": counts["group_counts"],
        }
        document.update(overrides)
        Path(path).write_text(json.dumps(document), encoding="utf-8")
        return Path(path)

    def channel(self, document, name):
        for report in document["channels"]:
            if report["name"] == name:
                return report
        raise AssertionError("channel %s missing" % name)


_STANDARD_WELLS = {
    "mini/train_a.las": {
        "uwi": "1/1-1",
        "rows": [
            "0.0 1 30000 10.0 2.0 0.1 1.0",
            "1.0 1 30000 20.0 2.5 0.2 10.0",
            "2.0 1 30000 30.0 3.0 0.3 100.0",
        ],
    },
    "mini/train_b.las": {
        "uwi": "2/2-2",
        "rows": [
            "0.0 2 65000 -50.0 -999.25 0.05 0.5",
            "1.0 2 65000 -999.25 2.0 0.15 -10.0",
            "2.0 2 65000 -25.0 2.2 -999.25 0.0",
        ],
    },
    "mini/val_a.las": {
        "uwi": "3/3-3",
        "rows": [
            "0.0 1 30000 1e9 -1e9 1e9 1e9",
            "1.0 1 30000 -1e9 1e9 -1e9 1e-9",
        ],
    },
    "mini/test_a.las": {
        "uwi": "4/4-4",
        "rows": ["0.0 3 90000 0.0 0.0 0.0 0.0"],
    },
}

_STANDARD_SPLITS = {
    "mini/train_a.las": ("train", "1/1-1"),
    "mini/train_b.las": ("train", "2/2-2"),
    "mini/val_a.las": ("validation", "3/3-3"),
    "mini/test_a.las": ("test", "4/4-4"),
}


class ForcePreprocessTests(unittest.TestCase):
    maxDiff = None

    def test_analytic_two_and_three_point_statistics(self):
        with tempfile.TemporaryDirectory() as tmp:
            wells = {
                "mini/three.las": {
                    "uwi": "7/1-1",
                    "rows": [
                        "0.0 1 30000 10.0 2.0 0.1 1.0",
                        "1.0 1 30000 20.0 2.5 0.2 10.0",
                        "2.0 1 30000 30.0 3.0 0.3 100.0",
                    ],
                },
                "mini/val.las": {"uwi": "7/1-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            splits = {
                "mini/three.las": ("train", "7/1-1"),
                "mini/val.las": ("validation", "7/1-2"),
            }
            scene = _Scene(tmp, wells, splits)
            document = scene.fit()
            gr = scene.channel(document, "GR")
            self.assertEqual(
                gr["counts"], {"valid": 3, "null": 0, "nonpositive": 0, "absent": 0}
            )
            self.assertEqual(gr["valid_samples"], 3)
            self.assertAlmostEqual(gr["mean"], 20.0, places=12)
            self.assertAlmostEqual(gr["variance"], 200.0 / 3.0, places=12)
            self.assertAlmostEqual(gr["std"], (200.0 / 3.0) ** 0.5, places=12)
            self.assertFalse(gr["zero_variance"])
            rhob = scene.channel(document, "RHOB")
            self.assertAlmostEqual(rhob["mean"], 2.5, places=12)
            self.assertAlmostEqual(rhob["variance"], 0.5 / 3.0, places=12)
            nphi = scene.channel(document, "NPHI")
            self.assertAlmostEqual(nphi["mean"], 0.2, places=12)
            self.assertAlmostEqual(nphi["variance"], 0.02 / 3.0, places=12)
            rdep = scene.channel(document, "RDEP")
            self.assertEqual(rdep["transform_version"], "log10-positive-v1")
            self.assertAlmostEqual(rdep["mean"], 1.0, places=12)
            self.assertAlmostEqual(rdep["variance"], 2.0 / 3.0, places=12)

            two = Path(tmp) / "two"
            wells_two = {
                "mini/two.las": {
                    "uwi": "7/2-1",
                    "rows": [
                        "0.0 1 30000 10.0 2.0 0.1 1.0",
                        "1.0 1 30000 30.0 4.0 0.3 100.0",
                    ],
                },
                "mini/val.las": {"uwi": "7/1-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            scene_two = _Scene(
                two,
                wells_two,
                {"mini/two.las": ("train", "7/2-1"), "mini/val.las": ("validation", "7/1-2")},
            )
            document_two = scene_two.fit()
            gr_two = scene_two.channel(document_two, "GR")
            self.assertEqual(gr_two["valid_samples"], 2)
            self.assertAlmostEqual(gr_two["mean"], 20.0, places=12)
            self.assertAlmostEqual(gr_two["variance"], 100.0, places=12)
            rhob_two = scene_two.channel(document_two, "RHOB")
            self.assertAlmostEqual(rhob_two["mean"], 3.0, places=12)
            self.assertAlmostEqual(rhob_two["variance"], 1.0, places=12)
            nphi_two = scene_two.channel(document_two, "NPHI")
            self.assertAlmostEqual(nphi_two["mean"], 0.2, places=12)
            self.assertAlmostEqual(nphi_two["variance"], 0.01, places=12)
            rdep_two = scene_two.channel(document_two, "RDEP")
            self.assertAlmostEqual(rdep_two["mean"], 1.0, places=12)
            self.assertAlmostEqual(rdep_two["variance"], 1.0, places=12)

    def test_null_versus_valid_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            wells = {
                "mini/train.las": {
                    "uwi": "7/3-1",
                    "rows": [
                        "0.0 1 30000 10.0 2.0 0.1 1.0",
                        "1.0 1 30000 -999.25 2.0 0.1 1.0",
                        "2.0 1 30000 -50.0 2.0 0.1 1.0",
                    ],
                },
                "mini/val.las": {"uwi": "7/3-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            scene = _Scene(
                tmp,
                wells,
                {"mini/train.las": ("train", "7/3-1"), "mini/val.las": ("validation", "7/3-2")},
            )
            document = scene.fit()
            gr = scene.channel(document, "GR")
            self.assertEqual(
                gr["counts"], {"valid": 2, "null": 1, "nonpositive": 0, "absent": 0}
            )
            self.assertAlmostEqual(gr["mean"], -20.0, places=12)
            self.assertAlmostEqual(gr["variance"], 900.0, places=12)
            rhob = scene.channel(document, "RHOB")
            self.assertEqual(
                rhob["counts"], {"valid": 3, "null": 0, "nonpositive": 0, "absent": 0}
            )
            self.assertTrue(rhob["zero_variance"])
            self.assertEqual(rhob["std"], 0.0)
            self.assertEqual(rhob["effective_scale"], 1.0)

    def test_rdep_nonpositive_masked_and_log10(self):
        with tempfile.TemporaryDirectory() as tmp:
            wells = {
                "mini/train.las": {
                    "uwi": "7/4-1",
                    "rows": [
                        "0.0 1 30000 5.0 2.0 0.1 0.0",
                        "1.0 1 30000 5.0 2.0 0.1 -5.0",
                        "2.0 1 30000 5.0 2.0 0.1 100.0",
                    ],
                },
                "mini/val.las": {"uwi": "7/4-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            scene = _Scene(
                tmp,
                wells,
                {"mini/train.las": ("train", "7/4-1"), "mini/val.las": ("validation", "7/4-2")},
            )
            document = scene.fit()
            rdep = scene.channel(document, "RDEP")
            self.assertEqual(
                rdep["counts"], {"valid": 1, "null": 0, "nonpositive": 2, "absent": 0}
            )
            self.assertAlmostEqual(rdep["mean"], 2.0, places=12)
            self.assertEqual(rdep["variance"], 0.0)
            self.assertTrue(rdep["zero_variance"])
            self.assertEqual(rdep["effective_scale"], 1.0)

    def test_absent_channel_counts_remain_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            reduced_curves = [
                ("DEPT", "m"),
                ("FORCE_2020_LITHOFACIES_CONFIDENCE", "_"),
                ("FORCE_2020_LITHOFACIES_LITHOLOGY", "_"),
                ("GR", "gAPI"),
                ("RHOB", "g/cm3"),
                ("RDEP", "ohm.m"),
            ]
            wells = {
                "mini/no_nphi.las": {
                    "uwi": "8/1-1",
                    "curves": reduced_curves,
                    "rows": ["0.0 1 30000 10.0 2.0 1.0"],
                },
                "mini/with_nphi.las": {
                    "uwi": "8/1-2",
                    "rows": [
                        "0.0 1 30000 10.0 2.0 0.1 1.0",
                        "1.0 1 30000 20.0 2.0 0.3 1.0",
                    ],
                },
                "mini/val.las": {"uwi": "8/1-3", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            scene = _Scene(
                tmp,
                wells,
                {
                    "mini/no_nphi.las": ("train", "8/1-1"),
                    "mini/with_nphi.las": ("train", "8/1-2"),
                    "mini/val.las": ("validation", "8/1-3"),
                },
            )
            document = scene.fit()
            nphi = scene.channel(document, "NPHI")
            self.assertEqual(
                nphi["counts"], {"valid": 2, "null": 0, "nonpositive": 0, "absent": 1}
            )
            self.assertAlmostEqual(nphi["mean"], 0.2, places=12)
            self.assertAlmostEqual(nphi["variance"], 0.01, places=12)
            gr = scene.channel(document, "GR")
            self.assertEqual(gr["counts"]["valid"], 3)

    def test_all_missing_channel_blocks_with_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            reduced_curves = [
                ("DEPT", "m"),
                ("FORCE_2020_LITHOFACIES_CONFIDENCE", "_"),
                ("FORCE_2020_LITHOFACIES_LITHOLOGY", "_"),
                ("GR", "gAPI"),
                ("RHOB", "g/cm3"),
                ("RDEP", "ohm.m"),
            ]
            wells = {
                "mini/train.las": {
                    "uwi": "8/2-1",
                    "curves": reduced_curves,
                    "rows": ["0.0 1 30000 10.0 2.0 1.0"],
                },
                "mini/val.las": {"uwi": "8/2-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            scene = _Scene(
                tmp,
                wells,
                {"mini/train.las": ("train", "8/2-1"), "mini/val.las": ("validation", "8/2-2")},
            )
            with self.assertRaises(force_preprocess.ForcePreprocessBlocked) as context:
                scene.fit()
            self.assertIn("NPHI", str(context.exception))
            self.assertIn("no valid training samples", str(context.exception))

    def test_constant_channels_zero_variance_and_effective_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            wells = {
                "mini/train.las": {
                    "uwi": "8/3-1",
                    "rows": [
                        "0.0 1 30000 5.0 2.0 0.1 10.0",
                        "1.0 1 30000 5.0 2.0 0.1 10.0",
                    ],
                },
                "mini/val.las": {"uwi": "8/3-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            scene = _Scene(
                tmp,
                wells,
                {"mini/train.las": ("train", "8/3-1"), "mini/val.las": ("validation", "8/3-2")},
            )
            document = scene.fit()
            for name, expected_mean in (
                ("GR", 5.0),
                ("RHOB", 2.0),
                ("NPHI", 0.1),
                ("RDEP", 1.0),
            ):
                report = scene.channel(document, name)
                self.assertTrue(report["zero_variance"], name)
                self.assertEqual(report["variance"], 0.0)
                self.assertEqual(report["std"], 0.0)
                self.assertEqual(report["effective_scale"], 1.0)
                self.assertAlmostEqual(report["mean"], expected_mean, places=12)

    def test_held_out_members_never_opened_and_cannot_change_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            opened = []
            real_open = zipfile.ZipFile.open

            def tracking_open(self, name, *args, **kwargs):
                opened.append(name if isinstance(name, str) else name.filename)
                return real_open(self, name, *args, **kwargs)

            zipfile.ZipFile.open = tracking_open
            try:
                document = scene.fit()
            finally:
                zipfile.ZipFile.open = real_open
            self.assertEqual(
                opened, ["mini/train_a.las", "mini/train_b.las"], opened
            )
            for held_out in ("mini/val_a.las", "mini/test_a.las"):
                self.assertNotIn(held_out, opened)

            other = Path(tmp) / "other"
            other_wells = dict(_STANDARD_WELLS)
            other_wells["mini/val_a.las"] = {
                "uwi": "3/3-3",
                "rows": ["0.0 1 30000 5e-300 -5e-300 5e-300 5e-300"],
            }
            other_wells["mini/test_a.las"] = {
                "uwi": "4/4-4",
                "rows": ["0.0 3 90000 -1e300 1e300 -1e300 1e300"],
            }
            other_scene = _Scene(other, other_wells, _STANDARD_SPLITS)
            other_document = other_scene.fit()
            self.assertEqual(document["channels"], other_document["channels"])
            self.assertEqual(document["train"], other_document["train"])

    def test_label_and_confidence_values_leave_fitting_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            baseline = scene.fit()

            changed = Path(tmp) / "changed"
            changed_wells = {
                "mini/train_a.las": {
                    "uwi": "1/1-1",
                    "rows": [
                        "0.0 3 90000 10.0 2.0 0.1 1.0",
                        "1.0 3 90000 20.0 2.5 0.2 10.0",
                        "2.0 1 65000 30.0 3.0 0.3 100.0",
                    ],
                },
                "mini/train_b.las": {
                    "uwi": "2/2-2",
                    "rows": [
                        "0.0 3 99000 -50.0 -999.25 0.05 0.5",
                        "1.0 3 99000 -999.25 2.0 0.15 -10.0",
                        "2.0 3 99000 -25.0 2.2 -999.25 0.0",
                    ],
                },
                "mini/val_a.las": dict(_STANDARD_WELLS["mini/val_a.las"]),
                "mini/test_a.las": dict(_STANDARD_WELLS["mini/test_a.las"]),
            }
            scene_changed = _Scene(changed, changed_wells, _STANDARD_SPLITS)
            mutated = scene_changed.fit()
            self.assertEqual(baseline["channels"], mutated["channels"])
            self.assertEqual(baseline["train"], mutated["train"])

            label_document = json.loads(scene_changed.label_path.read_text(encoding="utf-8"))
            label_document["classes"] = [
                {"index": 0, "name": "Shale"},
                {"index": 1, "name": "Chalk"},
            ]
            label_document["confidence_codes"] = {"1": "high", "9": "unused"}
            scene_changed.label_path.write_text(
                json.dumps(label_document), encoding="utf-8"
            )
            scene_changed._rebuild_splits()
            after_label_edit = scene_changed.fit()
            self.assertEqual(baseline["channels"], after_label_edit["channels"])

    def test_fit_order_is_split_row_order_and_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            first = scene.fit()
            second = scene.fit()
            self.assertEqual(first["channels"], second["channels"])
            rows = scene.load_splits()["rows"]
            expected_members = [row["member"] for row in rows if row["split"] == "train"]
            self.assertEqual(
                [entry["member"] for entry in first["fitting_wells"]], expected_members
            )
            self.assertEqual(first["train"], {"wells": 2, "parent_groups": 2, "data_rows": 6})
            self.assertEqual(
                sum(entry["rows"] for entry in first["fitting_wells"]),
                first["train"]["data_rows"],
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit(chunk_bytes=0)
            self.assertIn("chunk_bytes", str(context.exception))

    def test_column_count_malformed_reports_member_and_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(_DEFAULT_CURVES, ["0.0 1 30000 10.0 2.0 0.1"], "1/1-1"),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            message = str(context.exception)
            self.assertIn("member=mini/train_a.las", message)
            self.assertIn("line=18", message)
            self.assertIn("row has 6 values for 7 curves", message)

    def test_non_numeric_and_nonfinite_values_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(_DEFAULT_CURVES, ["0.0 1 30000 abc 2.0 0.1 1.0"], "1/1-1"),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("non-numeric GR 'abc'", str(context.exception))
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(_DEFAULT_CURVES, ["0.0 1 30000 inf 2.0 0.1 1.0"], "1/1-1"),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("non-finite GR 'inf'", str(context.exception))

    def test_duplicate_curve_mnemonic_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    _DEFAULT_CURVES + [("GR", "gAPI")],
                    ["0.0 1 30000 10.0 2.0 0.1 1.0 2.0"],
                    "1/1-1",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("duplicate curve mnemonic", str(context.exception))

    def test_depth_null_and_decreasing_depth_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    _DEFAULT_CURVES,
                    ["-999.25 1 30000 10.0 2.0 0.1 1.0"],
                    "1/1-1",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("NULL depth value", str(context.exception))
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    _DEFAULT_CURVES,
                    [
                        "0.0 1 30000 10.0 2.0 0.1 1.0",
                        "2.0 1 30000 20.0 2.5 0.2 10.0",
                        "1.0 1 30000 30.0 3.0 0.3 100.0",
                    ],
                    "1/1-1",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("depth decreased", str(context.exception))

    def test_unsupported_wrap_and_version_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    _DEFAULT_CURVES,
                    ["0.0 1 30000 10.0 2.0 0.1 1.0"],
                    "1/1-1",
                    wrap="YES",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("unsupported WRAP 'YES'", str(context.exception))
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    _DEFAULT_CURVES,
                    ["0.0 1 30000 10.0 2.0 0.1 1.0"],
                    "1/1-1",
                    vers="1.2",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("unsupported LAS version '1.2'", str(context.exception))

            document = scene.load_inventory()
            for record in document["wells"]:
                if record["member"] == "mini/train_a.las":
                    record["wrap"] = "YES"
            scene.save_inventory(document)
            scene._rebuild_splits()
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("unsupported WRAP 'YES'", str(context.exception))

    def test_unknown_unit_and_varying_units_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            empty_unit_curves = [
                (mnemonic, "" if mnemonic == "GR" else unit)
                for mnemonic, unit in _DEFAULT_CURVES
            ]
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    empty_unit_curves,
                    ["0.0 1 30000 10.0 2.0 0.1 1.0"],
                    "1/1-1",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("unknown (empty) unit for GR", str(context.exception))

            other = Path(tmp) / "other"
            variant_wells = dict(_STANDARD_WELLS)
            variant_curves = [
                (mnemonic, "API" if mnemonic == "GR" else unit)
                for mnemonic, unit in _DEFAULT_CURVES
            ]
            variant_wells["mini/train_b.las"] = dict(_STANDARD_WELLS["mini/train_b.las"])
            variant_wells["mini/train_b.las"]["curves"] = variant_curves
            scene_variant = _Scene(other, variant_wells, _STANDARD_SPLITS)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene_variant.fit()
            self.assertIn("ambiguous units for GR", str(context.exception))

    def test_hash_mismatches_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit(expected_archive_sha256="0" * 64)
            self.assertIn("archive sha256", str(context.exception))
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit(expected_archive_bytes=os.path.getsize(scene.zip_path) + 13)
            self.assertIn("archive byte count", str(context.exception))
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit(expected_inventory_sha256="1" * 64)
            self.assertIn("inventory sha256", str(context.exception))
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit(expected_splits_sha256="2" * 64)
            self.assertIn("splits sha256", str(context.exception))

            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    _DEFAULT_CURVES,
                    [
                        "0.0 1 30000 11.0 2.0 0.1 1.0",
                        "1.0 1 30000 20.0 2.5 0.2 10.0",
                        "2.0 1 30000 30.0 3.0 0.3 100.0",
                    ],
                    "1/1-1",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            message = str(context.exception)
            self.assertIn("mini/train_a.las", message)
            self.assertIn("member sha256", message)

    def test_manifest_cross_reference_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            original = scene.load_splits()
            try:
                for key in (
                    "policy_sha256",
                    "inventory_sha256",
                    "source_archive_sha256",
                    "label_schema_sha256",
                ):
                    document = dict(original)
                    document[key] = "0" * 64
                    scene.save_splits(document)
                    with self.assertRaises(
                        force_preprocess.ForcePreprocessError
                    ) as context:
                        scene.fit()
                    self.assertIn(key + " does not match", str(context.exception))
            finally:
                scene.save_splits(original)

    def test_declared_counts_and_row_loops_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            original = scene.load_splits()
            try:
                document = json.loads(json.dumps(original))
                document["well_counts"]["train"] = 3
                scene.save_splits(document)
                with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                    scene.fit()
                self.assertIn("well_counts[train] = 3 != expected 2", str(context.exception))

                document = json.loads(json.dumps(original))
                document["group_counts"]["train"] = 1
                scene.save_splits(document)
                with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                    scene.fit()
                self.assertIn(
                    "group_counts[train] = 1 != expected 2", str(context.exception)
                )

                document = json.loads(json.dumps(original))
                for row in document["rows"]:
                    if row["member"] == "mini/val_a.las":
                        row["split"] = "train"
                scene.save_splits(document)
                with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                    scene.fit()
                self.assertIn(
                    "splits rows give 3 train wells", str(context.exception)
                )
            finally:
                scene.save_splits(original)

    def test_curve_order_mismatches_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            original_policy = scene.policy_path.read_text(encoding="utf-8")
            policy = json.loads(original_policy)
            policy["preprocessing"]["curve_order"] = ["RHOB", "GR", "NPHI", "RDEP"]
            scene.policy_path.write_text(json.dumps(policy), encoding="utf-8")
            scene._rebuild_splits()
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("policy curve_order", str(context.exception))
            scene.policy_path.write_text(original_policy, encoding="utf-8")
            scene._rebuild_splits()

            label = json.loads(scene.label_path.read_text(encoding="utf-8"))
            label["input_curve_order"] = ["GR", "RHOB", "RDEP", "NPHI"]
            scene.label_path.write_text(json.dumps(label), encoding="utf-8")
            scene._rebuild_splits()
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("label schema input_curve_order", str(context.exception))

    def test_unsafe_member_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            wells = {
                "mini/../evil.las": {
                    "uwi": "9/2-1",
                    "rows": ["0.0 1 30000 10.0 2.0 0.1 1.0"],
                },
                "mini/val.las": {"uwi": "9/2-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            scene = _Scene(
                tmp,
                wells,
                {
                    "mini/../evil.las": ("train", "9/2-1"),
                    "mini/val.las": ("validation", "9/2-2"),
                },
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("unsafe member path", str(context.exception))

    def test_duplicate_zip_member_paths_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            with zipfile.ZipFile(scene.zip_path) as archive:
                members = [
                    (info.filename, archive.read(info.filename))
                    for info in archive.infolist()
                ]
            with zipfile.ZipFile(scene.zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in members:
                    archive.writestr(name, data)
                archive.writestr(members[0][0], members[0][1])
            scene._rebuild_splits()
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("duplicate member paths", str(context.exception))

    def test_malformed_held_out_member_is_never_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            scene.rewrite_member_bytes(
                "mini/val_a.las",
                _las_bytes(_DEFAULT_CURVES, ["0.0 1 30000 broken"], "3/3-3"),
            )
            scene._derive_inventory()
            scene._rebuild_splits()
            baseline = _Scene(Path(tmp) / "baseline", _STANDARD_WELLS, _STANDARD_SPLITS).fit()
            document = scene.fit()
            self.assertEqual(document["channels"], baseline["channels"])

    def test_output_document_provenance_and_no_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            out = Path(tmp) / "written.json"
            document = scene.fit(out=str(out))
            self.assertTrue(out.exists())
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(written["channels"], document["channels"])
            self.assertEqual(document["schema"], 1)
            self.assertEqual(document["kind"], "deepeye-force-preprocess")
            self.assertTrue(document["software_only"])
            self.assertEqual(document["product_card_c01"], "not_run")
            self.assertIn("c01_not_run", document["status"])
            self.assertEqual(document["algorithm"]["name"], "c01-preprocess-welford-v1")
            self.assertEqual(document["algorithm"]["channel_order"], CURVE_ORDER)
            self.assertEqual(document["contract"]["id"], "DEEPEYE-HUMAN-LOCK-20261014")
            self.assertEqual(document["contract"]["revision"], 1)
            self.assertEqual(
                document["inputs"]["archive"]["sha256"], _sha256_file(scene.zip_path)
            )
            self.assertEqual(
                document["inputs"]["inventory"]["sha256"],
                _sha256_file(scene.inventory_path),
            )
            self.assertEqual(
                document["inputs"]["splits"]["sha256"], _sha256_file(scene.splits_path)
            )
            self.assertEqual(
                [report["name"] for report in document["channels"]], CURVE_ORDER
            )
            units = {report["name"]: report["unit"] for report in document["channels"]}
            self.assertEqual(
                units,
                {"GR": "gAPI", "RHOB": "g/cm3", "NPHI": "m3/m3", "RDEP": "ohm.m"},
            )
            self.assertEqual(len(document["fitting_wells"]), 2)
            self.assertEqual(document["train"]["data_rows"], 6)
            self.assertEqual(document["grouping_validation"]["rows"], 4)
            self.assertEqual(document["grouping_validation"]["root_count"], 4)
            self.assertEqual(
                document["grouping_validation"]["split_rows"],
                {"train": 2, "validation": 1, "test": 1},
            )
            self.assertEqual(
                document["inputs"]["helpers"]["grouping"]["sha256"],
                _sha256_file(_MODULE_PATH.parent / "grouping.py"),
            )
            self.assertEqual(
                document["inputs"]["helpers"]["force_inventory"]["sha256"],
                _sha256_file(_MODULE_PATH.parent / "force_inventory.py"),
            )
            self.assertIn("column_parsing", document["algorithm"])
            dumped = json.dumps(document)
            self.assertNotIn("FORCE_2020_LITHOFACIES", dumped)
            self.assertNotIn("Sandstone", dumped)

    def test_unselected_columns_are_never_parsed_numerically(self):
        with tempfile.TemporaryDirectory() as tmp:
            opaque_wells = {
                "mini/train.las": {
                    "uwi": "6/1-1",
                    "rows": [
                        "0.0 unavailable n/a 10.0 2.0 0.1 1.0",
                        "1.0 nan inf 20.0 2.5 0.2 10.0",
                        "2.0 -999.25 30000 30.0 3.0 0.3 100.0",
                    ],
                },
                "mini/val.las": {"uwi": "6/1-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            splits = {
                "mini/train.las": ("train", "6/1-1"),
                "mini/val.las": ("validation", "6/1-2"),
            }
            scene = _Scene(tmp, opaque_wells, splits)
            calls = []
            real_strict = force_preprocess._strict_number

            def spy(token, what, member_name, line_number):
                calls.append(what)
                return real_strict(token, what, member_name, line_number)

            force_preprocess._strict_number = spy
            try:
                document = scene.fit()
            finally:
                force_preprocess._strict_number = real_strict
            gr = scene.channel(document, "GR")
            self.assertEqual(gr["valid_samples"], 3)
            self.assertAlmostEqual(gr["mean"], 20.0, places=12)
            self.assertAlmostEqual(gr["variance"], 200.0 / 3.0, places=12)
            # The instrument records every numeric conversion the parser performs:
            # only the depth column and the four selected channel columns, even
            # though the label/confidence columns hold nonnumeric and nonfinite
            # tokens that any conversion attempt would reject.
            self.assertEqual(set(calls), {"depth", "GR", "RHOB", "NPHI", "RDEP"})
            self.assertEqual(calls.count("depth"), 3)
            self.assertEqual(calls.count("GR"), 3)
            self.assertEqual(len(calls), 15)
            numeric_wells = {
                "mini/train.las": {
                    "uwi": "6/1-1",
                    "rows": [
                        "0.0 1 30000 10.0 2.0 0.1 1.0",
                        "1.0 1 30000 20.0 2.5 0.2 10.0",
                        "2.0 1 30000 30.0 3.0 0.3 100.0",
                    ],
                },
                "mini/val.las": {"uwi": "6/1-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            scene_numeric = _Scene(Path(tmp) / "numeric", numeric_wells, splits)
            self.assertEqual(document["channels"], scene_numeric.fit()["channels"])

    def test_selected_or_depth_opaque_tokens_still_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    _DEFAULT_CURVES,
                    ["0.0 1 30000 label_unavailable 2.0 0.1 1.0"],
                    "1/1-1",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            message = str(context.exception)
            self.assertIn("member=mini/train_a.las", message)
            self.assertIn("non-numeric GR 'label_unavailable'", message)
            scene.rewrite_member_bytes(
                "mini/train_a.las",
                _las_bytes(
                    _DEFAULT_CURVES,
                    ["n/a 1 30000 10.0 2.0 0.1 1.0"],
                    "1/1-1",
                ),
            )
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            message = str(context.exception)
            self.assertIn("member=mini/train_a.las", message)
            self.assertIn("non-numeric depth 'n/a'", message)

    def test_shared_parent_across_splits_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            wells = {
                "mini/root.las": {"uwi": "1/2-3", "rows": ["0.0 1 30000 10.0 2.0 0.1 1.0"]},
                "mini/sidetrack.las": {
                    "uwi": "1/2-3 A",
                    "rows": ["0.0 1 30000 20.0 2.0 0.1 1.0"],
                },
            }
            splits = {
                "mini/root.las": ("train", "1/2-3"),
                "mini/sidetrack.las": ("validation", "1/2-3"),
            }
            scene = _Scene(tmp, wells, splits)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            message = str(context.exception)
            self.assertIn("split grouping rejected", message)
            self.assertIn("cross_split_root", message)

    def test_sidetrack_grouping_preserved_within_one_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            wells = {
                "mini/base.las": {"uwi": "1/2-3", "rows": ["0.0 1 30000 10.0 2.0 0.1 1.0"]},
                "mini/sidetrack.las": {
                    "uwi": "1/2-3 A",
                    "rows": ["0.0 1 30000 20.0 2.0 0.1 1.0"],
                },
                "mini/val.las": {"uwi": "4/4-4", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            splits = {
                "mini/base.las": ("train", "1/2-3"),
                "mini/sidetrack.las": ("train", "1/2-3"),
                "mini/val.las": ("validation", "4/4-4"),
            }
            scene = _Scene(tmp, wells, splits)
            document = scene.fit()
            self.assertEqual(document["train"]["wells"], 2)
            self.assertEqual(document["train"]["parent_groups"], 1)
            self.assertEqual(
                [entry["uwi"] for entry in document["fitting_wells"]],
                ["1/2-3", "1/2-3 A"],
            )

    def test_wrong_well_id_with_matching_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            document = scene.load_splits()
            for row in document["rows"]:
                if row["member"] == "mini/train_a.las":
                    row["well_id"] = "9/9-9"
            scene.save_splits(document)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            message = str(context.exception)
            self.assertIn("member=mini/train_a.las", message)
            self.assertIn("does not match the reviewed inventory UWI", message)

    def test_wrong_root_and_non_force_well_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            document = scene.load_splits()
            for row in document["rows"]:
                if row["member"] == "mini/train_a.las":
                    row["root_id"] = "9/9-9"
            scene.save_splits(document)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("is not the derived parent well", str(context.exception))

            weird = _Scene(Path(tmp) / "weird", _STANDARD_WELLS, _STANDARD_SPLITS)
            inventory = weird.load_inventory()
            for record in inventory["wells"]:
                if record["member"] == "mini/train_a.las":
                    record["uwi"] = "NOT-A-WELL"
            weird.save_inventory(inventory)
            weird._rebuild_splits()
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                weird.fit()
            self.assertIn(
                "does not match the frozen FORCE parent-well rule",
                str(context.exception),
            )

    def test_derivative_rules_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            wells = {
                "mini/parent.las": {"uwi": "1/2-3", "rows": ["0.0 1 30000 10.0 2.0 0.1 1.0"]},
                "mini/child.las": {
                    "uwi": "1/2-4 D1",
                    "rows": ["0.0 1 30000 20.0 2.0 0.1 1.0"],
                },
                "mini/val.las": {"uwi": "4/4-4", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            cross_root = {
                "mini/parent.las": ("train", "1/2-3"),
                "mini/child.las": ("train", "1/2-4", "1/2-3"),
                "mini/val.las": ("validation", "4/4-4"),
            }
            scene = _Scene(Path(tmp) / "cross_root", wells, cross_root)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("derivative_root_mismatch", str(context.exception))

            unknown_parent = dict(cross_root)
            unknown_parent["mini/child.las"] = ("train", "1/2-4", "999/9-9")
            scene = _Scene(Path(tmp) / "unknown", wells, unknown_parent)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("unknown_parent", str(context.exception))

            cycle_wells = {
                "mini/c1.las": {"uwi": "1/2-5 C1", "rows": ["0.0 1 30000 10.0 2.0 0.1 1.0"]},
                "mini/c2.las": {"uwi": "1/2-5 C2", "rows": ["0.0 1 30000 20.0 2.0 0.1 1.0"]},
                "mini/val.las": {"uwi": "4/4-4", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            cycle = {
                "mini/c1.las": ("train", "1/2-5", "1/2-5 C2"),
                "mini/c2.las": ("train", "1/2-5", "1/2-5 C1"),
                "mini/val.las": ("validation", "4/4-4"),
            }
            scene = _Scene(Path(tmp) / "cycle", cycle_wells, cycle)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("derivative_cycle", str(context.exception))

            cross_domain = {
                "mini/parent.las": ("train", "1/2-3"),
                "mini/child.las": {
                    "split": "train",
                    "root": "1/2-4",
                    "derived_from": "1/2-3",
                    "source_domain": "synthetic_other_domain",
                },
                "mini/val.las": ("validation", "4/4-4"),
            }
            scene = _Scene(Path(tmp) / "cross_domain", wells, cross_domain)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("derivative_domain_mismatch", str(context.exception))

    def test_duplicate_identity_and_held_out_sha_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            duplicate_uwi_wells = {
                "mini/a.las": {"uwi": "1/1-9", "rows": ["0.0 1 30000 10.0 2.0 0.1 1.0"]},
                "mini/b.las": {"uwi": "1/1-9", "rows": ["0.0 1 30000 20.0 2.0 0.1 1.0"]},
                "mini/val.las": {"uwi": "4/4-4", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            duplicate_uwi_splits = {
                "mini/a.las": {"split": "train", "root": "1/1-9", "row_id": "row-a"},
                "mini/b.las": {"split": "train", "root": "1/1-9", "row_id": "row-b"},
                "mini/val.las": {"split": "validation", "root": "4/4-4", "row_id": "row-v"},
            }
            scene = _Scene(Path(tmp) / "uwi", duplicate_uwi_wells, duplicate_uwi_splits)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("duplicate inventory UWI", str(context.exception))

            duplicate_row_wells = {
                "mini/a.las": {"uwi": "2/1-1", "rows": ["0.0 1 30000 10.0 2.0 0.1 1.0"]},
                "mini/b.las": {"uwi": "2/1-2", "rows": ["0.0 1 30000 20.0 2.0 0.1 1.0"]},
                "mini/val.las": {"uwi": "4/4-4", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            duplicate_row_splits = {
                "mini/a.las": {"split": "train", "root": "2/1-1", "row_id": "row-dup"},
                "mini/b.las": {"split": "train", "root": "2/1-2", "row_id": "row-dup"},
                "mini/val.las": {"split": "validation", "root": "4/4-4", "row_id": "row-v"},
            }
            scene = _Scene(Path(tmp) / "row", duplicate_row_wells, duplicate_row_splits)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn("duplicate split row_id", str(context.exception))

            scene = _Scene(Path(tmp) / "heldout", _STANDARD_WELLS, _STANDARD_SPLITS)
            document = scene.load_splits()
            for row in document["rows"]:
                if row["split"] == "validation":
                    row["member_sha256"] = "0" * 64
            scene.save_splits(document)
            with self.assertRaises(force_preprocess.ForcePreprocessError) as context:
                scene.fit()
            self.assertIn(
                "split member sha256 does not match the reviewed inventory",
                str(context.exception),
            )

    def test_cli_exit_codes_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = _Scene(tmp, _STANDARD_WELLS, _STANDARD_SPLITS)
            expect = scene.write_expectations(Path(tmp) / "expect.json")

            def _command(target_scene, out_path, expect_path):
                return [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-B",
                    str(_MODULE_PATH),
                    "--zip",
                    str(target_scene.zip_path),
                    "--inventory",
                    str(target_scene.inventory_path),
                    "--splits",
                    str(target_scene.splits_path),
                    "--policy",
                    str(target_scene.policy_path),
                    "--label",
                    str(target_scene.label_path),
                    "--out",
                    str(out_path),
                    "--expectations",
                    str(expect_path),
                ]

            out_ok = Path(tmp) / "ok.json"
            result = subprocess.run(
                _command(scene, out_ok, expect), capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ok train_wells=2", result.stdout)
            self.assertIn("train_rows=6", result.stdout)
            self.assertTrue(out_ok.exists())
            document = json.loads(out_ok.read_text(encoding="utf-8"))
            self.assertEqual(
                [report["name"] for report in document["channels"]], CURVE_ORDER
            )

            bad_expect = scene.write_expectations(
                Path(tmp) / "bad.json", archive_sha256="0" * 64
            )
            out_bad = Path(tmp) / "bad_out.json"
            result_bad = subprocess.run(
                _command(scene, out_bad, bad_expect), capture_output=True, text=True
            )
            self.assertEqual(result_bad.returncode, 1)
            self.assertIn("FAILED: archive sha256", result_bad.stderr)
            self.assertFalse(out_bad.exists())

            reduced_curves = [
                ("DEPT", "m"),
                ("FORCE_2020_LITHOFACIES_CONFIDENCE", "_"),
                ("FORCE_2020_LITHOFACIES_LITHOLOGY", "_"),
                ("GR", "gAPI"),
                ("RHOB", "g/cm3"),
                ("RDEP", "ohm.m"),
            ]
            blocked_wells = {
                "mini/train.las": {
                    "uwi": "9/1-1",
                    "curves": reduced_curves,
                    "rows": ["0.0 1 30000 10.0 2.0 1.0"],
                },
                "mini/val.las": {"uwi": "9/1-2", "rows": ["0.0 1 30000 0.0 0.0 0.0 0.0"]},
            }
            blocked_scene = _Scene(
                Path(tmp) / "blocked",
                blocked_wells,
                {
                    "mini/train.las": ("train", "9/1-1"),
                    "mini/val.las": ("validation", "9/1-2"),
                },
            )
            blocked_expect = blocked_scene.write_expectations(
                Path(tmp) / "blocked.json"
            )
            out_blocked = Path(tmp) / "blocked_out.json"
            result_blocked = subprocess.run(
                _command(blocked_scene, out_blocked, blocked_expect),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result_blocked.returncode, 3)
            self.assertIn("BLOCKED: channel NPHI", result_blocked.stderr)
            self.assertFalse(out_blocked.exists())

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
            names,
            {
                "argparse",
                "datetime",
                "hashlib",
                "importlib",
                "json",
                "math",
                "pathlib",
                "re",
                "sys",
                "zipfile",
                "__future__",
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

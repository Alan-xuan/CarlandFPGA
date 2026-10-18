"""Unit tests for tools/verify_data.py (software-only C01 offline verifier).

Synthetic fixtures here are explicitly labelled ``synthetic_fixture`` and
their pins come from temporary files, so no synthetic run can claim pinned
production provenance.  The real-data tests only read the frozen pinned
artifacts and, when ``DEEPEYE_FORCE_ARCHIVE`` points at the real archive, its
bytes; nothing is rewritten.  This suite is software evidence only: the C01
product card remains not_run and no model, calibration, live-data or
hardware claim is made here.

Portability: the suite never references a private controller file or a
``.local`` tree.  Pure tests (synthetic, metadata, error, output) run from
an ordinary checkout; the integration cases that need the real archive skip
with a counted reason when ``DEEPEYE_FORCE_ARCHIVE`` is unset, and the C
evidence run sets it and requires zero skips.

Coverage: real pinned force-offline success (exit 0,
passed_offline_identity_consistency_only, C01 not_run) and default full
scope blocked (exit 2 with the missing archive prerequisite reported
truthfully); missing file blocked versus wrong hash failed; a missing pin
never masks an observed corruption (both listed, exit 1); a file replaced
between the pin pass and the parse is detected and never parsed as verified
data; wrong or missing archive; cross-file link, contract, schema/domain,
duplicate/omitted well and parent cross-split/misrank failures; held-out or
duplicate fitting wells; training-row and statistics metadata mismatches;
derivative rows that inherit their root group (accepted by the pinned
grouping validator) versus derivative rows crossing roots or splits
(rejected); malformed documents that never surface as tracebacks; the CLI
from a non-product working directory with atomic output (identical
stdout/file bytes, no residue); refusal to write ``--output`` over a pinned
input, the verifier entrypoint or a samefile alias while a legitimate
report beside the pins still works; immutable spec containers and rejection
of a forged production-labelled spec without touching any pinned byte; zero
ZIP member opens and zero LAS parsing (zipfile is poisoned while the real
byte-stream hash still succeeds, and a fresh import does not even load
zipfile); and that the production constants equal independently written
literals from the main-approved decision pins.
"""

import builtins
import copy
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from tools.verify_data import (  # noqa: E402
    ARCHIVE_BASENAME,
    ARCHIVE_BYTES,
    ARCHIVE_SHA256,
    CONTRACT_ID,
    CONTRACT_REQUIREMENTS_SHA256,
    CONTRACT_REVISION,
    CONTRACT_SOURCE_COMMIT,
    DESIGN_COMMIT,
    MISSING_FULL_GATES,
    PARENT_RULE_EXPECTED,
    PINNED_ARTIFACTS,
    PRODUCTION_SPEC,
    TASK_ID,
    TASK_VERSION,
    VerificationSpec,
    VerifyDataError,
    extract_parent_rule,
    load_pinned_helper_module,
    rank_split_assignments,
    run_verification,
    sha256_file_stream,
    verify_pins,
    write_text_atomic,
)

from tools import verify_data as verify_data_module  # noqa: E402

CLI_PATH = PRODUCT_ROOT / "tools/verify_data.py"
PYTHON = sys.executable

# Integration-only tests read the real archive location from this explicit
# test-only environment variable.  Without it those cases skip with a
# clearly counted reason and never claim that real data ran.  No private
# controller file or .local tree is referenced anywhere in this suite.
REAL_ARCHIVE_ENV = "DEEPEYE_FORCE_ARCHIVE"
_ARCHIVE_ENV_VALUE = os.environ.get(REAL_ARCHIVE_ENV)
REAL_ARCHIVE = Path(_ARCHIVE_ENV_VALUE) if _ARCHIVE_ENV_VALUE else None

# Independently written literal expectations transcribed from the
# main-approved verify-data-main-decisions.json pins plus the accepted-gate
# status update.  They are duplicated from the module constants on purpose:
# the constants test fails if either side drifts.
EXPECTED_PINS = {
    "data/source_inventory.json": "7800fda1b4f712d5e93a05d14b6a0726eb5699f979db065dea61eb9a7f84337c",
    "data/force_wells.json": "ace9a0eb9930f19c6b8125e151d07346fb23029b1455eac04964d15b97461e59",
    "data/splits.json": "f10ddb8f37e6bdf7c9663eed45d0f6554ef8992899724013a7e487ad3e3cef91",
    "data/split_policy.json": "66c5138ad45138104bca20d39c4680daa82534a16e381f8d2879eea6f37b81c9",
    "data/label_schema.json": "0913ff5a59085b47802a9902f23a836f4fa1129700de8e6593840416f4d7beed",
    "data/preprocessing.json": "cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef",
    "data/force_inventory.py": "86404425615f7551ce04907c9dbd6d7a40edca76372ad82a1a9655092a186932",
    "data/grouping.py": "f1a35a5b060cafb640d8f65b2914af9616258b7fa21f99d1a589d232f7b2be4d",
    "data/force_preprocess.py": "1cc71d045065495d99a3f79c31107705cdc3a4942409a8decf6ae732501bc308",
    "data/provenance/force_2020_v1/force_inventory.py": "5bba8316ea36484df058dacb2289073ffb09ce19e401dfb297598b3e3cd10f47",
    "data/provenance/force_2020_v1/force_preprocess.py": "75b2015c0ec9deab9a94a2032b77117124085631f2bd758a54c7ea7fdfdf2848",
}
EXPECTED_ARCHIVE_BASENAME = (
    "LAS_files_Force_2020_all_wells_train_test_blind_hidden_final.zip"
)
EXPECTED_ARCHIVE_BYTES = 169785172
EXPECTED_ARCHIVE_SHA256 = (
    "042ef1d473100dc12768cae7107a8cead071a394f137af3bc1ddaf8a5d1b8dda"
)
EXPECTED_FULL_GATES = (
    "R03 public resource/profile/observation schema acceptance",
    "sensor_live whole acquisition-run manifest",
    "sim_em_v2 whole-scenario and derivative splits",
    "runtime future-label/truth-access instrumentation",
)
# Documented expectation for the clean-checkout run without
# DEEPEYE_FORCE_ARCHIVE: exactly the three real-archive integration cases
# skip; every pure test still runs and passes.
EXPECTED_CLEAN_CHECKOUT_SKIPS = 3

CHANNEL_ORDER = ("GR", "RHOB", "NPHI", "RDEP")
CHANNEL_TRANSFORMS = {
    "GR": "identity-v1",
    "RHOB": "identity-v1",
    "NPHI": "identity-v1",
    "RDEP": "log10-positive-v1",
}
SYNTHETIC_DOMAIN = "synthetic_fixture_domain"


def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def run_cli(arguments, cwd, *, cli_path=CLI_PATH):
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [PYTHON, "-X", "utf8", "-B", str(cli_path), *arguments],
        cwd=str(cwd),
        capture_output=True,
        env=environment,
    )


def parse_stdout(proc):
    return json.loads(proc.stdout.decode("utf-8"))


class SyntheticFixture:
    """Small, self-consistent, explicitly synthetic artifact family.

    The pins recorded in the spec are the actual SHA256 values of the files
    written into the temporary root, so the fixture is self-consistent but
    can never be confused with the pinned production artifacts.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        (self.root / "data").mkdir(parents=True, exist_ok=True)
        self.archive_rel = "synthetic_archive.zip"
        self.archive_bytes = (
            b"SYNTHETIC-FORCE-FIXTURE-ARCHIVE-" + bytes(range(256)) * 4
        )
        self.salt = "SYNTHETIC-FIXTURE-SALT-20261015"
        self.fractions = {"train": 0.70, "validation": 0.15, "test": 0.15}
        self.doi = "10.0000/synthetic-fixture"
        self.repository_commit = "0" * 40
        self.license_id = "synthetic-license"
        self.original_license_text = "SYNTHETIC 1.0"
        roots = [
            "10/1-1",
            "10/1-2",
            "10/1-3",
            "10/2-1",
            "10/2-2",
            "10/3-1",
            "10/3-2",
            "10/4-1",
            "10/4-2",
            "10/5-1",
        ]
        self.roots = roots
        self.wells = []
        for index, root in enumerate(roots):
            if root == "10/1-3":
                well_ids = ["10/1-3 A", "10/1-3 S"]
            else:
                well_ids = [root]
            for suffix_index, well_id in enumerate(well_ids):
                rows = 120 + 7 * index + 3 * suffix_index
                self.wells.append(
                    {
                        "member": "SYNTH_FORCE_fixture/"
                        + well_id.replace("/", "_")
                        + ".las",
                        "uwi": well_id,
                        "root": root,
                        "rows": rows,
                        "member_sha256": sha256_hex("synthetic member " + well_id),
                    }
                )
        draft = types.SimpleNamespace(salt=self.salt, fractions=self.fractions)
        predicted = rank_split_assignments(self.roots, draft)
        self.well_split = {
            well["uwi"]: predicted[well["root"]] for well in self.wells
        }
        self.group_counts = {name: 0 for name in ("train", "validation", "test")}
        for root in self.roots:
            self.group_counts[predicted[root]] += 1
        self.well_counts = {name: 0 for name in ("train", "validation", "test")}
        for split in self.well_split.values():
            self.well_counts[split] += 1
        self.train_wells = [
            well for well in self.wells if self.well_split[well["uwi"]] == "train"
        ]
        self.train_rows = sum(well["rows"] for well in self.train_wells)
        self.train_roots = {
            well["root"] for well in self.train_wells
        }
        self.rows_total = sum(well["rows"] for well in self.wells)
        self.curves_total = 2 * len(self.wells)
        self.archive_sha = sha256_hex(self.archive_bytes)
        self.pins = {}
        self.docs = {}
        self._write_helpers()
        self._write_all_documents()
        self._refresh_pins()

    # -- file writers -----------------------------------------------------

    def _write_helpers(self) -> None:
        (self.root / "data" / "force_inventory.py").write_text(
            "# synthetic fixture helper (not the reviewed inventory module)\n"
            "FIXTURE = 'synthetic-force-inventory'\n",
            encoding="utf-8",
        )
        (self.root / "data" / "force_preprocess.py").write_text(
            "# synthetic fixture helper (not the reviewed preprocessing module)\n"
            "FIXTURE = 'synthetic-force-preprocess'\n",
            encoding="utf-8",
        )
        grouping_bytes = (PRODUCT_ROOT / "data" / "grouping.py").read_bytes()
        (self.root / "data" / "grouping.py").write_bytes(grouping_bytes)

    def _write_document(self, name: str, document: dict) -> None:
        path = self.root / "data" / (name + ".json")
        path.write_text(
            json.dumps(document, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.docs[name] = document

    def _read_document_sha(self, name: str) -> str:
        return sha256_hex((self.root / "data" / (name + ".json")).read_bytes())

    def _write_all_documents(self) -> None:
        (self.root / self.archive_rel).write_bytes(self.archive_bytes)
        self._write_document("force_wells", self._build_force_wells())
        self._write_document("label_schema", self._build_label_schema())
        sha_wells = self._read_document_sha("force_wells")
        self._write_document("split_policy", self._build_split_policy())
        sha_policy = self._read_document_sha("split_policy")
        sha_label = self._read_document_sha("label_schema")
        self._write_document(
            "splits", self._build_splits(sha_wells, sha_policy, sha_label)
        )
        sha_splits = self._read_document_sha("splits")
        self._write_document(
            "source_inventory", self._build_source_inventory(sha_wells, sha_splits)
        )
        sha_force_inventory = sha256_hex(
            (self.root / "data" / "force_inventory.py").read_bytes()
        )
        sha_grouping = sha256_hex((self.root / "data" / "grouping.py").read_bytes())
        self._write_document(
            "preprocessing",
            self._build_preprocessing(
                sha_wells,
                sha_splits,
                sha_policy,
                sha_label,
                sha_force_inventory,
                sha_grouping,
            ),
        )

    def _refresh_pins(self) -> None:
        self.pins = {
            "data/source_inventory.json": self._read_document_sha("source_inventory"),
            "data/force_wells.json": self._read_document_sha("force_wells"),
            "data/splits.json": self._read_document_sha("splits"),
            "data/split_policy.json": self._read_document_sha("split_policy"),
            "data/label_schema.json": self._read_document_sha("label_schema"),
            "data/preprocessing.json": self._read_document_sha("preprocessing"),
            "data/force_inventory.py": sha256_hex(
                (self.root / "data" / "force_inventory.py").read_bytes()
            ),
            "data/grouping.py": sha256_hex(
                (self.root / "data" / "grouping.py").read_bytes()
            ),
            "data/force_preprocess.py": sha256_hex(
                (self.root / "data" / "force_preprocess.py").read_bytes()
            ),
        }

    def spec(self) -> VerificationSpec:
        return VerificationSpec(
            name="synthetic",
            pins=dict(self.pins),
            archive=(self.archive_rel, len(self.archive_bytes), self.archive_sha),
            members=len(self.wells),
            rows_total=self.rows_total,
            curves_total=self.curves_total,
            roots=len(self.roots),
            group_counts=dict(self.group_counts),
            well_counts=dict(self.well_counts),
            train_wells=len(self.train_wells),
            train_parent_groups=len(self.train_roots),
            train_data_rows=self.train_rows,
            channel_order=CHANNEL_ORDER,
            channel_transforms=dict(CHANNEL_TRANSFORMS),
            domain=SYNTHETIC_DOMAIN,
            curve_input_shape=(1, 8, 128, 1),
            summary_input_shape=(1, 13, 32, 1),
            target_curve="SYNTHETIC_LITHOLOGY",
            confidence_curve="SYNTHETIC_CONFIDENCE",
            label_class_count=12,
            confidence_codes=("1", "2", "3"),
            salt=self.salt,
            fractions=dict(self.fractions),
            license_id=self.license_id,
            original_license_text=self.original_license_text,
            doi=self.doi,
            repository_commit=self.repository_commit,
            record_url="https://example.invalid/synthetic",
            repository_url="https://example.invalid/synthetic-repo",
            dataset_label="synthetic fixture dataset",
        )

    def mutate(self, document_name: str, mutator) -> dict:
        """Deep-copy a document, mutate it, rewrite the file and re-pin it."""

        document = copy.deepcopy(self.docs[document_name])
        mutator(document)
        self._write_document(document_name, document)
        self._refresh_pins()
        return document

    # -- document builders ------------------------------------------------

    def _contract(self) -> dict:
        return {
            "id": CONTRACT_ID,
            "revision": CONTRACT_REVISION,
            "source_commit": CONTRACT_SOURCE_COMMIT,
            "requirements_sha256": CONTRACT_REQUIREMENTS_SHA256,
        }

    def _build_force_wells(self) -> dict:
        wells = []
        for index, well in enumerate(self.wells):
            rows = well["rows"]
            null_count = 1 + index % 3
            wells.append(
                {
                    "member": well["member"],
                    "member_size_bytes": 900 + rows,
                    "member_sha256": well["member_sha256"],
                    "crc_verified": True,
                    "rows": rows,
                    "wrap": "NO",
                    "uwi": well["uwi"],
                    "well": well["uwi"],
                    "depth": {
                        "mnemonic": "DEPT",
                        "unit": "m",
                        "count": rows,
                        "null_count": 0,
                        "min": 1.0,
                        "max": float(rows),
                        "monotonic_nondecreasing": True,
                    },
                    "curves": [
                        {
                            "mnemonic": "DEPT",
                            "unit": "m",
                            "count": rows,
                            "null_count": 0,
                            "nonmissing_count": rows,
                        },
                        {
                            "mnemonic": "GR",
                            "unit": "gAPI",
                            "count": rows,
                            "null_count": null_count,
                            "nonmissing_count": rows - null_count,
                        },
                    ],
                }
            )
        return {
            "schema": 1,
            "kind": "synthetic-fixture-inventory",
            "fixture": "synthetic",
            "generated_utc": "2026-10-15T00:00:00Z",
            "provenance": {
                "dataset": "synthetic fixture (not real FORCE data)",
                "doi": self.doi,
                "record_url": "https://example.invalid/synthetic",
                "authors_repository": "https://example.invalid/synthetic-repo",
                "authors_repository_commit": self.repository_commit,
                "archive_file": self.archive_rel,
                "archive_bytes": len(self.archive_bytes),
                "archive_sha256": self.archive_sha,
                "archive_md5": hashlib.md5(self.archive_bytes).hexdigest(),
                "notes": "Synthetic fixture; never presented as pinned "
                "production provenance.",
            },
            "summary": {
                "members": len(self.wells),
                "rows_total": self.rows_total,
                "curves_total": self.curves_total,
                "duplicate_uwi": 0,
                "all_wrap_no": True,
            },
            "wells": wells,
        }

    def _build_label_schema(self) -> dict:
        return {
            "schema": 1,
            "task_id": TASK_ID,
            "task_version": TASK_VERSION,
            "contract": self._contract(),
            "design_commit": DESIGN_COMMIT,
            "scope": "synthetic fixture label schema",
            "source": {
                "repository": "https://example.invalid/synthetic-repo",
                "commit": self.repository_commit,
                "path": "synthetic",
            },
            "target_curve": "SYNTHETIC_LITHOLOGY",
            "classes": [
                {"index": index, "source_code": 100000 + index, "name": "Class{}".format(index)}
                for index in range(12)
            ],
            "confidence_curve": "SYNTHETIC_CONFIDENCE",
            "confidence_codes": {"1": "high", "2": "medium", "3": "low"},
            "input_curve_order": list(CHANNEL_ORDER),
            "curve_input_shape": [1, 8, 128, 1],
            "summary_input_shape": [1, 13, 32, 1],
            "status": "synthetic_fixture",
        }

    def _build_split_policy(self) -> dict:
        return {
            "schema": 1,
            "task_id": TASK_ID,
            "task_version": TASK_VERSION,
            "contract": self._contract(),
            "status": "synthetic_fixture",
            "source_archive_sha256": self.archive_sha,
            "grouping": {
                "primary_identity": "synthetic fixture UWI",
                "parent_well_rule": "match full UWI with "
                + PARENT_RULE_EXPECTED
                + " and use capture1; synthetic fixture",
                "unknown_identity": "fail",
                "source_domains": "synthetic fixture domains stay separate",
            },
            "assignment": {
                "salt": self.salt,
                "algorithm": "sort by SHA256(UTF8(salt + newline + parent)); "
                "floor fractions",
                "fraction_targets": dict(self.fractions),
                "outcome_independence": "fixed salt and identities only",
                "resplit_policy": "no reroll",
            },
            "preprocessing": {
                "fit_domain": "synthetic fixture training wells only",
                "curve_order": list(CHANNEL_ORDER),
            },
            "acceptance": "synthetic fixture",
        }

    def _build_splits(self, sha_wells, sha_policy, sha_label) -> dict:
        rows = []
        for well in self.wells:
            rows.append(
                {
                    "row_id": well["uwi"],
                    "source_domain": SYNTHETIC_DOMAIN,
                    "root_id": well["root"],
                    "well_id": well["uwi"],
                    "member": well["member"],
                    "member_sha256": well["member_sha256"],
                    "split": self.well_split[well["uwi"]],
                    "derived_from": None,
                }
            )
        return {
            "schema": 1,
            "task_id": TASK_ID,
            "task_version": TASK_VERSION,
            "contract": self._contract(),
            "design_commit": DESIGN_COMMIT,
            "source_archive_sha256": self.archive_sha,
            "inventory_sha256": sha_wells,
            "policy_sha256": sha_policy,
            "label_schema_sha256": sha_label,
            "group_counts": dict(self.group_counts),
            "well_counts": dict(self.well_counts),
            "rows": rows,
            "status": "synthetic_fixture",
        }

    def _build_source_inventory(self, sha_wells, sha_splits) -> dict:
        return {
            "schema": 1,
            "purpose": "synthetic fixture source pinning",
            "task_id": TASK_ID,
            "task_version": TASK_VERSION,
            "design_commit": DESIGN_COMMIT,
            "contract": self._contract(),
            "source_record": {
                "url": "https://example.invalid/synthetic",
                "doi": self.doi,
                "publication_date": "2026-10-15",
                "version": "fixture",
                "metadata_sha256": "0" * 64,
                "license_id_from_record": self.license_id,
                "original_data_license_text": self.original_license_text,
            },
            "authors_repository": {
                "url": "https://example.invalid/synthetic-repo",
                "commit": self.repository_commit,
            },
            "selected_file": {
                "name": self.archive_rel,
                "expected_bytes": len(self.archive_bytes),
                "local_sha256": self.archive_sha,
                "actual_bytes": len(self.archive_bytes),
            },
            "data_domain": "synthetic_fixture",
            "source_mode": "geo_replay",
            "grouping_unit": "complete_well",
            "complete_well_inventory": {
                "status": "fixture",
                "file": "force_wells.json",
                "sha256": sha_wells,
                "members": len(self.wells),
                "rows": self.rows_total,
            },
            "split_manifest": {
                "file": "splits.json",
                "sha256": sha_splits,
                "group_counts": dict(self.group_counts),
                "well_counts": dict(self.well_counts),
            },
        }

    def _build_preprocessing(
        self, sha_wells, sha_splits, sha_policy, sha_label, sha_force_inventory, sha_grouping
    ) -> dict:
        channels = []
        for index, name in enumerate(CHANNEL_ORDER):
            channels.append(
                {
                    "name": name,
                    "unit": "synthetic",
                    "transform_version": CHANNEL_TRANSFORMS[name],
                    "counts": {
                        "valid": self.train_rows,
                        "null": 0,
                        "nonpositive": 0,
                        "absent": 0,
                    },
                    "valid_samples": self.train_rows,
                    "mean": 1.0 + index,
                    "variance": 4.0,
                    "std": 2.0,
                    "zero_variance": False,
                    "effective_scale": 2.0,
                }
            )
        fitting_wells = [
            {
                "member": well["member"],
                "member_sha256": well["member_sha256"],
                "uwi": well["uwi"],
                "well": well["uwi"],
                "rows": well["rows"],
                "crc_verified": True,
            }
            for well in self.train_wells
        ]
        validation = {
            "validator": "data/grouping.py:validate_split_assignments",
            "rows": len(self.wells),
            "root_count": len(self.roots),
            "split_rows": dict(self.well_counts),
            "domains": {
                SYNTHETIC_DOMAIN: {
                    "rows": len(self.wells),
                    "roots": len(self.roots),
                    "derivatives": 0,
                    "split_rows": dict(self.well_counts),
                }
            },
        }
        contract = self._contract()
        contract = dict(contract, design_commit=DESIGN_COMMIT)
        return {
            "schema": 1,
            "kind": "synthetic-fixture-preprocessing",
            "task_id": TASK_ID,
            "task_version": TASK_VERSION,
            "contract": contract,
            "status": "synthetic_fixture",
            "algorithm": {"name": "synthetic-fixture", "channel_order": list(CHANNEL_ORDER)},
            "inputs": {
                "archive": {
                    "path": "synthetic",
                    "bytes": len(self.archive_bytes),
                    "sha256": self.archive_sha,
                },
                "inventory": {"path": "data/force_wells.json", "sha256": sha_wells},
                "splits": {"path": "data/splits.json", "sha256": sha_splits},
                "policy": {"path": "data/split_policy.json", "sha256": sha_policy},
                "label_schema": {
                    "path": "data/label_schema.json",
                    "sha256": sha_label,
                },
                "helpers": {
                    "force_inventory": {
                        "path": "data/force_inventory.py",
                        "sha256": sha_force_inventory,
                    },
                    "grouping": {
                        "path": "data/grouping.py",
                        "sha256": sha_grouping,
                    },
                },
            },
            "channels": channels,
            "train": {
                "wells": len(self.train_wells),
                "parent_groups": len(self.train_roots),
                "data_rows": self.train_rows,
            },
            "grouping_validation": validation,
            "fitting_wells": fitting_wells,
            "software_only": True,
            "product_card_c01": "not_run",
            "limits": ["synthetic fixture"],
        }


class FixtureTestCase(unittest.TestCase):
    """Base class: one synthetic fixture tree per test with auto cleanup."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="verify_data_fixture_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fixture = SyntheticFixture(self.root)
        self.archive_path = self.root / self.fixture.archive_rel

    def run_scope(self, scope="force-offline", archive_path=None, spec=None):
        return run_verification(
            self.root,
            self.fixture.spec() if spec is None else spec,
            scope=scope,
            archive_path=self.archive_path if archive_path is None else archive_path,
            python_version="fixture",
        )

    def check_entry(self, report, check_id):
        for entry in report["checks"]:
            if entry["id"] == check_id:
                return entry
        self.fail("missing check entry {}".format(check_id))

    def assert_failed(self, report, exit_code):
        self.assertEqual(report["status"], "failed")
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["product_card_C01"], "not_run")
        failed = [
            entry["id"] for entry in report["checks"] if entry["status"] == "failed"
        ]
        self.assertTrue(failed, "expected at least one failed check")
        return failed


class RealPinnedDataTests(unittest.TestCase):
    """Read-only runs against the frozen pins; nothing here is rewritten."""

    @unittest.skipUnless(
        REAL_ARCHIVE is not None,
        "set DEEPEYE_FORCE_ARCHIVE to the pinned FORCE-2020 archive",
    )
    def test_real_force_offline_passes_without_claiming_c01(self):
        self.assertTrue(
            REAL_ARCHIVE.is_absolute(), "DEEPEYE_FORCE_ARCHIVE must be absolute"
        )
        self.assertTrue(REAL_ARCHIVE.is_file(), "pinned archive must exist")
        proc = run_cli(
            ["--scope", "force-offline", "--archive", str(REAL_ARCHIVE)],
            PRODUCT_ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        report = parse_stdout(proc)
        self.assertEqual(report["status"], "passed_offline_identity_consistency_only")
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["product_card_C01"], "not_run")
        self.assertEqual(report["spec"], "production")
        statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
        self.assertEqual(
            {key: value for key, value in statuses.items() if value in ("failed", "blocked")},
            {},
        )
        self.assertEqual(statuses["full_c01_prerequisite_gates"], "not_run")
        self.assertEqual(statuses["runtime_future_label_access"], "not_run")
        counts = report["counts"]
        self.assertEqual(counts["inventory_members"], 118)
        self.assertEqual(counts["well_rows_total"], 2337639)
        self.assertEqual(counts["curves_total"], 2393)
        self.assertEqual(counts["parent_roots"], 117)
        self.assertEqual(counts["group_counts"], {"train": 81, "validation": 17, "test": 19})
        self.assertEqual(counts["well_counts"], {"train": 82, "validation": 17, "test": 19})
        self.assertEqual(counts["train_rows"], 1634292)
        self.assertEqual(counts["fitting_wells"], 82)
        self.assertEqual(counts["fitting_rows"], 1634292)
        self.assertEqual(report["archive"]["status"], "verified")
        self.assertEqual(report["archive"]["actual_bytes"], 169785172)
        self.assertEqual(report["archive"]["actual_sha256"], ARCHIVE_SHA256)
        self.assertEqual(report["missing_full_gates"], list(MISSING_FULL_GATES))
        provenance = report["provenance"]
        self.assertEqual(provenance["doi"], "10.5281/zenodo.4351156")
        self.assertEqual(provenance["record_url"], "https://zenodo.org/records/4351156")
        self.assertEqual(
            provenance["authors_repository_commit"],
            "c8d01ee92c1c8e1ecba36f96cca6ea7b689338a1",
        )
        self.assertEqual(provenance["record_license_id"], "cc-by-4.0")
        self.assertEqual(provenance["original_description_license_text"], "NOLD 2.0")
        self.assertEqual(provenance["archive_file"], ARCHIVE_BASENAME)
        self.assertEqual(provenance["archive_sha256"], ARCHIVE_SHA256)
        self.assertFalse(provenance["raw_archive_in_product_repository"])
        self.assertEqual(len(report["artifacts"]), 11)
        self.assertTrue(
            all(item["status"] == "verified" for item in report["artifacts"])
        )
        self.assertNotIn("passed_full", report["status"])
        self.assertNotEqual(report["status"], "passed")

    def test_real_default_full_scope_is_blocked_exit_2(self):
        proc = run_cli([], PRODUCT_ROOT)
        self.assertEqual(proc.returncode, 2, proc.stderr.decode("utf-8", "replace"))
        report = parse_stdout(proc)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["product_card_C01"], "not_run")
        statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
        self.assertEqual(statuses["full_c01_prerequisite_gates"], "blocked")
        offline_ids = (
            "pinned_artifact_hashes",
            "contract_task_design_identity",
            "cross_file_hash_links",
            "inventory_structure",
            "split_structure_and_coverage",
            "whole_well_grouping",
            "rank_split_reconstruction",
            "label_schema_alignment",
            "preprocessing_fit_identity",
            "preprocessing_statistics_metadata",
        )
        for check_id in offline_ids:
            self.assertEqual(statuses[check_id], "passed", check_id)
        # The default full scope must not invent an archive location: without
        # an explicit --archive the report states the missing prerequisite
        # truthfully (blocked) instead of guessing a repository path.
        self.assertEqual(statuses["archive_bytes_and_sha256"], "blocked")
        self.assertEqual(report["archive"]["status"], "no_path")
        self.assertIsNone(report["command"]["archive_file"])

    @unittest.skipUnless(
        REAL_ARCHIVE is not None,
        "set DEEPEYE_FORCE_ARCHIVE to the pinned FORCE-2020 archive",
    )
    def test_real_cli_from_non_product_cwd_with_atomic_output(self):
        with tempfile.TemporaryDirectory(prefix="verify_data_cwd_") as cwd_dir:
            output = Path(cwd_dir) / "report.json"
            proc = run_cli(
                [
                    "--scope",
                    "force-offline",
                    "--archive",
                    str(REAL_ARCHIVE),
                    "--output",
                    str(output),
                ],
                cwd_dir,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes(), proc.stdout)
            report = parse_stdout(proc)
            statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
            self.assertEqual(statuses["output_write"], "passed")
            self.assertEqual(report["command"]["output"], "report.json")
            self.assertEqual(report["command"]["archive_file"], ARCHIVE_BASENAME)
            leftovers = sorted(
                item.name for item in Path(cwd_dir).iterdir() if item.name != "report.json"
            )
            self.assertEqual(leftovers, [])

    def test_real_missing_archive_blocked_and_wrong_archive_failed(self):
        with tempfile.TemporaryDirectory(prefix="verify_data_missing_") as cwd_dir:
            missing = Path(cwd_dir) / "missing.zip"
            proc = run_cli(
                ["--scope", "force-offline", "--archive", str(missing)], PRODUCT_ROOT
            )
            self.assertEqual(proc.returncode, 2)
            report = parse_stdout(proc)
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["exit_code"], 2)
            self.assertEqual(report["archive"]["status"], "missing")
        wrong = PRODUCT_ROOT / "data" / "label_schema.json"
        proc = run_cli(
            ["--scope", "force-offline", "--archive", str(wrong)], PRODUCT_ROOT
        )
        self.assertEqual(proc.returncode, 1)
        report = parse_stdout(proc)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["archive"]["status"], "mismatch")
        self.assertEqual(report["product_card_C01"], "not_run")

    def test_real_cli_usage_errors_are_deterministic(self):
        cases = (
            ["--archive", "somewhere.zip"],
            ["--archive", "somewhere.zip", "--scope", "full_c01"],
            ["--scope", "bogus"],
        )
        for arguments in cases:
            proc = run_cli(arguments, PRODUCT_ROOT)
            self.assertEqual(proc.returncode, 2, arguments)
            report = parse_stdout(proc)
            self.assertEqual(report["status"], "usage_error", arguments)
            self.assertEqual(report["exit_code"], 2)
            self.assertEqual(report["product_card_C01"], "not_run")

    def test_force_offline_without_archive_is_blocked_not_usage_error(self):
        proc = run_cli(["--scope", "force-offline"], PRODUCT_ROOT)
        self.assertEqual(proc.returncode, 2, proc.stderr.decode("utf-8", "replace"))
        report = parse_stdout(proc)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["product_card_C01"], "not_run")
        statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
        self.assertEqual(statuses["archive_bytes_and_sha256"], "blocked")
        self.assertEqual(report["archive"]["status"], "no_path")
        self.assertIsNone(report["command"]["archive_file"])

    @unittest.skipUnless(
        REAL_ARCHIVE is not None,
        "set DEEPEYE_FORCE_ARCHIVE to the pinned FORCE-2020 archive",
    )
    def test_real_inprocess_run_with_zipfile_spy(self):
        class ForbiddenZipFile:
            def __init__(self, *args, **kwargs):
                raise AssertionError("the verifier must not open a ZIP member")

        saved = zipfile.ZipFile
        zipfile.ZipFile = ForbiddenZipFile
        try:
            report, exit_code = run_verification(
                PRODUCT_ROOT,
                PRODUCTION_SPEC,
                scope="force-offline",
                archive_path=REAL_ARCHIVE,
                python_version="fixture",
            )
        finally:
            zipfile.ZipFile = saved
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "passed_offline_identity_consistency_only")
        self.assertEqual(report["archive"]["actual_sha256"], ARCHIVE_SHA256)
        self.assertEqual(report["software_facts"]["zip_members_opened"], 0)
        self.assertEqual(report["software_facts"]["las_values_parsed"], 0)
        self.assertFalse(report["software_facts"]["statistics_recomputed"])

    def test_fresh_import_does_not_load_zipfile_module(self):
        code = (
            "import sys; sys.path.insert(0, r'{root}'); "
            "import tools.verify_data; "
            "print('zipfile' in sys.modules)"
        ).format(root=str(PRODUCT_ROOT))
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [PYTHON, "-X", "utf8", "-B", "-c", code],
            cwd=str(PRODUCT_ROOT),
            capture_output=True,
            env=environment,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stdout.decode("utf-8").strip(), "False")

    def test_production_constants_match_main_decisions(self):
        # Independent literals only: no private controller file is read here,
        # so an ordinary checkout can reproduce this identity check.
        self.assertEqual(dict(PRODUCTION_SPEC.pins), dict(EXPECTED_PINS))
        self.assertEqual(set(PINNED_ARTIFACTS), set(EXPECTED_PINS))
        self.assertEqual(ARCHIVE_BASENAME, EXPECTED_ARCHIVE_BASENAME)
        self.assertEqual(ARCHIVE_BYTES, EXPECTED_ARCHIVE_BYTES)
        self.assertEqual(ARCHIVE_SHA256, EXPECTED_ARCHIVE_SHA256)
        self.assertEqual(PRODUCTION_SPEC.archive[0], EXPECTED_ARCHIVE_BASENAME)
        self.assertEqual(PRODUCTION_SPEC.archive[1], EXPECTED_ARCHIVE_BYTES)
        self.assertEqual(PRODUCTION_SPEC.archive[2], EXPECTED_ARCHIVE_SHA256)
        self.assertEqual(list(MISSING_FULL_GATES), list(EXPECTED_FULL_GATES))
        self.assertEqual(CONTRACT_ID, "DEEPEYE-HUMAN-LOCK-20261014")
        self.assertEqual(CONTRACT_REVISION, 1)
        self.assertEqual(CONTRACT_SOURCE_COMMIT, "f5989cd5defce561f9ba98e6b18fc2682945f0a2")
        self.assertEqual(
            CONTRACT_REQUIREMENTS_SHA256,
            "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
        )
        self.assertEqual(TASK_ID, "DEEPEYE-IMPLEMENTATION-20261014")
        self.assertEqual(TASK_VERSION, 1)
        self.assertEqual(DESIGN_COMMIT, "1011259415a0916054eb580687612580bc1e5f09")
        self.assertEqual(len(PINNED_ARTIFACTS), 11)
        self.assertEqual(PRODUCTION_SPEC.name, "production")
        self.assertEqual(PRODUCTION_SPEC.members, 118)
        self.assertEqual(PRODUCTION_SPEC.rows_total, 2337639)
        self.assertEqual(PRODUCTION_SPEC.roots, 117)
        self.assertEqual(PRODUCTION_SPEC.train_data_rows, 1634292)
        self.assertEqual(
            verify_data_module.classify_spec(PRODUCTION_SPEC), "production"
        )
        self.assertEqual(
            extract_parent_rule(
                "match full UWI with "
                + PARENT_RULE_EXPECTED
                + " and use capture1; sidetracks/suffix variants stay together"
            ),
            PARENT_RULE_EXPECTED,
        )


class SyntheticOfflineTests(FixtureTestCase):
    """Synthetic fixtures: pass/fail/blocked mechanics and validator edges."""

    def test_positive_force_offline_passes_with_synthetic_label(self):
        report, exit_code = self.run_scope()
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "synthetic_fixture_checks_passed")
        self.assertEqual(report["spec"], "synthetic_fixture")
        self.assertEqual(report["requested_spec_name"], "synthetic")
        self.assertFalse(report["production_provenance"])
        self.assertEqual(report["product_card_C01"], "not_run")
        failed = [e["id"] for e in report["checks"] if e["status"] == "failed"]
        self.assertEqual(failed, [])
        self.assertTrue(all(item["status"] == "verified" for item in report["artifacts"]))
        counts = report["counts"]
        self.assertEqual(counts["inventory_members"], len(self.fixture.wells))
        self.assertEqual(counts["parent_roots"], len(self.fixture.roots))
        self.assertEqual(counts["train_rows"], self.fixture.train_rows)
        self.assertEqual(counts["fitting_wells"], len(self.fixture.train_wells))

    def test_full_scope_with_synthetic_fixture_is_still_blocked(self):
        report, exit_code = self.run_scope(scope="full_c01")
        self.assertEqual(exit_code, 2)
        self.assertEqual(report["status"], "blocked")
        statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
        self.assertEqual(statuses["full_c01_prerequisite_gates"], "blocked")
        self.assertEqual(statuses["whole_well_grouping"], "passed")

    def test_missing_pinned_file_blocks(self):
        (self.root / "data" / "force_preprocess.py").unlink()
        report, exit_code = self.run_scope()
        self.assertEqual(exit_code, 2)
        self.assertEqual(report["status"], "blocked")
        entry = self.check_entry(report, "pinned_artifact_hashes")
        self.assertEqual(entry["status"], "blocked")
        self.assertIn("force_preprocess.py", entry["detail"])

    def test_wrong_pin_hash_fails(self):
        path = self.root / "data" / "force_inventory.py"
        path.write_bytes(path.read_bytes() + b"# tampered\n")
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("pinned_artifact_hashes", failed)

    def test_archive_missing_blocks(self):
        report, exit_code = self.run_scope(
            archive_path=self.root / "missing_archive.zip"
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["archive"]["status"], "missing")

    def test_archive_tampered_bytes_fail(self):
        path = self.root / self.fixture.archive_rel
        data = bytearray(path.read_bytes())
        data[-1] ^= 0x01
        path.write_bytes(bytes(data))
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("archive_bytes_and_sha256", failed)
        self.assertEqual(report["archive"]["status"], "mismatch")

    def test_archive_size_change_fails(self):
        path = self.root / self.fixture.archive_rel
        path.write_bytes(path.read_bytes() + b"SIZE")
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("archive_bytes_and_sha256", failed)

    def test_contract_identity_tamper_fails(self):
        self.fixture.mutate(
            "splits", lambda document: document.__setitem__("design_commit", "deadbeef")
        )
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("contract_task_design_identity", failed)

    def test_cross_file_link_tamper_fails(self):
        self.fixture.mutate(
            "splits",
            lambda document: document.__setitem__("inventory_sha256", "0" * 64),
        )
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("cross_file_hash_links", failed)

    def test_inventory_duplicate_uwi_fails(self):
        def mutate(document):
            document["wells"][1]["uwi"] = document["wells"][0]["uwi"]

        self.fixture.mutate("force_wells", mutate)
        report, exit_code = self.run_scope()
        self.assert_failed(report, exit_code)
        entry = self.check_entry(report, "inventory_structure")
        self.assertEqual(entry["status"], "failed")
        self.assertIn("duplicate inventory UWIs", entry["detail"])

    def test_split_omitted_well_fails(self):
        self.fixture.mutate(
            "splits", lambda document: document.__setitem__("rows", document["rows"][:-1])
        )
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("split_structure_and_coverage", failed)

    def test_split_duplicate_row_fails(self):
        def mutate(document):
            document["rows"].append(copy.deepcopy(document["rows"][0]))

        self.fixture.mutate("splits", mutate)
        report, exit_code = self.run_scope()
        self.assert_failed(report, exit_code)
        entry = self.check_entry(report, "split_structure_and_coverage")
        self.assertIn("duplicate row_id", entry["detail"])

    def test_parent_group_crossing_splits_fails(self):
        def mutate(document):
            for row in document["rows"]:
                if row["well_id"] == "10/1-3 S":
                    row["split"] = (
                        "validation" if row["split"] != "validation" else "test"
                    )

        self.fixture.mutate("splits", mutate)
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("whole_well_grouping", failed)
        entry = self.check_entry(report, "whole_well_grouping")
        self.assertIn("cross_split_root", entry["detail"])

    def test_parent_group_misranked_fails(self):
        def mutate(document):
            single_rows = {}
            for row in document["rows"]:
                single_rows.setdefault(row["root_id"], []).append(row)
            candidates = [
                (root, rows[0]["split"])
                for root, rows in single_rows.items()
                if len(rows) == 1
            ]
            first_root, first_split = candidates[0]
            second_root, second_split = None, None
            for root, split in candidates[1:]:
                if split != first_split:
                    second_root, second_split = root, split
                    break
            self.assertIsNotNone(second_root, "fixture needs two single-well roots")
            for row in document["rows"]:
                if row["root_id"] == first_root:
                    row["split"] = second_split
                elif row["root_id"] == second_root:
                    row["split"] = first_split

        self.fixture.mutate("splits", mutate)
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("rank_split_reconstruction", failed)
        entry = self.check_entry(report, "rank_split_reconstruction")
        self.assertIn("rank reconstruction mismatch", entry["detail"])

    def test_held_out_fitting_member_fails(self):
        validation_row = next(
            row
            for row in self.fixture.docs["splits"]["rows"]
            if row["split"] == "validation"
        )
        replacement_rows = next(
            well["rows"]
            for well in self.fixture.wells
            if well["uwi"] == validation_row["well_id"]
        )

        def mutate(document):
            entry = document["fitting_wells"][0]
            entry["member"] = validation_row["member"]
            entry["member_sha256"] = validation_row["member_sha256"]
            entry["uwi"] = validation_row["well_id"]
            entry["well"] = validation_row["well_id"]
            entry["rows"] = replacement_rows

        self.fixture.mutate("preprocessing", mutate)
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("preprocessing_fit_identity", failed)

    def test_duplicate_fitting_member_fails(self):
        def mutate(document):
            document["fitting_wells"][1] = copy.deepcopy(document["fitting_wells"][0])

        self.fixture.mutate("preprocessing", mutate)
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("preprocessing_fit_identity", failed)

    def test_training_rows_mismatch_fails(self):
        def mutate(document):
            document["train"]["data_rows"] += 1

        self.fixture.mutate("preprocessing", mutate)
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("preprocessing_fit_identity", failed)

    def test_invalid_statistics_fail(self):
        def negative_variance(document):
            document["channels"][0]["variance"] = -1.0

        self.fixture.mutate("preprocessing", negative_variance)
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("preprocessing_statistics_metadata", failed)
        with tempfile.TemporaryDirectory(prefix="verify_data_fixture2_") as another:
            fixture = SyntheticFixture(Path(another))

            def zero_variance_scale(document):
                document["channels"][2]["zero_variance"] = True
                document["channels"][2]["effective_scale"] = 0.5

            fixture.mutate("preprocessing", zero_variance_scale)
            second_report, second_exit = run_verification(
                Path(another),
                fixture.spec(),
                scope="force-offline",
                archive_path=Path(another) / fixture.archive_rel,
                python_version="fixture",
            )
            self.assert_failed(second_report, second_exit)
            self.assertIn(
                "preprocessing_statistics_metadata",
                [e["id"] for e in second_report["checks"] if e["status"] == "failed"],
            )

    def test_split_domain_confusion_fails(self):
        self.fixture.mutate(
            "splits",
            lambda document: document["rows"][0].__setitem__(
                "source_domain", "sim_em_v2"
            ),
        )
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("split_structure_and_coverage", failed)

    def test_label_curve_order_confusion_fails(self):
        self.fixture.mutate(
            "label_schema",
            lambda document: document.__setitem__(
                "input_curve_order", list(reversed(document["input_curve_order"]))
            ),
        )
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("cross_file_hash_links", failed)

    def test_malformed_document_is_deterministic_failed(self):
        path = self.root / "data" / "splits.json"
        path.write_text("{not json", encoding="utf-8")
        self.fixture._refresh_pins()
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("pinned_documents_parse", failed)
        self.assertIn(
            "not valid UTF-8 JSON",
            self.check_entry(report, "pinned_documents_parse")["detail"],
        )

    def test_top_level_list_document_is_deterministic_failed(self):
        path = self.root / "data" / "force_wells.json"
        path.write_text("[]\n", encoding="utf-8")
        self.fixture._refresh_pins()
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("pinned_documents_parse", failed)

    def test_split_row_type_confusion_is_deterministic_failed(self):
        def mutate(document):
            document["rows"][0] = "not-a-row"

        self.fixture.mutate("splits", mutate)
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("split_structure_and_coverage", failed)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["product_card_C01"], "not_run")

    def test_derivative_rows_inherit_root_groups(self):
        grouping_module = load_pinned_helper_module(
            PRODUCT_ROOT, PRODUCTION_SPEC, "data/grouping.py", "_deepeye_test_grouping"
        )
        rows = copy.deepcopy(self.fixture.docs["splits"]["rows"])
        base = rows[0]
        derivative = dict(
            base, row_id=base["row_id"] + " aug", derived_from=base["row_id"]
        )
        report = grouping_module.validate_split_assignments(rows + [derivative])
        self.assertEqual(report.rows, len(rows) + 1)
        self.assertEqual(report.root_count, len(self.fixture.roots))
        domain = report.domains[SYNTHETIC_DOMAIN]
        self.assertEqual(domain.derivatives, 1)
        crossing = dict(
            derivative,
            split="validation" if derivative["split"] != "validation" else "test",
        )
        with self.assertRaises(grouping_module.SplitAssignmentError):
            grouping_module.validate_split_assignments(rows + [crossing])
        orphan = dict(derivative, derived_from="missing-row")
        with self.assertRaises(grouping_module.SplitAssignmentError):
            grouping_module.validate_split_assignments(rows + [orphan])

    def test_derivative_row_rejected_by_pinned_split_table_check(self):
        def mutate(document):
            base = document["rows"][0]
            derivative = dict(
                base, row_id=base["row_id"] + " aug", derived_from=base["row_id"]
            )
            document["rows"].append(derivative)

        self.fixture.mutate("splits", mutate)
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("split_structure_and_coverage", failed)
        self.assertIn(
            "derived_from",
            self.check_entry(report, "split_structure_and_coverage")["detail"],
        )

    def test_grouping_helper_hash_gate(self):
        spec = self.fixture.spec()
        tampered = dict(spec.pins)
        tampered["data/grouping.py"] = "0" * 64
        bad_spec = dataclasses.replace(spec, pins=tampered)
        with self.assertRaises(VerifyDataError) as context:
            load_pinned_helper_module(
                self.root, bad_spec, "data/grouping.py", "_deepeye_test_bad"
            )
        self.assertEqual(context.exception.status, "failed")
        self.assertIn("hash mismatch", context.exception.detail)

    def test_open_spy_sees_no_las_or_zip_member_reads(self):
        recorded = []
        real_open = builtins.open

        def spy(file, mode="r", *args, **kwargs):
            recorded.append(str(os.fspath(file)))
            return real_open(file, mode, *args, **kwargs)

        builtins.open = spy
        try:
            report, exit_code = self.run_scope()
        finally:
            builtins.open = real_open
        self.assertEqual(exit_code, 0)
        allowed = {str(self.archive_path)}
        for relative in self.fixture.pins:
            allowed.add(str(self.root / relative))
        self.assertTrue(recorded)
        for path in recorded:
            self.assertIn(path, allowed, path)
            self.assertFalse(path.endswith(".las"), path)
        self.assertFalse(any(".zip/" in path or ".zip\\" in path for path in recorded))
        self.assertEqual(report["software_facts"]["zip_members_opened"], 0)
        self.assertEqual(report["software_facts"]["las_values_parsed"], 0)

    def test_replacement_between_pin_pass_and_parse_is_detected(self):
        target = self.root / "data" / "preprocessing.json"
        spec = self.fixture.spec()
        pinned_sha = spec.pins["data/preprocessing.json"]
        consumed = []
        original_verify_pins = verify_data_module.verify_pins
        original_statistics = verify_data_module.check_preprocessing_statistics

        def racing_verify_pins(product_root, patch_spec):
            records = original_verify_pins(product_root, patch_spec)
            document = json.loads(target.read_bytes())
            document["channels"][0]["mean"] += 100
            target.write_text(json.dumps(document), encoding="utf-8")
            return records

        def observing_statistics(document, patch_spec):
            consumed.append(document["channels"][0]["mean"])
            return original_statistics(document, patch_spec)

        with (
            mock.patch.object(verify_data_module, "verify_pins", racing_verify_pins),
            mock.patch.object(
                verify_data_module,
                "check_preprocessing_statistics",
                observing_statistics,
            ),
        ):
            report, exit_code = run_verification(
                self.root,
                spec,
                scope="force-offline",
                archive_path=self.archive_path,
                python_version="fixture",
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["status"], "failed")
        entry = self.check_entry(report, "pinned_documents_parse")
        self.assertEqual(entry["status"], "failed")
        self.assertIn("not parsed", entry["detail"])
        self.assertIn("data/preprocessing.json", entry["detail"])
        self.assertNotEqual(report["status"], "passed_offline_identity_consistency_only")
        # The changed bytes were never handed to a consumer and never match
        # the pinned digest: no report claims they were verified.
        self.assertEqual(consumed, [])
        self.assertNotEqual(sha256_hex(target.read_bytes()), pinned_sha)

    def test_missing_pin_does_not_mask_observed_corruption(self):
        (self.root / "data" / "force_inventory.py").rename(
            self.root / "data" / "force_inventory.absent"
        )
        (self.root / "data" / "source_inventory.json").write_bytes(
            b"corrupt available input"
        )
        report, exit_code = self.run_scope()
        failed = self.assert_failed(report, exit_code)
        self.assertIn("pinned_artifact_hashes", failed)
        entry = self.check_entry(report, "pinned_artifact_hashes")
        self.assertEqual(entry["status"], "failed")
        self.assertIn("hash mismatch", entry["detail"])
        self.assertIn("data/source_inventory.json", entry["detail"])
        self.assertIn("also missing", entry["detail"])
        self.assertIn("data/force_inventory.py", entry["detail"])
        self.assertEqual(report["product_card_C01"], "not_run")

    def test_production_relabelled_spec_is_rejected_without_any_read(self):
        forged = dataclasses.replace(self.fixture.spec(), name="production")
        calls = []

        def forbidden(*args, **kwargs):
            calls.append(args)
            raise AssertionError("a forged production spec must not read pinned data")

        with (
            mock.patch.object(verify_data_module, "verify_pins", forbidden),
            mock.patch.object(verify_data_module, "load_json_document", forbidden),
            mock.patch.object(
                verify_data_module, "load_pinned_helper_module", forbidden
            ),
            mock.patch.object(verify_data_module, "check_archive_identity", forbidden),
        ):
            report, exit_code = self.run_scope(spec=forged)
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["spec"], "rejected_forged_production")
        self.assertEqual(report["requested_spec_name"], "production")
        self.assertFalse(report["production_provenance"])
        self.assertEqual(report["artifacts"], [])
        statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
        self.assertEqual(statuses["spec_context"], "failed")
        self.assertEqual(calls, [])
        forged_counts = dataclasses.replace(PRODUCTION_SPEC, members=999)
        report_two, exit_two = self.run_scope(spec=forged_counts)
        self.assertEqual(exit_two, 1)
        self.assertEqual(report_two["spec"], "rejected_forged_production")
        self.assertFalse(report_two["production_provenance"])

    def test_spec_containers_are_immutable_ingress_copies(self):
        caller_pins = dict(PRODUCTION_SPEC.pins)
        clone = dataclasses.replace(PRODUCTION_SPEC, pins=caller_pins)
        self.assertEqual(clone, PRODUCTION_SPEC)
        caller_pins["data/preprocessing.json"] = "0" * 64
        self.assertEqual(
            clone.pins["data/preprocessing.json"],
            EXPECTED_PINS["data/preprocessing.json"],
        )
        self.assertEqual(clone, PRODUCTION_SPEC)
        caller_counts = {"train": 999}
        counts_clone = dataclasses.replace(PRODUCTION_SPEC, group_counts=caller_counts)
        self.assertEqual(dict(counts_clone.group_counts), {"train": 999})
        caller_counts["train"] = 1
        self.assertEqual(dict(counts_clone.group_counts), {"train": 999})
        self.assertNotEqual(counts_clone, PRODUCTION_SPEC)
        caller_order = list(PRODUCTION_SPEC.channel_order)
        order_clone = dataclasses.replace(PRODUCTION_SPEC, channel_order=caller_order)
        caller_order.append("EVIL")
        self.assertEqual(order_clone.channel_order, ("GR", "RHOB", "NPHI", "RDEP"))
        with self.assertRaises(TypeError):
            PRODUCTION_SPEC.pins["data/preprocessing.json"] = "0" * 64
        with self.assertRaises(TypeError):
            PINNED_ARTIFACTS["data/preprocessing.json"] = "0" * 64
        self.assertEqual(verify_data_module.classify_spec(PRODUCTION_SPEC), "production")
        self.assertEqual(verify_data_module.classify_spec(clone), "production")


class OutputAtomicityTests(unittest.TestCase):
    """Atomic output behavior at the helper and CLI level."""

    def test_write_text_atomic_roundtrip_and_no_residue(self):
        with tempfile.TemporaryDirectory(prefix="verify_data_atomic_") as directory:
            target = Path(directory) / "report.json"
            write_text_atomic(target, "{\"a\": 1}\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "{\"a\": 1}\n")
            self.assertEqual(
                sorted(item.name for item in Path(directory).iterdir()),
                ["report.json"],
            )
            write_text_atomic(target, "{\"a\": 2}\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "{\"a\": 2}\n")
            self.assertEqual(
                sorted(item.name for item in Path(directory).iterdir()),
                ["report.json"],
            )

    def test_write_text_atomic_failure_leaves_nothing(self):
        with tempfile.TemporaryDirectory(prefix="verify_data_atomic_") as directory:
            target = Path(directory) / "missing" / "report.json"
            with self.assertRaises(OSError):
                write_text_atomic(target, "{}\n")
            self.assertFalse(target.exists())
            self.assertEqual(sorted(item.name for item in Path(directory).iterdir()), [])

    def test_cli_output_into_missing_directory_fails_exit_1(self):
        with tempfile.TemporaryDirectory(prefix="verify_data_out_") as directory:
            target = Path(directory) / "missing" / "report.json"
            proc = run_cli(
                [
                    "--scope",
                    "force-offline",
                    "--output",
                    str(target),
                ],
                PRODUCT_ROOT,
            )
            self.assertEqual(proc.returncode, 1, proc.stderr.decode("utf-8", "replace"))
            report = parse_stdout(proc)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["exit_code"], 1)
            statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
            self.assertEqual(statuses["output_write"], "failed")
            self.assertEqual(report["product_card_C01"], "not_run")
            self.assertFalse(target.exists())
            self.assertEqual(sorted(item.name for item in Path(directory).iterdir()), [])


class HistoricalGeneratorPinTests(FixtureTestCase):
    """Historical generation and current code are independently pinned roles."""

    HISTORICAL_INVENTORY = "data/provenance/force_2020_v1/force_inventory.py"
    HISTORICAL_PREPROCESS = "data/provenance/force_2020_v1/force_preprocess.py"

    def historical_fixture(self):
        historical = {}
        for relative in (self.HISTORICAL_INVENTORY, self.HISTORICAL_PREPROCESS):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            # A pin-only verifier must never execute this deliberately raising
            # synthetic snapshot, even when every digest is valid.
            path.write_bytes(("raise AssertionError('historical snapshot executed: "
                              + path.name + "')\n").encode("ascii"))
            historical[relative] = sha256_hex(path.read_bytes())
        self.fixture.mutate(
            "preprocessing",
            lambda doc: doc["inputs"]["helpers"]["force_inventory"].__setitem__(
                "sha256", historical[self.HISTORICAL_INVENTORY]),
        )
        self.fixture.pins.update(historical)
        return historical

    def test_historical_helper_matches_old_snapshot_not_current_code(self):
        historical = self.historical_fixture()
        self.assertNotEqual(historical[self.HISTORICAL_INVENTORY],
                            self.fixture.pins["data/force_inventory.py"])
        report, code = self.run_scope()
        self.assertEqual(code, 0)
        self.assertFalse(report["production_provenance"])
        self.assertEqual(self.check_entry(report, "cross_file_hash_links")["status"], "passed")
        self.assertEqual(len(report["artifacts"]), 11)

    def test_current_hash_cannot_relabel_historical_preprocessing(self):
        historical = self.historical_fixture()
        self.fixture.mutate(
            "preprocessing",
            lambda doc: doc["inputs"]["helpers"]["force_inventory"].__setitem__(
                "sha256", self.fixture.pins["data/force_inventory.py"]),
        )
        self.fixture.pins.update(historical)
        report, code = self.run_scope()
        self.assertIn("cross_file_hash_links", self.assert_failed(report, code))

    def test_missing_historical_snapshot_blocks_without_live_fallback(self):
        self.historical_fixture()
        for relative in (self.HISTORICAL_INVENTORY, self.HISTORICAL_PREPROCESS):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.unlink()
                report, code = self.run_scope()
                self.assertEqual(code, 2)
                self.assertEqual(self.check_entry(report, "pinned_artifact_hashes")["status"], "blocked")
                path.write_bytes(original)

    def test_corrupted_snapshot_fails_without_live_fallback(self):
        self.historical_fixture()
        for relative in (self.HISTORICAL_INVENTORY, self.HISTORICAL_PREPROCESS):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.write_bytes(original + b"# corruption\n")
                report, code = self.run_scope()
                self.assertIn("pinned_artifact_hashes", self.assert_failed(report, code))
                path.write_bytes(original)

    def test_live_helper_corruption_is_not_hidden_by_valid_history(self):
        self.historical_fixture()
        for relative in ("data/force_inventory.py", "data/force_preprocess.py"):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.write_bytes(original + b"# corruption\n")
                report, code = self.run_scope()
                self.assertIn("pinned_artifact_hashes", self.assert_failed(report, code))
                path.write_bytes(original)

    def test_missing_history_does_not_hide_corrupt_live_helper(self):
        self.historical_fixture()
        (self.root / self.HISTORICAL_INVENTORY).unlink()
        path = self.root / "data/force_inventory.py"
        path.write_bytes(path.read_bytes() + b"# corruption\n")
        report, code = self.run_scope()
        self.assertIn("pinned_artifact_hashes", self.assert_failed(report, code))
        self.assertIn("also missing", self.check_entry(report, "pinned_artifact_hashes")["detail"])

    def test_only_grouping_executes_and_no_zip_member_is_opened(self):
        self.historical_fixture()
        imported = []
        original_loader = verify_data_module.load_pinned_helper_module

        def allowed_loader(root, spec, relative, name):
            imported.append(relative)
            self.assertEqual(relative, "data/grouping.py")
            return original_loader(root, spec, relative, name)

        with mock.patch.object(verify_data_module, "load_pinned_helper_module", allowed_loader):
            report, code = self.run_scope()
        self.assertEqual(code, 0)
        self.assertEqual(imported, ["data/grouping.py"])
        self.assertEqual(report["software_facts"]["zip_members_opened"], 0)
        self.assertEqual(report["software_facts"]["las_values_parsed"], 0)
        self.assertFalse(report["software_facts"]["statistics_recomputed"])

    def test_production_cannot_drop_historical_pins_to_use_synthetic_fallback(self):
        pins = dict(PRODUCTION_SPEC.pins)
        for relative in (self.HISTORICAL_INVENTORY, self.HISTORICAL_PREPROCESS):
            pins.pop(relative, None)
        forged = dataclasses.replace(PRODUCTION_SPEC, pins=pins)
        with mock.patch.object(verify_data_module, "verify_pins",
                               side_effect=AssertionError("forged context read pins")):
            report, code = self.run_scope(spec=forged)
        self.assertEqual(code, 1)
        self.assertEqual(report["spec"], "rejected_forged_production")
        self.assertEqual(report["artifacts"], [])


class CliOutputProtectionTests(unittest.TestCase):
    """--output must never replace a verifier input (VD04)."""

    def test_output_rejects_pinned_input_and_parent_alias(self):
        target = PRODUCT_ROOT / "data" / "preprocessing.json"
        before = sha256_hex(target.read_bytes())
        aliases = (
            str(target),
            str(PRODUCT_ROOT / "data" / ".." / "data" / "preprocessing.json"),
        )
        for alias in aliases:
            proc = run_cli(
                ["--scope", "force-offline", "--output", alias], PRODUCT_ROOT
            )
            self.assertEqual(proc.returncode, 1, alias)
            report = parse_stdout(proc)
            self.assertEqual(report["status"], "failed", alias)
            self.assertEqual(report["exit_code"], 1, alias)
            statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
            self.assertEqual(statuses["output_write"], "failed", alias)
            self.assertIn("refusing to write", report["error"], alias)
            self.assertEqual(report["product_card_C01"], "not_run", alias)
        self.assertEqual(sha256_hex(target.read_bytes()), before)

    def test_output_rejects_verifier_entrypoint(self):
        before = sha256_hex(CLI_PATH.read_bytes())
        proc = run_cli(
            ["--scope", "force-offline", "--output", str(CLI_PATH)], PRODUCT_ROOT
        )
        self.assertEqual(proc.returncode, 1)
        report = parse_stdout(proc)
        self.assertEqual(report["status"], "failed")
        statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
        self.assertEqual(statuses["output_write"], "failed")
        self.assertIn("refusing to write", report["error"])
        self.assertIn("verifier entrypoint", report["error"])
        self.assertEqual(sha256_hex(CLI_PATH.read_bytes()), before)

    def test_output_rejects_hardlink_alias_of_pinned_input(self):
        original = PRODUCT_ROOT / "data" / "preprocessing.json"
        before = sha256_hex(original.read_bytes())
        with tempfile.TemporaryDirectory(prefix="verify_data_alias_") as directory:
            # A copied minimal product tree keeps the source and alias on
            # one temporary volume even if the checkout lives elsewhere.
            product_root = Path(directory) / "product"
            target = product_root / "data" / "preprocessing.json"
            entrypoint = product_root / "tools" / "verify_data.py"
            target.parent.mkdir(parents=True)
            entrypoint.parent.mkdir(parents=True)
            shutil.copyfile(original, target)
            shutil.copyfile(CLI_PATH, entrypoint)
            alias = product_root / "alias.json"
            os.link(target, alias)
            self.assertTrue(os.path.samefile(target, alias))
            proc = run_cli(
                ["--scope", "force-offline", "--output", str(alias)],
                product_root,
                cli_path=entrypoint,
            )
            self.assertEqual(proc.returncode, 1)
            report = parse_stdout(proc)
            statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
            self.assertEqual(statuses["output_write"], "failed")
            self.assertIn("same underlying file", report["error"])
            self.assertEqual(sha256_hex(alias.read_bytes()), before)
            self.assertEqual(sha256_hex(target.read_bytes()), before)
            self.assertNotIn(
                "deepeye-verify-data-report", alias.read_text(encoding="utf-8")
            )
        self.assertEqual(sha256_hex(original.read_bytes()), before)

    def test_output_allows_legitimate_report_path(self):
        with tempfile.TemporaryDirectory(prefix="verify_data_output_") as directory:
            output = Path(directory) / "report.json"
            proc = run_cli(
                ["--scope", "force-offline", "--output", str(output)], PRODUCT_ROOT
            )
            # Without an explicit --archive this scope reports its missing
            # prerequisite truthfully (blocked, exit 2); the write itself is
            # still a legitimate, un-protected path.
            self.assertEqual(proc.returncode, 2, proc.stderr.decode("utf-8", "replace"))
            report = parse_stdout(proc)
            self.assertEqual(report["status"], "blocked")
            statuses = {entry["id"]: entry["status"] for entry in report["checks"]}
            self.assertEqual(statuses["output_write"], "passed")
            self.assertEqual(output.read_bytes(), proc.stdout)

    def test_output_protects_historical_snapshots_and_hardlink_aliases(self):
        for filename in ("force_inventory.py", "force_preprocess.py"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory(prefix="verify_history_alias_") as directory:
                product_root = Path(directory) / "product"
                target = product_root / "data" / "provenance" / "force_2020_v1" / filename
                entrypoint = product_root / "tools" / "verify_data.py"
                target.parent.mkdir(parents=True)
                entrypoint.parent.mkdir(parents=True)
                original = b"# synthetic historical snapshot; never execute\n"
                target.write_bytes(original)
                shutil.copyfile(CLI_PATH, entrypoint)
                alias = product_root / "history_alias.py"
                os.link(target, alias)
                self.assertTrue(os.path.samefile(target, alias))
                for output in (target, alias):
                    proc = run_cli(["--scope", "force-offline", "--output", str(output)],
                                   product_root, cli_path=entrypoint)
                    self.assertEqual(proc.returncode, 1)
                    report = parse_stdout(proc)
                    outcomes = {item["id"]: item["status"] for item in report["checks"]}
                    self.assertEqual(outcomes["output_write"], "failed")
                    self.assertIn("refusing to write", report["error"])
                    self.assertEqual(target.read_bytes(), original)
                    self.assertEqual(alias.read_bytes(), original)


class SkipContractTests(unittest.TestCase):
    """The clean-checkout skip contract stays explicit and counted."""

    def test_env_gated_skip_contract(self):
        module = sys.modules[__name__]
        reason = (
            "set DEEPEYE_FORCE_ARCHIVE to the pinned"
            + " FORCE-2020 archive"
        )
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count(reason), EXPECTED_CLEAN_CHECKOUT_SKIPS)
        real = module.RealPinnedDataTests
        decorated = [
            name
            for name, member in vars(real).items()
            if callable(member) and getattr(member, "__unittest_skip__", False)
        ]
        expected_names = {
            "test_real_force_offline_passes_without_claiming_c01",
            "test_real_cli_from_non_product_cwd_with_atomic_output",
            "test_real_inprocess_run_with_zipfile_spy",
        }
        self.assertTrue(expected_names <= set(vars(real)))
        if module.REAL_ARCHIVE is None:
            self.assertEqual(len(decorated), EXPECTED_CLEAN_CHECKOUT_SKIPS)
            self.assertTrue(expected_names <= set(decorated))
        else:
            self.assertEqual(decorated, [])
        others = []
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, unittest.TestCase)
                and value is not real
            ):
                for name, member in vars(value).items():
                    if callable(member) and getattr(member, "__unittest_skip__", False):
                        others.append("{}.{}".format(value.__name__, name))
        self.assertEqual(others, [])


if __name__ == "__main__":
    unittest.main()

"""C01 offline data verifier: provenance and identity/consistency checks.

Software-only foundation for the C01 "causal data and model input" card
(DEEPEYE-HUMAN-LOCK-20261014 revision 1, design commit
1011259415a0916054eb580687612580bc1e5f09).  It verifies the frozen offline
FORCE-2020 artifact family that C already produced without touching,
re-fitting, re-splitting or re-parsing it:

* SHA256 and byte pins for six frozen JSON documents, three current helper
  modules and two historical generator snapshots;
* contract / task / design identity fields wherever defined;
* cross-file hash links between the documents;
* inventory structure (member / UWI / member SHA256 uniqueness, counts)
  from the previously reviewed pinned inventory;
* split-table structure and exact one-to-one coverage of the frozen well
  set (118 wells for the production pins);
* whole-well parent grouping through the pinned ``data/grouping.py``
  validator (imported only after its SHA256 was checked) plus an
  independent reconstruction of the salt-ranked parent assignment from the
  pinned split policy;
* preprocessing fit identity (fitting wells == the train wells, in pinned
  split row order; rows sum 1634292 for the production pins) and
  documented statistics metadata consistency (finite values, std/variance
  agreement, explicit zero-variance effective_scale rule).  The numeric
  fit is NOT recomputed here;
* raw archive byte length and stream SHA256 for the pinned 169785172-byte
  ZIP.  No ZIP member is opened and no LAS value is parsed by this tool;
  the archive is read only as a byte stream.

Scope and acceptance boundaries (all product and hardware cards remain
not_run):

* ``python tools/verify_data.py`` defaults to the full C01 scope and is
  blocked (exit 2) because the required R03 / sensor_live / sim_em_v2 /
  runtime-secrecy / curve-main gates are unavailable.  It never reports a
  full pass.
* ``python tools/verify_data.py --scope force-offline --archive ABS_ZIP
  [--output OUT.json]`` runs the partial offline check only and may exit 0
  with ``status=passed_offline_identity_consistency_only`` and
  ``product_card_C01=not_run``.
* Invalid or corrupt available input is a failure (exit 1); missing
  prerequisites are blocked (exit 2).  When a missing prerequisite and an
  observed corruption coexist, the report is failed (exit 1) and lists
  both, never a silent block.
* Every pinned document is hash-checked on the exact byte buffer that is
  decoded and parsed, so a file swapped in after the pin pass is detected
  and never parsed as verified data.
* ``--output`` is refused (exit 1) when it resolves to any input this run
  reads: one of the pinned artifacts, the selected archive or this
  entrypoint (including symlink/junction/hardlink aliases).
* Only the canonical ``PRODUCTION_SPEC`` carries the production label.  A
  nonproduction spec is reported as ``synthetic_fixture`` with
  ``production_provenance=false``; a forged production-labelled spec is
  rejected (exit 1) before any pinned data or helper module is touched.
* The CLI exposes no expected-hash override and no skip-check bypass, and
  it runs no commands, no network access and no git.

The report JSON is written to stdout and, when ``--output`` is given,
atomically to that path (temporary sibling then replace) with identical
bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
import types
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ARCHIVE_BASENAME",
    "ARCHIVE_BYTES",
    "ARCHIVE_SHA256",
    "CONTRACT_ID",
    "CONTRACT_REQUIREMENTS_SHA256",
    "CONTRACT_REVISION",
    "CONTRACT_SOURCE_COMMIT",
    "DESIGN_COMMIT",
    "MISSING_FULL_GATES",
    "PINNED_ARTIFACTS",
    "PRODUCTION_SPEC",
    "TASK_ID",
    "TASK_VERSION",
    "CheckOutcome",
    "PinRecord",
    "SPEC_CONTEXT_FORGED",
    "SPEC_CONTEXT_PRODUCTION",
    "SPEC_CONTEXT_SYNTHETIC",
    "VerificationSpec",
    "VerifyDataError",
    "check_archive_identity",
    "check_contract_and_task_identity",
    "check_cross_file_hash_links",
    "check_inventory_structure",
    "check_label_schema_alignment",
    "check_preprocessing_fit_identity",
    "check_preprocessing_statistics",
    "check_rank_split_reconstruction",
    "check_split_structure_and_coverage",
    "check_whole_well_grouping",
    "classify_spec",
    "default_archive_path",
    "display_path",
    "extract_parent_rule",
    "load_json_document",
    "load_pinned_helper_module",
    "main",
    "product_root_from_file",
    "rank_split_assignments",
    "render_report",
    "run_verification",
    "sha256_bytes",
    "sha256_file_stream",
    "verify_pins",
    "write_text_atomic",
]

CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014"
CONTRACT_REVISION = 1
CONTRACT_SOURCE_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
CONTRACT_REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"

ARCHIVE_BASENAME = "LAS_files_Force_2020_all_wells_train_test_blind_hidden_final.zip"
ARCHIVE_BYTES = 169785172
ARCHIVE_SHA256 = "042ef1d473100dc12768cae7107a8cead071a394f137af3bc1ddaf8a5d1b8dda"
ARCHIVE_DEFAULT_RELATIVE = ".local/datasets/force-2020/" + ARCHIVE_BASENAME

# Main-approved SHA256 pins (verify-data-main-decisions.json).  Nothing in
# this module imports or otherwise consumes a pinned artifact before its
# bytes have been hash-checked against these values.  The public canonical
# pin map is frozen: a mapping proxy over a private copy.
PINNED_ARTIFACTS = types.MappingProxyType(
    {
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
)

DOCUMENT_PATHS = {
    "source_inventory": "data/source_inventory.json",
    "force_wells": "data/force_wells.json",
    "splits": "data/splits.json",
    "split_policy": "data/split_policy.json",
    "label_schema": "data/label_schema.json",
    "preprocessing": "data/preprocessing.json",
}

LOCKED_CONTRACT_DOCUMENTS = (
    "source_inventory",
    "splits",
    "split_policy",
    "label_schema",
    "preprocessing",
)

SPLIT_NAMES = ("train", "validation", "test")

PARENT_RULE_EXPECTED = r"^([0-9]+/[0-9]+-[0-9]+)(?:[ ]+[A-Z0-9 -]+)?$"

# The former "causal curve input main acceptance" gate was accepted by main
# (CURVE05 pure builder accepted, PR25 head fe9fc080).  This is a status
# correction only: the four remaining gates keep the full C01 scope blocked
# and every product card stays not_run.
MISSING_FULL_GATES = (
    "R03 public resource/profile/observation schema acceptance",
    "sensor_live whole acquisition-run manifest",
    "sim_em_v2 whole-scenario and derivative splits",
    "runtime future-label/truth-access instrumentation",
)

LIMITATIONS = (
    "The archive is read only as a raw byte stream (SHA256 plus byte length)."
    " No ZIP member was opened, no LAS value was parsed and no statistic was"
    " recomputed.",
    "The archive hash and the previously reviewed pinned inventory together"
    " give provenance; this verifier does not perform a fresh per-well"
    " parsing measurement.",
    "The numeric preprocessing fit was previously main-audited; this verifier"
    " checks documented metadata and fit-identity consistency only, with"
    " defined tolerances for derived scalars.",
    "Current parser modules and historical generator snapshots have separate"
    " byte pins. Historical snapshots preserve the frozen preprocessing"
    " provenance and are never imported or executed; repaired parsers did"
    " not regenerate the frozen documents.",
    "Offline FORCE-2020 public lithology domain only; sensor_live acquisition"
    " runs and sim_em_v2 complete scenarios are not covered.",
    "Label-schema metadata only; no row-level label or confidence value is"
    " read, and runtime future-label access is unverified (unknown, never"
    " reported as zero).",
    "No model training, no held-out evaluation, no calibration and no"
    " hardware acceptance; the C01 product card remains not_run.",
)


@dataclass(frozen=True)
class VerificationSpec:
    """Expected identity and counts for one verifier context.

    ``PRODUCTION_SPEC`` carries the main-approved pins and counts for the
    frozen C01 artifact family.  Tests build clearly labelled synthetic
    specs whose pins come from temporary fixture files, so a synthetic run
    can never masquerade as pinned production provenance.
    """

    name: str
    pins: dict
    archive: tuple
    members: int
    rows_total: int
    curves_total: int
    roots: int
    group_counts: dict
    well_counts: dict
    train_wells: int
    train_parent_groups: int
    train_data_rows: int
    channel_order: tuple
    channel_transforms: dict
    domain: str
    curve_input_shape: tuple
    summary_input_shape: tuple
    target_curve: str
    confidence_curve: str
    label_class_count: int
    confidence_codes: tuple
    salt: str
    fractions: dict
    license_id: str
    original_license_text: str
    doi: str
    repository_commit: str
    record_url: str
    repository_url: str
    dataset_label: str


    def __post_init__(self) -> None:
        """Freeze every container on ingress (immutable copies only)."""

        def freeze_mapping(value: object, field: str) -> None:
            if not isinstance(value, Mapping):
                raise TypeError(
                    "VerificationSpec.{} must be a mapping, got {}".format(
                        field, type(value).__name__
                    )
                )
            object.__setattr__(self, field, types.MappingProxyType(dict(value)))

        def freeze_sequence(value: object, field: str) -> None:
            if isinstance(value, (str, bytes)) or not isinstance(
                value, (tuple, list)
            ):
                raise TypeError(
                    "VerificationSpec.{} must be a tuple/list, got {}".format(
                        field, type(value).__name__
                    )
                )
            object.__setattr__(self, field, tuple(value))

        if not isinstance(self.name, str):
            raise TypeError("VerificationSpec.name must be a string")
        freeze_mapping(self.pins, "pins")
        freeze_mapping(self.group_counts, "group_counts")
        freeze_mapping(self.well_counts, "well_counts")
        freeze_mapping(self.channel_transforms, "channel_transforms")
        freeze_mapping(self.fractions, "fractions")
        freeze_sequence(self.archive, "archive")
        freeze_sequence(self.channel_order, "channel_order")
        freeze_sequence(self.curve_input_shape, "curve_input_shape")
        freeze_sequence(self.summary_input_shape, "summary_input_shape")
        freeze_sequence(self.confidence_codes, "confidence_codes")


PRODUCTION_SPEC = VerificationSpec(
    name="production",
    pins=dict(PINNED_ARTIFACTS),
    archive=(ARCHIVE_BASENAME, ARCHIVE_BYTES, ARCHIVE_SHA256),
    members=118,
    rows_total=2337639,
    curves_total=2393,
    roots=117,
    group_counts={"train": 81, "validation": 17, "test": 19},
    well_counts={"train": 82, "validation": 17, "test": 19},
    train_wells=82,
    train_parent_groups=81,
    train_data_rows=1634292,
    channel_order=("GR", "RHOB", "NPHI", "RDEP"),
    channel_transforms={
        "GR": "identity-v1",
        "RHOB": "identity-v1",
        "NPHI": "identity-v1",
        "RDEP": "log10-positive-v1",
    },
    domain="force_2020_public_lithology",
    curve_input_shape=(1, 8, 128, 1),
    summary_input_shape=(1, 13, 32, 1),
    target_curve="FORCE_2020_LITHOFACIES_LITHOLOGY",
    confidence_curve="FORCE_2020_LITHOFACIES_CONFIDENCE",
    label_class_count=12,
    confidence_codes=("1", "2", "3"),
    salt="DEEPEYE-FORCE-WELL-SPLIT-20261014-v1",
    fractions={"train": 0.70, "validation": 0.15, "test": 0.15},
    license_id="cc-by-4.0",
    original_license_text="NOLD 2.0",
    doi="10.5281/zenodo.4351156",
    repository_commit="c8d01ee92c1c8e1ecba36f96cca6ea7b689338a1",
    record_url="https://zenodo.org/records/4351156",
    repository_url=(
        "https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition"
    ),
    dataset_label="FORCE 2020 machine learning competition well logs (public lithology domain)",
)


# Spec contexts.  Only the immutable canonical ``PRODUCTION_SPEC`` may carry
# the production label; any other name is a synthetic fixture context, and a
# production-labelled spec that does not equal the canonical object is a
# forged context, rejected before any pinned byte or helper module is
# touched.  This is a structural identity check, not a caller-supplied
# trusted flag.
SPEC_CONTEXT_PRODUCTION = "production"
SPEC_CONTEXT_SYNTHETIC = "synthetic_fixture"
SPEC_CONTEXT_FORGED = "rejected_forged_production"


def classify_spec(spec: VerificationSpec) -> str:
    """Return the context of ``spec``: production, synthetic or forged."""

    if spec.name == "production":
        return (
            SPEC_CONTEXT_PRODUCTION
            if spec == PRODUCTION_SPEC
            else SPEC_CONTEXT_FORGED
        )
    return SPEC_CONTEXT_SYNTHETIC


class VerifyDataError(Exception):
    """A deterministic blocked/failed condition for one verification step."""

    def __init__(self, status: str, detail: str) -> None:
        if status not in ("blocked", "failed"):
            raise ValueError("unsupported VerifyDataError status {!r}".format(status))
        self.status = status
        self.detail = detail
        super().__init__("{}: {}".format(status, detail))


@dataclass(frozen=True)
class CheckOutcome:
    """Result of one named check (passed / failed / blocked / not_run)."""

    check_id: str
    status: str
    detail: str


@dataclass(frozen=True)
class PinRecord:
    """Byte/hash evidence for one pinned artifact."""

    path: str
    expected_sha256: str
    actual_sha256: object
    bytes: object
    status: str


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file_stream(path: Path) -> tuple:
    """Return (bytes_read, sha256_hex) hashing ``path`` in bounded chunks.

    The file is opened in binary mode and never interpreted.  This is the
    only way the archive is touched (no ZIP member access).
    """

    digest = hashlib.sha256()
    total = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
    return total, digest.hexdigest()


def product_root_from_file() -> Path:
    return Path(__file__).resolve().parents[1]


def default_archive_path(product_root: Path) -> Path:
    """Legacy helper for the historical implicit archive location.

    The CLI no longer calls this: a caller that wants the historical
    repository location must pass it explicitly with ``--archive``.
    """

    repository_root = product_root.parents[3]
    return repository_root / ARCHIVE_DEFAULT_RELATIVE


def display_path(path: Path, product_root: Path) -> str:
    """Public path form for reports: product-relative or basename only."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(product_root.resolve()).as_posix()
    except ValueError:
        return resolved.name


def extract_parent_rule(rule_text: object) -> str:
    """Extract the ``^...$`` parent-well regex from the pinned policy text."""

    if not isinstance(rule_text, str):
        raise VerifyDataError("failed", "split policy parent_well_rule is not a string")
    start = rule_text.find("^")
    end = rule_text.find("$", start + 1) if start >= 0 else -1
    if start < 0 or end <= start:
        raise VerifyDataError(
            "failed", "cannot extract a ^...$ parent regex from {!r}".format(rule_text)
        )
    return rule_text[start : end + 1]


def is_hex64(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def nested(document: object, *keys: str) -> object:
    current = document
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def truncate(detail: str, limit: int = 600) -> str:
    return detail if len(detail) <= limit else detail[: limit - 3] + "..."


def verify_pins(product_root: Path, spec: VerificationSpec) -> list:
    """Hash every pinned artifact; nothing pinned is imported here."""

    records = []
    for relative in sorted(spec.pins):
        path = product_root / relative
        if not path.is_file():
            records.append(PinRecord(relative, spec.pins[relative], None, None, "missing"))
            continue
        try:
            size, actual = sha256_file_stream(path)
        except OSError:
            records.append(
                PinRecord(relative, spec.pins[relative], None, None, "unreadable")
            )
            continue
        status = "verified" if actual == spec.pins[relative] else "hash_mismatch"
        records.append(PinRecord(relative, spec.pins[relative], actual, size, status))
    return records


def overall_pin_status(records: list) -> str:
    """Observed corruption or unreadable bytes fail; all-missing-only blocks.

    Precedence matters: a missing prerequisite must never mask an observed
    hash mismatch or unreadable input; the report then fails (exit 1) and
    lists both conditions.
    """

    if any(record.status in ("hash_mismatch", "unreadable") for record in records):
        return "failed"
    if any(record.status == "missing" for record in records):
        return "blocked"
    return "verified"


def load_json_document(product_root: Path, name: str, spec: VerificationSpec) -> dict:
    """Load one pinned JSON document from a single hash-verified buffer.

    The file is read exactly once; that buffer is checked against the
    context's expected pin and only then decoded and parsed.  A file that
    changes between the pin pass and this load is therefore never parsed as
    verified data.
    """

    relative = DOCUMENT_PATHS[name]
    expected = spec.pins.get(relative)
    if expected is None:
        raise VerifyDataError(
            "failed",
            "{} is not part of the pinned artifact set for this context".format(
                relative
            ),
        )
    path = product_root / relative
    if not path.is_file():
        raise VerifyDataError(
            "blocked", "pinned document {} is missing".format(relative)
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VerifyDataError(
            "failed", "{} unreadable after pin check: {}".format(relative, exc)
        ) from exc
    actual = sha256_bytes(raw)
    if actual != expected:
        raise VerifyDataError(
            "failed",
            "{} changed between pin check and parse: actual={} expected={}; "
            "the unverified bytes were not parsed".format(
                relative, actual, expected
            ),
        )
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerifyDataError(
            "failed", "{} is not valid UTF-8 JSON: {}".format(relative, exc)
        ) from exc
    if not isinstance(document, dict):
        raise VerifyDataError(
            "failed",
            "{} top level is {}, expected a JSON object".format(
                relative, type(document).__name__
            ),
        )
    return document


_HELPER_MODULE_CACHE: dict = {}


def load_pinned_helper_module(
    product_root: Path, spec: VerificationSpec, relative: str, module_name: str
) -> types.ModuleType:
    """Import one pinned helper module only after its SHA256 was verified."""

    expected = spec.pins.get(relative)
    if expected is None:
        raise VerifyDataError(
            "failed", "{} is not part of the pinned artifact set".format(relative)
        )
    path = product_root / relative
    if not path.is_file():
        raise VerifyDataError("blocked", "pinned helper {} is missing".format(relative))
    data = path.read_bytes()
    actual = sha256_bytes(data)
    if actual != expected:
        raise VerifyDataError(
            "failed",
            "pinned helper {} hash mismatch: actual={} expected={}".format(
                relative, actual, expected
            ),
        )
    cache_key = (str(path), expected)
    cached = _HELPER_MODULE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    sys.modules[module_name] = module
    try:
        exec(compile(data, str(path), "exec"), module.__dict__)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise VerifyDataError(
            "failed",
            "pinned helper {} failed to import: {}: {}".format(
                relative, type(exc).__name__, exc
            ),
        ) from exc
    _HELPER_MODULE_CACHE[cache_key] = module
    return module


def check_contract_and_task_identity(docs: dict) -> CheckOutcome:
    """Every defined contract/task/design field must equal the frozen values."""

    problems = []
    for name in sorted(docs):
        document = docs[name]
        contract = document.get("contract")
        if contract is None:
            if name in LOCKED_CONTRACT_DOCUMENTS:
                problems.append("{}: missing contract block".format(name))
        elif not isinstance(contract, dict):
            problems.append(
                "{}: contract is {}, expected object".format(
                    name, type(contract).__name__
                )
            )
        else:
            for key, expected in (
                ("id", CONTRACT_ID),
                ("revision", CONTRACT_REVISION),
                ("source_commit", CONTRACT_SOURCE_COMMIT),
                ("requirements_sha256", CONTRACT_REQUIREMENTS_SHA256),
            ):
                value = contract.get(key)
                if value != expected:
                    problems.append(
                        "{}.contract.{}: actual={!r} expected={!r}".format(
                            name, key, value, expected
                        )
                    )
        for key, expected in (("task_id", TASK_ID), ("task_version", TASK_VERSION)):
            if key in document and document.get(key) != expected:
                problems.append(
                    "{}.{}: actual={!r} expected={!r}".format(
                        name, key, document.get(key), expected
                    )
                )
        design_values = (
            ("design_commit", document.get("design_commit")),
            (
                "contract.design_commit",
                contract.get("design_commit") if isinstance(contract, dict) else None,
            ),
        )
        for location, value in design_values:
            if value is not None and value != DESIGN_COMMIT:
                problems.append(
                    "{}.{}: actual={!r} expected={!r}".format(
                        name, location, value, DESIGN_COMMIT
                    )
                )
        schema = document.get("schema")
        if schema is not None and schema != 1:
            problems.append(
                "{}.schema: actual={!r} expected=1".format(name, schema)
            )
    if problems:
        return CheckOutcome(
            "contract_task_design_identity", "failed", truncate("; ".join(problems))
        )
    return CheckOutcome(
        "contract_task_design_identity",
        "passed",
        "contract/task/design identity matches DEEPEYE-HUMAN-LOCK-20261014 r1 "
        "(source f5989cd5..., design 10112594...) in all {} documents".format(
            len(docs)
        ),
    )


def check_cross_file_hash_links(docs: dict, spec: VerificationSpec) -> CheckOutcome:
    """Structural equality of every cross-file hash link and provenance field."""

    problems = []
    pins = spec.pins
    archive_file, archive_size, archive_sha = spec.archive

    def expect(label: str, actual: object, expected: object) -> None:
        if actual != expected:
            problems.append(
                "{}: actual={!r} expected={!r}".format(label, actual, expected)
            )

    inventory = docs.get("source_inventory", {})
    wells_doc = docs.get("force_wells", {})
    splits = docs.get("splits", {})
    policy = docs.get("split_policy", {})
    label_schema = docs.get("label_schema", {})
    preprocessing = docs.get("preprocessing", {})

    expect(
        "source_inventory.complete_well_inventory.sha256",
        nested(inventory, "complete_well_inventory", "sha256"),
        pins.get("data/force_wells.json"),
    )
    expect(
        "source_inventory.split_manifest.sha256",
        nested(inventory, "split_manifest", "sha256"),
        pins.get("data/splits.json"),
    )
    expect(
        "source_inventory.selected_file.local_sha256",
        nested(inventory, "selected_file", "local_sha256"),
        archive_sha,
    )
    expect(
        "source_inventory.selected_file.expected_bytes",
        nested(inventory, "selected_file", "expected_bytes"),
        archive_size,
    )
    expect(
        "source_inventory.selected_file.actual_bytes",
        nested(inventory, "selected_file", "actual_bytes"),
        archive_size,
    )
    expect(
        "source_inventory.complete_well_inventory.members",
        nested(inventory, "complete_well_inventory", "members"),
        spec.members,
    )
    expect(
        "source_inventory.complete_well_inventory.rows",
        nested(inventory, "complete_well_inventory", "rows"),
        spec.rows_total,
    )
    expect(
        "source_inventory.source_record.doi",
        nested(inventory, "source_record", "doi"),
        spec.doi,
    )
    expect(
        "source_inventory.source_record.license_id_from_record",
        nested(inventory, "source_record", "license_id_from_record"),
        spec.license_id,
    )
    expect(
        "source_inventory.source_record.original_data_license_text",
        nested(inventory, "source_record", "original_data_license_text"),
        spec.original_license_text,
    )
    expect(
        "source_inventory.authors_repository.commit",
        nested(inventory, "authors_repository", "commit"),
        spec.repository_commit,
    )
    expect("source_inventory.source_mode", inventory.get("source_mode"), "geo_replay")
    expect(
        "source_inventory.grouping_unit",
        inventory.get("grouping_unit"),
        "complete_well",
    )
    expect(
        "source_inventory.split_manifest.group_counts",
        nested(inventory, "split_manifest", "group_counts"),
        spec.group_counts,
    )
    expect(
        "source_inventory.split_manifest.well_counts",
        nested(inventory, "split_manifest", "well_counts"),
        spec.well_counts,
    )

    expect(
        "splits.inventory_sha256",
        splits.get("inventory_sha256"),
        pins.get("data/force_wells.json"),
    )
    expect(
        "splits.policy_sha256", splits.get("policy_sha256"), pins.get("data/split_policy.json")
    )
    expect(
        "splits.label_schema_sha256",
        splits.get("label_schema_sha256"),
        pins.get("data/label_schema.json"),
    )
    expect("splits.source_archive_sha256", splits.get("source_archive_sha256"), archive_sha)
    expect("splits.group_counts", splits.get("group_counts"), spec.group_counts)
    expect("splits.well_counts", splits.get("well_counts"), spec.well_counts)

    expect(
        "split_policy.source_archive_sha256", policy.get("source_archive_sha256"), archive_sha
    )
    expect("split_policy.assignment.salt", nested(policy, "assignment", "salt"), spec.salt)
    expect(
        "split_policy.assignment.fraction_targets",
        nested(policy, "assignment", "fraction_targets"),
        spec.fractions,
    )
    expect(
        "split_policy.preprocessing.curve_order",
        nested(policy, "preprocessing", "curve_order"),
        list(spec.channel_order),
    )

    expect(
        "label_schema.input_curve_order",
        label_schema.get("input_curve_order"),
        list(spec.channel_order),
    )
    expect(
        "label_schema.curve_input_shape",
        label_schema.get("curve_input_shape"),
        list(spec.curve_input_shape),
    )
    expect(
        "label_schema.summary_input_shape",
        label_schema.get("summary_input_shape"),
        list(spec.summary_input_shape),
    )
    expect("label_schema.target_curve", label_schema.get("target_curve"), spec.target_curve)
    expect(
        "label_schema.confidence_curve",
        label_schema.get("confidence_curve"),
        spec.confidence_curve,
    )
    expect(
        "label_schema.source.commit",
        nested(label_schema, "source", "commit"),
        spec.repository_commit,
    )

    expect(
        "preprocessing.inputs.archive.sha256",
        nested(preprocessing, "inputs", "archive", "sha256"),
        archive_sha,
    )
    expect(
        "preprocessing.inputs.archive.bytes",
        nested(preprocessing, "inputs", "archive", "bytes"),
        archive_size,
    )
    expect(
        "preprocessing.inputs.inventory.sha256",
        nested(preprocessing, "inputs", "inventory", "sha256"),
        pins.get("data/force_wells.json"),
    )
    expect(
        "preprocessing.inputs.splits.sha256",
        nested(preprocessing, "inputs", "splits", "sha256"),
        pins.get("data/splits.json"),
    )
    expect(
        "preprocessing.inputs.policy.sha256",
        nested(preprocessing, "inputs", "policy", "sha256"),
        pins.get("data/split_policy.json"),
    )
    expect(
        "preprocessing.inputs.label_schema.sha256",
        nested(preprocessing, "inputs", "label_schema", "sha256"),
        pins.get("data/label_schema.json"),
    )
    historical_inventory_path = "data/provenance/force_2020_v1/force_inventory.py"
    if historical_inventory_path in pins:
        inventory_generator_sha = pins[historical_inventory_path]
    elif classify_spec(spec) == SPEC_CONTEXT_SYNTHETIC:
        # Explicit synthetic fixtures can model a single current generator.
        # Canonical production always requires both historical snapshot pins;
        # a missing file/hash never falls back to repaired current code.
        inventory_generator_sha = pins.get("data/force_inventory.py")
    else:
        raise VerifyDataError("failed", "production historical inventory generator pin is missing")
    expect(
        "preprocessing.inputs.helpers.force_inventory.sha256",
        nested(preprocessing, "inputs", "helpers", "force_inventory", "sha256"),
        inventory_generator_sha,
    )
    expect(
        "preprocessing.inputs.helpers.grouping.sha256",
        nested(preprocessing, "inputs", "helpers", "grouping", "sha256"),
        pins.get("data/grouping.py"),
    )
    expect(
        "preprocessing.algorithm.channel_order",
        nested(preprocessing, "algorithm", "channel_order"),
        list(spec.channel_order),
    )
    expect("preprocessing.software_only", preprocessing.get("software_only"), True)
    expect(
        "preprocessing.product_card_c01", preprocessing.get("product_card_c01"), "not_run"
    )

    expect(
        "force_wells.provenance.archive_sha256",
        nested(wells_doc, "provenance", "archive_sha256"),
        archive_sha,
    )
    expect(
        "force_wells.provenance.archive_bytes",
        nested(wells_doc, "provenance", "archive_bytes"),
        archive_size,
    )
    expect("force_wells.provenance.doi", nested(wells_doc, "provenance", "doi"), spec.doi)
    expect(
        "force_wells.provenance.authors_repository_commit",
        nested(wells_doc, "provenance", "authors_repository_commit"),
        spec.repository_commit,
    )
    expect(
        "force_wells.provenance.archive_file",
        nested(wells_doc, "provenance", "archive_file"),
        archive_file,
    )

    if problems:
        return CheckOutcome(
            "cross_file_hash_links", "failed", truncate("; ".join(problems))
        )
    return CheckOutcome(
        "cross_file_hash_links",
        "passed",
        "all cross-file SHA256 links, counts, license/DOI/commit provenance "
        "fields and curve-order references match the pinned values",
    )


def check_inventory_structure(inventory: dict, spec: VerificationSpec) -> tuple:
    """Inventory member/UWI/member-SHA uniqueness and structural counts."""

    problems = []
    data = {"members": None, "rows_total": None, "curves_total": None}
    wells = inventory.get("wells")
    if not isinstance(wells, list):
        return (
            CheckOutcome(
                "inventory_structure",
                "failed",
                "inventory.wells is {}, expected list".format(type(wells).__name__),
            ),
            data,
        )
    if len(wells) != spec.members:
        problems.append(
            "inventory.wells count: actual={} expected={}".format(
                len(wells), spec.members
            )
        )
    summary = inventory.get("summary")
    if not isinstance(summary, dict):
        problems.append("inventory.summary missing or not an object")
        summary = {}
    if summary.get("members") != spec.members:
        problems.append(
            "summary.members: actual={!r} expected={}".format(
                summary.get("members"), spec.members
            )
        )
    if summary.get("duplicate_uwi") != 0:
        problems.append(
            "summary.duplicate_uwi: actual={!r} expected=0".format(
                summary.get("duplicate_uwi")
            )
        )
    if summary.get("all_wrap_no") is not True:
        problems.append(
            "summary.all_wrap_no: actual={!r} expected=True".format(
                summary.get("all_wrap_no")
            )
        )
    seen_members = {}
    seen_uwis = {}
    seen_hashes = {}
    rows_total = 0
    curves_total = 0
    for index, well in enumerate(wells):
        if not isinstance(well, dict):
            problems.append(
                "wells[{}] is {}, expected object".format(
                    index, type(well).__name__
                )
            )
            continue
        member = well.get("member")
        uwi = well.get("uwi")
        member_sha = well.get("member_sha256")
        rows = well.get("rows")
        if isinstance(member, str) and member:
            seen_members[member] = seen_members.get(member, 0) + 1
        else:
            problems.append("wells[{}].member is not a non-empty string".format(index))
        if isinstance(uwi, str) and uwi:
            seen_uwis[uwi] = seen_uwis.get(uwi, 0) + 1
        else:
            problems.append("wells[{}].uwi is not a non-empty string".format(index))
        if is_hex64(member_sha):
            seen_hashes[member_sha] = seen_hashes.get(member_sha, 0) + 1
        else:
            problems.append(
                "wells[{}].member_sha256 is not 64 lowercase hex".format(index)
            )
        if isinstance(rows, int) and not isinstance(rows, bool) and rows > 0:
            rows_total += rows
            depth = well.get("depth")
            depth_count = depth.get("count") if isinstance(depth, dict) else None
            if depth_count != rows:
                problems.append(
                    "wells[{}].depth.count: actual={!r} expected={}".format(
                        index, depth_count, rows
                    )
                )
        else:
            problems.append("wells[{}].rows is not a positive integer".format(index))
        if well.get("crc_verified") is not True:
            problems.append("wells[{}].crc_verified is not True".format(index))
        if well.get("wrap") != "NO":
            problems.append(
                "wells[{}].wrap: actual={!r} expected='NO'".format(
                    index, well.get("wrap")
                )
            )
        curves = well.get("curves")
        if not isinstance(curves, list) or not curves:
            problems.append("wells[{}].curves is not a non-empty list".format(index))
            continue
        curves_total += len(curves)
        for curve_index, curve in enumerate(curves):
            label = "wells[{}].curves[{}]".format(index, curve_index)
            if not isinstance(curve, dict):
                problems.append("{} is not an object".format(label))
                continue
            if not isinstance(curve.get("mnemonic"), str) or not curve.get("mnemonic"):
                problems.append("{}.mnemonic is not a non-empty string".format(label))
            if not isinstance(curve.get("unit"), str) or not curve.get("unit"):
                problems.append("{}.unit is not a non-empty string".format(label))
            count = curve.get("count")
            null_count = curve.get("null_count")
            nonmissing = curve.get("nonmissing_count")
            if count != rows:
                problems.append(
                    "{}.count: actual={!r} expected well rows {!r}".format(
                        label, count, rows
                    )
                )
            if (
                not isinstance(null_count, int)
                or isinstance(null_count, bool)
                or null_count < 0
                or (isinstance(rows, int) and null_count > rows)
            ):
                problems.append(
                    "{}.null_count is not an integer in [0, rows]".format(label)
                )
            elif nonmissing != count - null_count:
                problems.append(
                    "{}.nonmissing_count != count - null_count".format(label)
                )
    duplicate_members = sorted(
        member for member, count in seen_members.items() if count > 1
    )
    if duplicate_members:
        problems.append(
            "duplicate inventory members: {}".format(duplicate_members[:5])
        )
    duplicate_uwis = sorted(uwi for uwi, count in seen_uwis.items() if count > 1)
    if duplicate_uwis:
        problems.append("duplicate inventory UWIs: {}".format(duplicate_uwis[:5]))
    duplicate_hashes = sorted(
        member_sha for member_sha, count in seen_hashes.items() if count > 1
    )
    if duplicate_hashes:
        problems.append(
            "duplicate inventory member SHA256 values: {}".format(
                duplicate_hashes[:5]
            )
        )
    if summary.get("rows_total") != spec.rows_total:
        problems.append(
            "summary.rows_total: actual={!r} expected={}".format(
                summary.get("rows_total"), spec.rows_total
            )
        )
    if rows_total != spec.rows_total:
        problems.append(
            "summed well rows: actual={} expected={}".format(
                rows_total, spec.rows_total
            )
        )
    if summary.get("curves_total") != curves_total:
        problems.append(
            "summary.curves_total: actual={!r} expected summed {}".format(
                summary.get("curves_total"), curves_total
            )
        )
    if curves_total != spec.curves_total:
        problems.append(
            "curves total: actual={} expected={}".format(
                curves_total, spec.curves_total
            )
        )
    data = {
        "members": len(wells),
        "rows_total": rows_total,
        "curves_total": curves_total,
    }
    if problems:
        return (
            CheckOutcome("inventory_structure", "failed", truncate("; ".join(problems))),
            data,
        )
    return (
        CheckOutcome(
            "inventory_structure",
            "passed",
            "{} members, {} rows and {} curve columns verified with unique "
            "member/UWI/member-SHA256 identities, wrap NO and per-curve counts "
            "consistent with well rows".format(
                len(wells), rows_total, curves_total
            ),
        ),
        data,
    )


def check_split_structure_and_coverage(
    splits_doc: dict, inventory: dict, policy_doc: dict, spec: VerificationSpec
) -> tuple:
    """Split rows must map exactly onto the pinned wells with pinned identities."""

    problems = []
    data = {
        "roots": None,
        "group_counts": None,
        "well_counts": None,
        "train_rows": None,
        "total_rows": None,
    }
    rows = splits_doc.get("rows")
    if not isinstance(rows, list):
        return (
            CheckOutcome(
                "split_structure_and_coverage",
                "failed",
                "splits.rows is {}, expected list".format(type(rows).__name__),
            ),
            data,
        )
    try:
        pattern = re.compile(
            extract_parent_rule(nested(policy_doc, "grouping", "parent_well_rule"))
        )
    except VerifyDataError as exc:
        return (
            CheckOutcome("split_structure_and_coverage", exc.status, exc.detail),
            data,
        )
    if pattern.pattern != PARENT_RULE_EXPECTED:
        problems.append(
            "declared parent rule {!r} differs from the reviewed rule {!r}".format(
                pattern.pattern, PARENT_RULE_EXPECTED
            )
        )
    inventory_by_member = {}
    uwi_rows = {}
    wells = inventory.get("wells")
    if isinstance(wells, list):
        for well in wells:
            if not isinstance(well, dict):
                continue
            member = well.get("member")
            uwi = well.get("uwi")
            count = well.get("rows")
            if isinstance(member, str) and member:
                inventory_by_member[member] = well
            if (
                isinstance(uwi, str)
                and uwi
                and isinstance(count, int)
                and not isinstance(count, bool)
            ):
                uwi_rows[uwi] = count
    if len(rows) != spec.members:
        problems.append(
            "splits.rows count: actual={} expected={}".format(len(rows), spec.members)
        )
    member_directories = set()
    required = (
        "row_id",
        "source_domain",
        "root_id",
        "well_id",
        "member",
        "member_sha256",
        "split",
        "derived_from",
    )
    row_id_counts = {}
    well_split = {}
    root_wells = {}
    derived_rows = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(
                "splits.rows[{}] is {}, expected object".format(
                    index, type(row).__name__
                )
            )
            continue
        missing = [key for key in required if key not in row]
        if missing:
            problems.append("splits.rows[{}] missing keys {}".format(index, missing))
            continue
        row_id = row["row_id"]
        well_id = row["well_id"]
        member = row["member"]
        member_sha = row["member_sha256"]
        root_id = row["root_id"]
        domain = row["source_domain"]
        split = row["split"]
        if not isinstance(row_id, str) or not row_id:
            problems.append(
                "splits.rows[{}].row_id must be a non-empty string".format(index)
            )
            continue
        row_id_counts[row_id] = row_id_counts.get(row_id, 0) + 1
        if row_id != well_id:
            problems.append(
                "splits.rows[{}]: row_id {!r} != well_id {!r}".format(
                    index, row_id, well_id
                )
            )
        if domain != spec.domain:
            problems.append(
                "splits.rows[{}].source_domain: actual={!r} expected={!r}".format(
                    index, domain, spec.domain
                )
            )
        if split not in SPLIT_NAMES:
            problems.append(
                "splits.rows[{}].split: actual={!r} expected one of {}".format(
                    index, split, list(SPLIT_NAMES)
                )
            )
            continue
        if row["derived_from"] is not None:
            derived_rows += 1
        well = inventory_by_member.get(member) if isinstance(member, str) else None
        if well is None:
            problems.append(
                "splits.rows[{}].member {!r} is not a pinned inventory member".format(
                    index, member
                )
            )
        else:
            if member_sha != well.get("member_sha256"):
                problems.append(
                    "splits.rows[{}].member_sha256 does not match the inventory "
                    "for {!r}".format(index, member)
                )
            if well_id != well.get("uwi"):
                problems.append(
                    "splits.rows[{}].well_id {!r} does not match inventory UWI "
                    "{!r}".format(index, well_id, well.get("uwi"))
                )
        if isinstance(well_id, str) and isinstance(member, str):
            directory, _, filename = member.rpartition("/")
            if not directory:
                problems.append(
                    "splits.rows[{}].member {!r} is not a directory/file "
                    "member path".format(index, member)
                )
            else:
                member_directories.add(directory)
            expected_filename = well_id.replace("/", "_") + ".las"
            if filename != expected_filename:
                problems.append(
                    "splits.rows[{}].member basename {!r} does not follow the "
                    "pinned rule {!r}".format(index, filename, expected_filename)
                )
        if not isinstance(root_id, str) or not root_id:
            problems.append(
                "splits.rows[{}].root_id must be a non-empty string".format(index)
            )
        elif isinstance(well_id, str):
            match = pattern.fullmatch(well_id)
            if match is None:
                problems.append(
                    "splits.rows[{}].well_id {!r} does not match the declared "
                    "parent rule".format(index, well_id)
                )
            elif match.group(1) != root_id:
                problems.append(
                    "splits.rows[{}]: parent capture {!r} != root_id {!r}".format(
                        index, match.group(1), root_id
                    )
                )
        if isinstance(well_id, str):
            previous = well_split.get(well_id)
            if previous is None:
                well_split[well_id] = split
            elif previous != split:
                problems.append(
                    "well {!r} appears in splits {!r} and {!r}".format(
                        well_id, previous, split
                    )
                )
            if isinstance(root_id, str):
                root_wells.setdefault(root_id, set()).add(well_id)
    duplicates = sorted(rid for rid, count in row_id_counts.items() if count > 1)
    if duplicates:
        problems.append("duplicate row_id values: {}".format(duplicates[:5]))
    if len(member_directories) > 1:
        problems.append(
            "split members live in {} directories: {}".format(
                len(member_directories), sorted(member_directories)[:5]
            )
        )
    if derived_rows:
        problems.append(
            "{} split row(s) declare derived_from; the pinned FORCE manifest "
            "contains base wells only".format(derived_rows)
        )
    covered = set(well_split)
    missing_wells = sorted(set(uwi_rows) - covered)
    extra_wells = sorted(covered - set(uwi_rows))
    if missing_wells or extra_wells:
        problems.append(
            "split coverage mismatch: missing={} extra={}".format(
                missing_wells[:5], extra_wells[:5]
            )
        )
    if len(root_wells) != spec.roots:
        problems.append(
            "parent groups: actual={} expected={}".format(len(root_wells), spec.roots)
        )
    root_split = {}
    for root, members in root_wells.items():
        splits_seen = {well_split.get(well) for well in members}
        if len(splits_seen) != 1 or None in splits_seen:
            problems.append(
                "parent group {!r} crosses splits {!r} or has wells without an "
                "accepted split row".format(root, sorted(str(s) for s in splits_seen))
            )
        else:
            root_split[root] = splits_seen.pop()
    group_counts = {name: 0 for name in SPLIT_NAMES}
    for name in root_split.values():
        group_counts[name] += 1
    well_counts = {name: 0 for name in SPLIT_NAMES}
    for name in well_split.values():
        well_counts[name] += 1
    if group_counts != spec.group_counts:
        problems.append(
            "group counts: actual={} expected={}".format(
                group_counts, spec.group_counts
            )
        )
    if well_counts != spec.well_counts:
        problems.append(
            "well counts: actual={} expected={}".format(well_counts, spec.well_counts)
        )
    train_rows = sum(
        uwi_rows.get(well, 0) for well, split in well_split.items() if split == "train"
    )
    total_rows = sum(uwi_rows.values())
    if train_rows != spec.train_data_rows:
        problems.append(
            "train well rows: actual={} expected={}".format(
                train_rows, spec.train_data_rows
            )
        )
    if total_rows != spec.rows_total:
        problems.append(
            "total inventory rows: actual={} expected={}".format(
                total_rows, spec.rows_total
            )
        )
    data = {
        "roots": len(root_wells),
        "group_counts": group_counts,
        "well_counts": well_counts,
        "train_rows": train_rows,
        "total_rows": total_rows,
    }
    if problems:
        return (
            CheckOutcome(
                "split_structure_and_coverage",
                "failed",
                truncate("; ".join(problems)),
            ),
            data,
        )
    return (
        CheckOutcome(
            "split_structure_and_coverage",
            "passed",
            "{} split rows map one-to-one onto the {} pinned wells with "
            "matching UWIs and byte hashes, the declared parent rule and the "
            "pinned naming rule; per-split counts {} groups / {} wells".format(
                len(rows),
                len(uwi_rows),
                group_counts,
                well_counts,
            ),
        ),
        data,
    )


def check_whole_well_grouping(
    rows: list, grouping_module: types.ModuleType, spec: VerificationSpec, preprocessing_grouping_validation: object
) -> tuple:
    """Run the pinned grouping validator and compare the audited summary."""

    data = {"rows": None, "root_count": None, "split_rows": None}
    try:
        report = grouping_module.validate_split_assignments(rows)
    except Exception as exc:
        return (
            CheckOutcome(
                "whole_well_grouping",
                "failed",
                truncate(
                    "pinned grouping validator rejected the split table: "
                    "{}: {}".format(type(exc).__name__, exc)
                ),
            ),
            data,
        )
    problems = []
    split_rows = dict(report.split_rows)
    data = {
        "rows": report.rows,
        "root_count": report.root_count,
        "split_rows": split_rows,
    }
    expected_derivatives = sum(
        1
        for row in rows
        if isinstance(row, dict) and row.get("derived_from") is not None
    )
    if report.rows != len(rows):
        problems.append(
            "grouping report rows {} != table rows {}".format(report.rows, len(rows))
        )
    if report.root_count != spec.roots:
        problems.append(
            "grouping report root_count: actual={} expected={}".format(
                report.root_count, spec.roots
            )
        )
    if split_rows != spec.well_counts:
        problems.append(
            "grouping report split_rows: actual={} expected={}".format(
                split_rows, spec.well_counts
            )
        )
    domain = report.domains.get(spec.domain)
    if domain is None:
        problems.append(
            "grouping report has no domain {!r} (found {})".format(
                spec.domain, sorted(report.domains)
            )
        )
    else:
        if domain.rows != report.rows:
            problems.append(
                "domain rows: actual={} expected={}".format(domain.rows, report.rows)
            )
        if domain.roots != report.root_count:
            problems.append(
                "domain roots: actual={} expected={}".format(
                    domain.roots, report.root_count
                )
            )
        if domain.derivatives != expected_derivatives:
            problems.append(
                "domain derivatives: actual={} expected={}".format(
                    domain.derivatives, expected_derivatives
                )
            )
        if dict(domain.split_rows) != split_rows:
            problems.append(
                "domain split_rows: actual={} expected={}".format(
                    dict(domain.split_rows), split_rows
                )
            )
    block = preprocessing_grouping_validation
    if block is not None:
        if not isinstance(block, dict):
            problems.append("preprocessing.grouping_validation is not an object")
        else:
            expected_block = {
                "rows": report.rows,
                "root_count": report.root_count,
                "split_rows": split_rows,
                "domains": {
                    spec.domain: {
                        "rows": report.rows,
                        "roots": report.root_count,
                        "derivatives": expected_derivatives,
                        "split_rows": split_rows,
                    }
                },
            }
            for key in ("rows", "root_count", "split_rows", "domains"):
                if block.get(key) != expected_block[key]:
                    problems.append(
                        "preprocessing.grouping_validation.{}: actual={!r} "
                        "expected={!r}".format(key, block.get(key), expected_block[key])
                    )
    if problems:
        return (
            CheckOutcome("whole_well_grouping", "failed", truncate("; ".join(problems))),
            data,
        )
    return (
        CheckOutcome(
            "whole_well_grouping",
            "passed",
            "pinned grouping validator accepted {} rows in {} root groups with "
            "rows per split {} and no cross-split parent".format(
                report.rows, report.root_count, split_rows
            ),
        ),
        data,
    )


def rank_split_assignments(roots, spec: VerificationSpec) -> dict:
    """Independent reconstruction: sort by SHA256(salt + newline + parent)."""

    ordered = sorted(
        roots,
        key=lambda parent: (
            hashlib.sha256((spec.salt + "\n" + parent).encode("utf-8")).hexdigest(),
            parent,
        ),
    )
    total = len(ordered)
    train_cut = math.floor(total * spec.fractions["train"])
    validation_cut = train_cut + math.floor(total * spec.fractions["validation"])
    assignment = {}
    for index, parent in enumerate(ordered):
        if index < train_cut:
            assignment[parent] = "train"
        elif index < validation_cut:
            assignment[parent] = "validation"
        else:
            assignment[parent] = "test"
    return assignment


def check_rank_split_reconstruction(splits_doc: dict, spec: VerificationSpec) -> tuple:
    """The pinned table must equal the salt-ranked reconstruction root by root."""

    problems = []
    data = {"roots": None, "group_counts": None}
    rows = splits_doc.get("rows")
    if not isinstance(rows, list):
        return (
            CheckOutcome(
                "rank_split_reconstruction",
                "failed",
                "splits.rows is {}, expected list".format(type(rows).__name__),
            ),
            data,
        )
    actual = {}
    for row in rows:
        if (
            isinstance(row, dict)
            and isinstance(row.get("root_id"), str)
            and row.get("split") in SPLIT_NAMES
        ):
            actual.setdefault(row["root_id"], row["split"])
    roots = sorted(actual)
    if len(roots) != spec.roots:
        problems.append(
            "roots: actual={} expected={}".format(len(roots), spec.roots)
        )
    predicted = rank_split_assignments(roots, spec)
    mismatched = [root for root in roots if predicted.get(root) != actual.get(root)]
    if mismatched:
        problems.append(
            "rank reconstruction mismatch for {} root(s), first {}".format(
                len(mismatched), mismatched[:3]
            )
        )
    predicted_counts = {name: 0 for name in SPLIT_NAMES}
    for name in predicted.values():
        predicted_counts[name] += 1
    if predicted_counts != spec.group_counts:
        problems.append(
            "predicted group counts: actual={} expected={}".format(
                predicted_counts, spec.group_counts
            )
        )
    data = {"roots": len(roots), "group_counts": predicted_counts}
    if problems:
        return (
            CheckOutcome(
                "rank_split_reconstruction", "failed", truncate("; ".join(problems))
            ),
            data,
        )
    return (
        CheckOutcome(
            "rank_split_reconstruction",
            "passed",
            "all {} parent groups reproduce the SHA256(salt + newline + parent) "
            "ranked assignment with floor(fraction * N) cuts".format(len(roots)),
        ),
        data,
    )


def check_label_schema_alignment(label_schema: dict, spec: VerificationSpec) -> CheckOutcome:
    """Label-schema metadata only: classes, codes and confidence levels."""

    problems = []
    classes = label_schema.get("classes")
    if not isinstance(classes, list) or len(classes) != spec.label_class_count:
        problems.append(
            "classes count: actual={!r} expected={}".format(
                len(classes) if isinstance(classes, list) else classes,
                spec.label_class_count,
            )
        )
    else:
        if any(not isinstance(entry, dict) for entry in classes):
            problems.append("class entries must be objects")
            classes = [entry for entry in classes if isinstance(entry, dict)]
        indices = [entry.get("index") for entry in classes]
        if sorted(indices) != list(range(spec.label_class_count)):
            problems.append(
                "class indices: actual={!r} expected 0..{}".format(
                    indices, spec.label_class_count - 1
                )
            )
        codes = [entry.get("source_code") for entry in classes]
        if not all(isinstance(code, int) and not isinstance(code, bool) for code in codes):
            problems.append("class source_code values must be integers: {!r}".format(codes))
        elif len(set(codes)) != len(codes):
            problems.append("class source_code values must be unique: {!r}".format(codes))
        names = [entry.get("name") for entry in classes]
        if not all(isinstance(name, str) and name for name in names):
            problems.append("class names must be non-empty strings")
    confidence_codes = label_schema.get("confidence_codes")
    if not isinstance(confidence_codes, dict) or sorted(confidence_codes) != sorted(
        spec.confidence_codes
    ):
        problems.append(
            "confidence_codes keys: actual={!r} expected keys {}".format(
                confidence_codes, list(spec.confidence_codes)
            )
        )
    if problems:
        return CheckOutcome(
            "label_schema_alignment", "failed", truncate("; ".join(problems))
        )
    return CheckOutcome(
        "label_schema_alignment",
        "passed",
        "{} label classes (indices 0..{}) and confidence codes {} are "
        "well-formed metadata; no row-level label value was read".format(
            spec.label_class_count,
            spec.label_class_count - 1,
            sorted(spec.confidence_codes),
        ),
    )


def check_preprocessing_fit_identity(
    preprocessing: dict, inventory: dict, splits_doc: dict, spec: VerificationSpec
) -> tuple:
    """Fitting wells must be exactly the train wells in pinned split row order."""

    problems = []
    data = {"fitting_wells": None, "fitting_rows": None, "train_root_count": None}
    wells_by_member = {}
    wells = inventory.get("wells")
    if isinstance(wells, list):
        for well in wells:
            if isinstance(well, dict) and isinstance(well.get("member"), str):
                wells_by_member[well["member"]] = well
    rows = splits_doc.get("rows")
    train_members = []
    train_roots = set()
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or row.get("split") != "train":
                continue
            if isinstance(row.get("member"), str):
                train_members.append(row["member"])
            if isinstance(row.get("root_id"), str):
                train_roots.add(row["root_id"])
    fit = preprocessing.get("fitting_wells")
    if not isinstance(fit, list):
        return (
            CheckOutcome(
                "preprocessing_fit_identity",
                "failed",
                "preprocessing.fitting_wells is {}, expected list".format(
                    type(fit).__name__
                ),
            ),
            data,
        )
    fit_members = [
        entry.get("member") if isinstance(entry, dict) else None for entry in fit
    ]
    if fit_members != train_members:
        first_difference = None
        for index in range(max(len(fit_members), len(train_members))):
            left = fit_members[index] if index < len(fit_members) else None
            right = train_members[index] if index < len(train_members) else None
            if left != right:
                first_difference = (index, left, right)
                break
        problems.append(
            "fitting_wells identity/order differs from the train rows "
            "({} fitting entries vs {} train rows; first difference at "
            "index {}: fit={!r} train={!r})".format(
                len(fit_members),
                len(train_members),
                first_difference[0] if first_difference else -1,
                first_difference[1] if first_difference else None,
                first_difference[2] if first_difference else None,
            )
        )
    string_members = [member for member in fit_members if isinstance(member, str)]
    if len(set(string_members)) != len(fit_members):
        problems.append("fitting_wells contains duplicate member identities")
    fit_rows_total = 0
    for index, entry in enumerate(fit):
        if not isinstance(entry, dict):
            problems.append(
                "fitting_wells[{}] is {}, expected object".format(
                    index, type(entry).__name__
                )
            )
            continue
        member = entry.get("member")
        well = wells_by_member.get(member) if isinstance(member, str) else None
        if well is None:
            problems.append(
                "fitting_wells[{}].member {!r} is not a pinned inventory "
                "member".format(index, member)
            )
            continue
        if entry.get("member_sha256") != well.get("member_sha256"):
            problems.append(
                "fitting_wells[{}].member_sha256 does not match the inventory "
                "for {!r}".format(index, member)
            )
        if entry.get("uwi") != well.get("uwi"):
            problems.append(
                "fitting_wells[{}].uwi {!r} does not match inventory UWI "
                "{!r}".format(index, entry.get("uwi"), well.get("uwi"))
            )
        if entry.get("rows") != well.get("rows"):
            problems.append(
                "fitting_wells[{}].rows {!r} does not match inventory rows "
                "{!r}".format(index, entry.get("rows"), well.get("rows"))
            )
        if entry.get("crc_verified") is not True:
            problems.append("fitting_wells[{}].crc_verified is not True".format(index))
        entry_rows = entry.get("rows")
        if isinstance(entry_rows, int) and not isinstance(entry_rows, bool):
            fit_rows_total += entry_rows
    expected_train_rows = nested(preprocessing, "train", "data_rows")
    if expected_train_rows != spec.train_data_rows:
        problems.append(
            "preprocessing.train.data_rows: actual={!r} expected={}".format(
                expected_train_rows, spec.train_data_rows
            )
        )
    if fit_rows_total != expected_train_rows:
        problems.append(
            "fitting well row sum: actual={} expected preprocessing.train."
            "data_rows={!r}".format(fit_rows_total, expected_train_rows)
        )
    inventory_train_rows = sum(
        wells_by_member[member].get("rows", 0)
        for member in train_members
        if member in wells_by_member
        and isinstance(wells_by_member[member].get("rows", 0), int)
        and not isinstance(wells_by_member[member].get("rows", 0), bool)
    )
    if inventory_train_rows != expected_train_rows:
        problems.append(
            "independently summed train inventory rows: actual={} expected="
            "{!r}".format(inventory_train_rows, expected_train_rows)
        )
    if nested(preprocessing, "train", "wells") != spec.train_wells:
        problems.append(
            "preprocessing.train.wells: actual={!r} expected={}".format(
                nested(preprocessing, "train", "wells"), spec.train_wells
            )
        )
    if nested(preprocessing, "train", "parent_groups") != spec.train_parent_groups:
        problems.append(
            "preprocessing.train.parent_groups: actual={!r} expected={}".format(
                nested(preprocessing, "train", "parent_groups"),
                spec.train_parent_groups,
            )
        )
    if len(train_roots) != spec.train_parent_groups:
        problems.append(
            "train parent groups from the split table: actual={} expected="
            "{}".format(len(train_roots), spec.train_parent_groups)
        )
    data = {
        "fitting_wells": len(fit),
        "fitting_rows": fit_rows_total,
        "train_root_count": len(train_roots),
    }
    if problems:
        return (
            CheckOutcome(
                "preprocessing_fit_identity", "failed", truncate("; ".join(problems))
            ),
            data,
        )
    return (
        CheckOutcome(
            "preprocessing_fit_identity",
            "passed",
            "{} fitting wells are exactly the train members in pinned split row "
            "order with matching SHA256/UWI/rows; row sum {} equals the "
            "documented and inventory-summed train rows in {} parent "
            "groups".format(
                len(fit), fit_rows_total, len(train_roots)
            ),
        ),
        data,
    )


def check_preprocessing_statistics(preprocessing: dict, spec: VerificationSpec) -> CheckOutcome:
    """Documented statistics metadata consistency (the fit is not recomputed)."""

    problems = []
    channels = preprocessing.get("channels")
    if not isinstance(channels, list) or len(channels) != len(spec.channel_order):
        return CheckOutcome(
            "preprocessing_statistics_metadata",
            "failed",
            "channels is {!r}, expected a list of {} channels".format(
                len(channels) if isinstance(channels, list) else channels,
                len(spec.channel_order),
            ),
        )
    train_rows = nested(preprocessing, "train", "data_rows")
    for index, channel in enumerate(channels):
        if not isinstance(channel, dict):
            problems.append(
                "channels[{}] is {}, expected object".format(
                    index, type(channel).__name__
                )
            )
            continue
        expected_name = spec.channel_order[index]
        if channel.get("name") != expected_name:
            problems.append(
                "channels[{}].name: actual={!r} expected={!r}".format(
                    index, channel.get("name"), expected_name
                )
            )
            continue
        if not isinstance(channel.get("unit"), str) or not channel.get("unit"):
            problems.append(
                "channels[{}].unit must be a non-empty string".format(index)
            )
        expected_transform = spec.channel_transforms[expected_name]
        if channel.get("transform_version") != expected_transform:
            problems.append(
                "channels[{}].transform_version: actual={!r} expected={!r}".format(
                    index, channel.get("transform_version"), expected_transform
                )
            )
        counts = channel.get("counts")
        bucket_total = 0
        buckets_valid = True
        if not isinstance(counts, dict):
            problems.append("channels[{}].counts is not an object".format(index))
            counts = {}
            buckets_valid = False
        for key in ("valid", "null", "nonpositive", "absent"):
            value = counts.get(key)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                problems.append(
                    "channels[{}].counts.{} must be a non-negative "
                    "integer".format(index, key)
                )
                buckets_valid = False
            else:
                bucket_total += value
        if buckets_valid and isinstance(train_rows, int) and bucket_total != train_rows:
            problems.append(
                "channels[{}] bucket sum: actual={} expected train rows "
                "{!r}".format(index, bucket_total, train_rows)
            )
        valid = counts.get("valid")
        if channel.get("valid_samples") != valid:
            problems.append(
                "channels[{}].valid_samples: actual={!r} expected={!r}".format(
                    index, channel.get("valid_samples"), valid
                )
            )
        if isinstance(valid, int) and not isinstance(valid, bool) and valid <= 0:
            problems.append(
                "channels[{}] has no valid training samples; an all-missing "
                "training channel is a blocker".format(index)
            )
        mean = channel.get("mean")
        variance = channel.get("variance")
        std = channel.get("std")
        scale = channel.get("effective_scale")
        zero_variance = channel.get("zero_variance")
        if not is_finite_number(mean):
            problems.append("channels[{}].mean is not a finite number".format(index))
        if not is_finite_number(variance) or variance < 0:
            problems.append(
                "channels[{}].variance is not a finite non-negative "
                "number".format(index)
            )
        if not is_finite_number(std) or std < 0:
            problems.append(
                "channels[{}].std is not a finite non-negative number".format(index)
            )
        if is_finite_number(variance) and is_finite_number(std):
            if not math.isclose(std, math.sqrt(variance), rel_tol=1e-9, abs_tol=0.0):
                problems.append(
                    "channels[{}].std {!r} != sqrt(variance) {!r} within "
                    "rel_tol 1e-9".format(index, std, math.sqrt(variance))
                )
        if not isinstance(zero_variance, bool):
            problems.append(
                "channels[{}].zero_variance must be a boolean".format(index)
            )
        elif is_finite_number(variance) and zero_variance != (variance == 0.0):
            problems.append(
                "channels[{}].zero_variance {!r} inconsistent with variance "
                "{!r}".format(index, zero_variance, variance)
            )
        if zero_variance is True:
            if scale != 1.0:
                problems.append(
                    "channels[{}].effective_scale must be exactly 1.0 for zero "
                    "variance (recorded explicitly, not silent)".format(index)
                )
        elif zero_variance is False:
            if not is_finite_number(scale) or scale <= 0:
                problems.append(
                    "channels[{}].effective_scale must be a finite positive "
                    "number".format(index)
                )
            elif is_finite_number(std) and not math.isclose(
                scale, std, rel_tol=1e-12, abs_tol=0.0
            ):
                problems.append(
                    "channels[{}].effective_scale {!r} != std {!r} within "
                    "rel_tol 1e-12".format(index, scale, std)
                )
    if problems:
        return CheckOutcome(
            "preprocessing_statistics_metadata", "failed", truncate("; ".join(problems))
        )
    return CheckOutcome(
        "preprocessing_statistics_metadata",
        "passed",
        "4 channels in pinned order with finite mean/variance/std, "
        "std==sqrt(variance) within rel_tol 1e-9, bucket sums equal to the "
        "train rows and the explicit zero-variance effective_scale rule "
        "(numeric fit not recomputed)",
    )


def check_archive_identity(archive_path, spec: VerificationSpec) -> tuple:
    """Stream-hash the raw archive; never open a ZIP member."""

    expected_file, expected_bytes, expected_sha = spec.archive
    data = {
        "expected_file": expected_file,
        "expected_sha256": expected_sha,
        "expected_bytes": expected_bytes,
        "actual_file": None,
        "actual_sha256": None,
        "actual_bytes": None,
        "status": "not_checked",
    }
    if archive_path is None:
        data["status"] = "no_path"
        return (
            CheckOutcome(
                "archive_bytes_and_sha256",
                "blocked",
                "no archive path was supplied",
            ),
            data,
        )
    try:
        is_file = Path(archive_path).is_file()
    except OSError:
        is_file = False
    if not is_file:
        data["status"] = "missing"
        data["actual_file"] = Path(archive_path).name
        return (
            CheckOutcome(
                "archive_bytes_and_sha256",
                "blocked",
                "archive {} is missing (missing prerequisite, not corrupt "
                "input)".format(Path(archive_path).name),
            ),
            data,
        )
    size, actual = sha256_file_stream(Path(archive_path))
    data["actual_file"] = Path(archive_path).name
    data["actual_sha256"] = actual
    data["actual_bytes"] = size
    if size == expected_bytes and actual == expected_sha:
        data["status"] = "verified"
        return (
            CheckOutcome(
                "archive_bytes_and_sha256",
                "passed",
                "archive byte stream verified: {} bytes, sha256 {} (byte "
                "stream only; no ZIP member opened)".format(size, actual),
            ),
            data,
        )
    data["status"] = "mismatch"
    return (
        CheckOutcome(
            "archive_bytes_and_sha256",
            "failed",
            "archive identity mismatch: actual file={} bytes={} sha256={}; "
            "expected file={} bytes={} sha256={}".format(
                data["actual_file"],
                size,
                actual,
                expected_file,
                expected_bytes,
                expected_sha,
            ),
        ),
        data,
    )


CHECK_IDS = (
    "spec_context",
    "pinned_artifact_hashes",
    "pinned_documents_parse",
    "contract_task_design_identity",
    "cross_file_hash_links",
    "inventory_structure",
    "split_structure_and_coverage",
    "whole_well_grouping",
    "rank_split_reconstruction",
    "label_schema_alignment",
    "preprocessing_fit_identity",
    "preprocessing_statistics_metadata",
    "archive_bytes_and_sha256",
    "zip_member_and_las_parse_absence",
    "output_write",
    "runtime_future_label_access",
    "real_sim_domain_separation",
    "full_c01_prerequisite_gates",
)


def render_report(report: dict) -> str:
    return json.dumps(report, indent=1, ensure_ascii=False) + "\n"


def _configure_stdout() -> None:
    """Keep stdout bytes identical to the atomic file content.

    Without this, the default text-mode newline translation on Windows would
    turn every "\\n" into "\\r\\n" on stdout only.
    """

    try:
        sys.stdout.reconfigure(newline="")
    except (AttributeError, ValueError, OSError):
        pass


def set_check(report: dict, check_id: str, status: str, detail: str) -> None:
    for entry in report.get("checks", []):
        if entry.get("id") == check_id:
            entry["status"] = status
            entry["detail"] = detail
            return
    report.setdefault("checks", []).append(
        {"id": check_id, "status": status, "detail": detail}
    )


def tool_sha256() -> object:
    try:
        return sha256_bytes(Path(__file__).resolve().read_bytes())
    except OSError:
        return None


def _run_checks(
    product_root: Path,
    spec: VerificationSpec,
    *,
    scope: str,
    archive_path,
    output_display: object,
    checks: dict,
    check_data: dict,
) -> list:
    """Populate ``checks``/``check_data`` for a context that passed the gate.

    Data problems never raise from here: the caller records deterministic
    passed/failed/blocked/not_run outcomes.  Only specs classified as
    production or synthetic reach this helper, and it returns the artifact
    records for the report.
    """

    if scope not in ("full_c01", "force-offline"):
        raise ValueError("unsupported scope {!r}".format(scope))

    def record(outcome: CheckOutcome) -> None:
        checks[outcome.check_id] = outcome

    def run_check(check_id: str, func, *args) -> tuple:
        try:
            result = func(*args)
        except VerifyDataError as exc:
            return CheckOutcome(check_id, exc.status, truncate(exc.detail)), {}
        except Exception as exc:
            return (
                CheckOutcome(
                    check_id,
                    "failed",
                    truncate("unexpected {}: {}".format(type(exc).__name__, exc)),
                ),
                {},
            )
        if isinstance(result, tuple):
            outcome, data = result
            return outcome, data if isinstance(data, dict) else {}
        return result, {}

    pin_records = verify_pins(product_root, spec)
    artifacts = [
        {
            "path": record_item.path,
            "expected_sha256": record_item.expected_sha256,
            "actual_sha256": record_item.actual_sha256,
            "bytes": record_item.bytes,
            "status": record_item.status,
        }
        for record_item in pin_records
    ]
    pin_state = overall_pin_status(pin_records)
    if pin_state == "verified":
        record(
            CheckOutcome(
                "pinned_artifact_hashes",
                "passed",
                "all {} pinned artifacts match their expected SHA256 and byte "
                "length".format(len(pin_records)),
            )
        )
    elif pin_state == "blocked":
        missing = [item.path for item in pin_records if item.status == "missing"]
        record(
            CheckOutcome(
                "pinned_artifact_hashes",
                "blocked",
                truncate("missing pinned artifacts: {}".format(missing)),
            )
        )
    else:
        mismatched = [
            "{} (actual={})".format(item.path, item.actual_sha256)
            for item in pin_records
            if item.status == "hash_mismatch"
        ]
        unreadable = [
            item.path for item in pin_records if item.status == "unreadable"
        ]
        missing = [item.path for item in pin_records if item.status == "missing"]
        parts = []
        if mismatched:
            parts.append("hash mismatch: {}".format(mismatched))
        if unreadable:
            parts.append("unreadable: {}".format(unreadable))
        if missing:
            parts.append(
                "also missing, but observed corruption outranks missing "
                "prerequisites: {}".format(missing)
            )
        record(
            CheckOutcome(
                "pinned_artifact_hashes",
                "failed",
                truncate("pinned artifact corruption; " + "; ".join(parts)),
            )
        )

    docs = {}
    documents_ok = False
    if pin_state == "verified":
        load_errors = []
        load_missing = []
        for name in (
            "source_inventory",
            "force_wells",
            "splits",
            "split_policy",
            "label_schema",
            "preprocessing",
        ):
            try:
                docs[name] = load_json_document(product_root, name, spec)
            except VerifyDataError as exc:
                if exc.status == "blocked":
                    load_missing.append(exc.detail)
                else:
                    load_errors.append(exc.detail)
        if load_errors:
            record(
                CheckOutcome(
                    "pinned_documents_parse", "failed", truncate("; ".join(load_errors))
                )
            )
        elif load_missing:
            record(
                CheckOutcome(
                    "pinned_documents_parse",
                    "blocked",
                    truncate("; ".join(load_missing)),
                )
            )
        else:
            record(
                CheckOutcome(
                    "pinned_documents_parse",
                    "passed",
                    "all {} pinned JSON documents parse as objects".format(len(docs)),
                )
            )
            documents_ok = True

    if documents_ok:
        outcome = run_check(
            "contract_task_design_identity", check_contract_and_task_identity, docs
        )[0]
        record(outcome)
        outcome = run_check(
            "cross_file_hash_links", check_cross_file_hash_links, docs, spec
        )[0]
        record(outcome)
        outcome, data = run_check(
            "inventory_structure", check_inventory_structure, docs["force_wells"], spec
        )
        record(outcome)
        check_data[outcome.check_id] = data
        outcome, data = run_check(
            "split_structure_and_coverage",
            check_split_structure_and_coverage,
            docs["splits"],
            docs["force_wells"],
            docs["split_policy"],
            spec,
        )
        record(outcome)
        check_data[outcome.check_id] = data
        grouping_module = None
        try:
            grouping_module = load_pinned_helper_module(
                product_root, spec, "data/grouping.py", "_deepeye_verify_data_grouping"
            )
        except VerifyDataError as exc:
            record(CheckOutcome("whole_well_grouping", exc.status, truncate(exc.detail)))
        if grouping_module is not None:
            rows = docs["splits"].get("rows")
            rows = rows if isinstance(rows, list) else []
            outcome, data = run_check(
                "whole_well_grouping",
                check_whole_well_grouping,
                rows,
                grouping_module,
                spec,
                docs["preprocessing"].get("grouping_validation"),
            )
            record(outcome)
            check_data[outcome.check_id] = data
        outcome, data = run_check(
            "rank_split_reconstruction",
            check_rank_split_reconstruction,
            docs["splits"],
            spec,
        )
        record(outcome)
        check_data[outcome.check_id] = data
        outcome = run_check(
            "label_schema_alignment", check_label_schema_alignment, docs["label_schema"], spec
        )[0]
        record(outcome)
        outcome, data = run_check(
            "preprocessing_fit_identity",
            check_preprocessing_fit_identity,
            docs["preprocessing"],
            docs["force_wells"],
            docs["splits"],
            spec,
        )
        record(outcome)
        check_data[outcome.check_id] = data
        outcome = run_check(
            "preprocessing_statistics_metadata",
            check_preprocessing_statistics,
            docs["preprocessing"],
            spec,
        )[0]
        record(outcome)

    if pin_state == "verified":
        outcome, data = run_check(
            "archive_bytes_and_sha256", check_archive_identity, archive_path, spec
        )
        record(outcome)
        check_data[outcome.check_id] = data
        archive_outcome = outcome
    else:
        archive_outcome = CheckOutcome(
            "archive_bytes_and_sha256", "not_run", "skipped: pinned prerequisite unmet"
        )
        record(archive_outcome)
        check_data["archive_bytes_and_sha256"] = {
            "expected_file": spec.archive[0],
            "expected_sha256": spec.archive[2],
            "expected_bytes": spec.archive[1],
            "actual_file": None,
            "actual_sha256": None,
            "actual_bytes": None,
            "status": "not_checked",
        }

    record(
        CheckOutcome(
            "zip_member_and_las_parse_absence",
            "passed",
            "by construction this verifier never opens ZIP members and never "
            "parses LAS values; the archive is read as a raw byte stream only "
            "(current archive check status: {})".format(archive_outcome.status),
        )
    )
    record(
        CheckOutcome(
            "runtime_future_label_access",
            "not_run",
            "requires runtime future-label/truth-access instrumentation "
            "(missing full gate); the status is unknown and is not reported "
            "as zero",
        )
    )
    record(
        CheckOutcome(
            "real_sim_domain_separation",
            "not_run",
            "sensor_live acquisition runs and sim_em_v2 complete scenarios are "
            "not part of this offline foundation; domain separation is "
            "unverified here",
        )
    )
    if scope == "force-offline":
        record(
            CheckOutcome(
                "full_c01_prerequisite_gates",
                "not_run",
                "{} full-C01 gates are outside the force-offline scope; the "
                "offline checks cannot substitute for them".format(
                    len(MISSING_FULL_GATES)
                ),
            )
        )
    else:
        record(
            CheckOutcome(
                "full_c01_prerequisite_gates",
                "blocked",
                "full C01 verification is blocked; missing gates: {}".format(
                    "; ".join(MISSING_FULL_GATES)
                ),
            )
        )
    if output_display is None:
        record(
            CheckOutcome("output_write", "not_run", "stdout only (no --output path given)")
        )
    else:
        record(
            CheckOutcome(
                "output_write",
                "not_run",
                "--output requested; the CLI wrapper performs the atomic write "
                "after the report is built",
            )
        )

    return artifacts


def run_verification(
    product_root: Path,
    spec: VerificationSpec,
    *,
    scope: str,
    archive_path,
    output_display: object = None,
    python_version: object = None,
    generated_utc: object = None,
) -> tuple:
    """Run the requested scope and return (report_dict, exit_code).

    Data problems never raise: they surface as deterministic
    passed/failed/blocked/not_run check outcomes.  Exit codes: 0 only for
    the explicit force-offline scope with every offline check passed; 1 for
    invalid/corrupt input; 2 for blocked or missing prerequisites.  When a
    missing prerequisite and an observed corruption coexist, the report is
    failed (1) and lists both, never a silent block.

    Context gate: only the immutable canonical ``PRODUCTION_SPEC`` runs
    with the production label.  Any other spec runs as a synthetic fixture
    context (``production_provenance=false`` in the report); a
    production-labelled spec that does not equal the canonical object is
    rejected (exit 1) before any pinned byte, helper module or archive is
    touched.
    """

    checks: dict = {}
    check_data: dict = {}
    context = classify_spec(spec)
    artifacts: list = []
    if context == SPEC_CONTEXT_FORGED:
        checks["spec_context"] = CheckOutcome(
            "spec_context",
            "failed",
            "rejected: a production-labelled spec must exactly equal the "
            "immutable canonical PRODUCTION_SPEC (fields, pins, counts and "
            "provenance); no pinned data, helper module or archive was read",
        )
    else:
        checks["spec_context"] = CheckOutcome(
            "spec_context",
            "passed",
            "context {}; production_provenance={}".format(
                context, context == SPEC_CONTEXT_PRODUCTION
            ),
        )
        artifacts = _run_checks(
            product_root,
            spec,
            scope=scope,
            archive_path=archive_path,
            output_display=output_display,
            checks=checks,
            check_data=check_data,
        )

    statuses = [outcome.status for outcome in checks.values()]
    if "failed" in statuses:
        status, exit_code = "failed", 1
    elif "blocked" in statuses:
        status, exit_code = "blocked", 2
    elif scope == "force-offline" and context == SPEC_CONTEXT_PRODUCTION:
        status, exit_code = "passed_offline_identity_consistency_only", 0
    elif scope == "force-offline":
        status, exit_code = "synthetic_fixture_checks_passed", 0
    else:
        status, exit_code = "blocked", 2

    inventory_counts = check_data.get("inventory_structure", {})
    split_counts = check_data.get("split_structure_and_coverage", {})
    pre_counts = check_data.get("preprocessing_fit_identity", {})
    counts = {
        "inventory_members": inventory_counts.get("members"),
        "well_rows_total": inventory_counts.get("rows_total"),
        "curves_total": inventory_counts.get("curves_total"),
        "parent_roots": split_counts.get("roots"),
        "group_counts": split_counts.get("group_counts"),
        "well_counts": split_counts.get("well_counts"),
        "train_rows": split_counts.get("train_rows"),
        "fitting_wells": pre_counts.get("fitting_wells"),
        "fitting_rows": pre_counts.get("fitting_rows"),
    }
    archive_data = check_data.get("archive_bytes_and_sha256", {})
    report = {
        "schema": 1,
        "kind": "deepeye-verify-data-report",
        "generated_utc": generated_utc or utc_now(),
        "tool": {"path": "tools/verify_data.py", "sha256": tool_sha256()},
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "design_commit": DESIGN_COMMIT,
        "contract": {
            "id": CONTRACT_ID,
            "revision": CONTRACT_REVISION,
            "source_commit": CONTRACT_SOURCE_COMMIT,
            "requirements_sha256": CONTRACT_REQUIREMENTS_SHA256,
        },
        "spec": {
            SPEC_CONTEXT_PRODUCTION: "production",
            SPEC_CONTEXT_SYNTHETIC: "synthetic_fixture",
            SPEC_CONTEXT_FORGED: "rejected_forged_production",
        }[context],
        "requested_spec_name": spec.name,
        "production_provenance": context == SPEC_CONTEXT_PRODUCTION,
        "scope": scope,
        "status": status,
        "exit_code": exit_code,
        "product_card_C01": "not_run",
        "software_scope": (
            "offline provenance/identity/consistency only; no live sensor, "
            "sim_em_v2 scenario or runtime verification"
        ),
        "command": {
            "entrypoint": "tools/verify_data.py",
            "scope": scope,
            "archive_file": Path(archive_path).name if archive_path is not None else None,
            "output": output_display,
            "python": python_version,
        },
        "provenance": {
            "dataset": spec.dataset_label,
            "source_domain": spec.domain,
            "doi": spec.doi,
            "record_url": spec.record_url,
            "authors_repository": spec.repository_url,
            "authors_repository_commit": spec.repository_commit,
            "record_license_id": spec.license_id,
            "original_description_license_text": spec.original_license_text,
            "original_description_license_note": (
                "Verbatim licensing text from the pinned source record, kept "
                "separately from the deposited resource license id."
            ),
            "archive_file": spec.archive[0],
            "archive_bytes": spec.archive[1],
            "archive_sha256": spec.archive[2],
            "raw_archive_in_product_repository": False,
        },
        "artifacts": artifacts,
        "archive": archive_data,
        "counts": counts,
        "checks": [
            {
                "id": check_id,
                "status": checks[check_id].status
                if check_id in checks
                else "not_run",
                "detail": checks[check_id].detail
                if check_id in checks
                else "skipped: prerequisite unmet",
            }
            for check_id in CHECK_IDS
        ],
        "missing_full_gates": list(MISSING_FULL_GATES),
        "unverified": {
            "runtime_future_label_access": "unknown_not_run",
            "real_sim_domain_separation": "unknown_not_run",
            "sensor_live_run_manifest": "unknown_not_run",
            "sim_em_v2_scenario_splits": "unknown_not_run",
        },
        "limitations": list(LIMITATIONS),
        "software_facts": {
            "zip_members_opened": 0,
            "las_values_parsed": 0,
            "statistics_recomputed": False,
            "network_calls": 0,
            "subprocesses_spawned": 0,
        },
    }
    return report, exit_code


class _UsageError(Exception):
    """Raised instead of argparse's SystemExit for deterministic output."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):  # noqa: D401 - argparse hook
        raise _UsageError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="tools/verify_data.py",
        description=(
            "C01 offline provenance/identity verifier (software-only; the C01 "
            "product card remains not_run)"
        ),
    )
    parser.add_argument(
        "--scope",
        choices=("full_c01", "force-offline"),
        default="full_c01",
        help=(
            "full_c01 (default) runs the full C01 scope and is blocked while "
            "the required gates are missing; force-offline runs only the "
            "partial offline identity/consistency check"
        ),
    )
    parser.add_argument(
        "--archive",
        default=None,
        help="path of the FORCE ZIP; required with --scope force-offline",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "optional path for the report JSON (atomic write via temporary "
            "sibling and replace); stdout always receives identical content"
        ),
    )
    return parser


def _skeleton_report(scope: str, output_display: object = None) -> dict:
    return {
        "schema": 1,
        "kind": "deepeye-verify-data-report",
        "generated_utc": utc_now(),
        "tool": {"path": "tools/verify_data.py", "sha256": tool_sha256()},
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "design_commit": DESIGN_COMMIT,
        "contract": {
            "id": CONTRACT_ID,
            "revision": CONTRACT_REVISION,
            "source_commit": CONTRACT_SOURCE_COMMIT,
            "requirements_sha256": CONTRACT_REQUIREMENTS_SHA256,
        },
        "spec": "production",
        "scope": scope,
        "status": "usage_error",
        "exit_code": 2,
        "product_card_C01": "not_run",
        "software_scope": (
            "offline provenance/identity/consistency only; no live sensor, "
            "sim_em_v2 scenario or runtime verification"
        ),
        "command": {
            "entrypoint": "tools/verify_data.py",
            "scope": scope,
            "archive_file": None,
            "output": output_display,
            "python": "{}.{}.{}".format(*sys.version_info[:3]),
        },
        "artifacts": [],
        "archive": {},
        "counts": {},
        "checks": [],
        "missing_full_gates": list(MISSING_FULL_GATES),
        "unverified": {
            "runtime_future_label_access": "unknown_not_run",
            "real_sim_domain_separation": "unknown_not_run",
            "sensor_live_run_manifest": "unknown_not_run",
            "sim_em_v2_scenario_splits": "unknown_not_run",
        },
        "limitations": list(LIMITATIONS),
        "software_facts": {
            "zip_members_opened": 0,
            "las_values_parsed": 0,
            "statistics_recomputed": False,
            "network_calls": 0,
            "subprocesses_spawned": 0,
        },
    }


def write_text_atomic(path, text: str) -> None:
    """Write ``text`` via a temporary sibling then os.replace."""

    path = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _protected_output_problem(
    output, product_root: Path, spec: VerificationSpec, archive_path, entrypoint=None
) -> object:
    """Return a failure detail when ``--output`` targets a verifier input.

    The protected set is exactly what this run reads: all pinned
    artifacts, the selected archive (when one was given) and this
    entrypoint.  The output path is resolved (``..`` spellings and
    symlinks/junctions are canonicalized) and, when both files exist,
    compared with ``os.path.samefile`` so hardlink aliases are caught too.
    """

    output_path = Path(output)

    def canonical(path) -> Path:
        try:
            return Path(path).resolve()
        except OSError:
            return Path(os.path.abspath(os.fspath(path)))

    protected = [
        ("pinned artifact", product_root / relative) for relative in sorted(spec.pins)
    ]
    if archive_path is not None:
        protected.append(("selected archive", Path(archive_path)))
    protected.append(
        (
            "verifier entrypoint",
            Path(entrypoint) if entrypoint is not None else Path(__file__),
        )
    )

    output_canonical = canonical(output_path)
    for label, protected_path in protected:
        protected_path = Path(protected_path)
        if output_canonical == canonical(protected_path):
            return (
                "refusing to write the report over a verifier input ({}): "
                "output {} resolves to {}, the same path as the protected "
                "input".format(label, output_path, output_canonical)
            )
        try:
            both_exist = output_path.exists() and protected_path.exists()
        except OSError:
            both_exist = False
        if both_exist:
            try:
                same = os.path.samefile(output_path, protected_path)
            except OSError:
                same = False
            if same:
                return (
                    "refusing to write the report over a verifier input ({}): "
                    "output {} and {} are the same underlying file "
                    "(hardlink or alias)".format(label, output_path, protected_path)
                )
    return None


def _output_probe(output: Path) -> object:
    """Return None when the output directory accepts a temporary sibling."""

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=Path(output).name + ".", suffix=".probe.tmp", dir=str(Path(output).parent)
        )
    except OSError as exc:
        return "output directory not writable: {}".format(exc)
    os.close(descriptor)
    try:
        os.unlink(temporary_name)
    except OSError:
        pass
    return None


def main(argv=None) -> int:
    _configure_stdout()
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except _UsageError as exc:
        report = _skeleton_report("unknown")
        report["checks"] = [
            {"id": "cli_arguments", "status": "failed", "detail": str(exc)}
        ]
        report["error"] = str(exc)
        sys.stdout.write(render_report(report))
        sys.stderr.write("usage error: {}\n".format(exc))
        return 2
    except SystemExit as exc:
        return 0 if not exc.code else 2
    if args.archive is not None and args.scope != "force-offline":
        message = "--archive requires --scope force-offline"
        report = _skeleton_report(args.scope)
        report["checks"] = [
            {"id": "cli_arguments", "status": "failed", "detail": message}
        ]
        report["error"] = message
        sys.stdout.write(render_report(report))
        sys.stderr.write("usage error: {}\n".format(message))
        return 2

    product_root = product_root_from_file()
    # No implicit archive location: without an explicit --archive the
    # selected archive stays None and the report states the missing
    # prerequisite truthfully (blocked, exit 2) instead of guessing a
    # repository path.  Passing an archive path explicitly remains the
    # caller decision for the force-offline scope.
    archive_path = Path(args.archive) if args.archive is not None else None
    output = Path(args.output) if args.output is not None else None
    output_display = display_path(output, product_root) if output is not None else None
    python_version = "{}.{}.{}".format(*sys.version_info[:3])
    try:
        report, exit_code = run_verification(
            product_root,
            PRODUCTION_SPEC,
            scope=args.scope,
            archive_path=archive_path,
            output_display=output_display,
            python_version=python_version,
        )
    except Exception as exc:  # deterministic failure instead of a traceback
        message = "unexpected {}: {}".format(type(exc).__name__, exc)
        report = _skeleton_report(args.scope, output_display=output_display)
        report["status"] = "failed"
        report["exit_code"] = 1
        report["checks"] = [
            {"id": "unexpected_error", "status": "failed", "detail": message}
        ]
        report["error"] = message
        sys.stdout.write(render_report(report))
        return 1
    write_target = None
    if output is not None:
        problem = _protected_output_problem(
            output, product_root, PRODUCTION_SPEC, archive_path
        )
        if problem is None:
            problem = _output_probe(output)
        if problem is None:
            set_check(
                report,
                "output_write",
                "passed",
                "atomically written to {} (temporary sibling then replace); "
                "stdout and file content identical".format(output_display),
            )
            write_target = output
        else:
            set_check(report, "output_write", "failed", problem)
            report["status"] = "failed"
            report["exit_code"] = 1
            report["error"] = problem
            exit_code = 1
    text = render_report(report)
    if write_target is not None:
        try:
            write_text_atomic(write_target, text)
        except Exception as exc:
            message = "atomic write failed: {}: {}".format(type(exc).__name__, exc)
            set_check(report, "output_write", "failed", message)
            report["status"] = "failed"
            report["exit_code"] = 1
            report["error"] = message
            exit_code = 1
            text = render_report(report)
    sys.stdout.write(text)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

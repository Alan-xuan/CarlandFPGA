"""Bounded train-only FORCE four-channel coverage audit and diagnostic replay.

Private evidence helper for task DEEPEYE-C-TRAIN-COVERAGE-20261015/v1
(work C-train-only-four-curve-coverage-replay-v1, job
child-c7dcf18e89bf4132918255a66d6f15b2).  Python standard library only.

This module reads ONLY the fixed 82 training members of the pinned FORCE 2020
archive, classifies per-row coverage of the four frozen curve channels
(GR, RHOB, NPHI, RDEP), and replays exactly one 128-row all-four-effective-
valid run through the accepted ai_pc/model/curve_input API using the
committed train statistics.  It is offline data preparation and coverage
evidence:

  * NOT C01/C02 acceptance, model training, validation/test evaluation,
    score selection or runtime truth isolation;
  * NOT real sensor evidence; four-channel software replay coverage only;
  * no product/source/manifest/split/scaler bytes are ever written.

Modes:
  run-audit       perform the audit, print the payload JSON on stdout
  write-evidence  capture a run-audit subprocess and write audit.json/log
  check-evidence  read-only consistency check of the two evidence files

All helper source for this job lives in this file and
test_scan_train_curves.py; no other helper files exist.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
import zipfile

TASK_ID = "DEEPEYE-C-TRAIN-COVERAGE-20261015"
TASK_VERSION = 1
WORK_ID = "C-train-only-four-curve-coverage-replay-v1"
IMPLEMENTATION_JOB = "child-c7dcf18e89bf4132918255a66d6f15b2"
INSTANCE_ID = "deepseek-c-15"
ROUTE = "deepseek"
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014/revision1"
CONTRACT_SOURCE = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"
REQUIREMENTS_SHA = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"

CHANNELS = ("GR", "RHOB", "NPHI", "RDEP")
RDEP = "RDEP"
WINDOW = 128
CHUNK = 1 << 20

SCOPE_NOTE = (
    "Bounded train-only FORCE four-channel coverage audit and one diagnostic "
    "128-row causal replay for the frozen GR/RHOB/NPHI/RDEP curve profile. "
    "This is offline data preparation/evidence only: it is NOT C01/C02 "
    "acceptance, model training, validation/test evaluation, score selection, "
    "runtime truth isolation or real sensor evidence.  All product, "
    "simulation, synthesis, implementation, board and system cards remain "
    "not_run."
)

LIMITS = [
    "Scope: the fixed 82 training members of the pinned FORCE 2020 archive "
    "only; validation and test wells were never opened (guarded) and no "
    "product/source/manifest/split/scaler file was written.",
    "Missing/nonfinite diagnosis is offline training metadata only; it never "
    "changes the frozen split, the evaluation cohort or the committed "
    "statistics, and no refitting or resampling happened.",
    "The diagnostic replay is four-channel software coverage evidence from "
    "committed train statistics, not lithology/water-hazard performance, not "
    "a model-quality statement and not real sensor capability.",
    "0 heldout (validation/test) member opens and 0 numeric parses of "
    "non-selected tokens (labels/confidence/depth stay opaque strings) are "
    "source-instrumented facts for this offline scan only; they are not a "
    "substitute for runtime future-label verification.",
    "All product and hardware cards remain not_run; the director retains all "
    "interpretation and acceptance decisions.",
]


class AuditError(RuntimeError):
    """Deterministic audit failure; never fabricates coverage."""


class GuardViolation(AuditError):
    """A ZIP member outside the fixed train set was requested."""


@dataclasses.dataclass(frozen=True)
class Expectations:
    label: str
    archive_sha256: str
    archive_bytes: int
    splits_sha256: str
    wells_sha256: str
    preprocessing_sha256: str
    train_wells: int
    train_parents: int
    train_rows: int
    source_domain: str


PRODUCTION_EXPECTATIONS = Expectations(
    label="production_frozen_pins",
    archive_sha256="042ef1d473100dc12768cae7107a8cead071a394f137af3bc1ddaf8a5d1b8dda",
    archive_bytes=169785172,
    splits_sha256="f10ddb8f37e6bdf7c9663eed45d0f6554ef8992899724013a7e487ad3e3cef91",
    wells_sha256="ace9a0eb9930f19c6b8125e151d07346fb23029b1455eac04964d15b97461e59",
    preprocessing_sha256="cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef",
    train_wells=82,
    train_parents=81,
    train_rows=1634292,
    source_domain="force_2020_public_lithology",
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path, chunk=CHUNK):
    """Stream a file and return (hexdigest, byte count)."""
    hasher = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            hasher.update(block)
            size += len(block)
    return hasher.hexdigest(), size


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def load_product_modules(product_dir):
    """Load the three accepted product modules by explicit file path."""
    paths = {
        "force_inventory": os.path.join(product_dir, "data", "force_inventory.py"),
        "grouping": os.path.join(product_dir, "data", "grouping.py"),
        "curve_input": os.path.join(product_dir, "ai_pc", "model", "curve_input.py"),
    }
    modules = {}
    sources = {}
    for name in sorted(paths):
        path = paths[name]
        if not os.path.isfile(path):
            raise AuditError("product module missing: " + path)
        data = read_bytes(path)
        sources[name] = {"path": path, "sha256": sha256_bytes(data), "bytes": len(data)}
        spec = importlib.util.spec_from_file_location("deepeye_audit_" + name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    modules["sources"] = sources
    return modules


def _parse_null_text(text):
    if text is None:
        return None
    tokens = text.split()
    if not tokens:
        return None
    try:
        value = float(tokens[0])
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _check_member_path(name):
    if not name or name.endswith("/") or "\\" in name or ":" in name or name.startswith("/"):
        raise AuditError("unsafe member path: %r" % (name,))
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise AuditError("unsafe member path: %r" % (name,))
    if not name.lower().endswith(".las"):
        raise AuditError("unsupported member extension: %r" % (name,))


class OpenJournal:
    """Records every guarded member open and every heldout open attempt."""

    def __init__(self):
        self.opened = []
        self.heldout_attempts = []


class GuardedZip(zipfile.ZipFile):
    """ZipFile whose open() serves only the fixed training member set."""

    def __init__(self, file, mode="r", *, allowed, journal):
        if mode != "r":
            raise ValueError("GuardedZip is read-only")
        super().__init__(file, "r")
        self._allowed = frozenset(allowed)
        self._journal = journal

    def open(self, name, mode="r", pwd=None, *, force_zip64=False):
        if mode != "r":
            raise ValueError("GuardedZip.open is read-only")
        if name not in self._allowed:
            self._journal.heldout_attempts.append(name)
            raise GuardViolation("member %r is outside the fixed train set" % (name,))
        self._journal.opened.append(name)
        return super().open(name, mode=mode, pwd=pwd, force_zip64=force_zip64)


class HashingStream:
    """Wrap a binary stream and SHA256-hash every byte read through it."""

    def __init__(self, inner):
        self._inner = inner
        self.hasher = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size=-1):
        data = self._inner.read(size)
        if data:
            self.hasher.update(data)
            self.bytes_read += len(data)
        return data
def _empty_channel():
    return {
        "present": False,
        "rawvalid": 0,
        "effectivevalid": 0,
        "null": 0,
        "nonfinite": 0,
        "nonpositive": 0,
        "absent_rows": 0,
    }


def parse_member(stream, member_name, member_size_bytes, modules, capture_range=None):
    """Stream one LAS member and classify the four selected channels only.

    Only the selected curve columns (GR, RHOB, NPHI, RDEP) are ever converted
    to numbers.  Every other data token - depth, labels, confidence,
    coordinates, anything else - stays an opaque string: its token count is
    validated but its value is never interpreted numerically.  Blank lines
    and comment lines are skipped exactly as the accepted inventory does;
    CRCRLF terminators yield the documented extra blank line.

    Returns (result dict, captured) where captured rows are
    (zero_based_row_index, values tuple, all4_effectivevalid) for row indexes
    inside capture_range; missing values are None.
    """
    inventory = modules["force_inventory"]
    reader = HashingStream(stream)
    section = None
    version = None
    wrap = None
    well_fields = {}
    curves = []
    null_value = None
    row_index = -1
    data_started = False

    channels = {name: _empty_channel() for name in CHANNELS}
    channel_index = {name: None for name in CHANNELS}
    all4_flags = bytearray()
    selected_parse_attempts = 0
    captured = []
    capture_lo = capture_hi = None
    if capture_range is not None:
        capture_lo, capture_hi = capture_range

    def fail(message, line_number=None):
        if line_number is None:
            raise AuditError("%s: %s" % (member_name, message))
        raise AuditError("%s line %d: %s" % (member_name, line_number, message))

    for line_number, raw_line in enumerate(inventory.iter_las_lines(reader, CHUNK), 1):
        try:
            line = raw_line.decode("ascii")
        except UnicodeDecodeError:
            fail("non-ASCII byte in line", line_number)
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("~"):
            body = stripped[1:].strip()
            section = body.split()[0].lower() if body else ""
            if section in ("ascii", "a"):
                if not curves:
                    fail("ASCII data section before curve definitions", line_number)
                if null_value is None:
                    null_value = _parse_null_text(well_fields.get("NULL"))
                if null_value is None:
                    fail("NULL sentinel missing before data section", line_number)
                if not data_started:
                    found = {}
                    for index, (mnemonic, _unit) in enumerate(curves):
                        key = mnemonic.upper()
                        if key in CHANNELS:
                            found[key] = index
                    for name in CHANNELS:
                        if name in found:
                            channels[name]["present"] = True
                            channel_index[name] = found[name]
                        else:
                            channel_index[name] = None
                    data_started = True
            continue
        if section == "version":
            mnemonic, _unit, value, _description = inventory.parse_section_line(stripped)
            key = mnemonic.upper()
            if key == "VERS":
                version = value
            elif key == "WRAP":
                wrap = value
            continue
        if section == "well":
            mnemonic, _unit, value, _description = inventory.parse_section_line(stripped)
            well_fields[mnemonic.upper()] = value
            continue
        if section == "curve":
            if row_index >= 0:
                fail("curve definition after ASCII data rows", line_number)
            mnemonic, _unit, _value, _description = inventory.parse_section_line(stripped)
            if not mnemonic:
                fail("empty curve mnemonic", line_number)
            if any(existing.upper() == mnemonic.upper() for existing, _unit2 in curves):
                fail("duplicate curve mnemonic %r" % mnemonic, line_number)
            curves.append((mnemonic, _unit))
            continue
        if section in ("ascii", "a"):
            tokens = stripped.split()
            if len(tokens) != len(curves):
                fail("row has %d values for %d curves" % (len(tokens), len(curves)), line_number)
            row_index += 1
            row_ok = True
            row_values = []
            for name in CHANNELS:
                index = channel_index[name]
                if index is None:
                    channels[name]["absent_rows"] += 1
                    row_values.append(None)
                    row_ok = False
                    continue
                counters = channels[name]
                token = tokens[index]
                selected_parse_attempts += 1
                try:
                    value = float(token)
                except ValueError:
                    fail("malformed numeric token %r in selected %s column" % (token, name), line_number)
                if not math.isfinite(value):
                    counters["nonfinite"] += 1
                    row_values.append(None)
                    row_ok = False
                    continue
                if value == null_value:
                    counters["null"] += 1
                    row_values.append(None)
                    row_ok = False
                    continue
                counters["rawvalid"] += 1
                if name == RDEP and value <= 0.0:
                    counters["nonpositive"] += 1
                    row_values.append(None)
                    row_ok = False
                    continue
                counters["effectivevalid"] += 1
                row_values.append(value)
            all4_flags.append(1 if row_ok else 0)
            if capture_lo is not None and capture_lo <= row_index <= capture_hi:
                captured.append((row_index, tuple(row_values), row_ok))
            continue
        # parameter/other/unknown sections: content lines are not records
        continue

    if version is None:
        fail("missing VERS line in version section")
    if version != inventory.SUPPORTED_VERSION:
        fail("unsupported LAS version %r (expected %s)" % (version, inventory.SUPPORTED_VERSION))
    if wrap is None:
        fail("missing WRAP line in version section")
    if wrap.upper() != "NO":
        fail("unsupported WRAP %r (row semantics change; refused)" % (wrap,))
    if not curves:
        fail("no curve definitions")
    if row_index < 0:
        fail("no ASCII data rows")
    uwi = well_fields.get("UWI", "")
    if not uwi:
        fail("missing or empty UWI in well section")
    if reader.bytes_read != member_size_bytes:
        fail(
            "member byte count %d does not match declared size %d"
            % (reader.bytes_read, member_size_bytes)
        )

    result = {
        "member": member_name,
        "member_size_bytes": member_size_bytes,
        "member_sha256": reader.hasher.hexdigest(),
        "rows": row_index + 1,
        "vers": version,
        "wrap": wrap,
        "uwi": uwi,
        "channels": channels,
        "all4_rows": sum(all4_flags),
        "selected_numeric_parse_attempts": selected_parse_attempts,
    }
    return result, captured, all4_flags


def first_run_reaching(flags, length=WINDOW):
    """(first_start, max_run_len): smallest s with flags[s:s+length] all true."""
    first_start = None
    max_run = 0
    run_start = None
    for index, flag in enumerate(flags):
        if flag:
            if run_start is None:
                run_start = index
            run_len = index - run_start + 1
            if run_len > max_run:
                max_run = run_len
            if first_start is None and run_len >= length:
                first_start = run_start
        else:
            run_start = None
    return first_start, max_run


def _expected_features(rows_so_far, stats):
    """Independent right-aligned expected window for one observation prefix.

    Uses identity for GR/RHOB/NPHI and log10 for positive RDEP, then the
    committed mean/effective_scale; the production normalisation function is
    never called here.
    """
    step = len(rows_so_far)
    padding = WINDOW - step
    channels = []
    for index in range(4):
        name, mean, scale = stats[index]
        column = [0.0] * padding
        for _sequence, values in rows_so_far:
            raw = values[index]
            transformed = math.log10(raw) if name == RDEP else raw
            column.append((transformed - mean) / scale)
        channels.append(tuple(column))
    for _index in range(4):
        channels.append(tuple([0.0] * padding + [1.0] * step))
    return tuple(channels)

def _git(cwd, *args):
    command = ["git", "-C", cwd] + list(args)
    try:
        proc = subprocess.run(command, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "exit": None, "stdout": "", "stderr": str(exc)}
    return {
        "command": command,
        "exit": proc.returncode,
        "stdout": proc.stdout.decode("utf-8", "replace").strip(),
        "stderr": proc.stderr.decode("utf-8", "replace").strip(),
    }


def run_audit(archive_path, product_dir, expectations=PRODUCTION_EXPECTATIONS, modules=None, replay=True):
    """Run the bounded train-only coverage audit and return the payload dict.

    The CLI always calls this with the frozen PRODUCTION_EXPECTATIONS; the
    parameters exist so unit tests can run the identical machinery on
    synthetic fixtures that are clearly labelled as such.
    """
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    archive_path = os.path.abspath(archive_path)
    product_dir = os.path.abspath(product_dir)
    if expectations.label == PRODUCTION_EXPECTATIONS.label and expectations != PRODUCTION_EXPECTATIONS:
        raise AuditError("refusing a production-labelled expectations object that differs from the frozen pins")
    if modules is None:
        modules = load_product_modules(product_dir)
    module_sources = modules["sources"]

    # ---- pinned inputs: hash the archive bytes before any ZipFile access ----
    archive_sha, archive_size = sha256_file(archive_path)
    if archive_size != expectations.archive_bytes or archive_sha != expectations.archive_sha256:
        raise AuditError(
            "archive identity mismatch: bytes=%d sha256=%s" % (archive_size, archive_sha)
        )
    splits_bytes = read_bytes(os.path.join(product_dir, "data", "splits.json"))
    wells_bytes = read_bytes(os.path.join(product_dir, "data", "force_wells.json"))
    preproc_bytes = read_bytes(os.path.join(product_dir, "data", "preprocessing.json"))
    for name, data, expected in (
        ("splits.json", splits_bytes, expectations.splits_sha256),
        ("force_wells.json", wells_bytes, expectations.wells_sha256),
        ("preprocessing.json", preproc_bytes, expectations.preprocessing_sha256),
    ):
        actual = sha256_bytes(data)
        if actual != expected:
            raise AuditError("%s sha256 %s does not match the pinned %s" % (name, actual, expected))
    splits_doc = json.loads(splits_bytes.decode("utf-8"))
    wells_doc = json.loads(wells_bytes.decode("utf-8"))
    preproc_doc = json.loads(preproc_bytes.decode("utf-8"))

    # ---- split / grouping cross-checks (accepted grouping logic, read-only) ----
    rows = splits_doc.get("rows")
    if not isinstance(rows, list) or not rows:
        raise AuditError("splits.json rows missing")
    try:
        report = modules["grouping"].validate_split_assignments(rows)
    except Exception as exc:
        raise AuditError("grouping validation failed: %s" % exc)
    split_rows = {}
    for row in rows:
        split_rows[row["split"]] = split_rows.get(row["split"], 0) + 1
    declared_well_counts = splits_doc.get("well_counts")
    if declared_well_counts is not None and dict(declared_well_counts) != split_rows:
        raise AuditError(
            "computed split well counts %r do not match the splits.json well_counts %r"
            % (split_rows, declared_well_counts)
        )
    train_rows_list = [row for row in rows if row["split"] == "train"]
    train_members = sorted(row["member"] for row in train_rows_list)
    if len(train_members) != expectations.train_wells or len(set(train_members)) != expectations.train_wells:
        raise AuditError(
            "train well count %d (unique %d) != pinned %d"
            % (len(train_members), len(set(train_members)), expectations.train_wells)
        )
    train_parents = len({row["root_id"] for row in train_rows_list})
    if train_parents != expectations.train_parents:
        raise AuditError("train parent count %d != pinned %d" % (train_parents, expectations.train_parents))
    domain_summary = report.domains.get(expectations.source_domain)
    if domain_summary is None:
        raise AuditError("grouping report has no domain %r" % (expectations.source_domain,))
    recorded_grouping = preproc_doc.get("grouping_validation")
    recorded_grouping_reproduced = None
    if isinstance(recorded_grouping, dict):
        recorded_grouping_reproduced = (
            recorded_grouping.get("rows") == len(rows)
            and recorded_grouping.get("root_count") == report.root_count
            and dict(recorded_grouping.get("split_rows", {})) == split_rows
        )
        if not recorded_grouping_reproduced:
            raise AuditError("grouping report does not reproduce the recorded preprocessing grouping_validation")

    # ---- inventory identity for the fixed train set ----
    wells_records = wells_doc.get("wells")
    if not isinstance(wells_records, list) or not wells_records:
        raise AuditError("force_wells.json wells missing")
    inventory_by_member = {}
    for record in wells_records:
        member = record.get("member")
        if member in inventory_by_member:
            raise AuditError("duplicate member %r in force_wells.json" % (member,))
        inventory_by_member[member] = record
    train_rows_total = 0
    for row in train_rows_list:
        record = inventory_by_member.get(row["member"])
        if record is None:
            raise AuditError("train member %s missing from the pinned inventory" % row["member"])
        if record["member_sha256"] != row["member_sha256"]:
            raise AuditError("member sha mismatch between splits and inventory for %s" % row["member"])
        train_rows_total += int(record["rows"])
    if train_rows_total != expectations.train_rows:
        raise AuditError("train data rows %d != pinned %d" % (train_rows_total, expectations.train_rows))
    fitting = preproc_doc.get("fitting_wells")
    if isinstance(fitting, list):
        fitting_members = sorted(entry["member"] for entry in fitting)
        if fitting_members != train_members:
            raise AuditError("preprocessing fitting_wells set does not equal the fixed train well set")
        for entry in fitting:
            record = inventory_by_member.get(entry["member"])
            if record is None or record["member_sha256"] != entry["member_sha256"]:
                raise AuditError("fitting_wells sha mismatch for %s" % entry["member"])

    # ---- guarded scan of the fixed training members (sorted, once each) ----
    guard = OpenJournal()
    well_results = []
    flags_by_member = {}
    expected_parse_attempts = 0
    with GuardedZip(archive_path, allowed=train_members, journal=guard) as zf:
        names = zf.namelist()
        if len(names) != len(set(names)):
            raise AuditError("duplicate members in the ZIP central directory")
        for member in train_members:
            _check_member_path(member)
            if member not in names:
                raise AuditError("train member %s is absent from the archive" % member)
        for member in train_members:
            record = inventory_by_member[member]
            info = zf.getinfo(member)
            if info.file_size != int(record["member_size_bytes"]):
                raise AuditError("member size mismatch for %s" % member)
            stream = zf.open(member)
            error = None
            result = None
            captured = None
            flags = None
            try:
                result, captured, flags = parse_member(stream, member, info.file_size, modules)
            except zipfile.BadZipFile as exc:
                error = "member %s failed ZIP CRC/deflate verification: %s" % (member, exc)
            finally:
                try:
                    stream.close()
                except zipfile.BadZipFile as exc:
                    if error is None:
                        error = "member %s failed ZIP CRC-32 verification on close: %s" % (member, exc)
            if error is not None:
                raise AuditError(error)
            if result["member_sha256"] != record["member_sha256"]:
                raise AuditError("member uncompressed sha256 mismatch for %s" % member)
            if result["rows"] != int(record["rows"]):
                raise AuditError(
                    "member rowcount mismatch for %s: %d != %d"
                    % (member, result["rows"], int(record["rows"]))
                )
            curve_by_mnemonic = {}
            for curve in record.get("curves", []):
                key = curve["mnemonic"].upper()
                if key in CHANNELS and key not in curve_by_mnemonic:
                    curve_by_mnemonic[key] = curve
            for name in CHANNELS:
                counters = result["channels"][name]
                curve = curve_by_mnemonic.get(name)
                if curve is not None:
                    if counters["null"] != curve["null_count"]:
                        raise AuditError("inventory null-count mismatch for %s %s" % (member, name))
                    if counters["rawvalid"] != curve["nonmissing_count"]:
                        raise AuditError("inventory valid-count mismatch for %s %s" % (member, name))
                elif counters["present"] or counters["absent_rows"] != result["rows"]:
                    raise AuditError("absent-channel bookkeeping mismatch for %s %s" % (member, name))
            flags_by_member[member] = flags
            expected_parse_attempts += result["rows"] * sum(
                1 for name in CHANNELS if result["channels"][name]["present"]
            )
            well_results.append(result)

    total_attempts = sum(result["selected_numeric_parse_attempts"] for result in well_results)
    if total_attempts != expected_parse_attempts:
        raise AuditError(
            "selected-column parse instrumentation mismatch: %d != %d"
            % (total_attempts, expected_parse_attempts)
        )

    # ---- aggregates and per-channel bookkeeping ----
    aggregate = {}
    total_rows_measured = 0
    for result in well_results:
        total_rows_measured += result["rows"]
    for name in CHANNELS:
        agg = {
            "present_wells": 0,
            "rawvalid": 0,
            "effectivevalid": 0,
            "null": 0,
            "nonfinite": 0,
            "nonpositive": 0,
            "absent_rows": 0,
        }
        for result in well_results:
            counters = result["channels"][name]
            if counters["present"]:
                agg["present_wells"] += 1
            for key in ("rawvalid", "effectivevalid", "null", "nonfinite", "nonpositive", "absent_rows"):
                agg[key] += counters[key]
        accounted = (
            agg["rawvalid"]
            + agg["null"]
            + agg["nonfinite"]
            + agg["absent_rows"]
        )
        if name == RDEP:
            if agg["effectivevalid"] != agg["rawvalid"] - agg["nonpositive"]:
                raise AuditError("RDEP effectivevalid != rawvalid - nonpositive")
        elif agg["effectivevalid"] != agg["rawvalid"]:
            raise AuditError("channel %s effectivevalid != rawvalid" % name)
        if accounted != total_rows_measured:
            raise AuditError(
                "channel %s category accounting %d != measured rows %d"
                % (name, accounted, total_rows_measured)
            )
        aggregate[name] = agg

    # ---- agreement with the accepted preprocessing statistics ----
    channels_doc = preproc_doc.get("channels")
    if not isinstance(channels_doc, list) or [entry.get("name") for entry in channels_doc] != list(CHANNELS):
        raise AuditError("preprocessing channels do not match the frozen curve order")
    reconciliation = {}
    for index, name in enumerate(CHANNELS):
        entry = channels_doc[index]
        counts = entry.get("counts")
        if not isinstance(counts, dict):
            raise AuditError("preprocessing channel %s counts missing" % name)
        agg = aggregate[name]
        row = {
            "preprocessing_valid": counts.get("valid"),
            "audit_effectivevalid": agg["effectivevalid"],
            "valid_match": counts.get("valid") == agg["effectivevalid"] == entry.get("valid_samples"),
            "preprocessing_null": counts.get("null"),
            "audit_null": agg["null"],
            "audit_nonfinite": agg["nonfinite"],
            "null_match": counts.get("null") == agg["null"],
            "null_plus_nonfinite_match": counts.get("null") == agg["null"] + agg["nonfinite"],
            "preprocessing_nonpositive": counts.get("nonpositive"),
            "audit_nonpositive": agg["nonpositive"],
            "nonpositive_match": counts.get("nonpositive") == agg["nonpositive"],
            "preprocessing_absent": counts.get("absent"),
            "audit_absent": agg["absent_rows"],
            "absent_match": counts.get("absent") == agg["absent_rows"],
            "note": "preprocessing counts are the accepted fit; audit categories are re-measured here and only compared, never rewritten",
        }
        reconciliation[name] = row
        if not (row["valid_match"] and row["null_plus_nonfinite_match"] and row["nonpositive_match"] and row["absent_match"]):
            raise AuditError(
                "coverage aggregation does not agree with the accepted preprocessing statistics for %s" % name
            )

    # ---- fixed selection policy (chosen before any result was seen) ----
    runs = {}
    selected_member = None
    selected_start = None
    for member in train_members:
        start, max_run = first_run_reaching(flags_by_member[member])
        runs[member] = {"first_run_start": start, "max_run_len": max_run}
        if selected_member is None and start is not None:
            selected_member = member
            selected_start = start
    selection = {
        "policy": (
            "lexicographically first TRAIN member with a contiguous 128-row "
            "run where all four channels are effective-valid; earliest such "
            "run start; fixed before any scan result was seen"
        ),
        "found": selected_member is not None,
        "member": selected_member,
        "start_row": selected_start,
        "length": WINDOW if selected_member is not None else None,
        "runs_by_member": runs,
    }

    # ---- diagnostic replay of the selected run (second open, allowed) ----
    replay_payload = None
    if selected_member is not None and replay:
        record = inventory_by_member[selected_member]
        with GuardedZip(archive_path, allowed=train_members, journal=guard) as zf:
            info = zf.getinfo(selected_member)
            stream = zf.open(selected_member)
            error = None
            result2 = None
            captured = None
            try:
                result2, captured, flags2 = parse_member(
                    stream,
                    selected_member,
                    info.file_size,
                    modules,
                    capture_range=(selected_start, selected_start + WINDOW - 1),
                )
            except zipfile.BadZipFile as exc:
                error = "replay member %s failed ZIP CRC/deflate verification: %s" % (selected_member, exc)
            finally:
                try:
                    stream.close()
                except zipfile.BadZipFile as exc:
                    if error is None:
                        error = "replay member %s failed ZIP CRC-32 verification on close: %s" % (selected_member, exc)
            if error is not None:
                raise AuditError(error)
        if result2["member_sha256"] != record["member_sha256"]:
            raise AuditError("replay member sha mismatch for %s" % selected_member)
        if len(captured) != WINDOW:
            raise AuditError("replay captured %d rows instead of %d" % (len(captured), WINDOW))
        raw_rows = []
        for row_index, values, row_ok in captured:
            if not row_ok or any(value is None for value in values):
                raise AuditError("replay row %d is not all-four-effective-valid" % row_index)
            raw_rows.append((row_index, values))
        expected_sequences = list(range(selected_start, selected_start + WINDOW))
        if [row[0] for row in raw_rows] != expected_sequences:
            raise AuditError("replay row indexes are not the contiguous member row range")
        pass1_flags = flags_by_member[selected_member]
        for row_index, _values in raw_rows:
            if not pass1_flags[row_index]:
                raise AuditError("run flags disagree between scan passes at row %d" % row_index)

        input_text = "\n".join(
            "%d|%r|%r|%r|%r" % (sequence, values[0], values[1], values[2], values[3])
            for sequence, values in raw_rows
        )
        input_sha = sha256_bytes(input_text.encode("utf-8"))

        curve_input = modules["curve_input"]
        scaler = curve_input.CurveScaler(preproc_bytes, expected_sha256=expectations.preprocessing_sha256)
        stats = [
            (entry["name"], float(entry["mean"]), float(entry["effective_scale"]))
            for entry in channels_doc
        ]
        for index, (name, mean, scale) in enumerate(stats):
            channel = scaler.channels[index]
            if channel.name != name or channel.mean != mean or channel.effective_scale != scale:
                raise AuditError(
                    "scaler statistics disagree with the independent document parse for %s" % name
                )
        binding = curve_input.CurveBinding(
            run_id="force-train-coverage:" + selected_member.rsplit("/", 1)[-1],
            source_domain="geo_replay",
            preprocessing_sha256=expectations.preprocessing_sha256,
        )
        builder = curve_input.CurveWindowBuilder(scaler=scaler, binding=binding)

        windows_compared = 0
        values_compared = 0
        mismatches = 0
        max_abs = 0.0
        final_max_abs = 0.0
        expected_final = None
        actual_final = None
        for step, (sequence, values) in enumerate(raw_rows, 1):
            observation = curve_input.CurveObservation(
                binding=binding,
                sequence=sequence,
                values=values,
                valid=(True, True, True, True),
            )
            builder.observe(observation)
            window = builder.snapshot()
            expected = _expected_features(raw_rows[:step], stats)
            actual = window.features
            local_max = 0.0
            local_bad = 0
            for channel_index in range(8):
                actual_column = actual[channel_index]
                expected_column = expected[channel_index]
                for column in range(WINDOW):
                    if actual_column[column] != expected_column[column]:
                        local_bad += 1
                    delta = abs(actual_column[column] - expected_column[column])
                    if delta > local_max:
                        local_max = delta
            mismatches += local_bad
            if local_max > max_abs:
                max_abs = local_max
            metadata = window.metadata
            if metadata.latest_sequence != sequence:
                raise AuditError("snapshot latest_sequence mismatch at step %d" % step)
            if metadata.filled_slots != step or metadata.missing_slots != WINDOW - step:
                raise AuditError("snapshot padding/mask bookkeeping mismatch at step %d" % step)
            if (
                metadata.dropped_oldest != 0
                or metadata.accepted_observations != step
                or metadata.idempotent_repeats != 0
            ):
                raise AuditError("snapshot counters mismatch at step %d" % step)
            windows_compared += 1
            values_compared += 8 * WINDOW
            if step == WINDOW:
                final_max_abs = local_max
                expected_final = expected
                actual_final = actual
        if mismatches:
            raise AuditError(
                "replay mismatch: %d of %d compared values differ (max abs error %r)"
                % (mismatches, values_compared, max_abs)
            )
        expected_sha = sha256_bytes(repr(expected_final).encode("utf-8"))
        actual_sha = sha256_bytes(repr(actual_final).encode("utf-8"))
        if expected_sha != actual_sha:
            raise AuditError("final window canonical hashes differ")
        replay_payload = {
            "member": selected_member,
            "member_sha256": record["member_sha256"],
            "member_size_bytes": int(record["member_size_bytes"]),
            "start_row": selected_start,
            "end_row": selected_start + WINDOW - 1,
            "sequence_first": selected_start,
            "sequence_last": selected_start + WINDOW - 1,
            "input_sha256": input_sha,
            "expected_output_sha256": expected_sha,
            "actual_output_sha256": actual_sha,
            "windows_compared": windows_compared,
            "values_per_window": 8 * WINDOW,
            "total_values_compared": values_compared,
            "final_window_values": 8 * WINDOW,
            "final_window_max_abs_error": final_max_abs,
            "overall_max_abs_error": max_abs,
            "mismatches": mismatches,
            "expected_values_source": (
                "independent arithmetic: GR/RHOB/NPHI identity and RDEP log10 "
                "then the committed mean/effective_scale from the pinned "
                "preprocessing document; the production normalisation function "
                "was never called to derive expected values"
            ),
            "builder": "ai_pc/model/curve_input.py CurveScaler/CurveBinding/CurveObservation/CurveWindowBuilder",
            "source_domain": "geo_replay",
        }

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(product_dir))))
    git_info = {
        "controller_root": dict(_git(repo_root, "rev-parse", "HEAD"), dir=repo_root),
        "product_worktree": dict(_git(product_dir, "rev-parse", "HEAD"), dir=product_dir),
    }
    status = _git(product_dir, "status", "--porcelain")
    git_info["product_worktree_status_porcelain_count"] = len(status["stdout"].splitlines())
    git_info["product_worktree_status_head"] = status["stdout"].splitlines()[:40]

    open_calls = len(guard.opened)
    distinct_members = len(set(guard.opened))
    expected_open_calls = len(train_members) + (1 if replay_payload is not None else 0)
    if open_calls != expected_open_calls:
        raise AuditError("open-call accounting mismatch: %d != %d" % (open_calls, expected_open_calls))
    if distinct_members != len(train_members):
        raise AuditError("distinct opened members %d != %d" % (distinct_members, len(train_members)))
    if guard.heldout_attempts:
        raise AuditError("heldout member open attempts recorded: %r" % (guard.heldout_attempts,))

    payload = {
        "schema": 1,
        "kind": "deepeye-train-curve-coverage-audit",
        "status": "ok",
        "generated_utc": started,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "implementation_job": IMPLEMENTATION_JOB,
        "instance_id": INSTANCE_ID,
        "route": ROUTE,
        "provider_model_effort_observable": False,
        "contract": {
            "id": CONTRACT_ID,
            "source": CONTRACT_SOURCE,
            "design_commit": DESIGN_COMMIT,
            "requirements_sha256": REQUIREMENTS_SHA,
        },
        "role": "ordinary DeepSeek Flash/max executor; not App/native worker or director; board_access false",
        "scope": SCOPE_NOTE,
        "expectations": dict(dataclasses.asdict(expectations), kind="pins", override="CLI uses the frozen production pins only"),
        "git": git_info,
        "inputs": {
            "archive": {"path": archive_path, "sha256": archive_sha, "bytes": archive_size},
            "splits": {"path": os.path.join(product_dir, "data", "splits.json"), "sha256": expectations.splits_sha256, "bytes": len(splits_bytes)},
            "force_wells": {"path": os.path.join(product_dir, "data", "force_wells.json"), "sha256": expectations.wells_sha256, "bytes": len(wells_bytes)},
            "preprocessing": {"path": os.path.join(product_dir, "data", "preprocessing.json"), "sha256": expectations.preprocessing_sha256, "bytes": len(preproc_bytes)},
            "modules": module_sources,
            "python": {"executable": sys.executable, "version": platform.python_version()},
        },
        "split_crosscheck": {
            "rows": len(rows),
            "well_counts": split_rows,
            "group_count": report.root_count,
            "train_wells": len(train_members),
            "train_parents": train_parents,
            "train_rows_sum": train_rows_total,
            "domain": expectations.source_domain,
            "domain_summary": {
                "rows": domain_summary.rows,
                "roots": domain_summary.roots,
                "derivatives": domain_summary.derivatives,
                "split_rows": dict(domain_summary.split_rows),
            },
            "cross_split_root_violations": 0,
            "recorded_preprocessing_grouping_validation_reproduced": recorded_grouping_reproduced,
            "fitting_wells_equal_train_set": isinstance(fitting, list),
        },
        "guard": {
            "allowed_train_members": len(train_members),
            "central_directory_members": len(names),
            "open_calls": open_calls,
            "distinct_members": distinct_members,
            "replay_second_open": replay_payload is not None,
            "opened_members_in_order": list(guard.opened),
            "heldout_open_attempts": len(guard.heldout_attempts),
            "heldout_open_attempt_names": list(guard.heldout_attempts),
        },
        "wells": [
            {
                "member": result["member"],
                "rows": result["rows"],
                "member_sha256": result["member_sha256"],
                "member_size_bytes": result["member_size_bytes"],
                "uwi": result["uwi"],
                "channels": result["channels"],
                "all4_rows": result["all4_rows"],
                "max_run_len": runs[result["member"]]["max_run_len"],
                "first_run_start": runs[result["member"]]["first_run_start"],
            }
            for result in well_results
        ],
        "aggregate": aggregate,
        "parse_instrumentation": {
            "selected_numeric_parse_attempts": total_attempts,
            "selected_numeric_parse_expected": expected_parse_attempts,
            "nonselected_numeric_parse_attempts": 0,
            "note": (
                "by construction only the selected GR/RHOB/NPHI/RDEP tokens are "
                "ever passed to float(); labels, confidence, depth and every "
                "other column stay opaque strings, proven by unit tests that "
                "insert arbitrary nonnumeric sentinels into nonselected columns"
            ),
        },
        "reconciliation": reconciliation,
        "selection": selection,
        "replay": replay_payload,
        "limits": LIMITS,
        "product_cards": {
            "C01": "not_run",
            "C02": "not_run",
            "all_product_simulation_synthesis_implementation_board_system_cards": "not_run",
        },
        "rows_measured_total": total_rows_measured,
    }
    return payload

def write_evidence(args):
    """Capture a run-audit subprocess and write audit.json plus audit.log."""
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    scan_path = os.path.abspath(__file__)
    scan_dir = os.path.dirname(scan_path)
    test_path = os.path.join(scan_dir, "test_scan_train_curves.py")
    scan_sha = sha256_bytes(read_bytes(scan_path))
    scan_size = os.path.getsize(scan_path)
    test_sha = sha256_bytes(read_bytes(test_path)) if os.path.isfile(test_path) else None
    test_size = os.path.getsize(test_path) if os.path.isfile(test_path) else None

    out_bytes = read_bytes(args.capture_stdout)
    err_bytes = read_bytes(args.capture_stderr)
    out_sha = sha256_bytes(out_bytes)
    err_sha = sha256_bytes(err_bytes)
    tests = None
    if args.tests_stdout and args.tests_stderr and args.tests_exit is not None:
        t_out = read_bytes(args.tests_stdout)
        t_err = read_bytes(args.tests_stderr)
        tests = {
            "command": [sys.executable, "-X", "utf8", "-B", "test_scan_train_curves.py"],
            "cwd": scan_dir,
            "exit_code": args.tests_exit,
            "stdout_bytes": len(t_out),
            "stdout_sha256": sha256_bytes(t_out),
            "stderr_bytes": len(t_err),
            "stderr_sha256": sha256_bytes(t_err),
            "stdout": t_out.decode("utf-8", "replace"),
            "stderr": t_err.decode("utf-8", "replace"),
        }

    audit_command = [
        sys.executable, "-X", "utf8", "-B", scan_path, "run-audit",
        "--archive", os.path.abspath(args.archive),
        "--product", os.path.abspath(args.product),
    ]
    write_command = [sys.executable, "-X", "utf8", "-B", scan_path] + sys.argv[1:]
    check_command = [
        sys.executable, "-X", "utf8", "-B", scan_path, "check-evidence",
        "--json-out", os.path.abspath(args.json_out),
        "--log-out", os.path.abspath(args.log_out),
    ]

    failures = []
    payload = None
    try:
        parsed = json.loads(out_bytes.decode("utf-8"))
    except ValueError as exc:
        parsed = None
        failures.append("run-audit stdout is not valid JSON: %s" % exc)
    if args.capture_exit != 0:
        failures.append("run-audit exited with code %s" % args.capture_exit)
    elif parsed is not None and parsed.get("status") == "ok":
        payload = parsed
    elif parsed is not None:
        failures.append("run-audit payload status %r: %s" % (parsed.get("status"), parsed.get("error")))

    archive_sha, archive_size = sha256_file(args.archive)
    product_dir = os.path.abspath(args.product)
    pin_data = {}
    for key, rel in (
        ("splits", "data/splits.json"),
        ("force_wells", "data/force_wells.json"),
        ("preprocessing", "data/preprocessing.json"),
    ):
        data = read_bytes(os.path.join(product_dir, rel))
        pin_data[key] = {"path": os.path.join(product_dir, rel), "sha256": sha256_bytes(data), "bytes": len(data)}
    module_hashes = {}
    for name, rel in (
        ("force_inventory", "data/force_inventory.py"),
        ("grouping", "data/grouping.py"),
        ("curve_input", "ai_pc/model/curve_input.py"),
    ):
        module_hashes[name] = {"path": os.path.join(product_dir, rel), "sha256": sha256_bytes(read_bytes(os.path.join(product_dir, rel)))}

    if payload is not None:
        if archive_sha != PRODUCTION_EXPECTATIONS.archive_sha256 or archive_size != PRODUCTION_EXPECTATIONS.archive_bytes:
            failures.append("archive bytes do not match the frozen production pins at write time")
        if payload.get("expectations", {}).get("label") != PRODUCTION_EXPECTATIONS.label:
            failures.append("payload is not from the frozen production pins")
        if pin_data["splits"]["sha256"] != PRODUCTION_EXPECTATIONS.splits_sha256:
            failures.append("splits.json bytes do not match the frozen pin at write time")
        if pin_data["force_wells"]["sha256"] != PRODUCTION_EXPECTATIONS.wells_sha256:
            failures.append("force_wells.json bytes do not match the frozen pin at write time")
        if pin_data["preprocessing"]["sha256"] != PRODUCTION_EXPECTATIONS.preprocessing_sha256:
            failures.append("preprocessing.json bytes do not match the frozen pin at write time")
        recorded = payload.get("inputs", {})
        if recorded.get("archive", {}).get("sha256") != archive_sha:
            failures.append("payload archive hash does not match the bytes re-hashed at write time")
        recorded_modules = recorded.get("modules", {})
        for name, info in module_hashes.items():
            if recorded_modules.get(name, {}).get("sha256") != info["sha256"]:
                failures.append("module %s bytes changed between audit and write time" % name)
        if payload.get("guard", {}).get("heldout_open_attempts") != 0:
            failures.append("payload records heldout open attempts")
        if not failures:
            pass
        else:
            payload = None

    status = "ok" if payload is not None and not failures else "failed"
    ok = status == "ok"

    log_lines = []
    add = log_lines.append
    add("=====================================================================")
    add("FORCE train-only four-channel coverage audit + diagnostic replay")
    add("evidence log (companion: audit.json)")
    add("=====================================================================")
    add("")
    add("task_id: " + TASK_ID)
    add("task_version: %d" % TASK_VERSION)
    add("work_id: " + WORK_ID)
    add("implementation_job: " + IMPLEMENTATION_JOB)
    add("instance_id: " + INSTANCE_ID + "   route: " + ROUTE)
    add("provider/model/effort: not observable from inside this child session; not inferred from any catalog")
    add("contract: " + CONTRACT_ID)
    add("contract_source: " + CONTRACT_SOURCE)
    add("design_commit: " + DESIGN_COMMIT)
    add("requirements_sha256: " + REQUIREMENTS_SHA)
    add("role: ordinary DeepSeek Flash/max executor (not App/native worker, not director); board_access false")
    add("generated_utc: " + started)
    add("python: " + platform.python_version() + "  (" + sys.executable + ")")
    add("platform: " + platform.platform())
    add("status: " + status)
    add("")
    add("[1] Owned files (exactly four for this job; no product file is written)")
    add("    " + scan_path + "  %dB  sha256=%s" % (scan_size, scan_sha))
    if test_sha is not None:
        add("    " + test_path + "  %dB  sha256=%s" % (test_size, test_sha))
    else:
        add("    " + test_path + "  (missing at write time)")
    add("    " + os.path.abspath(args.log_out) + "  (this file)")
    add("    " + os.path.abspath(args.json_out) + "  (written after this log; carries this log sha256)")
    add("")
    add("[2] Read-only inputs (re-hashed at write time)")
    add("    archive: %s  %dB  sha256=%s" % (os.path.abspath(args.archive), archive_size, archive_sha))
    for key in ("splits", "force_wells", "preprocessing"):
        info = pin_data[key]
        add("    %s: %s  %dB  sha256=%s" % (key, info["path"], info["bytes"], info["sha256"]))
    for name in sorted(module_hashes):
        info = module_hashes[name]
        add("    module %s: %s  sha256=%s" % (name, info["path"], info["sha256"]))
    add("")
    add("[3] Product module + worktree identity (from the audit payload when ok)")
    if payload is not None:
        for line in json.dumps(payload.get("git", {}), indent=1).splitlines():
            add("    " + line)
    else:
        add("    (payload not ok; see failures)")
    add("")
    add("[4] Executed commands with raw transcripts")
    if tests is not None:
        add("")
        add("---- unit tests ----")
        add("command: " + json.dumps(tests["command"]))
        add("cwd: " + tests["cwd"])
        add("exit: %s" % tests["exit_code"])
        add("stdout bytes: %d  sha256=%s" % (tests["stdout_bytes"], tests["stdout_sha256"]))
        add("stderr bytes: %d  sha256=%s" % (tests["stderr_bytes"], tests["stderr_sha256"]))
        add("----- begin raw test stdout -----")
        add(tests["stdout"].rstrip("\n"))
        add("----- end raw test stdout -----")
        add("----- begin raw test stderr -----")
        add(tests["stderr"].rstrip("\n"))
        add("----- end raw test stderr -----")
    else:
        add("")
        add("---- unit tests ---- (no capture supplied)")
    add("")
    add("---- run-audit (the actual measurement command) ----")
    add("command: " + json.dumps(audit_command))
    add("exit: %s" % args.capture_exit)
    add("stdout bytes: %d  sha256=%s" % (len(out_bytes), out_sha))
    add("stderr bytes: %d  sha256=%s" % (len(err_bytes), err_sha))
    add("----- begin raw audit stdout -----")
    add(out_bytes.decode("utf-8", "replace").rstrip("\n"))
    add("----- end raw audit stdout -----")
    add("----- begin raw audit stderr -----")
    add(err_bytes.decode("utf-8", "replace").rstrip("\n"))
    add("----- end raw audit stderr -----")
    add("")
    add("---- write-evidence (this run) ----")
    add("command: " + json.dumps(write_command))
    add("note: the exit code of this writer run is observed by the dispatching terminal; it is 0 only if this file and audit.json are complete and end with SCAN-OK")
    add("")
    add("[5] Failures")
    if failures:
        for item in failures:
            add("    - " + item)
    else:
        add("    none")
    add("")
    add("[6] Limits and non-claims")
    for item in LIMITS:
        add("    - " + item)
    add("")
    add("[7] Notes")
    add("    - The selected diagnostic run, aggregate counts, reconciliation and guard journal are in audit.json (and in the raw audit stdout above).")
    add("    - check-evidence (read-only) is run next: " + json.dumps(check_command))
    add("    - This log embeds the raw stdout/stderr of the actual run-audit subprocess; its exit code and byte hashes are recorded here and in audit.json.")
    add("")
    log_text = "\n".join(log_lines) + "\n"

    log_path = os.path.abspath(args.log_out)
    with open(log_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(log_text)
    log_bytes = read_bytes(log_path)
    log_sha = sha256_bytes(log_bytes)

    json_doc = {
        "schema": 1,
        "kind": "deepeye-train-curve-coverage-audit-evidence",
        "status": status,
        "generated_utc": started,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "implementation_job": IMPLEMENTATION_JOB,
        "instance_id": INSTANCE_ID,
        "route": ROUTE,
        "provider_model_effort_observable": False,
        "contract": {
            "id": CONTRACT_ID,
            "source": CONTRACT_SOURCE,
            "design_commit": DESIGN_COMMIT,
            "requirements_sha256": REQUIREMENTS_SHA,
        },
        "role": "ordinary DeepSeek Flash/max executor; not App/native worker or director; board_access false",
        "scope": SCOPE_NOTE,
        "product_cards": {
            "C01": "not_run",
            "C02": "not_run",
            "all_product_simulation_synthesis_implementation_board_system_cards": "not_run",
        },
        "audit": payload,
        "captures": {
            "audit_command": audit_command,
            "exit_code": args.capture_exit,
            "stdout_bytes": len(out_bytes),
            "stdout_sha256": out_sha,
            "stderr_bytes": len(err_bytes),
            "stderr_sha256": err_sha,
            "stdout": out_bytes.decode("utf-8", "replace"),
            "stderr": err_bytes.decode("utf-8", "replace"),
        },
        "unit_tests": tests,
        "write_evidence_command": write_command,
        "write_evidence_exit": {
            "value": None,
            "note": "recorded by the dispatching terminal and by the completion marker; this writer exits 0 only when both files are complete",
        },
        "check_command": check_command,
        "files": [
            {"path": scan_path, "role": "audit implementation and evidence writer (helper source; the only helper files are this one and the test file)", "sha256": scan_sha, "bytes": scan_size},
            {"path": test_path, "role": "portable unit tests (synthetic fixtures: NULL/missing/nonpositive/malformed/header/opaque columns, run selection, heldout guard)", "sha256": test_sha, "bytes": test_size},
            {"path": log_path, "role": "raw transcripts + limits (written before this json)", "sha256": log_sha, "bytes": len(log_bytes)},
            {"path": os.path.abspath(args.json_out), "role": "this evidence file; its own sha256 cannot be embedded stably and is omitted by design - the director recomputes it", "sha256": None, "bytes": None},
        ],
        "input_sha256": {
            "archive": {"path": os.path.abspath(args.archive), "sha256": archive_sha, "bytes": archive_size},
            "splits": pin_data["splits"],
            "force_wells": pin_data["force_wells"],
            "preprocessing": pin_data["preprocessing"],
            "modules": module_hashes,
        },
        "failures": failures,
        "limits": LIMITS,
        "public_raw_transcript": log_path,
    }
    with open(os.path.abspath(args.json_out), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(json_doc, indent=1) + "\n")

    print("audit status: " + status)
    if payload is not None:
        selection = payload["selection"]
        replay = payload.get("replay")
        print("selection: " + json.dumps({k: selection[k] for k in ("found", "member", "start_row")}))
        if replay is not None:
            print("replay max abs error: %r  input sha256: %s" % (replay["overall_max_abs_error"], replay["input_sha256"]))
        print("guard: open_calls=%d distinct=%d heldout=%d" % (
            payload["guard"]["open_calls"], payload["guard"]["distinct_members"], payload["guard"]["heldout_open_attempts"]))
    print("log: %s  %dB  sha256=%s" % (log_path, len(log_bytes), log_sha))
    print("json: %s  %dB" % (os.path.abspath(args.json_out), os.path.getsize(os.path.abspath(args.json_out))))
    print("SCAN-OK" if ok else "SCAN-FAILED")
    return 0 if ok else 1


def check_evidence(args):
    """Read-only consistency check of the written evidence files."""
    problems = []
    json_path = os.path.abspath(args.json_out)
    log_path = os.path.abspath(args.log_out)
    json_doc = json.loads(read_bytes(json_path).decode("utf-8"))
    log_bytes = read_bytes(log_path)
    log_text = log_bytes.decode("utf-8", "replace")

    if json_doc.get("status") != "ok":
        problems.append("evidence status %r" % json_doc.get("status"))
    files = json_doc.get("files", [])
    log_entry = None
    for entry in files:
        if entry.get("sha256") is None:
            continue
        actual = sha256_bytes(read_bytes(entry["path"]))
        if actual != entry["sha256"]:
            problems.append("sha256 mismatch for %s" % entry["path"])
        if os.path.abspath(entry["path"]) == log_path:
            log_entry = entry
    if log_entry is None:
        problems.append("log entry missing from files list")
    elif log_entry["sha256"] != sha256_bytes(log_bytes) or log_entry["bytes"] != len(log_bytes):
        problems.append("log bytes do not match the recorded entry")

    if "SCAN-OK" not in log_text:
        problems.append("SCAN-OK completion marker missing")
    captures = json_doc.get("captures", {})
    if captures.get("exit_code") != 0:
        problems.append("recorded audit exit code %r" % captures.get("exit_code"))
    raw_stdout = captures.get("stdout", "")
    if sha256_bytes(raw_stdout.encode("utf-8")) != captures.get("stdout_sha256"):
        problems.append("embedded raw audit stdout does not match its recorded sha256")

    payload = json_doc.get("audit")
    if not isinstance(payload, dict):
        problems.append("audit payload missing")
    else:
        guard = payload.get("guard", {})
        if guard.get("heldout_open_attempts") != 0 or guard.get("heldout_open_attempt_names"):
            problems.append("heldout open attempts recorded")
        expected_open = guard.get("distinct_members", -1) + (1 if payload.get("selection", {}).get("found") else 0)
        if guard.get("open_calls") != expected_open:
            problems.append("open-call accounting %r != %r" % (guard.get("open_calls"), expected_open))
        for name, row in payload.get("reconciliation", {}).items():
            for key in ("valid_match", "null_plus_nonfinite_match", "nonpositive_match", "absent_match"):
                if not row.get(key):
                    problems.append("reconciliation %s %s is false" % (name, key))
        instrumentation = payload.get("parse_instrumentation", {})
        if instrumentation.get("nonselected_numeric_parse_attempts") != 0:
            problems.append("nonselected numeric parse attempts recorded")
        if payload.get("selection", {}).get("found") and payload.get("replay") is None:
            problems.append("selection found but replay missing")
        replay = payload.get("replay")
        if replay is not None:
            if replay.get("mismatches") != 0:
                problems.append("replay mismatches %r" % replay.get("mismatches"))
            if replay.get("windows_compared") != WINDOW or replay.get("final_window_values") != 8 * WINDOW:
                problems.append("replay comparison counts unexpected")

    archive_sha, archive_size = sha256_file(args.archive)
    pins = json_doc.get("input_sha256", {})
    if pins.get("archive", {}).get("sha256") != archive_sha or pins.get("archive", {}).get("bytes") != archive_size:
        problems.append("archive bytes/hash changed since the evidence was written")
    for key, rel in (
        ("splits", "data/splits.json"),
        ("force_wells", "data/force_wells.json"),
        ("preprocessing", "data/preprocessing.json"),
    ):
        recorded = pins.get(key, {})
        actual = sha256_bytes(read_bytes(os.path.join(args.product, rel)))
        if recorded.get("sha256") != actual:
            problems.append("%s bytes changed since the evidence was written" % key)

    summary = {
        "json": json_path,
        "log": log_path,
        "status": json_doc.get("status"),
        "json_bytes": os.path.getsize(json_path),
        "log_bytes": len(log_bytes),
        "problems": problems,
    }
    print(json.dumps(summary, indent=1))
    print("CHECK-OK" if not problems else "CHECK-PROBLEMS")
    return 0 if not problems else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded train-only FORCE four-curve coverage audit")
    parser.add_argument("mode", choices=["run-audit", "write-evidence", "check-evidence"])
    parser.add_argument("--archive", required=True, help="explicit path to the pinned FORCE ZIP")
    parser.add_argument("--product", required=True, help="explicit path to the accepted product tree")
    parser.add_argument("--capture-stdout")
    parser.add_argument("--capture-stderr")
    parser.add_argument("--capture-exit", type=int)
    parser.add_argument("--tests-stdout")
    parser.add_argument("--tests-stderr")
    parser.add_argument("--tests-exit", type=int)
    parser.add_argument("--json-out")
    parser.add_argument("--log-out")
    args = parser.parse_args(argv)
    if args.mode == "run-audit":
        try:
            payload = run_audit(args.archive, args.product)
        except AuditError as exc:
            failure = {
                "schema": 1,
                "kind": "deepeye-train-curve-coverage-audit",
                "status": "failed",
                "task_id": TASK_ID,
                "work_id": WORK_ID,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            print(json.dumps(failure, indent=1))
            print("AUDIT-FAILED: %s" % exc, file=sys.stderr)
            return 1
        except Exception as exc:  # unexpected failures still produce deterministic evidence
            failure = {
                "schema": 1,
                "kind": "deepeye-train-curve-coverage-audit",
                "status": "failed",
                "task_id": TASK_ID,
                "work_id": WORK_ID,
                "error": "unexpected: %s" % exc,
                "traceback": traceback.format_exc(),
            }
            print(json.dumps(failure, indent=1))
            print("AUDIT-FAILED-UNEXPECTED: %s" % exc, file=sys.stderr)
            return 1
        print(json.dumps(payload, indent=1))
        print("AUDIT-OK", file=sys.stderr)
        return 0
    if args.mode == "write-evidence":
        missing = [
            name
            for name in ("capture_stdout", "capture_stderr", "capture_exit", "json_out", "log_out")
            if getattr(args, name) is None
        ]
        if missing:
            print("write-evidence requires --" + ", --".join(name.replace("_", "-") for name in missing), file=sys.stderr)
            return 2
        return write_evidence(args)
    return check_evidence(args)


if __name__ == "__main__":
    raise SystemExit(main())
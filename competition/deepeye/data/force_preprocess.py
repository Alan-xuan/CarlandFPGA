"""C01 train-only preprocessing fitter for the FORCE 2020 LAS archive (stdlib only).

Software-only preparation step for card C01: fit the frozen four-channel
FORCE curve-profile preprocessing baseline (GR, RHOB, NPHI, RDEP) from
training wells only, over the already-verified local archive, and record the
fitted statistics with their provenance.  These four FORCE curves are
curve-profile preprocessing inputs, not the online sim_em_v2 summary
contract, which is a separate later artifact.  Nothing here trains a model,
builds causal replay windows, implements the verify_data entrypoint or
touches any online scene; product C01 stays not_run.

Hard boundaries, all deliberate:

* Fixed channel order GR, RHOB, NPHI, RDEP taken from the frozen split policy
  and label schema (``input_curve_order``); a manifest whose order differs is
  refused.
* Provenance first: the archive bytes/SHA256 and the inventory/split/policy/
  label manifest references are verified before any member is opened.  The
  reviewed inventory (``force_wells.json``) and pinned split manifest
  (``splits.json``) are read-only inputs; nothing is rewritten, no split is
  rerolled and held-out wells are only cross-checked at manifest level.
* Only ``split == "train"`` members may be decompressed.  The ZIP directory
  may be listed and the compressed archive may be hashed, but a non-training
  member is never opened for fitting (guarded and regression-tested).
* Every fitted member must match the reviewed inventory exactly: decompressed
  byte count, SHA256, ZIP CRC (checked by zipfile on a complete read), row
  count, UWI, well name, NULL sentinel, curve identities (mnemonics/units in
  order) and depth-column mnemonic.  Any mismatch refuses with member/line.
* Row parsing validates the column count, the depth column (finite, not NULL,
  non-decreasing) and the four selected sensor columns only.  Label and
  confidence columns are deliberately NOT parsed, so their values can never
  become fitted features; depth and coordinates are never fitted features.
* LAS NULL (the declared sentinel) is missing.  For RDEP only strictly
  positive observed values are valid and transformed with log10; nonpositive
  RDEP is invalid/masked and counted.  For GR/RHOB/NPHI any finite value that
  is not the NULL sentinel is valid, including negative values.  An absent
  selected curve marks every row of that well absent/masked with explicit
  counts.  Unknown (empty) units, units that vary across wells and ambiguous
  (duplicate) curve mappings are refused; observed units are recorded and no
  unit conversion is applied.
* Statistics: population mean and population variance from a numerically
  stable one-pass Welford accumulation over valid transformed TRAIN samples
  only, in the deterministic fixed split row order.  ``std = sqrt(M2/n)``;
  zero variance is recorded and ``effective_scale`` becomes 1.0 explicitly
  (never silently).  A training channel with zero valid samples BLOCKS the
  run instead of guessing a scale.  Overflow or non-finite intermediate
  values/results are rejected, never clipped.
* The emitted document records the exact fitting well list and member hashes,
  all input hashes, per-channel source counts, means, variances, effective
  scales, transform versions, algorithm identity and the software-only status.
  It contains no labels and no validation/test statistics, and it is neither
  calibration nor a claim about real sensors or the FPGA board.

CLI exit codes: 0 success, 1 refused input/failed verification, 3 blocked
(a training channel has no valid samples).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import math
import pathlib
import re
import sys
import zipfile

__all__ = [
    "CHANNELS",
    "ALGORITHM_VERSION",
    "TRANSFORM_VERSIONS",
    "TASK_ID",
    "TASK_VERSION",
    "CONTRACT_ID",
    "CONTRACT_REVISION",
    "SOURCE_COMMIT",
    "REQUIREMENTS_SHA256",
    "DESIGN_COMMIT",
    "PINNED_ARCHIVE_BYTES",
    "PINNED_ARCHIVE_SHA256",
    "PINNED_INVENTORY_SHA256",
    "PINNED_SPLITS_SHA256",
    "PINNED_WELL_COUNTS",
    "PINNED_GROUP_COUNTS",
    "DEFAULT_CHUNK_BYTES",
    "ForcePreprocessError",
    "ForcePreprocessBlocked",
    "fit_preprocessing",
    "main",
]

CHANNELS: tuple[str, str, str, str] = ("GR", "RHOB", "NPHI", "RDEP")
ALGORITHM_VERSION = "c01-preprocess-welford-v1"
TRANSFORM_VERSIONS = {
    "GR": "identity-v1",
    "RHOB": "identity-v1",
    "NPHI": "identity-v1",
    "RDEP": "log10-positive-v1",
}
TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014"
CONTRACT_REVISION = 1
SOURCE_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"

PINNED_ARCHIVE_BYTES = 169785172
PINNED_ARCHIVE_SHA256 = "042ef1d473100dc12768cae7107a8cead071a394f137af3bc1ddaf8a5d1b8dda"
PINNED_INVENTORY_SHA256 = "ace9a0eb9930f19c6b8125e151d07346fb23029b1455eac04964d15b97461e59"
PINNED_SPLITS_SHA256 = "f10ddb8f37e6bdf7c9663eed45d0f6554ef8992899724013a7e487ad3e3cef91"
PINNED_WELL_COUNTS = {"train": 82, "validation": 17, "test": 19}
PINNED_GROUP_COUNTS = {"train": 81, "validation": 17, "test": 19}

DEFAULT_CHUNK_BYTES = 1 << 20
REQUIRED_SPLITS = ("train", "validation", "test")

_HERE = pathlib.Path(__file__).resolve().parent
_LOCAL_ROOT = _HERE.parents[3]
_DEFAULT_ARCHIVE = _LOCAL_ROOT / "datasets" / "force-2020" / (
    "LAS_files_Force_2020_all_wells_train_test_blind_hidden_final.zip"
)
_DEFAULT_INVENTORY = _HERE / "force_wells.json"
_DEFAULT_SPLITS = _HERE / "splits.json"
_DEFAULT_POLICY = _HERE / "split_policy.json"
_DEFAULT_LABEL = _HERE / "label_schema.json"
_DEFAULT_CARD = _HERE / "dataset_card.md"
_DEFAULT_OUT = _HERE / "preprocessing.json"


def _load_streaming_helpers():
    """Load the read-only inventory module (reused for bounded line splitting)."""
    spec = importlib.util.spec_from_file_location(
        "deepeye_force_inventory_reuse", _HERE / "force_inventory.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


_STREAMING = _load_streaming_helpers()
iter_las_lines = _STREAMING.iter_las_lines
parse_section_line = _STREAMING.parse_section_line

FORCE_PARENT_PATTERN = re.compile(r"^([0-9]+/[0-9]+-[0-9]+)(?:[ ]+[A-Z0-9 -]+)?$")


def _force_parent_well(well_id):
    """Derive the parent well id with the frozen FORCE parent-well rule."""
    if not isinstance(well_id, str):
        return None
    match = FORCE_PARENT_PATTERN.match(well_id)
    return match.group(1) if match else None


def _load_grouping_helper():
    """Load the read-only split grouping validator module (no writes)."""
    spec = importlib.util.spec_from_file_location(
        "deepeye_grouping_reuse", _HERE / "grouping.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


class ForcePreprocessError(Exception):
    """Refused input, failed verification or a malformed LAS member."""

    def __init__(self, message, member=None, line=None):
        if member is not None:
            location = "member=" + str(member)
            if line is not None:
                location += " line=" + str(line)
            message = location + ": " + message
        super().__init__(message)
        self.member = member
        self.line = line


class ForcePreprocessBlocked(ForcePreprocessError):
    """A training channel has no valid samples; no scale can be fitted."""


def _sha256_file(path, chunk_bytes=DEFAULT_CHUNK_BYTES):
    digest = hashlib.sha256()
    total = 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(block)
            total += len(block)
    return digest.hexdigest(), total


def _load_json(path, what):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise ForcePreprocessError("%s is not readable JSON: %s" % (what, error))


def _expect(condition, message, member=None, line=None):
    if not condition:
        raise ForcePreprocessError(message, member, line)


def _expect_str(value, what, allow_empty=False):
    _expect(isinstance(value, str), "%s must be a string" % what)
    if not allow_empty:
        _expect(bool(value), "%s must be a non-empty string" % what)
    return value


def _check_contract(document, what):
    contract = document.get("contract")
    _expect(isinstance(contract, dict), "%s: missing contract block" % what)
    _expect(contract.get("id") == CONTRACT_ID, "%s: contract id mismatch" % what)
    _expect(
        contract.get("revision") == CONTRACT_REVISION,
        "%s: contract revision mismatch" % what,
    )
    _expect(
        contract.get("source_commit") == SOURCE_COMMIT,
        "%s: contract source_commit mismatch" % what,
    )
    _expect(
        contract.get("requirements_sha256") == REQUIREMENTS_SHA256,
        "%s: contract requirements_sha256 mismatch" % what,
    )


def _safe_member_path(name):
    _expect(isinstance(name, str) and bool(name), "unsafe member path %r" % (name,))
    _expect(not name.endswith("/"), "directory entry not supported: %r" % (name,))
    _expect(
        "\\" not in name and ":" not in name and not name.startswith("/"),
        "unsafe member path %r" % (name,),
    )
    parts = name.split("/")
    _expect(
        all(part not in ("", ".", "..") for part in parts),
        "unsafe member path %r" % (name,),
    )
    _expect(
        name.lower().endswith(".las"),
        "unsupported member extension (expected .las): %r" % (name,),
    )
    return name


def _strict_number(token, what, member_name, line_number):
    try:
        value = float(token)
    except (TypeError, ValueError):
        raise ForcePreprocessError(
            "non-numeric %s %r" % (what, token), member_name, line_number
        )
    if not math.isfinite(value):
        raise ForcePreprocessError(
            "non-finite %s %r" % (what, token), member_name, line_number
        )
    return value


class _ChannelFit:
    """One-pass Welford accumulator plus source counts for one channel."""

    __slots__ = ("channel", "unit", "counts", "n", "mean", "m2")

    def __init__(self, channel):
        self.channel = channel
        self.unit = None
        self.counts = {"valid": 0, "null": 0, "nonpositive": 0, "absent": 0}
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def note_unit(self, unit, member_name):
        if not isinstance(unit, str) or not unit.strip():
            raise ForcePreprocessError(
                "unknown (empty) unit for %s" % self.channel, member_name
            )
        unit = unit.strip()
        if self.unit is None:
            self.unit = unit
        elif self.unit != unit:
            raise ForcePreprocessError(
                "ambiguous units for %s: %r vs %r" % (self.channel, self.unit, unit),
                member_name,
            )

    def observe(self, value, member_name, line_number):
        self.counts["valid"] += 1
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        if not math.isfinite(self.mean) or not math.isfinite(self.m2):
            raise ForcePreprocessError(
                "non-finite Welford intermediate for %s" % self.channel,
                member_name,
                line_number,
            )


class _HashingStream:
    """Binary stream wrapper hashing every byte read through it."""

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



# ---------------------------------------------------------------------------
# Member-level fitting (train members only; label/confidence never read)
# ---------------------------------------------------------------------------


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_hex64(value):
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _curve_indices(curves, member_name):
    """Map the four selected channels to unique curve column indices.

    Returns ``(index_by_channel, absent_channels)``.  A channel whose mnemonic
    is not present is absent for the member: every data row of that member is
    counted as an absent observation for that channel.  A mnemonic matching
    more than one curve would be an ambiguous mapping and is refused.
    """
    index_by_channel = {}
    absent_channels = set()
    for channel in CHANNELS:
        matches = [
            index
            for index, (mnemonic, _unit) in enumerate(curves)
            if mnemonic.upper() == channel
        ]
        if not matches:
            absent_channels.add(channel)
        elif len(matches) > 1:
            raise ForcePreprocessError(
                "ambiguous curve mapping for %s (%d matching curves)"
                % (channel, len(matches)),
                member_name,
            )
        else:
            index_by_channel[channel] = matches[0]
    return index_by_channel, absent_channels


def _parse_null(text):
    """Parse the LAS NULL sentinel exactly like the reviewed inventory parser."""
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


def _fit_member(stream, member_name, chunk_bytes, channels):
    """Stream one train member and update the per-channel Welford fits.

    Mirrors the reviewed inventory parser for the structural checks (column
    count, section order) and adds the fitting rules: depth
    must be non-NULL and non-decreasing; LAS NULL counts as missing; RDEP is
    valid only when strictly positive and is log10-transformed; other finite
    non-NULL values (including negatives) are valid; a selected channel that
    is absent from the curve definitions is counted absent for every row.
    Only the depth column and the four selected channel columns are converted
    numerically; every other column is structurally validated for row
    cardinality but never parsed, so label, confidence, coordinate or other
    unselected metadata may carry opaque non-numeric or non-finite sentinels
    without failing the fit.
    """
    reader = _HashingStream(stream)
    section = None
    version = None
    wrap = None
    well_fields = {}
    curves = []
    null_value = None
    rows = 0
    depth_previous = None
    index_by_channel = None
    absent_channels = set()
    for line_number, raw_line in enumerate(iter_las_lines(reader, chunk_bytes), 1):
        try:
            line = raw_line.decode("ascii")
        except UnicodeDecodeError:
            raise ForcePreprocessError("non-ASCII byte in line", member_name, line_number)
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("~"):
            body = stripped[1:].strip()
            section = body.split()[0].lower() if body else ""
            if section in ("ascii", "a"):
                if not curves:
                    raise ForcePreprocessError(
                        "ASCII data section before curve definitions",
                        member_name,
                        line_number,
                    )
                if null_value is None:
                    null_value = _parse_null(well_fields.get("NULL"))
                if null_value is None:
                    raise ForcePreprocessError(
                        "NULL sentinel missing or unparseable before data section",
                        member_name,
                        line_number,
                    )
                if index_by_channel is None:
                    if curves[0][0].upper() != "DEPT":
                        raise ForcePreprocessError(
                            "unexpected depth column %r (expected DEPT)" % (curves[0][0],),
                            member_name,
                            line_number,
                        )
                    index_by_channel, absent_channels = _curve_indices(curves, member_name)
                    for channel in index_by_channel:
                        channels[channel].note_unit(
                            curves[index_by_channel[channel]][1], member_name
                        )
            continue
        if section == "version":
            mnemonic, _unit, value, _description = parse_section_line(stripped)
            key = mnemonic.upper()
            if key == "VERS":
                version = value
            elif key == "WRAP":
                wrap = value
            continue
        if section == "well":
            mnemonic, _unit, value, _description = parse_section_line(stripped)
            well_fields[mnemonic.upper()] = value
            continue
        if section == "curve":
            if rows:
                raise ForcePreprocessError(
                    "curve definition after ASCII data rows", member_name, line_number
                )
            mnemonic, unit, _value, _description = parse_section_line(stripped)
            if not mnemonic:
                raise ForcePreprocessError("empty curve mnemonic", member_name, line_number)
            if any(name.upper() == mnemonic.upper() for name, _unit2 in curves):
                raise ForcePreprocessError(
                    "duplicate curve mnemonic", member_name, line_number
                )
            curves.append((mnemonic, unit))
            continue
        if section in ("ascii", "a"):
            tokens = stripped.split()
            if len(tokens) != len(curves):
                raise ForcePreprocessError(
                    "row has %d values for %d curves" % (len(tokens), len(curves)),
                    member_name,
                    line_number,
                )
            if null_value is None or index_by_channel is None:
                raise ForcePreprocessError(
                    "data row before NULL sentinel or curve mapping",
                    member_name,
                    line_number,
                )
            rows += 1
            depth = _strict_number(tokens[0], "depth", member_name, line_number)
            if depth == null_value:
                raise ForcePreprocessError("NULL depth value", member_name, line_number)
            if depth_previous is not None and depth < depth_previous:
                raise ForcePreprocessError(
                    "depth decreased from %r to %r" % (depth_previous, depth),
                    member_name,
                    line_number,
                )
            depth_previous = depth
            for channel in CHANNELS:
                fit = channels[channel]
                if channel in absent_channels:
                    fit.counts["absent"] += 1
                    continue
                value = _strict_number(
                    tokens[index_by_channel[channel]], channel, member_name, line_number
                )
                if value == null_value:
                    fit.counts["null"] += 1
                    continue
                if channel == "RDEP" and value <= 0.0:
                    fit.counts["nonpositive"] += 1
                    continue
                transformed = math.log10(value) if channel == "RDEP" else value
                if not math.isfinite(transformed):
                    raise ForcePreprocessError(
                        "non-finite transformed %s value %r" % (channel, value),
                        member_name,
                        line_number,
                    )
                fit.observe(transformed, member_name, line_number)
            continue
    if version != "2.0":
        raise ForcePreprocessError(
            "unsupported LAS version %r (expected 2.0)" % (version,), member_name
        )
    if wrap != "NO":
        raise ForcePreprocessError("unsupported WRAP %r (expected NO)" % (wrap,), member_name)
    if not curves:
        raise ForcePreprocessError("no curve definitions found", member_name)
    if rows == 0:
        raise ForcePreprocessError("member has no ASCII data rows", member_name)
    uwi = well_fields.get("UWI")
    if uwi is None or not uwi.strip():
        raise ForcePreprocessError("UWI missing", member_name)
    well_name = well_fields.get("WELL")
    if well_name is None or not well_name.strip():
        raise ForcePreprocessError("WELL name missing", member_name)
    return {
        "uwi": uwi,
        "well": well_name,
        "rows": rows,
        "null_value": null_value,
        "vers": version,
        "wrap": wrap,
        "curves": curves,
        "sha256": reader.hasher.hexdigest(),
        "bytes": reader.bytes_read,
    }



def _compare_member_to_inventory(record, inventory_record, member_name):
    """Refuse any drift between the decompressed member and the reviewed inventory."""
    _expect(
        record["sha256"] == inventory_record["member_sha256"],
        "member sha256 %s != reviewed inventory %s"
        % (record["sha256"], inventory_record["member_sha256"]),
        member_name,
    )
    _expect(
        record["bytes"] == inventory_record["member_size_bytes"],
        "member byte count %d != reviewed inventory %d"
        % (record["bytes"], inventory_record["member_size_bytes"]),
        member_name,
    )
    _expect(
        record["rows"] == inventory_record["rows"],
        "row count %d != reviewed inventory %d"
        % (record["rows"], inventory_record["rows"]),
        member_name,
    )
    _expect(
        record["uwi"] == inventory_record["uwi"],
        "UWI %r != reviewed inventory %r" % (record["uwi"], inventory_record["uwi"]),
        member_name,
    )
    _expect(
        record["well"] == inventory_record["well"],
        "WELL name %r != reviewed inventory %r"
        % (record["well"], inventory_record["well"]),
        member_name,
    )
    _expect(
        record["null_value"] == inventory_record["null_value"],
        "NULL sentinel %r != reviewed inventory %r"
        % (record["null_value"], inventory_record["null_value"]),
        member_name,
    )
    _expect(
        record["vers"] == inventory_record["vers"],
        "VERS %r != reviewed inventory %r" % (record["vers"], inventory_record["vers"]),
        member_name,
    )
    _expect(
        record["wrap"] == inventory_record["wrap"],
        "WRAP %r != reviewed inventory %r" % (record["wrap"], inventory_record["wrap"]),
        member_name,
    )
    expected_curves = [
        (curve["mnemonic"], curve["unit"]) for curve in inventory_record["curves"]
    ]
    _expect(
        record["curves"] == expected_curves,
        "curve identities %r != reviewed inventory %r"
        % (record["curves"], expected_curves),
        member_name,
    )


def fit_preprocessing(
    archive_path=None,
    inventory_path=None,
    splits_path=None,
    policy_path=None,
    label_path=None,
    out=None,
    *,
    expected_archive_bytes=PINNED_ARCHIVE_BYTES,
    expected_archive_sha256=PINNED_ARCHIVE_SHA256,
    expected_inventory_sha256=PINNED_INVENTORY_SHA256,
    expected_splits_sha256=PINNED_SPLITS_SHA256,
    expected_well_counts=None,
    expected_group_counts=None,
    expected_curve_order=None,
    chunk_bytes=DEFAULT_CHUNK_BYTES,
    generated_utc=None,
):
    """Fit the four-channel train-only statistics and return the document.

    Every pinned expectation can be overridden explicitly (used by the
    synthetic unit tests); the CLI passes no overrides, so the pinned
    constants above apply to the real frozen inputs.  Only
    ``split == "train"`` members are ever decompressed: non-training members
    are cross-checked at manifest level only (ZIP directory names, inventory
    records, split rows) and never opened.  Writes ``out`` as JSON when
    given and returns the document either way.
    """
    archive = pathlib.Path(archive_path) if archive_path else _DEFAULT_ARCHIVE
    inventory_file = pathlib.Path(inventory_path) if inventory_path else _DEFAULT_INVENTORY
    splits_file = pathlib.Path(splits_path) if splits_path else _DEFAULT_SPLITS
    policy_file = pathlib.Path(policy_path) if policy_path else _DEFAULT_POLICY
    label_file = pathlib.Path(label_path) if label_path else _DEFAULT_LABEL
    output_file = pathlib.Path(out) if out is not None else None
    if expected_well_counts is None:
        expected_well_counts = PINNED_WELL_COUNTS
    if expected_group_counts is None:
        expected_group_counts = PINNED_GROUP_COUNTS
    if expected_curve_order is None:
        expected_curve_order = list(CHANNELS)
    else:
        expected_curve_order = list(expected_curve_order)
    pinned_expectations = (
        expected_archive_bytes == PINNED_ARCHIVE_BYTES
        and expected_archive_sha256 == PINNED_ARCHIVE_SHA256
        and expected_inventory_sha256 == PINNED_INVENTORY_SHA256
        and expected_splits_sha256 == PINNED_SPLITS_SHA256
        and expected_well_counts == PINNED_WELL_COUNTS
        and expected_group_counts == PINNED_GROUP_COUNTS
        and expected_curve_order == list(CHANNELS)
    )
    _expect(
        type(chunk_bytes) is int and chunk_bytes > 0,
        "chunk_bytes must be a positive integer",
    )
    if expected_archive_bytes is not None:
        _expect(
            type(expected_archive_bytes) is int and expected_archive_bytes > 0,
            "expected_archive_bytes must be a positive integer",
        )
    for name, digest in (
        ("expected_archive_sha256", expected_archive_sha256),
        ("expected_inventory_sha256", expected_inventory_sha256),
        ("expected_splits_sha256", expected_splits_sha256),
    ):
        _expect(
            digest is None or _is_hex64(str(digest).lower()),
            "%s must be a 64-character hex digest when given" % name,
        )
    for counts_name, counts in (
        ("expected_well_counts", expected_well_counts),
        ("expected_group_counts", expected_group_counts),
    ):
        _expect(isinstance(counts, dict), "%s must be a mapping" % counts_name)
        for split_name in REQUIRED_SPLITS:
            _expect(
                type(counts.get(split_name)) is int and counts[split_name] >= 0,
                "%s[%s] must be a non-negative integer" % (counts_name, split_name),
            )

    # 1. Full archive byte/SHA256 verification before any ingest.
    archive_sha256, archive_bytes = _sha256_file(archive)
    if expected_archive_bytes is not None:
        _expect(
            archive_bytes == expected_archive_bytes,
            "archive byte count %d != expected %d"
            % (archive_bytes, expected_archive_bytes),
        )
    if expected_archive_sha256 is not None:
        _expect(
            archive_sha256 == str(expected_archive_sha256).lower(),
            "archive sha256 %s != expected %s" % (archive_sha256, expected_archive_sha256),
        )

    # 2. Manifest file hashes before any parse.
    inventory_sha256, _ = _sha256_file(inventory_file)
    if expected_inventory_sha256 is not None:
        _expect(
            inventory_sha256 == str(expected_inventory_sha256).lower(),
            "inventory sha256 %s != expected %s"
            % (inventory_sha256, expected_inventory_sha256),
        )
    splits_sha256, _ = _sha256_file(splits_file)
    if expected_splits_sha256 is not None:
        _expect(
            splits_sha256 == str(expected_splits_sha256).lower(),
            "splits sha256 %s != expected %s" % (splits_sha256, expected_splits_sha256),
        )
    policy_sha256, _ = _sha256_file(policy_file)
    label_sha256, _ = _sha256_file(label_file)

    inventory = _load_json(inventory_file, "reviewed inventory")
    splits = _load_json(splits_file, "splits manifest")
    policy = _load_json(policy_file, "split policy")
    label = _load_json(label_file, "label schema")

    # 3. Contract blocks and manifest cross references.
    _check_contract(splits, "splits manifest")
    _check_contract(policy, "split policy")
    _check_contract(label, "label schema")
    _expect(
        splits.get("inventory_sha256") == inventory_sha256,
        "splits manifest inventory_sha256 does not match the inventory file",
    )
    _expect(
        splits.get("source_archive_sha256") == archive_sha256,
        "splits manifest source_archive_sha256 does not match the archive bytes",
    )
    _expect(
        splits.get("policy_sha256") == policy_sha256,
        "splits manifest policy_sha256 does not match the split policy file",
    )
    _expect(
        splits.get("label_schema_sha256") == label_sha256,
        "splits manifest label_schema_sha256 does not match the label schema file",
    )

    # 4. Frozen curve order control; label/confidence values are never parsed.
    policy_preprocessing = policy.get("preprocessing")
    _expect(
        isinstance(policy_preprocessing, dict),
        "split policy is missing the preprocessing block",
    )
    _expect(
        policy_preprocessing.get("curve_order") == expected_curve_order,
        "policy curve_order %r != frozen order %r"
        % (policy_preprocessing.get("curve_order"), expected_curve_order),
    )
    _expect(
        label.get("input_curve_order") == expected_curve_order,
        "label schema input_curve_order %r != frozen order %r"
        % (label.get("input_curve_order"), expected_curve_order),
    )

    # 5. Declared split sizes.
    well_counts = splits.get("well_counts")
    group_counts = splits.get("group_counts")
    _expect(isinstance(well_counts, dict), "splits manifest is missing well_counts")
    _expect(isinstance(group_counts, dict), "splits manifest is missing group_counts")
    for split_name in REQUIRED_SPLITS:
        _expect(
            well_counts.get(split_name) == expected_well_counts[split_name],
            "well_counts[%s] = %r != expected %r"
            % (split_name, well_counts.get(split_name), expected_well_counts[split_name]),
        )
        _expect(
            group_counts.get(split_name) == expected_group_counts[split_name],
            "group_counts[%s] = %r != expected %r"
            % (split_name, group_counts.get(split_name), expected_group_counts[split_name]),
        )

    # 6. Reviewed inventory manifest validation (needed for per-row identity).
    _expect(
        inventory.get("kind") == "deepeye-force-las-inventory",
        "unexpected inventory kind %r" % (inventory.get("kind"),),
    )
    wells = inventory.get("wells")
    _expect(
        isinstance(wells, list) and wells,
        "reviewed inventory wells must be a non-empty list",
    )
    inventory_by_member = {}
    inventory_uwis = set()
    for record in wells:
        _expect(isinstance(record, dict), "inventory well entry must be an object")
        member = record.get("member")
        _expect(
            isinstance(member, str) and bool(member),
            "inventory well entry has no member path",
        )
        _safe_member_path(member)
        _expect(
            member not in inventory_by_member,
            "duplicate inventory member %r" % (member,),
        )
        _expect(
            _is_hex64(record.get("member_sha256")),
            "inventory member %r has no valid member_sha256" % (member,),
        )
        size = record.get("member_size_bytes")
        _expect(
            type(size) is int and size > 0,
            "inventory member %r has invalid member_size_bytes %r" % (member, size),
        )
        row_count = record.get("rows")
        _expect(
            type(row_count) is int and row_count >= 0,
            "inventory member %r has invalid rows %r" % (member, row_count),
        )
        uwi = record.get("uwi")
        _expect(
            isinstance(uwi, str) and bool(uwi),
            "inventory member %r has no uwi" % (member,),
        )
        _expect(
            uwi not in inventory_uwis,
            "duplicate inventory UWI %r" % (uwi,),
        )
        inventory_uwis.add(uwi)
        _expect(
            isinstance(record.get("well"), str) and bool(record["well"]),
            "inventory member %r has no well name" % (member,),
        )
        null_value = record.get("null_value")
        _expect(
            type(null_value) in (int, float) and math.isfinite(float(null_value)),
            "inventory member %r has invalid null_value %r" % (member, null_value),
        )
        _expect(
            record.get("vers") == "2.0",
            "inventory member %r has unsupported VERS %r" % (member, record.get("vers")),
        )
        _expect(
            record.get("wrap") == "NO",
            "inventory member %r has unsupported WRAP %r" % (member, record.get("wrap")),
        )
        _expect(
            record.get("crc_verified") is True,
            "inventory member %r is not CRC-verified" % (member,),
        )
        curve_list = record.get("curves")
        _expect(
            isinstance(curve_list, list) and curve_list,
            "inventory member %r has no curves" % (member,),
        )
        for curve in curve_list:
            _expect(
                isinstance(curve, dict)
                and isinstance(curve.get("mnemonic"), str)
                and bool(curve["mnemonic"])
                and isinstance(curve.get("unit"), str),
                "inventory member %r has an invalid curve entry" % (member,),
            )
        inventory_by_member[member] = record

    # 7. Row-level identity and manifest validation in file order.
    rows = splits.get("rows")
    _expect(
        isinstance(rows, list) and rows,
        "splits manifest rows must be a non-empty list",
    )
    seen_members = {}
    seen_row_ids = set()
    seen_wells = {}
    train_rows = []
    counted_wells = {split_name: 0 for split_name in REQUIRED_SPLITS}
    counted_groups = {split_name: set() for split_name in REQUIRED_SPLITS}
    for position, row in enumerate(rows):
        _expect(isinstance(row, dict), "splits rows[%d] must be an object" % position)
        row_id = row.get("row_id")
        _expect(
            isinstance(row_id, str) and bool(row_id),
            "splits rows[%d] has no row_id" % position,
        )
        _expect(
            row_id not in seen_row_ids,
            "duplicate split row_id %r" % (row_id,),
        )
        seen_row_ids.add(row_id)
        member = row.get("member")
        _expect(
            isinstance(member, str) and bool(member),
            "splits rows[%d] has no member path" % position,
        )
        _safe_member_path(member)
        _expect(member not in seen_members, "duplicate split member %r" % (member,))
        _expect(
            _is_hex64(row.get("member_sha256")),
            "splits member %r has no valid member_sha256" % (member,),
        )
        split_name = row.get("split")
        _expect(
            split_name in REQUIRED_SPLITS,
            "splits member %r has unknown split %r" % (member, split_name),
        )
        root_id = row.get("root_id")
        _expect(
            isinstance(root_id, str) and bool(root_id),
            "splits member %r has no root_id" % (member,),
        )
        source_domain = row.get("source_domain")
        _expect(
            isinstance(source_domain, str) and bool(source_domain),
            "splits member %r has no source_domain" % (member,),
        )
        derived_from = row.get("derived_from")
        _expect(
            derived_from is None
            or (isinstance(derived_from, str) and bool(derived_from)),
            "splits member %r has an invalid derived_from" % (member,),
        )
        inventory_record = inventory_by_member.get(member)
        _expect(
            inventory_record is not None,
            "split member %r is missing from the reviewed inventory" % (member,),
            member,
        )
        _expect(
            row["member_sha256"] == inventory_record["member_sha256"],
            "split member sha256 does not match the reviewed inventory",
            member,
        )
        well_id = row.get("well_id")
        _expect(
            isinstance(well_id, str) and bool(well_id),
            "splits member %r has no well_id" % (member,),
            member,
        )
        _expect(
            well_id == inventory_record["uwi"],
            "split well_id %r does not match the reviewed inventory UWI %r"
            % (well_id, inventory_record["uwi"]),
            member,
        )
        well_key = (source_domain, well_id)
        _expect(
            well_key not in seen_wells,
            "well %r in domain %r appears in multiple split rows (%r and %r)"
            % (well_id, source_domain, seen_wells.get(well_key), member),
            member,
        )
        seen_wells[well_key] = member
        parent_well = _force_parent_well(well_id)
        _expect(
            parent_well is not None,
            "well_id %r does not match the frozen FORCE parent-well rule" % (well_id,),
            member,
        )
        _expect(
            root_id == parent_well,
            "root_id %r is not the derived parent well %r of well_id %r"
            % (root_id, parent_well, well_id),
            member,
        )
        counted_wells[split_name] += 1
        counted_groups[split_name].add((source_domain, root_id))
        seen_members[member] = row
        if split_name == "train":
            train_rows.append(row)
    for split_name in REQUIRED_SPLITS:
        _expect(
            counted_wells[split_name] == well_counts[split_name],
            "splits rows give %d %s wells but well_counts declares %r"
            % (counted_wells[split_name], split_name, well_counts[split_name]),
        )
        _expect(
            len(counted_groups[split_name]) == group_counts[split_name],
            "splits rows give %d %s parent groups but group_counts declares %r"
            % (len(counted_groups[split_name]), split_name, group_counts[split_name]),
        )

    # 8. Complete grouping/derivative validation (read-only data/grouping.py).
    grouping_helper = _load_grouping_helper()
    grouping_rows = [
        {
            "row_id": row["row_id"],
            "source_domain": row["source_domain"],
            "root_id": row["root_id"],
            "split": row["split"],
            "derived_from": row.get("derived_from"),
        }
        for row in rows
    ]
    try:
        grouping_report = grouping_helper.validate_split_assignments(grouping_rows)
    except grouping_helper.SplitAssignmentError as error:
        raise ForcePreprocessError("split grouping rejected: %s" % (error,))

    # 9. Manifest set cross-check (archive directory, inventory, splits).
    channels = {channel: _ChannelFit(channel) for channel in CHANNELS}
    fitting_wells = []
    train_rows_total = 0
    try:
        with zipfile.ZipFile(archive) as archive_zip:
            names = archive_zip.namelist()
            _expect(len(names) == len(set(names)), "archive contains duplicate member paths")
            for name in names:
                _safe_member_path(name)
            _expect(
                set(names) == set(inventory_by_member),
                "archive members do not match the reviewed inventory",
            )
            _expect(
                set(seen_members) == set(inventory_by_member),
                "splits members do not match the reviewed inventory",
            )

            # 10. Train-only streaming fit in deterministic split row order.
            for row in train_rows:
                member = row["member"]
                inventory_record = inventory_by_member[member]
                _expect(
                    row["member_sha256"] == inventory_record["member_sha256"],
                    "split member sha256 does not match the reviewed inventory",
                    member,
                )
                try:
                    with archive_zip.open(member) as stream:
                        record = _fit_member(stream, member, chunk_bytes, channels)
                        if stream.read(1):
                            raise ForcePreprocessError(
                                "member stream not consumed completely", member
                            )
                except zipfile.BadZipFile as error:
                    raise ForcePreprocessError(
                        "member read or CRC failure: %s" % (error,), member
                    )
                _compare_member_to_inventory(record, inventory_record, member)
                train_rows_total += record["rows"]
                fitting_wells.append(
                    {
                        "member": member,
                        "member_sha256": record["sha256"],
                        "uwi": record["uwi"],
                        "well": record["well"],
                        "rows": record["rows"],
                        "crc_verified": True,
                    }
                )
    except zipfile.BadZipFile as error:
        raise ForcePreprocessError("archive is not a readable ZIP: %s" % (error,))

    # 11. Finalize population statistics; all-missing channels BLOCK.
    channel_reports = []
    for channel in CHANNELS:
        fit = channels[channel]
        valid = fit.counts["valid"]
        if valid == 0:
            raise ForcePreprocessBlocked(
                "channel %s has no valid training samples (counts=%s); "
                "refusing to invent a scale" % (channel, fit.counts)
            )
        variance = fit.m2 / valid
        _expect(
            math.isfinite(variance) and variance >= 0.0,
            "non-finite or negative variance for channel %s" % channel,
        )
        std = math.sqrt(variance)
        _expect(
            math.isfinite(std) and math.isfinite(fit.mean),
            "non-finite statistics for channel %s" % channel,
        )
        zero_variance = variance == 0.0
        channel_reports.append(
            {
                "name": channel,
                "unit": fit.unit,
                "transform_version": TRANSFORM_VERSIONS[channel],
                "counts": dict(fit.counts),
                "valid_samples": valid,
                "mean": fit.mean,
                "variance": variance,
                "std": std,
                "zero_variance": zero_variance,
                "effective_scale": 1.0 if zero_variance else std,
            }
        )

    document = {
        "schema": 1,
        "kind": "deepeye-force-preprocess",
        "generated_utc": generated_utc or _utc_now(),
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "contract": {
            "id": CONTRACT_ID,
            "revision": CONTRACT_REVISION,
            "source_commit": SOURCE_COMMIT,
            "requirements_sha256": REQUIREMENTS_SHA256,
            "design_commit": DESIGN_COMMIT,
        },
        "status": "software_only_fit_complete_c01_not_run",
        "expectations": "pinned constants" if pinned_expectations else "explicit overrides",
        "algorithm": {
            "name": ALGORITHM_VERSION,
            "channel_order": list(CHANNELS),
            "column_parsing": "depth column and the four selected channel columns only; every other column is validated for cardinality but never parsed numerically",
            "fit_order": "deterministic splits.json rows order, train rows only",
            "statistics": "population mean and population variance from a numerically stable one-pass Welford accumulation over valid transformed train samples only",
            "missing_policy": "LAS NULL is missing; imputation centers with the train mean and an explicit zero mask",
            "zero_variance_policy": "variance 0 is recorded; std 0; effective_scale 1.0 explicitly",
        },
        "inputs": {
            "archive": {
                "path": str(archive),
                "bytes": archive_bytes,
                "sha256": archive_sha256,
            },
            "inventory": {"path": str(inventory_file), "sha256": inventory_sha256},
            "splits": {
                "path": str(splits_file),
                "sha256": splits_sha256,
                "well_counts": dict(well_counts),
                "group_counts": dict(group_counts),
            },
            "policy": {"path": str(policy_file), "sha256": policy_sha256},
            "label_schema": {
                "path": str(label_file),
                "sha256": label_sha256,
                "usage": "curve-order control only; label and confidence values are never parsed or fitted",
            },
            "helpers": {
                "force_inventory": {
                    "path": str(_HERE / "force_inventory.py"),
                    "sha256": _sha256_file(_HERE / "force_inventory.py")[0],
                },
                "grouping": {
                    "path": str(_HERE / "grouping.py"),
                    "sha256": _sha256_file(_HERE / "grouping.py")[0],
                },
            },
        },
        "channels": channel_reports,
        "train": {
            "wells": len(fitting_wells),
            "parent_groups": group_counts.get("train"),
            "data_rows": train_rows_total,
        },
        "grouping_validation": {
            "validator": "data/grouping.py:validate_split_assignments",
            "rows": grouping_report.rows,
            "root_count": grouping_report.root_count,
            "split_rows": dict(grouping_report.split_rows),
            "domains": {
                domain: {
                    "rows": summary.rows,
                    "roots": summary.roots,
                    "derivatives": summary.derivatives,
                    "split_rows": dict(summary.split_rows),
                }
                for domain, summary in grouping_report.domains.items()
            },
        },
        "fitting_wells": fitting_wells,
        "software_only": True,
        "product_card_c01": "not_run",
        "limits": [
            "Software-only preprocessing fit from the offline public FORCE 2020 wells; no model training, no causal replay windows, no verify_data entrypoint and no online scene.",
            "Not C01 acceptance, not calibration and not evidence of real sensor capability; all product and hardware cards remain not_run.",
            "No validation/test statistics were computed; held-out members were cross-checked at manifest level only and never decompressed.",
        ],
    }
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    return document



def _load_expectations(path):
    """Load an explicit expectations override file (used by unit tests)."""
    document = _load_json(path, "expectations file")
    _expect(isinstance(document, dict), "expectations file must be a JSON object")
    allowed = {
        "archive_bytes",
        "archive_sha256",
        "inventory_sha256",
        "splits_sha256",
        "well_counts",
        "group_counts",
        "curve_order",
    }
    unknown = sorted(set(document) - allowed)
    _expect(not unknown, "unknown expectations keys: %s" % (", ".join(unknown),))
    overrides = {}
    mapping = {
        "archive_bytes": "expected_archive_bytes",
        "archive_sha256": "expected_archive_sha256",
        "inventory_sha256": "expected_inventory_sha256",
        "splits_sha256": "expected_splits_sha256",
        "well_counts": "expected_well_counts",
        "group_counts": "expected_group_counts",
        "curve_order": "expected_curve_order",
    }
    for key, value in document.items():
        overrides[mapping[key]] = value
    return overrides


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "C01 train-only preprocessing fitter for the FORCE 2020 LAS archive "
            "(software-only; no training, no acceptance)."
        )
    )
    parser.add_argument("--zip", dest="archive", default=None, help="FORCE LAS archive path")
    parser.add_argument("--inventory", default=None, help="reviewed inventory JSON path")
    parser.add_argument("--splits", default=None, help="frozen split manifest path")
    parser.add_argument("--policy", default=None, help="frozen split policy path")
    parser.add_argument("--label", dest="label_schema", default=None, help="label schema path")
    parser.add_argument(
        "--out",
        default=None,
        help="output JSON path (default: data/preprocessing.json)",
    )
    parser.add_argument(
        "--expectations",
        default=None,
        help=(
            "optional JSON file overriding the pinned archive/manifest expectations "
            "(synthetic tests only); the default run uses the pinned constants"
        ),
    )
    args = parser.parse_args(argv)
    overrides = {}
    if args.expectations:
        try:
            overrides = _load_expectations(args.expectations)
        except ForcePreprocessError as error:
            print("FAILED: " + str(error), file=sys.stderr)
            return 1
    output_path = args.out if args.out else _DEFAULT_OUT
    try:
        document = fit_preprocessing(
            archive_path=args.archive,
            inventory_path=args.inventory,
            splits_path=args.splits,
            policy_path=args.policy,
            label_path=args.label_schema,
            out=output_path,
            **overrides,
        )
    except ForcePreprocessBlocked as error:
        print("BLOCKED: " + str(error), file=sys.stderr)
        return 3
    except ForcePreprocessError as error:
        print("FAILED: " + str(error), file=sys.stderr)
        return 1
    valid = {channel["name"]: channel["valid_samples"] for channel in document["channels"]}
    print(
        "ok train_wells=%d train_rows=%d valid=%s out=%s"
        % (
            document["train"]["wells"],
            document["train"]["data_rows"],
            ",".join("%s:%d" % (name, valid[name]) for name in CHANNELS),
            output_path,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Bounded streaming inventory of the FORCE 2020 LAS archive (stdlib only).

Offline data audit of the already-verified local ZIP: the archive is never
extracted to disk, every member is streamed with bounded memory, each exact
decompressed member is SHA256-hashed, and the ZIP CRC is verified by complete
reads (zipfile raises on mismatch at end of stream). Only aggregate facts are
recorded: counts, minima, maxima, simple monotonic diagnostics and label
histograms. Row-level values are intentionally not exported.

Non-goals: no train/test split selection, no statistics fitting, no model
training or evaluation, and no reading of any online scene truth. The
lithology code/confidence histograms are an offline dataset audit, not a
held-out model evaluation; any split must be frozen later, independently of
outcomes. A successful run is software-only evidence.

Parsing rules (LAS 2.0, as observed in the verified archive):
- line terminators LF, CRLF or lone CR are accepted; a CRCRLF sequence yields a
  blank line, which is skipped and counted explicitly;
- section headers start with '~'; '#' starts a comment line;
- section lines are "MNEM.UNIT VALUE : DESCRIPTION";
- the ~Well section must provide a non-empty UWI, a parseable NULL sentinel and
  was observed to carry STRT/STOP/STEP; VERS must be 2.0 and WRAP must be NO
  (WRAP YES is refused: wrapped records change row semantics);
- VERS/WRAP/UWI/NULL may repeat before ASCII only with identical parsed text;
  conflicting duplicates and every declaration after the first ASCII marker
  are refused, including declarations before that section's first row;
- '~A'/'~Ascii' rows are whitespace-separated ASCII numbers, exactly one per
  curve, each finite; a value equal to the declared NULL sentinel counts as
  missing, and other negative values remain valid data;
- malformed rows, non-numeric tokens, non-ASCII bytes, missing sections,
  unsafe member paths and duplicate UWI values are refused with member and
  line information (nonzero exit), never silently dropped or clipped.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import sys
import zipfile

__all__ = [
    "LasInventoryError",
    "iter_las_lines",
    "parse_section_line",
    "inventory_las_member",
    "inventory_archive",
    "main",
]

FORCE_DOI = "10.5281/zenodo.4351156"
FORCE_RECORD_URL = "https://zenodo.org/records/4351156"
FORCE_REPO_URL = "https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition"
FORCE_REPO_COMMIT = "c8d01ee92c1c8e1ecba36f96cca6ea7b689338a1"
LITHOLOGY_MNEMONIC = "FORCE_2020_LITHOFACIES_LITHOLOGY"
CONFIDENCE_MNEMONIC = "FORCE_2020_LITHOFACIES_CONFIDENCE"
SUPPORTED_VERSION = "2.0"
DEFAULT_CHUNK_BYTES = 1 << 20

_PROVENANCE_NOTE = (
    "Offline data audit only. No train/test split selection, no statistics "
    "fitting beyond counts/min/max, no model training or evaluation. Label "
    "histograms are dataset audit counts, not held-out model evaluation; any "
    "split must be frozen later and independently of outcomes. Row-level "
    "values are not included; histogram keys are exact numeric values and the "
    "declared NULL sentinel appears under its own key."
)


class LasInventoryError(Exception):
    """Malformed, unsupported or unsafe LAS input (never silently dropped)."""

    def __init__(self, message, member=None, line=None):
        if member is not None:
            location = "member=" + str(member)
            if line is not None:
                location += " line=" + str(line)
            message = location + ": " + message
        super().__init__(message)
        self.member = member
        self.line = line


def iter_las_lines(stream, chunk_bytes=DEFAULT_CHUNK_BYTES):
    """Yield raw line bytes without terminators from a binary stream.

    Terminators are LF, CRLF and lone CR. CRCRLF yields one blank line in
    addition to the preceding line; blank lines are counted by the parser.
    Memory use is bounded by one chunk plus the current line.
    """
    if type(chunk_bytes) is not int or chunk_bytes <= 0:
        raise LasInventoryError("chunk_bytes must be a positive integer")
    buffer = bytearray()
    position = 0
    eof = False
    while True:
        i_cr = buffer.find(13, position)
        i_lf = buffer.find(10, position)
        if i_cr == -1 and i_lf == -1:
            if eof:
                if position < len(buffer):
                    yield bytes(buffer[position:])
                return
            block = stream.read(chunk_bytes)
            if not block:
                eof = True
            else:
                if position:
                    del buffer[:position]
                    position = 0
                buffer += block
            continue
        if i_lf != -1 and (i_cr == -1 or i_lf < i_cr):
            yield bytes(buffer[position:i_lf])
            position = i_lf + 1
            continue
        if i_cr + 1 >= len(buffer):
            if not eof:
                block = stream.read(chunk_bytes)
                if block:
                    if position:
                        del buffer[:position]
                        position = 0
                    buffer += block
                    continue
                eof = True
            yield bytes(buffer[position:i_cr])
            position = i_cr + 1
            continue
        if buffer[i_cr + 1] == 10:
            yield bytes(buffer[position:i_cr])
            position = i_cr + 2
        else:
            yield bytes(buffer[position:i_cr])
            position = i_cr + 1

def parse_section_line(line):
    """Split "MNEM.UNIT VALUE : DESCRIPTION" into (mnemonic, unit, value, description)."""
    left, _, right = line.partition(":")
    mnemonic, has_dot, remainder = left.partition(".")
    mnemonic = mnemonic.strip()
    if has_dot and remainder[:1] and not remainder[:1].isspace():
        tokens = remainder.split(None, 1)
        unit = tokens[0]
        value = tokens[1].strip() if len(tokens) > 1 else ""
    else:
        unit = ""
        value = remainder.strip()
    return mnemonic, unit, value, right.strip()


def _format_value(value):
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(value)


def _find_curve(curves, mnemonic):
    for index, (name, _unit) in enumerate(curves):
        if name.upper() == mnemonic:
            return index
    return None


def _parse_null(text):
    if text is None:
        return None
    tokens = text.split()
    if not tokens:
        return None
    try:
        value = float(tokens[0])
        return value if math.isfinite(value) else None
    except ValueError:
        return None


def _record_critical_header(headers, key, value, ascii_started, error_type,
                            member_name, line_number):
    """Apply the same critical-header policy in inventory and fitting.

    Compare the parsed value text, without silently normalizing declarations.
    Identical duplicates are harmless only before the first ASCII marker;
    once row interpretation is frozen even an identical declaration is late.
    """
    if ascii_started:
        raise error_type(key + " header after ASCII data section", member_name, line_number)
    if key in headers and headers[key] != value:
        raise error_type("conflicting duplicate " + key + " header", member_name, line_number)
    headers[key] = value


def _check_member_path(name):
    if not name or name.endswith("/"):
        raise LasInventoryError("unsafe or unsupported member path", name)
    if "\\" in name or ":" in name or name.startswith("/"):
        raise LasInventoryError("unsafe member path", name)
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise LasInventoryError("unsafe member path", name)
    if not name.lower().endswith(".las"):
        raise LasInventoryError("unsupported member extension (expected .las)", name)


class _HashingStream:
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


def inventory_las_member(stream, member_name, member_size, chunk_bytes=DEFAULT_CHUNK_BYTES):
    """Parse one member stream into an aggregate inventory record."""
    reader = _HashingStream(stream)
    section = None
    section_names = []
    version = None
    wrap = None
    critical_headers = {}
    ascii_started = False
    well_fields = {}
    curves = []
    counts = []
    null_counts = []
    rows = 0
    blank_lines = 0
    comment_lines = 0
    depth_null = 0
    depth_min = None
    depth_max = None
    depth_previous = None
    increasing_steps = 0
    duplicate_steps = 0
    decreasing_steps = 0
    step_min = None
    step_max = None
    lithology_index = None
    confidence_index = None
    lithology_histogram = {}
    confidence_histogram = {}
    null_value = None

    for line_number, raw_line in enumerate(iter_las_lines(reader, chunk_bytes), 1):
        try:
            line = raw_line.decode("ascii")
        except UnicodeDecodeError:
            raise LasInventoryError("non-ASCII byte in line", member_name, line_number)
        stripped = line.strip()
        if not stripped:
            blank_lines += 1
            continue
        if stripped.startswith("#"):
            comment_lines += 1
            continue
        if stripped.startswith("~"):
            body = stripped[1:].strip()
            section = body.split()[0].lower() if body else ""
            if section not in section_names:
                section_names.append(section)
            if section in ("ascii", "a"):
                ascii_started = True
                if not curves:
                    raise LasInventoryError(
                        "ASCII data section before curve definitions", member_name, line_number
                    )
                if lithology_index is None:
                    lithology_index = _find_curve(curves, LITHOLOGY_MNEMONIC)
                    confidence_index = _find_curve(curves, CONFIDENCE_MNEMONIC)
                if null_value is None:
                    null_value = _parse_null(well_fields.get("NULL"))
                if null_value is None:
                    raise LasInventoryError(
                        "NULL sentinel missing before data section", member_name, line_number
                    )
            continue
        if section == "version":
            mnemonic, _unit, value, _description = parse_section_line(stripped)
            key = mnemonic.upper()
            if key in ("VERS", "WRAP"):
                _record_critical_header(
                    critical_headers, key, value, ascii_started, LasInventoryError,
                    member_name, line_number,
                )
            if key == "VERS":
                version = value
            elif key == "WRAP":
                wrap = value
            continue
        if section == "well":
            mnemonic, _unit, value, _description = parse_section_line(stripped)
            key = mnemonic.upper()
            if key in ("UWI", "NULL"):
                _record_critical_header(
                    critical_headers, key, value, ascii_started, LasInventoryError,
                    member_name, line_number,
                )
            well_fields[key] = value
            continue
        if section == "curve":
            if counts:
                raise LasInventoryError(
                    "curve definition after ASCII data rows", member_name, line_number
                )
            mnemonic, unit, _value, _description = parse_section_line(stripped)
            if not mnemonic:
                raise LasInventoryError("empty curve mnemonic", member_name, line_number)
            if any(name.upper() == mnemonic.upper() for name, _ in curves):
                raise LasInventoryError("duplicate curve mnemonic", member_name, line_number)
            curves.append((mnemonic, unit))
            continue
        if section in ("ascii", "a"):
            tokens = stripped.split()
            if len(tokens) != len(curves):
                raise LasInventoryError(
                    "row has %d values for %d curves" % (len(tokens), len(curves)),
                    member_name,
                    line_number,
                )
            values = []
            for token in tokens:
                try:
                    numeric = float(token)
                except ValueError:
                    raise LasInventoryError(
                        "non-numeric value %r" % (token,), member_name, line_number
                    )
                if not math.isfinite(numeric):
                    raise LasInventoryError(
                        "non-finite value %r" % (token,), member_name, line_number
                    )
                values.append(numeric)
            if not counts:
                counts = [0] * len(curves)
                null_counts = [0] * len(curves)
                if null_value is None:
                    null_value = _parse_null(well_fields.get("NULL"))
                if null_value is None:
                    raise LasInventoryError(
                        "NULL sentinel missing or unparseable before data section",
                        member_name,
                        line_number,
                    )
            rows += 1
            for index, numeric in enumerate(values):
                counts[index] += 1
                if numeric == null_value:
                    null_counts[index] += 1
                if index == 0:
                    if numeric == null_value:
                        depth_null += 1
                    else:
                        if depth_min is None or numeric < depth_min:
                            depth_min = numeric
                        if depth_max is None or numeric > depth_max:
                            depth_max = numeric
                        if depth_previous is not None:
                            difference = numeric - depth_previous
                            if difference > 0.0:
                                increasing_steps += 1
                            elif difference == 0.0:
                                duplicate_steps += 1
                            else:
                                decreasing_steps += 1
                            if step_min is None or difference < step_min:
                                step_min = difference
                            if step_max is None or difference > step_max:
                                step_max = difference
                        depth_previous = numeric
                if index == lithology_index:
                    key = _format_value(numeric)
                    lithology_histogram[key] = lithology_histogram.get(key, 0) + 1
                elif index == confidence_index:
                    key = _format_value(numeric)
                    confidence_histogram[key] = confidence_histogram.get(key, 0) + 1
            continue
        # parameter/other/unknown sections: content lines are not records
        continue

    if version is None:
        raise LasInventoryError("missing VERS line in version section", member_name)
    if version != SUPPORTED_VERSION:
        raise LasInventoryError(
            "unsupported LAS version %r (expected %s)" % (version, SUPPORTED_VERSION),
            member_name,
        )
    if wrap is None:
        raise LasInventoryError("missing WRAP line in version section", member_name)
    if wrap.upper() != "NO":
        raise LasInventoryError(
            "unsupported WRAP %r (WRAP YES changes row semantics and is refused)" % (wrap,),
            member_name,
        )
    if not curves:
        raise LasInventoryError("no curve definitions", member_name)
    if rows == 0:
        raise LasInventoryError("no ASCII data rows", member_name)
    uwi = well_fields.get("UWI", "")
    if not uwi:
        raise LasInventoryError("missing or empty UWI in well section", member_name)
    if reader.bytes_read != member_size:
        raise LasInventoryError("member byte count does not match declared size", member_name)

    depth_record = {
        "mnemonic": curves[0][0],
        "unit": curves[0][1],
        "count": rows,
        "null_count": depth_null,
        "min": depth_min,
        "max": depth_max,
        "increasing_steps": increasing_steps,
        "duplicate_steps": duplicate_steps,
        "decreasing_steps": decreasing_steps,
        "step_min": step_min,
        "step_max": step_max,
        "monotonic_nondecreasing": decreasing_steps == 0,
    }
    curve_records = []
    for index, (mnemonic, unit) in enumerate(curves):
        curve_records.append(
            {
                "mnemonic": mnemonic,
                "unit": unit,
                "count": counts[index] if counts else 0,
                "null_count": null_counts[index] if null_counts else 0,
                "nonmissing_count": (counts[index] - null_counts[index]) if counts else 0,
            }
        )
    return {
        "member": member_name,
        "member_size_bytes": member_size,
        "member_sha256": reader.hasher.hexdigest(),
        # A generic stream cannot establish a ZIP CRC. The archive wrapper
        # sets this only after zipfile completes its verified read.
        "crc_verified": None,
        "rows": rows,
        "blank_lines": blank_lines,
        "comment_lines": comment_lines,
        "sections": section_names,
        "vers": version,
        "wrap": wrap,
        "uwi": uwi,
        "well": well_fields.get("WELL", ""),
        "null_value": null_value,
        "strt": well_fields.get("STRT", ""),
        "stop": well_fields.get("STOP", ""),
        "step": well_fields.get("STEP", ""),
        "depth": depth_record,
        "curves": curve_records,
        "lithology_code_histogram": {
            "present": lithology_index is not None,
            "values": lithology_histogram,
        },
        "lithology_confidence_histogram": {
            "present": confidence_index is not None,
            "values": confidence_histogram,
        },
    }


def inventory_archive(
    zip_path,
    expected_bytes,
    expected_sha256,
    expected_md5=None,
    output_path=None,
    chunk_bytes=DEFAULT_CHUNK_BYTES,
):
    """Verify the archive bytes/hash, stream every member, return the document."""
    actual_bytes = os.path.getsize(zip_path)
    if actual_bytes != expected_bytes:
        raise LasInventoryError(
            "archive size %d != expected %d" % (actual_bytes, expected_bytes)
        )
    sha_hasher = hashlib.sha256()
    md5_hasher = hashlib.md5() if expected_md5 else None
    with open(zip_path, "rb") as handle:
        while True:
            block = handle.read(DEFAULT_CHUNK_BYTES)
            if not block:
                break
            sha_hasher.update(block)
            if md5_hasher is not None:
                md5_hasher.update(block)
    digest = sha_hasher.hexdigest()
    if digest != expected_sha256.lower():
        raise LasInventoryError(
            "archive sha256 %s != expected %s" % (digest, expected_sha256.lower())
        )
    if md5_hasher is not None and md5_hasher.hexdigest() != expected_md5.lower():
        raise LasInventoryError(
            "archive md5 %s != expected %s" % (md5_hasher.hexdigest(), expected_md5.lower())
        )

    records = []
    with zipfile.ZipFile(zip_path) as archive:
        infos = sorted(archive.infolist(), key=lambda info: info.filename)
        if not infos:
            raise LasInventoryError("archive contains no LAS members")
        if len({info.filename for info in infos}) != len(infos):
            raise LasInventoryError("duplicate member paths refused")
        for info in infos:
            _check_member_path(info.filename)
            if info.is_dir():
                raise LasInventoryError("directory entry not supported", info.filename)
            with archive.open(info) as member_stream:
                try:
                    record = inventory_las_member(
                        member_stream, info.filename, info.file_size, chunk_bytes
                    )
                    if member_stream.read(1):
                        raise LasInventoryError("member stream not consumed completely", info.filename)
                except zipfile.BadZipFile as error:
                    raise LasInventoryError(
                        "member read or CRC failure: %s" % (error,), info.filename
                    )
            record["crc_verified"] = True
            records.append(record)

    duplicates = {}
    seen = {}
    for record in records:
        seen.setdefault(record["uwi"], []).append(record["member"])
    for uwi, members in seen.items():
        if len(members) > 1:
            duplicates[uwi] = members
    if duplicates:
        raise LasInventoryError(
            "duplicate UWI values refused: "
            + json.dumps(duplicates, ensure_ascii=True, sort_keys=True)
        )

    missing_lithology = [
        record["member"] for record in records if not record["lithology_code_histogram"]["present"]
    ]
    missing_confidence = [
        record["member"]
        for record in records
        if not record["lithology_confidence_histogram"]["present"]
    ]
    document = {
        "schema": 1,
        "kind": "deepeye-force-las-inventory",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "provenance": {
            "dataset": "FORCE 2020 machine learning competition well logs",
            "doi": FORCE_DOI,
            "record_url": FORCE_RECORD_URL,
            "authors_repository": FORCE_REPO_URL,
            "authors_repository_commit": FORCE_REPO_COMMIT,
            "archive_file": os.path.basename(zip_path),
            "archive_bytes": actual_bytes,
            "archive_sha256": digest,
            "archive_md5": md5_hasher.hexdigest() if md5_hasher is not None else None,
            "receipt_reference": ".local/plan-20261014-final-c/director-startup/force-source/download.json",
            "notes": _PROVENANCE_NOTE,
        },
        "summary": {
            "members": len(records),
            "rows_total": sum(record["rows"] for record in records),
            "curves_total": sum(len(record["curves"]) for record in records),
            "duplicate_uwi": 0,
            "all_wrap_no": all(record["wrap"] == "NO" for record in records),
            "lithology_curve_missing_members": missing_lithology,
            "confidence_curve_missing_members": missing_confidence,
        },
        "wells": records,
    }
    if output_path is not None:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=1, ensure_ascii=True)
            handle.write("\n")
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Streaming FORCE LAS archive inventory (offline audit; no training)."
    )
    parser.add_argument("--zip", required=True, help="local archive path")
    parser.add_argument("--sha256", required=True, help="expected archive SHA256; verified before ingest")
    parser.add_argument("--bytes", required=True, type=int, dest="expected_bytes")
    parser.add_argument("--md5", default=None)
    parser.add_argument("--out", default=None, help="output JSON path")
    args = parser.parse_args(argv)
    try:
        document = inventory_archive(
            args.zip, args.expected_bytes, args.sha256, args.md5, args.out
        )
    except LasInventoryError as error:
        print("FAILED: " + str(error), file=sys.stderr)
        return 1
    summary = document["summary"]
    print(
        "ok members=%d rows=%d curves=%d all_wrap_no=%s out=%s"
        % (
            summary["members"],
            summary["rows_total"],
            summary["curves_total"],
            summary["all_wrap_no"],
            args.out,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

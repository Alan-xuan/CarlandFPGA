"""C01 causal input builder: deterministic 32-column summary windows.

Frozen source: ``taskbook_final.md`` C01 fixes the summary-model input as
``[1,13,32,1]`` - four means, four ranges, four valid masks and a normalised
age per window column, with startup history marked by masks and event peaks
entering only through the same channel adapter (never future samples).  This
module is the input-builder half of that profile on the C (PC AI) side.

Design boundaries, all deliberate:

* Pure and dependency-free (Python standard library only): no I/O, no global
  state, no hidden fitting.  Train-fitted scales and the profile age limit
  are explicit caller inputs; this module never estimates statistics from
  the records and never invents production channel normalisations.
* Only records bound to one (run_id, session_id, profile, epoch) are
  accepted.  Samples later than the caller's decision cutoff are excluded
  and counted; they never occupy a window column (the model window reads
  only current and history).
* A strict exact-field allowlist rejects unknown record fields, including
  truth/future/object/seed/oracle-style keys.  Unknown profiles, malformed
  schemas and inconsistent records raise :class:`CausalInputError`; schema
  handling never leaks ``TypeError``/``IndexError``/``KeyError``, and
  one-shot schema iterables (generators) are rejected instead of being
  silently consumed across validate/access calls.
* Synthetic fixtures must declare ``source_mode="software_fixture"`` and are
  never a claim of physical observation or licensed data.

``quality_flags`` semantics (one packed ``uint16`` per record, frozen
``runtime_gates.quality_bits`` layout; TELEM 0x01 carries it as two bytes):

    bits 0-3    valid, one bit per sensor channel (channel order below)
    bits 4-7    saturated, one bit per sensor channel
    bits 8-11   held (zero-order reuse), one bit per sensor channel
    bit 12      source_fault, applies to all four channels
    bits 13-15  grants, scheduling metadata only - never sensor validity

A channel mask is 1.0 exactly when ``valid && !saturated && !held &&
!fault && !stale``, where staleness is ``cutoff - tick_ms > age_limit_ms``.
``0x0000`` is invalid everywhere, ``0x000F`` is valid everywhere, ``0x100F``
is faulted everywhere, and ``0xE00F`` stays fully valid because grant bits
never mask sensor validity.  Held channels are zero-order reuse of earlier
acquisitions: repeated held deliveries of one acquisition are permitted and
never counted as fresh independent samples.

Time semantics: ``tick_ms`` is the TELEM last-included ADC acquisition tick
(never frame transmission time).  The per-channel native EM acquisition
tick is UNKNOWN from the legal board bytes, so ``source_native_tick_ms`` is
a computed output field that is always ``None`` here; it is never a caller
supplied sideband, and held channels keep their unknown native tick
honestly.  Summary age stays truthful: ``cutoff - tick_ms``.

Window policy (one model column per acquisition): transport records collapse
into exactly ONE summary column per distinct acquisition tick, sorted by
tick oldest first.  All arrivals of one tick must carry the same
``means``/``ranges`` payload - held deliveries are not exempt - while their
quality bits merge conservatively: valid bits intersect, and saturated,
held and source_fault bits union, so a worsening flag can never be cleared
by a duplicate delivery or by reordering.  Re-deliveries of a known tick
therefore never create fresh model history and never evict older
observations.  ``fresh_counts`` counts merged acquisition columns whose
combined mask is fresh-valid for a channel; held, saturated, source-fault
and stale counts describe those same merged columns.  Grant bits stay
per-arrival scheduling metadata: they never change the feature grid and a
combined grant is never execution authorization.

Layout of ``SummaryWindow.features`` (13 channels x 32 columns, oldest
column first, left-padded with masked zeros for cold start):

    rows 0-3    normalised means,   mean[c] / scales[c]
    rows 4-7    normalised ranges,  range[c] / scales[4 + c]
    rows 8-11   valid masks, 1.0 for a fresh valid sample else 0.0
    row 12      normalised age, min(age_ms / age_limit_ms, 1.0)

Derived features that overflow or become non-finite raise
:class:`CausalInputError` instead of entering the grid.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

__all__ = [
    "CHANNEL_COUNT",
    "WINDOW_COLUMNS",
    "SUMMARY_CHANNELS",
    "MODEL_INPUT_SHAPE",
    "SOURCE_MODES",
    "SENSOR_CHANNELS",
    "VALID_BIT_BASE",
    "SATURATED_BIT_BASE",
    "HELD_BIT_BASE",
    "SOURCE_FAULT_BIT",
    "GRANT_BIT_BASE",
    "SENSOR_BITS_MASK",
    "GRANT_BITS_MASK",
    "HELD_REUSE_MASK",
    "VALID_BITS_MASK",
    "SATURATED_BITS_MASK",
    "SOURCE_FAULT_FLAG_MASK",
    "MAX_QUALITY_FLAGS",
    "CausalInputError",
    "TelemetrySchema",
    "SummaryBinding",
    "SummaryColumn",
    "SummaryWindowMetadata",
    "SummaryWindow",
    "build_summary_window",
]

CHANNEL_COUNT = 13
WINDOW_COLUMNS = 32
SUMMARY_CHANNELS = 4
MODEL_INPUT_SHAPE = (1, CHANNEL_COUNT, WINDOW_COLUMNS, 1)

SENSOR_CHANNELS: tuple[str, str, str, str] = (
    "log10_rho_apparent",
    "azimuth_log10_rho_difference",
    "elevation_log10_rho_difference",
    "near_bit_vibration_rms_g",
)

SOURCE_MODES: tuple[str, ...] = (
    "sensor_live",
    "geo_replay",
    "twin_fixture",
    "software_fixture",
)

VALID_BIT_BASE = 0
SATURATED_BIT_BASE = 4
HELD_BIT_BASE = 8
SOURCE_FAULT_BIT = 12
GRANT_BIT_BASE = 13
SENSOR_BITS_MASK = 0x1FFF
GRANT_BITS_MASK = 0xE000
HELD_REUSE_MASK = 0x0F00
VALID_BITS_MASK = 0x000F
SATURATED_BITS_MASK = 0x00F0
SOURCE_FAULT_FLAG_MASK = 0x1000
MAX_QUALITY_FLAGS = 0xFFFF

_FORBIDDEN_FIELD_TOKENS = (
    "truth",
    "future",
    "object",
    "seed",
    "oracle",
    "editor",
    "screen",
    "collider",
    "mesh",
)


class CausalInputError(ValueError):
    """Raised when records or arguments cannot form a legal causal window."""


def _forbidden_field(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in _FORBIDDEN_FIELD_TOKENS)


def _finite_number(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CausalInputError(f"{what} must be a number, got {value!r}")
    try:
        number = float(value)
    except OverflowError as exc:
        raise CausalInputError(f"{what} is out of float range: {exc}") from exc
    if not isfinite(number):
        raise CausalInputError(f"{what} must be finite, got {value!r}")
    return number


def _normalized_feature(numerator: float, scale: float, what: str) -> float:
    value = numerator / scale
    if not isfinite(value):
        raise CausalInputError(
            f"{what} overflows the float range during scaling (got {value!r})"
        )
    return value


def _non_negative_int(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CausalInputError(f"{what} must be a non-negative integer, got {value!r}")
    return value


def _positive_scale(value: object, index: int) -> float:
    number = _finite_number(value, f"scales[{index}]")
    if number <= 0:
        raise CausalInputError(f"scales[{index}] must be > 0")
    return number


def _quality_flags(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CausalInputError(
            f"{what} must be an integer packed uint16 quality_flags, got {value!r}"
        )
    if not 0 <= value <= MAX_QUALITY_FLAGS:
        raise CausalInputError(
            f"{what} must be in 0..{MAX_QUALITY_FLAGS}, got {value!r}"
        )
    return value


def _channel_state(flags: int, channel: int) -> tuple[bool, bool, bool, bool]:
    """Per-channel (valid, saturated, held, source_fault) bits of one record."""
    valid = bool((flags >> (VALID_BIT_BASE + channel)) & 1)
    saturated = bool((flags >> (SATURATED_BIT_BASE + channel)) & 1)
    held = bool((flags >> (HELD_BIT_BASE + channel)) & 1)
    source_fault = bool((flags >> SOURCE_FAULT_BIT) & 1)
    return valid, saturated, held, source_fault


def _sensor_content(entry: Mapping[str, object]) -> tuple:
    """Sensor-relevant content of one candidate (grant bits excluded)."""
    return (
        int(entry["tick_ms"]),
        str(entry["source_mode"]),
        tuple(entry["means"]),
        tuple(entry["ranges"]),
        int(entry["flags"]) & SENSOR_BITS_MASK,
    )


def _merge_acquisition_ticks(
    candidates: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Collapse transport records into exactly one merged entry per tick.

    For one acquisition tick every arrival must carry the same ``means`` and
    ``ranges`` payload - held deliveries are NOT exempt - while quality bits
    combine conservatively (valid bits intersect; saturated, held and
    source_fault bits union) so a worsening flag is never cleared by a
    duplicate or by reordering.  Grant bits are kept per arrival for audit
    only and never influence the merged sensor state.  The merged entry
    keeps the smallest ``seq`` as its deterministic representative.
    """
    by_tick: dict[int, dict[str, object]] = {}
    for entry in candidates:
        tick_ms = int(entry["tick_ms"])
        seq = int(entry["seq"])
        flags = int(entry["flags"])
        payload = (tuple(entry["means"]), tuple(entry["ranges"]))
        merged = by_tick.get(tick_ms)
        if merged is None:
            by_tick[tick_ms] = {
                "tick_ms": tick_ms,
                "source_mode": str(entry["source_mode"]),
                "normalized_means": tuple(entry["normalized_means"]),
                "normalized_ranges": tuple(entry["normalized_ranges"]),
                "payload": payload,
                "valid_bits": flags & VALID_BITS_MASK,
                "saturated_bits": flags & SATURATED_BITS_MASK,
                "held_bits": flags & HELD_REUSE_MASK,
                "source_fault_bit": flags & SOURCE_FAULT_FLAG_MASK,
                "grants_by_seq": {seq: flags & GRANT_BITS_MASK},
                "arrivals": 1,
            }
            continue
        if payload != merged["payload"]:
            raise CausalInputError(
                f"records for acquisition tick {tick_ms} conflict on means/ranges "
                "payload; held deliveries are not exempt from this check and "
                "different payloads are rejected instead of merged"
            )
        merged["valid_bits"] = int(merged["valid_bits"]) & (flags & VALID_BITS_MASK)
        merged["saturated_bits"] = int(merged["saturated_bits"]) | (
            flags & SATURATED_BITS_MASK
        )
        merged["held_bits"] = int(merged["held_bits"]) | (flags & HELD_REUSE_MASK)
        merged["source_fault_bit"] = int(merged["source_fault_bit"]) | (
            flags & SOURCE_FAULT_FLAG_MASK
        )
        grants_by_seq = merged["grants_by_seq"]
        grants_by_seq[seq] = flags & GRANT_BITS_MASK
        merged["arrivals"] = int(merged["arrivals"]) + 1
    return [by_tick[tick_ms] for tick_ms in sorted(by_tick)]



@dataclass(frozen=True)
class TelemetrySchema:
    """Exact field allowlist for caller-supplied summary records.

    Callers may rename every field by passing a different schema; each record
    must then contain exactly those names and nothing else.  ``means`` and
    ``ranges`` keep the frozen sensor-channel order of :data:`SENSOR_CHANNELS`
    and must each name exactly four fields as a fixed sequence (tuple/list);
    one-shot iterables such as generators are rejected so repeated
    validate/access calls stay stable.  ``quality_flags`` names the one
    packed ``uint16`` quality field (bits 0-3 valid, 4-7 saturated, 8-11
    held, 12 source_fault, 13-15 grants); there is no per-channel quality
    code field.  ``tick_ms`` names the acquisition tick of the last included
    sample (frame transmission time is never used as tick).
    """

    run_id: str = "run_id"
    session_id: str = "session_id"
    profile: str = "profile"
    epoch: str = "epoch"
    seq: str = "seq"
    tick_ms: str = "tick_ms"
    source_mode: str = "source_mode"
    means: tuple[str, str, str, str] = ("mean_0", "mean_1", "mean_2", "mean_3")
    ranges: tuple[str, str, str, str] = ("range_0", "range_1", "range_2", "range_3")
    quality_flags: str = "quality_flags"

    def field_names(self) -> tuple[str, ...]:
        """Every allowed record field name, exactly once, in declaration order.

        Cardinality of ``means``/``ranges`` is enforced here so callers get
        :class:`CausalInputError` instead of ``TypeError``/``IndexError``.
        Groups must be fixed sequences; one-shot iterators are rejected
        before any element is consumed, never silently drained.
        """
        names: list = [
            self.run_id,
            self.session_id,
            self.profile,
            self.epoch,
            self.seq,
            self.tick_ms,
            self.source_mode,
            self.quality_flags,
        ]
        for label, group in (("means", self.means), ("ranges", self.ranges)):
            if isinstance(group, (str, bytes)) or not isinstance(group, Sequence):
                raise CausalInputError(
                    f"schema {label} must be a fixed sequence (e.g. a tuple) of "
                    f"exactly {SUMMARY_CHANNELS} field names; one-shot iterables "
                    "such as generators are not supported"
                )
            group_names = tuple(group)
            if len(group_names) != SUMMARY_CHANNELS:
                raise CausalInputError(
                    f"schema {label} must name exactly {SUMMARY_CHANNELS} fields, "
                    f"got {len(group_names)}"
                )
            names.extend(group_names)
        return tuple(names)

    def allowed(self) -> frozenset[str]:
        """The exact allowed key set for one record."""
        return frozenset(self.field_names())

    def validate(self) -> None:
        """Reject a schema that cannot serve as an exact allowlist."""
        seen: set[str] = set()
        for name in self.field_names():
            if not isinstance(name, str) or not name:
                raise CausalInputError("schema field names must be non-empty strings")
            if _forbidden_field(name):
                raise CausalInputError(
                    f"schema field {name!r} uses a forbidden semantic token"
                )
            if name in seen:
                raise CausalInputError(f"schema field {name!r} is declared twice")
            seen.add(name)


@dataclass(frozen=True)
class SummaryBinding:
    """The single (run, session, profile, epoch) a window may be built from."""

    run_id: str
    session_id: str
    profile: str
    epoch: int

    def validate(self) -> None:
        """Reject non-conforming binding identifiers."""
        for name in ("run_id", "session_id", "profile"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise CausalInputError(f"binding {name} must be a non-empty string")
        if isinstance(self.epoch, bool) or not isinstance(self.epoch, int) or self.epoch < 0:
            raise CausalInputError("binding epoch must be a non-negative integer")


@dataclass(frozen=True)
class SummaryColumn:
    """Metadata for one of the 32 window columns (index 0 is oldest).

    One column represents exactly one acquisition tick.  ``contributing_seqs``
    lists every accepted transport ``seq`` that merged into this tick in
    ascending order; ``seq`` is the deterministic representative (smallest).
    ``quality_flags`` is the merged packed ``uint16`` (``None`` for cold-start
    padding columns): valid bits intersected, saturated/held/source_fault bits
    unioned across arrivals, and its grant bits mirror the representative
    arrival.  ``grant_arrivals`` keeps each arrival's ``(seq, grants)`` pair
    separately because grants are scheduling metadata that never affect
    ``valid_mask`` and are never execution authorization.
    ``source_native_tick_ms`` is a computed output that is always ``None``:
    legal board bytes never carry the per-channel native acquisition tick, so
    this module never invents one and never accepts a caller sideband.
    """

    index: int
    padded: bool
    seq: int | None
    contributing_seqs: tuple[int, ...]
    tick_ms: int | None
    age_ms: int | None
    normalized_age: float
    source_mode: str | None
    quality_flags: int | None
    grants: tuple[bool, bool, bool]
    grant_arrivals: tuple[tuple[int, tuple[bool, bool, bool]], ...]
    valid_mask: tuple[float, float, float, float]
    held: tuple[bool, bool, bool, bool]
    saturated: tuple[bool, bool, bool, bool]
    source_fault: tuple[bool, bool, bool, bool]
    stale: tuple[bool, bool, bool, bool]
    source_native_tick_ms: int | None = None


@dataclass(frozen=True)
class SummaryWindowMetadata:
    """Window-level record of what was used, dropped, masked and counted.

    Counting levels are deliberately explicit now that each acquisition tick
    owns exactly one model column: ``fresh_counts`` counts merged columns
    whose conservative combined mask is fresh-valid for a channel, while
    held, saturated, source-fault and stale counts describe those same
    merged columns.  ``accepted_records`` is the number of transport records
    retained after future exclusion and identical-``seq`` dropping;
    ``duplicate_tick_records`` counts accepted records that merely merged
    into an already-represented acquisition tick (``accepted_records`` minus
    distinct accepted ticks), and ``unique_acquisition_ticks`` counts the
    distinct ticks represented by the retained (non-padded) window columns.
    """

    binding: SummaryBinding
    decision_cutoff_ms: int
    age_limit_ms: float
    scales: tuple[float, ...]
    total_records: int
    accepted_records: int
    excluded_future_records: int
    duplicate_records_dropped: int
    duplicate_tick_records: int
    unique_acquisition_ticks: int
    columns_padded: int
    columns_dropped_oldest: int
    source_modes: tuple[str, ...]
    fresh_counts: tuple[int, int, int, int]
    held_counts: tuple[int, int, int, int]
    saturated_counts: tuple[int, int, int, int]
    source_fault_counts: tuple[int, int, int, int]
    stale_counts: tuple[int, int, int, int]


@dataclass(frozen=True)
class SummaryWindow:
    """One deterministic summary window for the frozen [1,13,32,1] profile."""

    features: tuple[tuple[float, ...], ...]
    columns: tuple[SummaryColumn, ...]
    metadata: SummaryWindowMetadata

    def to_model_input(self) -> tuple:
        """Return the nested-tuple model input shaped [1, 13, 32, 1]."""
        channels = tuple(
            tuple((value,) for value in channel) for channel in self.features
        )
        return (channels,)


def build_summary_window(
    records: Iterable[Mapping[str, object]],
    *,
    binding: SummaryBinding,
    known_profiles: Iterable[str],
    decision_cutoff_ms: int,
    scales: Sequence[float],
    age_limit_ms: float,
    schema: TelemetrySchema | None = None,
) -> SummaryWindow:
    """Build one summary window from legal telemetry summary records.

    ``records`` must be mappings that contain exactly the schema field names.
    Every record must match ``binding``, carry ``tick_ms`` no later than
    ``decision_cutoff_ms`` (later records are excluded and counted) and carry
    one packed ``uint16`` ``quality_flags`` field using the frozen bit layout
    (valid 0-3, saturated 4-7, held 8-11, source_fault 12, grants 13-15).
    A channel is fresh-valid when the valid bit is set, the saturated, held
    and fault bits are clear, and ``cutoff - tick_ms`` does not exceed
    ``age_limit_ms``; grant bits never mask and never validate.

    Records are validated, future records are excluded and counted, identical
    re-deliveries of one transport ``seq`` are dropped (conflicting ``seq``
    content is rejected), and the remaining transport records collapse into
    exactly ONE summary column per distinct acquisition tick, oldest tick
    first.  All arrivals of one tick must agree on the ``means``/``ranges``
    payload - held deliveries are not exempt - while quality bits merge
    conservatively: valid bits intersect and saturated/held/source_fault bits
    union, so a worsening flag is never cleared by duplicates or reordering
    deliveries.  Each merged column keeps every contributing ``seq`` in
    ascending order (the smallest is the deterministic representative) and
    every arrival's grant bits as separate scheduling metadata; grants never
    change the feature grid and are never execution authorization.  The
    newest ``WINDOW_COLUMNS`` merged columns are kept, oldest first,
    left-padded with masked zeros when history is short; repeated deliveries
    of a known tick never add a column and never evict older observations.

    ``scales`` must carry eight positive finite train-fitted factors (four
    mean scales, then four range scales); ``age_limit_ms`` is the profile
    freshness limit.  Both are caller responsibilities: nothing is fitted
    here.  Derived features that overflow to a non-finite value raise
    :class:`CausalInputError`, as do huge numeric inputs that cannot be
    converted to finite floats.
    """
    record_schema = schema if schema is not None else TelemetrySchema()
    if not isinstance(record_schema, TelemetrySchema):
        raise CausalInputError("schema must be a TelemetrySchema")
    if not isinstance(binding, SummaryBinding):
        raise CausalInputError("binding must be a SummaryBinding")
    record_schema.validate()
    binding.validate()
    try:
        profiles = frozenset(known_profiles)
    except TypeError as exc:
        raise CausalInputError(
            "known_profiles must be an iterable of profile names"
        ) from exc
    if not profiles or any(not isinstance(name, str) or not name for name in profiles):
        raise CausalInputError("known_profiles must contain non-empty strings")
    if binding.profile not in profiles:
        raise CausalInputError(f"unknown profile {binding.profile!r}")

    cutoff = _non_negative_int(decision_cutoff_ms, "decision_cutoff_ms")
    age_limit = _finite_number(age_limit_ms, "age_limit_ms")
    if age_limit <= 0:
        raise CausalInputError("age_limit_ms must be > 0")

    try:
        raw_scales = tuple(scales)
    except TypeError as exc:
        raise CausalInputError(
            "scales must be an iterable of 8 train-fitted factors"
        ) from exc
    if len(raw_scales) != SUMMARY_CHANNELS * 2:
        raise CausalInputError(
            "scales must supply exactly 8 train-fitted factors (4 means, 4 ranges)"
        )
    scale_values = tuple(
        _positive_scale(value, index) for index, value in enumerate(raw_scales)
    )

    allowed = record_schema.allowed()
    total_records = 0
    excluded_future = 0
    duplicate_dropped = 0
    candidates: list[dict[str, object]] = []
    seen_seq: dict[int, dict[str, object]] = {}

    for index, record in enumerate(records):
        total_records += 1
        if not isinstance(record, Mapping):
            raise CausalInputError(f"record {index} must be a mapping")
        keys = set(record.keys())
        unexpected = sorted((key for key in keys if key not in allowed), key=repr)
        if unexpected:
            raise CausalInputError(
                f"record {index} has unexpected field(s): "
                f"{', '.join(map(repr, unexpected))}"
            )
        forbidden = sorted((key for key in keys if _forbidden_field(str(key))), key=repr)
        if forbidden:
            raise CausalInputError(
                f"record {index} has forbidden field(s): "
                f"{', '.join(map(repr, forbidden))}"
            )
        present = {key for key in keys if isinstance(key, str)}
        missing = sorted(allowed - present)
        if missing:
            raise CausalInputError(
                f"record {index} is missing field(s): {', '.join(missing)}"
            )

        run_id = record[record_schema.run_id]
        session_id = record[record_schema.session_id]
        profile = record[record_schema.profile]
        if not isinstance(run_id, str) or not run_id:
            raise CausalInputError(f"record {index}: run_id must be a non-empty string")
        if not isinstance(session_id, str) or not session_id:
            raise CausalInputError(f"record {index}: session_id must be a non-empty string")
        if not isinstance(profile, str) or not profile:
            raise CausalInputError(f"record {index}: profile must be a non-empty string")
        if run_id != binding.run_id:
            raise CausalInputError(
                f"record {index}: run_id {run_id!r} is not bound to {binding.run_id!r}"
            )
        if session_id != binding.session_id:
            raise CausalInputError(
                f"record {index}: session_id {session_id!r} is not bound to "
                f"{binding.session_id!r}"
            )
        if profile != binding.profile:
            raise CausalInputError(
                f"record {index}: profile {profile!r} is not bound to {binding.profile!r}"
            )
        epoch = _non_negative_int(record[record_schema.epoch], f"record {index} epoch")
        if epoch != binding.epoch:
            raise CausalInputError(
                f"record {index}: epoch {epoch} is not bound to {binding.epoch}"
            )
        seq = _non_negative_int(record[record_schema.seq], f"record {index} seq")
        tick_ms = _non_negative_int(record[record_schema.tick_ms], f"record {index} tick_ms")
        source_mode = record[record_schema.source_mode]
        if not isinstance(source_mode, str) or source_mode not in SOURCE_MODES:
            raise CausalInputError(
                f"record {index}: source_mode {source_mode!r} is not one of {SOURCE_MODES}"
            )
        means = tuple(
            _finite_number(
                record[record_schema.means[channel]], f"record {index} means[{channel}]"
            )
            for channel in range(SUMMARY_CHANNELS)
        )
        ranges = tuple(
            _finite_number(
                record[record_schema.ranges[channel]], f"record {index} ranges[{channel}]"
            )
            for channel in range(SUMMARY_CHANNELS)
        )
        for channel, value in enumerate(ranges):
            if value < 0:
                raise CausalInputError(
                    f"record {index} ranges[{channel}] must be >= 0, got {value!r}"
                )
        flags = _quality_flags(
            record[record_schema.quality_flags], f"record {index} quality_flags"
        )
        normalized_means = tuple(
            _normalized_feature(
                means[channel],
                scale_values[channel],
                f"record {index} means[{channel}] / scales[{channel}]",
            )
            for channel in range(SUMMARY_CHANNELS)
        )
        normalized_ranges = tuple(
            _normalized_feature(
                ranges[channel],
                scale_values[SUMMARY_CHANNELS + channel],
                f"record {index} ranges[{channel}] / scales[{SUMMARY_CHANNELS + channel}]",
            )
            for channel in range(SUMMARY_CHANNELS)
        )

        if tick_ms > cutoff:
            excluded_future += 1
            continue

        entry: dict[str, object] = {
            "seq": seq,
            "tick_ms": tick_ms,
            "source_mode": source_mode,
            "means": means,
            "ranges": ranges,
            "flags": flags,
            "normalized_means": normalized_means,
            "normalized_ranges": normalized_ranges,
        }
        prior = seen_seq.get(seq)
        if prior is not None:
            if _sensor_content(prior) != _sensor_content(entry):
                raise CausalInputError(
                    f"record {index}: duplicate seq {seq} conflicts with an earlier record"
                )
            duplicate_dropped += 1
            continue
        seen_seq[seq] = entry
        candidates.append(entry)

    modes = sorted({str(entry["source_mode"]) for entry in candidates})
    if len(modes) > 1:
        raise CausalInputError(
            f"records mix source_mode values {tuple(modes)} within one window"
        )

    merged_ticks = _merge_acquisition_ticks(candidates)
    duplicate_tick_records = len(candidates) - len(merged_ticks)
    columns_dropped_oldest = max(0, len(merged_ticks) - WINDOW_COLUMNS)
    selected = (
        merged_ticks[-WINDOW_COLUMNS:] if columns_dropped_oldest else list(merged_ticks)
    )
    columns_padded = WINDOW_COLUMNS - len(selected)

    grid: list[list[float]] = [[0.0] * WINDOW_COLUMNS for _ in range(CHANNEL_COUNT)]
    columns: list[SummaryColumn] = []
    fresh_ticks: list[set[int]] = [set(), set(), set(), set()]
    held_counts = [0, 0, 0, 0]
    saturated_counts = [0, 0, 0, 0]
    source_fault_counts = [0, 0, 0, 0]
    stale_counts = [0, 0, 0, 0]
    used_modes: set[str] = set()

    for column_index in range(WINDOW_COLUMNS):
        if column_index < columns_padded:
            columns.append(
                SummaryColumn(
                    index=column_index,
                    padded=True,
                    seq=None,
                    contributing_seqs=(),
                    tick_ms=None,
                    age_ms=None,
                    normalized_age=0.0,
                    source_mode=None,
                    quality_flags=None,
                    grants=(False, False, False),
                    grant_arrivals=(),
                    valid_mask=(0.0, 0.0, 0.0, 0.0),
                    held=(False, False, False, False),
                    saturated=(False, False, False, False),
                    source_fault=(False, False, False, False),
                    stale=(False, False, False, False),
                    source_native_tick_ms=None,
                )
            )
            continue

        entry = selected[column_index - columns_padded]
        tick_ms = int(entry["tick_ms"])
        grants_by_seq: dict[int, int] = entry["grants_by_seq"]
        contributing_seqs = tuple(sorted(grants_by_seq))
        representative_seq = contributing_seqs[0]
        grant_arrivals = tuple(
            (
                seq,
                (
                    bool((grants_by_seq[seq] >> GRANT_BIT_BASE) & 1),
                    bool((grants_by_seq[seq] >> (GRANT_BIT_BASE + 1)) & 1),
                    bool((grants_by_seq[seq] >> (GRANT_BIT_BASE + 2)) & 1),
                ),
            )
            for seq in contributing_seqs
        )
        representative_grants = grant_arrivals[0][1]
        flags = (
            int(entry["valid_bits"])
            | int(entry["saturated_bits"])
            | int(entry["held_bits"])
            | int(entry["source_fault_bit"])
            | grants_by_seq[representative_seq]
        )
        age_ms = cutoff - tick_ms
        normalized_age = 1.0 if age_ms >= age_limit else age_ms / age_limit
        mask: list[float] = []
        held: list[bool] = []
        saturated: list[bool] = []
        source_fault: list[bool] = []
        stale: list[bool] = []
        for channel in range(SUMMARY_CHANNELS):
            valid_bit, saturated_bit, held_bit, fault_bit = _channel_state(flags, channel)
            channel_stale = age_ms > age_limit
            channel_valid = (
                valid_bit
                and not saturated_bit
                and not held_bit
                and not fault_bit
                and not channel_stale
            )
            mask.append(1.0 if channel_valid else 0.0)
            held.append(held_bit)
            saturated.append(saturated_bit)
            source_fault.append(fault_bit)
            stale.append(channel_stale)
            if channel_valid:
                fresh_ticks[channel].add(tick_ms)
            if held_bit:
                held_counts[channel] += 1
            if saturated_bit:
                saturated_counts[channel] += 1
            if fault_bit:
                source_fault_counts[channel] += 1
            if channel_stale:
                stale_counts[channel] += 1
        for channel in range(SUMMARY_CHANNELS):
            grid[channel][column_index] = float(entry["normalized_means"][channel])
            grid[SUMMARY_CHANNELS + channel][column_index] = float(
                entry["normalized_ranges"][channel]
            )
            grid[SUMMARY_CHANNELS * 2 + channel][column_index] = mask[channel]
        grid[CHANNEL_COUNT - 1][column_index] = normalized_age
        used_modes.add(str(entry["source_mode"]))
        columns.append(
            SummaryColumn(
                index=column_index,
                padded=False,
                seq=representative_seq,
                contributing_seqs=contributing_seqs,
                tick_ms=tick_ms,
                age_ms=age_ms,
                normalized_age=normalized_age,
                source_mode=str(entry["source_mode"]),
                quality_flags=flags,
                grants=representative_grants,
                grant_arrivals=grant_arrivals,
                valid_mask=(mask[0], mask[1], mask[2], mask[3]),
                held=(held[0], held[1], held[2], held[3]),
                saturated=(saturated[0], saturated[1], saturated[2], saturated[3]),
                source_fault=(
                    source_fault[0],
                    source_fault[1],
                    source_fault[2],
                    source_fault[3],
                ),
                stale=(stale[0], stale[1], stale[2], stale[3]),
                source_native_tick_ms=None,
            )
        )

    unique_acquisition_ticks = len({int(entry["tick_ms"]) for entry in selected})

    metadata = SummaryWindowMetadata(
        binding=binding,
        decision_cutoff_ms=cutoff,
        age_limit_ms=age_limit,
        scales=scale_values,
        total_records=total_records,
        accepted_records=len(candidates),
        excluded_future_records=excluded_future,
        duplicate_records_dropped=duplicate_dropped,
        duplicate_tick_records=duplicate_tick_records,
        unique_acquisition_ticks=unique_acquisition_ticks,
        columns_padded=columns_padded,
        columns_dropped_oldest=columns_dropped_oldest,
        source_modes=tuple(sorted(used_modes)),
        fresh_counts=(
            len(fresh_ticks[0]),
            len(fresh_ticks[1]),
            len(fresh_ticks[2]),
            len(fresh_ticks[3]),
        ),
        held_counts=(held_counts[0], held_counts[1], held_counts[2], held_counts[3]),
        saturated_counts=(
            saturated_counts[0],
            saturated_counts[1],
            saturated_counts[2],
            saturated_counts[3],
        ),
        source_fault_counts=(
            source_fault_counts[0],
            source_fault_counts[1],
            source_fault_counts[2],
            source_fault_counts[3],
        ),
        stale_counts=(stale_counts[0], stale_counts[1], stale_counts[2], stale_counts[3]),
    )
    return SummaryWindow(
        features=tuple(tuple(row) for row in grid),
        columns=tuple(columns),
        metadata=metadata,
    )

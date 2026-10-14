"""C01 curve-profile input builder: deterministic [1,8,128,1] windows (stdlib only).

Frozen source: the C01 task fixes the curve-profile model input as
``[1,8,128,1]`` - the four licensed FORCE curve channels GR, RHOB, NPHI and
RDEP followed by their four exact validity masks, over up to 128
acquisition-index columns, right-aligned at the current sample (a 128-point
curve profile is 128 actually selected points with explicit tick/mask, never
a fake 100 Hz continuous curve).  This module is the input-builder half of
that profile on the C (PC AI) side.  It is deliberately separate from
``ai_pc.model.causal_input``, which owns the distinct ``[1,13,32,1]``
sim_em_v2 summary profile; the two profiles are never mixed here and no A
wire field is invented.

Design boundaries, all deliberate:

* Pure and dependency-free (Python standard library only): no file I/O, no
  scene/schema imports, no hidden fitting, no training, no quantisation and
  no motion authority - model features are inputs and never authorize
  motion.  The frozen scaler is constructed only from exactly the expected
  preprocessing-document bytes and their pinned SHA256 - there is no
  constructor that accepts a hash together with caller-supplied statistics,
  so statistics can never claim a provenance they were not parsed from -
  and the committed train statistics are validated and used, never refitted,
  modified or clipped.
* One immutable binding identifies the opaque ``run_id``, the
  ``source_domain`` (``geo_replay`` or ``software_fixture``), the profile id
  ``force_curve_v1`` and the preprocessing SHA256.  This is a C internal
  model API, not a new A wire field.  The observation schema is validated
  and copied into immutable tuples at construction, so it is frozen for the
  lifetime of a builder.
* Every observation carries the matching binding, an exact ``uint64``
  sample sequence, four numeric sensor values and four exact bool validity
  flags.  Unknown keys (labels, coordinates, scene/seed/truth-style fields)
  are rejected; the public dataclass constructors validate exactly like the
  mapping parser, so there is no bypass.
* The four values are sensor-only: there is no label or target parameter
  anywhere in this API or its output, and offline labels remain separate
  evaluator data.  LAS NULL detection belongs to the adapter validity
  flags, never to value magic inside this builder.
* Causal window state: at most 128 acquisition-index slots with constant
  bookkeeping.  Strictly increasing sequences advance the window; gaps
  become explicit all-missing slots (a huge gap clears in bounded work and
  never loops per missing index); startup history is left-padded as missing.
  Re-delivering the current sequence with the exact same payload is
  idempotent; conflicting duplicates and older/out-of-order sequences are
  rejected without altering history; there is no sequence wrap within one
  binding and no future lookahead.  A snapshot never mutates after later
  observations and no future or unselected data can be appended to a
  produced window.  A new run means constructing a new bound builder -
  never an implicit switch.

Normalisation policy recorded by the accepted FORCE preprocessing document
(validated against the frozen contract identity): valid GR/RHOB/NPHI values
are used as-is (identity-v1) and centred/scaled by the committed train mean
and effective scale; valid positive RDEP values are ``log10`` transformed
first (log10-positive-v1); a nonpositive RDEP value becomes missing exactly
as the recorded policy says.  Missing channels normalise to ``0.0`` with
mask ``0.0``.  Valid finite negative values of the other three channels
remain legitimate.  Non-finite or lossy inputs, and normalised values that
do not stay finite, raise :class:`CurveInputError` - nothing is clipped,
dropped or silently converted.
"""

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import itertools
import json
import math

__all__ = [
    "CHANNEL_NAMES",
    "CHANNEL_TRANSFORMS",
    "CHANNEL_UNITS",
    "CONTRACT_DESIGN_COMMIT",
    "CONTRACT_ID",
    "CONTRACT_REQUIREMENTS_SHA256",
    "CONTRACT_REVISION",
    "CONTRACT_SOURCE_COMMIT",
    "DOCUMENT_KIND",
    "DOCUMENT_SCHEMA",
    "FEATURE_CHANNELS",
    "MAX_SEQUENCE",
    "MODEL_INPUT_SHAPE",
    "PRODUCT_CARD_STATUS",
    "PROFILE_ID",
    "SOURCE_DOMAINS",
    "WINDOW_COLUMNS",
    "CurveBinding",
    "CurveChannelStatistics",
    "CurveInputError",
    "CurveObservation",
    "CurveScaler",
    "CurveSchema",
    "CurveWindow",
    "CurveWindowBuilder",
    "CurveWindowMetadata",
    "observation_from_mapping",
]

PROFILE_ID = "force_curve_v1"
CHANNEL_NAMES = ("GR", "RHOB", "NPHI", "RDEP")
CHANNEL_UNITS = ("gAPI", "g/cm3", "m3/m3", "ohm.m")
CHANNEL_TRANSFORMS = ("identity-v1", "identity-v1", "identity-v1", "log10-positive-v1")
WINDOW_COLUMNS = 128
FEATURE_CHANNELS = 8
MODEL_INPUT_SHAPE = (1, FEATURE_CHANNELS, WINDOW_COLUMNS, 1)
SOURCE_DOMAINS = ("geo_replay", "software_fixture")
MAX_SEQUENCE = (1 << 64) - 1

DOCUMENT_KIND = "deepeye-force-preprocess"
DOCUMENT_SCHEMA = 1
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014"
CONTRACT_REVISION = 1
CONTRACT_SOURCE_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
CONTRACT_REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
CONTRACT_DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"
PRODUCT_CARD_STATUS = "not_run"

_RDEP_INDEX = 3
_HEX_DIGITS = frozenset("0123456789abcdef")
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
    "label",
    "target",
    "coordinate",
    "confidence",
    "scene",
)


class CurveInputError(ValueError):
    """Raised when curve inputs, scalers or observations cannot form a legal window."""


def _forbidden_field(name):
    lowered = name.lower()
    return any(token in lowered for token in _FORBIDDEN_FIELD_TOKENS)


def _sha256_hex(value, what):
    if not isinstance(value, str):
        raise CurveInputError("%s must be a lowercase hex sha256 string, got %s" % (what, type(value).__name__))
    if len(value) != 64 or any(character not in _HEX_DIGITS for character in value):
        raise CurveInputError("%s must be exactly 64 lowercase hex characters" % what)
    return value


def _finite_number(value, what):
    if isinstance(value, bool):
        raise CurveInputError("%s must not be a bool; booleans are never numbers here" % what)
    if isinstance(value, int):
        try:
            converted = float(value)
        except OverflowError as exc:
            raise CurveInputError("%s integer %r overflows a float" % (what, value)) from exc
        if converted != value:
            raise CurveInputError(
                "%s integer %r cannot be represented exactly as a float; no silent conversion" % (what, value)
            )
        return converted
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CurveInputError("%s must be finite, got %r" % (what, value))
        return value
    raise CurveInputError("%s must be a finite int or float, got %s" % (what, type(value).__name__))


def _exact_bool(value, what):
    if not isinstance(value, bool):
        raise CurveInputError("%s must be an exact bool, got %s" % (what, type(value).__name__))
    return value


def _four_number_sequence(values, what):
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise CurveInputError(
            "%s must be a fixed sequence of exactly 4 numbers; one-shot iterables such as generators are not supported"
            % what
        )
    if len(values) != 4:
        raise CurveInputError("%s must contain exactly 4 numbers, got %d" % (what, len(values)))
    return tuple(_finite_number(value, "%s[%d]" % (what, index)) for index, value in enumerate(values))


def _four_bool_sequence(valid, what):
    if isinstance(valid, (str, bytes)) or not isinstance(valid, Sequence):
        raise CurveInputError(
            "%s must be a fixed sequence of exactly 4 flags; one-shot iterables such as generators are not supported"
            % what
        )
    if len(valid) != 4:
        raise CurveInputError("%s must contain exactly 4 flags, got %d" % (what, len(valid)))
    return tuple(_exact_bool(value, "%s[%d]" % (what, index)) for index, value in enumerate(valid))


@dataclass(frozen=True)
class CurveSchema:
    """Exact frozen field allowlist for caller-supplied curve observations.

    Callers may rename every field by passing a different schema; each
    observation mapping must then contain exactly those names and nothing
    else.  Every scalar field must be a non-empty non-forbidden string and
    ``values``/``valid`` must each be a fixed sequence of exactly four such
    strings in the frozen curve-channel order of :data:`CHANNEL_NAMES`.
    Construction validates all thirteen names (string type, forbidden
    tokens, duplicates) and copies the two groups into immutable tuples, so
    a builder's schema cannot be changed afterwards by mutating the
    caller's original lists; one-shot iterables such as generators are
    rejected.
    """

    run_id: str = "run_id"
    source_domain: str = "source_domain"
    profile_id: str = "profile_id"
    preprocessing_sha256: str = "preprocessing_sha256"
    sequence: str = "sequence"
    values: tuple = ("value_0", "value_1", "value_2", "value_3")
    valid: tuple = ("valid_0", "valid_1", "valid_2", "valid_3")

    def __post_init__(self):
        for label in ("run_id", "source_domain", "profile_id", "preprocessing_sha256", "sequence"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value:
                raise CurveInputError("schema %s field name must be a non-empty string" % label)
        checked_groups = []
        for label, group in (("values", self.values), ("valid", self.valid)):
            if isinstance(group, (str, bytes)) or not isinstance(group, Sequence):
                raise CurveInputError(
                    "schema %s must be a fixed sequence (e.g. a tuple) of exactly 4 field names; "
                    "one-shot iterables such as generators are not supported" % label
                )
            group_names = tuple(group)
            if len(group_names) != 4:
                raise CurveInputError("schema %s must name exactly 4 fields, got %d" % (label, len(group_names)))
            checked_groups.append(group_names)
        seen = set()
        for name in (
            self.run_id,
            self.source_domain,
            self.profile_id,
            self.preprocessing_sha256,
            self.sequence,
            checked_groups[0][0],
            checked_groups[0][1],
            checked_groups[0][2],
            checked_groups[0][3],
            checked_groups[1][0],
            checked_groups[1][1],
            checked_groups[1][2],
            checked_groups[1][3],
        ):
            if not isinstance(name, str) or not name:
                raise CurveInputError("schema field names must be non-empty strings")
            if _forbidden_field(name):
                raise CurveInputError(
                    "schema field name %r is not allowed (label/coordinate/future/truth-style names are rejected)" % name
                )
            if name in seen:
                raise CurveInputError("schema field name %r is used more than once" % name)
            seen.add(name)
        object.__setattr__(self, "values", checked_groups[0])
        object.__setattr__(self, "valid", checked_groups[1])

    def field_names(self):
        """Return the frozen, validated field names in exact schema order."""
        return (
            self.run_id,
            self.source_domain,
            self.profile_id,
            self.preprocessing_sha256,
            self.sequence,
            self.values[0],
            self.values[1],
            self.values[2],
            self.values[3],
            self.valid[0],
            self.valid[1],
            self.valid[2],
            self.valid[3],
        )

    def allowed(self):
        return frozenset(self.field_names())

    def validate(self):
        seen = set()
        for name in self.field_names():
            if not isinstance(name, str) or not name:
                raise CurveInputError("schema field names must be non-empty strings")
            if _forbidden_field(name):
                raise CurveInputError(
                    "schema field name %r is not allowed (label/coordinate/future/truth-style names are rejected)" % name
                )
            if name in seen:
                raise CurveInputError("schema field name %r is used more than once" % name)
            seen.add(name)

@dataclass(frozen=True)
class CurveBinding:
    """Immutable identity of one bound curve-profile run (C internal API).

    ``run_id`` is an opaque caller string; ``source_domain`` must be one of
    :data:`SOURCE_DOMAINS`; ``profile_id`` is the frozen ``force_curve_v1``
    profile and ``preprocessing_sha256`` must be the lowercase hex SHA256 of
    the exact preprocessing document the scaler was loaded from.  Bindings
    are validated here; a builder rejects any observation carrying a
    different binding, and a new run always means a new builder.
    """

    run_id: str
    source_domain: str
    preprocessing_sha256: str
    profile_id: str = PROFILE_ID

    def __post_init__(self):
        if not isinstance(self.run_id, str) or not self.run_id:
            raise CurveInputError("binding run_id must be a non-empty string")
        if not isinstance(self.source_domain, str) or self.source_domain not in SOURCE_DOMAINS:
            raise CurveInputError(
                "binding source_domain must be one of %r, got %r" % (SOURCE_DOMAINS, self.source_domain)
            )
        _sha256_hex(self.preprocessing_sha256, "binding preprocessing_sha256")
        if self.profile_id != PROFILE_ID:
            raise CurveInputError("binding profile_id must be %r, got %r" % (PROFILE_ID, self.profile_id))


@dataclass(frozen=True)
class CurveObservation:
    """One validated causal curve observation for the bound run.

    Fields are exactly: the matching :class:`CurveBinding`, the exact
    ``uint64`` sample sequence, four numeric sensor values (finite int/float;
    bools rejected) and four exact bool validity flags in the frozen channel
    order ``GR, RHOB, NPHI, RDEP``.  There is no label or target field.
    Invalid values raise :class:`CurveInputError` from this constructor, so
    direct construction cannot bypass validation.
    """

    binding: CurveBinding
    sequence: int
    values: tuple
    valid: tuple

    def __post_init__(self):
        if not isinstance(self.binding, CurveBinding):
            raise CurveInputError("observation binding must be a CurveBinding")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise CurveInputError("observation sequence must be an exact int, got %s" % type(self.sequence).__name__)
        if not 0 <= self.sequence <= MAX_SEQUENCE:
            raise CurveInputError(
                "observation sequence must be a uint64 (0..%d), got %r" % (MAX_SEQUENCE, self.sequence)
            )
        checked_values = _four_number_sequence(self.values, "observation values")
        checked_valid = _four_bool_sequence(self.valid, "observation valid")
        object.__setattr__(self, "values", checked_values)
        object.__setattr__(self, "valid", checked_valid)

    @classmethod
    def from_mapping(cls, record, *, schema=None):
        """Parse one observation mapping with the exact schema allowlist."""
        return observation_from_mapping(record, schema=schema)


def observation_from_mapping(record, *, schema=None):
    """Parse one observation mapping into a validated :class:`CurveObservation`.

    The mapping must contain exactly the schema field names - any extra key
    (labels, coordinates, scene/seed/truth-style keys included) is rejected,
    as is any missing field.  Values and flags go through the same strict
    validation as the public dataclass constructor.
    """
    record_schema = schema if schema is not None else CurveSchema()
    record_schema.validate()
    if not isinstance(record, Mapping):
        raise CurveInputError("observation must be a mapping of the schema fields")
    keys = set()
    for key in record.keys():
        if not isinstance(key, str):
            raise CurveInputError("observation field names must be strings")
        keys.add(key)
    allowed = record_schema.allowed()
    unexpected = keys - allowed
    if unexpected:
        for key in sorted(unexpected):
            if _forbidden_field(key):
                raise CurveInputError(
                    "observation field %r is rejected: label/coordinate/future/truth-style inputs are never part "
                    "of this API" % key
                )
        raise CurveInputError("observation contains unknown field(s) %r" % sorted(unexpected))
    missing = allowed - keys
    if missing:
        raise CurveInputError("observation is missing required field(s) %r" % sorted(missing))
    binding = CurveBinding(
        run_id=record[record_schema.run_id],
        source_domain=record[record_schema.source_domain],
        preprocessing_sha256=record[record_schema.preprocessing_sha256],
        profile_id=record[record_schema.profile_id],
    )
    return CurveObservation(
        binding=binding,
        sequence=record[record_schema.sequence],
        values=tuple(record[record_schema.values[index]] for index in range(4)),
        valid=tuple(record[record_schema.valid[index]] for index in range(4)),
    )

def _channel_statistics(entry, index):
    if not isinstance(entry, dict):
        raise CurveInputError("preprocessing channel block %d must be an object" % index)
    name = CHANNEL_NAMES[index]
    if entry.get("name") != name:
        raise CurveInputError("preprocessing channel %d must be %r in the frozen profile order" % (index, name))
    if entry.get("unit") != CHANNEL_UNITS[index]:
        raise CurveInputError("preprocessing channel %s unit must be %r" % (name, CHANNEL_UNITS[index]))
    if entry.get("transform_version") != CHANNEL_TRANSFORMS[index]:
        raise CurveInputError("preprocessing channel %s transform_version must be %r" % (name, CHANNEL_TRANSFORMS[index]))
    valid_samples = entry.get("valid_samples")
    if isinstance(valid_samples, bool) or not isinstance(valid_samples, int) or valid_samples <= 0:
        raise CurveInputError("preprocessing channel %s valid_samples must be a positive int" % name)
    counts = entry.get("counts")
    if not isinstance(counts, dict):
        raise CurveInputError("preprocessing channel %s counts block is missing" % name)
    for key in ("valid", "null", "nonpositive", "absent"):
        count = counts.get(key)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise CurveInputError("preprocessing channel %s counts[%r] must be a non-negative int" % (name, key))
    if counts["valid"] != valid_samples:
        raise CurveInputError("preprocessing channel %s counts['valid'] must equal valid_samples" % name)
    mean = _finite_number(entry.get("mean"), "preprocessing channel %s mean" % name)
    variance = _finite_number(entry.get("variance"), "preprocessing channel %s variance" % name)
    std = _finite_number(entry.get("std"), "preprocessing channel %s std" % name)
    zero_variance = entry.get("zero_variance")
    if not isinstance(zero_variance, bool):
        raise CurveInputError("preprocessing channel %s zero_variance must be an exact bool" % name)
    effective_scale = _finite_number(entry.get("effective_scale"), "preprocessing channel %s effective_scale" % name)
    return CurveChannelStatistics(
        name=name,
        unit=CHANNEL_UNITS[index],
        transform_version=CHANNEL_TRANSFORMS[index],
        valid_samples=valid_samples,
        mean=mean,
        variance=variance,
        std=std,
        zero_variance=zero_variance,
        effective_scale=effective_scale,
    )


@dataclass(frozen=True)
class CurveChannelStatistics:
    """Validated frozen statistics of one curve channel.

    ``zero_variance`` is explicit: a zero-variance channel records
    ``variance == std == 0`` and ``effective_scale == 1.0``; otherwise
    ``variance > 0``, ``std == sqrt(variance)`` and ``effective_scale ==
    std``.  Nothing here is ever fitted by this module.
    """

    name: str
    unit: str
    transform_version: str
    valid_samples: int
    mean: float
    variance: float
    std: float
    zero_variance: bool
    effective_scale: float

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise CurveInputError("channel name must be a non-empty string")
        if not isinstance(self.unit, str) or not self.unit:
            raise CurveInputError("channel %s unit must be a non-empty string" % self.name)
        if not isinstance(self.transform_version, str) or not self.transform_version:
            raise CurveInputError("channel %s transform_version must be a non-empty string" % self.name)
        if isinstance(self.valid_samples, bool) or not isinstance(self.valid_samples, int) or self.valid_samples <= 0:
            raise CurveInputError("channel %s valid_samples must be a positive int" % self.name)
        mean = _finite_number(self.mean, "channel %s mean" % self.name)
        variance = _finite_number(self.variance, "channel %s variance" % self.name)
        std = _finite_number(self.std, "channel %s std" % self.name)
        effective_scale = _finite_number(self.effective_scale, "channel %s effective_scale" % self.name)
        if variance < 0.0:
            raise CurveInputError("channel %s variance must be >= 0" % self.name)
        if std < 0.0:
            raise CurveInputError("channel %s std must be >= 0" % self.name)
        if not isinstance(self.zero_variance, bool):
            raise CurveInputError("channel %s zero_variance must be an exact bool" % self.name)
        if self.zero_variance:
            if variance != 0.0 or std != 0.0 or effective_scale != 1.0:
                raise CurveInputError(
                    "channel %s records zero variance, so variance/std must be 0 and effective_scale must be exactly 1.0"
                    % self.name
                )
        else:
            if variance <= 0.0:
                raise CurveInputError("channel %s is not flagged zero_variance, so variance must be > 0" % self.name)
            if std != math.sqrt(variance):
                raise CurveInputError("channel %s std must equal sqrt(variance)" % self.name)
            if effective_scale != std or effective_scale <= 0.0:
                raise CurveInputError("channel %s effective_scale must equal std > 0" % self.name)
        object.__setattr__(self, "mean", mean)
        object.__setattr__(self, "variance", variance)
        object.__setattr__(self, "std", std)
        object.__setattr__(self, "effective_scale", effective_scale)


def _parse_preprocessing_document(data, expected_sha256):
    """Hash, copy, decode and validate preprocessing document bytes.

    Private helper: every public scaler construction path funnels here, so a
    :class:`CurveScaler` can only ever derive its statistics from bytes whose
    SHA256 was verified against the caller-pinned expected hash.  Returns the
    actual document digest and the validated four-channel statistics tuple.
    """
    expected = _sha256_hex(expected_sha256, "expected_sha256")
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise CurveInputError("preprocessing document must be passed as bytes")
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise CurveInputError(
            "preprocessing document sha256 %s does not match the expected %s" % (actual, expected)
        )
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CurveInputError("preprocessing document is not valid UTF-8: %s" % exc) from exc
    try:
        document = json.loads(decoded)
    except ValueError as exc:
        raise CurveInputError("preprocessing document is not valid JSON: %s" % exc) from exc
    if not isinstance(document, dict):
        raise CurveInputError("preprocessing document must be a JSON object")
    if document.get("kind") != DOCUMENT_KIND:
        raise CurveInputError("preprocessing document kind must be %r" % DOCUMENT_KIND)
    schema = document.get("schema")
    if isinstance(schema, bool) or schema != DOCUMENT_SCHEMA:
        raise CurveInputError("preprocessing document schema must be %r" % DOCUMENT_SCHEMA)
    contract = document.get("contract")
    if not isinstance(contract, dict):
        raise CurveInputError("preprocessing document contract block is missing")
    contract_expected = {
        "id": CONTRACT_ID,
        "revision": CONTRACT_REVISION,
        "source_commit": CONTRACT_SOURCE_COMMIT,
        "requirements_sha256": CONTRACT_REQUIREMENTS_SHA256,
        "design_commit": CONTRACT_DESIGN_COMMIT,
    }
    for key, wanted in contract_expected.items():
        if contract.get(key) != wanted:
            raise CurveInputError("preprocessing document contract %r does not match the frozen DEEPEYE contract" % key)
    if document.get("software_only") is not True:
        raise CurveInputError("preprocessing document must be software_only true")
    if document.get("product_card_c01") != PRODUCT_CARD_STATUS:
        raise CurveInputError("preprocessing document product_card_c01 must be %r" % PRODUCT_CARD_STATUS)
    algorithm = document.get("algorithm")
    if not isinstance(algorithm, dict) or list(algorithm.get("channel_order", ())) != list(CHANNEL_NAMES):
        raise CurveInputError("preprocessing document algorithm channel_order does not match the frozen curve profile")
    entries = document.get("channels")
    if not isinstance(entries, list) or len(entries) != 4:
        raise CurveInputError("preprocessing document must carry exactly 4 channel blocks")
    statistics = []
    for index, entry in enumerate(entries):
        statistics.append(_channel_statistics(entry, index))
    return actual, tuple(statistics)


@dataclass(frozen=True, init=False)
class CurveScaler:
    """Frozen four-channel scaler derived from the pinned preprocessing bytes.

    The only construction path takes the exact preprocessing document bytes
    plus the expected document SHA256; the bytes are copied to an immutable
    ``bytes`` object, hashed and parsed, and the frozen DEEPEYE contract
    identity, the ``force_curve_v1`` channel order/units/transforms, finite
    statistics, positive valid counts, ``variance >= 0``, the recorded
    std/variance consistency and the explicit zero-variance
    ``effective_scale == 1`` rule are all validated while parsing, before any
    field is set.  There is deliberately no constructor that accepts a hash
    together with caller-supplied statistics, so a scaler can never assert a
    provenance its statistics were not parsed from, and the dataclass
    ``replace`` helper cannot rebuild a scaler either.  This module never
    fits or modifies scalers.
    """

    preprocessing_sha256: str
    channels: tuple

    def __init__(self, document_bytes, *, expected_sha256):
        actual, statistics = _parse_preprocessing_document(document_bytes, expected_sha256)
        object.__setattr__(self, "preprocessing_sha256", actual)
        object.__setattr__(self, "channels", statistics)

    @classmethod
    def from_document_bytes(cls, data, *, expected_sha256):
        """Validate and load the frozen scaler from the exact document bytes."""
        return cls(data, expected_sha256=expected_sha256)

    def normalize(self, values, valid):
        """Normalise four sensor values with the frozen policy; returns (values, masks).

        Missing channels (``valid`` false) normalise to ``0.0`` with mask
        ``0.0``; a valid nonpositive RDEP value also becomes missing exactly
        as the recorded policy says.  Valid values are identity-transformed
        for GR/RHOB/NPHI and ``log10``-transformed for positive RDEP, then
        centred and scaled by the frozen train statistics.  Nothing is
        clipped; a non-finite (overflowing) result raises
        :class:`CurveInputError`.
        """
        checked_values = _four_number_sequence(values, "values")
        checked_valid = _four_bool_sequence(valid, "valid")
        normalized = []
        masks = []
        for index, stats in enumerate(self.channels):
            value = checked_values[index]
            if not checked_valid[index]:
                normalized.append(0.0)
                masks.append(0.0)
                continue
            if index == _RDEP_INDEX:
                if value <= 0.0:
                    normalized.append(0.0)
                    masks.append(0.0)
                    continue
                transformed = math.log10(value)
            else:
                transformed = value
            result = (transformed - stats.mean) / stats.effective_scale
            if not math.isfinite(result):
                raise CurveInputError(
                    "channel %s normalised value is non-finite for value %r" % (stats.name, value)
                )
            normalized.append(result)
            masks.append(1.0)
        return tuple(normalized), tuple(masks)

@dataclass(frozen=True)
class CurveWindowMetadata:
    """Snapshot metadata: identity, latest sequence and bounded bookkeeping.

    ``filled_slots`` counts real samples represented in the snapshot
    (padding and gap slots are missing), ``dropped_oldest`` counts real
    samples evicted by the 128-slot capacity, ``accepted_observations``
    counts fresh advancing observations and ``idempotent_repeats`` counts
    exact re-deliveries of the current sequence that changed nothing.
    """

    binding: CurveBinding
    profile_id: str
    preprocessing_sha256: str
    latest_sequence: object
    filled_slots: int
    missing_slots: int
    dropped_oldest: int
    accepted_observations: int
    idempotent_repeats: int

    def __post_init__(self):
        if not isinstance(self.binding, CurveBinding):
            raise CurveInputError("window metadata binding must be a CurveBinding")
        if self.profile_id != PROFILE_ID:
            raise CurveInputError("window metadata profile_id must be %r" % PROFILE_ID)
        _sha256_hex(self.preprocessing_sha256, "window metadata preprocessing_sha256")
        if self.latest_sequence is not None and (
            isinstance(self.latest_sequence, bool)
            or not isinstance(self.latest_sequence, int)
            or not 0 <= self.latest_sequence <= MAX_SEQUENCE
        ):
            raise CurveInputError("window metadata latest_sequence must be None or a uint64")
        for name in ("filled_slots", "missing_slots", "dropped_oldest", "accepted_observations", "idempotent_repeats"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise CurveInputError("window metadata %s must be a non-negative int" % name)
        if self.filled_slots + self.missing_slots != WINDOW_COLUMNS:
            raise CurveInputError("window metadata filled_slots + missing_slots must equal %d" % WINDOW_COLUMNS)


@dataclass(frozen=True)
class CurveWindow:
    """One immutable snapshot for the frozen [1,8,128,1] curve profile.

    ``features`` carries 8 channels x 128 columns: the four normalised
    values in channel order GR, RHOB, NPHI, RDEP followed by their four
    validity masks (``1.0`` valid, ``0.0`` missing), right-aligned at the
    latest accepted sample.  Snapshots are plain tuples and never mutate
    after later observations; nothing can be appended to a produced window.
    """

    features: tuple
    metadata: CurveWindowMetadata

    def __post_init__(self):
        if not isinstance(self.metadata, CurveWindowMetadata):
            raise CurveInputError("window metadata must be a CurveWindowMetadata")
        if not isinstance(self.features, Sequence) or isinstance(self.features, (str, bytes)) or len(self.features) != FEATURE_CHANNELS:
            raise CurveInputError("window features must be exactly %d channels" % FEATURE_CHANNELS)
        for index, channel in enumerate(self.features):
            if not isinstance(channel, Sequence) or isinstance(channel, (str, bytes)) or len(channel) != WINDOW_COLUMNS:
                raise CurveInputError("window features channel %d must have exactly %d columns" % (index, WINDOW_COLUMNS))
        object.__setattr__(self, "features", tuple(tuple(channel) for channel in self.features))

    def to_model_input(self):
        """Return the nested-tuple model input shaped [1, 8, 128, 1]."""
        channels = tuple(tuple((value,) for value in channel) for channel in self.features)
        return (channels,)


class CurveWindowBuilder:
    """Bound causal builder for one run: at most 128 right-aligned slots.

    Constructed once per binding: the scaler, the binding and the optional
    observation schema are fixed for the builder's lifetime, and observing
    with any other binding is rejected - resetting or switching runs is done
    by constructing a new builder, never implicitly.  ``observe`` validates
    completely before touching state, so invalid input is atomic.
    """

    def __init__(self, *, scaler, binding, schema=None):
        if not isinstance(scaler, CurveScaler):
            raise CurveInputError("builder scaler must be a CurveScaler")
        if not isinstance(binding, CurveBinding):
            raise CurveInputError("builder binding must be a CurveBinding")
        if binding.preprocessing_sha256 != scaler.preprocessing_sha256:
            raise CurveInputError("builder binding preprocessing_sha256 does not match the frozen scaler document hash")
        record_schema = schema if schema is not None else CurveSchema()
        if not isinstance(record_schema, CurveSchema):
            raise CurveInputError("builder schema must be a CurveSchema")
        record_schema.validate()
        self._scaler = scaler
        self._binding = binding
        self._schema = record_schema
        self._slots = deque(maxlen=WINDOW_COLUMNS)
        self._last_sequence = None
        self._last_values = None
        self._last_valid = None
        self._filled = 0
        self._dropped_oldest = 0
        self._accepted = 0
        self._idempotent = 0

    @property
    def binding(self):
        return self._binding

    @property
    def scaler(self):
        return self._scaler

    @property
    def latest_sequence(self):
        return self._last_sequence

    def observe(self, observation):
        """Validate and append one observation; atomic on any rejection.

        The current sequence re-delivered with the exact same payload and
        binding is idempotent and changes nothing (no delivery duplication
        fills history).  A conflicting duplicate of the current sequence or
        an older/out-of-order sequence raises :class:`CurveInputError`
        without altering any state.  Missing acquisition indexes become
        explicit all-missing slots; a huge gap is handled in bounded work
        without looping over the gap.
        """
        if isinstance(observation, CurveObservation):
            candidate = observation
        elif isinstance(observation, Mapping):
            candidate = observation_from_mapping(observation, schema=self._schema)
        else:
            raise CurveInputError("observation must be a CurveObservation or a mapping of the schema fields")
        if candidate.binding != self._binding:
            raise CurveInputError(
                "observation binding does not match this builder's binding "
                "(run_id/source_domain/profile/preprocessing mismatch); construct a new builder for a different run"
            )
        sequence = candidate.sequence
        if self._last_sequence is not None:
            if sequence < self._last_sequence:
                raise CurveInputError(
                    "observation sequence %d is older than the latest accepted %d" % (sequence, self._last_sequence)
                )
            if sequence == self._last_sequence:
                if candidate.values == self._last_values and candidate.valid == self._last_valid:
                    self._idempotent += 1
                    return
                raise CurveInputError("conflicting duplicate observation for the current sequence %d" % sequence)
        normalized, masks = self._scaler.normalize(candidate.values, candidate.valid)
        if self._last_sequence is None:
            missing_before = WINDOW_COLUMNS - 1
        else:
            missing_before = min(sequence - self._last_sequence - 1, WINDOW_COLUMNS - 1)
        evict = len(self._slots) + missing_before + 1 - WINDOW_COLUMNS
        evicted_samples = 0
        if evict > 0:
            for slot in itertools.islice(self._slots, evict):
                if slot is not None:
                    evicted_samples += 1
        self._slots.extend(itertools.repeat(None, missing_before))
        self._slots.append((normalized, masks))
        self._filled += 1 - evicted_samples
        self._dropped_oldest += evicted_samples
        self._last_sequence = sequence
        self._last_values = candidate.values
        self._last_valid = candidate.valid
        self._accepted += 1

    def snapshot(self):
        """Return an immutable right-aligned [1,8,128,1] snapshot."""
        slots = tuple(self._slots)
        padding = WINDOW_COLUMNS - len(slots)
        channels = []
        for channel in range(4):
            column = [0.0] * padding
            column.extend(0.0 if slot is None else slot[0][channel] for slot in slots)
            channels.append(tuple(column))
        for channel in range(4):
            column = [0.0] * padding
            column.extend(0.0 if slot is None else slot[1][channel] for slot in slots)
            channels.append(tuple(column))
        features = tuple(channels)
        filled = sum(1 for slot in slots if slot is not None)
        if filled != self._filled:
            raise CurveInputError("internal curve-window bookkeeping mismatch")
        metadata = CurveWindowMetadata(
            binding=self._binding,
            profile_id=PROFILE_ID,
            preprocessing_sha256=self._scaler.preprocessing_sha256,
            latest_sequence=self._last_sequence,
            filled_slots=filled,
            missing_slots=WINDOW_COLUMNS - filled,
            dropped_oldest=self._dropped_oldest,
            accepted_observations=self._accepted,
            idempotent_repeats=self._idempotent,
        )
        return CurveWindow(features=features, metadata=metadata)

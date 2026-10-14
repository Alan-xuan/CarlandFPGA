"""Unit tests for ai_pc/model/curve_input.py with synthetic fixtures only.

Software-only foundation evidence for the bounded C01 curve-profile input
([1,8,128,1]: GR, RHOB, NPHI, RDEP plus four validity masks over 128
acquisition-index columns, right-aligned).  Everything here is synthetic and
in-memory: this suite is not a model evaluation, not a data source, not a
real board observation and not product-card acceptance (C01 stays not_run).

Coverage: frozen scaler document validation (bytes/hash, contract identity,
profile order/units/transforms, finite statistics, positive valid counts,
std/variance consistency and the explicit zero-variance effective_scale=1
rule), normalisation policy (identity, log10 RDEP, nonpositive RDEP missing,
null masks, legitimate negatives, all-missing columns), a hand-computed
short-prefix expectation, 127/128/129 rollovers, huge gaps and uint64
boundaries, idempotent duplicates versus conflicts and reordering, binding
mixes, mapping allowlists with opaque forbidden keys, immutable prefix
snapshots, mutable input isolation, bounded retained state over 2000
acquisitions, scaler provenance (construction only from document bytes whose
pinned SHA256 was verified, including a regression against the committed
production preprocessing document, and rejection of forged
hash+statistics construction), frozen schema copies (post-construction
caller-list mutation cannot change a builder's allowlist) and the
public-constructor validation surface.
"""

import dataclasses
import hashlib
import inspect
import json
import math
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

PINNED_PREPROCESSING_SHA256 = "cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef"

from ai_pc.model.curve_input import (  # noqa: E402
    CHANNEL_NAMES,
    CHANNEL_TRANSFORMS,
    CHANNEL_UNITS,
    CONTRACT_DESIGN_COMMIT,
    CONTRACT_ID,
    CONTRACT_REQUIREMENTS_SHA256,
    CONTRACT_REVISION,
    CONTRACT_SOURCE_COMMIT,
    FEATURE_CHANNELS,
    MAX_SEQUENCE,
    MODEL_INPUT_SHAPE,
    PROFILE_ID,
    SOURCE_DOMAINS,
    WINDOW_COLUMNS,
    CurveBinding,
    CurveChannelStatistics,
    CurveInputError,
    CurveObservation,
    CurveScaler,
    CurveSchema,
    CurveWindow,
    CurveWindowBuilder,
    CurveWindowMetadata,
    observation_from_mapping,
)

_GR_MEAN, _GR_STD = 10.0, 2.0
_RHOB_MEAN, _RHOB_STD = 0.5, 0.5
_NPHI_MEAN, _NPHI_STD = 0.2, 0.2
_RDEP_MEAN, _RDEP_STD = 1.0, 1.0


def _channel(name, unit, transform, mean, variance, zero_variance=False, valid_samples=10):
    std = 0.0 if zero_variance else math.sqrt(variance)
    return {
        "name": name,
        "unit": unit,
        "transform_version": transform,
        "valid_samples": valid_samples,
        "counts": {"valid": valid_samples, "null": 0, "nonpositive": 0, "absent": 0},
        "mean": mean,
        "variance": 0.0 if zero_variance else variance,
        "std": std,
        "zero_variance": zero_variance,
        "effective_scale": 1.0 if zero_variance else std,
    }


def _default_channels():
    return [
        _channel("GR", "gAPI", "identity-v1", _GR_MEAN, 4.0),
        _channel("RHOB", "g/cm3", "identity-v1", _RHOB_MEAN, 0.25),
        _channel("NPHI", "m3/m3", "identity-v1", _NPHI_MEAN, 0.04),
        _channel("RDEP", "ohm.m", "log10-positive-v1", _RDEP_MEAN, 1.0),
    ]


def _document(channels=None):
    return {
        "schema": 1,
        "kind": "deepeye-force-preprocess",
        "generated_utc": "2026-10-15T00:00:00Z",
        "contract": {
            "id": CONTRACT_ID,
            "revision": CONTRACT_REVISION,
            "source_commit": CONTRACT_SOURCE_COMMIT,
            "requirements_sha256": CONTRACT_REQUIREMENTS_SHA256,
            "design_commit": CONTRACT_DESIGN_COMMIT,
        },
        "software_only": True,
        "product_card_c01": "not_run",
        "algorithm": {"name": "c01-preprocess-welford-v1", "channel_order": list(CHANNEL_NAMES)},
        "channels": _default_channels() if channels is None else channels,
    }


def _document_bytes(document):
    return json.dumps(document, sort_keys=True).encode("utf-8")


def _scaler_from(document):
    data = _document_bytes(document)
    return CurveScaler.from_document_bytes(data, expected_sha256=hashlib.sha256(data).hexdigest())


def _default_scaler():
    return _scaler_from(_document())


def _binding(scaler, run_id="run-a", source_domain="software_fixture"):
    return CurveBinding(
        run_id=run_id,
        source_domain=source_domain,
        preprocessing_sha256=scaler.preprocessing_sha256,
    )


def _observation(binding, sequence, values, valid):
    return CurveObservation(binding=binding, sequence=sequence, values=values, valid=valid)


def _column(window, index):
    return tuple(channel[index] for channel in window.features)

class ScalerDocumentTests(unittest.TestCase):
    def test_document_bytes_hash_and_type_are_enforced(self):
        data = _document_bytes(_document())
        expected = hashlib.sha256(data).hexdigest()
        scaler = CurveScaler.from_document_bytes(data, expected_sha256=expected)
        self.assertEqual(scaler.preprocessing_sha256, expected)
        with self.assertRaises(CurveInputError):
            CurveScaler.from_document_bytes(data, expected_sha256="0" * 64)
        with self.assertRaises(CurveInputError):
            CurveScaler.from_document_bytes(data.decode("utf-8"), expected_sha256=expected)
        with self.assertRaises(CurveInputError):
            CurveScaler.from_document_bytes(data, expected_sha256=expected.upper())
        with self.assertRaises(CurveInputError):
            CurveScaler.from_document_bytes(data, expected_sha256=expected[:63])
        not_utf8 = b"\xff\xfe\xfa"
        with self.assertRaises(CurveInputError):
            CurveScaler.from_document_bytes(not_utf8, expected_sha256=hashlib.sha256(not_utf8).hexdigest())
        bad_json = b"{not json"
        with self.assertRaises(CurveInputError):
            CurveScaler.from_document_bytes(bad_json, expected_sha256=hashlib.sha256(bad_json).hexdigest())
        with self.assertRaises(CurveInputError):
            _scaler_from([1, 2, 3])

    def test_contract_identity_and_status_are_pinned(self):
        mutations = (
            lambda document: document.update({"kind": "something-else"}),
            lambda document: document.update({"schema": 2}),
            lambda document: document.update({"schema": True}),
            lambda document: document.update({"software_only": False}),
            lambda document: document.update({"product_card_c01": "passed"}),
            lambda document: document["contract"].update({"id": "OTHER-LOCK"}),
            lambda document: document["contract"].update({"revision": 2}),
            lambda document: document["contract"].update({"source_commit": "0" * 40}),
            lambda document: document["contract"].update({"requirements_sha256": "0" * 64}),
            lambda document: document["contract"].update({"design_commit": "0" * 40}),
            lambda document: document.pop("contract"),
        )
        for mutate in mutations:
            document = _document()
            mutate(document)
            with self.assertRaises(CurveInputError):
                _scaler_from(document)

    def test_profile_channel_order_units_and_transforms_are_pinned(self):
        channels = _default_channels()
        channels[1], channels[2] = channels[2], channels[1]
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(channels))
        channels = _default_channels()
        channels[0]["unit"] = "mV"
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(channels))
        channels = _default_channels()
        channels[3]["transform_version"] = "identity-v1"
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(channels))
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(_default_channels()[:3]))
        document = _document()
        document["algorithm"]["channel_order"] = ["RHOB", "GR", "NPHI", "RDEP"]
        with self.assertRaises(CurveInputError):
            _scaler_from(document)

    def test_channel_statistics_are_validated(self):
        cases = (
            ("valid_samples", 0),
            ("valid_samples", -3),
            ("valid_samples", True),
            ("mean", float("inf")),
            ("mean", float("nan")),
            ("mean", True),
            ("variance", -1.0),
            ("std", math.sqrt(4.0) + 1e-9),
            ("effective_scale", 0.0),
            ("effective_scale", math.sqrt(4.0) * 2.0),
        )
        for key, value in cases:
            channels = _default_channels()
            channels[0][key] = value
            with self.assertRaises(CurveInputError, msg="case %r=%r" % (key, value)):
                _scaler_from(_document(channels))
        channels = _default_channels()
        channels[0]["counts"]["valid"] = 9
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(channels))
        channels = _default_channels()
        channels[0]["counts"]["null"] = -1
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(channels))
        channels = _default_channels()
        channels[0]["zero_variance"] = True
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(channels))
        channels = _default_channels()
        channels[0]["variance"] = 0.0
        channels[0]["std"] = 0.0
        channels[0]["effective_scale"] = 0.0
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(channels))
        channels = _default_channels()
        channels[0].pop("mean")
        with self.assertRaises(CurveInputError):
            _scaler_from(_document(channels))

    def test_scaler_constructor_validation_cannot_be_bypassed(self):
        good = dict(
            name="GR", unit="gAPI", transform_version="identity-v1", valid_samples=10,
            mean=1.0, variance=1.0, std=1.0, zero_variance=False, effective_scale=1.0,
        )
        stats = CurveChannelStatistics(**good)
        for kwargs in (
            dict(preprocessing_sha256="zz", channels=(stats, stats, stats, stats)),
            dict(preprocessing_sha256="0" * 64, channels=(stats, stats, stats)),
            dict(preprocessing_sha256="0" * 64, channels=(stats, stats, stats, stats)),
        ):
            with self.assertRaises((TypeError, CurveInputError)):
                CurveScaler(**kwargs)
        scaler = _default_scaler()
        with self.assertRaises((TypeError, ValueError)):
            dataclasses.replace(scaler)
        with self.assertRaises((TypeError, ValueError)):
            dataclasses.replace(scaler, channels=(stats, stats, stats, stats))
        with self.assertRaises((TypeError, ValueError)):
            dataclasses.replace(scaler, preprocessing_sha256="0" * 64)
        for mutate in (
            {"valid_samples": 0},
            {"variance": 4.0, "std": 1.0, "effective_scale": 1.0},
            {"variance": -1.0},
            {"variance": 0.0, "std": 0.0, "effective_scale": 0.0},
            {"zero_variance": True},
            {"mean": float("inf")},
            {"effective_scale": True},
            {"name": ""},
        ):
            fields = dict(good)
            fields.update(mutate)
            with self.assertRaises(CurveInputError, msg=repr(mutate)):
                CurveChannelStatistics(**fields)
        zero = CurveChannelStatistics(
            name="GR", unit="gAPI", transform_version="identity-v1", valid_samples=10,
            mean=10.0, variance=0.0, std=0.0, zero_variance=True, effective_scale=1.0,
        )
        self.assertEqual(zero.effective_scale, 1.0)

    def test_scaler_constructs_only_from_document_bytes(self):
        data = _document_bytes(_document())
        expected = hashlib.sha256(data).hexdigest()
        direct = CurveScaler(data, expected_sha256=expected)
        wrapped = CurveScaler.from_document_bytes(data, expected_sha256=expected)
        self.assertEqual(direct, wrapped)
        self.assertEqual(direct.preprocessing_sha256, expected)
        mutable = bytearray(data)
        copied = CurveScaler(mutable, expected_sha256=expected)
        mutable[0:1] = b"{"
        self.assertEqual(copied, direct)
        self.assertEqual(copied.preprocessing_sha256, hashlib.sha256(data).hexdigest())

    def test_cp01_forged_statistics_cannot_reuse_a_verified_hash(self):
        document = _document()
        document["channels"][0]["mean"] = _GR_MEAN + 10.0
        data = _document_bytes(document)
        own_hash = hashlib.sha256(data).hexdigest()
        with self.assertRaises(CurveInputError):
            CurveScaler(data, expected_sha256=PINNED_PREPROCESSING_SHA256)
        with self.assertRaises(CurveInputError):
            CurveScaler.from_document_bytes(data, expected_sha256=PINNED_PREPROCESSING_SHA256)
        forged = CurveScaler(data, expected_sha256=own_hash)
        self.assertNotEqual(forged.preprocessing_sha256, PINNED_PREPROCESSING_SHA256)
        self.assertEqual(forged.channels[0].mean, _GR_MEAN + 10.0)
        mismatched = CurveBinding(
            run_id="forged-run", source_domain="software_fixture",
            preprocessing_sha256=PINNED_PREPROCESSING_SHA256,
        )
        with self.assertRaises(CurveInputError):
            CurveWindowBuilder(scaler=forged, binding=mismatched)

    def test_cp01_committed_production_document_provenance(self):
        data = (PRODUCT_ROOT / "data" / "preprocessing.json").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), PINNED_PREPROCESSING_SHA256)
        scaler = CurveScaler(data, expected_sha256=PINNED_PREPROCESSING_SHA256)
        self.assertEqual(scaler.preprocessing_sha256, PINNED_PREPROCESSING_SHA256)
        self.assertEqual(tuple(channel.name for channel in scaler.channels), CHANNEL_NAMES)
        document = json.loads(data.decode("utf-8"))
        document["channels"][0]["mean"] = float(document["channels"][0]["mean"]) + 10.0
        modified = json.dumps(document, sort_keys=True).encode("utf-8")
        with self.assertRaises(CurveInputError):
            CurveScaler(modified, expected_sha256=PINNED_PREPROCESSING_SHA256)
        with self.assertRaises((TypeError, CurveInputError)):
            CurveScaler(preprocessing_sha256=PINNED_PREPROCESSING_SHA256, channels=scaler.channels)

    def test_zero_variance_channel_uses_effective_scale_one(self):
        channels = _default_channels()
        channels[0] = _channel("GR", "gAPI", "identity-v1", 10.0, 0.0, zero_variance=True)
        scaler = _scaler_from(_document(channels))
        binding = _binding(scaler)
        builder = CurveWindowBuilder(scaler=scaler, binding=binding)
        builder.observe(_observation(binding, 1, (13.5, 0.5, 0.2, 10.0), (True, True, True, True)))
        column = _column(builder.snapshot(), 127)
        self.assertEqual(column[0], 3.5)
        self.assertEqual(column[4], 1.0)


class ObservationValidationTests(unittest.TestCase):
    def setUp(self):
        self.scaler = _default_scaler()
        self.binding = _binding(self.scaler)

    def test_observation_constructor_validates_numbers_and_flags(self):
        bad_values = (
            (True, 0.0, 0.0, 0.0),
            (1.0, 2.0, 3.0),
            (1.0, 2.0, 3.0, 4.0, 5.0),
            float("inf"),
            float("nan"),
            "1.0",
            None,
        )
        for values in bad_values:
            with self.assertRaises(CurveInputError, msg=repr(values)):
                _observation(self.binding, 1, values, (True, True, True, True))
        bad_valid = (
            (1, 1, 1, 1),
            (True, True, True),
            (True, True, True, True, False),
            "T",
            (True, True, "yes", True),
            (True, True, True, None),
        )
        for valid in bad_valid:
            with self.assertRaises(CurveInputError, msg=repr(valid)):
                _observation(self.binding, 1, (1.0, 2.0, 3.0, 4.0), valid)
        for sequence in (True, 1.5, "1", -1, MAX_SEQUENCE + 1):
            with self.assertRaises(CurveInputError, msg=repr(sequence)):
                _observation(self.binding, sequence, (1.0, 2.0, 3.0, 4.0), (True, True, True, True))
        with self.assertRaises(CurveInputError):
            _observation("not-a-binding", 1, (1.0, 2.0, 3.0, 4.0), (True, True, True, True))
        lossy_integer = (2 ** 53) + 1
        with self.assertRaises(CurveInputError):
            _observation(self.binding, 1, (lossy_integer, 2.0, 3.0, 4.0), (True, True, True, True))
        with self.assertRaises(CurveInputError):
            _observation(self.binding, 1, (10 ** 400, 2.0, 3.0, 4.0), (True, True, True, True))
        with self.assertRaises(CurveInputError):
            _observation(self.binding, 1, (number for number in (1.0, 2.0, 3.0, 4.0)), (True, True, True, True))
        with self.assertRaises(CurveInputError):
            _observation(self.binding, 1, (1.0, 2.0, 3.0, 4.0), (flag for flag in (True, True, True, True)))
        observation = _observation(self.binding, 0, (1, 2, 3, 4), (True, True, True, True))
        self.assertEqual(observation.values, (1.0, 2.0, 3.0, 4.0))

    def test_binding_validation(self):
        with self.assertRaises(CurveInputError):
            CurveBinding(run_id="", source_domain="software_fixture", preprocessing_sha256="0" * 64)
        with self.assertRaises(CurveInputError):
            CurveBinding(run_id=5, source_domain="software_fixture", preprocessing_sha256="0" * 64)
        with self.assertRaises(CurveInputError):
            CurveBinding(run_id="run", source_domain="simulated", preprocessing_sha256="0" * 64)
        with self.assertRaises(CurveInputError):
            CurveBinding(run_id="run", source_domain="software_fixture", preprocessing_sha256="XYZ")
        with self.assertRaises(CurveInputError):
            CurveBinding(
                run_id="run", source_domain="software_fixture",
                preprocessing_sha256="0" * 64, profile_id="sim_em_v2",
            )
        binding = CurveBinding(run_id="run", source_domain="geo_replay", preprocessing_sha256="0" * 64)
        self.assertEqual(binding.profile_id, PROFILE_ID)
        self.assertEqual(SOURCE_DOMAINS, ("geo_replay", "software_fixture"))

    def test_mapping_exact_allowlist_and_forbidden_keys(self):
        base = {
            "run_id": "run-a",
            "source_domain": "software_fixture",
            "profile_id": PROFILE_ID,
            "preprocessing_sha256": self.scaler.preprocessing_sha256,
            "sequence": 3,
            "value_0": 12.0, "value_1": 0.3, "value_2": 0.2, "value_3": 10.0,
            "valid_0": True, "valid_1": True, "valid_2": True, "valid_3": True,
        }
        observation = observation_from_mapping(base)
        self.assertEqual(observation.sequence, 3)
        self.assertEqual(observation.binding.run_id, "run-a")
        for extra_key in ("label", "future_gr", "seed", "truth_obstacle", "x", "confidence", "scene_name", "target"):
            record = dict(base)
            record[extra_key] = 1
            with self.assertRaises(CurveInputError, msg=extra_key):
                observation_from_mapping(record)
        record = dict(base)
        del record["valid_3"]
        with self.assertRaises(CurveInputError):
            observation_from_mapping(record)
        record = dict(base)
        record[7] = "value"
        with self.assertRaises(CurveInputError):
            observation_from_mapping(record)
        record = dict(base)
        record["value_0"] = "12.0"
        with self.assertRaises(CurveInputError):
            observation_from_mapping(record)
        with self.assertRaises(CurveInputError):
            observation_from_mapping(["run-a"])

    def test_custom_schema_and_generator_rejection(self):
        schema = CurveSchema(
            run_id="rid", source_domain="domain", profile_id="prof", preprocessing_sha256="hash",
            sequence="seq", values=("v0", "v1", "v2", "v3"), valid=("m0", "m1", "m2", "m3"),
        )
        record = {
            "rid": "run-b", "domain": "geo_replay", "prof": PROFILE_ID,
            "hash": self.scaler.preprocessing_sha256, "seq": 4,
            "v0": 12.0, "v1": 0.3, "v2": 0.2, "v3": 10.0,
            "m0": True, "m1": True, "m2": True, "m3": False,
        }
        observation = observation_from_mapping(record, schema=schema)
        self.assertEqual(observation.binding.run_id, "run-b")
        binding_b = CurveBinding(run_id="run-b", source_domain="geo_replay", preprocessing_sha256=self.scaler.preprocessing_sha256)
        builder = CurveWindowBuilder(scaler=self.scaler, binding=binding_b, schema=schema)
        builder.observe(record)
        self.assertEqual(builder.snapshot().metadata.latest_sequence, 4)
        with self.assertRaises(CurveInputError):
            observation_from_mapping(record)
        with self.assertRaises(CurveInputError):
            CurveSchema(values=(name for name in ("v0", "v1", "v2", "v3")))
        with self.assertRaises(CurveInputError):
            CurveWindowBuilder(scaler=self.scaler, binding=self.binding, schema=CurveSchema(run_id="label"))

    def test_cp02_schema_freezes_caller_sequences(self):
        values = ["a0", "a1", "a2", "a3"]
        valid = ["b0", "b1", "b2", "b3"]
        schema = CurveSchema(sequence="seqx", values=values, valid=valid)
        self.assertIsInstance(schema.values, tuple)
        self.assertIsInstance(schema.valid, tuple)
        builder = CurveWindowBuilder(scaler=self.scaler, binding=self.binding, schema=schema)
        values[0] = "renamed_a0"
        values.append("extra_a")
        valid[1] = "renamed_b1"
        record = {
            "run_id": "run-a", "source_domain": "software_fixture", "profile_id": PROFILE_ID,
            "preprocessing_sha256": self.scaler.preprocessing_sha256, "seqx": 1,
            "a0": 12.0, "a1": 0.3, "a2": 0.2, "a3": 10.0,
            "b0": True, "b1": True, "b2": True, "b3": False,
        }
        builder.observe(record)
        snapshot = builder.snapshot()
        self.assertEqual(snapshot.metadata.latest_sequence, 1)
        self.assertEqual(snapshot.metadata.accepted_observations, 1)
        renamed = dict(record)
        renamed["renamed_a0"] = renamed.pop("a0")
        with self.assertRaises(CurveInputError):
            builder.observe(renamed)
        after = builder.snapshot()
        self.assertEqual(after.metadata.latest_sequence, 1)
        self.assertEqual(after.metadata.accepted_observations, 1)
        self.assertEqual(schema.values, ("a0", "a1", "a2", "a3"))
        self.assertEqual(schema.valid, ("b0", "b1", "b2", "b3"))

    def test_cp02_schema_constructor_rejects_invalid_names(self):
        cases = (
            dict(values=(name for name in ("v0", "v1", "v2", "v3"))),
            dict(values=["v0", "v1", "v2"]),
            dict(valid=("m0", "m1", "m2", "m3", "m4")),
            dict(values=("v0", "v0", "v2", "v3")),
            dict(run_id="label"),
            dict(values=("v0", "v1", "v2", 4)),
            dict(source_domain=""),
            dict(values=("run_id", "v1", "v2", "v3")),
            dict(values="v0"),
        )
        for kwargs in cases:
            with self.assertRaises(CurveInputError, msg=repr(kwargs)):
                CurveSchema(**kwargs)

class CurveWindowBehaviourTests(unittest.TestCase):
    def setUp(self):
        self.scaler = _default_scaler()
        self.binding = _binding(self.scaler)

    def _builder(self):
        return CurveWindowBuilder(scaler=self.scaler, binding=self.binding)

    def test_short_prefix_hand_computed(self):
        builder = self._builder()
        builder.observe(_observation(self.binding, 5, (12.0, 0.0, -0.1, 100.0), (True, False, True, True)))
        builder.observe(_observation(self.binding, 6, (8.0, 0.3, 0.5, 0.1), (True, True, True, True)))
        builder.observe(_observation(self.binding, 9, (11.0, 0.4, 0.1, 1.0), (True, True, True, True)))
        window = builder.snapshot()
        newest = (
            (11.0 - _GR_MEAN) / _GR_STD,
            (0.4 - _RHOB_MEAN) / _RHOB_STD,
            (0.1 - _NPHI_MEAN) / _NPHI_STD,
            (math.log10(1.0) - _RDEP_MEAN) / _RDEP_STD,
            1.0, 1.0, 1.0, 1.0,
        )
        self.assertEqual(_column(window, 127), newest)
        self.assertEqual(_column(window, 126), (0.0,) * 8)
        self.assertEqual(_column(window, 125), (0.0,) * 8)
        second = (
            (8.0 - _GR_MEAN) / _GR_STD,
            (0.3 - _RHOB_MEAN) / _RHOB_STD,
            (0.5 - _NPHI_MEAN) / _NPHI_STD,
            (math.log10(0.1) - _RDEP_MEAN) / _RDEP_STD,
            1.0, 1.0, 1.0, 1.0,
        )
        self.assertEqual(_column(window, 124), second)
        first = (
            (12.0 - _GR_MEAN) / _GR_STD,
            0.0,
            (-0.1 - _NPHI_MEAN) / _NPHI_STD,
            (math.log10(100.0) - _RDEP_MEAN) / _RDEP_STD,
            1.0, 0.0, 1.0, 1.0,
        )
        self.assertEqual(_column(window, 123), first)
        self.assertEqual(_column(window, 0), (0.0,) * 8)
        metadata = window.metadata
        self.assertEqual(metadata.filled_slots, 3)
        self.assertEqual(metadata.missing_slots, 125)
        self.assertEqual(metadata.latest_sequence, 9)
        self.assertEqual(metadata.accepted_observations, 3)
        self.assertEqual(metadata.dropped_oldest, 0)
        self.assertEqual(metadata.idempotent_repeats, 0)
        self.assertEqual(metadata.binding, self.binding)
        self.assertEqual(metadata.profile_id, PROFILE_ID)
        self.assertEqual(metadata.preprocessing_sha256, self.scaler.preprocessing_sha256)
        self.assertEqual(builder.latest_sequence, 9)
        self.assertIs(builder.scaler, self.scaler)
        self.assertEqual(builder.binding, self.binding)

    def test_transforms_missing_negative_and_all_missing(self):
        builder = self._builder()
        builder.observe(_observation(self.binding, 1, (-4.0, -2.5, 9.0, -0.5), (True, True, True, True)))
        column = _column(builder.snapshot(), 127)
        self.assertEqual(column[0], (-4.0 - _GR_MEAN) / _GR_STD)
        self.assertEqual(column[1], (-2.5 - _RHOB_MEAN) / _RHOB_STD)
        self.assertEqual(column[2], (9.0 - _NPHI_MEAN) / _NPHI_STD)
        self.assertEqual(column[3], 0.0)
        self.assertEqual(column[4:], (1.0, 1.0, 1.0, 0.0))
        builder.observe(_observation(self.binding, 2, (0.0, 0.0, 0.0, 0.0), (True, True, True, True)))
        column = _column(builder.snapshot(), 127)
        self.assertEqual(column[3], 0.0)
        self.assertEqual(column[7], 0.0)
        builder.observe(_observation(self.binding, 3, (7.0, 2.0, 0.9, 1000.0), (False, False, False, False)))
        column = _column(builder.snapshot(), 127)
        self.assertEqual(column, (0.0,) * 8)

    def test_rollover_127_128_129(self):
        for count, expected_first_sequence in ((127, None), (128, 0), (129, 1)):
            builder = self._builder()
            for index in range(count):
                builder.observe(
                    _observation(self.binding, index, (float(index), 0.5, 0.2, 10.0), (True, True, True, True))
                )
            window = builder.snapshot()
            metadata = window.metadata
            expected_filled = min(count, 128)
            self.assertEqual(metadata.filled_slots, expected_filled, count)
            self.assertEqual(metadata.missing_slots, 128 - expected_filled, count)
            self.assertEqual(metadata.latest_sequence, count - 1, count)
            self.assertEqual(metadata.dropped_oldest, max(0, count - 128), count)
            self.assertEqual(metadata.accepted_observations, count, count)
            self.assertEqual(_column(window, 127)[0], (float(count - 1) - _GR_MEAN) / _GR_STD, count)
            self.assertEqual(_column(window, 127)[4:], (1.0, 1.0, 1.0, 1.0), count)
            if expected_first_sequence is None:
                self.assertEqual(_column(window, 0), (0.0,) * 8, count)
                self.assertEqual(_column(window, 1)[0], (0.0 - _GR_MEAN) / _GR_STD, count)
            else:
                self.assertEqual(_column(window, 0)[0], (float(expected_first_sequence) - _GR_MEAN) / _GR_STD, count)

    def test_huge_gap_and_uint64_boundaries(self):
        builder = self._builder()
        builder.observe(_observation(self.binding, 5, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        huge = 5 + 10 ** 15
        builder.observe(_observation(self.binding, huge, (14.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        window = builder.snapshot()
        self.assertEqual(window.metadata.filled_slots, 1)
        self.assertEqual(window.metadata.dropped_oldest, 1)
        self.assertEqual(window.metadata.latest_sequence, huge)
        self.assertEqual(_column(window, 0), (0.0,) * 8)
        self.assertEqual(_column(window, 126), (0.0,) * 8)
        self.assertEqual(_column(window, 127)[0], (14.0 - _GR_MEAN) / _GR_STD)
        builder2 = self._builder()
        builder2.observe(_observation(self.binding, 0, (1.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        builder2.observe(_observation(self.binding, MAX_SEQUENCE, (1.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        self.assertEqual(builder2.snapshot().metadata.latest_sequence, MAX_SEQUENCE)
        builder2.observe(_observation(self.binding, MAX_SEQUENCE, (1.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        self.assertEqual(builder2.snapshot().metadata.idempotent_repeats, 1)
        with self.assertRaises(CurveInputError):
            builder2.observe(_observation(self.binding, MAX_SEQUENCE, (2.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        with self.assertRaises(CurveInputError):
            builder2.observe(_observation(self.binding, 0, (1.0, 0.5, 0.2, 10.0), (True, True, True, True)))

    def test_duplicate_conflict_reorder_and_atomicity(self):
        builder = self._builder()
        builder.observe(_observation(self.binding, 10, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        before = builder.snapshot()
        builder.observe(_observation(self.binding, 10, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        after = builder.snapshot()
        self.assertEqual(before.features, after.features)
        self.assertEqual(after.metadata.idempotent_repeats, 1)
        self.assertEqual(after.metadata.accepted_observations, 1)
        with self.assertRaises(CurveInputError):
            builder.observe(_observation(self.binding, 10, (13.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        with self.assertRaises(CurveInputError):
            builder.observe(_observation(self.binding, 10, (12.0, 0.5, 0.2, 10.0), (False, True, True, True)))
        with self.assertRaises(CurveInputError):
            builder.observe(_observation(self.binding, 9, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        unchanged = builder.snapshot()
        self.assertEqual(unchanged.features, before.features)
        self.assertEqual(unchanged.metadata.idempotent_repeats, 1)
        self.assertEqual(unchanged.metadata.accepted_observations, 1)
        builder.observe(_observation(self.binding, 11, (16.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        self.assertEqual(builder.snapshot().metadata.latest_sequence, 11)
        overflow_scaler = _scaler_from(_document([
            _channel("GR", "gAPI", "identity-v1", -1e308, 1.0),
            _channel("RHOB", "g/cm3", "identity-v1", 0.5, 0.25),
            _channel("NPHI", "m3/m3", "identity-v1", 0.2, 0.04),
            _channel("RDEP", "ohm.m", "log10-positive-v1", 1.0, 1.0),
        ]))
        overflow_binding = _binding(overflow_scaler)
        overflow_builder = CurveWindowBuilder(scaler=overflow_scaler, binding=overflow_binding)
        overflow_builder.observe(_observation(overflow_binding, 1, (100.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        with self.assertRaises(CurveInputError):
            overflow_builder.observe(_observation(overflow_binding, 2, (1e308, 0.5, 0.2, 10.0), (True, True, True, True)))
        self.assertEqual(overflow_builder.snapshot().metadata.latest_sequence, 1)
        self.assertEqual(overflow_builder.snapshot().metadata.filled_slots, 1)

    def test_binding_mismatch_requires_new_builder(self):
        builder = self._builder()
        builder.observe(_observation(self.binding, 1, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        before = builder.snapshot()
        other_run = _binding(self.scaler, run_id="run-b")
        with self.assertRaises(CurveInputError):
            builder.observe(_observation(other_run, 2, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        other_domain = _binding(self.scaler, run_id="run-a", source_domain="geo_replay")
        with self.assertRaises(CurveInputError):
            builder.observe(_observation(other_domain, 2, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        other_hash = CurveBinding(run_id="run-a", source_domain="software_fixture", preprocessing_sha256="0" * 64)
        with self.assertRaises(CurveInputError):
            builder.observe(_observation(other_hash, 2, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        with self.assertRaises(CurveInputError):
            CurveWindowBuilder(scaler=self.scaler, binding=other_hash)
        self.assertEqual(builder.snapshot().features, before.features)
        fresh = CurveWindowBuilder(scaler=self.scaler, binding=other_run)
        fresh.observe(_observation(other_run, 2, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        self.assertEqual(fresh.snapshot().metadata.filled_slots, 1)
        self.assertEqual(builder.snapshot().metadata.filled_slots, 1)
        self.assertEqual(builder.snapshot().metadata.latest_sequence, 1)

    def test_prefix_snapshots_never_mutate(self):
        builder = self._builder()
        builder.observe(_observation(self.binding, 1, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        builder.observe(_observation(self.binding, 2, (13.0, 0.6, 0.3, 100.0), (True, True, True, True)))
        prefix = builder.snapshot()
        saved_features = tuple(tuple(channel) for channel in prefix.features)
        saved_column = _column(prefix, 127)
        builder.observe(_observation(self.binding, 3, (14.0, 0.7, 0.4, 1000.0), (True, True, True, True)))
        self.assertEqual(prefix.features, saved_features)
        self.assertEqual(_column(prefix, 127), saved_column)
        self.assertNotEqual(_column(builder.snapshot(), 127), saved_column)
        with self.assertRaises(TypeError):
            prefix.features[0][0] = 1.0
        with self.assertRaises(Exception):
            prefix.metadata.latest_sequence = 0
        self.assertFalse(hasattr(builder, "append"))
        self.assertFalse(hasattr(builder, "reset"))
        self.assertFalse(hasattr(prefix, "append"))

    def test_mutable_inputs_cannot_alter_stored_state(self):
        builder = self._builder()
        values = [12.0, 0.5, 0.2, 10.0]
        flags = [True, True, True, True]
        builder.observe(_observation(self.binding, 1, values, flags))
        values[0] = 999.0
        flags[0] = False
        column = _column(builder.snapshot(), 127)
        self.assertEqual(column[0], (12.0 - _GR_MEAN) / _GR_STD)
        self.assertEqual(column[4], 1.0)
        record = {
            "run_id": "run-a", "source_domain": "software_fixture", "profile_id": PROFILE_ID,
            "preprocessing_sha256": self.scaler.preprocessing_sha256, "sequence": 2,
            "value_0": 13.0, "value_1": 0.5, "value_2": 0.2, "value_3": 10.0,
            "valid_0": True, "valid_1": True, "valid_2": True, "valid_3": True,
        }
        builder.observe(record)
        record["value_0"] = 999.0
        record["valid_0"] = False
        column = _column(builder.snapshot(), 127)
        self.assertEqual(column[0], (13.0 - _GR_MEAN) / _GR_STD)
        self.assertEqual(column[4], 1.0)

    def test_bounded_retained_state_over_1000_acquisitions(self):
        builder = self._builder()
        for step in range(2000):
            sequence = step * 3
            values = (float(step % 40), 0.5, 0.2, 10.0)
            builder.observe(_observation(self.binding, sequence, values, (True, True, True, True)))
            if step % 100 == 99:
                builder.observe(_observation(self.binding, sequence, values, (True, True, True, True)))
        window = builder.snapshot()
        metadata = window.metadata
        self.assertEqual(metadata.accepted_observations, 2000)
        self.assertEqual(metadata.idempotent_repeats, 20)
        latest = (2000 - 1) * 3
        retained = [step for step in range(2000) if step * 3 >= latest - (WINDOW_COLUMNS - 1)]
        self.assertEqual(metadata.filled_slots, len(retained))
        self.assertLessEqual(metadata.filled_slots, WINDOW_COLUMNS)
        self.assertEqual(metadata.missing_slots, WINDOW_COLUMNS - len(retained))
        self.assertEqual(metadata.dropped_oldest, 2000 - len(retained))
        self.assertEqual(metadata.latest_sequence, (2000 - 1) * 3)
        self.assertEqual(len(window.features), FEATURE_CHANNELS)
        for channel in window.features:
            self.assertEqual(len(channel), WINDOW_COLUMNS)
            self.assertTrue(all(math.isfinite(value) for value in channel))
        model_input = window.to_model_input()
        self.assertEqual(MODEL_INPUT_SHAPE, (1, FEATURE_CHANNELS, WINDOW_COLUMNS, 1))
        self.assertEqual(len(model_input), 1)
        self.assertEqual(len(model_input[0]), FEATURE_CHANNELS)
        for channel in model_input[0]:
            self.assertEqual(len(channel), WINDOW_COLUMNS)
            self.assertTrue(all(len(column) == 1 for column in channel))
        self.assertEqual(_column(window, 126), (0.0,) * 8)
        self.assertEqual(_column(window, 125), (0.0,) * 8)
        self.assertEqual(_column(window, 127)[4], 1.0)
        self.assertEqual(_column(window, 127)[0], (float(1999 % 40) - _GR_MEAN) / _GR_STD)

    def test_duplicate_deliveries_never_fill_history(self):
        builder = self._builder()
        builder.observe(_observation(self.binding, 1, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        for _ in range(32):
            builder.observe(_observation(self.binding, 1, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        window = builder.snapshot()
        self.assertEqual(window.metadata.filled_slots, 1)
        self.assertEqual(window.metadata.accepted_observations, 1)
        self.assertEqual(window.metadata.idempotent_repeats, 32)
        self.assertEqual(_column(window, 126), (0.0,) * 8)

    def test_window_constructor_validation(self):
        builder = self._builder()
        builder.observe(_observation(self.binding, 1, (12.0, 0.5, 0.2, 10.0), (True, True, True, True)))
        window = builder.snapshot()
        with self.assertRaises(CurveInputError):
            CurveWindow(features=window.features[:7], metadata=window.metadata)
        with self.assertRaises(CurveInputError):
            CurveWindow(features=window.features[:-1], metadata=window.metadata)
        with self.assertRaises(CurveInputError):
            CurveWindow(features=window.features, metadata="nope")
        with self.assertRaises(CurveInputError):
            CurveWindow(features=tuple(tuple(channel[:-1]) for channel in window.features), metadata=window.metadata)

    def test_no_label_or_target_in_api(self):
        for dataclass_type in (
            CurveObservation, CurveBinding, CurveScaler, CurveChannelStatistics, CurveWindowMetadata, CurveWindow,
        ):
            for field_name in dataclass_type.__dataclass_fields__:
                lowered = field_name.lower()
                self.assertNotIn("label", lowered)
                self.assertNotIn("target", lowered)
        signature = inspect.signature(CurveWindowBuilder.observe)
        self.assertNotIn("label", signature.parameters)
        self.assertNotIn("target", signature.parameters)
        builder = self._builder()
        record = {
            "run_id": "run-a", "source_domain": "software_fixture", "profile_id": PROFILE_ID,
            "preprocessing_sha256": self.scaler.preprocessing_sha256, "sequence": 1,
            "value_0": 12.0, "value_1": 0.5, "value_2": 0.2, "value_3": 10.0,
            "valid_0": True, "valid_1": True, "valid_2": True, "valid_3": True,
            "label": "sandstone",
        }
        with self.assertRaises(CurveInputError):
            builder.observe(record)
        self.assertEqual(builder.snapshot().metadata.filled_slots, 0)
        self.assertIsNone(builder.snapshot().metadata.latest_sequence)


class ProfileConstantTests(unittest.TestCase):
    def test_profile_constants(self):
        self.assertEqual(PROFILE_ID, "force_curve_v1")
        self.assertEqual(CHANNEL_NAMES, ("GR", "RHOB", "NPHI", "RDEP"))
        self.assertEqual(CHANNEL_UNITS, ("gAPI", "g/cm3", "m3/m3", "ohm.m"))
        self.assertEqual(
            CHANNEL_TRANSFORMS,
            ("identity-v1", "identity-v1", "identity-v1", "log10-positive-v1"),
        )
        self.assertEqual(MODEL_INPUT_SHAPE, (1, 8, 128, 1))
        self.assertEqual(WINDOW_COLUMNS, 128)
        self.assertEqual(FEATURE_CHANNELS, 8)
        self.assertEqual(SOURCE_DOMAINS, ("geo_replay", "software_fixture"))
        self.assertEqual(MAX_SEQUENCE, (1 << 64) - 1)
        self.assertEqual(CONTRACT_ID, "DEEPEYE-HUMAN-LOCK-20261014")
        self.assertEqual(CONTRACT_REVISION, 1)
        self.assertEqual(CONTRACT_SOURCE_COMMIT, "f5989cd5defce561f9ba98e6b18fc2682945f0a2")
        self.assertEqual(
            CONTRACT_REQUIREMENTS_SHA256,
            "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
        )
        self.assertEqual(CONTRACT_DESIGN_COMMIT, "1011259415a0916054eb580687612580bc1e5f09")


if __name__ == "__main__":
    unittest.main()

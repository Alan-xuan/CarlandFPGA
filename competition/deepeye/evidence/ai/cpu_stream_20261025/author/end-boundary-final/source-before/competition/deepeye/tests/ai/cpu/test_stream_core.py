"""New streaming controls only; real pinned learned model, no old suite calls."""
import copy
import hashlib
import inspect
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PRODUCT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PRODUCT))
from ai_pc.cpu_package import stream_core as module
from ai_pc.cpu_package.stream_core import FrozenForceStream, SessionToken, StreamError, StreamLimits

MODEL = PRODUCT / "ai_pc/cpu_model/force_v1/model_manifest.json"
PUBLIC = PRODUCT / "ai_pc/cpu_model/force_v1/public_input.jsonl"
SAVED = PRODUCT / "evidence/ai/cpu_package_20261024/cpu-baseline/prediction-result.json"


def raw_record(sequence=0, run_id="stream-unit", **changes):
    # Constructed unit-boundary observations; not public-source/model-quality evidence.
    record = {"run_id": run_id, "source_domain": "geo_replay", "profile_id": "force_curve_v1",
              "preprocessing_sha256": module._runner.FIXED_PREPROCESSING_SHA256, "sequence": sequence,
              "value_0": 80.0, "value_1": 2.4, "value_2": .2, "value_3": 10.0,
              "valid_0": True, "valid_1": True, "valid_2": True, "valid_3": True}
    record.update(changes)
    return module._runner.canonical_json(record) + b"\n"


def start(core, generation=1, epoch=0, run_id="stream-unit"):
    return core.start_session(generation=generation, epoch=epoch, run_id=run_id)


class StreamCoreTests(unittest.TestCase):
    def assertUnchangedFailure(self, core, token, raw, code=None):
        before = core.state()
        try:
            previous = core.latest_result(token)
            active_token = True
        except StreamError:
            active_token = False
        with self.assertRaises(StreamError) as caught:
            core.observe(token, raw)
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(core.state(), before)
        if active_token:
            self.assertIs(core.latest_result(token), previous)
        return caught.exception

    def test_selected_saved_c19_prefix_parity_without_old_execute_or_all128(self):
        with PUBLIC.open("rb") as source:
            records = tuple(source.readline() for _ in range(8))
        saved_raw = SAVED.read_bytes()
        self.assertEqual(hashlib.sha256(saved_raw).hexdigest(), "e84bdfe850efb8a231f72c98a5fb05cc20c7f6036014f4db77ef3f6cf44b418f")
        saved = json.loads(saved_raw)["predictions"]
        core = FrozenForceStream()
        token = start(core, run_id="C-FORCE-CPU-20261024-v1")
        compared = []
        for index, raw in enumerate(records):
            actual = core.observe(token, raw)
            if index in (0, 1, 7):
                expected = saved[index]
                self.assertEqual(actual.feature_tensor_sha256, expected["feature_tensor_sha256"])
                self.assertEqual(actual.input_prefix_sha256, expected["input_prefix_sha256"])
                self.assertEqual(actual.probabilities, tuple(expected["probabilities"]))
                self.assertEqual(actual.sequence, expected["window"]["latest_sequence"])
                self.assertEqual(actual.predicted_class_index, expected["predicted_class_index"])
                self.assertEqual(actual.latest_valid_masks, tuple(expected["latest_valid_masks"]))
                compared.append({"index": index, "sequence": actual.sequence,
                                 "feature_sha256": actual.feature_tensor_sha256,
                                 "prefix_sha256": actual.input_prefix_sha256,
                                 "probabilities": actual.probabilities})
        self.assertEqual(core.state().session_deliveries, 8)
        self.assertEqual(actual.metadata.filled_slots, 8)
        self.assertEqual(actual.metadata.missing_slots, 120)
        print(json.dumps({"control": "selected_C19_parity", "new_prefix_calls": 8, "compared": compared}, sort_keys=True))

    def test_model_scaler_loaded_once_and_no_observe_file_reads(self):
        from ai_pc.model import force_cnn
        original_load = force_cnn.load_frozen_model
        original_scaler = module.CurveScaler.from_document_bytes
        with patch.object(force_cnn, "load_frozen_model", wraps=original_load) as load:
            with patch.object(module.CurveScaler, "from_document_bytes", wraps=original_scaler) as scaler:
                core = FrozenForceStream()
                token = start(core)
                with patch("builtins.open", side_effect=AssertionError("post-construction file read")):
                    core.observe(token, raw_record(0))
                    core.observe(token, raw_record(1))
                    core.end_session(token)
                    token2 = start(core, 2, 1)
                    core.observe(token2, raw_record(0))
                self.assertEqual(load.call_count, 1)
                self.assertEqual(scaler.call_count, 1)

    def test_prefix_returns_before_any_invalid_future_record_is_supplied(self):
        core = FrozenForceStream()
        token = start(core)
        raw = raw_record()
        first = core.observe(token, raw)
        self.assertEqual(first.input_prefix_sha256, hashlib.sha256(raw).hexdigest())
        self.assertIs(core.latest_result(token), first)
        future_invalid = raw_record(1, future_tick=123, truth="forbidden")
        self.assertUnchangedFailure(core, token, future_invalid, "schema_invalid")
        self.assertEqual(first.metadata.accepted_observations, 1)

    def test_exact_duplicates_advance_raw_prefix_delivery_but_not_observation(self):
        core = FrozenForceStream()
        token = start(core)
        raw = raw_record(7)
        first = core.observe(token, raw)
        altered_whitespace = b"  " + raw
        with patch.object(module._runner, "_predict", side_effect=AssertionError("duplicate must reuse actual earlier probabilities")):
            second = core.observe(token, altered_whitespace)
        self.assertEqual((second.delivery_index, second.sequence), (1, 7))
        self.assertEqual((second.metadata.accepted_observations, second.metadata.idempotent_repeats), (1, 1))
        self.assertEqual(second.feature_tensor_sha256, first.feature_tensor_sha256)
        self.assertEqual(second.probabilities, first.probabilities)
        self.assertEqual(second.input_prefix_sha256, hashlib.sha256(raw + altered_whitespace).hexdigest())
        self.assertEqual(first.delivery_index, 0)
        self.assertEqual(first.metadata.idempotent_repeats, 0)

    def test_mask_gap_huge_gap_uint64_and_regression_binding_controls(self):
        core = FrozenForceStream()
        token = start(core)
        core.observe(token, raw_record(0))
        masked = core.observe(token, raw_record(2, valid_1=False, value_3=0))
        self.assertEqual(masked.latest_valid_masks, (1., 0., 1., 0.))
        self.assertEqual((masked.metadata.filled_slots, masked.metadata.missing_slots), (2, 126))
        huge = core.observe(token, raw_record((1 << 64) - 1))
        self.assertEqual((huge.metadata.filled_slots, huge.metadata.missing_slots), (1, 127))
        self.assertEqual(huge.sequence, (1 << 64) - 1)
        self.assertUnchangedFailure(core, token, raw_record(0), "schema_invalid")
        self.assertUnchangedFailure(core, token, raw_record(1 << 64), "schema_invalid")
        self.assertUnchangedFailure(core, token, raw_record((1 << 64) - 1, value_0=81), "schema_invalid")
        self.assertUnchangedFailure(core, token, raw_record((1 << 64) - 1, run_id="different"), "binding_invalid")

    def test_float32_failure_after_trial_build_does_not_change_any_committed_state(self):
        core = FrozenForceStream()
        token = start(core)
        first_raw = raw_record(0)
        first = core.observe(token, first_raw)
        self.assertUnchangedFailure(core, token, raw_record(1, value_0=1e300), "feature_invalid")
        next_raw = raw_record(1)
        recovered = core.observe(token, next_raw)
        self.assertEqual((recovered.delivery_index, recovered.metadata.accepted_observations), (1, 2))
        self.assertEqual(recovered.input_prefix_sha256, hashlib.sha256(first_raw + next_raw).hexdigest())
        self.assertEqual(first.metadata.accepted_observations, 1)

    def test_model_and_serialization_failures_including_duplicate_are_atomic(self):
        core = FrozenForceStream()
        token = start(core)
        raw = raw_record(0)
        core.observe(token, raw)
        with patch.object(module._runner, "_predict", side_effect=RuntimeError("injected failure only; no fake logits")):
            self.assertUnchangedFailure(core, token, raw_record(1), "transaction_failed")
        for failure_raw in (raw_record(1), raw):
            with patch.object(module, "_encode", side_effect=ValueError("injected serialization failure")):
                self.assertUnchangedFailure(core, token, failure_raw, "transaction_failed")
        recovered = core.observe(token, raw_record(1))
        self.assertEqual(recovered.delivery_index, 1)
        self.assertEqual(recovered.metadata.idempotent_repeats, 0)

    def test_explicit_end_start_strict_monotonic_identifiers_and_stale_tokens(self):
        core = FrozenForceStream()
        token = start(core)
        core.observe(token, raw_record(0))
        before = core.state()
        with self.assertRaises(StreamError):
            start(core, 2, 1)
        self.assertEqual(core.state(), before)
        for forged in (SessionToken(*token), token._replace(), copy.copy(token), None, True):
            self.assertIsNot(forged, token)
            self.assertUnchangedFailure(core, forged, raw_record(1), "stale_session")
        receipt = core.end_session(token)
        self.assertFalse(receipt.movement_authorized)
        inactive = core.state()
        self.assertEqual((inactive.active_generation, inactive.session_deliveries, inactive.latest_result_sha256), (None, 0, None))
        for generation, epoch in ((1, 1), (2, 0), (True, 1), (2, True), (0, 1), (1 << 32, 1)):
            with self.subTest(generation=generation, epoch=epoch), self.assertRaises(StreamError):
                start(core, generation, epoch)
            self.assertEqual(core.state(), inactive)
        token2 = start(core, 2, 1)  # same opaque run label does not reuse state
        self.assertUnchangedFailure(core, token, raw_record(0), "stale_session")
        cold = core.observe(token2, raw_record(0))
        self.assertEqual((cold.delivery_index, cold.metadata.filled_slots), (0, 1))

    def test_identifier_exhaustion_never_wraps_or_reuses_old_token(self):
        core = FrozenForceStream()
        token = start(core, module.MAX_IDENTIFIER, module.MAX_IDENTIFIER)
        core.end_session(token)
        before = core.state()
        for generation, epoch in ((0, 0), (module.MAX_IDENTIFIER, module.MAX_IDENTIFIER),
                                  (module.MAX_IDENTIFIER + 1, module.MAX_IDENTIFIER + 1)):
            with self.assertRaises(StreamError):
                start(core, generation, epoch)
            self.assertEqual(core.state(), before)

    def test_immutable_nested_output_and_no_external_result_install_method(self):
        core = FrozenForceStream()
        token = start(core)
        result = core.observe(token, raw_record())
        for target, field, value in ((result, "sequence", 123), (result.binding, "run_id", "changed"),
                                     (result.metadata, "accepted_observations", 999)):
            with self.assertRaises((AttributeError, TypeError)):
                object.__setattr__(target, field, value)
        with self.assertRaises(TypeError):
            result.probabilities[0] = 0
        self.assertLessEqual(len(result.encoded), 8192)
        decoded = json.loads(result.encoded)
        self.assertFalse(decoded["movement_authorized"])
        self.assertIsNone(decoded["motion_bytes"])
        self.assertEqual(tuple(decoded["probabilities"]), result.probabilities)
        fake = result._replace(probabilities=(0.,) * 12)
        self.assertUnchangedFailure(core, token, fake, "record_limit")
        self.assertIs(core.latest_result(token), result)
        self.assertNotIn("model", inspect.signature(FrozenForceStream).parameters)
        self.assertNotIn("result", inspect.signature(core.observe).parameters)

    def test_exact_bytes_int_string_and_error_bounds(self):
        class LyingBytes(bytes):
            def __len__(self):
                return 1
        class IntSubclass(int):
            pass
        core = FrozenForceStream()
        token = start(core)
        for raw in (LyingBytes(b"x" * 20000), bytearray(raw_record()), memoryview(raw_record()), iter([raw_record()]), b"x" * 16385):
            self.assertUnchangedFailure(core, token, raw, "record_limit")
        for malformed in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'{}{}', raw_record(label=1), raw_record(sequence=True)):
            exc = self.assertUnchangedFailure(core, token, malformed)
            self.assertLessEqual(len(str(exc)), 256)
        core.end_session(token)
        for kwargs in ({"generation": IntSubclass(2), "epoch": 1, "run_id": "stream-unit"},
                       {"generation": 2, "epoch": 1, "run_id": "x" * 129},
                       {"generation": 2, "epoch": 1, "run_id": "\ud800"}):
            with self.assertRaises(StreamError):
                core.start_session(**kwargs)

    def test_lifetime_delivery_and_byte_caps_cannot_be_reset_by_new_session(self):
        raw = raw_record()
        for limits in (StreamLimits(max_deliveries=1), StreamLimits(max_total_bytes=len(raw))):
            core = FrozenForceStream(limits=limits)
            token = start(core)
            core.observe(token, raw)
            core.end_session(token)
            token2 = start(core, 2, 1)
            self.assertUnchangedFailure(core, token2, raw, "stream_limit")
            self.assertEqual((core.state().lifetime_deliveries, core.state().lifetime_bytes), (1, len(raw)))

    def test_limits_alias_output_and_transition_exhaustion(self):
        limits = StreamLimits(max_deliveries=1, max_sessions=1)
        core = FrozenForceStream(limits=limits)
        object.__setattr__(limits, "max_deliveries", 999)
        token = start(core)
        core.observe(token, raw_record())
        self.assertUnchangedFailure(core, token, raw_record(1), "stream_limit")
        core.end_session(token)
        before = core.state()
        with self.assertRaises(StreamError) as caught:
            start(core, 2, 1)
        self.assertEqual(caught.exception.code, "lifecycle_limit")
        self.assertEqual(core.state(), before)
        limited = FrozenForceStream(limits=StreamLimits(max_output_bytes=512))
        token = start(limited)
        self.assertUnchangedFailure(limited, token, raw_record(), "output_limit")
        self.assertEqual(limited.state().session_deliveries, 0)
        limited.end_session(token)

    def test_reentry_reads_and_lifecycle_are_guarded_without_spawning_threads(self):
        core = FrozenForceStream()
        token = start(core)
        original = module._runner._predict
        def control(torch, model, tensor):
            for action in (lambda: core.state(), lambda: core.latest_result(token),
                           lambda: core.end_session(token), lambda: core.observe(token, raw_record(1))):
                with self.assertRaises(StreamError) as caught:
                    action()
                self.assertEqual(caught.exception.code, "busy")
            return original(torch, model, tensor)
        with patch.object(module._runner, "_predict", side_effect=control):
            result = core.observe(token, raw_record())
        self.assertEqual(result.delivery_index, 0)
        self.assertEqual(core.state().session_deliveries, 1)

    def test_end_serialization_failure_keeps_active_session(self):
        core = FrozenForceStream()
        token = start(core)
        before = core.state()
        with patch.object(module, "_encode", side_effect=ValueError("end failure")):
            with self.assertRaises(StreamError) as caught:
                core.end_session(token)
            self.assertEqual(caught.exception.code, "transaction_failed")
        self.assertEqual(core.state(), before)
        self.assertIsNone(core.latest_result(token))
        core.end_session(token)

    def test_wrong_profile_device_manifest_and_public_injection_refused(self):
        for kwargs, code in (({"profile": "sim_em_v2"}, "sim_em_model_missing"),
                             ({"device": "hip"}, "device_invalid"),
                             ({"expected_manifest_sha256": "0" * 64}, "hash_mismatch")):
            with self.subTest(kwargs=kwargs), self.assertRaises(StreamError) as caught:
                FrozenForceStream(**kwargs)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(TypeError):
            FrozenForceStream(model=lambda x: [0.] * 12)
        for kwargs in ({"max_record_bytes": 16385}, {"max_deliveries": True}, {"max_output_bytes": 1}):
            with self.assertRaises(StreamError):
                StreamLimits(**kwargs)


if __name__ == "__main__":
    unittest.main(verbosity=2)

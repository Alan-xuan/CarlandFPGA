"""Pure software fixtures, never proof of clocks, liveness, source or motion.

The A validator below is an unchanged exact-blob fixture. TEST_ONLY_Verifier
deliberately stands in for an unavailable trusted runtime implementation.
"""
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from ai_pc.control_broker.motion_request import (  # noqa: E402
    HostContext, INT63_MAX, MAX_MESSAGE_BYTES, MAX_OBSERVATIONS,
    MotionRequestAdapter, MotionRequestError, RuntimeBlocked, SentObservation,
)
from ai_pc.control_broker.mailbox import (  # noqa: E402
    BrokerBinding, Candidate, ObservationRef,
)

MS = 1_000_000
CONTEXT = HostContext(42, 3, "b" * 64, 1, 1, 2, 1)
REFERENCE = PRODUCT_ROOT / "evidence/ai/motion_request/reference"


def encoded(document):
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


def observation(sequence=7, *, ordinal=70000, tick=100, lower=0, context=CONTEXT,
                upper=None, anchor=None):
    return SentObservation(context, ordinal, sequence, tick, tick if anchor is None else anchor,
                           lower, lower + MS if upper is None else upper)


def candidate(identity=1, *, context=CONTEXT, seq=7, completed=10 * MS, action=1,
              yaw=0, pitch=0, speed=20, duration=1000):
    return {"schema_version": 1, "context": context.as_dict(), "kind": "model_candidate",
            "candidate_id": identity, "model_sha256": "a" * 64,
            "observation": None if seq is None else
                {"context": context.as_dict(), "observed_seq": seq},
            "completed_monotonic_ns": completed,
            "target": {"action": action, "yaw_q": yaw, "pitch_q": pitch,
                       "speed_code": speed, "duration_ms": duration}}


class TEST_ONLY_Verifier:
    """An explicit software fake. Does not establish any runtime gate."""
    def __init__(self):
        self.checks = []

    def verify_motion(self, check):
        self.checks.append(check)


def adapter_with(*observations, context=CONTEXT, verifier=None):
    verifier = TEST_ONLY_Verifier() if verifier is None else verifier
    adapter = MotionRequestAdapter(context=context, verifier=verifier)
    for item in observations or (observation(context=context),):
        adapter.register_observation(item)
    return adapter, verifier


def submit(adapter, document=None, *, issue=20 * MS, now=20 * MS):
    return adapter.submit(encoded(candidate() if document is None else document),
                          host_issue_ns=issue, now_ns=now)


class ProjectionTests(unittest.TestCase):
    def test_exact_projection_and_audit_keep_original_inputs(self):
        adapter, verifier = adapter_with()
        document = candidate()
        result = submit(adapter, document, now=30 * MS)
        wire = json.loads(result.request_bytes)
        self.assertEqual(set(wire), {"schema_version", "context", "kind", "candidate_id",
                                     "command_seq", "observation", "host_issue_monotonic_ns", "target"})
        self.assertEqual(wire["target"], document["target"])
        self.assertEqual(wire["observation"], document["observation"])
        self.assertEqual(wire["candidate_id"], 1)
        self.assertEqual(wire["command_seq"], 0)
        self.assertEqual(wire["host_issue_monotonic_ns"], 20 * MS)
        self.assertEqual(result.timing.first_issue_ns, 20 * MS)
        self.assertEqual(result.timing.deadline_ns, 1020 * MS)
        self.assertEqual(result.timing.sample_lower_ns, 0)
        self.assertEqual(result.candidate_sha256, hashlib.sha256(encoded(document)).hexdigest())
        self.assertFalse(result.must_stop)
        self.assertFalse(result.movement_authorized)
        self.assertEqual(verifier.checks[0].target, (1, 0, 0, 20, 1000))
        self.assertEqual(verifier.checks[0].observation.sent_ordinal, 70000)
        with self.assertRaises(FrozenInstanceError):
            result.timing.deadline_ns = 10000000000
        document["target"]["speed_code"] = 0
        self.assertEqual(json.loads(result.request_bytes)["target"]["speed_code"], 20)

    def test_stop_needs_no_observation_no_model_or_runtime_proof(self):
        adapter = MotionRequestAdapter(context=CONTEXT)
        result = adapter.safe_stop(now_ns=0)
        document = json.loads(result.request_bytes)
        self.assertIsNone(document["observation"])
        self.assertEqual(document["target"], dict(action=0, yaw_q=0, pitch_q=0, speed_code=0,
                                                   duration_ms=0))
        self.assertTrue(result.must_stop)
        self.assertFalse(result.movement_authorized)
        self.assertIsNone(result.timing)
        self.assertEqual((result.candidate_id, result.command_seq), (0, 0))

    def test_model_stop_accepts_stale_observation_or_null(self):
        for seq in (None, 7):
            with self.subTest(seq=seq):
                adapter = MotionRequestAdapter(context=CONTEXT)
                result = submit(adapter, candidate(seq=seq, action=0, speed=0, duration=0),
                                now=999999 * MS)
                self.assertIsNotNone(result.request_bytes)
                self.assertTrue(result.must_stop)

    def test_opaque_mailbox_payload_is_parsed_and_never_passthrough(self):
        bound = BrokerBinding("run", "session", "fast_9600", 3)
        mailbox_ref = ObservationRef("sent", 100, 0, 70000)
        opaque = Candidate(bound, mailbox_ref, 1, b'{"hidden_map_seed":123}', 10 * MS)
        opaque.validate()  # Existing mailbox deliberately treats payload as opaque.
        adapter, _ = adapter_with()
        with self.assertRaises(MotionRequestError):
            adapter.submit(opaque.payload, host_issue_ns=20 * MS, now_ns=20 * MS)
        legal = replace(opaque, payload=encoded(candidate()))
        self.assertEqual(json.loads(adapter.submit(legal.payload, host_issue_ns=20 * MS,
                                                  now_ns=20 * MS).request_bytes)["kind"],
                         "motion_request")


class StrictInputTests(unittest.TestCase):
    def assert_rejected(self, document):
        adapter, _ = adapter_with()
        with self.assertRaises(MotionRequestError):
            submit(adapter, document)

    def test_every_context_field_is_required_and_exact(self):
        for name, value in CONTEXT.as_dict().items():
            with self.subTest(name=name, variant="missing"):
                document = candidate()
                del document["context"][name]
                self.assert_rejected(document)
            with self.subTest(name=name, variant="mismatch"):
                document = candidate()
                document["context"][name] = "c" * 64 if name == "boot_sha256" else (2 if value != 2 else 1)
                self.assert_rejected(document)
            with self.subTest(name=name, variant="nested"):
                document = candidate()
                document["observation"]["context"][name] = "c" * 64 if name == "boot_sha256" else 0
                self.assert_rejected(document)

    def test_unknown_or_truth_fields_at_every_allowed_object_reject(self):
        for location in ((), ("context",), ("target",), ("observation",),
                         ("observation", "context")):
            for key in ("truth", "obstacle_geometry", "map_seed", "future_sensors",
                        "editor_history", "screenshots", "collision_query", "grant", "extra"):
                with self.subTest(location=location, key=key):
                    document = candidate()
                    node = document
                    for part in location:
                        node = node[part]
                    node[key] = 1
                    self.assert_rejected(document)

    def test_wrong_kind_or_missing_keys_cannot_be_forwarded(self):
        for name in candidate():
            document = candidate()
            del document[name]
            self.assert_rejected(document)
        for kind in ("motion_request", "motion_grant", "board_response", "telem_observation"):
            document = candidate()
            document["kind"] = kind
            self.assert_rejected(document)

    def test_integer_and_hash_fields_reject_bools_floats_ranges(self):
        for name in ("candidate_id", "completed_monotonic_ns", "schema_version"):
            for value in (True, 1.0, -1, INT63_MAX + 1, "1", None):
                document = candidate()
                document[name] = value
                self.assert_rejected(document)
        for value in ("A" * 64, "a" * 63, "g" * 64, 1, None):
            document = candidate()
            document["model_sha256"] = value
            self.assert_rejected(document)
        for value in (True, 1.0, -1, 65536):
            document = candidate()
            document["observation"]["observed_seq"] = value
            self.assert_rejected(document)

    def test_raw_parsing_bounds_duplicates_nonfinite_and_nested_payloads(self):
        good = encoded(candidate())
        bad = [bytearray(good), {}, b"", b"x" * (MAX_MESSAGE_BYTES + 1), b"\xff",
               b"[" * 17 + b"0" + b"]" * 17,
               good[:-1] + b',"candidate_id":2}', good + b"{}",
               good.replace(b'"candidate_id":1', b'"candidate_id":NaN'),
               good.replace(b'"candidate_id":1', b'"candidate_id":Infinity'),
               good.replace(b'"candidate_id":1', b'"candidate_id":1e999'),
               good.replace(b'"candidate_id":1', b'"candidate_id":1.0')]
        for raw in bad:
            with self.subTest(raw=str(raw)[:80]):
                adapter, _ = adapter_with()
                with self.assertRaises(MotionRequestError):
                    adapter.submit(raw, host_issue_ns=20 * MS, now_ns=20 * MS)

    def test_postquantization_combined_curvature_and_zero_speed(self):
        # FAST speed20 radius-ROM permits one axis7000, but not both7000.
        adapter, _ = adapter_with()
        self.assertIsNotNone(submit(adapter, candidate(yaw=7000)).request_bytes)
        for changes in (dict(yaw=7000, pitch=7000), dict(speed=0, yaw=1),
                        dict(speed=21), dict(yaw=15001), dict(duration=0),
                        dict(duration=3001), dict(action=2), dict(action=0),
                        dict(yaw=True), dict(speed=1.0)):
            self.assert_rejected(candidate(**changes))
        stress = replace(CONTEXT, transport_profile_id=2)
        adapter, _ = adapter_with(context=stress)
        self.assertIsNotNone(submit(adapter, candidate(context=stress, yaw=57, duration=12000)).request_bytes)
        for changes in (dict(yaw=58), dict(yaw=41, pitch=41), dict(duration=12001)):
            adapter, _ = adapter_with(context=stress)
            with self.assertRaises(MotionRequestError):
                submit(adapter, candidate(context=stress, **changes))


class IdentityAndClockTests(unittest.TestCase):
    def test_replay_changed_duplicate_and_regression_reject(self):
        adapter, verifier = adapter_with()
        original = submit(adapter, candidate(10))
        for document in (candidate(10), candidate(10, speed=19), candidate(9)):
            with self.assertRaises(MotionRequestError):
                submit(adapter, document, issue=30 * MS, now=30 * MS)
        later = submit(adapter, candidate(11), issue=30 * MS, now=30 * MS)
        self.assertEqual(later.command_seq, 1)
        self.assertEqual(original.timing.first_issue_ns, 20 * MS)
        self.assertEqual(original.timing.deadline_ns, 1020 * MS)
        self.assertEqual(len(verifier.checks), 2)

    def test_generation_restart_is_not_used_as_global_candidate_identity(self):
        adapter, _ = adapter_with()
        first = submit(adapter, candidate(100))
        adapter.register_observation(observation(8, ordinal=70001, tick=101, lower=MS))
        with self.assertRaises(MotionRequestError):
            submit(adapter, candidate(1, seq=8))
        second = submit(adapter, candidate(101, seq=8))
        self.assertEqual((first.candidate_id, second.candidate_id), (100, 101))

    def test_stop_retires_identity_and_command_ids_never_reuse(self):
        adapter, _ = adapter_with()
        self.assertEqual(submit(adapter).command_seq, 0)
        stop = adapter.safe_stop(now_ns=20 * MS)
        self.assertEqual((stop.candidate_id, stop.command_seq), (2, 1))
        with self.assertRaises(MotionRequestError):
            submit(adapter, candidate(2))
        self.assertEqual(submit(adapter, candidate(3)).command_seq, 2)

    def test_clock_regression_and_completion_issue_ordering(self):
        adapter, _ = adapter_with()
        adapter.safe_stop(now_ns=30 * MS)
        with self.assertRaises(MotionRequestError):
            submit(adapter, candidate(10), now=29 * MS)
        for completed, issue, now in ((30, 20, 30), (10, 31, 30)):
            with self.assertRaises(MotionRequestError):
                submit(adapter, candidate(10, completed=completed * MS), issue=issue * MS, now=now * MS)
        self.assertIsNotNone(submit(adapter, candidate(10), now=30 * MS).request_bytes)
        for invalid in (True, 1.0, -1, INT63_MAX + 1):
            with self.assertRaises(MotionRequestError):
                adapter.safe_stop(now_ns=invalid)

    def test_candidate_exhaustion_and_command_sequence_no_wrap(self):
        adapter = MotionRequestAdapter(context=CONTEXT)
        stopped = candidate(INT63_MAX, seq=None, action=0, speed=0, duration=0)
        self.assertIsNotNone(submit(adapter, stopped).request_bytes)
        self.assertIsNone(adapter.safe_stop(now_ns=20 * MS).request_bytes)
        adapter = MotionRequestAdapter(context=CONTEXT)
        for sequence in range(65536):
            result = adapter.safe_stop(now_ns=sequence)
            self.assertEqual(result.command_seq, sequence)
        blocked = adapter.safe_stop(now_ns=65536)
        self.assertIsNone(blocked.request_bytes)
        self.assertIn("new_session_required", blocked.reason)
        self.assertTrue(blocked.must_stop)


class ObservationAndExpiryTests(unittest.TestCase):
    def test_bounded_history_eviction_never_revives_or_rebinds(self):
        adapter, _ = adapter_with()
        first = observation()
        for index in range(1, 6):
            adapter.register_observation(observation(7 + index, ordinal=70000 + index,
                                                      tick=100 + index, lower=index * MS))
        self.assertEqual(len(adapter.retained_observations), MAX_OBSERVATIONS)
        with self.assertRaises(MotionRequestError):
            adapter.register_observation(first)
        result = submit(adapter)
        self.assertTrue(result.must_stop)
        self.assertIsNone(result.request_bytes)
        self.assertEqual(result.reason, "observation_missing_or_retired")

    def test_duplicates_and_all_regressions_are_checked(self):
        original = observation()
        adapter, _ = adapter_with(original)
        adapter.register_observation(original)
        self.assertEqual(len(adapter.retained_observations), 1)
        next_obs = observation(8, ordinal=70001, tick=101, lower=MS, anchor=101)
        for changed in (replace(next_obs, sent_ordinal=70000), replace(next_obs, sample_sequence=7),
                        replace(next_obs, sample_tick_ms=100), replace(next_obs, anchor_tick_ms=99),
                        replace(next_obs, context=replace(CONTEXT, source_id=2))):
            with self.assertRaises(MotionRequestError):
                adapter.register_observation(changed)
        adapter.register_observation(next_obs)
        with self.assertRaises(MotionRequestError):
            adapter.register_observation(observation(9, ordinal=70002, tick=102, lower=0))

    def test_tick_rollover_explicit_sequence_wrap_forbidden_and_half_range_rejected(self):
        edge = (1 << 32) - 1
        old = observation(65534, tick=edge, anchor=edge - 1)
        new = observation(65535, ordinal=70001, tick=edge + 1, anchor=edge, lower=MS)
        self.assertEqual(old.wire_tick_ms, 0xFFFFFFFF)
        self.assertEqual(new.wire_tick_ms, 0)
        self.assertEqual(new.wire_observed_seq, 65535)
        self.assertNotEqual(new.sent_ordinal, new.wire_observed_seq)
        adapter, _ = adapter_with(old)
        adapter.register_observation(new)
        self.assertIsNotNone(submit(adapter, candidate(seq=65535)).request_bytes)
        for seq, tick, anchor in ((65536, edge + 2, edge), (0, 1 << 31, 0),
                                  (0, 0, 1 << 31)):
            with self.assertRaises(MotionRequestError):
                observation(seq, tick=tick, anchor=anchor)
        with self.assertRaises(MotionRequestError):
            adapter.register_observation(observation(0, ordinal=70002, tick=edge + 2,
                                                      anchor=edge, lower=2 * MS))

    def test_original_issue_duration_and_age_deadlines_at_exact_boundary(self):
        for duration, issue, boundary in ((1, 20 * MS, 21 * MS), (3000, 20 * MS, 1500 * MS)):
            for delta, allowed in ((-1, True), (0, False), (1, False)):
                with self.subTest(duration=duration, delta=delta):
                    adapter, _ = adapter_with()
                    result = submit(adapter, candidate(duration=duration), issue=issue,
                                    now=boundary + delta)
                    self.assertEqual(result.request_bytes is not None, allowed)
                    self.assertEqual(result.timing.first_issue_ns, issue)
                    self.assertEqual(result.timing.deadline_ns, boundary)
        stress = replace(CONTEXT, transport_profile_id=2)
        for now in (12000 * MS - 1, 12000 * MS):
            adapter, _ = adapter_with(context=stress)
            result = submit(adapter, candidate(context=stress, duration=12000), now=now)
            self.assertEqual(result.request_bytes is not None, now < 12000 * MS)

    def test_acquisition_interval_never_becomes_receipt_or_native_em_time(self):
        # An upper bound extending beyond now is uncertainty; earliest sample bounds age.
        adapter, verifier = adapter_with(observation(lower=0, upper=500 * MS))
        result = submit(adapter, candidate(duration=3000), now=100 * MS)
        self.assertEqual(result.timing.sample_upper_ns, 500 * MS)
        self.assertEqual(result.timing.deadline_ns, 1500 * MS)
        self.assertFalse(hasattr(verifier.checks[0].observation, "native_em_time"))
        adapter, _ = adapter_with(observation(lower=11 * MS))
        result = submit(adapter)
        self.assertIsNone(result.request_bytes)
        self.assertEqual(result.reason, "completion_precedes_sample")


class RuntimeBoundaryTests(unittest.TestCase):
    def test_mutated_context_and_shadowed_validation_cannot_emit_invalid_context(self):
        context = replace(CONTEXT)
        object.__setattr__(context, "source_id", True)
        object.__setattr__(context, "__post_init__", lambda: None)
        with self.assertRaises(MotionRequestError):
            MotionRequestAdapter(context=context)
        for operation in ("register", "submit", "stop"):
            for forged in (True, 2):  # invalid bool OR valid enum changing negotiated identity
                with self.subTest(operation=operation, forged=forged):
                    context = replace(CONTEXT)
                    adapter, _ = adapter_with(context=context)
                    object.__setattr__(context, "source_id", forged)
                    object.__setattr__(context, "__post_init__", lambda: None)
                    with self.assertRaises(MotionRequestError):
                        if operation == "register":
                            adapter.register_observation(observation(8, ordinal=70001, tick=101))
                        elif operation == "submit":
                            submit(adapter)
                        else:
                            adapter.safe_stop(now_ns=20 * MS)
        context = replace(CONTEXT)
        object.__setattr__(context, "as_dict", lambda: {"source_id": True})
        adapter = MotionRequestAdapter(context=context)
        wire = json.loads(adapter.safe_stop(now_ns=0).request_bytes)
        self.assertEqual(wire["context"], CONTEXT.as_dict())
        self.assertIs(type(wire["context"]["source_id"]), int)

    def test_observation_class_validation_and_detached_sample_snapshots(self):
        forged = observation()
        object.__setattr__(forged, "sample_sequence", True)
        object.__setattr__(forged, "__post_init__", lambda: None)
        adapter = MotionRequestAdapter(context=CONTEXT)
        with self.assertRaises(MotionRequestError):
            adapter.register_observation(forged)
        source = observation()
        adapter, verifier = adapter_with(source)
        object.__setattr__(source, "sample_lower_ns", 999999999)
        public_copy = adapter.retained_observations[0]
        object.__setattr__(public_copy, "sample_lower_ns", 999999999)
        public_context = adapter.context
        object.__setattr__(public_context, "source_id", True)
        result = submit(adapter)
        self.assertEqual(result.timing.sample_lower_ns, 0)
        self.assertEqual(verifier.checks[0].observation.sample_lower_ns, 0)
        self.assertEqual(json.loads(result.request_bytes)["context"], CONTEXT.as_dict())

    def test_deadline_signed63_overflow_blocks_without_fabricating_timing(self):
        near_end = observation(lower=INT63_MAX - 20 * MS, upper=INT63_MAX - 19 * MS)
        adapter, _ = adapter_with(near_end)
        result = submit(adapter, candidate(completed=INT63_MAX - 10 * MS),
                        issue=INT63_MAX - 5 * MS, now=INT63_MAX - MS)
        self.assertIsNone(result.request_bytes)
        self.assertTrue(result.must_stop)
        self.assertIsNone(result.timing)
        self.assertEqual(result.reason, "original_deadline_unrepresentable")
        self.assertIsNotNone(adapter.safe_stop(now_ns=INT63_MAX).request_bytes)
        # An overflowing unused term is harmless when the minimum remains representable.
        adapter, _ = adapter_with(observation(lower=INT63_MAX - 1500 * MS,
                                              upper=INT63_MAX - 1499 * MS))
        result = submit(adapter, candidate(completed=INT63_MAX - 10 * MS),
                        issue=INT63_MAX - 5 * MS, now=INT63_MAX - MS)
        self.assertIsNotNone(result.request_bytes)
        self.assertEqual(result.timing.deadline_ns, INT63_MAX)

    def test_missing_verifier_is_blocked_and_retired_even_after_recovery(self):
        adapter = MotionRequestAdapter(context=CONTEXT)
        adapter.register_observation(observation())
        result = submit(adapter)
        self.assertIsNone(result.request_bytes)
        self.assertTrue(result.must_stop)
        self.assertEqual(result.reason, "runtime_verifier_missing")
        with self.assertRaises(MotionRequestError):
            submit(adapter, issue=30 * MS, now=30 * MS)
        self.assertIsNotNone(adapter.safe_stop(now_ns=30 * MS).request_bytes)

    def test_failed_clock_provenance_or_liveness_and_boolean_attestation_block(self):
        class Failure:
            def __init__(self, reason):
                self.reason = reason

            def verify_motion(self, check):
                raise RuntimeBlocked(self.reason)

        class BooleanAttestation:
            def verify_motion(self, check):
                return True

        for verifier in [Failure("no measured clock"), Failure("unknown source provenance"),
                         Failure("source heartbeat timeout"), Failure("model dead"),
                         BooleanAttestation(), object()]:
            adapter, _ = adapter_with(verifier=verifier)
            result = submit(adapter)
            self.assertIsNone(result.request_bytes)
            self.assertEqual(result.reason, "runtime_evidence_unverified")
            self.assertTrue(result.must_stop)

    def test_verifier_is_called_for_every_motion_with_complete_immutable_check(self):
        adapter, verifier = adapter_with()
        submit(adapter)
        submit(adapter, candidate(2), issue=30 * MS, now=40 * MS)
        self.assertEqual(len(verifier.checks), 2)
        check = verifier.checks[1]
        self.assertEqual(check.context, CONTEXT)
        self.assertEqual(check.timing.first_issue_ns, 30 * MS)
        self.assertEqual(check.now_ns, 40 * MS)
        with self.assertRaises(FrozenInstanceError):
            check.observation.sample_lower_ns = 40 * MS


class ExactAInteroperabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fail if fixtures are absent or changed; interoperability never silently skips.
        manifest = json.loads((REFERENCE / "manifest.json").read_bytes())
        assert manifest["commit"] == "d5bf26adcf76f8c9af3165cdd7043cb3ff19649b"
        for entry in manifest["files"]:
            raw = (REFERENCE / entry["fixture_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == entry["sha256"], entry["fixture_path"]
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            assert blob == entry["git_blob_sha1"], entry["fixture_path"]
        spec = importlib.util.spec_from_file_location("a_exact_host_envelope",
                                                      REFERENCE / "integration/host_envelope.py")
        cls.reference = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.reference
        spec.loader.exec_module(cls.reference)

    def validate(self, raw, context, now):
        return self.reference.validate_message(raw, producer="control_broker",
                                               context=context.as_dict(), now_ns=now)

    def test_every_profile_and_topology_request_passes_exact_a_validator(self):
        for profile in (1, 2):
            for topology in (1, 2, 3):
                context = replace(CONTEXT, transport_profile_id=profile, topology_id=topology)
                adapter, _ = adapter_with(context=context)
                result = submit(adapter, candidate(context=context, yaw=1))
                accepted = self.validate(result.request_bytes, context, 20 * MS)
                self.assertEqual(accepted.kind, "motion_request")
                stopped = adapter.safe_stop(now_ns=20 * MS)
                self.assertEqual(self.validate(stopped.request_bytes, context, 20 * MS).kind,
                                 "motion_request")

    def test_independent_a_rejects_injected_or_wrong_producer_request(self):
        adapter, _ = adapter_with()
        raw = submit(adapter).request_bytes
        for name in ("truth", "model_sha256", "completed_monotonic_ns", "deadline_monotonic_ns"):
            document = json.loads(raw)
            document[name] = 1
            with self.assertRaises(ValueError):
                self.validate(encoded(document), CONTEXT, 20 * MS)
        with self.assertRaises(ValueError):
            self.reference.validate_message(raw, producer="ai_controller",
                                             context=CONTEXT.as_dict(), now_ns=20 * MS)

    def test_curvature_boundary_grid_agrees_with_independent_a_reference(self):
        for profile in (1, 2):
            context = replace(CONTEXT, transport_profile_id=profile)
            for speed in (0, 1, 10, 20):
                limit = self.reference._motion.curvature_limit_squared(
                    "fast_9600" if profile == 1 else "stress_300", speed)
                import math
                edge = math.isqrt(limit)
                for yaw, pitch in ((edge, 0), (edge + 1, 0), (edge, edge),
                                   (-edge, 0), (0, 0)):
                    expected = yaw * yaw + pitch * pitch <= limit
                    adapter, _ = adapter_with(context=context)
                    try:
                        result = submit(adapter, candidate(context=context, yaw=yaw, pitch=pitch,
                                                           speed=speed))
                    except MotionRequestError:
                        self.assertFalse(expected)
                    else:
                        self.assertTrue(expected)
                        self.validate(result.request_bytes, context, 20 * MS)


if __name__ == "__main__":
    unittest.main()

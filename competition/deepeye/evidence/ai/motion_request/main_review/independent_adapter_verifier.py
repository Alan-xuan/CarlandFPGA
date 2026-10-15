"""Independent C adapter verification. Run only after parent sends STABLE.

Uses the reviewed A PR24 exact validator and the adapter's public API only.
Synthetic provenance verifiers here are fixtures, never runtime/board proof.
No product source or service state is written; bytecode writing is disabled.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import random
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
DEFAULT_PRODUCT = PROJECT / ".local/deepeye-implementation-c/competition/deepeye"
INT63_MAX = (1 << 63) - 1
CONTEXT = {"session": 42, "config_epoch": 3, "boot_sha256": "b" * 64,
           "transport_profile_id": 1, "source_id": 1, "topology_id": 2,
           "acquisition_profile_id": 1}
REQUEST_KEYS = {"schema_version", "context", "kind", "candidate_id", "command_seq",
                "observation", "host_issue_monotonic_ns", "target"}
TARGET = {"action": 1, "yaw_q": 0, "pitch_q": 0, "speed_code": 20, "duration_ms": 1000}
ZERO = {"action": 0, "yaw_q": 0, "pitch_q": 0, "speed_code": 0, "duration_ms": 0}
EXPECTED_A = {
    "host_contract.json": "a291d48a8791757bf0d612bdcc08d4c5c0d2a133b57990e803063619f8a88f28",
    "host_envelope.py": "025adf0eee851327f6492ac853b77bc6ebfbb26c17eb7960f01baf644de4b7fd",
    "motion.py": "69d016f8890298829e71c18efbbb76e747bbf5c79d2ca3af1d5defd364071822",
    "wire.py": "31533439f1bab32ca71fae138bb988f51ce1d043b4e364a6c33a09eab1d5f5ec",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reference():
    for filename, expected in EXPECTED_A.items():
        if sha(HERE / filename) != expected:
            raise RuntimeError("exact A reference identity mismatch: " + filename)
    spec = importlib.util.spec_from_file_location("independent_exact_A_host_envelope", HERE / "host_envelope.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.SCHEMA_PATH = HERE / "host_contract.json"
    return module


def raw(document):
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def candidate(context=None, candidate_id=1, target=None, observation=True, completed=10_000_000, sequence=7):
    ctx = deepcopy(CONTEXT if context is None else context)
    return {"schema_version": 1, "context": ctx, "kind": "model_candidate", "candidate_id": candidate_id,
            "model_sha256": "a" * 64,
            "observation": {"context": deepcopy(ctx), "observed_seq": sequence} if observation else None,
            "completed_monotonic_ns": completed, "target": deepcopy(TARGET if target is None else target)}


class FixtureVerifier:
    """Permissive fixture; records a check but supplies no runtime proof."""
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def verify_motion(self, check):
        self.calls.append(check)
        if self.error is not None:
            raise self.error
        return self.result


class IndependentAdapterTests(unittest.TestCase):
    def adapter(self, *, context=None, verifier="fixture", register=True, **observation_changes):
        ctx = deepcopy(CONTEXT if context is None else context)
        fixture = FixtureVerifier() if verifier == "fixture" else verifier
        instance = ADAPTER.MotionRequestAdapter(context=ADAPTER.HostContext(**ctx), verifier=fixture)
        if register:
            fields = {"context": ADAPTER.HostContext(**ctx), "sent_ordinal": 70000, "sample_sequence": 7,
                      "sample_tick_ms": 100, "anchor_tick_ms": 100, "sample_lower_ns": 0,
                      "sample_upper_ns": 1_000_000}
            fields.update(observation_changes)
            instance.register_observation(ADAPTER.SentObservation(**fields))
        return instance, fixture

    def submit(self, instance, document=None, *, issue=20_000_000, now=30_000_000):
        payload = raw(candidate() if document is None else document)
        return instance.submit(payload, host_issue_ns=issue, now_ns=now)

    def assert_no_motion(self, decision):
        self.assertIs(decision.movement_authorized, False)
        self.assertIs(decision.must_stop, True)
        self.assertIsNone(decision.request_bytes)

    def rejected(self, fn):
        try:
            decision = fn()
        except ADAPTER.MotionRequestError:
            return
        self.assert_no_motion(decision)

    def validate_request(self, decision, *, context=None, now=30_000_000):
        ctx = CONTEXT if context is None else context
        self.assertIs(decision.movement_authorized, False)
        self.assertIsInstance(decision.request_bytes, bytes)
        record = A.validate_message(decision.request_bytes, producer="control_broker", context=ctx, now_ns=now)
        doc = record.document
        self.assertEqual(set(doc), REQUEST_KEYS)
        self.assertEqual(doc["kind"], "motion_request")
        self.assertEqual(doc["context"], ctx)
        self.assertIs(type(doc["command_seq"]), int)
        self.assertTrue(0 <= doc["command_seq"] <= 65535)
        return doc

    def test_01_exact_A_interoperability_and_projection(self):
        instance, fixture = self.adapter()
        payload = raw(candidate())
        result = instance.submit(payload, host_issue_ns=20_000_000, now_ns=30_000_000)
        self.assertIs(result.must_stop, False)
        doc = self.validate_request(result)
        self.assertEqual(doc["candidate_id"], 1)
        self.assertEqual(doc["observation"], candidate()["observation"])
        self.assertEqual(doc["target"], TARGET)
        self.assertEqual(doc["host_issue_monotonic_ns"], 20_000_000)
        self.assertEqual(result.candidate_sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(len(fixture.calls), 1)
        self.assertEqual(result.timing.first_issue_ns, 20_000_000)
        self.assertEqual(result.timing.original_duration_ms, 1000)
        self.assertEqual(result.timing.sample_lower_ns, 0)
        self.assertEqual(result.timing.sample_upper_ns, 1_000_000)
        self.assertEqual(result.timing.deadline_ns, 1_020_000_000)

    def test_02_missing_provenance_is_closed_and_identity_retired(self):
        instance, _ = self.adapter(verifier=None)
        self.assert_no_motion(self.submit(instance))
        self.rejected(lambda: self.submit(instance, issue=40_000_000, now=50_000_000))

    def test_03_verifier_failure_or_non_none_is_closed(self):
        for fixture in (FixtureVerifier(result=True), FixtureVerifier(result=False),
                        FixtureVerifier(result="verified"), FixtureVerifier(error=RuntimeError("fixture failure"))):
            with self.subTest(result=repr(fixture.result), error=repr(fixture.error)):
                instance, _ = self.adapter(verifier=fixture)
                self.assert_no_motion(self.submit(instance))

    def test_04_safe_stop_independent_of_observation_and_verifier(self):
        instance, _ = self.adapter(verifier=None, register=False)
        decision = instance.safe_stop(now_ns=30_000_000)
        doc = self.validate_request(decision)
        self.assertEqual(doc["target"], ZERO)
        self.assertIsNone(doc["observation"])

    def test_05_model_stop_null_observation_is_legal(self):
        instance, _ = self.adapter(verifier=None, register=False)
        decision = self.submit(instance, candidate(target=ZERO, observation=False))
        self.assertEqual(self.validate_request(decision)["target"], ZERO)

    def test_06_replay_or_changed_payload_cannot_reissue(self):
        for changed in (False, True):
            with self.subTest(changed=changed):
                instance, _ = self.adapter()
                first = self.submit(instance)
                initial = first.timing
                retry = candidate()
                if changed:
                    retry["target"]["duration_ms"] = 999
                self.rejected(lambda: self.submit(instance, retry, issue=40_000_000, now=50_000_000))
                self.assertEqual(initial.first_issue_ns, 20_000_000)
                self.assertEqual(initial.deadline_ns, 1_020_000_000)

    def test_07_candidate_id_monotonicity_and_range(self):
        instance, _ = self.adapter()
        self.validate_request(self.submit(instance, candidate(candidate_id=2)))
        self.rejected(lambda: self.submit(instance, candidate(candidate_id=1), now=40_000_000))
        for identity in (True, 1.0, -1, INT63_MAX + 1):
            instance, _ = self.adapter()
            self.rejected(lambda: self.submit(instance, candidate(candidate_id=identity)))

    def test_08_context_whitelist_and_target_rejections(self):
        documents = []
        doc = candidate(); doc["run_id"] = "hidden internal metadata"; documents.append(doc)
        doc = candidate(); doc["truth_obstacle"] = [1, 2, 3]; documents.append(doc)
        doc = candidate(); doc["context"]["session"] = 43; documents.append(doc)
        doc = candidate(); doc["observation"]["context"]["source_id"] = 2; documents.append(doc)
        doc = candidate(); doc["context"]["transport_profile_id"] = 1.0; documents.append(doc)
        doc = candidate(); doc["observation"] = None; documents.append(doc)
        doc = candidate(); doc["observation"]["observed_seq"] = 4464; documents.append(doc)
        doc = candidate(); doc["target"]["duration_ms"] = 3001; documents.append(doc)
        doc = candidate(); doc["target"].update(yaw_q=6000, pitch_q=6000); documents.append(doc)
        doc = candidate(); doc["target"].update(speed_code=0, yaw_q=1); documents.append(doc)
        doc = candidate(); doc["target"].update(action=0); documents.append(doc)
        for number, doc in enumerate(documents):
            with self.subTest(number=number):
                instance, _ = self.adapter()
                self.rejected(lambda: self.submit(instance, doc))

    def test_09_raw_parser_rejects_duplicates_nonfinite_and_oversize(self):
        original = raw(candidate())
        malformed = [original.replace(b'"candidate_id":1', b'"candidate_id":1,"candidate_id":2'),
                     original.replace(b'"candidate_id":1', b'"candidate_id":NaN'),
                     b" " * 16385, b"\xff", original + b"{}"]
        for payload in malformed:
            instance, _ = self.adapter()
            self.rejected(lambda: instance.submit(payload, host_issue_ns=20_000_000, now_ns=30_000_000))

    def test_10_timestamp_and_clock_order_fail_closed(self):
        for complete, issue, now in ((30_000_001, 20_000_000, 30_000_000),
                                     (25_000_000, 20_000_000, 30_000_000),
                                     (10_000_000, 30_000_001, 30_000_000)):
            instance, _ = self.adapter()
            self.rejected(lambda: self.submit(instance, candidate(completed=complete), issue=issue, now=now))
        instance, _ = self.adapter(sample_lower_ns=15_000_000, sample_upper_ns=16_000_000)
        self.rejected(lambda: self.submit(instance))

    def test_11_history_eviction_and_wrong_reference(self):
        instance, _ = self.adapter(register=False)
        for i in range(5):
            instance.register_observation(ADAPTER.SentObservation(context=ADAPTER.HostContext(**CONTEXT),
                sent_ordinal=70000+i, sample_sequence=7+i, sample_tick_ms=100+i, anchor_tick_ms=100,
                sample_lower_ns=i*1_000_000, sample_upper_ns=(i+1)*1_000_000))
        self.rejected(lambda: self.submit(instance, candidate(sequence=7)))
        self.rejected(lambda: self.submit(instance, candidate(candidate_id=2, sequence=65535)))

    def test_12_independent_random_deadline_arithmetic(self):
        rng = random.Random(20261015)
        for number in range(96):
            profile = 1 if number % 2 == 0 else 2
            age_cap = 1_500_000_000 if profile == 1 else 12_000_000_000
            duration_cap = 3000 if profile == 1 else 12000
            sample_lower = rng.randrange(0, 1_000_000_000_000)
            issue = sample_lower + rng.randrange(2_000_001, 100_000_000)
            duration = rng.randrange(1, duration_cap + 1)
            expected = min(issue + duration * 1_000_000, sample_lower + age_cap)
            ctx = deepcopy(CONTEXT); ctx["transport_profile_id"] = profile
            instance, _ = self.adapter(context=ctx, sample_lower_ns=sample_lower,
                                       sample_upper_ns=sample_lower+1_000_000)
            target = dict(TARGET, duration_ms=duration)
            doc = candidate(ctx, target=target, completed=issue-1)
            decision = self.submit(instance, doc, issue=issue, now=issue)
            with self.subTest(number=number, profile=profile):
                self.assertIs(decision.must_stop, False)
                self.validate_request(decision, context=ctx, now=issue)
                self.assertEqual(decision.timing.deadline_ns, expected)
                self.assertEqual(decision.timing.first_issue_ns, issue)
                self.assertEqual(decision.timing.original_duration_ms, duration)
                self.assertEqual(decision.timing.sample_lower_ns, sample_lower)

    def test_13_exact_deadline_and_age_expire(self):
        for duration, issue, now in ((1000, 20_000_000, 1_020_000_000),
                                     (3000, 20_000_000, 1_500_000_000)):
            instance, _ = self.adapter()
            self.assert_no_motion(self.submit(instance, candidate(target=dict(TARGET, duration_ms=duration)), issue=issue, now=now))

    def test_14_public_command_allocator_never_wraps(self):
        instance, _ = self.adapter(verifier=None, register=False)
        previous_candidate = -1
        seen = set()
        for index in range(65536):
            decision = instance.safe_stop(now_ns=index)
            self.assertIs(decision.movement_authorized, False)
            self.assertIsInstance(decision.request_bytes, bytes)
            doc = json.loads(decision.request_bytes)
            sequence = doc["command_seq"]
            self.assertIs(type(sequence), int)
            self.assertTrue(0 <= sequence <= 65535)
            self.assertNotIn(sequence, seen)
            self.assertGreater(doc["candidate_id"], previous_candidate)
            previous_candidate = doc["candidate_id"]
            seen.add(sequence)
            if index in (0, 65535):
                self.validate_request(decision, now=index)
        self.assertEqual(len(seen), 65536)
        exhausted = instance.safe_stop(now_ns=65536)
        self.assert_no_motion(exhausted)
        self.assertIn("new_session_required", exhausted.reason)

    def test_15_candidate_allocator_does_not_wrap_at_INT63(self):
        instance, _ = self.adapter(verifier=None, register=False)
        self.validate_request(self.submit(instance, candidate(candidate_id=INT63_MAX, target=ZERO, observation=False)))
        exhausted = instance.safe_stop(now_ns=40_000_000)
        self.assert_no_motion(exhausted)
        self.assertIn("new_session_required", exhausted.reason)

    def test_16_mutated_dataclasses_cannot_bypass_public_boundaries(self):
        forged_context = ADAPTER.HostContext(**CONTEXT)
        object.__setattr__(forged_context, "source_id", True)
        with self.assertRaises(ADAPTER.MotionRequestError):
            ADAPTER.MotionRequestAdapter(context=forged_context, verifier=FixtureVerifier())

        live_context = ADAPTER.HostContext(**CONTEXT)
        instance = ADAPTER.MotionRequestAdapter(context=live_context, verifier=FixtureVerifier())
        observation = ADAPTER.SentObservation(context=live_context, sent_ordinal=70000,
            sample_sequence=7, sample_tick_ms=100, anchor_tick_ms=100,
            sample_lower_ns=0, sample_upper_ns=1_000_000)
        instance.register_observation(observation)
        object.__setattr__(live_context, "source_id", True)
        try:
            result = self.submit(instance)
        except ADAPTER.MotionRequestError:
            pass
        else:
            if result.request_bytes is None:
                self.assert_no_motion(result)
            else:
                # A defensive immutable snapshot is also safe: it must emit the
                # original complete integer context, never the mutated bool.
                self.validate_request(result)

        instance, _ = self.adapter(register=False)
        forged_observation = ADAPTER.SentObservation(context=ADAPTER.HostContext(**CONTEXT),
            sent_ordinal=70000, sample_sequence=7, sample_tick_ms=100, anchor_tick_ms=100,
            sample_lower_ns=0, sample_upper_ns=1_000_000)
        object.__setattr__(forged_observation, "sample_lower_ns", -1)
        try:
            object.__setattr__(forged_observation, "validate", lambda: None)
        except AttributeError:
            pass  # Slot-based objects cannot shadow a validation method.
        with self.assertRaises(ADAPTER.MotionRequestError):
            instance.register_observation(forged_observation)

    def test_17_deadline_representability_does_not_wrap_or_authorize(self):
        sample_lower = INT63_MAX - 50_000_000
        issue = INT63_MAX - 20_000_000
        instance, _ = self.adapter(sample_lower_ns=sample_lower, sample_upper_ns=sample_lower+1_000_000)
        self.rejected(lambda: self.submit(instance, candidate(completed=issue-1), issue=issue, now=issue))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable-sha256", required=True, help="Exact stable adapter source SHA256 supplied by parent after worker final")
    parser.add_argument("--product-root", type=Path, default=DEFAULT_PRODUCT)
    args = parser.parse_args()
    product = args.product_root.resolve()
    adapter_path = product / "ai_pc/control_broker/motion_request.py"
    if sha(adapter_path) != args.stable_sha256.lower():
        raise RuntimeError("stable adapter identity mismatch before import")
    global A, ADAPTER
    A = load_reference()
    sys.path.insert(0, str(product))
    ADAPTER = importlib.import_module("ai_pc.control_broker.motion_request")
    if Path(ADAPTER.__file__).resolve() != adapter_path.resolve():
        raise RuntimeError("import did not resolve to the parent-selected adapter")
    sources = [adapter_path, product / "ai_pc/control_broker/mailbox.py", product / "ai_pc/control_broker/deadlines.py"]
    before = {str(path): sha(path) for path in sources}
    log = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IndependentAdapterTests)
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    after = {str(path): sha(path) for path in sources}
    unchanged = before == after
    if not unchanged:
        log.write("\nSOURCE_CHANGED_DURING_VERIFICATION\n")
    output = {"work_id": "C-independent-motion-adapter-verifier-20261015-v1",
              "scope": "Independent software record/fixture checks only; no runtime/ACL/source-clock/capture/board/product acceptance",
              "a_commit": "d5bf26adcf76f8c9af3165cdd7043cb3ff19649b", "a_references": EXPECTED_A,
              "immutable_scope_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
              "python_executable": sys.executable, "python_version": sys.version,
              "jsonschema": importlib.metadata.version("jsonschema"), "verifier_source_sha256": sha(Path(__file__)),
              "source_hashes_before": before, "source_hashes_after": after, "source_bytes_unchanged": unchanged,
              "tests_run": result.testsRun, "random_deadline_vectors": 96, "public_stop_allocations": 65536,
              "failures": len(result.failures), "errors": len(result.errors),
              "exit_code": 0 if result.wasSuccessful() and unchanged else 1}
    log_bytes = log.getvalue().encode("utf-8")
    (HERE / "independent-adapter-verifier.log").write_bytes(log_bytes)
    output["raw_log_sha256"] = hashlib.sha256(log_bytes).hexdigest()
    (HERE / "independent-adapter-verifier-result.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(log.getvalue(), end="")
    print(json.dumps(output))
    return output["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())

"""Independent tests for ai_pc.control_broker.mailbox (C05 foundation).

Software fixtures only: caller-supplied integer monotonic nanoseconds and
opaque payload bytes, no clock, board, network or world I/O.  Coverage:
bounded observation history, sequence wrap rejection, exact binding,
lineage-first ordering with reversed completions, identical/conflicting
duplicates, forged dataclass inputs through public entrypoints, the
150/250 ms next-slot handoff, stale/evicted observations, age boundary,
the always-False movement authorization boundary, persisted high-water
ordering (B01), future completions (B02), explicit uint64 sent ordinals
with constant-size state (B03), frozen profile binding names, the
caller-clock high-water scalar (BR21) and the frozen-profile caller age cap
bound (BR22).
"""

import inspect
import sys
import unittest
from dataclasses import replace
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from ai_pc.control_broker.deadlines import BrokerError  # noqa: E402
from ai_pc.control_broker.mailbox import (  # noqa: E402
    CONSUME_COMPLETED_AFTER_SLOT_DEADLINE,
    CONSUME_EMPTY,
    CONSUME_OBSERVATION_AGE_EXCEEDED,
    CONSUME_OBSERVATION_EVICTED,
    CONSUME_OK,
    MAX_SENT_OBSERVATIONS,
    OFFER_ACCEPTED,
    OFFER_DUPLICATE_IGNORED,
    OFFER_STALE_IGNORED,
    BrokerBinding,
    Candidate,
    Consumption,
    ControlMailbox,
    ObservationRef,
)

SECOND = 1_000_000_000
MS = 1_000_000
AGE_LIMIT = 1_500 * MS
FAST_CAP = 1_500 * MS
STRESS_CAP = 12 * SECOND
BINDING = BrokerBinding(
    run_id="sim-run-1", session_id="sess-7", profile="fast_9600", epoch=3
)
STRESS_BINDING = BrokerBinding(
    run_id="sim-run-1", session_id="sess-7", profile="stress_300", epoch=3
)


def observation(oid="telem-1", *, ordinal=1, tick=100, lower=0):
    return ObservationRef(
        observation_id=oid,
        sample_tick_ms=tick,
        sample_time_lower_ns=lower,
        sent_ordinal=ordinal,
    )


def candidate(obs, *, ordinal=1, payload=b"payload-1", completed=100 * MS,
              binding=BINDING):
    return Candidate(
        binding=binding,
        observation=obs,
        generation_ordinal=ordinal,
        payload=payload,
        completed_at_ns=completed,
    )


def mailbox_with(*observations):
    mailbox = ControlMailbox(binding=BINDING)
    for item in observations:
        mailbox.register_sent_observation(item)
    return mailbox


class RegistrationTests(unittest.TestCase):
    def test_bounded_history_retains_four_and_retires_oldest(self):
        mailbox = ControlMailbox(binding=BINDING)
        ordinals = []
        for index in range(5):
            ordinals.append(
                mailbox.register_sent_observation(
                    observation(
                        f"telem-{index}",
                        ordinal=index + 1,
                        tick=100 * (index + 1),
                        lower=10 * MS * index,
                    )
                )
            )
        self.assertEqual(ordinals, [1, 2, 3, 4, 5])
        self.assertEqual(len(mailbox.observation_ids), MAX_SENT_OBSERVATIONS)
        self.assertEqual(
            mailbox.observation_ids, ("telem-1", "telem-2", "telem-3", "telem-4")
        )
        self.assertEqual(mailbox.observation_ordinals, (2, 3, 4, 5))
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-0", ordinal=1, tick=600, lower=60 * MS)
            )

    def test_idempotent_reregistration_returns_same_ordinal(self):
        mailbox = ControlMailbox(binding=BINDING)
        item = observation()
        first = mailbox.register_sent_observation(item)
        second = mailbox.register_sent_observation(item)
        self.assertEqual(first, second)
        self.assertEqual(mailbox.observation_ids, ("telem-1",))

    def test_conflicting_reregistration_rejected(self):
        mailbox = mailbox_with(observation())
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(observation(ordinal=1, tick=200))

    def test_non_increasing_tick_rejected_as_sequence_wrap(self):
        mailbox = mailbox_with(observation())
        for tick in (100, 50):
            with self.subTest(tick=tick):
                with self.assertRaises(BrokerError):
                    mailbox.register_sent_observation(
                        observation("telem-2", ordinal=2, tick=tick)
                    )
        self.assertEqual(mailbox.observation_ids, ("telem-1",))

    def test_lower_bound_regression_rejected(self):
        mailbox = mailbox_with(observation(lower=50 * MS))
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-2", ordinal=2, tick=200, lower=40 * MS)
            )
        equal = mailbox.register_sent_observation(
            observation("telem-2", ordinal=2, tick=200, lower=50 * MS)
        )
        self.assertEqual(equal, 2)

    def test_register_validation(self):
        mailbox = ControlMailbox(binding=BINDING)
        bad_observations = (
            ObservationRef(
                observation_id="",
                sample_tick_ms=100,
                sample_time_lower_ns=0,
                sent_ordinal=1,
            ),
            ObservationRef(
                observation_id="x",
                sample_tick_ms=-1,
                sample_time_lower_ns=0,
                sent_ordinal=1,
            ),
            ObservationRef(
                observation_id="x",
                sample_tick_ms=True,
                sample_time_lower_ns=0,
                sent_ordinal=1,
            ),
            ObservationRef(
                observation_id="x",
                sample_tick_ms=100,
                sample_time_lower_ns=1.5,
                sent_ordinal=1,
            ),
            ObservationRef(
                observation_id="x",
                sample_tick_ms=100,
                sample_time_lower_ns=0,
                sent_ordinal=True,
            ),
            ObservationRef(
                observation_id="x",
                sample_tick_ms=100,
                sample_time_lower_ns=0,
                sent_ordinal=-1,
            ),
            ObservationRef(
                observation_id="x",
                sample_tick_ms=100,
                sample_time_lower_ns=0,
                sent_ordinal=1.5,
            ),
            ObservationRef(
                observation_id="x",
                sample_tick_ms=100,
                sample_time_lower_ns=0,
                sent_ordinal=2**64,
            ),
        )
        for bad in bad_observations:
            with self.subTest(bad=bad):
                with self.assertRaises(BrokerError):
                    mailbox.register_sent_observation(bad)
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation({"observation_id": "x"})
        with self.assertRaises(BrokerError):
            ControlMailbox(binding={"run_id": "r"})
        with self.assertRaises(BrokerError):
            BrokerBinding(
                run_id="r", session_id="s", profile="other_profile", epoch=0
            ).validate()
        with self.assertRaises(BrokerError):
            ControlMailbox(
                binding=BrokerBinding(
                    run_id="r", session_id="s", profile="unknown", epoch=0
                )
            )

    def test_more_than_1000_registrations_stay_constant_size(self):
        mailbox = ControlMailbox(binding=BINDING)
        for ordinal in range(1, 1002):
            mailbox.register_sent_observation(
                observation(
                    f"telem-{ordinal}",
                    ordinal=ordinal,
                    tick=100 * ordinal,
                    lower=ordinal * MS,
                )
            )
        self.assertEqual(mailbox.observation_ordinals, (998, 999, 1000, 1001))
        self.assertEqual(len(mailbox.observation_ordinals), MAX_SENT_OBSERVATIONS)
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-1", ordinal=1, tick=100, lower=0)
            )
        reused = mailbox.register_sent_observation(
            observation("telem-997", ordinal=1002, tick=100_200, lower=1002 * MS)
        )
        self.assertEqual(reused, 1002)
        self.assertIn("telem-997", mailbox.observation_ids)
        with self.assertRaises(BrokerError):
            mailbox.offer(
                candidate(
                    observation(
                        "telem-997", ordinal=997, tick=99_700, lower=997 * MS
                    )
                )
            )

    def test_id_reuse_after_eviction_requires_later_ordinal(self):
        old_obs = observation("telem-1", ordinal=1, tick=100, lower=0)
        mailbox = mailbox_with(
            old_obs,
            observation("telem-2", ordinal=2, tick=200, lower=10 * MS),
            observation("telem-3", ordinal=3, tick=300, lower=20 * MS),
            observation("telem-4", ordinal=4, tick=400, lower=30 * MS),
        )
        old_candidate = candidate(old_obs, completed=100 * MS)
        self.assertEqual(mailbox.offer(old_candidate), OFFER_ACCEPTED)
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-1", ordinal=9, tick=900, lower=40 * MS)
            )
        mailbox.register_sent_observation(
            observation("telem-5", ordinal=5, tick=500, lower=40 * MS)
        )
        reused = mailbox.register_sent_observation(
            observation("telem-1", ordinal=6, tick=600, lower=50 * MS)
        )
        self.assertEqual(reused, 6)
        self.assertEqual(
            mailbox.observation_ids,
            ("telem-3", "telem-4", "telem-5", "telem-1"),
        )
        self.assertEqual(mailbox.observation_ordinals, (3, 4, 5, 6))
        with self.assertRaises(BrokerError):
            mailbox.offer(old_candidate)
        result = mailbox.consume(
            consumed_at_ns=500 * MS,
            slot_deadline_ns=500 * MS,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(result.reason, CONSUME_OBSERVATION_EVICTED)
        self.assertIsNone(mailbox.pending)
        with self.assertRaises(BrokerError):
            mailbox.offer(old_candidate)

    def test_no_wrap_or_restart_within_binding(self):
        mailbox = mailbox_with(observation())
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-2", ordinal=1, tick=200, lower=10 * MS)
            )
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-3", ordinal=9, tick=50, lower=0)
            )
        for ordinal in range(2, 7):
            mailbox.register_sent_observation(
                observation(
                    f"telem-{ordinal}",
                    ordinal=ordinal,
                    tick=100 * ordinal,
                    lower=10 * MS * (ordinal - 1),
                )
            )
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-97", ordinal=2, tick=900, lower=90 * MS)
            )
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-98", ordinal=6, tick=900, lower=90 * MS)
            )

    def test_uint64_ordinal_bounds(self):
        mailbox = ControlMailbox(binding=BINDING)
        self.assertEqual(
            mailbox.register_sent_observation(
                observation("telem-0", ordinal=0, tick=0, lower=0)
            ),
            0,
        )
        self.assertEqual(
            mailbox.register_sent_observation(
                observation("telem-max", ordinal=2**64 - 1, tick=100, lower=0)
            ),
            2**64 - 1,
        )
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-over", ordinal=2**64, tick=200, lower=0)
            )
        with self.assertRaises(BrokerError):
            mailbox.register_sent_observation(
                observation("telem-wrap", ordinal=0, tick=200, lower=0)
            )


class OfferTests(unittest.TestCase):
    def test_absent_history_rejected(self):
        mailbox = ControlMailbox(binding=BINDING)
        with self.assertRaises(BrokerError):
            mailbox.offer(candidate(observation()))

    def test_observation_fields_must_match_registered(self):
        mailbox = mailbox_with(observation())
        forged = candidate(observation(tick=101))
        with self.assertRaises(BrokerError):
            mailbox.offer(forged)

    def test_binding_mismatch_rejected(self):
        mailbox = mailbox_with(observation())
        for mutation in (
            {"run_id": "other-run"},
            {"session_id": "other-session"},
            {"profile": "stress_300"},
            {"epoch": 4},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(BrokerError):
                    mailbox.offer(
                        candidate(observation(), binding=replace(BINDING, **mutation))
                    )

    def test_newer_lineage_wins_over_late_old_completion(self):
        first_obs = observation("telem-1", tick=100)
        second_obs = observation("telem-2", ordinal=2, tick=200, lower=100 * MS)
        mailbox = mailbox_with(first_obs, second_obs)
        older = candidate(first_obs, completed=500 * MS, payload=b"old")
        newer = candidate(second_obs, completed=100 * MS, payload=b"new")
        self.assertEqual(mailbox.offer(older), OFFER_ACCEPTED)
        self.assertEqual(mailbox.offer(newer), OFFER_ACCEPTED)
        self.assertIs(mailbox.pending, newer)
        late = candidate(first_obs, completed=900 * MS, payload=b"old")
        self.assertEqual(mailbox.offer(late), OFFER_STALE_IGNORED)
        self.assertIs(mailbox.pending, newer)

    def test_identical_duplicate_keeps_earliest_completion(self):
        item = observation()
        mailbox = mailbox_with(item)
        self.assertEqual(mailbox.offer(candidate(item, completed=500 * MS)), OFFER_ACCEPTED)
        later_copy = candidate(item, completed=800 * MS)
        self.assertEqual(mailbox.offer(later_copy), OFFER_DUPLICATE_IGNORED)
        self.assertEqual(mailbox.pending.completed_at_ns, 500 * MS)
        earlier_copy = candidate(item, completed=300 * MS)
        self.assertEqual(mailbox.offer(earlier_copy), OFFER_DUPLICATE_IGNORED)
        self.assertEqual(mailbox.pending.completed_at_ns, 300 * MS)

    def test_conflicting_duplicate_same_key_rejected(self):
        item = observation()
        mailbox = mailbox_with(item)
        self.assertEqual(mailbox.offer(candidate(item, payload=b"alpha")), OFFER_ACCEPTED)
        with self.assertRaises(BrokerError):
            mailbox.offer(candidate(item, payload=b"beta"))
        self.assertEqual(mailbox.pending.payload, b"alpha")

    def test_generation_ordinal_order_within_observation(self):
        item = observation()
        mailbox = mailbox_with(item)
        self.assertEqual(mailbox.offer(candidate(item, ordinal=1)), OFFER_ACCEPTED)
        second = candidate(item, ordinal=2, completed=50 * MS)
        self.assertEqual(mailbox.offer(second), OFFER_ACCEPTED)
        self.assertIs(mailbox.pending, second)
        regressed = candidate(item, ordinal=1, completed=500 * MS)
        self.assertEqual(mailbox.offer(regressed), OFFER_STALE_IGNORED)
        self.assertEqual(mailbox.pending.generation_ordinal, 2)

    def test_forged_candidate_inputs_rejected(self):
        item = observation()
        mailbox = mailbox_with(item)
        forged = (
            Candidate(
                binding=BINDING,
                observation=item,
                generation_ordinal=1,
                payload="payload",
                completed_at_ns=100 * MS,
            ),
            Candidate(
                binding=BINDING,
                observation=item,
                generation_ordinal=1,
                payload=b"",
                completed_at_ns=100 * MS,
            ),
            Candidate(
                binding=BINDING,
                observation=item,
                generation_ordinal=1,
                payload=b"payload",
                completed_at_ns=True,
            ),
            Candidate(
                binding=BINDING,
                observation=item,
                generation_ordinal=1,
                payload=b"payload",
                completed_at_ns=-1,
            ),
            Candidate(
                binding=BINDING,
                observation=item,
                generation_ordinal=-1,
                payload=b"payload",
                completed_at_ns=100 * MS,
            ),
            Candidate(
                binding=BINDING,
                observation=item,
                generation_ordinal=2.5,
                payload=b"payload",
                completed_at_ns=100 * MS,
            ),
            Candidate(
                binding=BINDING,
                observation={"observation_id": "telem-1"},
                generation_ordinal=1,
                payload=b"payload",
                completed_at_ns=100 * MS,
            ),
            Candidate(
                binding={"run_id": "r"},
                observation=item,
                generation_ordinal=1,
                payload=b"payload",
                completed_at_ns=100 * MS,
            ),
            Candidate(
                binding=BINDING,
                observation=observation("telem-9", ordinal=9, tick=900, lower=0),
                generation_ordinal=1,
                payload=b"payload",
                completed_at_ns=100 * MS,
            ),
        )
        for bad in forged:
            with self.subTest(bad=bad):
                with self.assertRaises(BrokerError):
                    mailbox.offer(bad)
        with self.assertRaises(BrokerError):
            mailbox.offer("not-a-candidate")


class ConsumptionTests(unittest.TestCase):
    def test_next_slot_handoff_150_250ms(self):
        item = observation()
        mailbox = mailbox_with(item)
        offered = candidate(item, completed=200 * MS)
        mailbox.offer(offered)
        first = mailbox.consume(
            consumed_at_ns=200 * MS, slot_deadline_ns=150 * MS, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(first.reason, CONSUME_COMPLETED_AFTER_SLOT_DEADLINE)
        self.assertIsNone(first.candidate)
        self.assertFalse(first.movement_authorized)
        self.assertIs(mailbox.pending, offered)
        second = mailbox.consume(
            consumed_at_ns=250 * MS, slot_deadline_ns=250 * MS, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(second.reason, CONSUME_OK)
        self.assertIs(second.candidate, offered)
        self.assertEqual(second.observation_age_ns, 250 * MS)
        self.assertFalse(second.movement_authorized)
        self.assertIsNone(mailbox.pending)
        third = mailbox.consume(
            consumed_at_ns=260 * MS, slot_deadline_ns=260 * MS, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(third.reason, CONSUME_EMPTY)
        self.assertIsNone(third.observation_age_ns)

    def test_completion_exactly_at_slot_deadline_is_ok(self):
        item = observation()
        mailbox = mailbox_with(item)
        offered = candidate(item, completed=150 * MS)
        mailbox.offer(offered)
        result = mailbox.consume(
            consumed_at_ns=200 * MS, slot_deadline_ns=150 * MS, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(result.reason, CONSUME_OK)
        self.assertIs(result.candidate, offered)

    def test_age_boundary_drops_candidate(self):
        item = observation()
        mailbox = mailbox_with(item)
        mailbox.offer(candidate(item))
        expired = mailbox.consume(
            consumed_at_ns=AGE_LIMIT, slot_deadline_ns=AGE_LIMIT, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(expired.reason, CONSUME_OBSERVATION_AGE_EXCEEDED)
        self.assertEqual(expired.observation_age_ns, AGE_LIMIT)
        self.assertIsNone(mailbox.pending)

        fresh_mailbox = mailbox_with(item)
        fresh_mailbox.offer(candidate(item))
        fresh = fresh_mailbox.consume(
            consumed_at_ns=AGE_LIMIT - 1,
            slot_deadline_ns=AGE_LIMIT,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(fresh.reason, CONSUME_OK)

    def test_age_is_measured_from_sample_lower_bound(self):
        item = observation(lower=500 * MS)
        mailbox = mailbox_with(item)
        mailbox.offer(candidate(item, completed=500 * MS))
        result = mailbox.consume(
            consumed_at_ns=SECOND, slot_deadline_ns=SECOND, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(result.reason, CONSUME_OK)
        self.assertEqual(result.observation_age_ns, 500 * MS)

    def test_consumed_time_before_sample_bound_rejected(self):
        item = observation(lower=500 * MS)
        mailbox = mailbox_with(item)
        mailbox.offer(candidate(item, completed=500 * MS))
        with self.assertRaises(BrokerError):
            mailbox.consume(
                consumed_at_ns=499 * MS,
                slot_deadline_ns=SECOND,
                age_limit_ns=AGE_LIMIT,
            )

    def test_evicted_observation_drops_pending(self):
        first_obs = observation("telem-1", tick=100)
        mailbox = mailbox_with(
            first_obs,
            observation("telem-2", ordinal=2, tick=200, lower=50 * MS),
            observation("telem-3", ordinal=3, tick=300, lower=100 * MS),
            observation("telem-4", ordinal=4, tick=400, lower=150 * MS),
        )
        mailbox.offer(candidate(first_obs, completed=100 * MS))
        mailbox.register_sent_observation(
            observation("telem-5", ordinal=5, tick=500, lower=200 * MS)
        )
        result = mailbox.consume(
            consumed_at_ns=500 * MS, slot_deadline_ns=500 * MS, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(result.reason, CONSUME_OBSERVATION_EVICTED)
        self.assertIsNone(result.candidate)
        self.assertIsNone(mailbox.pending)

    def test_empty_mailbox_consumes_nothing(self):
        mailbox = ControlMailbox(binding=BINDING)
        result = mailbox.consume(
            consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(result.reason, CONSUME_EMPTY)
        self.assertIsNone(result.candidate)
        self.assertIsNone(result.observation_age_ns)

    def test_consumption_is_never_movement_permission(self):
        default = Consumption(None, CONSUME_EMPTY, 0, 0, None)
        self.assertFalse(default.movement_authorized)
        params = set(inspect.signature(ControlMailbox.consume).parameters)
        self.assertFalse(any("ack" in name.lower() for name in params))
        item = observation()
        mailbox = mailbox_with(item)
        mailbox.offer(candidate(item))
        result = mailbox.consume(
            consumed_at_ns=100 * MS, slot_deadline_ns=100 * MS, age_limit_ns=AGE_LIMIT
        )
        self.assertEqual(result.reason, CONSUME_OK)
        self.assertFalse(result.movement_authorized)

    def test_consume_validation(self):
        mailbox = ControlMailbox(binding=BINDING)
        for bad in (True, 1.5, -1):
            with self.subTest(bad=bad):
                with self.assertRaises(BrokerError):
                    mailbox.consume(
                        consumed_at_ns=bad, slot_deadline_ns=0, age_limit_ns=AGE_LIMIT
                    )
                with self.assertRaises(BrokerError):
                    mailbox.consume(
                        consumed_at_ns=0, slot_deadline_ns=bad, age_limit_ns=AGE_LIMIT
                    )
                with self.assertRaises(BrokerError):
                    mailbox.consume(
                        consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=bad
                    )
        with self.assertRaises(BrokerError):
            mailbox.consume(consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=0)


    def test_b01_older_completion_after_consume_is_stale(self):
        first_obs = observation("telem-1", ordinal=1, tick=100)
        second_obs = observation("telem-2", ordinal=2, tick=200, lower=10 * MS)
        mailbox = mailbox_with(first_obs, second_obs)
        older = candidate(first_obs, completed=100 * MS, payload=b"old")
        newer = candidate(second_obs, completed=110 * MS, payload=b"new")
        self.assertEqual(mailbox.offer(older), OFFER_ACCEPTED)
        self.assertEqual(mailbox.offer(newer), OFFER_ACCEPTED)
        ok = mailbox.consume(
            consumed_at_ns=120 * MS,
            slot_deadline_ns=120 * MS,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(ok.reason, CONSUME_OK)
        self.assertIs(ok.candidate, newer)
        self.assertIsNone(mailbox.pending)
        late = candidate(first_obs, completed=130 * MS, payload=b"old")
        self.assertEqual(mailbox.offer(late), OFFER_STALE_IGNORED)
        self.assertIsNone(mailbox.pending)
        empty = mailbox.consume(
            consumed_at_ns=140 * MS,
            slot_deadline_ns=140 * MS,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(empty.reason, CONSUME_EMPTY)

    def test_b01_stale_older_completion_after_expiry_not_requeued(self):
        first_obs = observation("telem-1", ordinal=1, tick=100)
        second_obs = observation("telem-2", ordinal=2, tick=200)
        mailbox = mailbox_with(first_obs, second_obs)
        pending = candidate(second_obs, completed=100 * MS, payload=b"new")
        self.assertEqual(mailbox.offer(pending), OFFER_ACCEPTED)
        expired = mailbox.consume(
            consumed_at_ns=AGE_LIMIT,
            slot_deadline_ns=AGE_LIMIT,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(expired.reason, CONSUME_OBSERVATION_AGE_EXCEEDED)
        self.assertIsNone(mailbox.pending)
        late_old = candidate(first_obs, completed=100 * MS, payload=b"old")
        self.assertEqual(mailbox.offer(late_old), OFFER_STALE_IGNORED)
        same = candidate(second_obs, completed=100 * MS, payload=b"new")
        self.assertEqual(mailbox.offer(same), OFFER_DUPLICATE_IGNORED)
        self.assertIsNone(mailbox.pending)

    def test_high_water_persists_after_consume(self):
        item = observation()
        mailbox = mailbox_with(item)
        offered = candidate(item, completed=100 * MS)
        self.assertEqual(mailbox.offer(offered), OFFER_ACCEPTED)
        self.assertEqual(mailbox.high_water_key, (1, 1))
        self.assertEqual(mailbox.high_water_completed_at_ns, 100 * MS)
        self.assertEqual(mailbox.high_water_digest, offered.payload_digest)
        result = mailbox.consume(
            consumed_at_ns=100 * MS,
            slot_deadline_ns=100 * MS,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(result.reason, CONSUME_OK)
        self.assertIsNone(mailbox.pending)
        self.assertEqual(mailbox.high_water_key, (1, 1))
        self.assertEqual(mailbox.high_water_completed_at_ns, 100 * MS)
        redelivery = candidate(item, completed=120 * MS)
        self.assertEqual(mailbox.offer(redelivery), OFFER_DUPLICATE_IGNORED)
        self.assertIsNone(mailbox.pending)
        with self.assertRaises(BrokerError):
            mailbox.offer(candidate(item, payload=b"conflicting"))

    def test_b02_future_completion_rejected_and_retained(self):
        item = observation()
        mailbox = mailbox_with(item)
        self.assertEqual(
            mailbox.offer(candidate(item, completed=300 * MS)), OFFER_ACCEPTED
        )
        with self.assertRaises(BrokerError):
            mailbox.consume(
                consumed_at_ns=200 * MS,
                slot_deadline_ns=500 * MS,
                age_limit_ns=AGE_LIMIT,
            )
        self.assertIsNotNone(mailbox.pending)
        ok = mailbox.consume(
            consumed_at_ns=300 * MS,
            slot_deadline_ns=300 * MS,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(ok.reason, CONSUME_OK)

    def test_completion_before_sample_lower_rejected(self):
        item = observation(lower=500 * MS)
        mailbox = mailbox_with(item)
        with self.assertRaises(BrokerError):
            mailbox.offer(candidate(item, completed=499 * MS))
        self.assertIsNone(mailbox.pending)

    def test_higher_generation_is_new_without_age_renewal(self):
        item = observation()
        mailbox = mailbox_with(item)
        first = candidate(item, ordinal=1, completed=100 * MS, payload=b"gen-1")
        self.assertEqual(mailbox.offer(first), OFFER_ACCEPTED)
        consumed = mailbox.consume(
            consumed_at_ns=100 * MS,
            slot_deadline_ns=100 * MS,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(consumed.reason, CONSUME_OK)
        second = candidate(item, ordinal=2, completed=150 * MS, payload=b"gen-2")
        self.assertEqual(mailbox.offer(second), OFFER_ACCEPTED)
        self.assertEqual(mailbox.high_water_key, (1, 2))
        late = mailbox.consume(
            consumed_at_ns=AGE_LIMIT,
            slot_deadline_ns=AGE_LIMIT,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(late.reason, CONSUME_OBSERVATION_AGE_EXCEEDED)
        self.assertIsNone(mailbox.pending)


class CallerClockHighWaterTests(unittest.TestCase):
    """BR21: one constant-size last consumed-time high-water scalar."""

    def test_br21_regressed_clock_rejected_after_missed_slot(self):
        item = observation()
        mailbox = mailbox_with(item)
        offered = candidate(item, completed=200)
        self.assertEqual(mailbox.offer(offered), OFFER_ACCEPTED)
        missed = mailbox.consume(
            consumed_at_ns=500, slot_deadline_ns=100, age_limit_ns=1000
        )
        self.assertEqual(missed.reason, CONSUME_COMPLETED_AFTER_SLOT_DEADLINE)
        self.assertIs(mailbox.pending, offered)
        self.assertEqual(mailbox.last_consumed_now_ns, 500)
        with self.assertRaises(BrokerError):
            mailbox.consume(
                consumed_at_ns=300, slot_deadline_ns=300, age_limit_ns=1000
            )
        self.assertIs(mailbox.pending, offered)
        self.assertEqual(mailbox.high_water_key, (1, 1))
        equal = mailbox.consume(
            consumed_at_ns=500, slot_deadline_ns=500, age_limit_ns=1000
        )
        self.assertEqual(equal.reason, CONSUME_OK)
        self.assertIs(equal.candidate, offered)

    def test_empty_consume_establishes_clock_before_offer(self):
        mailbox = ControlMailbox(binding=BINDING)
        self.assertIsNone(mailbox.last_consumed_now_ns)
        empty = mailbox.consume(
            consumed_at_ns=500, slot_deadline_ns=0, age_limit_ns=1000
        )
        self.assertEqual(empty.reason, CONSUME_EMPTY)
        self.assertEqual(mailbox.last_consumed_now_ns, 500)
        item = observation()
        mailbox.register_sent_observation(item)
        offered = candidate(item, completed=200)
        self.assertEqual(mailbox.offer(offered), OFFER_ACCEPTED)
        with self.assertRaises(BrokerError):
            mailbox.consume(
                consumed_at_ns=300, slot_deadline_ns=300, age_limit_ns=1000
            )
        self.assertIs(mailbox.pending, offered)

    def test_expiry_then_higher_generation_regressed_clock_rejected(self):
        item = observation()
        mailbox = mailbox_with(item)
        self.assertEqual(
            mailbox.offer(candidate(item, ordinal=1, completed=100 * MS)),
            OFFER_ACCEPTED,
        )
        expired = mailbox.consume(
            consumed_at_ns=AGE_LIMIT,
            slot_deadline_ns=AGE_LIMIT,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(expired.reason, CONSUME_OBSERVATION_AGE_EXCEEDED)
        second = candidate(item, ordinal=2, completed=200 * MS, payload=b"gen-2")
        self.assertEqual(mailbox.offer(second), OFFER_ACCEPTED)
        with self.assertRaises(BrokerError):
            mailbox.consume(
                consumed_at_ns=AGE_LIMIT - 1,
                slot_deadline_ns=AGE_LIMIT,
                age_limit_ns=AGE_LIMIT,
            )
        self.assertIs(mailbox.pending, second)
        self.assertEqual(mailbox.high_water_key, (1, 2))
        aged = mailbox.consume(
            consumed_at_ns=AGE_LIMIT,
            slot_deadline_ns=AGE_LIMIT,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(aged.reason, CONSUME_OBSERVATION_AGE_EXCEEDED)
        self.assertIsNone(mailbox.pending)

    def test_future_completion_retries_at_equal_or_later_clock_only(self):
        item = observation()
        mailbox = mailbox_with(item)
        offered = candidate(item, completed=300 * MS)
        self.assertEqual(mailbox.offer(offered), OFFER_ACCEPTED)
        with self.assertRaises(BrokerError):
            mailbox.consume(
                consumed_at_ns=200 * MS,
                slot_deadline_ns=500 * MS,
                age_limit_ns=AGE_LIMIT,
            )
        self.assertEqual(mailbox.last_consumed_now_ns, 200 * MS)
        with self.assertRaises(BrokerError):
            mailbox.consume(
                consumed_at_ns=199 * MS,
                slot_deadline_ns=500 * MS,
                age_limit_ns=AGE_LIMIT,
            )
        self.assertIs(mailbox.pending, offered)
        ok = mailbox.consume(
            consumed_at_ns=300 * MS,
            slot_deadline_ns=300 * MS,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(ok.reason, CONSUME_OK)
        self.assertIs(ok.candidate, offered)

    def test_malformed_arguments_never_advance_the_clock(self):
        mailbox = ControlMailbox(binding=BINDING)
        first = mailbox.consume(
            consumed_at_ns=500, slot_deadline_ns=0, age_limit_ns=1000
        )
        self.assertEqual(first.reason, CONSUME_EMPTY)
        malformed = (
            {"consumed_at_ns": 600, "slot_deadline_ns": -1, "age_limit_ns": 1000},
            {"consumed_at_ns": 600, "slot_deadline_ns": 0, "age_limit_ns": True},
            {"consumed_at_ns": 600, "slot_deadline_ns": 0, "age_limit_ns": 1.5},
            {"consumed_at_ns": 600, "slot_deadline_ns": 0, "age_limit_ns": 0},
            {
                "consumed_at_ns": 600,
                "slot_deadline_ns": 0,
                "age_limit_ns": 10 * SECOND,
            },
            {"consumed_at_ns": True, "slot_deadline_ns": 0, "age_limit_ns": 1000},
            {"consumed_at_ns": 1.5, "slot_deadline_ns": 0, "age_limit_ns": 1000},
            {"consumed_at_ns": -1, "slot_deadline_ns": 0, "age_limit_ns": 1000},
        )
        for args in malformed:
            with self.subTest(args=args):
                with self.assertRaises(BrokerError):
                    mailbox.consume(**args)
        self.assertEqual(mailbox.last_consumed_now_ns, 500)
        legal = mailbox.consume(
            consumed_at_ns=599, slot_deadline_ns=0, age_limit_ns=1000
        )
        self.assertEqual(legal.reason, CONSUME_EMPTY)
        self.assertEqual(mailbox.last_consumed_now_ns, 599)

    def test_high_water_scalar_is_constant_size_and_per_binding(self):
        mailbox = ControlMailbox(binding=BINDING)
        for now in (100, 200, 300):
            mailbox.consume(
                consumed_at_ns=now, slot_deadline_ns=0, age_limit_ns=1000
            )
        self.assertEqual(mailbox.last_consumed_now_ns, 300)
        self.assertIsInstance(mailbox.last_consumed_now_ns, int)
        self.assertIsNone(ControlMailbox(binding=BINDING).last_consumed_now_ns)
        self.assertIsNone(
            ControlMailbox(binding=STRESS_BINDING).last_consumed_now_ns
        )


class CallerAgeCapBoundTests(unittest.TestCase):
    """BR22: the frozen profile age cap is a hard upper bound for consumption."""

    def test_br22_oversized_caller_cap_rejected_even_empty(self):
        item = observation()
        mailbox = mailbox_with(item)
        offered = candidate(item, completed=100 * MS)
        self.assertEqual(mailbox.offer(offered), OFFER_ACCEPTED)
        with self.assertRaises(BrokerError):
            mailbox.consume(
                consumed_at_ns=2 * SECOND,
                slot_deadline_ns=2 * SECOND,
                age_limit_ns=10 * SECOND,
            )
        self.assertIs(mailbox.pending, offered)
        self.assertIsNone(mailbox.last_consumed_now_ns)
        empty = ControlMailbox(binding=BINDING)
        with self.assertRaises(BrokerError):
            empty.consume(
                consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=10 * SECOND
            )
        self.assertEqual(
            empty.consume(
                consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=FAST_CAP
            ).reason,
            CONSUME_EMPTY,
        )

    def test_cap_boundary_both_profiles(self):
        fast = ControlMailbox(binding=BINDING)
        self.assertEqual(
            fast.consume(
                consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=FAST_CAP
            ).reason,
            CONSUME_EMPTY,
        )
        with self.assertRaises(BrokerError):
            fast.consume(
                consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=FAST_CAP + 1
            )
        stress = ControlMailbox(binding=STRESS_BINDING)
        self.assertEqual(
            stress.consume(
                consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=STRESS_CAP
            ).reason,
            CONSUME_EMPTY,
        )
        with self.assertRaises(BrokerError):
            stress.consume(
                consumed_at_ns=0,
                slot_deadline_ns=0,
                age_limit_ns=STRESS_CAP + 1,
            )

    def test_stress_profile_allows_larger_legal_caller_cap(self):
        item = observation()
        mailbox = ControlMailbox(binding=STRESS_BINDING)
        mailbox.register_sent_observation(item)
        offered = candidate(item, completed=500 * MS, binding=STRESS_BINDING)
        self.assertEqual(mailbox.offer(offered), OFFER_ACCEPTED)
        ok = mailbox.consume(
            consumed_at_ns=2 * SECOND,
            slot_deadline_ns=2 * SECOND,
            age_limit_ns=10 * SECOND,
        )
        self.assertEqual(ok.reason, CONSUME_OK)
        self.assertIs(ok.candidate, offered)
        self.assertEqual(ok.observation_age_ns, 2 * SECOND)

    def test_stricter_caller_budget_and_exact_expiry(self):
        item = observation()
        early_mailbox = mailbox_with(item)
        early_mailbox.offer(candidate(item, completed=100 * MS))
        early = early_mailbox.consume(
            consumed_at_ns=SECOND - 1,
            slot_deadline_ns=SECOND,
            age_limit_ns=SECOND,
        )
        self.assertEqual(early.reason, CONSUME_OK)
        self.assertEqual(early.observation_age_ns, SECOND - 1)
        exact_mailbox = mailbox_with(item)
        exact_mailbox.offer(candidate(item, completed=100 * MS))
        expired = exact_mailbox.consume(
            consumed_at_ns=SECOND,
            slot_deadline_ns=SECOND,
            age_limit_ns=SECOND,
        )
        self.assertEqual(expired.reason, CONSUME_OBSERVATION_AGE_EXCEEDED)
        self.assertEqual(expired.observation_age_ns, SECOND)
        wider_mailbox = mailbox_with(item)
        wider_mailbox.offer(candidate(item, completed=100 * MS))
        with self.assertRaises(BrokerError):
            wider_mailbox.consume(
                consumed_at_ns=SECOND,
                slot_deadline_ns=SECOND,
                age_limit_ns=AGE_LIMIT + 1,
            )
        self.assertIsNone(wider_mailbox.last_consumed_now_ns)
        ok = wider_mailbox.consume(
            consumed_at_ns=SECOND - 1,
            slot_deadline_ns=SECOND,
            age_limit_ns=AGE_LIMIT,
        )
        self.assertEqual(ok.reason, CONSUME_OK)

    def test_malformed_caps_rejected_without_state_change(self):
        mailbox = ControlMailbox(binding=BINDING)
        for bad in (0, True, 1.5, -1, "9000"):
            with self.subTest(bad=bad):
                with self.assertRaises(BrokerError):
                    mailbox.consume(
                        consumed_at_ns=0, slot_deadline_ns=0, age_limit_ns=bad
                    )
        self.assertIsNone(mailbox.last_consumed_now_ns)


if __name__ == "__main__":
    unittest.main()

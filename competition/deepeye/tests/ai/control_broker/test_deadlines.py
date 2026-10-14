"""Independent tests for ai_pc.control_broker.deadlines (C05 foundation).

Software fixtures only: caller-supplied integer monotonic nanoseconds, no
clock, board, network or world I/O.  Coverage: profile caps, first-ACK-lost
bound, 150/250 ms receipt terms, late-ACK 8 s with original 12 s TTL and
lost STATE/EVENT, FAST 3 s analogue, unknown clock/USB bounds stopping,
age/previous-deadline terms, negative subtraction, deadline boundary and
forged-input rejection, future sample lower bounds (B04 regression), frozen
exported profile limits, LeaseDeadline self-validation and the mode-scoped
audit term contract (BR23: mandatory/optional term names per mode; unknown,
cross-mode, duplicate and missing names rejected).
"""

import re
import sys
import unittest
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from ai_pc.control_broker.deadlines import (  # noqa: E402
    BrokerError,
    HIL_MODE,
    PC_DIRECT_MODE,
    PROFILE_LIMITS,
    LeaseDeadline,
    hil_deadline,
    pc_direct_deadline,
    profile_limits,
)

SECOND = 1_000_000_000
MS = 1_000_000
FAST = "fast_9600"
STRESS = "stress_300"
FAST_TTL = 3 * SECOND
FAST_AGE = 1_500 * MS
STRESS_TTL = 12 * SECOND
STRESS_AGE = 12 * SECOND


def receipt_bounds(remaining, *, serialized=SECOND, usb=5 * MS, clock=2 * MS):
    return {
        "current_remaining_ttl_ns": remaining,
        "serialized_frame_duration_ns": serialized,
        "usb_processing_upper_bound_ns": usb,
        "clock_error_upper_bound_ns": clock,
    }


def hil(**overrides):
    kwargs = {
        "first_send_ns": 0,
        "original_ttl_ns": STRESS_TTL,
        "referenced_sample_time_lower_ns": 0,
        "profile": STRESS,
    }
    kwargs.update(overrides)
    return hil_deadline(**kwargs)


def term(decision, label):
    return dict(decision.terms_ns)[label]


class ProfileAndModeTests(unittest.TestCase):
    def test_profile_caps_are_frozen(self):
        self.assertEqual(profile_limits(FAST).max_ttl_ns, FAST_TTL)
        self.assertEqual(profile_limits(FAST).observation_age_limit_ns, FAST_AGE)
        self.assertEqual(profile_limits(STRESS).max_ttl_ns, STRESS_TTL)
        self.assertEqual(profile_limits(STRESS).observation_age_limit_ns, STRESS_AGE)
        self.assertEqual(set(PROFILE_LIMITS), {FAST, STRESS})

    def test_unknown_profile_stops(self):
        for profile in ("unknown_profile", "", 7, None, True):
            with self.subTest(profile=profile):
                with self.assertRaises(BrokerError):
                    profile_limits(profile)
                with self.assertRaises(BrokerError):
                    hil(profile=profile)
                with self.assertRaises(BrokerError):
                    pc_direct_deadline(
                        first_host_issue_ns=0,
                        requested_duration_ns=SECOND,
                        referenced_sample_time_lower_ns=0,
                        profile=profile,
                    )


class HilDeadlineTests(unittest.TestCase):
    def test_first_ack_lost_bounded_by_first_send_plus_ttl(self):
        decision = hil()
        self.assertEqual(decision.mode, HIL_MODE)
        self.assertFalse(decision.must_stop)
        self.assertEqual(decision.deadline_ns, STRESS_TTL)
        self.assertEqual(term(decision, "first_send_plus_original_ttl"), STRESS_TTL)
        self.assertFalse(decision.expired_at(STRESS_TTL - 1))
        self.assertTrue(decision.expired_at(STRESS_TTL))

    def test_receipt_term_150ms(self):
        decision = hil(
            first_send_ns=0,
            receipt_ns=0,
            **receipt_bounds(
                200 * MS, serialized=40 * MS, usb=8 * MS, clock=2 * MS
            ),
        )
        self.assertEqual(decision.deadline_ns, 150 * MS)
        self.assertEqual(term(decision, "receipt_plus_remaining_budget"), 150 * MS)
        self.assertFalse(decision.expired_at(150 * MS - 1))
        self.assertTrue(decision.expired_at(150 * MS))

    def test_receipt_term_250ms(self):
        decision = hil(
            first_send_ns=0,
            receipt_ns=0,
            **receipt_bounds(
                300 * MS, serialized=40 * MS, usb=8 * MS, clock=2 * MS
            ),
        )
        self.assertEqual(decision.deadline_ns, 250 * MS)
        self.assertEqual(term(decision, "receipt_plus_remaining_budget"), 250 * MS)

    def test_late_ack_8s_original_ttl_12s_stale_replay_never_extends(self):
        decision = hil(
            first_send_ns=0,
            receipt_ns=8 * SECOND,
            **receipt_bounds(STRESS_TTL),
        )
        self.assertEqual(decision.deadline_ns, STRESS_TTL)
        retried = hil(
            first_send_ns=0,
            receipt_ns=8 * SECOND + 500 * MS,
            previous_deadline_ns=decision.deadline_ns,
            **receipt_bounds(STRESS_TTL),
        )
        self.assertEqual(retried.deadline_ns, STRESS_TTL)
        self.assertTrue(retried.expired_at(STRESS_TTL))

    def test_late_ack_8s_reduced_remaining_stops_earlier(self):
        decision = hil(first_send_ns=0, receipt_ns=8 * SECOND, **receipt_bounds(4 * SECOND))
        self.assertEqual(decision.deadline_ns, 8 * SECOND + 2_993 * MS)
        self.assertLess(decision.deadline_ns, STRESS_TTL)
        self.assertTrue(decision.expired_at(8 * SECOND + 2_993 * MS))
        self.assertFalse(decision.expired_at(8 * SECOND + 2_992 * MS))

    def test_late_ack_with_state_event_lost_stops(self):
        decision = hil(
            first_send_ns=0,
            receipt_ns=8 * SECOND,
            current_remaining_ttl_ns=None,
            serialized_frame_duration_ns=SECOND,
            usb_processing_upper_bound_ns=5 * MS,
            clock_error_upper_bound_ns=2 * MS,
        )
        self.assertTrue(decision.must_stop)
        self.assertIsNone(decision.deadline_ns)
        self.assertIn("current_remaining_ttl_ns", decision.stop_reason)
        self.assertTrue(decision.expired_at(0))
        self.assertTrue(decision.expired_at(STRESS_TTL))
        self.assertEqual(decision.terms_ns, ())

    def test_fast_analogue_3s_ttl(self):
        replay = hil(
            first_send_ns=2 * SECOND,
            original_ttl_ns=FAST_TTL,
            profile=FAST,
            referenced_sample_time_lower_ns=2 * SECOND,
            receipt_ns=2 * SECOND,
            **receipt_bounds(
                FAST_TTL, serialized=33 * MS, usb=3 * MS, clock=1 * MS
            ),
        )
        self.assertEqual(replay.deadline_ns, 2 * SECOND + FAST_AGE)
        self.assertLess(replay.deadline_ns, 2 * SECOND + FAST_TTL)
        self.assertTrue(replay.expired_at(2 * SECOND + FAST_AGE))
        self.assertFalse(replay.expired_at(2 * SECOND + FAST_AGE - 1))
        reduced = hil(
            first_send_ns=2 * SECOND,
            original_ttl_ns=FAST_TTL,
            profile=FAST,
            referenced_sample_time_lower_ns=2 * SECOND,
            receipt_ns=2 * SECOND,
            **receipt_bounds(
                SECOND, serialized=33 * MS, usb=3 * MS, clock=1 * MS
            ),
        )
        self.assertEqual(reduced.deadline_ns, 2 * SECOND + 963 * MS)
        self.assertLess(reduced.deadline_ns, FAST_TTL)

    def test_unknown_usb_clock_or_serialization_bound_stops(self):
        cases = {
            "usb_processing_upper_bound_ns": {
                "serialized_frame_duration_ns": SECOND,
                "clock_error_upper_bound_ns": 2 * MS,
            },
            "clock_error_upper_bound_ns": {
                "serialized_frame_duration_ns": SECOND,
                "usb_processing_upper_bound_ns": 5 * MS,
            },
            "serialized_frame_duration_ns": {
                "usb_processing_upper_bound_ns": 5 * MS,
                "clock_error_upper_bound_ns": 2 * MS,
            },
        }
        for missing, provided in cases.items():
            with self.subTest(missing=missing):
                decision = hil(
                    receipt_ns=SECOND,
                    current_remaining_ttl_ns=4 * SECOND,
                    **provided,
                )
                self.assertTrue(decision.must_stop)
                self.assertIsNone(decision.deadline_ns)
                self.assertIn(missing, decision.stop_reason)
                self.assertTrue(decision.expired_at(0))

    def test_receipt_absent_with_bounds_rejected(self):
        with self.assertRaises(BrokerError):
            hil(current_remaining_ttl_ns=SECOND)
        with self.assertRaises(BrokerError):
            hil(serialized_frame_duration_ns=SECOND)

    def test_age_term_binds_for_fast_profile(self):
        decision = hil(
            original_ttl_ns=FAST_TTL,
            profile=FAST,
            referenced_sample_time_lower_ns=0,
            receipt_ns=0,
            **receipt_bounds(
                FAST_TTL, serialized=33 * MS, usb=3 * MS, clock=1 * MS
            ),
        )
        self.assertEqual(decision.deadline_ns, FAST_AGE)
        self.assertEqual(term(decision, "sample_lower_plus_age_limit"), FAST_AGE)

    def test_previous_deadline_chain_cannot_extend(self):
        first = hil(
            receipt_ns=0,
            **receipt_bounds(STRESS_TTL),
        )
        self.assertEqual(first.deadline_ns, 10_993 * MS)
        retried = hil(
            previous_deadline_ns=first.deadline_ns,
            receipt_ns=SECOND,
            **receipt_bounds(11 * SECOND),
        )
        self.assertEqual(retried.deadline_ns, first.deadline_ns)
        capped = hil(previous_deadline_ns=5 * SECOND, receipt_ns=0, **receipt_bounds(STRESS_TTL))
        self.assertEqual(capped.deadline_ns, 5 * SECOND)

    def test_negative_delay_subtraction_yields_immediate_stop(self):
        decision = hil(
            receipt_ns=10 * MS,
            **receipt_bounds(50 * MS, serialized=100 * MS, usb=0, clock=0),
        )
        self.assertEqual(term(decision, "receipt_plus_remaining_budget"), 10 * MS)
        self.assertEqual(decision.deadline_ns, 10 * MS)
        self.assertFalse(decision.expired_at(10 * MS - 1))
        self.assertTrue(decision.expired_at(10 * MS))


class InputValidationTests(unittest.TestCase):
    def test_numeric_inputs_reject_bool_float_and_negative(self):
        for bad in (True, 1.5, -1):
            with self.subTest(bad=bad):
                with self.assertRaises(BrokerError):
                    hil(first_send_ns=bad)
                with self.assertRaises(BrokerError):
                    hil(original_ttl_ns=bad)
                with self.assertRaises(BrokerError):
                    hil(referenced_sample_time_lower_ns=bad)
                with self.assertRaises(BrokerError):
                    hil(receipt_ns=bad, **receipt_bounds(4 * SECOND))
                with self.assertRaises(BrokerError):
                    hil(
                        receipt_ns=0,
                        current_remaining_ttl_ns=bad,
                        serialized_frame_duration_ns=0,
                        usb_processing_upper_bound_ns=0,
                        clock_error_upper_bound_ns=0,
                    )
                with self.assertRaises(BrokerError):
                    hil(
                        receipt_ns=0,
                        current_remaining_ttl_ns=SECOND,
                        serialized_frame_duration_ns=bad,
                        usb_processing_upper_bound_ns=0,
                        clock_error_upper_bound_ns=0,
                    )
                with self.assertRaises(BrokerError):
                    hil(
                        receipt_ns=0,
                        current_remaining_ttl_ns=SECOND,
                        serialized_frame_duration_ns=0,
                        usb_processing_upper_bound_ns=bad,
                        clock_error_upper_bound_ns=0,
                    )
                with self.assertRaises(BrokerError):
                    hil(
                        receipt_ns=0,
                        current_remaining_ttl_ns=SECOND,
                        serialized_frame_duration_ns=0,
                        usb_processing_upper_bound_ns=0,
                        clock_error_upper_bound_ns=bad,
                    )
                with self.assertRaises(BrokerError):
                    hil(previous_deadline_ns=bad)

    def test_profile_caps_are_enforced(self):
        with self.assertRaises(BrokerError):
            hil(original_ttl_ns=STRESS_TTL + 1)
        with self.assertRaises(BrokerError):
            hil(original_ttl_ns=FAST_TTL + 1, profile=FAST)
        allowed = hil(original_ttl_ns=STRESS_TTL)
        self.assertEqual(allowed.deadline_ns, STRESS_TTL)
        with self.assertRaises(BrokerError):
            hil(
                receipt_ns=0,
                current_remaining_ttl_ns=STRESS_TTL + 1,
                serialized_frame_duration_ns=0,
                usb_processing_upper_bound_ns=0,
                clock_error_upper_bound_ns=0,
            )

    def test_receipt_must_not_precede_first_send(self):
        with self.assertRaises(BrokerError):
            hil(first_send_ns=SECOND, receipt_ns=SECOND - 1, **receipt_bounds(4 * SECOND))
        allowed = hil(first_send_ns=SECOND, receipt_ns=SECOND, **receipt_bounds(4 * SECOND))
        self.assertFalse(allowed.must_stop)

    def test_expired_at_rejects_bad_now(self):
        decision = hil()
        for bad in (True, 1.5, -1):
            with self.subTest(bad=bad):
                with self.assertRaises(BrokerError):
                    decision.expired_at(bad)


class PcDirectTests(unittest.TestCase):
    def test_pc_direct_min_terms_and_mode(self):
        decision = pc_direct_deadline(
            first_host_issue_ns=SECOND,
            requested_duration_ns=2 * SECOND,
            referenced_sample_time_lower_ns=0,
            profile=STRESS,
        )
        self.assertEqual(decision.mode, PC_DIRECT_MODE)
        self.assertEqual(decision.deadline_ns, 3 * SECOND)
        self.assertEqual(
            term(decision, "first_host_issue_plus_requested_duration"), 3 * SECOND
        )

    def test_pc_direct_age_term_and_previous_deadline(self):
        aged = pc_direct_deadline(
            first_host_issue_ns=0,
            requested_duration_ns=FAST_TTL,
            referenced_sample_time_lower_ns=0,
            profile=FAST,
        )
        self.assertEqual(aged.deadline_ns, FAST_AGE)
        capped = pc_direct_deadline(
            first_host_issue_ns=0,
            requested_duration_ns=FAST_TTL,
            referenced_sample_time_lower_ns=0,
            profile=FAST,
            previous_deadline_ns=SECOND,
        )
        self.assertEqual(capped.deadline_ns, SECOND)

    def test_pc_direct_zero_duration_stops_immediately(self):
        decision = pc_direct_deadline(
            first_host_issue_ns=5 * MS,
            requested_duration_ns=0,
            referenced_sample_time_lower_ns=0,
            profile=FAST,
        )
        self.assertEqual(decision.deadline_ns, 5 * MS)
        self.assertTrue(decision.expired_at(5 * MS))
        self.assertFalse(decision.expired_at(5 * MS - 1))

    def test_pc_direct_needs_no_motion_ack(self):
        import inspect

        params = set(inspect.signature(pc_direct_deadline).parameters)
        self.assertFalse(any("ack" in name.lower() for name in params))
        decision = pc_direct_deadline(
            first_host_issue_ns=0,
            requested_duration_ns=SECOND,
            referenced_sample_time_lower_ns=0,
            profile=FAST,
        )
        self.assertFalse(decision.must_stop)
        self.assertIsNotNone(decision.deadline_ns)

    def test_pc_direct_caps_and_validation(self):
        allowed = pc_direct_deadline(
            first_host_issue_ns=0,
            requested_duration_ns=STRESS_TTL,
            referenced_sample_time_lower_ns=0,
            profile=STRESS,
        )
        self.assertEqual(allowed.terms_ns[0][1], STRESS_TTL)
        with self.assertRaises(BrokerError):
            pc_direct_deadline(
                first_host_issue_ns=0,
                requested_duration_ns=STRESS_TTL + 1,
                referenced_sample_time_lower_ns=0,
                profile=STRESS,
            )
        for bad in (True, 1.5, -1):
            with self.subTest(bad=bad):
                with self.assertRaises(BrokerError):
                    pc_direct_deadline(
                        first_host_issue_ns=bad,
                        requested_duration_ns=SECOND,
                        referenced_sample_time_lower_ns=0,
                        profile=STRESS,
                    )
                with self.assertRaises(BrokerError):
                    pc_direct_deadline(
                        first_host_issue_ns=0,
                        requested_duration_ns=bad,
                        referenced_sample_time_lower_ns=0,
                        profile=STRESS,
                    )
                with self.assertRaises(BrokerError):
                    pc_direct_deadline(
                        first_host_issue_ns=0,
                        requested_duration_ns=SECOND,
                        referenced_sample_time_lower_ns=0,
                        profile=STRESS,
                        previous_deadline_ns=bad,
                    )


class FutureSampleLowerTests(unittest.TestCase):
    def test_hil_rejects_sample_lower_after_first_send(self):
        with self.assertRaises(BrokerError):
            hil(first_send_ns=SECOND, referenced_sample_time_lower_ns=SECOND + 1)
        boundary = hil(
            first_send_ns=SECOND, referenced_sample_time_lower_ns=SECOND
        )
        self.assertFalse(boundary.must_stop)

    def test_b04_pc_direct_future_sample_lower_now_rejected(self):
        with self.assertRaises(BrokerError):
            pc_direct_deadline(
                first_host_issue_ns=0,
                requested_duration_ns=SECOND,
                referenced_sample_time_lower_ns=SECOND,
                profile=FAST,
            )
        boundary = pc_direct_deadline(
            first_host_issue_ns=SECOND,
            requested_duration_ns=SECOND,
            referenced_sample_time_lower_ns=SECOND,
            profile=FAST,
        )
        self.assertEqual(boundary.deadline_ns, 2 * SECOND)


class FrozenLimitsTests(unittest.TestCase):
    def test_profile_limits_mapping_is_read_only(self):
        with self.assertRaises(TypeError):
            PROFILE_LIMITS[FAST] = None
        with self.assertRaises(TypeError):
            PROFILE_LIMITS["new_profile"] = None
        with self.assertRaises(TypeError):
            del PROFILE_LIMITS[FAST]
        self.assertEqual(set(PROFILE_LIMITS), {FAST, STRESS})

    def test_profile_limits_values_are_frozen(self):
        limits = profile_limits(FAST)
        with self.assertRaises(AttributeError):
            limits.max_ttl_ns = 1
        with self.assertRaises(AttributeError):
            limits.observation_age_limit_ns = 1


class LeaseDeadlineValidationTests(unittest.TestCase):
    def test_valid_manual_constructions(self):
        stop = LeaseDeadline(
            mode=HIL_MODE,
            deadline_ns=None,
            must_stop=True,
            stop_reason="unknown_bounds:current_remaining_ttl_ns",
            terms_ns=(),
        )
        self.assertTrue(stop.expired_at(0))
        self.assertTrue(stop.expired_at(STRESS_TTL))
        ok = LeaseDeadline(
            mode=PC_DIRECT_MODE,
            deadline_ns=5,
            must_stop=False,
            stop_reason=None,
            terms_ns=(
                ("first_host_issue_plus_requested_duration", 7),
                ("sample_lower_plus_age_limit", 5),
            ),
        )
        self.assertFalse(ok.expired_at(4))
        self.assertTrue(ok.expired_at(5))
        full_hil = LeaseDeadline(
            mode=HIL_MODE,
            deadline_ns=3,
            must_stop=False,
            stop_reason=None,
            terms_ns=(
                ("first_send_plus_original_ttl", 9),
                ("receipt_plus_remaining_budget", 3),
                ("sample_lower_plus_age_limit", 4),
                ("previous_deadline", 8),
            ),
        )
        self.assertTrue(full_hil.expired_at(3))
        pc_chained = LeaseDeadline(
            mode=PC_DIRECT_MODE,
            deadline_ns=1,
            must_stop=False,
            stop_reason=None,
            terms_ns=(
                ("first_host_issue_plus_requested_duration", 6),
                ("sample_lower_plus_age_limit", 2),
                ("previous_deadline", 1),
            ),
        )
        self.assertTrue(pc_chained.expired_at(1))

    def test_malformed_constructions_rejected(self):
        base = {
            "mode": HIL_MODE,
            "deadline_ns": 1,
            "must_stop": False,
            "stop_reason": None,
            "terms_ns": (
                ("first_send_plus_original_ttl", 1),
                ("sample_lower_plus_age_limit", 1),
            ),
        }
        cases = [
            {**base, "mode": "UNKNOWN_MODE"},
            {**base, "deadline_ns": None},
            {**base, "deadline_ns": True},
            {**base, "deadline_ns": -1},
            {**base, "deadline_ns": 1.5},
            {**base, "must_stop": "no"},
            {**base, "stop_reason": "should not be here"},
            {**base, "terms_ns": ()},
            {**base, "terms_ns": [("first_send_plus_original_ttl", 1)]},
            {
                **base,
                "terms_ns": (
                    ("first_send_plus_original_ttl", 2),
                    ("sample_lower_plus_age_limit", 2),
                ),
            },
            {
                **base,
                "terms_ns": (
                    ("sample_lower_plus_age_limit", True),
                    ("first_send_plus_original_ttl", 1),
                ),
            },
            {
                **base,
                "terms_ns": (
                    ("first_send_plus_original_ttl", -1),
                    ("sample_lower_plus_age_limit", 1),
                ),
            },
            {**base, "terms_ns": (("", 1),)},
            {
                **base,
                "terms_ns": (
                    ("first_send_plus_original_ttl", 1),
                    ("first_send_plus_original_ttl", 1),
                ),
            },
            {**base, "terms_ns": (("first_send_plus_original_ttl",),)},
            {**base, "terms_ns": (["first_send_plus_original_ttl", 1],)},
            {
                "mode": HIL_MODE,
                "deadline_ns": 1,
                "must_stop": True,
                "stop_reason": "x",
                "terms_ns": (),
            },
            {
                "mode": HIL_MODE,
                "deadline_ns": None,
                "must_stop": True,
                "stop_reason": "",
                "terms_ns": (),
            },
            {
                "mode": HIL_MODE,
                "deadline_ns": None,
                "must_stop": True,
                "stop_reason": "x",
                "terms_ns": (("term", 1),),
            },
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(BrokerError):
                    LeaseDeadline(**case)

    def test_expired_at_revalidates_mutated_instance(self):
        decision = hil()
        object.__setattr__(decision, "deadline_ns", None)
        with self.assertRaises(BrokerError):
            decision.expired_at(0)
        stop = hil(
            receipt_ns=0,
            current_remaining_ttl_ns=None,
            serialized_frame_duration_ns=SECOND,
            usb_processing_upper_bound_ns=5 * MS,
            clock_error_upper_bound_ns=2 * MS,
        )
        object.__setattr__(stop, "must_stop", False)
        with self.assertRaises(BrokerError):
            stop.expired_at(0)

    def test_br23_unknown_crossmode_and_missing_names_rejected(self):
        cases = (
            {
                "mode": HIL_MODE,
                "deadline_ns": 1,
                "must_stop": False,
                "stop_reason": None,
                "terms_ns": (
                    ("first_send_plus_original_ttl", 1),
                    ("sample_lower_plus_age_limit", 1),
                    ("audit_label_alpha", 1),
                ),
            },
            {
                "mode": HIL_MODE,
                "deadline_ns": 1,
                "must_stop": False,
                "stop_reason": None,
                "terms_ns": (
                    ("first_send_plus_original_ttl", 1),
                    ("sample_lower_plus_age_limit", 1),
                    ("first_host_issue_plus_requested_duration", 1),
                ),
            },
            {
                "mode": PC_DIRECT_MODE,
                "deadline_ns": 1,
                "must_stop": False,
                "stop_reason": None,
                "terms_ns": (
                    ("first_host_issue_plus_requested_duration", 1),
                    ("sample_lower_plus_age_limit", 1),
                    ("first_send_plus_original_ttl", 1),
                ),
            },
            {
                "mode": PC_DIRECT_MODE,
                "deadline_ns": 1,
                "must_stop": False,
                "stop_reason": None,
                "terms_ns": (
                    ("first_host_issue_plus_requested_duration", 1),
                    ("sample_lower_plus_age_limit", 1),
                    ("receipt_plus_remaining_budget", 1),
                ),
            },
            {
                "mode": HIL_MODE,
                "deadline_ns": 1,
                "must_stop": False,
                "stop_reason": None,
                "terms_ns": (("first_send_plus_original_ttl", 1),),
            },
            {
                "mode": HIL_MODE,
                "deadline_ns": 1,
                "must_stop": False,
                "stop_reason": None,
                "terms_ns": (("sample_lower_plus_age_limit", 1),),
            },
            {
                "mode": PC_DIRECT_MODE,
                "deadline_ns": 1,
                "must_stop": False,
                "stop_reason": None,
                "terms_ns": (("sample_lower_plus_age_limit", 1),),
            },
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(BrokerError):
                    LeaseDeadline(**case)

    def test_builder_term_names_match_the_mode_contract(self):
        plain_hil = hil()
        self.assertEqual(
            set(dict(plain_hil.terms_ns)),
            {"first_send_plus_original_ttl", "sample_lower_plus_age_limit"},
        )
        receipt_hil = hil(receipt_ns=0, **receipt_bounds(4 * SECOND))
        self.assertEqual(
            set(dict(receipt_hil.terms_ns)),
            {
                "first_send_plus_original_ttl",
                "receipt_plus_remaining_budget",
                "sample_lower_plus_age_limit",
            },
        )
        chained = hil(previous_deadline_ns=SECOND)
        self.assertIn("previous_deadline", dict(chained.terms_ns))
        plain_pc = pc_direct_deadline(
            first_host_issue_ns=0,
            requested_duration_ns=SECOND,
            referenced_sample_time_lower_ns=0,
            profile=FAST,
        )
        self.assertEqual(
            set(dict(plain_pc.terms_ns)),
            {
                "first_host_issue_plus_requested_duration",
                "sample_lower_plus_age_limit",
            },
        )
        chained_pc = pc_direct_deadline(
            first_host_issue_ns=0,
            requested_duration_ns=SECOND,
            referenced_sample_time_lower_ns=0,
            profile=FAST,
            previous_deadline_ns=SECOND,
        )
        self.assertIn("previous_deadline", dict(chained_pc.terms_ns))

    def test_audit_structure_is_not_provenance_or_authorization(self):
        text = " ".join(
            (
                (LeaseDeadline.__doc__ or "")
                + " "
                + (LeaseDeadline.validate.__doc__ or "")
            ).split()
        )
        self.assertIn("not cryptographic provenance", text)
        self.assertIn("never movement authorization", text)


class SourceScanTests(unittest.TestCase):
    def test_sources_have_no_world_clock_network_or_file_io(self):
        sources = {
            "deadlines": PRODUCT_ROOT / "ai_pc/control_broker/deadlines.py",
            "mailbox": PRODUCT_ROOT / "ai_pc/control_broker/mailbox.py",
        }
        forbidden = (
            "import time",
            "import datetime",
            "import socket",
            "import os",
            "import subprocess",
            "import urllib",
            "import requests",
            "from time",
            "from datetime",
            "from socket",
            "from os",
            "from subprocess",
            "open(",
        )
        for name, path in sources.items():
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(source=name, token=token):
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()

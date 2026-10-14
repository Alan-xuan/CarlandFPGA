"""Independent regression tests for ai_pc.model.causal_input (C01 repair #2).

Repair #2 supersedes repair #1 expectations after the main D04 adversarial
finding: many transport seqs sharing one acquisition tick must produce
exactly ONE model column.  All synthetic records declare
source_mode="software_fixture": they are a software fixture, never a claim
of physical observation or licensed data.

Coverage: packed quality_flags semantics (valid/saturated/held/fault/grant
bits), combined mask rule, per-channel bit positions, invalid flag values,
one-column-per-acquisition-tick merging, conservative same-tick quality
merge (valid intersect; saturated/held/source_fault union; worsening flags
never cleared by duplicates or reordering), same-tick payload conflicts
rejecting (held deliveries are not exempt), per-arrival grant metadata that
never changes features, contributing-seq bookkeeping and deterministic
representative seq, schema cardinality/name errors, one-shot schema
generator rejection, normalisation overflow, honest unknown native ages and
held semantics, leakage/forbidden fields, future timestamps,
binding/session/profile/epoch mixes, malformed numeric values, cold start,
zero-order held reuse, staleness and the frozen [1,13,32,1] layout.
"""

import sys
import unittest
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from ai_pc.model.causal_input import (  # noqa: E402
    CHANNEL_COUNT,
    GRANT_BITS_MASK,
    HELD_BIT_BASE,
    HELD_REUSE_MASK,
    MODEL_INPUT_SHAPE,
    SATURATED_BITS_MASK,
    SATURATED_BIT_BASE,
    SENSOR_BITS_MASK,
    SOURCE_FAULT_BIT,
    SOURCE_FAULT_FLAG_MASK,
    VALID_BITS_MASK,
    VALID_BIT_BASE,
    WINDOW_COLUMNS,
    CausalInputError,
    SummaryBinding,
    TelemetrySchema,
    build_summary_window,
)

BINDING = SummaryBinding(
    run_id="sim-run-1", session_id="sess-7", profile="fast_9600", epoch=3
)
KNOWN_PROFILES = ("fast_9600", "stress_300")
SCALES = (1.0, 2.0, 4.0, 8.0, 0.5, 0.25, 2.0, 4.0)
AGE_LIMIT_MS = 1500.0
VALID_ALL = 0x000F
HELD_ALL = 0x0F0F


def record(seq, tick_ms, *, binding=BINDING, means=None, ranges=None,
           quality_flags=VALID_ALL, mode="software_fixture", **overrides):
    """Build one legal software_fixture summary record with one packed uint16."""
    means = tuple(means) if means is not None else (0.0, 1.0, 2.0, 3.0)
    ranges = tuple(ranges) if ranges is not None else (0.5, 0.5, 0.5, 0.5)
    row = {
        "run_id": binding.run_id,
        "session_id": binding.session_id,
        "profile": binding.profile,
        "epoch": binding.epoch,
        "seq": seq,
        "tick_ms": tick_ms,
        "source_mode": mode,
        "mean_0": means[0],
        "mean_1": means[1],
        "mean_2": means[2],
        "mean_3": means[3],
        "range_0": ranges[0],
        "range_1": ranges[1],
        "range_2": ranges[2],
        "range_3": ranges[3],
        "quality_flags": quality_flags,
    }
    row.update(overrides)
    return row


def build(records, *, cutoff=1000, binding=BINDING, scales=SCALES,
          age_limit_ms=AGE_LIMIT_MS, known_profiles=KNOWN_PROFILES, schema=None):
    return build_summary_window(
        records,
        binding=binding,
        known_profiles=known_profiles,
        decision_cutoff_ms=cutoff,
        scales=scales,
        age_limit_ms=age_limit_ms,
        schema=schema,
    )


class CausalInputTestCase(unittest.TestCase):
    def assert_build_error(self, records, **kwargs):
        with self.assertRaises(CausalInputError):
            build(records, **kwargs)


class WindowLayoutTests(CausalInputTestCase):
    def test_shape_scaling_layout_and_model_input(self):
        window = build([
            record(1, 900, means=(2.0, 4.0, 6.0, 8.0), ranges=(1.0, 1.0, 1.0, 1.0))
        ])
        self.assertEqual(len(window.features), CHANNEL_COUNT)
        self.assertTrue(all(len(channel) == WINDOW_COLUMNS for channel in window.features))
        column = window.columns[-1]
        self.assertFalse(column.padded)
        self.assertEqual(column.tick_ms, 900)
        self.assertEqual(column.seq, 1)
        self.assertEqual(column.contributing_seqs, (1,))
        self.assertEqual(column.grant_arrivals, ((1, (False, False, False)),))
        self.assertEqual(column.age_ms, 100)
        self.assertAlmostEqual(column.normalized_age, 100 / AGE_LIMIT_MS, places=12)
        self.assertAlmostEqual(window.features[0][-1], 2.0)
        self.assertAlmostEqual(window.features[1][-1], 2.0)
        self.assertAlmostEqual(window.features[3][-1], 1.0)
        self.assertAlmostEqual(window.features[4][-1], 2.0)
        for mask_row in range(8, 12):
            self.assertEqual(window.features[mask_row][-1], 1.0)
        self.assertAlmostEqual(window.features[12][-1], 100 / AGE_LIMIT_MS, places=12)
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))
        self.assertEqual(window.metadata.excluded_future_records, 0)
        self.assertEqual(window.metadata.duplicate_records_dropped, 0)
        self.assertEqual(window.metadata.source_modes, ("software_fixture",))
        self.assertEqual(window.metadata.scales, SCALES)

        model_input = window.to_model_input()
        shape = (
            len(model_input),
            len(model_input[0]),
            len(model_input[0][0]),
            len(model_input[0][0][0]),
        )
        self.assertEqual(shape, MODEL_INPUT_SHAPE)

    def test_cold_start_left_padding_is_masked(self):
        window = build([record(5, 990)])
        padded = window.columns[:31]
        self.assertTrue(all(column.padded for column in padded))
        self.assertFalse(window.columns[31].padded)
        for channel in window.features:
            self.assertEqual(channel[:31], (0.0,) * 31)
        for column in padded:
            self.assertEqual(column.valid_mask, (0.0, 0.0, 0.0, 0.0))
            self.assertIsNone(column.quality_flags)
            self.assertEqual(column.grants, (False, False, False))
            self.assertEqual(column.contributing_seqs, ())
            self.assertEqual(column.grant_arrivals, ())
            self.assertIsNone(column.source_native_tick_ms)
        self.assertEqual(window.metadata.columns_padded, 31)

    def test_records_sorted_by_acquisition_tick(self):
        window = build([
            record(3, 800, means=(0.3, 0, 0, 0)),
            record(1, 600, means=(0.1, 0, 0, 0)),
            record(2, 700, means=(0.2, 0, 0, 0)),
        ])
        ticks = [column.tick_ms for column in window.columns if not column.padded]
        self.assertEqual(ticks, [600, 700, 800])
        self.assertAlmostEqual(window.features[0][-1], 0.3)

    def test_last_32_columns_keep_newest_oldest_first(self):
        records = [record(seq, seq * 10) for seq in range(1, 41)]
        window = build(records)
        self.assertEqual(window.metadata.columns_padded, 0)
        self.assertEqual(window.metadata.columns_dropped_oldest, 8)
        self.assertEqual(window.metadata.duplicate_tick_records, 0)
        ticks = [column.tick_ms for column in window.columns]
        self.assertEqual(ticks, list(range(90, 401, 10)))
        self.assertEqual(window.metadata.unique_acquisition_ticks, 32)
        self.assertEqual(window.metadata.fresh_counts, (32, 32, 32, 32))
        for column in window.columns:
            self.assertEqual(column.contributing_seqs, (column.seq,))



class QualityFlagTests(CausalInputTestCase):
    def test_packed_bit_constants(self):
        self.assertEqual(VALID_BIT_BASE, 0)
        self.assertEqual(SATURATED_BIT_BASE, 4)
        self.assertEqual(HELD_BIT_BASE, 8)
        self.assertEqual(SOURCE_FAULT_BIT, 12)
        self.assertEqual(VALID_BITS_MASK, 0x000F)
        self.assertEqual(SATURATED_BITS_MASK, 0x00F0)
        self.assertEqual(SOURCE_FAULT_FLAG_MASK, 0x1000)
        self.assertEqual(SENSOR_BITS_MASK, 0x1FFF)
        self.assertEqual(GRANT_BITS_MASK, 0xE000)
        self.assertEqual(HELD_REUSE_MASK, 0x0F00)
        self.assertEqual(
            VALID_BITS_MASK
            | SATURATED_BITS_MASK
            | HELD_REUSE_MASK
            | SOURCE_FAULT_FLAG_MASK,
            SENSOR_BITS_MASK,
        )
        self.assertEqual(SENSOR_BITS_MASK | GRANT_BITS_MASK, 0xFFFF)
        self.assertEqual(0xE00F & SENSOR_BITS_MASK, VALID_ALL)

    def test_all_zero_flags_are_invalid_everywhere(self):
        window = build([record(1, 900, quality_flags=0x0000)])
        column = window.columns[-1]
        self.assertEqual(column.valid_mask, (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(column.quality_flags, 0x0000)
        self.assertEqual(column.grants, (False, False, False))
        self.assertEqual(column.held, (False, False, False, False))
        self.assertEqual(column.saturated, (False, False, False, False))
        self.assertEqual(window.metadata.fresh_counts, (0, 0, 0, 0))
        for channel in window.features[8:12]:
            self.assertEqual(channel[-1], 0.0)

    def test_valid_all_flags_are_fresh(self):
        window = build([record(1, 900, quality_flags=VALID_ALL)])
        column = window.columns[-1]
        self.assertEqual(column.valid_mask, (1.0, 1.0, 1.0, 1.0))
        self.assertEqual(column.grants, (False, False, False))
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))

    def test_individual_valid_bit_positions(self):
        for channel in range(4):
            with self.subTest(channel=channel):
                window = build([record(1, 900, quality_flags=1 << (VALID_BIT_BASE + channel))])
                expected = tuple(1.0 if c == channel else 0.0 for c in range(4))
                self.assertEqual(window.columns[-1].valid_mask, expected)
                self.assertEqual(
                    window.metadata.fresh_counts,
                    tuple(1 if c == channel else 0 for c in range(4)),
                )

    def test_individual_saturated_bit_positions(self):
        for channel in range(4):
            with self.subTest(channel=channel):
                flags = VALID_ALL | (1 << (SATURATED_BIT_BASE + channel))
                window = build([record(1, 900, quality_flags=flags)])
                expected = tuple(0.0 if c == channel else 1.0 for c in range(4))
                self.assertEqual(window.columns[-1].valid_mask, expected)
                self.assertEqual(
                    window.columns[-1].saturated,
                    tuple(c == channel for c in range(4)),
                )
                self.assertEqual(
                    window.metadata.fresh_counts,
                    tuple(0 if c == channel else 1 for c in range(4)),
                )

    def test_individual_held_bit_positions(self):
        for channel in range(4):
            with self.subTest(channel=channel):
                flags = VALID_ALL | (1 << (HELD_BIT_BASE + channel))
                window = build([record(1, 900, quality_flags=flags)])
                expected = tuple(0.0 if c == channel else 1.0 for c in range(4))
                self.assertEqual(window.columns[-1].valid_mask, expected)
                self.assertEqual(
                    window.columns[-1].held, tuple(c == channel for c in range(4))
                )
                self.assertEqual(
                    window.metadata.fresh_counts,
                    tuple(0 if c == channel else 1 for c in range(4)),
                )
                self.assertEqual(
                    window.metadata.held_counts,
                    tuple(1 if c == channel else 0 for c in range(4)),
                )

    def test_source_fault_bit_masks_all_channels(self):
        window = build([record(1, 900, quality_flags=0x100F)])
        column = window.columns[-1]
        self.assertEqual(column.valid_mask, (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(column.source_fault, (True, True, True, True))
        self.assertEqual(window.metadata.fresh_counts, (0, 0, 0, 0))
        self.assertEqual(window.metadata.source_fault_counts, (1, 1, 1, 1))

        fault_only = build([record(1, 900, quality_flags=1 << SOURCE_FAULT_BIT)])
        self.assertEqual(fault_only.columns[-1].valid_mask, (0.0, 0.0, 0.0, 0.0))

    def test_combined_saturated_and_held_mask(self):
        flags = VALID_ALL | (1 << (SATURATED_BIT_BASE + 1)) | (1 << (HELD_BIT_BASE + 2))
        window = build([record(1, 900, quality_flags=flags)])
        self.assertEqual(window.columns[-1].valid_mask, (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(window.metadata.fresh_counts, (1, 0, 0, 1))

    def test_grant_bits_never_mask_or_validate(self):
        all_grants = build([record(1, 900, quality_flags=0xE00F)])
        column = all_grants.columns[-1]
        self.assertEqual(column.quality_flags, 0xE00F)
        self.assertEqual(column.grants, (True, True, True))
        self.assertEqual(column.valid_mask, (1.0, 1.0, 1.0, 1.0))
        self.assertEqual(all_grants.metadata.fresh_counts, (1, 1, 1, 1))

        single_grant = build([record(1, 900, quality_flags=0x200F)])
        self.assertEqual(single_grant.columns[-1].grants, (True, False, False))
        self.assertEqual(single_grant.columns[-1].valid_mask, (1.0, 1.0, 1.0, 1.0))

        grants_only = build([record(1, 900, quality_flags=0xE000)])
        self.assertEqual(grants_only.columns[-1].grants, (True, True, True))
        self.assertEqual(grants_only.columns[-1].valid_mask, (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(grants_only.metadata.fresh_counts, (0, 0, 0, 0))

    def test_invalid_flag_values_rejected(self):
        for flags in (-1, 0x10000, True, False, 3.5, "15", None):
            with self.subTest(flags=flags):
                self.assert_build_error([record(1, 900, quality_flags=flags)])


class SameTickPolicyTests(CausalInputTestCase):
    def test_duplicate_tick_merges_to_one_column(self):
        window = build([record(1, 900), record(2, 900)])
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))
        self.assertEqual(window.metadata.duplicate_tick_records, 1)
        self.assertEqual(window.metadata.unique_acquisition_ticks, 1)
        self.assertEqual(window.metadata.accepted_records, 2)
        selected = [column for column in window.columns if not column.padded]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].tick_ms, 900)
        self.assertEqual(selected[0].seq, 1)
        self.assertEqual(selected[0].contributing_seqs, (1, 2))
        self.assertEqual(selected[0].valid_mask, (1.0, 1.0, 1.0, 1.0))
        self.assertEqual(
            selected[0].grant_arrivals,
            ((1, (False, False, False)), (2, (False, False, False))),
        )

    def test_conflicting_summaries_same_tick_rejected(self):
        self.assert_build_error([
            record(1, 900, means=(0.0, 1.0, 2.0, 3.0)),
            record(2, 900, means=(9.0, 1.0, 2.0, 3.0)),
        ])

    def test_conflicting_ranges_same_tick_rejected(self):
        self.assert_build_error([
            record(1, 900, ranges=(0.5, 0.5, 0.5, 0.5)),
            record(2, 900, ranges=(0.5, 1.5, 0.5, 0.5)),
        ])

    def test_grant_only_difference_same_tick_allowed(self):
        window = build([
            record(1, 900, quality_flags=VALID_ALL),
            record(2, 900, quality_flags=0x200F),
        ])
        self.assertEqual(window.metadata.duplicate_tick_records, 1)
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))
        selected = [column for column in window.columns if not column.padded]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].grants, (False, False, False))
        self.assertEqual(
            selected[0].grant_arrivals,
            ((1, (False, False, False)), (2, (True, False, False))),
        )
        self.assertEqual(selected[0].valid_mask, (1.0, 1.0, 1.0, 1.0))

    def test_conflicting_held_payload_same_tick_rejected(self):
        self.assert_build_error([
            record(1, 900, means=(0.0, 1.0, 2.0, 3.0), quality_flags=HELD_ALL),
            record(2, 900, means=(9.0, 9.0, 9.0, 9.0), quality_flags=HELD_ALL),
        ])
        self.assert_build_error([
            record(1, 900, means=(0.0, 1.0, 2.0, 3.0), quality_flags=VALID_ALL),
            record(2, 900, means=(9.0, 9.0, 9.0, 9.0), quality_flags=HELD_ALL),
        ])

    def test_held_same_tick_same_payload_merges_conservatively(self):
        window = build([
            record(1, 900, means=(0.0, 1.0, 2.0, 3.0), quality_flags=HELD_ALL),
            record(2, 900, means=(0.0, 1.0, 2.0, 3.0), quality_flags=HELD_ALL),
        ])
        self.assertEqual(window.metadata.duplicate_tick_records, 1)
        self.assertEqual(window.metadata.fresh_counts, (0, 0, 0, 0))
        self.assertEqual(window.metadata.held_counts, (1, 1, 1, 1))
        selected = [column for column in window.columns if not column.padded]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].tick_ms, 900)
        self.assertEqual(selected[0].valid_mask, (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(selected[0].quality_flags, HELD_ALL)

    def test_held_and_fresh_same_tick_same_payload_merges_conservatively(self):
        window = build([
            record(1, 900, means=(0.0, 1.0, 2.0, 3.0), quality_flags=VALID_ALL),
            record(2, 900, means=(0.0, 1.0, 2.0, 3.0), quality_flags=HELD_ALL),
        ])
        self.assertEqual(window.metadata.duplicate_tick_records, 1)
        self.assertEqual(window.metadata.fresh_counts, (0, 0, 0, 0))
        self.assertEqual(window.metadata.held_counts, (1, 1, 1, 1))
        selected = [column for column in window.columns if not column.padded]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].valid_mask, (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(selected[0].quality_flags, HELD_ALL)


class DuplicateTickRepair2Tests(CausalInputTestCase):
    """Main D04 regressions: exactly one model column per acquisition tick."""

    def test_d04_repeated_deliveries_make_one_column(self):
        single = build([record(1, 900, means=(2.0, 4.0, 6.0, 8.0))])
        repeated = build([
            record(seq, 900, means=(2.0, 4.0, 6.0, 8.0)) for seq in range(1, 33)
        ])
        self.assertEqual(repeated.features, single.features)
        self.assertEqual(repeated.metadata.fresh_counts, single.metadata.fresh_counts)
        self.assertEqual(repeated.metadata.accepted_records, 32)
        self.assertEqual(repeated.metadata.duplicate_tick_records, 31)
        self.assertEqual(repeated.metadata.unique_acquisition_ticks, 1)
        self.assertEqual(repeated.metadata.duplicate_records_dropped, 0)
        selected = [column for column in repeated.columns if not column.padded]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].tick_ms, 900)
        self.assertEqual(selected[0].seq, 1)
        self.assertEqual(selected[0].contributing_seqs, tuple(range(1, 33)))
        self.assertEqual(len(selected[0].grant_arrivals), 32)
        for row in range(8, 12):
            self.assertEqual(sum(repeated.features[row]), 1.0)

    def test_duplicate_deliveries_do_not_evict_older_history(self):
        older = [
            record(seq, seq * 10, means=(float(seq), 0.0, 0.0, 0.0))
            for seq in range(1, 32)
        ]
        single = build(older + [record(900, 900)])
        repeated = build(older + [record(seq, 900) for seq in range(900, 932)])
        self.assertEqual(repeated.metadata.accepted_records, 63)
        self.assertEqual(repeated.metadata.duplicate_tick_records, 31)
        self.assertEqual(repeated.metadata.columns_padded, 0)
        self.assertEqual(repeated.metadata.columns_dropped_oldest, 0)
        selected = [column for column in repeated.columns if not column.padded]
        self.assertEqual(len(selected), 32)
        self.assertEqual([column.tick_ms for column in selected][:3], [10, 20, 30])
        self.assertEqual(selected[-1].tick_ms, 900)
        self.assertEqual(selected[-1].contributing_seqs, tuple(range(900, 932)))
        self.assertEqual(repeated.features, single.features)

    def test_delivery_order_permutation_is_deterministic(self):
        rows = [
            record(1, 100, means=(0.1, 0.0, 0.0, 0.0)),
            record(2, 200, means=(0.2, 0.0, 0.0, 0.0)),
            record(3, 200, means=(0.2, 0.0, 0.0, 0.0)),
            record(4, 300, means=(0.3, 0.0, 0.0, 0.0)),
            record(5, 100, means=(0.1, 0.0, 0.0, 0.0)),
        ]
        base = build(rows)
        for order in (
            list(reversed(rows)),
            [rows[2], rows[4], rows[0], rows[3], rows[1]],
            [rows[4], rows[3], rows[2], rows[1], rows[0]],
        ):
            with self.subTest(order=[entry["seq"] for entry in order]):
                other = build(order)
                self.assertEqual(other.features, base.features)
                self.assertEqual(other.metadata.fresh_counts, base.metadata.fresh_counts)
                self.assertEqual(
                    [
                        (column.tick_ms, column.seq, column.contributing_seqs)
                        for column in other.columns
                        if not column.padded
                    ],
                    [
                        (column.tick_ms, column.seq, column.contributing_seqs)
                        for column in base.columns
                        if not column.padded
                    ],
                )
                self.assertEqual(
                    other.metadata.duplicate_tick_records,
                    base.metadata.duplicate_tick_records,
                )

    def test_grant_variation_never_changes_features(self):
        clean = build([
            record(1, 900, means=(2.0, 4.0, 6.0, 8.0)),
            record(2, 900, means=(2.0, 4.0, 6.0, 8.0)),
        ])
        granted = build([
            record(1, 900, means=(2.0, 4.0, 6.0, 8.0)),
            record(2, 900, means=(2.0, 4.0, 6.0, 8.0), quality_flags=0xE00F),
            record(3, 900, means=(2.0, 4.0, 6.0, 8.0), quality_flags=0x200F),
        ])
        self.assertEqual(granted.features, clean.features)
        self.assertEqual(granted.metadata.fresh_counts, clean.metadata.fresh_counts)
        column = [entry for entry in granted.columns if not entry.padded][-1]
        self.assertEqual(column.quality_flags, 0x000F)
        self.assertEqual(column.grants, (False, False, False))
        self.assertEqual(
            column.grant_arrivals,
            (
                (1, (False, False, False)),
                (2, (True, True, True)),
                (3, (True, False, False)),
            ),
        )
        self.assertEqual(column.valid_mask, (1.0, 1.0, 1.0, 1.0))

    def test_conservative_quality_merge_never_clears(self):
        payload = {"means": (0.0, 1.0, 2.0, 3.0)}
        worse_flags = 0x000E | (1 << (SATURATED_BIT_BASE + 2)) | (1 << (HELD_BIT_BASE + 3))
        records = [
            record(1, 900, quality_flags=VALID_ALL, **payload),
            record(2, 900, quality_flags=worse_flags, **payload),
        ]
        window = build(records)
        self.assertEqual(window.metadata.duplicate_tick_records, 1)
        column = [entry for entry in window.columns if not entry.padded][-1]
        self.assertEqual(column.quality_flags, 0x084E)
        self.assertEqual(column.valid_mask, (0.0, 1.0, 0.0, 0.0))
        self.assertEqual(column.saturated, (False, False, True, False))
        self.assertEqual(column.held, (False, False, False, True))
        self.assertEqual(window.metadata.fresh_counts, (0, 1, 0, 0))
        later_clean = build(records + [record(3, 900, quality_flags=VALID_ALL, **payload)])
        self.assertEqual(later_clean.features, window.features)
        self.assertEqual(later_clean.metadata.fresh_counts, (0, 1, 0, 0))
        reversed_window = build(list(reversed(records)))
        self.assertEqual(reversed_window.features, window.features)
        self.assertEqual(reversed_window.metadata.fresh_counts, (0, 1, 0, 0))
        self.assertEqual(reversed_window.columns[-1].quality_flags, 0x084E)

    def test_source_fault_union_masks_all_and_never_clears(self):
        records = [
            record(1, 900, quality_flags=VALID_ALL),
            record(2, 900, quality_flags=0x100F),
        ]
        window = build(records)
        column = [entry for entry in window.columns if not entry.padded][-1]
        self.assertEqual(column.source_fault, (True, True, True, True))
        self.assertEqual(column.valid_mask, (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(window.metadata.fresh_counts, (0, 0, 0, 0))
        self.assertEqual(window.metadata.source_fault_counts, (1, 1, 1, 1))
        later_clean = build(records + [record(3, 900, quality_flags=VALID_ALL)])
        self.assertEqual(later_clean.features, window.features)
        self.assertEqual(later_clean.columns[-1].source_fault, (True, True, True, True))
        self.assertEqual(build(list(reversed(records))).features, window.features)

    def test_representative_seq_is_smallest_and_grants_stay_per_arrival(self):
        window = build([
            record(9, 900, quality_flags=0x200F),
            record(3, 900, quality_flags=0x400F),
            record(7, 900),
        ])
        column = [entry for entry in window.columns if not entry.padded][-1]
        self.assertEqual(column.seq, 3)
        self.assertEqual(column.contributing_seqs, (3, 7, 9))
        self.assertEqual(column.grants, (False, True, False))
        self.assertEqual(column.grant_arrivals[0], (3, (False, True, False)))
        self.assertEqual(column.quality_flags, 0x400F)



class SchemaValidationTests(CausalInputTestCase):
    def test_default_schema_exposes_one_quality_field(self):
        schema = TelemetrySchema()
        names = schema.field_names()
        self.assertEqual(len(names), 16)
        self.assertEqual(len(set(names)), 16)
        self.assertIn("quality_flags", names)
        self.assertNotIn("quality_0", names)
        self.assertEqual(schema.allowed(), frozenset(names))

    def test_field_names_access_is_stable_for_sequences(self):
        schema = TelemetrySchema()
        first = schema.field_names()
        second = schema.field_names()
        third = schema.field_names()
        self.assertEqual(first, second)
        self.assertEqual(second, third)
        self.assertEqual(len(first), 16)

    def test_wrong_cardinality_rejected_as_causal_error(self):
        bad_schemas = (
            TelemetrySchema(means=("mean_0", "mean_1", "mean_2")),
            TelemetrySchema(means=("m0", "m1", "m2", "m3", "m4")),
            TelemetrySchema(ranges=("range_0", "range_1")),
        )
        for schema in bad_schemas:
            with self.assertRaises(CausalInputError):
                schema.validate()
            self.assert_build_error([record(1, 900)], schema=schema)

    def test_non_string_or_empty_names_rejected(self):
        bad_schemas = (
            TelemetrySchema(means=(None, "m1", "m2", "m3")),
            TelemetrySchema(means=(1, "m1", "m2", "m3")),
            TelemetrySchema(run_id=""),
            TelemetrySchema(quality_flags=None),
            TelemetrySchema(ranges=("r0", "r1", "r2", "")),
        )
        for schema in bad_schemas:
            with self.assertRaises(CausalInputError):
                schema.validate()

    def test_unhashable_names_rejected_as_causal_error(self):
        schema = TelemetrySchema(means=(["mean_0"], "mean_1", "mean_2", "mean_3"))
        with self.assertRaises(CausalInputError):
            schema.validate()
        self.assert_build_error([record(1, 900)], schema=schema)

    def test_non_sequence_group_rejected_as_causal_error(self):
        bad_groups = (
            {"means": None},
            {"ranges": 4},
            {"means": {"m0", "m1", "m2", "m3"}},
        )
        for kwargs in bad_groups:
            with self.subTest(kwargs=kwargs):
                schema = TelemetrySchema(**kwargs)
                with self.assertRaises(CausalInputError):
                    schema.validate()

    def test_one_shot_generator_group_rejected_without_consumption(self):
        generator = (name for name in ("m0", "m1", "m2", "m3"))
        schema = TelemetrySchema(means=generator, ranges=("r0", "r1", "r2", "r3"))
        with self.assertRaises(CausalInputError):
            schema.validate()
        self.assertEqual(next(generator), "m0")
        self.assert_build_error([record(1, 900)], schema=schema)
        self.assertEqual(next(generator), "m1")

    def test_malformed_schema_generator_rejected(self):
        short = (name for name in ("m0", "m1"))
        schema = TelemetrySchema(means=short)
        with self.assertRaises(CausalInputError):
            schema.validate()
        self.assert_build_error([record(1, 900)], schema=schema)

    def test_duplicate_names_rejected(self):
        bad_schemas = (
            TelemetrySchema(run_id="seq"),
            TelemetrySchema(means=("m0", "m0", "m2", "m3")),
            TelemetrySchema(means=("mean_0", "mean_1", "mean_2", "range_0")),
        )
        for schema in bad_schemas:
            with self.assertRaises(CausalInputError):
                schema.validate()

    def test_forbidden_schema_token_rejected(self):
        schema = TelemetrySchema(means=("truth_0", "mean_1", "mean_2", "mean_3"))
        with self.assertRaises(CausalInputError):
            schema.validate()

    def test_custom_schema_renames_fields(self):
        schema = TelemetrySchema(
            run_id="case", session_id="sess", profile="profile", epoch="epoch",
            seq="seq", tick_ms="tick", source_mode="mode",
            means=("m0", "m1", "m2", "m3"), ranges=("r0", "r1", "r2", "r3"),
            quality_flags="quality")
        row = {
            "case": BINDING.run_id, "sess": BINDING.session_id,
            "profile": BINDING.profile, "epoch": BINDING.epoch,
            "seq": 1, "tick": 900, "mode": "software_fixture",
            "m0": 0.0, "m1": 1.0, "m2": 2.0, "m3": 3.0,
            "r0": 0.5, "r1": 0.5, "r2": 0.5, "r3": 0.5,
            "quality": VALID_ALL,
        }
        window = build([row], schema=schema)
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))
        self.assertEqual(len(schema.field_names()), 16)

    def test_list_groups_are_accepted_as_fixed_sequences(self):
        schema = TelemetrySchema(
            run_id="case", session_id="sess", profile="profile", epoch="epoch",
            seq="seq", tick_ms="tick", source_mode="mode",
            means=["m0", "m1", "m2", "m3"], ranges=["r0", "r1", "r2", "r3"],
            quality_flags="quality")
        row = {
            "case": BINDING.run_id, "sess": BINDING.session_id,
            "profile": BINDING.profile, "epoch": BINDING.epoch,
            "seq": 1, "tick": 900, "mode": "software_fixture",
            "m0": 0.0, "m1": 1.0, "m2": 2.0, "m3": 3.0,
            "r0": 0.5, "r1": 0.5, "r2": 0.5, "r3": 0.5,
            "quality": VALID_ALL,
        }
        window = build([row], schema=schema)
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))
        names = schema.field_names()
        self.assertEqual(names[7], "quality")
        self.assertEqual(len(names), 16)

    def test_extra_and_missing_fields_rejected(self):
        self.assert_build_error([record(1, 900, source_native_tick_ms=900)])
        broken = record(1, 900)
        del broken["mean_0"]
        self.assert_build_error([broken])

    def test_forbidden_record_fields_rejected(self):
        for key in ("truth_label", "future_tick", "object_id", "seed", "oracle_range"):
            with self.subTest(key=key):
                self.assert_build_error([record(1, 900, **{key: 1})])


class NumericValidationTests(CausalInputTestCase):
    def test_boolean_and_non_numeric_means_rejected(self):
        for bad in (True, "1.0", None):
            with self.subTest(bad=bad):
                self.assert_build_error([record(1, 900, means=(bad, 0.0, 0.0, 0.0))])
        self.assert_build_error([record(1, 900, ranges=("0.5", 0.5, 0.5, 0.5))])

    def test_non_finite_means_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad):
                self.assert_build_error([record(1, 900, means=(bad, 0.0, 0.0, 0.0))])
        self.assert_build_error([record(1, 900, ranges=(float("inf"), 0.5, 0.5, 0.5))])

    def test_negative_range_rejected(self):
        self.assert_build_error([record(1, 900, ranges=(-0.5, 0.5, 0.5, 0.5))])

    def test_invalid_identity_fields_rejected(self):
        self.assert_build_error([record(-1, 900)])
        self.assert_build_error([record(1, -900)])
        self.assert_build_error([record(1.5, 900)])
        self.assert_build_error([record(1, 900, epoch=True)])

    def test_scales_validation(self):
        for scales in (
            (1.0,) * 7,
            (1.0,) * 9,
            (1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            (1.0, 1.0, -2.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            (1.0, 1.0, float("inf"), 1.0, 1.0, 1.0, 1.0, 1.0),
            (1.0, 1.0, True, 1.0, 1.0, 1.0, 1.0, 1.0),
            None,
        ):
            with self.subTest(scales=scales):
                self.assert_build_error([record(1, 900)], scales=scales)

    def test_age_limit_and_cutoff_validation(self):
        for age_limit in (0.0, -1.0, float("inf"), True):
            with self.subTest(age_limit=age_limit):
                self.assert_build_error([record(1, 900)], age_limit_ms=age_limit)
        self.assert_build_error([record(1, 900)], cutoff=-1)

    def test_normalization_overflow_rejected(self):
        mean_scales = (1e-10, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        self.assert_build_error(
            [record(1, 900, means=(1e308, 0.0, 0.0, 0.0))], scales=mean_scales
        )
        range_scales = (1.0, 1.0, 1.0, 1.0, 1e-10, 1.0, 1.0, 1.0)
        self.assert_build_error(
            [record(1, 900, ranges=(1e308, 0.0, 0.0, 0.0))], scales=range_scales
        )

    def test_huge_integer_inputs_rejected(self):
        huge = 10 ** 400
        self.assert_build_error([record(1, 900, means=(huge, 0.0, 0.0, 0.0))])
        self.assert_build_error([record(1, 900, ranges=(huge, 0.0, 0.0, 0.0))])


class TimeAndFreshnessTests(CausalInputTestCase):
    def test_future_records_excluded_and_counted(self):
        window = build([record(1, 999), record(2, 1001), record(3, 1500)])
        self.assertEqual(window.metadata.total_records, 3)
        self.assertEqual(window.metadata.excluded_future_records, 2)
        self.assertEqual(window.metadata.accepted_records, 1)
        selected = [column for column in window.columns if not column.padded]
        self.assertEqual([column.tick_ms for column in selected], [999])

    def test_age_equal_to_limit_is_fresh(self):
        window = build([record(1, 0)], cutoff=1500)
        column = window.columns[-1]
        self.assertFalse(column.stale[0])
        self.assertEqual(column.valid_mask, (1.0, 1.0, 1.0, 1.0))
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))
        self.assertAlmostEqual(column.normalized_age, 1.0)

    def test_stale_record_masked_with_truthful_age(self):
        window = build([record(1, 900)], cutoff=10000)
        column = window.columns[-1]
        self.assertEqual(column.tick_ms, 900)
        self.assertEqual(column.age_ms, 9100)
        self.assertEqual(column.valid_mask, (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(column.stale, (True, True, True, True))
        self.assertEqual(window.metadata.fresh_counts, (0, 0, 0, 0))
        self.assertEqual(window.metadata.stale_counts, (1, 1, 1, 1))
        self.assertAlmostEqual(column.normalized_age, 1.0)

    def test_held_keeps_truthful_tick_and_unknown_native_tick(self):
        flags = VALID_ALL | (1 << HELD_BIT_BASE)
        window = build([record(1, 900, quality_flags=flags)])
        column = window.columns[-1]
        self.assertEqual(column.held, (True, False, False, False))
        self.assertEqual(column.tick_ms, 900)
        self.assertEqual(column.age_ms, 100)
        self.assertEqual(column.valid_mask, (0.0, 1.0, 1.0, 1.0))
        self.assertEqual(window.metadata.fresh_counts, (0, 1, 1, 1))
        self.assertIsNone(column.source_native_tick_ms)

    def test_native_tick_unknown_and_held_reuse_not_fresh(self):
        window = build([record(1, 800), record(2, 900, quality_flags=0x0F0F)])
        for column in window.columns[-2:]:
            self.assertIsNone(column.source_native_tick_ms)
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))
        self.assertEqual(window.metadata.held_counts, (1, 1, 1, 1))


class DuplicateAndBindingTests(CausalInputTestCase):
    def test_identical_seq_duplicate_dropped(self):
        window = build([record(5, 900), record(5, 900)])
        self.assertEqual(window.metadata.duplicate_records_dropped, 1)
        self.assertEqual(window.metadata.accepted_records, 1)
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))
        selected = [column for column in window.columns if not column.padded]
        self.assertEqual(len(selected), 1)

    def test_conflicting_seq_rejected(self):
        self.assert_build_error([record(5, 900), record(5, 950)])
        self.assert_build_error([
            record(5, 900, means=(0.0, 1.0, 2.0, 3.0)),
            record(5, 900, means=(9.0, 1.0, 2.0, 3.0)),
        ])
        self.assert_build_error([
            record(5, 900, quality_flags=VALID_ALL),
            record(5, 900, quality_flags=VALID_ALL | (1 << SATURATED_BIT_BASE)),
        ])

    def test_grant_only_difference_same_seq_is_a_transport_duplicate(self):
        window = build([
            record(5, 900, quality_flags=VALID_ALL),
            record(5, 900, quality_flags=0x200F),
        ])
        self.assertEqual(window.metadata.duplicate_records_dropped, 1)
        self.assertEqual(window.metadata.accepted_records, 1)
        self.assertEqual(window.metadata.fresh_counts, (1, 1, 1, 1))

    def test_binding_mismatch_rejected(self):
        self.assert_build_error([record(1, 900, session_id="other-session")])
        self.assert_build_error([record(1, 900, profile="stress_300")])
        self.assert_build_error([record(1, 900, epoch=4)])

    def test_unknown_profile_rejected(self):
        self.assert_build_error([record(1, 900)], known_profiles=("stress_300",))

    def test_source_mode_mix_rejected(self):
        self.assert_build_error([record(1, 800), record(2, 900, mode="twin_fixture")])

    def test_unknown_source_mode_rejected(self):
        self.assert_build_error([record(1, 900, mode="live_raw")])


class MainBoundaryRegressionTests(unittest.TestCase):
    def test_extreme_stale_age_clips_without_float_overflow(self):
        window = build([record(1, 0)], cutoff=10 ** 400)
        self.assertEqual(window.columns[-1].normalized_age, 1.0)
        self.assertEqual(window.columns[-1].valid_mask, (0.0,) * 4)

    def test_malformed_binding_and_schema_use_domain_error(self):
        with self.assertRaises(CausalInputError):
            build([], binding=None)
        with self.assertRaises(CausalInputError):
            build([], schema={})


if __name__ == "__main__":
    unittest.main()

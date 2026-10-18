"""Independent targeted review; no B implementation or roundtrip oracle."""

import binascii
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("c_decoder_under_review", HERE / "candidate_snapshot.py")
C = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = C
spec.loader.exec_module(C)
BOUND = {"session": 0x01020304, "config_epoch": 2, "e": 0}
METRICS = {}


def word(value, width):
    return value.to_bytes(width, "little")


def bit_bytes(bits):
    return bytes(sum(value << (7 - j) for j, value in enumerate(bits[i:i + 8]))
                 for i in range(0, len(bits), 8))


def residual_model(values, e):
    """Closed-loop source arithmetic copied from normative equation only."""
    restored = [values[0]]
    zigzags = []
    for original in values[1:]:
        delta = original - restored[-1]
        q = (delta + e) // (2 * e + 1)
        restored.append(max(0, min(65535, restored[-1] + q * (2 * e + 1))))
        zigzags.append(2 * q if q >= 0 else -2 * q - 1)
    return restored, zigzags


def rice_code(anchor, zigzags, k):
    digits = []
    for z in zigzags:
        digits.extend([0] * (z >> k))
        digits.append(1)
        digits.extend((z >> shift) & 1 for shift in range(k - 1, -1, -1))
    return 16 + len(digits), word(anchor, 2) + bit_bytes(digits)


def payload(values=None, *, e=0, channel=0, index=0, tick=0, count=None,
            index_stride=1, tick_stride=10, saturated=False, held=False,
            source_fault=False, origin=None, force_mode=None, force_k=None):
    valid = values is not None
    n = len(values) if valid else count
    settings = (0, 1, 2, 4, 8).index(e)
    quality = channel | (4 if valid else 0) | (8 if saturated else 0)
    quality |= (16 if held else 0) | (32 if source_fault else 0)
    optional = b""
    if n > 1:
        optional += word(index_stride, 2) + word(tick_stride, 2)
    if held:
        age = tick - origin
        if 1 <= age <= 65535:
            optional += word(age, 2)
        else:
            quality |= 64
            optional += word(origin, 8)
    if valid:
        reconstructed, zigzags = residual_model(values, e)
        choices = []
        for k in range(16):
            if all((z >> k) <= 31 for z in zigzags):
                significant = 16 + sum((z >> k) + 1 + k for z in zigzags)
                choices.append((significant, k))
        significant, k = min(choices) if choices else (65535, 0)
        raw = not choices or (significant + 7) // 8 >= 2 * n
        if force_mode is not None:
            raw = force_mode == "raw"
        if force_k is not None:
            k = force_k
        if raw:
            settings |= 8
            significant = 16 * n
            code = b"".join(word(value, 2) for value in values)
            reconstructed = list(values)
        else:
            settings |= k << 4
            significant, code = rice_code(values[0], zigzags, k)
    else:
        settings |= 8
        significant, code, reconstructed = 0, b"", [None] * n
    if significant > 255:
        raise ValueError("test construction exceeds one-byte bit count")
    prefix = bytes((1, settings, quality, n, significant))
    prefix += word(BOUND["session"], 4) + word(index, 4) + word(tick, 8)
    return prefix + optional + code, reconstructed


def frame(body, sequence, bound=BOUND):
    """Fixture header/CRC construction from normative byte offsets."""
    tick = int.from_bytes(body[13:21], "little")
    head = b"\xa5\x5a" + bytes((3, 7, len(body), bound["config_epoch"]))
    head += word(sequence, 2) + word(tick & 0xFFFFFFFF, 4)
    covered = head[2:] + body
    return head + body + word(binascii.crc_hqx(covered, 0xFFFF), 2)


class TargetedReview(unittest.TestCase):
    def rejects(self, body, *, e=0):
        with self.assertRaises(C.Reject):
            C.decode_payload(body, {**BOUND, "e": e})

    def accepts(self, body, expected, *, e=0):
        record = C.decode_payload(body, {**BOUND, "e": e})
        self.assertEqual([point["value"] for point in record["points"]], expected)
        self.assertEqual(record["byte_ledger"]["payload_bytes"], len(body))
        self.assertEqual(record["byte_ledger"]["frame_bytes"], len(body) + 14)
        self.assertEqual(record["byte_ledger"]["line_bits_8n1"], 10 * (len(body) + 14))
        return record

    def test_canonical_selection_independent_grid(self):
        patterns = (
            [0], [0, 0], [0, 0, 0], [0, 1, 2, 4], [0, 8, 16],
            [0, 64], [0, 2048, 4096], [0, 1, -1, 2], [0, -7, 5, -3],
            [0, 15, 31], [0, 32768], [0, 1, 0, 1, 0],
        )
        accepted = raw = rice = noncanonical_raw = nonoptimal_k = 0
        for e in (0, 1, 2, 4, 8):
            for anchor in (0, 9, 10000, 65526, 65535):
                for offsets in patterns:
                    values = [min(65535, max(0, anchor + delta)) for delta in offsets]
                    body, expected = payload(values, e=e)
                    if len(body) > 32:
                        continue
                    with self.subTest(e=e, values=values):
                        record = self.accepts(body, expected, e=e)
                        accepted += 1
                        raw += record["mode"] == "raw"
                        rice += record["mode"] == "rice"
                        self.assertTrue(all(abs(x - y) <= e for x, y in zip(values, expected)))
                        if record["mode"] == "rice":
                            false_raw, _ = payload(values, e=e, force_mode="raw")
                            if len(false_raw) <= 32:
                                self.rejects(false_raw, e=e)
                                noncanonical_raw += 1
                            _, zigzags = residual_model(values, e)
                            alternate = next((k for k in range(16)
                                              if k != record["k"] and
                                              all((z >> k) <= 31 for z in zigzags) and
                                              16 + sum((z >> k) + 1 + k for z in zigzags) <= 56), None)
                            if alternate is not None:
                                bad, _ = payload(values, e=e, force_mode="rice", force_k=alternate)
                                if len(bad) <= 32:
                                    self.rejects(bad, e=e)
                                    nonoptimal_k += 1
        METRICS["canonical_grid"] = dict(accepted=accepted, raw=raw, rice=rice,
                                           noncanonical_raw_rejected=noncanonical_raw,
                                           nonoptimal_k_rejected=nonoptimal_k)

    def test_explicit_ties_tc01_padding_and_impossible_residuals(self):
        for values, k, significant in (([10000, 10001, 10002, 10004], 1, 26),
                                       ([0, 8, 16], 3, 28)):
            body, expected = payload(values)
            record = self.accepts(body, expected)
            self.assertEqual((record["mode"], record["k"], record["significant_bits"]),
                             ("rice", k, significant))
            bad, _ = payload(values, force_mode="rice", force_k=k - 1)
            self.rejects(bad)
            if significant % 8:
                corrupt = body[:-1] + bytes((body[-1] | 1,))
                self.rejects(corrupt)
        for values, tie_k in (([0, 64], 6), ([0, 2048, 4096], 11)):
            body, expected = payload(values)
            record = self.accepts(body, expected)
            self.assertEqual(record["mode"], "raw")
            bad, _ = payload(values, force_mode="rice", force_k=tie_k)
            self.rejects(bad)
        # A residual that clamps to 65535 but has no possible uint16 source
        # under the normative quantizer must not become an accepted alias.
        prefix, _ = payload([65535, 65535, 65535])
        significant, code = rice_code(65535, [2, 0], 0)
        bad = bytearray(prefix[:25]); bad[4] = significant
        self.rejects(bytes(bad) + code)
        METRICS["explicit_canonical_boundaries"] = 11

    def test_held_source_age_boundaries_and_constant_origin(self):
        cases = ((1, 0, False), (65535, 0, False), (65536, 0, True),
                 ((1 << 64) - 1, (1 << 64) - 65536, False),
                 ((1 << 64) - 1, 0, True))
        for tick, origin, long_form in cases:
            body, expected = payload([1234], tick=tick, held=True, origin=origin)
            record = self.accepts(body, expected)
            self.assertEqual(bool(body[2] & 64), long_form)
            self.assertEqual(record["points"][0]["source_tick_ms"], origin)
            self.assertEqual(record["points"][0]["tick_ms"], tick)
        for tick, age in ((0, 1), (1, 2), (65534, 65535), (100, 0)):
            body, _ = payload([1234], tick=max(tick, 1), held=True, origin=0)
            malformed = bytearray(body[:21]); malformed[2] &= ~64
            malformed[13:21] = word(tick, 8)
            self.rejects(bytes(malformed) + word(age, 2) + word(1234, 2))
        for tick, origin in ((65535, 0), (65536, 1), (100, 100), (100, 101)):
            body, _ = payload([1234], tick=65536, held=True, origin=0)
            malformed = bytearray(body); malformed[13:21] = word(tick, 8)
            malformed[21:29] = word(origin, 8)
            self.rejects(bytes(malformed))
        body, expected = payload([100, 100], tick=65535, held=True, origin=0, tick_stride=65535)
        record = self.accepts(body, expected)
        self.assertFalse(body[2] & 64)
        self.assertEqual([point["source_tick_ms"] for point in record["points"]], [0, 0])
        self.assertEqual([point["tick_ms"] for point in record["points"]], [65535, 131070])
        METRICS["held_metadata"] = dict(positive=6, negative=8)

    def test_progression_masks_and_length_metadata(self):
        for channel in range(4):
            body, expected = payload(None, count=128, channel=channel, index=0, tick=0,
                                     index_stride=65535, tick_stride=65535, source_fault=True)
            record = self.accepts(body, expected)
            self.assertEqual(len(record["points"]), 128)
            for j, point in enumerate(record["points"]):
                self.assertEqual(point, dict(index=j * 65535, tick_ms=j * 65535,
                                            value=None, valid=False, saturated=False,
                                            held=False, source_fault=True, source_tick_ms=None))
            for invalid_flag in (8, 16, 64, 128):
                bad = bytearray(body); bad[2] |= invalid_flag
                self.rejects(bytes(bad))
        body, expected = payload([1234, 65535, 42], saturated=True, source_fault=True)
        record = self.accepts(body, expected)
        self.assertTrue(all(point["saturated"] and point["source_fault"] for point in record["points"]))
        for index, tick in (((1 << 32) - 1, 0), (0, (1 << 64) - 1)):
            body, _ = payload([100, 100], index=index, tick=tick)
            self.rejects(body)
        body, expected = payload([100, 100], index=(1 << 32) - 2, tick=(1 << 64) - 11)
        self.accepts(body, expected)
        valid, _ = payload([100])
        self.rejects(valid[:21] + word(1, 2) + word(1, 2) + valid[21:])
        for changed in (valid[:-1], valid + b"\x00"):
            self.rejects(changed)
        METRICS["progression_mask_metadata"] = dict(positive=6, negative=21)

    def test_cross_channel_highwaters_invalid_acquisitions_and_recovery(self):
        receiver = C.CandidateReceiver(BOUND)
        checks = 0

        def accept(body, sequence):
            nonlocal checks
            record = receiver.accept(frame(body, sequence)); checks += 1
            self.assertEqual(record["status"], "accepted")
            return record

        def unchanged_rejection(body, sequence):
            nonlocal checks
            before = receiver.state_snapshot()
            with self.assertRaises(C.Reject):
                receiver.accept(frame(body, sequence))
            self.assertEqual(receiver.state_snapshot(), before); checks += 1

        accept(payload([100], channel=0)[0], 0)
        accept(payload([100], channel=1)[0], 1)  # equal cross-channel origins legal
        unchanged_rejection(payload([100], channel=0, index=1, tick=0)[0], 2)
        accept(payload([100], channel=1, index=1, tick=1)[0], 2)
        accept(payload([100, 100, 100], channel=0, index=1, tick=10,
                       index_stride=4, tick_stride=10)[0], 3)
        for index, tick in ((8, 31), (10, 30), (0, 100)):
            unchanged_rejection(payload([100], channel=0, index=index, tick=tick)[0], 4)
        accept(payload([100], channel=0, index=10, tick=31)[0], 4)
        accept(payload([100], channel=3, index=9, tick=30)[0], 5)
        accept(payload(None, count=128, channel=2, index_stride=65535,
                       tick_stride=65535, source_fault=True)[0], 6)
        last = 127 * 65535
        unchanged_rejection(payload([100], channel=2, index=last, tick=last + 1)[0], 7)
        accept(payload([100], channel=2, index=last + 1, tick=last + 1)[0], 7)
        accept(payload([100], channel=0, index=11, tick=32, held=True, origin=0)[0], 8)
        # Nonwrapping acquisition high waters, independent from frame sequence.
        accept(payload([100], channel=3, index=(1 << 32) - 1, tick=(1 << 64) - 1)[0], 9)
        unchanged_rejection(payload([100], channel=3, index=0, tick=0)[0], 10)
        accept(payload([100], channel=0, index=12, tick=(1 << 32) - 1)[0], 10)
        accept(payload([100], channel=0, index=13, tick=1 << 32)[0], 11)
        METRICS["highwater_atomic_recovery_checks"] = checks


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TargetedReview)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    (HERE / "metrics.json").write_text(json.dumps(METRICS, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(not result.wasSuccessful())

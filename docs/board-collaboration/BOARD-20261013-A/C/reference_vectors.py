#!/usr/bin/env python3
"""Deterministic reference-vector generator for BOARD-20261013-A/C.

Emits exactly one JSON document on stdout and nothing else.
Standard library only (json, random, sys); pynq is never imported and no
hardware, board, or network access is performed by this script.
"""

import json
import random
import sys

REFERENCE_BASE = 0x40000000
REFERENCE_SIZE = 65536
OFFSET_BASE = 0xFC00
WORD_BYTES = 4
WORD_COUNT = 16
PATTERN_COUNT = 8
RNG_SEED = 0x20261013
ROUNDS = 3
MASK32 = 0xFFFFFFFF


def hex32(value):
    return "0x{:08x}".format(value & MASK32)


def hex16(value):
    return "0x{:04x}".format(value)


def build_word_slots():
    slots = []
    for index in range(WORD_COUNT):
        offset = OFFSET_BASE + WORD_BYTES * index
        address = REFERENCE_BASE + offset
        slots.append(
            {
                "index": index,
                "offset": offset,
                "offset_hex": hex16(offset),
                "addr": address,
                "addr_hex": hex32(address),
            }
        )
    return slots


def build_pattern_table(word_slots):
    rng = random.Random(RNG_SEED)
    random_words = [rng.getrandbits(32) for _ in range(WORD_COUNT)]
    definitions = [
        ("all0", "0x00000000 for every index", lambda index: 0x00000000),
        ("allFFFFFFFF", "0xFFFFFFFF for every index", lambda index: MASK32),
        ("all55555555", "0x55555555 for every index", lambda index: 0x55555555),
        ("allAAAAAAAA", "0xAAAAAAAA for every index", lambda index: 0xAAAAAAAA),
        ("A5A50000_or_i", "0xA5A50000 | i", lambda index: 0xA5A50000 | index),
        ("invert_A5A50000_or_i", "(~(0xA5A50000 | i)) & 0xffffffff", lambda index: (~(0xA5A50000 | index)) & MASK32),
        ("one_shl_i", "1 << i", lambda index: 1 << index),
        ("random_seed_20261013", "random.Random(0x20261013).getrandbits(32) called 16 times in index order", lambda index: random_words[index]),
    ]
    patterns = []
    for pattern_index, (name, definition, compute) in enumerate(definitions):
        words = []
        for index in range(WORD_COUNT):
            value = compute(index) & MASK32
            slot = word_slots[index]
            words.append(
                {
                    "index": index,
                    "addr": slot["addr"],
                    "addr_hex": slot["addr_hex"],
                    "value": value,
                    "value_hex": hex32(value),
                }
            )
        patterns.append(
            {
                "pattern_index": pattern_index,
                "name": name,
                "definition": definition,
                "word_count": WORD_COUNT,
                "words": words,
            }
        )
    return patterns


def build_document():
    word_slots = build_word_slots()
    pattern_table = build_pattern_table(word_slots)
    first_slot = word_slots[0]
    last_slot = word_slots[WORD_COUNT - 1]
    last_occupied_byte = last_slot["addr"] + WORD_BYTES - 1
    words_per_round = PATTERN_COUNT * WORD_COUNT
    comparisons_expected = ROUNDS * words_per_round
    return {
        "schema": "board-collaboration/BOARD-20261013-A/C/reference-vectors/v1",
        "purpose": "Deterministic reference word values emitted for later comparison; generation only, no hardware access, no board results, no acceptance decision.",
        "generator": {
            "script": "reference_vectors.py",
            "repo_relative_path": "docs/board-collaboration/BOARD-20261013-A/C/reference_vectors.py",
            "stdlib_only": True,
            "imports": ["json", "random", "sys"],
            "imports_pynq": False,
            "hardware_access": False,
            "network_access": False,
            "deterministic": True,
            "embedded_timestamp": False,
            "stdout_encoding": "utf-8",
            "stdout_newline": "LF",
        },
        "reference_metadata": {
            "base_addr": REFERENCE_BASE,
            "base_addr_hex": hex32(REFERENCE_BASE),
            "size_bytes": REFERENCE_SIZE,
            "offset_base": OFFSET_BASE,
            "offset_base_hex": hex16(OFFSET_BASE),
            "stride_bytes": WORD_BYTES,
            "word_bytes": WORD_BYTES,
            "word_count": WORD_COUNT,
            "index_first": 0,
            "index_last": WORD_COUNT - 1,
            "first_word_addr": first_slot["addr"],
            "first_word_addr_hex": first_slot["addr_hex"],
            "last_word_addr": last_slot["addr"],
            "last_word_addr_hex": last_slot["addr_hex"],
            "last_occupied_byte": last_occupied_byte,
            "last_occupied_byte_hex": hex32(last_occupied_byte),
            "region_end_exclusive": REFERENCE_BASE + REFERENCE_SIZE,
            "region_end_exclusive_hex": hex32(REFERENCE_BASE + REFERENCE_SIZE),
            "metadata_only": True,
            "disclaimer": "base_addr and size_bytes are expected metadata values recorded for reference comparison only. They are not authorization to access any address, and this artifact performs and claims no hardware access.",
        },
        "rng_convention": {
            "seed": RNG_SEED,
            "seed_hex": hex32(RNG_SEED),
            "construction": "random.Random(0x20261013) is constructed exactly once per script run",
            "call": "getrandbits(32)",
            "call_count": WORD_COUNT,
            "call_order": "index order 0..15; the first call feeds index 0 and the sixteenth call feeds index 15",
            "table_build": "the pattern table is generated once per run from these 16 values",
            "replay": "rounds 0, 1, and 2 replay the identical pattern table; the RNG is not reset, re-seeded, re-constructed, or called again between rounds or between patterns",
            "rng_reset_between_rounds": False,
            "rng_reset_between_patterns": False,
            "comparison_note": "the recorded values in this document are authoritative; any comparison protocol that reseeds or re-calls the RNG per round differs from this convention and must be reconciled explicitly instead of assumed",
        },
        "pattern_count": PATTERN_COUNT,
        "words_per_pattern": WORD_COUNT,
        "words_per_round": words_per_round,
        "rounds": ROUNDS,
        "round_plan": [
            {"round_index": 0, "table": "pattern_table", "comparisons": words_per_round},
            {"round_index": 1, "table": "pattern_table", "comparisons": words_per_round},
            {"round_index": 2, "table": "pattern_table", "comparisons": words_per_round},
        ],
        "comparisons_expected": comparisons_expected,
        "comparisons_derivation": "8 patterns x 16 words = 128 word comparisons per round; 128 x 3 rounds = 384",
        "comparison_semantics": "one expected comparison is one (address, value) 32-bit word pair as listed under pattern_table, checked once per round",
        "word_slots": word_slots,
        "pattern_table": pattern_table,
    }


def main():
    if "pynq" in sys.modules:
        raise SystemExit("pynq must not be imported by this generator")
    document = build_document()
    payload = json.dumps(document, indent=2, ensure_ascii=True) + "\n"
    sys.stdout.buffer.write(payload.encode("utf-8"))


if __name__ == "__main__":
    main()

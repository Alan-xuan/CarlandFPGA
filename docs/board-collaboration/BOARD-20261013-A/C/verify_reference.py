"""Hardware-free independent checks for the committed C reference table."""
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys


def main():
    folder = Path(__file__).resolve().parent
    raw = (folder / "reference-vectors.json").read_bytes()
    generated = subprocess.run(
        [sys.executable, "-B", str(folder / "reference_vectors.py")],
        capture_output=True, check=True,
    )
    assert raw == generated.stdout, "reference does not match generator bytes"
    data = json.loads(raw)
    rng = random.Random(0x20261013)
    expected = [
        [0] * 16, [4294967295] * 16, [1431655765] * 16,
        [2863311530] * 16,
        [2779054080 + i for i in range(16)],
        [1515913215 - i for i in range(16)],
        [2**i for i in range(16)],
        [rng.getrandbits(32) for _ in range(16)],
    ]
    assert len(data["pattern_table"]) == 8
    for p, values in zip(data["pattern_table"], expected):
        assert len(p["words"]) == 16
        assert [w["value"] for w in p["words"]] == values
        for i, word in enumerate(p["words"]):
            assert word["index"] == i
            assert word["addr"] == 1073806336 + 4 * i
            assert word["addr"] % 4 == 0
            assert 0x40000000 <= word["addr"] <= 0x40010000 - 4
    assert data["rounds"] == 3
    assert data["comparisons_expected"] == 384
    assert data["reference_metadata"]["last_occupied_byte"] == 0x4000FC3F
    assert data["word_slots"][-1]["offset"] + 4 == 0xFC40
    print("C independent reference verification: passed")
    print("python=" + sys.version.replace("\n", " "))
    print("values_checked=128; rounds=3; comparisons=384")
    print("window=[0x4000fc00,0x4000fc40); aperture=[0x40000000,0x40010000)")
    print("generated_bytes_match=true; sha256=" + hashlib.sha256(raw).hexdigest())
    print("hardware=not_run; RTL_simulation=not_run; synthesis=not_run; implementation=not_run")


if __name__ == "__main__":
    main()

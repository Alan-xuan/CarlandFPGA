"""Phase1 stdlib-only independent scalar and saved-evidence oracle; no product imports."""
import base64, hashlib, json, math, struct, sys
from datetime import datetime, timezone
from pathlib import Path

NODE = Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c")
WT = NODE / ".local/deepeye-implementation-c"
OUT = Path(__file__).resolve().parent
MODEL = WT / "competition/deepeye/ai_pc/cpu_model/force_v1"
PIN = "0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959"
BASELINE = WT / "competition/deepeye/evidence/ai/cpu_package_20261024/cpu-baseline/prediction-result.json"
SNAPSHOT = NODE / ".local/main-20261015-01a14025/watch-20261018/observer/run/snapshots/github-25-20261025T092001.413465Z-a26a469b.json"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def emit(name, obj):
    with (OUT / name).open("xb") as f:
        f.write((json.dumps(obj, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode())
        f.flush()
        import os
        os.fsync(f.fileno())

expected = {
    "competition/deepeye/ai_pc/cpu_package/runner.py": "92114790259b7e35e8bf7b1a0519f0e3f68da52729d08b5b9862c992deae70af",
    "competition/deepeye/ai_pc/model/curve_input.py": "c017729a2d5717ff2bbf5a6c591320519c415ac10068b4cee19b3136913d848c",
    "competition/deepeye/ai_pc/model/force_cnn.py": "5003427e1ac01e50b612d8f4f9c674c7df352b3942a5cc39978e23bdfbdb1260",
    "competition/deepeye/ai_pc/cpu_model/force_v1/model_manifest.json": PIN,
    "competition/deepeye/ai_pc/cpu_model/force_v1/graph.json": "6fd93fab7e65b56b1cd9473475c54b071b3e82ff09549ee447675988f07efee2",
    "competition/deepeye/ai_pc/cpu_model/force_v1/weights.json": "8988f4bbcf425d9b48c9a62866ac350e6096ea43fabdd9b1e616b22ba4b6d187",
    "competition/deepeye/data/preprocessing.json": "cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef",
    "competition/deepeye/data/label_schema.json": "0913ff5a59085b47802a9902f23a836f4fa1129700de8e6593840416f4d7beed",
    str(BASELINE.relative_to(WT)).replace("\\", "/"): "e84bdfe850efb8a231f72c98a5fb05cc20c7f6036014f4db77ef3f6cf44b418f",
}
pins = []
for rel, digest in expected.items():
    b = (WT / rel).read_bytes()
    actual = sha(b)
    assert actual == digest, (rel, actual)
    pins.append({"path": str(WT / rel), "bytes": len(b), "sha256": actual})
print("PINNED", len(pins), "unchanged saved inputs")

def walk(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk(v)

snapshot_bytes = SNAPSHOT.read_bytes()
matches = [x for x in walk(json.loads(snapshot_bytes)) if x.get("id") == 6395841435 and "body" in x]
assert len(matches) == 1, len(matches)
comment = matches[0]
assert comment["user"]["login"] == "carolwjade"
assert "A-C19-CPU-READBACK-STREAM-NEXT-20261025-v1" in comment["body"]
assert "\ufffd" not in comment["body"], "A source contains replacement characters"
source = {
    "snapshot_path": str(SNAPSHOT), "snapshot_sha256": sha(snapshot_bytes),
    "source_comment_url": "https://github.com/carolwjade/CarlandFPGA/pull/25#issuecomment-6395841435",
    "id": comment["id"], "author": comment["user"]["login"],
    "created_at": comment["created_at"], "updated_at": comment["updated_at"],
    "body_sha256_utf8": sha(comment["body"].encode("utf8")),
    "unicode_replacement_character_count": comment["body"].count("\ufffd"),
    "body": comment["body"],
}
emit("A-source-comment.json", source)
emit("source-pins.json", pins)

scaler = json.loads((WT / "competition/deepeye/data/preprocessing.json").read_bytes())
stats = scaler["channels"]
assert [s["name"] for s in stats] == ["GR", "RHOB", "NPHI", "RDEP"]
saved = json.loads(BASELINE.read_bytes())["predictions"]
lines, rows = [], []
with (MODEL / "public_input.jsonl").open("rb") as f:
    for _ in range(3):
        line = f.readline(16385)
        assert 0 < len(line) <= 16384
        lines.append(line)
        rows.append(json.loads(line))
assert [r["sequence"] for r in rows] == [7327, 7328, 7329]
prefix = hashlib.sha256()
selected = []
for i, (line, row) in enumerate(zip(lines, rows)):
    prefix.update(line)
    channels = [[0.0] * 128 for _ in range(8)]
    for k, observation in enumerate(rows[:i + 1], start=128 - i - 1):
        for c in range(4):
            value = observation["value_" + str(c)]
            valid = observation["valid_" + str(c)]
            usable = valid and value is not None and (c != 3 or value > 0)
            if usable:
                transformed = math.log10(value) if c == 3 else value
                channels[c][k] = (transformed - stats[c]["mean"]) / stats[c]["effective_scale"]
                channels[c + 4][k] = 1.0
    tensor_bytes = struct.pack("<1024f", *(v for channel in channels for v in channel))
    feature = sha(tensor_bytes)
    original = saved[i]
    assert original["record_index"] == i
    assert original["input_prefix_sha256"] == prefix.hexdigest()
    assert original["feature_tensor_sha256"] == feature
    assert original["window"]["latest_sequence"] == row["sequence"]
    assert original["window"]["filled_slots"] == i + 1
    assert original["window"]["missing_slots"] == 127 - i
    assert original["movement_authorized"] is False
    selected.append({
        "raw_bytes_base64": base64.b64encode(line).decode(),
        "raw_bytes_sha256": sha(line), "raw_bytes_length": len(line),
        "independent_scalar_feature_sha256": feature,
        "saved_prediction": original,
    })
print("PASS: first 3 exact-byte prefix hashes and scalar-only float32 feature hashes match saved C19")

# Same observation values/binding/sequence, byte representation changes.
canonical_line = (json.dumps(rows[0], sort_keys=True, separators=(",", ":")) + "\n").encode()
duplicate_cases = {
    "first_original": sha(lines[0]),
    "original_then_exact_duplicate": sha(lines[0] + lines[0]),
    "original_then_reencoded_semantic_duplicate": sha(lines[0] + canonical_line),
}
assert len(set(duplicate_cases.values())) == 3
overflow = (1e45 - stats[0]["mean"]) / stats[0]["effective_scale"]
f32max = struct.unpack("<f", bytes.fromhex("ffff7f7f"))[0]
assert math.isfinite(overflow) and overflow > f32max

# uint64 gap has no dependency on magnitude beyond min(gap,127).
max_seq = 2**64 - 1
gap_slots = min(max_seq - 0 - 1, 127)
assert gap_slots == 127
# First seq0 row plus127gap slots pluslastrow leaves onlylastrow.
huge_gap = {"first_sequence": 0, "next_sequence": max_seq,
            "inserted_missing_slots": gap_slots, "history_bound": 128,
            "filled_slots_after": 1, "missing_slots_after": 127,
            "sequence_must_not_round_via_float": max_seq != int(float(max_seq))}
assert huge_gap["sequence_must_not_round_via_float"]

oracle = {
    "work_id": "C-CPU-STREAM-INDEPENDENT-REVIEW-20261025-v1",
    "phase": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
    "kind": "stdlib scalar and saved evidence only; no stream source/model execution",
    "selected_records": selected,
    "duplicate_prefix_controls": duplicate_cases,
    "overflow_control": {"GR_value": 1e45, "normalized_double": overflow,
                         "float32_max": f32max,
                         "expectation": "builder-double valid but tensor conversion/finite check must reject atomically"},
    "huge_gap_control": huge_gap,
    "quality": {"fixed12_test_macro_f1": 0.1827348057438266,
                "centroid_fixed12_test_macro_f1": 0.2047004573101128,
                "threshold": 0.60, "status": "FAIL; unchanged; not reevaluated"},
    "not_executed": ["new stream code/import", "Torch/model forward", "old suites",
                     "train/heldout", "archive", "all128 baseline", "network/board"],
}
emit("phase1-oracles.json", oracle)
print("PASS: exact duplicate/reencoded prefix distinction; double-to-float32 overflow; bounded uint64 gap oracle")
print("NO model import/forward; NO new source read; NO active jobs")


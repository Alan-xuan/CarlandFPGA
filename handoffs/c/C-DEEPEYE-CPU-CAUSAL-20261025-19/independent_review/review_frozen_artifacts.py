"""Independent released-byte audit and one real fixed-window CPU control.

Never imports author tests/trainer/runner or opens the FORCE archive.
"""
from collections import Counter
import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c")
WORK = ROOT / ".local/main-20261015-01a14025/cpu-package-20261024"
REPO = ROOT / ".local/deepeye-implementation-c"
PRODUCT = REPO / "competition/deepeye"
OUT = WORK / "cpu_independent_review/final"
TRAIN = PRODUCT / "evidence/ai/force_cpu_training_20261024"
MODEL = PRODUCT / "ai_pc/cpu_model/force_v1"
RUNNER_EVIDENCE = PRODUCT / "evidence/ai/cpu_package_20261024"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def doc(path):
    return json.loads(path.read_text(encoding="utf-8"))

def pin(path, expected):
    actual = sha(path)
    assert actual == expected, (str(path), actual, expected)
    return actual

def audit_manifest(path, base, key, count, expected=None):
    if expected:
        pin(path, expected)
    manifest = doc(path)
    records = manifest[key]
    assert len(records) == count
    assert len({item["path"] for item in records}) == count
    for item in records:
        target = base / item["path"]
        assert target.resolve().is_relative_to(base.resolve()), item["path"]
        assert target.stat().st_size == item["bytes"], item["path"]
        pin(target, item["sha256"])
    return {"manifest_sha256": sha(path), "verified_files": count}

trainer_manifest = WORK / "force_cpu_model/delivery-manifest.json"
assert sha(trainer_manifest).startswith("44e9fa")
trainer_verification = audit_manifest(trainer_manifest, PRODUCT, "files", 69)
runner_verification = audit_manifest(RUNNER_EVIDENCE / "delivery-manifest.json", REPO, "artifacts", 41, "9fc1dfc5c048e379b53da9a3dc9ca1ccf5dac288c6ad3be12dd96e2eace8c6c2")
manifest_sha = pin(MODEL / "model_manifest.json", "0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959")
pin(MODEL / "graph.json", "6fd93fab7e65b56b1cd9473475c54b071b3e82ff09549ee447675988f07efee2")
pin(MODEL / "weights.json", "8988f4bbcf425d9b48c9a62866ac350e6096ea43fabdd9b1e616b22ba4b6d187")
fixture_sha = pin(MODEL / "public_input.jsonl", "d81b29a6200d83133eda22149c70d2a0f6b3db06f9885ae669ddaffc75e99b37")
pin(PRODUCT / "ai_pc/model/force_cnn.py", "5003427e1ac01e50b612d8f4f9c674c7df352b3942a5cc39978e23bdfbdb1260")
pin(PRODUCT / "ai_pc/cpu_package/runner.py", "92114790259b7e35e8bf7b1a0519f0e3f68da52729d08b5b9862c992deae70af")
pin(PRODUCT / "ai_pc/model/curve_input.py", "c017729a2d5717ff2bbf5a6c591320519c415ac10068b4cee19b3136913d848c")
preprocessing_sha = pin(PRODUCT / "data/preprocessing.json", "cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef")
saved_output_path = RUNNER_EVIDENCE / "cpu-baseline/prediction-result.json"
pin(saved_output_path, "e84bdfe850efb8a231f72c98a5fb05cc20c7f6036014f4db77ef3f6cf44b418f")

command = doc(WORK / "force_cpu_model/train-01.result.json")
assert command["exit_code"] == 0
for stream in ("stdout", "stderr"):
    path = WORK / ("force_cpu_model/train-01." + stream + ".txt")
    assert path.stat().st_size == command[stream]["bytes"]
    pin(path, command[stream]["sha256"])
events = [json.loads(line) for line in (WORK / "force_cpu_model/train-01.stdout.txt").read_text(encoding="utf-8").splitlines() if line]
epochs = [event for event in events if event["event"] == "epoch_complete"]
assert [event["epoch"] for event in epochs] == [1, 2, 3, 4, 5]
freeze_indices = [i for i, event in enumerate(events) if event["event"] == "model_frozen_before_test"]
assert len(freeze_indices) == 1
freeze_index = freeze_indices[0]
assert all(i < freeze_index for i, event in enumerate(events) if event["event"] == "epoch_complete")
prepared = [(i, event) for i, event in enumerate(events) if event["event"] == "prepared_well"]
assert Counter(event["split"] for _, event in prepared) == {"train": 82, "validation": 17, "test": 19}
assert all(i > freeze_index for i, event in prepared if event["split"] == "test")
assert all(i < freeze_index for i, event in prepared if event["split"] != "test")
assert events[-1]["event"] == "training_complete"
assert sum(event["event"] == "training_complete" for event in events) == 1
freeze = doc(TRAIN / "freeze-before-test.json")
graph_freeze = doc(TRAIN / "graph-freeze-before-optimizer.json")
assert not freeze["test_members_opened"] and freeze["selection_complete"]
assert freeze["manifest_sha256"] == manifest_sha
assert graph_freeze["optimizer_steps"] == 0 and not graph_freeze["test_members_opened"]
assert graph_freeze["graph_sha256"] == sha(MODEL / "graph.json")
assert datetime.datetime.fromisoformat(graph_freeze["frozen_utc"]) < datetime.datetime.fromisoformat(freeze["frozen_utc"])
pre_journal = doc(TRAIN / "pre-test-open-journal.json")
post_journal = doc(TRAIN / "source-open-journal.json")
assert not pre_journal["test_opened"] and set(pre_journal["opened_splits"]) == {"train", "validation"}
assert Counter(row["split"] for row in pre_journal["members"]) == {"train": 82, "validation": 17}
assert Counter(row["split"] for row in post_journal["members"]) == {"train": 82, "validation": 17, "test": 19}
assert post_journal["members"][:99] == pre_journal["members"]
assert post_journal["test_open_after_freeze"] is True
model_manifest = doc(MODEL / "model_manifest.json")
selected = max(epochs, key=lambda item: item["validation_macro_f1_fixed12"])
assert selected["epoch"] == model_manifest["training"]["selected_epoch"] == 5

def recompute(matrix):
    assert len(matrix) == 12 and all(len(row) == 12 for row in matrix)
    assert all(type(value) is int and value >= 0 for row in matrix for value in row)
    supports = list(map(sum, matrix))
    predicted = [sum(row[index] for row in matrix) for index in range(12)]
    true_positive = [matrix[index][index] for index in range(12)]
    f1 = [2 * tp / (support + prediction) if support + prediction else 0.0 for tp, support, prediction in zip(true_positive, supports, predicted)]
    return {"supports": supports, "predicted": predicted, "true_positive": true_positive, "f1": f1, "macro_f1_fixed12": sum(f1) / 12, "samples": sum(supports)}

metrics = doc(TRAIN / "heldout_metrics.json")
computed_metrics = {}
for name in ("test_model", "test_current_vector_centroid", "test_majority"):
    saved = metrics[name]
    computed = recompute(saved["confusion_true_rows_predicted_columns"])
    assert computed["samples"] == saved["samples"] == 244176
    assert computed["macro_f1_fixed12"] == saved["macro_f1_fixed12"]
    for index, per_class in enumerate(saved["per_class"]):
        for key, computed_key in (("support", "supports"), ("predicted", "predicted"), ("true_positive", "true_positive"), ("f1", "f1")):
            assert per_class[key] == computed[computed_key][index]
    wells = saved["per_well"]
    assert len(wells) == 19 and len({well["well_id"] for well in wells}) == 19
    sum_wells = [[sum(well["confusion_true_rows_predicted_columns"][i][j] for well in wells) for j in range(12)] for i in range(12)]
    assert sum_wells == saved["confusion_true_rows_predicted_columns"]
    computed_metrics[name] = computed
assert computed_metrics["test_model"]["macro_f1_fixed12"] < computed_metrics["test_current_vector_centroid"]["macro_f1_fixed12"]
assert computed_metrics["test_model"]["macro_f1_fixed12"] < 0.60
assert metrics["fixed12_macro_f1_target_met"] is False

# One actual fixed fixture check. Scalar normalization below is deliberately
# independent of CurveScaler.normalize, the training parser and runner helpers.
fixture_bytes = (MODEL / "public_input.jsonl").read_bytes()
observations = [json.loads(line) for line in fixture_bytes.splitlines()]
assert len(observations) == 128
assert [row["sequence"] for row in observations] == list(range(7327, 7455))
expected_keys = {"run_id", "source_domain", "profile_id", "preprocessing_sha256", "sequence"} | {prefix + str(i) for prefix in ("value_", "valid_") for i in range(4)}
assert all(set(row) == expected_keys for row in observations)
scaler_document = doc(PRODUCT / "data/preprocessing.json")
channels = scaler_document["channels"]
direct = [[] for _ in range(8)]
valid_counts = [0] * 4
for row in observations:
    for channel in range(4):
        value = row["value_" + str(channel)]
        valid = row["valid_" + str(channel)] and (channel != 3 or value > 0)
        normalized = 0.0
        if valid:
            transformed = math.log10(value) if channel == 3 else value
            normalized = (transformed - channels[channel]["mean"]) / channels[channel]["effective_scale"]
            valid_counts[channel] += 1
        direct[channel].append(normalized)
        direct[channel + 4].append(1.0 if valid else 0.0)
direct_bytes = struct.pack("<1024f", *(value for channel in direct for value in channel))
feature_sha = hashlib.sha256(direct_bytes).hexdigest()

sys.path.insert(0, str(PRODUCT))
import torch
from ai_pc.model.curve_input import CurveBinding, CurveScaler, CurveWindowBuilder
from ai_pc.model.force_cnn import build_model, load_frozen_model

torch.set_num_threads(4)
torch.set_num_interop_threads(1)
torch.use_deterministic_algorithms(True)
assert torch.__version__ == "2.9.0+cpu" and torch.version.cuda is None
scaler = CurveScaler((PRODUCT / "data/preprocessing.json").read_bytes(), expected_sha256=preprocessing_sha)
first = observations[0]
binding = CurveBinding(first["run_id"], first["source_domain"], preprocessing_sha)
builder = CurveWindowBuilder(scaler=scaler, binding=binding)
for observation in observations:
    builder.observe(observation)
window = builder.snapshot()
tensor = torch.tensor(window.to_model_input(), dtype=torch.float32)
builder_bytes = struct.pack("<1024f", *tensor.reshape(-1).tolist())
assert builder_bytes == direct_bytes
saved_prediction = doc(saved_output_path)["predictions"][-1]
assert feature_sha == saved_prediction["feature_tensor_sha256"]
assert saved_prediction["input_prefix_sha256"] == fixture_sha
assert saved_prediction["record_index"] == 127 and saved_prediction["window"]["latest_sequence"] == 7454

torch.manual_seed(20261024)
seeded_initial = build_model().state_dict()
loaded, _ = load_frozen_model(MODEL / "model_manifest.json", manifest_sha, device="cpu")
changed = {name: int(torch.count_nonzero(value - seeded_initial[name])) for name, value in loaded.state_dict().items()}
assert changed == model_manifest["training"]["learned_tensor_changed_elements_from_seeded_initialization"]
assert sum(changed.values()) == 4916
assert all(changed.values())
with torch.inference_mode():
    logits = loaded(tensor)
    probabilities = torch.softmax(logits, dim=1).tolist()[0]
assert tuple(logits.shape) == (1, 12) and bool(torch.isfinite(logits).all())
assert all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities)
assert abs(sum(probabilities) - 1) < 1e-5
differences = [abs(a - b) for a, b in zip(probabilities, saved_prediction["probabilities"])]
assert max(differences) <= 1e-7
assert max(range(12), key=probabilities.__getitem__) == saved_prediction["predicted_class_index"] == 2

result = {
    "recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "trainer_delivery": trainer_verification,
    "runner_delivery": runner_verification,
    "frozen_manifest_sha256": manifest_sha,
    "raw_train_exit_code": command["exit_code"],
    "exactly_five_epoch_events": True,
    "test_wells_opened_only_after_freeze_event": 19,
    "pre_freeze_members": 99,
    "graph_freeze_precedes_model_freeze": True,
    "validation_selection_epoch": selected["epoch"],
    "independently_recomputed_metrics": computed_metrics,
    "quality_target_failed": True,
    "cnn_worse_than_train_only_centroid": True,
    "real_fixture_control": {
        "observations": 128, "first_sequence": 7327, "last_sequence": 7454,
        "scalar_method": "frozen JSON means/effective_scale; identity GR/RHOB/NPHI; log10 positive RDEP; explicit masks; direct little-endian float32 packing",
        "valid_observation_counts": valid_counts,
        "direct_scalar_and_builder_float32_bytes_equal": True,
        "feature_tensor_sha256": feature_sha,
        "saved_runner_feature_sha_equal": True,
        "learned_tensor_changed_elements_from_seeded_initialization": changed,
        "learned_changed_elements_total": sum(changed.values()),
        "forward_calls": 1,
        "device": "cpu", "torch": torch.__version__, "python": sys.version,
        "logits": logits.tolist()[0], "probabilities": probabilities,
        "saved_runner_probability_max_absolute_difference": max(differences),
        "predicted_class_index": 2,
        "movement_authorized": False,
    },
    "scope": "saved-evidence arithmetic and one actual fixed offline FORCE window; no archive access, train, heldout evaluation, author test import or suite rerun; no sim_em/online AI/hardware acceptance",
}
(OUT / "review-result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
print(json.dumps({"trainer_files": 69, "runner_files": 41, "test_rows": 244176, "cnn_f1": computed_metrics["test_model"]["macro_f1_fixed12"], "centroid_f1": computed_metrics["test_current_vector_centroid"]["macro_f1_fixed12"], "feature_sha256": feature_sha, "changed_parameters": sum(changed.values()), "forward_calls": 1, "probability_difference": max(differences), "quality_target_failed": True}, sort_keys=True))

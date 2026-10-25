"""One bounded, reproducible FORCE-only CPU training run with safe JSON output.

Fixed recipe: seed 20261024, five epochs, Adam 0.001, batch256, train stride8,
sqrt-inverse class weighting, four CPU threads and no DataLoader workers.
Validation macro-F1 selects one epoch; test members are opened only after the
selected graph, weights and manifest are written and hashed. No test tuning.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import math
from pathlib import Path
import random
import sys
import time

_PRODUCT = Path(__file__).resolve().parents[1]
if str(_PRODUCT) not in sys.path:
    sys.path.insert(0, str(_PRODUCT))

import torch
from torch import nn
from ai_pc.force_training_data import ForceSource, ARCHIVE_SHA256, INVENTORY_SHA256, SPLITS_SHA256, PUBLIC_MEMBER, PUBLIC_ROWS
from ai_pc.model.force_cnn import MODEL_ID, PROFILE_ID, CLASS_ORDER, GRAPH, PREPROCESSING_SHA256, LABEL_SCHEMA_SHA256, build_model, export_weights, load_frozen_model, sha256_file

SEED = 20261024
EPOCHS = 5
BATCH = 256
TRAIN_STRIDE = 8


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def summarize(confusion):
    if isinstance(confusion, torch.Tensor):
        confusion = confusion.tolist()
    rows = []
    f1s = []
    supported = []
    total = sum(map(sum, confusion))
    correct = sum(confusion[i][i] for i in range(12))
    for index, code in enumerate(CLASS_ORDER):
        support = sum(confusion[index])
        predicted = sum(row[index] for row in confusion)
        tp = confusion[index][index]
        f1 = 2 * tp / (support + predicted) if support + predicted else 0.0
        f1s.append(f1)
        if support:
            supported.append(f1)
        rows.append({"index": index, "source_code": code, "support": support, "predicted": predicted, "true_positive": tp, "recall": tp / support if support else None, "precision": tp / predicted if predicted else None, "f1": f1})
    return {"samples": total, "accuracy": correct / total if total else None, "macro_f1_fixed12": sum(f1s) / 12, "supported_macro_f1_secondary": sum(supported) / len(supported) if supported else None, "per_class": rows, "confusion_true_rows_predicted_columns": confusion}


def _add_matrix(matrix, labels, predicted):
    matrix.add_(torch.bincount(labels * 12 + predicted, minlength=144).reshape(12, 12))


def evaluate(wells, predictor, *, with_probabilities=False, bootstrap=False):
    overall = torch.zeros((12, 12), dtype=torch.int64)
    by_confidence = {str(code): torch.zeros((12, 12), dtype=torch.int64) for code in (0, 1, 2, 3)}
    probability_bins = torch.zeros(10, dtype=torch.int64)
    per_well = []
    missing = 0
    started = time.perf_counter()
    with torch.inference_mode():
        for well in wells:
            local = torch.zeros((12, 12), dtype=torch.int64)
            indices = (well.targets >= 0).nonzero(as_tuple=True)[0]
            missing += well.targets.numel() - indices.numel()
            for batch in indices.split(512):
                labels = well.targets[batch]
                prediction = predictor(well, batch)
                if with_probabilities:
                    probabilities = torch.softmax(prediction, dim=1)
                    if not bool(torch.isfinite(probabilities).all()):
                        raise ValueError("nonfinite evaluated probability")
                    predicted = probabilities.argmax(1)
                    bins = torch.clamp((probabilities.max(1).values * 10).long(), max=9)
                    probability_bins.add_(torch.bincount(bins, minlength=10))
                else:
                    predicted = prediction
                _add_matrix(overall, labels, predicted)
                _add_matrix(local, labels, predicted)
                for code in (0, 1, 2, 3):
                    selection = well.confidence[batch] == code
                    _add_matrix(by_confidence[str(code)], labels[selection], predicted[selection])
            per_well.append({"well_id": well.well_id, "root_id": well.root_id, "member": well.member, **summarize(local)})
    result = {**summarize(overall), "missing_targets_retained_in_history": missing, "confidence_strata": {code: summarize(matrix) for code, matrix in by_confidence.items()}, "maximum_probability_bins_width_0_1": probability_bins.tolist() if with_probabilities else None, "per_well": per_well, "evaluation_seconds_not_batch1_latency": time.perf_counter() - started}
    if bootstrap:
        grouped = {}
        for item in per_well:
            key = item["root_id"]
            current = grouped.setdefault(key, [[0] * 12 for _ in range(12)])
            for i in range(12):
                for j in range(12):
                    current[i][j] += item["confusion_true_rows_predicted_columns"][i][j]
        matrices = list(grouped.values())
        rng = random.Random(SEED)
        scores = []
        for _ in range(200):
            selected = [matrices[rng.randrange(len(matrices))] for _ in matrices]
            combined = [[sum(matrix[i][j] for matrix in selected) for j in range(12)] for i in range(12)]
            scores.append(summarize(combined)["macro_f1_fixed12"])
        scores.sort()
        result["group_bootstrap_fixed12_macro_f1"] = {"unit": "complete parent well", "groups": len(matrices), "resamples": 200, "seed": SEED, "percentile_95_interval": [scores[4], scores[194]], "not_an_independent_external_test": True}
    return result


def scalar_baselines(train):
    counts = torch.zeros(12, dtype=torch.int64)
    sums = torch.zeros((12, 8), dtype=torch.float64)
    for well in train:
        selected = (well.targets >= 0).nonzero(as_tuple=True)[0]
        labels = well.targets[selected]
        current = well.features[:, selected + 127].T.double()
        counts.add_(torch.bincount(labels, minlength=12))
        sums.index_add_(0, labels, current)
    means = sums / counts.clamp_min(1).unsqueeze(1)
    majority = int(counts.argmax())
    def centroid(well, indices):
        current = well.features[:, indices + 127].T.double()
        distances = ((current[:, None, :] - means[None, :, :]) ** 2).sum(2)
        distances[:, counts == 0] = float("inf")
        return distances.argmin(1)
    def constant(well, indices):
        return torch.full((indices.numel(),), majority, dtype=torch.int64)
    return counts, means, majority, centroid, constant


def train(args):
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(SEED)
    random.seed(SEED)
    if torch.__version__ != "2.9.0+cpu" or torch.version.cuda is not None:
        raise ValueError("this recorded training recipe requires torch2.9.0+cpu")
    artifact = Path(args.artifact).resolve()
    evidence = Path(args.evidence).resolve()
    cache = Path(args.cache).resolve()
    if (artifact / "model_manifest.json").exists():
        raise ValueError("refuse repeated training over an existing frozen model")
    for directory in (artifact, evidence, cache):
        directory.mkdir(parents=True, exist_ok=True)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    recipe = {"work_id": "C-FORCE-CPU-CNN-20261024-v1", "seed": SEED, "epochs": EPOCHS, "batch_size": BATCH, "training_row_stride": TRAIN_STRIDE, "sampling": "every8th acquisition row of every TRAIN well, retain all positions in histories; no class filtering", "optimizer": "Adam", "learning_rate": 0.001, "class_weighting": "sqrt(total/count), mean normalized over supported TRAIN classes", "validation_selection": "maximum fixed12 macro-F1; first epoch wins ties", "test_selection": "none; source members first opened after frozen manifest", "threads": 4, "interop_threads": 1, "loader_workers": 0, "device": "cpu", "torch": torch.__version__, "python": sys.version, "deterministic_algorithms": True, "source_base_commit": "942fa309ffc8f1d32c816cfa643b009b031d7d0a", "started_utc": started}
    write_json(evidence / "recipe.json", recipe)
    source = ForceSource(args.archive)
    training = source.load_split("train")
    validation = source.load_split("validation")
    write_json(evidence / "pre-test-open-journal.json", {"opened_splits": sorted(source.opened_splits), "test_opened": False, "members": source.journal})
    write_json(evidence / "causal-window-equivalence.json", source.window_checks)
    if len(source.public_observations) != 128 or [item["sequence"] for item in source.public_observations] != list(range(PUBLIC_ROWS[0], PUBLIC_ROWS[1] + 1)):
        raise ValueError("fixed public sequence extraction failed")
    with (artifact / "public_input.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for item in source.public_observations:
            handle.write(json.dumps(item, allow_nan=False, separators=(",", ":")) + "\n")
    write_json(evidence / "public_input_evaluator_labels.json", {"not_online_input": True, "member": PUBLIC_MEMBER, "rows": list(PUBLIC_ROWS), "labels": source.public_labels})
    counts, means, majority, centroid, constant = scalar_baselines(training)
    write_json(evidence / "scalar_baselines.json", {"fit_split": "train only", "fit_rows": "all labeled TRAIN rows; CNN training uses stride8", "class_counts": counts.tolist(), "majority_class_index": majority, "majority_source_code": CLASS_ORDER[majority], "centroid_features": "current four normalized values plus four masks; no history", "centroids": means.tolist(), "validation_centroid": evaluate(validation, centroid), "validation_majority": evaluate(validation, constant)})
    sampled_counts = torch.zeros(12, dtype=torch.int64)
    eligible = []
    for well in training:
        indices = torch.arange(0, well.targets.numel(), TRAIN_STRIDE)
        indices = indices[well.targets[indices] >= 0]
        eligible.append(indices)
        sampled_counts.add_(torch.bincount(well.targets[indices], minlength=12))
    weights = torch.zeros(12)
    supported = sampled_counts > 0
    weights[supported] = torch.sqrt(sampled_counts.sum() / sampled_counts[supported].float())
    weights[supported] /= weights[supported].mean()
    model = build_model()
    graph = {"format": "fixed-force-cnn-graph-v1", "input_shape": ["N", 8, 128, 1], "output_shape": ["N", 12], "layers": GRAPH, "parameters": sum(p.numel() for p in model.parameters()), "source": {"path": "../../model/force_cnn.py", "sha256": sha256_file(_PRODUCT / "ai_pc/model/force_cnn.py")}}
    write_json(artifact / "graph.json", graph)
    frozen_graph_sha = sha256_file(artifact / "graph.json")
    write_json(evidence / "graph-freeze-before-optimizer.json", {"graph_sha256": frozen_graph_sha, "model_source_sha256": graph["source"]["sha256"], "optimizer_steps": 0, "architecture_selection": "fixed source before first bounded train; no search", "test_members_opened": False, "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    initial = {key: value.clone() for key, value in model.state_dict().items()}
    loss_function = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    history = []
    best_state, best_score, best_epoch = None, -1.0, None
    for epoch in range(1, EPOCHS + 1):
        model.train()
        generator = torch.Generator().manual_seed(SEED + epoch)
        well_order = torch.randperm(len(training), generator=generator).tolist()
        running, batches, trained_rows = 0.0, 0, 0
        epoch_start = time.perf_counter()
        for index in well_order:
            well = training[index]
            indices = eligible[index]
            shuffled = indices[torch.randperm(indices.numel(), generator=generator)]
            for batch in shuffled.split(BATCH):
                optimizer.zero_grad(set_to_none=True)
                logits = model(well.windows(batch))
                loss = loss_function(logits, well.targets[batch])
                if not bool(torch.isfinite(loss)):
                    raise ValueError("nonfinite training loss")
                loss.backward()
                optimizer.step()
                running += float(loss.detach()) * batch.numel()
                batches += 1
                trained_rows += batch.numel()
        model.eval()
        validation_result = evaluate(validation, lambda well, batch: model(well.windows(batch)), with_probabilities=True)
        score = validation_result["macro_f1_fixed12"]
        entry = {"epoch": epoch, "training_rows": trained_rows, "batches": batches, "weighted_batch_mean_loss": running / trained_rows, "validation": validation_result, "seconds": time.perf_counter() - epoch_start}
        history.append(entry)
        write_json(evidence / ("epoch-%02d.json" % epoch), entry)
        export_weights(model, cache / ("epoch-%02d-weights.json" % epoch))
        if score > best_score:
            best_state = copy.deepcopy(model.state_dict())
            best_score, best_epoch = score, epoch
        print(json.dumps({"event": "epoch_complete", "epoch": epoch, "training_rows": trained_rows, "validation_macro_f1_fixed12": score, "loss": running / trained_rows, "seconds": entry["seconds"]}), flush=True)
    model.load_state_dict(best_state)
    model.eval()
    changed = {name: int(torch.count_nonzero(value - initial[name])) for name, value in model.state_dict().items()}
    if not all(changed.values()):
        raise ValueError("expected every learned tensor to change from initialization")
    export_weights(model, artifact / "weights.json")
    if sha256_file(artifact / "graph.json") != frozen_graph_sha or sha256_file(_PRODUCT / "ai_pc/model/force_cnn.py") != graph["source"]["sha256"]:
        raise ValueError("frozen graph or model source changed during training")
    training_record = {"recipe": recipe, "sampled_class_counts": sampled_counts.tolist(), "class_weights": weights.tolist(), "selected_epoch": best_epoch, "selected_validation_macro_f1_fixed12": best_score, "learned_tensor_changed_elements_from_seeded_initialization": changed, "sources": {name: sha256_file(_PRODUCT / name) for name in ("ai_pc/train_force_cpu.py", "ai_pc/force_training_data.py", "ai_pc/model/force_cnn.py", "ai_pc/model/curve_input.py", "data/force_inventory.py")}, "archive_sha256": ARCHIVE_SHA256, "inventory_sha256": INVENTORY_SHA256, "splits_sha256": SPLITS_SHA256, "test_opened_before_freeze": False}
    manifest = {"schema_version": 1, "model_id": MODEL_ID, "profile_id": PROFILE_ID, "source_domain": "geo_replay", "input_shape": ["N", 8, 128, 1], "class_order": list(CLASS_ORDER), "graph": {"path": "graph.json", "sha256": sha256_file(artifact / "graph.json")}, "weights": {"path": "weights.json", "sha256": sha256_file(artifact / "weights.json")}, "preprocessing": {"path": "../../../data/preprocessing.json", "sha256": PREPROCESSING_SHA256}, "label_schema": {"path": "../../../data/label_schema.json", "sha256": LABEL_SCHEMA_SHA256}, "training": training_record, "scope": {"status": "learned_offline_FORCE_baseline_only", "not_sim_em_v2": True, "not_water_or_obstacle_model": True, "no_motion_authority": True, "all_formal_cards_incomplete": True}}
    write_json(artifact / "model_manifest.json", manifest)
    frozen_sha = sha256_file(artifact / "model_manifest.json")
    freeze = {"frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "manifest_sha256": frozen_sha, "weights_sha256": manifest["weights"]["sha256"], "test_members_opened": False, "selection_complete": True}
    write_json(evidence / "freeze-before-test.json", freeze)
    print(json.dumps({"event": "model_frozen_before_test", **freeze}), flush=True)
    loaded, _ = load_frozen_model(artifact / "model_manifest.json", frozen_sha)
    with torch.inference_mode():
        probe = validation[0].windows(torch.tensor([0, 127, 256]))
        if not torch.equal(model(probe), loaded(probe)):
            raise ValueError("safe JSON export/load changed logits")
    tests = source.load_split("test")
    test_model = evaluate(tests, lambda well, batch: loaded(well.windows(batch)), with_probabilities=True, bootstrap=True)
    test_centroid = evaluate(tests, centroid, bootstrap=True)
    test_majority = evaluate(tests, constant, bootstrap=True)
    if sha256_file(artifact / "model_manifest.json") != frozen_sha or sha256_file(artifact / "weights.json") != freeze["weights_sha256"]:
        raise ValueError("model changed during test evaluation")
    metrics = {"test_model": test_model, "test_current_vector_centroid": test_centroid, "test_majority": test_majority, "fixed12_macro_f1_target": 0.60, "fixed12_macro_f1_target_met": test_model["macro_f1_fixed12"] >= 0.60, "compressed_vs_raw_loss_gate": "not_run; no actual admitted trace profile used in this model", "no_test_tuning": True, "complete_heldout_wells": len(tests), "all_target_confidences_reported": True, "formal_C01_C02_C03_C04_C05_runtime_board_system_acceptance": "incomplete"}
    write_json(evidence / "heldout_metrics.json", metrics)
    write_json(evidence / "source-open-journal.json", {"opened_splits": sorted(source.opened_splits), "test_open_after_freeze": True, "members": source.journal})
    write_json(evidence / "data-preparation-summary.json", {"wells": [well.record for well in training + validation + tests], "public_fixed_input": {"path": "ai_pc/cpu_model/force_v1/public_input.jsonl", "sha256": sha256_file(artifact / "public_input.jsonl"), "observations": 128, "member": PUBLIC_MEMBER, "member_sha256": source.by_member[PUBLIC_MEMBER]["member_sha256"], "zero_based_rows": list(PUBLIC_ROWS), "source_split": "train", "not_heldout_accuracy": True, "labels": "separate evidence/ai/force_cpu_training_20261024/public_input_evaluator_labels.json; never model inputs"}, "causal_window_checks": source.window_checks})
    write_json(evidence / "training-result.json", {"status": "bounded_training_and_one_frozen_heldout_evaluation_complete", "manifest_sha256": frozen_sha, "public_input_sha256": sha256_file(artifact / "public_input.jsonl"), "selected_epoch": best_epoch, "test_fixed12_macro_f1": test_model["macro_f1_fixed12"], "centroid_fixed12_macro_f1": test_centroid["macro_f1_fixed12"], "majority_fixed12_macro_f1": test_majority["macro_f1_fixed12"], "formal_acceptance": "incomplete", "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print(json.dumps({"event": "training_complete", "manifest_sha256": frozen_sha, "test_fixed12_macro_f1": test_model["macro_f1_fixed12"], "target_met": metrics["fixed12_macro_f1_target_met"]}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--cache", required=True)
    args = parser.parse_args(argv)
    train(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

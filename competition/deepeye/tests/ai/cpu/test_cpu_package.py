"""New CPU-package behavioral checks, not C01/system/board acceptance.

Boundary-only values below are explicitly constructed unit fixtures. Positive
model checks use only the separately pinned real FORCE public input file and
actual trained frozen JSON weights; no dummy/logit model is introduced.
"""

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PRODUCT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PRODUCT))

from ai_pc.cpu_package.runner import (
    FIXED_PREPROCESSING_SHA256, PackageError, _output_is_fresh,
    canonical_json, causal_windows, execute, load_public_input, sha256,
    strict_json, write_exclusive,
)
from ai_pc.model.curve_input import CurveObservation, CurveScaler

ENTRY = PRODUCT / "ai_pc/run_cpu.py"
MODEL = PRODUCT / "ai_pc/cpu_model/force_v1/model_manifest.json"
INPUT = PRODUCT / "ai_pc/cpu_model/force_v1/public_input.jsonl"
# The command running positive tests supplies an external, separately recorded
# model pin. A missing pin is an error rather than an unreported skip.
EXPECTED_MODEL = os.environ.get("DEEPEYE_CPU_EXPECTED_MANIFEST_SHA256")


def fixture_record(sequence=0):
    # Synthetic unit-boundary values, not a claim about the licensed source.
    return {"run_id": "boundary-unit-fixture", "source_domain": "geo_replay",
            "profile_id": "force_curve_v1", "preprocessing_sha256": FIXED_PREPROCESSING_SHA256,
            "sequence": sequence, "value_0": 80.0, "value_1": 2.4,
            "value_2": 0.2, "value_3": 10.0,
            "valid_0": True, "valid_1": True, "valid_2": True, "valid_3": True}


def jsonl(records):
    return b"".join(canonical_json(item) + b"\n" for item in records)


class InputBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        raw = (PRODUCT / "data/preprocessing.json").read_bytes()
        self.scaler = CurveScaler.from_document_bytes(raw, expected_sha256=FIXED_PREPROCESSING_SHA256)

    def load(self, raw):
        path = self.root / "input.jsonl"
        path.write_bytes(raw)
        return load_public_input(path, sha256(raw))

    def test_exact_input_rejects_truth_labels_coordinates_timestamps_and_confidence(self):
        for field in ("truth", "label", "target", "confidence", "x", "coordinates", "future_tick", "tick_ms", "seed"):
            with self.subTest(field=field):
                row = fixture_record()
                row[field] = 1
                with self.assertRaises(PackageError) as caught:
                    self.load(jsonl([row]))
                self.assertEqual(caught.exception.code, "schema_invalid")

    def test_schema_rejects_missing_extra_and_wrong_types(self):
        variants = []
        row = fixture_record(); del row["valid_3"]; variants.append(row)
        for key, value in (("value_0", [1]), ("value_1", True), ("sequence", False),
                           ("valid_1", 1), ("sequence", -1), ("sequence", 2**64)):
            row = fixture_record(); row[key] = value; variants.append(row)
        for row in variants:
            with self.subTest(row=row), self.assertRaises(PackageError):
                self.load(jsonl([row]))

    def test_json_parser_rejects_duplicates_nan_invalid_utf8_and_empty_lines(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff', b'\n',
                    jsonl([fixture_record()]) + b'\n'):
            with self.subTest(raw=raw[:30]), self.assertRaises(PackageError):
                self.load(raw)

    def test_wrong_input_pin_fails_before_parsing(self):
        path = self.root / "input.jsonl"
        path.write_bytes(b"not JSON")
        with self.assertRaises(PackageError) as caught:
            load_public_input(path, "0" * 64)
        self.assertEqual(caught.exception.code, "hash_mismatch")

    def test_source_and_binding_cannot_switch(self):
        for key, value in (("run_id", "other"), ("source_domain", "software_fixture"),
                           ("preprocessing_sha256", "0" * 64), ("profile_id", "sim_em_v2")):
            row = fixture_record(1); row[key] = value
            with self.subTest(key=key), self.assertRaises(PackageError):
                self.load(jsonl([fixture_record(), row]))

    def test_cold_prefix_and_gap_masks_use_existing_causal_builder(self):
        rows, _, _ = self.load(jsonl([fixture_record(0), fixture_record(2)]))
        windows = list(causal_windows(rows, self.scaler))
        self.assertEqual(windows[0].metadata.filled_slots, 1)
        self.assertEqual(windows[0].metadata.missing_slots, 127)
        for channel in windows[0].features[4:]:
            self.assertEqual(channel[:-1], (0.0,) * 127)
            self.assertEqual(channel[-1], 1.0)
        for channel in windows[1].features[4:]:
            self.assertEqual(channel[-3:], (1.0, 0.0, 1.0))
        self.assertEqual(windows[1].metadata.latest_sequence, 2)

    def test_future_suffix_cannot_mutate_prior_features_and_new_runs_are_cold(self):
        prefix, _, _ = self.load(jsonl([fixture_record(index) for index in range(3)]))
        extended, _, _ = self.load(jsonl([fixture_record(index) for index in range(12)]))
        short = list(causal_windows(prefix, self.scaler))
        saved = canonical_json([item.features for item in short])
        full = list(causal_windows(extended, self.scaler))
        self.assertEqual(short, full[:3])
        self.assertEqual(saved, canonical_json([item.features for item in short]))
        cold = list(causal_windows(extended[-1:], self.scaler))[0]
        self.assertEqual(cold.metadata.filled_slots, 1)
        self.assertNotEqual(cold.features, full[-1].features)

    def test_conflicting_duplicate_and_older_sequences_fail_closed(self):
        conflict = fixture_record(1); conflict["value_0"] += 1
        for records in ([fixture_record(1), fixture_record(0)],
                        [fixture_record(1), conflict]):
            observations, _, _ = self.load(jsonl(records))
            with self.assertRaises(PackageError):
                list(causal_windows(observations, self.scaler))

    def test_line_size_bound(self):
        with self.assertRaises(PackageError):
            self.load(b" " * 16385 + b"\n")

    def test_output_exclusive_create_and_hardlink_alias_do_not_clobber(self):
        source = self.root / "source"
        source.write_bytes(b"pinned-input")
        alias = self.root / "hardlink-output"
        os.link(source, alias)
        for path in (source, alias):
            with self.subTest(path=path):
                with self.assertRaises(PackageError):
                    _output_is_fresh(path)
                with self.assertRaises(PackageError):
                    write_exclusive(path, b"changed")
                self.assertEqual(source.read_bytes(), b"pinned-input")
        output = self.root / "new"
        write_exclusive(output, b"complete")
        self.assertEqual(output.read_bytes(), b"complete")

    def cli(self, *extra):
        output = self.root / "output.json"
        command = [sys.executable, "-B", "-X", "utf8", str(ENTRY),
                   "--manifest", str(self.root / "absent-manifest.json"),
                   "--expected-manifest-sha256", "0" * 64,
                   "--input", str(self.root / "absent-input.jsonl"),
                   "--expected-input-sha256", "0" * 64, "--output", str(output), *extra]
        completed = subprocess.run(command, cwd=self.root, capture_output=True)
        return completed, output

    def test_missing_model_is_nonzero_blocked_without_output_or_logits(self):
        completed, output = self.cli()
        result = strict_json(completed.stdout)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(result["code"], "model_missing")
        self.assertFalse(output.exists())
        self.assertFalse(result["movement_authorized"])
        self.assertNotIn("probabilities", result)

    def test_sim_em_missing_model_is_explicit_and_never_force_remapped(self):
        completed, output = self.cli("--profile", "sim_em_v2")
        result = strict_json(completed.stdout)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(result["code"], "sim_em_model_missing")
        self.assertFalse(output.exists())

    def test_cli_output_alias_rejected_before_model_work(self):
        alias = self.root / "output.json"
        alias.write_bytes(b"original")
        completed, _ = self.cli()
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertEqual(strict_json(completed.stdout)["code"], "output_exists")
        self.assertEqual(alias.read_bytes(), b"original")

    def test_bad_manifest_hash_and_profile_fail_before_model_import(self):
        manifest = self.root / "manifest.json"
        manifest.write_bytes(b"{}")
        with self.assertRaises(PackageError) as caught:
            execute(manifest_path=manifest, expected_manifest_sha256="0" * 64,
                    input_path=self.root / "absent", expected_input_sha256="0" * 64)
        self.assertEqual(caught.exception.code, "hash_mismatch")
        with self.assertRaises(PackageError) as caught:
            execute(manifest_path=manifest, expected_manifest_sha256=sha256(b"{}"),
                    input_path=self.root / "absent", expected_input_sha256="0" * 64)
        self.assertEqual(caught.exception.code, "manifest_invalid")

    def test_bool_schema_and_unpinned_scaler_manifest_are_rejected(self):
        for schema, scaler_hash in ((True, FIXED_PREPROCESSING_SHA256), (1, "0" * 64)):
            manifest = self.root / "manifest.json"
            raw = canonical_json({"schema_version": schema, "profile_id": "force_curve_v1",
                                  "source_domain": "geo_replay", "preprocessing":
                                  {"path": "absent-preprocessing.json", "sha256": scaler_hash}})
            manifest.write_bytes(raw)
            input_path = self.root / "real-boundary-input.jsonl"
            observations = jsonl([fixture_record()])
            input_path.write_bytes(observations)
            with self.subTest(schema=schema), self.assertRaises(PackageError) as caught:
                execute(manifest_path=manifest, expected_manifest_sha256=sha256(raw),
                        input_path=input_path, expected_input_sha256=sha256(observations))
            self.assertEqual(caught.exception.code, "manifest_invalid")

    def test_unexpected_scaler_path_rejected_without_model_output(self):
        manifest = self.root / "manifest.json"
        raw = canonical_json({"schema_version": 1, "profile_id": "force_curve_v1",
                              "source_domain": "geo_replay", "preprocessing":
                              {"path": "absent-preprocessing.json", "sha256": FIXED_PREPROCESSING_SHA256}})
        manifest.write_bytes(raw)
        input_path = self.root / "boundary-input.jsonl"
        observations = jsonl([fixture_record()])
        input_path.write_bytes(observations)
        with self.assertRaises(PackageError) as caught:
            execute(manifest_path=manifest, expected_manifest_sha256=sha256(raw),
                    input_path=input_path, expected_input_sha256=sha256(observations))
        self.assertEqual(caught.exception.code, "manifest_invalid")
        self.assertFalse(caught.exception.blocked)


class ModelInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EXPECTED_MODEL:
            raise RuntimeError("positive tests require independently recorded DEEPEYE_CPU_EXPECTED_MANIFEST_SHA256")
        cls.raw = INPUT.read_bytes()
        cls._cached_result = None

    @property
    def result(self):
        if type(self)._cached_result is None:
            type(self)._cached_result = execute(
                manifest_path=MODEL, expected_manifest_sha256=EXPECTED_MODEL,
                input_path=INPUT, expected_input_sha256=sha256(self.raw), threads=4)
        return type(self)._cached_result

    def test_real_frozen_model_produces_finite12_class_causal_outputs(self):
        result = self.result
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["runtime"]["actual_device"], "cpu")
        self.assertFalse(result["movement_authorized"])
        self.assertIsNone(result["motion_bytes"])
        self.assertEqual(result["A_format_adoption"], "not_adopted")
        self.assertEqual(result["formal_acceptance"], "not_run")
        self.assertEqual(len(result["predictions"]), len(self.raw.splitlines()))
        for prediction in result["predictions"]:
            probabilities = prediction["probabilities"]
            self.assertEqual(len(probabilities), 12)
            self.assertTrue(all(math.isfinite(p) and 0 <= p <= 1 for p in probabilities))
            self.assertAlmostEqual(sum(probabilities), 1.0, places=5)
            self.assertFalse(prediction["movement_authorized"])
        self.assertEqual(result["predictions"][0]["window"]["filled_slots"], 1)
        self.assertEqual(result["predictions"][0]["window"]["missing_slots"], 127)

    def test_model_prefix_probabilities_are_invariant_to_future_suffix(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = b"".join(self.raw.splitlines(keepends=True)[:3])
            path = Path(temp) / "prefix.jsonl"
            path.write_bytes(prefix)
            short = execute(manifest_path=MODEL, expected_manifest_sha256=EXPECTED_MODEL,
                            input_path=path, expected_input_sha256=sha256(prefix), threads=4)
        self.assertEqual(short["predictions"], self.result["predictions"][:3])

    def test_explicit_hip_request_on_c_cpu_runtime_never_falls_back(self):
        import torch
        self.assertIsNone(torch.version.hip, "this evidence command is scoped to the C CPU environment")
        with self.assertRaises(PackageError) as caught:
            execute(manifest_path=MODEL, expected_manifest_sha256=EXPECTED_MODEL,
                    input_path=INPUT, expected_input_sha256=sha256(self.raw), device="hip")
        self.assertEqual(caught.exception.code, "hip_unavailable")
        self.assertTrue(caught.exception.blocked)

    def test_portable_copy_rejects_missing_and_corrupt_graph_weights(self):
        # Every mutation is in one temporary copied product tree. The actual
        # trained package, preprocessing and current working tree stay intact.
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp) / "portable-product"
            files = ["ai_pc/run_cpu.py", "ai_pc/model/curve_input.py", "ai_pc/model/force_cnn.py",
                     "data/preprocessing.json", "data/label_schema.json"]
            files += [str(path.relative_to(PRODUCT)) for path in (PRODUCT / "ai_pc/cpu_package").glob("*.py")]
            files += [str(path.relative_to(PRODUCT)) for path in MODEL.parent.glob("*.json*")]
            for relative in files:
                target = copied / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(PRODUCT / relative, target)
            copied_manifest = copied / MODEL.relative_to(PRODUCT)
            manifest_bytes = copied_manifest.read_bytes()
            manifest = strict_json(manifest_bytes)
            weights = copied_manifest.parent / manifest["weights"]["path"]
            graph = copied_manifest.parent / manifest["graph"]["path"]
            weights_bytes = weights.read_bytes()
            graph_bytes = graph.read_bytes()

            def run(expected_manifest, label):
                command = [sys.executable, "-B", "-X", "utf8", str(copied / "ai_pc/run_cpu.py"),
                           "--manifest", str(copied_manifest), "--expected-manifest-sha256", expected_manifest,
                           "--input", str(copied / INPUT.relative_to(PRODUCT)),
                           "--expected-input-sha256", sha256(self.raw),
                           "--output", str(Path(temp) / (label + ".json"))]
                result = subprocess.run(command, cwd=temp, capture_output=True)
                return result.returncode, strict_json(result.stdout)

            weights.unlink()
            code, result = run(EXPECTED_MODEL, "missing")
            self.assertEqual(code, 2, result)
            self.assertEqual(result["code"], "model_missing")
            self.assertNotIn("predictions", result)
            weights.write_bytes(weights_bytes)
            copied_scaler = copied / "data/preprocessing.json"
            scaler_bytes = copied_scaler.read_bytes()
            copied_scaler.unlink()
            code, result = run(EXPECTED_MODEL, "missing-scaler")
            self.assertEqual(code, 2, result)
            self.assertEqual(result["code"], "asset_missing")
            copied_scaler.write_bytes(scaler_bytes)
            graph.write_bytes(graph_bytes + b" ")
            code, result = run(EXPECTED_MODEL, "corrupt")
            self.assertEqual(code, 1, result)
            self.assertEqual(result["code"], "hash_mismatch")
            graph.write_bytes(graph_bytes)
            encoded = strict_json(weights_bytes)
            name = next(iter(encoded["tensors"]))
            encoded["tensors"][name]["shape"][0] += 1
            mutated_weights = canonical_json(encoded)
            weights.write_bytes(mutated_weights)
            manifest["weights"]["sha256"] = sha256(mutated_weights)
            mutated_manifest = canonical_json(manifest)
            copied_manifest.write_bytes(mutated_manifest)
            code, result = run(sha256(mutated_manifest), "shape")
            self.assertEqual(code, 1, result)
            self.assertEqual(result["code"], "model_invalid")


if __name__ == "__main__":
    unittest.main(verbosity=2)

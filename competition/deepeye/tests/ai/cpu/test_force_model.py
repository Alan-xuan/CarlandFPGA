"""New CNN/JSON-loader/buffer tests; synthetic cases are not model accuracy."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

PRODUCT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PRODUCT))
import torch
from ai_pc.model import force_cnn as cnn
from ai_pc.force_training_data import WellBuffer, normalize_sensor
from ai_pc.model.curve_input import CurveBinding, CurveObservation, CurveScaler, CurveWindowBuilder


def dump(path, document):
    path.write_text(json.dumps(document, allow_nan=False) + "\n", encoding="utf-8")
    return cnn.sha256_file(path)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def checkpoint(self, folder):
        model = cnn.build_model().eval()
        cnn.export_weights(model, folder / "weights.json")
        graph = {"format": "fixed-force-cnn-graph-v1", "parameters": 4916, "layers": copy.deepcopy(cnn.GRAPH), "input_shape": ["N", 8, 128, 1], "output_shape": ["N", 12], "source": {"path": Path(os.path.relpath(PRODUCT / "ai_pc/model/force_cnn.py", folder)).as_posix(), "sha256": cnn.sha256_file(PRODUCT / "ai_pc/model/force_cnn.py")}}
        graph_sha = dump(folder / "graph.json", graph)
        manifest = {"schema_version": 1, "model_id": cnn.MODEL_ID, "profile_id": cnn.PROFILE_ID, "source_domain": "geo_replay", "input_shape": ["N", 8, 128, 1], "class_order": list(cnn.CLASS_ORDER), "graph": {"path": "graph.json", "sha256": graph_sha}, "weights": {"path": "weights.json", "sha256": cnn.sha256_file(folder / "weights.json")}, "preprocessing": {"path": Path(os.path.relpath(PRODUCT / "data/preprocessing.json", folder)).as_posix(), "sha256": cnn.PREPROCESSING_SHA256}, "label_schema": {"path": Path(os.path.relpath(PRODUCT / "data/label_schema.json", folder)).as_posix(), "sha256": cnn.LABEL_SCHEMA_SHA256}, "training": {"synthetic_unit_test_only": True}, "scope": {"not_release": True}}
        digest = dump(folder / "model_manifest.json", manifest)
        return model, graph, manifest, digest

    def test_graph_and_safe_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            model, _, _, digest = self.checkpoint(folder)
            loaded, _ = cnn.load_frozen_model(folder / "model_manifest.json", digest)
            values = torch.randn(3, 8, 128, 1)
            with torch.inference_mode():
                self.assertEqual(tuple(loaded(values).shape), (3, 12))
                self.assertTrue(torch.equal(model(values), loaded(values)))
            self.assertEqual(sum(p.numel() for p in model.parameters()), 4916)
            with self.assertRaises(cnn.FrozenModelError):
                loaded(torch.zeros(1, 8, 129, 1))

    def test_identity_graph_shape_and_path_rejections(self):
        mutations = [
            lambda m: m.update(schema_version=True),
            lambda m: m.update(input_shape=["N", 8, 128, True]),
            lambda m: m.update(class_order=list(reversed(cnn.CLASS_ORDER))),
            lambda m: m.update(source_domain="sim_em_v2"),
            lambda m: m["weights"].update(path="../weights.json"),
            lambda m: m["preprocessing"].update(sha256="0" * 64),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                _, _, manifest, _ = self.checkpoint(folder)
                mutate(manifest)
                digest = dump(folder / "model_manifest.json", manifest)
                with self.assertRaises(cnn.FrozenModelError):
                    cnn.load_frozen_model(folder / "model_manifest.json", digest)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            _, graph, manifest, _ = self.checkpoint(folder)
            graph["layers"][0]["kernel"][1] = True
            manifest["graph"]["sha256"] = dump(folder / "graph.json", graph)
            digest = dump(folder / "model_manifest.json", manifest)
            with self.assertRaises(cnn.FrozenModelError):
                cnn.load_frozen_model(folder / "model_manifest.json", digest)

    def test_tampered_nonfinite_boolean_and_duplicate_weights_refused(self):
        variants = ("tamper", "boolean", "overflow", "shape_bool", "duplicate")
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                _, _, manifest, digest = self.checkpoint(folder)
                path = folder / "weights.json"
                encoded = json.loads(path.read_text())
                first = next(iter(encoded["tensors"].values()))
                if variant == "tamper":
                    path.write_bytes(path.read_bytes() + b" ")
                elif variant == "duplicate":
                    path.write_text('{"format":"x","format":"x","tensors":{}}', encoding="utf-8")
                else:
                    if variant == "boolean":
                        first["values"][0] = True
                    elif variant == "overflow":
                        first["values"][0] = 1e100
                    else:
                        first["shape"][-1] = True
                    dump(path, encoded)
                if variant != "tamper":
                    manifest["weights"]["sha256"] = cnn.sha256_file(path)
                    digest = dump(folder / "model_manifest.json", manifest)
                with self.assertRaises(cnn.FrozenModelError):
                    cnn.load_frozen_model(folder / "model_manifest.json", digest)

    def test_window_buffer_causal_order_padding_and_future_independence(self):
        scaler = CurveScaler((PRODUCT / "data/preprocessing.json").read_bytes(), expected_sha256=cnn.PREPROCESSING_SHA256)
        binding = CurveBinding("novel-buffer-test", "software_fixture", cnn.PREPROCESSING_SHA256)
        builder = CurveWindowBuilder(scaler=scaler, binding=binding)
        rows = []
        snapshots = {}
        for index in range(260):
            values = (index - 20.0, 2.0 + index / 1000, -0.1 + index / 500, 0.0 if index % 11 == 0 else 1 + index / 10)
            valid = (index % 5 != 0, True, index % 7 != 0, True)
            rows.append(normalize_sensor(values, valid, scaler.channels))
            builder.observe(CurveObservation(binding, index, values, valid))
            if index in (0, 31, 127, 128, 259):
                snapshots[index] = torch.tensor(builder.snapshot().to_model_input(), dtype=torch.float32)
        features = torch.cat((torch.zeros(8, 127), torch.tensor(rows, dtype=torch.float32).T), dim=1)
        well = WellBuffer("synthetic", "test", "test", "train", features, torch.full((260,), -1), torch.zeros(260, dtype=torch.uint8), {})
        for index, expected in snapshots.items():
            self.assertTrue(torch.equal(well.windows(torch.tensor([index])), expected))
        before = well.windows(torch.tensor([128])).clone()
        well.features[:, 127 + 129:] = 999
        self.assertTrue(torch.equal(before, well.windows(torch.tensor([128]))))

    def test_malformed_structures_and_bounded_reads_raise_controlled_error(self):
        for location, replacement in (("manifest", []), ("manifest", {"schema_version": 1}), ("graph", []), ("graph", {}), ("weights", []), ("weights", {"format": "finite-float32-state-dict-json-v1", "tensors": []})):
            with self.subTest(location=location, replacement=replacement), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                _, _, manifest, digest = self.checkpoint(folder)
                if location == "manifest":
                    digest = dump(folder / "model_manifest.json", replacement)
                else:
                    manifest[location]["sha256"] = dump(folder / (location + ".json"), replacement)
                    digest = dump(folder / "model_manifest.json", manifest)
                with self.assertRaises(cnn.FrozenModelError):
                    cnn.load_frozen_model(folder / "model_manifest.json", digest)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            _, _, manifest, _ = self.checkpoint(folder)
            weight_path = folder / "weights.json"
            weight_path.write_bytes(b" " * (3 * 1024 * 1024))
            manifest["weights"]["sha256"] = cnn.sha256_file(weight_path)
            digest = dump(folder / "model_manifest.json", manifest)
            original = Path.open
            reads = []
            class TrackedRead:
                def __init__(self, inner):
                    self.inner = inner
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    self.inner.close()
                def read(self, size=-1):
                    reads.append(size)
                    return self.inner.read(size)
            def opening(path, *args, **kwargs):
                inner = original(path, *args, **kwargs)
                return TrackedRead(inner) if path == weight_path else inner
            with mock.patch.object(Path, "open", opening):
                with self.assertRaises(cnn.FrozenModelError):
                    cnn.load_frozen_model(folder / "model_manifest.json", digest)
            self.assertEqual(reads, [2 * 1024 * 1024 + 1])
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing.json"
            with self.assertRaises(cnn.FrozenModelError):
                cnn.load_frozen_model(missing, "0" * 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)

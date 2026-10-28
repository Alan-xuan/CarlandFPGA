#!/usr/bin/env python3
"""New C24 synthetic-definition controls; executed only by main's bounded job.

No physical data, model, old suite or fixture is used.  Every constructed input
lives below the explicitly supplied private --work-dir.  Importing this test
source alone neither loads the tool nor creates inputs; main() does that only
when the authorized root batch launches this exact script.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


UNKNOWN_CLOCK = {
    "boot_id": None, "boot_reason": "synthetic definition has no BOOT provider",
    "clock_mapping_id": None, "clock_error_ns": None,
    "clock_reason": "declared offline clock, no verified live mapping",
    "own_odometry_history_ref": None,
    "history_reason": "no odometry provider in this synthetic definition",
}


class DefinitionCatalog:
    """Tiny new file definitions, never measured/qualified physical samples."""

    def __init__(self, root):
        self.root = root
        root.mkdir(exist_ok=False)
        for role in ("records", "provenance", "groups"):
            (root / role).mkdir()
        self.rows = {}
        self.entries = []
        self.next_index = 1

    def add(self, name, value=2, *, split="train", sequence=None,
            native_sequence=None, time_ns=None, native_time_ns=None,
            scene=None, event=None, profile="definition_real_v1",
            quantity="definition_scalar", representation="real",
            unit="definition_unit", calibration="synthetic-definition-v1",
            calibration_state="synthetic_definition",
            source_kind="synthetic_definition", valid=True, held=False,
            fault=None, saturated=False, native_ref=None, reason=None,
            native_reason=None, target="control-target"):
        index = self.next_index
        self.next_index += 1
        sequence = index if sequence is None else sequence
        native_sequence = sequence if native_sequence is None else native_sequence
        time_ns = index * 10 if time_ns is None else time_ns
        native_time_ns = time_ns if native_time_ns is None else native_time_ns
        unit_reason = "unknown native unit" if unit is None else None
        channel = {
            "channel_id": "channel0", "quantity_id": quantity,
            "representation": representation, "unit": unit,
            "unit_reason": unit_reason, "calibration_id": calibration,
            "value": copy.deepcopy(value), "reason": reason,
            "valid": valid, "held": held, "fault": fault,
            "saturated": saturated, "native_sequence": native_sequence,
            "native_time_ns": native_time_ns, "native_reason": native_reason,
            "native_ref": copy.deepcopy(native_ref),
        }
        record = {
            "schema_version": 1, "run_id": "synthetic-run",
            "sequence": sequence, "source_time_ns": time_ns,
            "clock_domain": "synthetic-clock", "profile_id": profile,
            "channels": [channel],
        }
        provenance = {
            "schema_version": 1, "record_sha256": "pending",
            "source_id": "synthetic-source", "source_kind": source_kind,
            "native_profile_id": profile, "delivery_index": index,
            "clock_context": copy.deepcopy(UNKNOWN_CLOCK),
            "channel_bindings": [{
                "channel_id": "channel0", "quantity_id": quantity,
                "representation": representation, "unit": unit,
                "unit_reason": unit_reason,
                "calibration": {
                    "state": calibration_state, "id": calibration,
                    "reason": "no physical calibration available" if calibration is None else None,
                },
            }],
        }
        group = {
            "schema_version": 1, "record_sha256": "pending",
            "scene_id": scene or "scene-" + name,
            "event_id": event or "event-" + name,
            "target": {"definition_id": "synthetic-target-v1",
                       "label": target, "reason": "unknown target" if target is None else None},
        }
        row = {"record": record, "provenance": provenance, "group": group}
        entry = {"sample_id": name, "split": split}
        self.rows[name] = row
        self.entries.append(entry)
        self.rewrite(name)
        return row

    def rewrite(self, name, *, record_raw=None):
        row = self.rows[name]
        raw = encoded(row["record"]) if record_raw is None else record_raw
        digest = sha(raw)
        row["provenance"]["record_sha256"] = digest
        row["group"]["record_sha256"] = digest
        entry = next(item for item in self.entries if item["sample_id"] == name)
        for role, folder in (("record", "records"), ("provenance", "provenance"), ("group", "groups")):
            data = raw if role == "record" else encoded(row[role])
            relative = folder + "/" + name + ".json"
            (self.root / relative).write_bytes(data)
            entry[role] = {"path": relative, "sha256": sha(data)}
        return digest

    def record_sha(self, name):
        return next(item for item in self.entries if item["sample_id"] == name)["record"]["sha256"]

    def pin(self):
        raw = encoded({"schema_version": 1, "entries": self.entries})
        (self.root / "catalog.json").write_bytes(raw)
        return sha(raw)


# Exact fields from the explicit static interface-results.json declaration
# (SHA256 6fb7690430e307a18343a0b6cbf32ebd71a783ca3ab45e55d89d5a1e1af4a4c3).
# No compatibility guessing, recursive key search or fallback adapters.
def scaler_statistics(document):
    return document["statistics"]


def window_features(document):
    rows = document["features"]
    if type(rows) is not list or len(rows) > 128:
        raise AssertionError("Exact bounded features list required")
    for row in rows:
        if type(row) is not list or not 1 <= len(row) <= 16:
            raise AssertionError("Exact bounded channel row required")
        for channel in row:
            if type(channel) is not dict or set(channel) != {"raw_value", "effective_mask", "status_reasons"}:
                raise AssertionError("Unexpected feature keys")
            mask = channel["effective_mask"]
            if type(mask) is not int or mask not in (0, 1):
                raise AssertionError("Effective mask must be exact int0/1, not bool")
            reasons = channel["status_reasons"]
            if type(reasons) is not list or any(type(item) is not str for item in reasons):
                raise AssertionError("Exact reason-code list required")
    return rows


class IndependentC24(unittest.TestCase):
    tool = None
    work_root = None
    module_path = None
    cli_invocations = 0
    cli_records = []

    def definitions(self, suffix=""):
        # Keep Windows private fixture paths short; case IDs remain descriptive
        # in unittest/JSON output. No existing path is deleted or reused.
        case_id = self._testMethodName.split("_", 2)[1].lower()
        return DefinitionCatalog(self.work_root / (case_id + suffix))

    def load(self, definition):
        return self.tool.load_catalog(definition.root, definition.pin())

    def candidate(self, report):
        self.assertIs(type(report["schema_version"]), int)
        self.assertEqual(report["schema_version"], 1)
        self.assertIs(report["approved_training_data"], False)
        self.assertIs(report["candidate_only"], True)
        self.assertIs(report["format_valid"], True)
        self.assertIn(report["status"], ("candidate", "blocked"))

    def rejects(self, code, operation):
        with self.assertRaises(self.tool.DataError) as result:
            operation()
        allowed = (code,) if isinstance(code, str) else code
        self.assertIn(result.exception.code, allowed)

    def test_P01_whole_scene_crosssplit(self):
        definition = self.definitions()
        definition.add("a", scene="whole-scene", event="eventA")
        definition.add("b", 4, split="test", scene="whole-scene", event="eventB")
        self.rejects("split_leakage", lambda: self.load(definition))

    def test_P02_event_and_transitive_crosssplit(self):
        direct = self.definitions("-direct")
        direct.add("a", scene="sceneA", event="whole-event")
        direct.add("b", 4, split="validation", scene="sceneB", event="whole-event")
        self.rejects("split_leakage", lambda: self.load(direct))
        chain = self.definitions("-transitive")
        chain.add("a", scene="sceneA", event="eventX")
        chain.add("b", 4, scene="sceneB", event="eventX")
        chain.add("c", 6, split="test", scene="sceneB", event="eventY")
        self.rejects("split_leakage", lambda: self.load(chain))

    def test_P03_native_duplicate_cannot_escape_groups(self):
        definition = self.definitions()
        definition.add("a", native_sequence=1, native_time_ns=10)
        definition.add("renamed", split="test", native_sequence=1, native_time_ns=10,
                       scene="renamed-scene", event="renamed-event")
        self.rejects("split_leakage", lambda: self.load(definition))
        exact = self.definitions("-exactbytes")
        original = exact.add("a")
        renamed = exact.add("renamed", split="test", scene="another-scene", event="another-event")
        renamed["record"] = copy.deepcopy(original["record"])
        exact.rewrite("renamed")
        self.assertEqual(exact.record_sha("a"), exact.record_sha("renamed"))
        self.rejects("split_leakage", lambda: self.load(exact))
        conflict = self.definitions("-conflict")
        conflict.add("a", native_sequence=1, native_time_ns=10)
        conflict.add("b", 9, native_sequence=1, native_time_ns=10)
        self.rejects("native_conflict", lambda: self.load(conflict))

    def test_P04_future_window_and_prefix(self):
        definition = self.definitions()
        definition.add("earlier", time_ns=10)
        definition.add("future", 99, time_ns=101)
        catalog = self.load(definition)
        earlier = self.tool.make_window(catalog, ["earlier"], cutoff_ns=100, max_age_ns=100)
        self.candidate(earlier)
        self.assertEqual(window_features(earlier), [[{"raw_value": 2, "effective_mask": 1, "status_reasons": []}]])
        self.rejects("future_sample", lambda: self.tool.make_window(
            catalog, ["earlier", "future"], cutoff_ns=100, max_age_ns=100))
        self.assertEqual(self.tool.make_window(catalog, ["earlier"], cutoff_ns=100, max_age_ns=100), earlier)
        native_future = self.definitions("-native-future")
        native_future.add("a", time_ns=10, native_time_ns=11)
        self.rejects("future_sample", lambda: self.load(native_future))

    def held_definition(self, suffix=""):
        definition = self.definitions(suffix)
        definition.add("original", time_ns=10, native_sequence=1, native_time_ns=10)
        definition.add("held", time_ns=20, native_sequence=1, native_time_ns=10, held=True,
                       native_ref={"record_sha256": definition.record_sha("original"), "channel_id": "channel0"})
        return definition

    def test_P05_held_original_native_hash(self):
        good = self.held_definition("-good")
        report = self.tool.make_window(self.load(good), ["original", "held"], cutoff_ns=20, max_age_ns=10)
        self.candidate(report)
        features = window_features(report)
        self.assertEqual([row[0]["raw_value"] for row in features], [2, 2])
        self.assertEqual([row[0]["effective_mask"] for row in features], [1, 0])
        native = report["causal_metadata"][1]["channels"][0]
        self.assertEqual(native["native_time_ns"], 10)
        self.assertEqual(native["age_ns"], 10)
        self.assertIs(native["held"], True)
        self.assertEqual(native["native_ref"], {"record_sha256": good.record_sha("original"), "channel_id": "channel0"})
        self.assertEqual(report["causal_metadata"][1]["source_time_ns"], 20)
        self.assertEqual(report["causal_metadata"][1]["clock_context"], UNKNOWN_CLOCK)
        # Each changed held wrapper is rehashed and its sidecars repinned: a
        # fresh wrapper SHA must not launder the original native reference.
        for field, value in (("native_time_ns", 20), ("value", 9), ("calibration_id", "another-definition")):
            with self.subTest(changed=field):
                bad = self.held_definition("-" + field)
                bad.rows["held"]["record"]["channels"][0][field] = value
                if field == "calibration_id":
                    bad.rows["held"]["provenance"]["channel_bindings"][0]["calibration"]["id"] = value
                bad.rewrite("held")
                self.rejects(("held_mismatch", "native_conflict", "binding_mismatch"), lambda: self.load(bad))
        bad_link = self.held_definition("-bad-original-hash")
        bad_link.rows["held"]["record"]["channels"][0]["native_ref"]["record_sha256"] = "f" * 64
        bad_link.rewrite("held")
        self.rejects("held_mismatch", lambda: self.load(bad_link))

    def test_P06_uncalibrated_code_is_not_voltage(self):
        definition = self.definitions()
        row = definition.add("raw", 42, profile="hardware_raw_code_candidate_v1",
                             quantity="hardware_raw_code", unit="count", calibration=None,
                             calibration_state="unknown", source_kind="hardware_unqualified")
        report = self.tool.fit_scaler(self.load(definition))
        self.candidate(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(scaler_statistics(report)[0]["reason"], "calibration_unknown")
        row["record"]["profile_id"] = "full_voltage_candidate_v1"
        row["record"]["channels"][0].update({
            "quantity_id": "full_induced_voltage", "representation": "complex",
            "unit": "V", "value": {"real": 42, "imag": 0},
        })
        definition.rewrite("raw")
        self.rejects("binding_mismatch", lambda: self.load(definition))

    def test_P07_unknown_missing_real_zero(self):
        definition = self.definitions()
        definition.add("missing", None, valid=False, reason="missing synthetic value")
        definition.add("zero", 0)
        catalog = self.load(definition)
        report = self.tool.make_window(catalog, ["missing", "zero"], cutoff_ns=20, max_age_ns=100)
        self.candidate(report)
        features = window_features(report)
        self.assertIsNone(features[0][0]["raw_value"])
        self.assertEqual(features[0][0]["effective_mask"], 0)
        self.assertEqual(features[1][0]["raw_value"], 0)
        self.assertEqual(features[1][0]["effective_mask"], 1)
        definition.rows["missing"]["record"]["channels"][0]["reason"] = None
        definition.rewrite("missing")
        self.rejects("schema_invalid", lambda: self.load(definition))
        unknown = self.definitions("-unknown")
        unknown.add("a", 2, profile="hardware_raw_code_candidate_v1", quantity="hardware_raw_code",
                    unit=None, calibration=None, calibration_state="unknown", source_kind="hardware_unqualified")
        unknown.add("b", 4, profile="hardware_raw_code_candidate_v1", quantity="hardware_raw_code",
                    unit=None, calibration=None, calibration_state="unknown", source_kind="hardware_unqualified")
        blocked = self.tool.fit_scaler(self.load(unknown))
        self.candidate(blocked)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(len(scaler_statistics(blocked)), 1)
        for item in scaler_statistics(blocked):
            self.assertIsNone(item["mean"])
            self.assertIsNone(item["scale"])
            self.assertTrue(item["reason"])
        native_unknown = self.definitions("-native-unknown")
        row = native_unknown.add("a", 7)
        row["record"]["channels"][0].update({
            "native_sequence": None, "native_time_ns": None,
            "native_reason": "original native time and sequence unknown",
        })
        native_unknown.rewrite("a")
        window = self.tool.make_window(self.load(native_unknown), ["a"], cutoff_ns=10, max_age_ns=100)
        self.candidate(window)
        self.assertEqual(window_features(window)[0][0]["raw_value"], 7)
        self.assertEqual(window_features(window)[0][0]["effective_mask"], 0)
        self.assertIsNone(window["causal_metadata"][0]["channels"][0]["native_time_ns"])
        self.assertIsNone(window["causal_metadata"][0]["channels"][0]["age_ns"])

    def test_P08_mask0_age_and_duplicates(self):
        definition = self.definitions()
        definition.add("first", 2, native_sequence=1, native_time_ns=10)
        definition.add("repeat", 2, native_sequence=1, native_time_ns=10)
        definition.add("fresh", 4, native_sequence=2, native_time_ns=30)
        definition.add("faulted", 7, fault="synthetic channel fault")
        catalog = self.load(definition)
        scaler = self.tool.fit_scaler(catalog)
        self.candidate(scaler)
        self.assert_population_pair(scaler)
        report = self.tool.make_window(catalog, ["first", "repeat", "fresh", "faulted"], cutoff_ns=40, max_age_ns=100)
        self.candidate(report)
        features = window_features(report)
        self.assertEqual([row[0]["raw_value"] for row in features], [2, 2, 4, 7])
        self.assertEqual([row[0]["effective_mask"] for row in features], [1, 0, 1, 0])
        self.assertEqual([row["channels"][0]["age_ns"] for row in report["causal_metadata"]], [30, 30, 10, 0])
        self.assertIn("duplicate_native", features[1][0]["status_reasons"])
        self.assertIn("fault", features[3][0]["status_reasons"])
        stale = self.tool.make_window(catalog, ["first"], cutoff_ns=40, max_age_ns=29)
        self.assertEqual(window_features(stale)[0][0]["raw_value"], 2)
        self.assertEqual(window_features(stale)[0][0]["effective_mask"], 0)

    def training_pair(self, suffix="", test_value=100):
        definition = self.definitions(suffix)
        definition.add("trainA", 2)
        definition.add("trainB", 4)
        definition.add("testC", test_value, split="test")
        return definition

    def assert_population_pair(self, scaler):
        stats = scaler_statistics(scaler)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["count"], 2)
        self.assertEqual(stats[0]["mean"], 3.0)
        self.assertEqual(stats[0]["scale"], 1.0)
        self.assertIsNone(stats[0]["reason"])

    def test_P09_train_only_scaler_and_recomputation(self):
        first = self.training_pair("-first")
        second = self.training_pair("-testchanged", test_value=1000)
        cat1, cat2 = self.load(first), self.load(second)
        fit1, fit2 = self.tool.fit_scaler(cat1), self.tool.fit_scaler(cat2)
        self.candidate(fit1)
        self.candidate(fit2)
        self.assert_population_pair(fit1)
        self.assert_population_pair(fit2)
        self.assert_training_equal(fit1, fit2)
        self.assertNotEqual(fit1["full_catalog_sha256"], fit2["full_catalog_sha256"])
        self.candidate(self.tool.validate_scaler(cat1, fit1))
        self.rejects("scaler_mismatch", lambda: self.tool.validate_scaler(cat2, fit1))
        for field, value in (("mean", 106.0 / 3), ("scale", 99.0), ("count", 3)):
            with self.subTest(tamper=field):
                forged = copy.deepcopy(fit1)
                scaler_statistics(forged)[0][field] = value
                self.rejects("scaler_mismatch", lambda: self.tool.validate_scaler(cat1, forged))
        self.forged_manifest_controls(cat1, fit1, first)

    def assert_training_equal(self, first, second):
        # Full catalog audit may change; fitting identities and values must not.
        for key in ("algorithm", "training_manifest", "training_manifest_sha256", "contributors", "statistics"):
            self.assertEqual(first[key], second[key], key)
        self.assertEqual(sha(encoded(first["training_manifest"])), first["training_manifest_sha256"])
        self.assertEqual([entry["sample_id"] for entry in first["training_manifest"]["entries"]], ["trainA", "trainB"])
        self.assertEqual(len(first["contributors"]), 2)

    def forged_manifest_controls(self, catalog, scaler, definition):
        forged_hash = copy.deepcopy(scaler)
        forged_hash["training_manifest"]["entries"][0]["group_sha256"] = "0" * 64
        forged_hash["training_manifest_sha256"] = sha(encoded(forged_hash["training_manifest"]))
        self.rejects("scaler_mismatch", lambda: self.tool.validate_scaler(catalog, forged_hash))
        # Include the *actual held-out row hashes* in a self-consistent forged
        # training manifest/contributor/statistic document. Rehashing the lie
        # cannot promote a test row into the real training group.
        entry = next(item for item in definition.entries if item["sample_id"] == "testC")
        test_row = definition.rows["testC"]
        forged_test = copy.deepcopy(scaler)
        forged_entry = copy.deepcopy(forged_test["training_manifest"]["entries"][0])
        forged_entry.update({"sample_id": "testC", "record_sha256": entry["record"]["sha256"],
                             "provenance_sha256": entry["provenance"]["sha256"], "group_sha256": entry["group"]["sha256"]})
        forged_test["training_manifest"]["entries"].append(forged_entry)
        forged_test["training_manifest"]["entries"].sort(key=lambda item: item["sample_id"])
        forged_test["training_manifest_sha256"] = sha(encoded(forged_test["training_manifest"]))
        contributor = copy.deepcopy(forged_test["contributors"][0])
        contributor["native_key"]["native_sequence"] = test_row["record"]["channels"][0]["native_sequence"]
        contributor.update({"record_sha256": entry["record"]["sha256"],
                            "provenance_sha256": entry["provenance"]["sha256"], "group_sha256": entry["group"]["sha256"]})
        value = test_row["record"]["channels"][0]["value"]
        contributor["components"] = {"value": value}
        forged_test["contributors"].append(contributor)
        values = [2.0, 4.0, float(value)]
        mean = math.fsum(values) / 3
        forged_test["statistics"][0].update({
            "count": 3, "mean": mean,
            "scale": math.sqrt(math.fsum((item - mean) ** 2 for item in values) / 3),
        })
        self.rejects("scaler_mismatch", lambda: self.tool.validate_scaler(catalog, forged_test))

    def test_P10_complex_and_native_binding(self):
        definition = self.definitions()
        definition.add("a", {"real": 2, "imag": 10}, profile="definition_complex_v1",
                       quantity="definition_complex", representation="complex")
        definition.add("b", {"real": 4, "imag": 14}, profile="definition_complex_v1",
                       quantity="definition_complex", representation="complex")
        catalog = self.load(definition)
        report = self.tool.make_window(catalog, ["a", "b"], cutoff_ns=20, max_age_ns=100)
        self.candidate(report)
        self.assertEqual([row[0]["raw_value"] for row in window_features(report)],
                         [{"real": 2, "imag": 10}, {"real": 4, "imag": 14}])
        fit = self.tool.fit_scaler(catalog)
        self.candidate(fit)
        stats = scaler_statistics(fit)
        self.assertEqual(len(stats), 2)
        self.assertEqual({item["component"]: (item["count"], item["mean"], item["scale"])
                          for item in stats}, {"real": (2, 3.0, 1.0), "imag": (2, 12.0, 2.0)})
        self.assertEqual([item["components"] for item in fit["contributors"]],
                         [{"real": 2, "imag": 10}, {"real": 4, "imag": 14}])
        for mutation in ("imaginary-missing", "bool", "unit"):
            with self.subTest(mutation=mutation):
                bad = self.definitions("-" + mutation)
                row = bad.add("a", {"real": 2, "imag": 10}, profile="definition_complex_v1",
                              quantity="definition_complex", representation="complex")
                ch = row["record"]["channels"][0]
                if mutation == "imaginary-missing":
                    ch["value"] = {"real": 2}
                elif mutation == "bool":
                    ch["value"]["real"] = True
                else:
                    ch["unit"] = "V"
                bad.rewrite("a")
                self.rejects(("schema_invalid", "binding_mismatch"), lambda: self.load(bad))

    def test_P11_self_accepted_is_not_authority(self):
        for field in ("accepted", "approved_training_data"):
            with self.subTest(field=field):
                definition = self.definitions("-" + field)
                row = definition.add("a")
                row["provenance"][field] = True
                definition.rewrite("a")
                self.rejects("schema_invalid", lambda: self.load(definition))
        candidate = self.definitions("-candidate")
        candidate.add("a")
        candidate.add("b", 4)
        catalog = self.load(candidate)
        self.candidate(self.tool.check_splits(catalog))
        self.candidate(self.tool.fit_scaler(catalog))

    def test_P12_raw_hash_paths_caps_and_cli(self):
        hashed = self.definitions("-hash")
        hashed.add("a")
        pin = hashed.pin()
        path = hashed.root / "records/a.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.rejects("hash_mismatch", lambda: self.tool.load_catalog(hashed.root, pin))
        for label, path_value in (("traversal", "records/../a.json"), ("absolute", str(path.resolve()))):
            with self.subTest(path=label):
                invalid = self.definitions("-" + label)
                invalid.add("a")
                invalid.entries[0]["record"]["path"] = path_value
                self.rejects("path_invalid", lambda: self.load(invalid))
        bounded = self.definitions("-cap")
        bounded.add("a")
        raw = encoded(bounded.rows["a"]["record"])
        bounded.rewrite("a", record_raw=raw + b" " * (16384 - len(raw)))
        self.candidate(self.tool.check_splits(self.load(bounded)))
        bounded.rewrite("a", record_raw=raw + b" " * (16385 - len(raw)))
        self.rejects("bounds_invalid", lambda: self.load(bounded))
        cli = self.definitions("-cli")
        cli.add("a")
        pin = cli.pin()
        command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(self.module_path),
                   "validate", str(cli.root), pin]
        type(self).cli_invocations += 1
        completed = subprocess.run(command, capture_output=True, timeout=5, check=False)
        (self.work_root / "CLI-validate.stdout.bin").write_bytes(completed.stdout)
        (self.work_root / "CLI-validate.stderr.bin").write_bytes(completed.stderr)
        type(self).cli_records.append({
            "argv": command, "exit_code": completed.returncode,
            "stdout_sha256": sha(completed.stdout), "stderr_sha256": sha(completed.stderr),
            "stdout_file": "CLI-validate.stdout.bin", "stderr_file": "CLI-validate.stderr.bin",
        })
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        self.assertLessEqual(len(completed.stdout), 131072)
        self.candidate(json.loads(completed.stdout.decode("utf-8")))

    def test_P13_labels_groups_not_features_and_snapshot(self):
        definition = self.training_pair()
        catalog = self.load(definition)
        first = self.tool.make_window(catalog, ["trainA", "trainB"], cutoff_ns=20, max_age_ns=100)
        for name in ("trainA", "trainB", "testC"):
            definition.rows[name]["group"]["target"]["label"] = "after-label-must-not-be-feature"
            definition.rows[name]["group"]["scene_id"] = "changed-scene-" + name
            definition.rows[name]["group"]["event_id"] = "changed-event-" + name
            definition.rewrite(name)
        changed = self.load(definition)
        second = self.tool.make_window(changed, ["trainA", "trainB"], cutoff_ns=20, max_age_ns=100)
        self.assertEqual(window_features(first), window_features(second))
        self.assertEqual(first, self.tool.make_window(catalog, ["trainA", "trainB"], cutoff_ns=20, max_age_ns=100))
        self.assert_no_group_or_target(first)
        definition.rows["trainA"]["record"]["layout"] = "forbidden-oracle"
        definition.rewrite("trainA")
        self.assertEqual(first, self.tool.make_window(catalog, ["trainA", "trainB"], cutoff_ns=20, max_age_ns=100))
        self.rejects("schema_invalid", lambda: self.load(definition))

    def assert_no_group_or_target(self, report):
        forbidden = {"group", "groups", "scene_id", "event_id", "target", "label", "seed",
                     "layout", "editor_history", "truth", "coordinates", "odometry"}
        def inspect(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)
        inspect(report)

    def test_P14_empty_support_and_exact_manifest(self):
        definition = self.definitions()
        definition.add("a", None, valid=False, reason="missing synthetic observation")
        definition.add("b", 7, fault="synthetic fault")
        report = self.tool.fit_scaler(self.load(definition))
        self.candidate(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(scaler_statistics(report)), 1)
        self.assertEqual(scaler_statistics(report)[0]["count"], 0)
        for stat in scaler_statistics(report):
            self.assertIsNone(stat["mean"])
            self.assertIsNone(stat["scale"])
            self.assertTrue(stat["reason"])
        constant = self.definitions("-constant")
        constant.add("a", 7)
        constant.add("b", 7)
        constant_fit = self.tool.fit_scaler(self.load(constant))
        self.candidate(constant_fit)
        self.assertEqual(constant_fit["status"], "blocked")
        self.assertEqual(scaler_statistics(constant_fit)[0]["reason"], "constant_values")
        self.assertIsNone(scaler_statistics(constant_fit)[0]["mean"])
        self.assertIsNone(scaler_statistics(constant_fit)[0]["scale"])
        positive = self.training_pair("-manifest")
        catalog = self.load(positive)
        fit = self.tool.fit_scaler(catalog)
        self.forged_manifest_controls(catalog, fit, positive)


class JSONResult(unittest.TextTestResult):
    """Keep the raw unittest stream on stderr and actual new-case counts on stdout."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.case_records = []
        self.by_id = {}

    def startTest(self, test):
        record = {"case_id": test.id().split(".")[-1], "status": "running", "subcases": []}
        self.case_records.append(record)
        self.by_id[test.id()] = record
        super().startTest(test)

    def addSuccess(self, test):
        self.by_id[test.id()]["status"] = "passed"
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.by_id[test.id()]["status"] = "failed"
        super().addFailure(test, err)

    def addError(self, test, err):
        self.by_id[test.id()]["status"] = "error"
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.by_id[test.id()]["status"] = "skipped"
        self.by_id[test.id()]["skip_reason"] = reason
        super().addSkip(test, reason)

    def addSubTest(self, test, subtest, err):
        record = self.by_id[test.id()]
        outcome = "passed" if err is None else ("failed" if issubclass(err[0], test.failureException) else "error")
        record["subcases"].append({"case_id": str(subtest), "status": outcome})
        if err is not None:
            if outcome == "error" or record["status"] != "error":
                record["status"] = outcome
        super().addSubTest(test, subtest, err)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.module.is_absolute() or not args.work_dir.is_absolute():
        parser.error("--module and --work-dir must be absolute")
    module_path = args.module.resolve(strict=True)
    if module_path != Path(__file__).resolve().with_name("causal_data.py"):
        parser.error("--module must be the adjacent new causal_data.py")
    if args.work_dir.is_symlink():
        parser.error("--work-dir cannot be a symlink")
    args.work_dir.mkdir(parents=True, exist_ok=True)
    work_root = args.work_dir.resolve(strict=True)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("c24_new_causal_data_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    IndependentC24.tool = module
    IndependentC24.work_root = work_root
    IndependentC24.module_path = module_path
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IndependentC24)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, resultclass=JSONResult).run(suite)
    report = {
        "kind": "new synthetic-definition C24 controls only",
        "qualified_physical_samples": 0, "model_or_training_runs": 0,
        "old_suites_or_fixtures": 0, "tests_run": result.testsRun,
        "passed": sum(item["status"] == "passed" for item in result.case_records),
        "failed": sum(item["status"] == "failed" for item in result.case_records),
        "errors": sum(item["status"] == "error" for item in result.case_records),
        "skipped": len(result.skipped),
        "failure_events": len(result.failures), "error_events": len(result.errors),
        "subcases_run": sum(len(item["subcases"]) for item in result.case_records),
        "CLI_invocations": IndependentC24.cli_invocations,
        "CLI_records": IndependentC24.cli_records,
        "cases": result.case_records, "success": result.wasSuccessful(),
    }
    print(encoded(report).decode("ascii"))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Pinned FORCE members -> separate targets and causal float32 curve windows.

No fitted statistic is changed. The source archive and each decompressed member
must match the existing reviewed inventory before any model feature is prepared.
The hardened inventory parser validates all LAS header/row identities. Public
fixed observations carry only the existing thirteen CurveObservation fields.
"""
from __future__ import annotations

from array import array
from collections import Counter
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

import torch

from data import force_inventory
from ai_pc.model.curve_input import CurveBinding, CurveObservation, CurveScaler, CurveWindowBuilder
from ai_pc.model.force_cnn import CLASS_ORDER, PREPROCESSING_SHA256, LABEL_SCHEMA_SHA256, sha256_file

ARCHIVE_SHA256 = "042ef1d473100dc12768cae7107a8cead071a394f137af3bc1ddaf8a5d1b8dda"
INVENTORY_SHA256 = "ace9a0eb9930f19c6b8125e151d07346fb23029b1455eac04964d15b97461e59"
SPLITS_SHA256 = "f10ddb8f37e6bdf7c9663eed45d0f6554ef8992899724013a7e487ad3e3cef91"
PUBLIC_MEMBER = "Force_2020_all_wells_train_test_blind_hidden_final/15_9-13.las"
PUBLIC_ROWS = (7327, 7454)
RUN_ID = "C-FORCE-CPU-20261024-v1"
CHANNELS = ("GR", "RHOB", "NPHI", "RDEP")
_PRODUCT = Path(__file__).resolve().parents[1]


@dataclass
class WellBuffer:
    member: str
    well_id: str
    root_id: str
    split: str
    features: torch.Tensor  # 8 x (127 + rows), startup padding exactly zero
    targets: torch.Tensor  # labels never appended to features
    confidence: torch.Tensor
    record: dict

    def windows(self, indices):
        view = self.features.unfold(1, 128, 1).permute(1, 0, 2)
        return view[indices].unsqueeze(-1).contiguous()


def normalize_sensor(values, valid, statistics):
    out, masks = [], []
    for index, (value, is_valid, stats) in enumerate(zip(values, valid, statistics)):
        usable = is_valid and (index != 3 or value > 0)
        if not usable:
            out.append(0.0)
            masks.append(0.0)
            continue
        transformed = math.log10(value) if index == 3 else value
        normalized = (transformed - stats.mean) / stats.effective_scale
        if not math.isfinite(normalized):
            raise ValueError("nonfinite normalized sensor")
        out.append(normalized)
        masks.append(1.0)
    return out + masks


def observation(sequence, values, valid):
    out = {"run_id": RUN_ID, "source_domain": "geo_replay", "profile_id": "force_curve_v1", "preprocessing_sha256": PREPROCESSING_SHA256, "sequence": sequence}
    out.update({"value_" + str(i): value for i, value in enumerate(values)})
    out.update({"valid_" + str(i): flag for i, flag in enumerate(valid)})
    return out


def _target(token, null, codes, what):
    if token is None:
        return -1
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("nonfinite " + what)
    if value == null:
        return -1
    if not value.is_integer() or int(value) not in codes:
        raise ValueError("unknown nonmissing " + what + ": " + token)
    return codes[int(value)]


class ForceSource:
    def __init__(self, archive):
        self.archive = Path(archive).resolve()
        if self.archive.stat().st_size != 169785172 or sha256_file(self.archive) != ARCHIVE_SHA256:
            raise ValueError("archive differs from frozen public FORCE source")
        for name, pin in (("force_wells.json", INVENTORY_SHA256), ("splits.json", SPLITS_SHA256), ("preprocessing.json", PREPROCESSING_SHA256), ("label_schema.json", LABEL_SCHEMA_SHA256)):
            if sha256_file(_PRODUCT / "data" / name) != pin:
                raise ValueError("fixed source file mismatch: " + name)
        self.inventory = json.loads((_PRODUCT / "data/force_wells.json").read_text(encoding="utf-8"))
        self.splits = json.loads((_PRODUCT / "data/splits.json").read_text(encoding="utf-8"))
        self.by_member = {item["member"]: item for item in self.inventory["wells"]}
        self.scaler = CurveScaler((_PRODUCT / "data/preprocessing.json").read_bytes(), expected_sha256=PREPROCESSING_SHA256)
        self.journal = []
        self.public_observations = []
        self.public_labels = []
        self.window_checks = []
        self.opened_splits = set()

    def load_split(self, split):
        if split not in ("train", "validation", "test") or split in self.opened_splits:
            raise ValueError("invalid or repeated split parse")
        self.opened_splits.add(split)
        rows = [row for row in self.splits["rows"] if row["split"] == split]
        if len(rows) != {"train": 82, "validation": 17, "test": 19}[split]:
            raise ValueError("frozen split member count mismatch")
        wells = []
        with zipfile.ZipFile(self.archive, "r") as zipped:
            if len(zipped.namelist()) != len(set(zipped.namelist())) or set(zipped.namelist()) != set(self.by_member):
                raise ValueError("archive member set mismatch")
            for row in rows:
                member = row["member"]
                known = self.by_member[member]
                if row["member_sha256"] != known["member_sha256"] or row["well_id"] != known["uwi"]:
                    raise ValueError("split/inventory identity differs")
                raw = zipped.read(member)  # zipfile verifies CRC on complete read
                if len(raw) != known["member_size_bytes"] or hashlib.sha256(raw).hexdigest() != known["member_sha256"]:
                    raise ValueError("member byte identity mismatch: " + member)
                checked = force_inventory.inventory_las_member(io.BytesIO(raw), member, len(raw))
                for key in ("rows", "uwi", "well", "null_value", "vers", "wrap", "member_sha256"):
                    if checked[key] != known[key]:
                        raise ValueError("hardened member validation mismatch: " + key)
                if [(c["mnemonic"], c["unit"]) for c in checked["curves"]] != [(c["mnemonic"], c["unit"]) for c in known["curves"]]:
                    raise ValueError("curve metadata differs")
                well = self._parse_verified(raw, row, known)
                wells.append(well)
                self.journal.append({"split": split, "member": member, "sha256": known["member_sha256"], "bytes": len(raw), "crc_verified": True, "rows": well.targets.numel()})
                print(json.dumps({"event": "prepared_well", "split": split, "well": row["well_id"], "rows": well.targets.numel()}), flush=True)
        return wells

    def _parse_verified(self, raw, row, known):
        names = [curve["mnemonic"].upper() for curve in known["curves"]]
        indices = [names.index(name) if name in names else None for name in CHANNELS]
        for name, index, unit in zip(CHANNELS, indices, ("gAPI", "g/cm3", "m3/m3", "ohm.m")):
            if index is not None and known["curves"][index]["unit"] != unit:
                raise ValueError("unsupported sensor unit: " + name)
        target_index = names.index("FORCE_2020_LITHOFACIES_LITHOLOGY") if "FORCE_2020_LITHOFACIES_LITHOLOGY" in names else None
        confidence_index = names.index("FORCE_2020_LITHOFACIES_CONFIDENCE") if "FORCE_2020_LITHOFACIES_CONFIDENCE" in names else None
        codes = {code: i for i, code in enumerate(CLASS_ORDER)}
        features, targets, confidences = array("f"), array("q"), bytearray()
        label_counts, confidence_counts = Counter(), Counter()
        raw_capture = {}
        section = None
        null = known["null_value"]
        row_index = 0
        capture = row["member"] == PUBLIC_MEMBER
        probe = row["split"] == "train" and len(self.window_checks) < 3
        for raw_line in force_inventory.iter_las_lines(io.BytesIO(raw), 1024 * 1024):
            line = raw_line.decode("ascii").strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("~"):
                section = line[1:].strip().split()[0].lower()
                continue
            if section not in ("ascii", "a"):
                continue
            tokens = line.split()
            if len(tokens) != len(names):
                raise ValueError("verified row cardinality changed")
            values, valid = [], []
            for index in indices:
                value = 0.0 if index is None else float(tokens[index])
                if not math.isfinite(value):
                    raise ValueError("nonfinite sensor value")
                flag = index is not None and value != null
                values.append(value if flag else 0.0)
                valid.append(flag)
            features.extend(normalize_sensor(values, valid, self.scaler.channels))
            target = _target(tokens[target_index] if target_index is not None else None, null, codes, "lithology label")
            confidence = _target(tokens[confidence_index] if confidence_index is not None else None, null, {1: 1, 2: 2, 3: 3}, "confidence label")
            targets.append(target)
            confidences.append(0 if confidence < 0 else confidence)
            label_counts[str(target)] += 1
            confidence_counts[str(confidence)] += 1
            if probe and row_index < 257:
                raw_capture[row_index] = (tuple(values), tuple(valid))
            if capture and PUBLIC_ROWS[0] <= row_index <= PUBLIC_ROWS[1]:
                self.public_observations.append(observation(row_index, values, valid))
                self.public_labels.append({"sequence": row_index, "class_index": target, "source_code": None if target < 0 else CLASS_ORDER[target], "confidence_code": None if confidence < 0 else confidence})
            row_index += 1
        if row_index != known["rows"]:
            raise ValueError("row count differs after feature preparation")
        tensor = torch.frombuffer(features, dtype=torch.float32).reshape(row_index, 8).T.contiguous()
        if not bool(torch.isfinite(tensor).all()):
            raise ValueError("normalized float32 overflow")
        padded = torch.cat((torch.zeros((8, 127), dtype=torch.float32), tensor), dim=1)
        target_tensor = torch.frombuffer(targets, dtype=torch.int64).clone()
        confidence_tensor = torch.frombuffer(confidences, dtype=torch.uint8).clone()
        record = {"member": row["member"], "well_id": row["well_id"], "root_id": row["root_id"], "split": row["split"], "rows": row_index, "label_counts": dict(label_counts), "confidence_counts": dict(confidence_counts), "missing_targets": label_counts.get("-1", 0)}
        well = WellBuffer(row["member"], row["well_id"], row["root_id"], row["split"], padded, target_tensor, confidence_tensor, record)
        if probe:
            binding = CurveBinding("training-equivalence-" + row["well_id"], "geo_replay", PREPROCESSING_SHA256)
            builder = CurveWindowBuilder(scaler=self.scaler, binding=binding)
            probes = (0, 1, 31, 127, 128, 256)
            for index, (values, flags) in raw_capture.items():
                builder.observe(CurveObservation(binding, index, values, flags))
                if index in probes:
                    expected = torch.tensor(builder.snapshot().to_model_input(), dtype=torch.float32)
                    actual = well.windows(torch.tensor([index]))
                    if not torch.equal(expected, actual):
                        raise ValueError("causal buffer differs from existing CurveWindowBuilder")
            self.window_checks.append({"member": row["member"], "sequences": list(probes), "float32_exact_equal": True, "startup_padding": True, "future_inputs": False})
        return well

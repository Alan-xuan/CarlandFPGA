"""Copy exact historical Git bytes into pin-only provenance snapshots."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
REPO = PRODUCT.parents[1]
COMMIT = "31267d6c4ae284b8788ebb457f49c4ae5a49c60c"
EXPECTED = {"force_inventory.py": ("e37e07250d14fc9031b18a81a3eaa4c752e4a769", "5bba8316ea36484df058dacb2289073ffb09ce19e401dfb297598b3e3cd10f47"),
            "force_preprocess.py": ("f3e7036e41d44362f65ed0b887ea62070a639f2d", "75b2015c0ec9deab9a94a2032b77117124085631f2bd758a54c7ea7fdfdf2848")}
records = []
for name, (expected_blob, expected_sha256) in EXPECTED.items():
    original = "competition/deepeye/data/" + name
    command = ["git", "-C", str(REPO), "show", COMMIT + ":" + original]
    response = subprocess.run(command, capture_output=True, check=True)
    raw = response.stdout
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    digest = hashlib.sha256(raw).hexdigest()
    assert blob == expected_blob and digest == expected_sha256
    target = PRODUCT / "data/provenance/force_2020_v1" / name
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    records.append({"source_commit": COMMIT, "source_path": original, "git_blob_sha1": blob,
                    "sha256": digest, "bytes": len(raw), "path": str(target.relative_to(PRODUCT)),
                    "executed": False})
prior = PRODUCT / "evidence/ai/data_boundary_repair"
prior_files = ("candidate_verify_suite.result.json", "candidate_verify_suite.stderr.txt")
receipt = {"copied_utc": datetime.now(timezone.utc).isoformat(), "snapshots": records,
           "preserved_prior_red": {str((prior / name).relative_to(PRODUCT)): hashlib.sha256((prior / name).read_bytes()).hexdigest() for name in prior_files}}
(HERE / "snapshot-source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))

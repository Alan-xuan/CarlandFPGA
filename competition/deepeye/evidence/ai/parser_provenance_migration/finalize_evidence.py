"""Finalize exact byte evidence and release only this assignment's ownership."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
REPO = PRODUCT.parents[1]
SNAPSHOTS = PRODUCT / "data/provenance/force_2020_v1"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

green = json.loads((HERE / "green_full.command.json").read_bytes())
assert green["exit_code"] == 0
green_text = (HERE / "green_full.stderr.txt").read_text()
assert "Ran 57 tests" in green_text and re.search(r"\nOK\s*$", green_text)
assert "skipped=" not in green_text
frozen = green["frozen_documents_before"]
assert frozen == green["frozen_documents_after"] == {name: sha(PRODUCT / name) for name in frozen}
assert sha(PRODUCT / "data/force_inventory.py") == "86404425615f7551ce04907c9dbd6d7a40edca76372ad82a1a9655092a186932"
assert sha(PRODUCT / "data/force_preprocess.py") == "1cc71d045065495d99a3f79c31107705cdc3a4942409a8decf6ae732501bc308"
assert sha(PRODUCT / "data/grouping.py") == "f1a35a5b060cafb640d8f65b2914af9616258b7fa21f99d1a589d232f7b2be4d"
receipt = json.loads((HERE / "snapshot-source-receipt.json").read_bytes())
for record in receipt["snapshots"]:
    assert sha(PRODUCT / record["path"]) == record["sha256"]
for relative, expected in receipt["preserved_prior_red"].items():
    assert sha(PRODUCT / relative) == expected
prior_stderr = PRODUCT / "evidence/ai/data_boundary_repair/candidate_verify_suite.stderr.txt"
assert "failures=4" in prior_stderr.read_text()
paths = ["competition/deepeye/tools/verify_data.py", "competition/deepeye/tests/ai/data_model/test_verify_data.py"]
diff = subprocess.run(["git", "-C", str(REPO), "diff", "--", *paths], capture_output=True, check=True)
(HERE / "reviewable.diff.txt").write_bytes(diff.stdout)
check = subprocess.run(["git", "-C", str(REPO), "diff", "--check", "--", *paths], capture_output=True)
assert check.returncode == 0
(HERE / "diff_check.stdout.txt").write_bytes(check.stdout)
(HERE / "diff_check.stderr.txt").write_bytes(check.stderr)
(HERE / "diff_check.command.json").write_text(json.dumps({"command": ["git", "diff", "--check", "--", *paths],
    "cwd": str(REPO), "exit_code": check.returncode, "stdout_sha256": hashlib.sha256(check.stdout).hexdigest(),
    "stderr_sha256": hashlib.sha256(check.stderr).hexdigest()}, indent=2) + "\n", encoding="utf-8")
summary = {"task_id": "DEEPEYE-IMPLEMENTATION-20261014", "task_version": 1,
           "work_id": "C-parser-provenance-migration-20261018-v1", "actual_agent_id": "/root/host_contract_review",
           "requirements_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
           "frozen_json_unchanged": frozen, "grouping_sha256": sha(PRODUCT / "data/grouping.py"),
           "current_parser_sha256": {name: sha(PRODUCT / name) for name in ("data/force_inventory.py", "data/force_preprocess.py")},
           "historical_snapshots": receipt["snapshots"], "prior_red_unchanged": receipt["preserved_prior_red"],
           "source_sha256": {name: sha(PRODUCT / name) for name in ("tools/verify_data.py", "tests/ai/data_model/test_verify_data.py")},
           "red": {"tests": 57, "failures": 10, "archive_skips": 3, "exit_code": 1},
           "green": {"tests": 57, "failures": 0, "skips": 0, "exit_code": 0,
                     "raw_stderr_sha256": sha(HERE / "green_full.stderr.txt")},
           "software_scope": "offline byte provenance/identity consistency only; historical snapshots never executed; no LAS parse/refit/labels/evaluation",
           "formal_acceptance": "not_run"}
(HERE / "validation-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
artifacts = [PRODUCT / "tools/verify_data.py", PRODUCT / "tests/ai/data_model/test_verify_data.py"]
artifacts += [p for p in SNAPSHOTS.rglob("*") if p.is_file()]
artifacts += [p for p in HERE.rglob("*") if p.is_file() and p.name not in ("manifest.json", "release.json")]
manifest = {"scope": "assignment artifacts only; manifest and final release excluded to avoid self-reference",
            "artifacts": [{"path": str(p.relative_to(PRODUCT)).replace("\\", "/"), "bytes": p.stat().st_size,
                           "sha256": sha(p)} for p in sorted(artifacts)]}
(HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
release = {"work_id": summary["work_id"], "actual_agent_id": summary["actual_agent_id"],
           "completed_utc": datetime.now(timezone.utc).isoformat(), "status": "complete", "ownership_released": True,
           "remaining_product_writes": False, "manifest_sha256": sha(HERE / "manifest.json"),
           "validation_summary_sha256": sha(HERE / "validation-summary.json"), "source_sha256": summary["source_sha256"],
           "formal_acceptance": "not_run"}
(HERE / "release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"release": release, "release_sha256": sha(HERE / "release.json"), "artifact_count": len(artifacts)}))

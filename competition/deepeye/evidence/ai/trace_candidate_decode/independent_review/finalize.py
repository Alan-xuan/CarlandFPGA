"""Bind the private review result and release only its assigned directory."""

import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


result = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
assert result["exit_code"] == 0 and result["candidate_unchanged_during_review"]
assert sha(HERE / "candidate_snapshot.py") == result["candidate_sha256"]
assert sha(ROOT / ".local/deepeye-implementation-c/competition/deepeye/evidence/ai/trace_candidate_decode/candidate_decode.py") == result["candidate_sha256"]
assert sha(HERE / "probe.py") == result["probe_sha256"]
assert sha(HERE / "stdout.txt") == result["stdout_sha256"]
assert sha(HERE / "stderr.txt") == result["stderr_sha256"]
for name, record in result["normative_inputs"].items():
    assert sha(HERE / "normative_inputs" / name) == record["sha256"]
release = dict(
    task_id=result["task_id"], task_version=result["task_version"],
    work_id=result["work_id"], actual_agent_id=result["actual_agent_id"],
    released_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    state="completed read-only review; no further writes/execution; private review ownership released to /root",
    released_paths=[".local/main-20261015-01a14025/watch-20261018/trace-adversarial-review/**"],
    candidate_sha256=result["candidate_sha256"], bounded_result="5 targeted methods passed; no defect found",
    candidate_source_ownership="remains with /root/trace_decoder; no transfer performed",
    production_runtime_hardware_acceptance="not_run",
)
assert not (HERE / "release.json").exists()
assert not (HERE / "manifest.json").exists()
(HERE / "release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
manifest = {
    "artifacts": {path.relative_to(HERE).as_posix(): {"sha256": sha(path), "bytes": path.stat().st_size}
                  for path in sorted(HERE.rglob("*")) if path.is_file()}
}
(HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": "released", "candidate_sha256": result["candidate_sha256"],
                  "manifest_sha256": sha(HERE / "manifest.json")}, indent=2))

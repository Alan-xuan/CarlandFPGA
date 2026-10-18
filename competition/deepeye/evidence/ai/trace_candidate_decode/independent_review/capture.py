"""Freeze C-only review inputs and preserve raw targeted-review results."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CANDIDATE = ROOT / ".local/deepeye-implementation-c/competition/deepeye/evidence/ai/trace_candidate_decode"
EXPECTED_SOURCE = "b02010280b72d3a94842db627f733df9c1fa6ecfe54f572509d57869d2d3d72c"
NORMATIVE = ("main_candidate_spec.md", "TRACE_CANDIDATE.md", "trace_candidate_layout.json",
             "main_manual_vectors.json", "trace_candidate_vectors.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    source = CANDIDATE / "candidate_decode.py"
    assert digest(source) == EXPECTED_SOURCE, "source changed; obtain new stable review hash"
    if (HERE / "result.json").exists():
        raise RuntimeError("review already recorded")
    shutil.copyfile(source, HERE / "candidate_snapshot.py")
    assert digest(HERE / "candidate_snapshot.py") == EXPECTED_SOURCE
    inputs = HERE / "normative_inputs"
    inputs.mkdir(exist_ok=False)
    pinned = {}
    for name in NORMATIVE:
        path = inputs / name
        shutil.copyfile(CANDIDATE / "inputs" / name, path)
        pinned[name] = {"sha256": digest(path), "bytes": path.stat().st_size}
    assert pinned["main_candidate_spec.md"]["sha256"] == "7bc33ebc28c9f08e200c539a1a59c07b42b36211cb49b08ac449875bf75f9a73"
    assert pinned["main_manual_vectors.json"]["sha256"] == "36b8e3fdb53e3c8fc911cc44b4f4151d62863d2e05b189f68c42fefe869b2d24"
    human_scope = json.loads((CANDIDATE / "inputs/immutable_scope.json").read_bytes())
    human_hash = hashlib.sha256(json.dumps(human_scope["requirements"], ensure_ascii=False,
                                          sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert human_hash == "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
    command = [sys.executable, "-B", "-X", "utf8", str(HERE / "probe.py")]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    environment = dict(os.environ); environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, env=environment)
    (HERE / "stdout.txt").write_bytes(completed.stdout)
    (HERE / "stderr.txt").write_bytes(completed.stderr)
    result = dict(
        task_id="DEEPEYE-IMPLEMENTATION-20261014", task_version=1,
        work_id="C-independent-trace-adversarial-review-20261018-v1",
        actual_agent_id="/root/data_boundary_repair", command=command, cwd=str(ROOT),
        started_utc=started, completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        exit_code=completed.returncode, python=sys.version, candidate_sha256=EXPECTED_SOURCE,
        candidate_unchanged_during_review=digest(source) == EXPECTED_SOURCE,
        normative_inputs=pinned, stdout_sha256=digest(HERE / "stdout.txt"),
        stderr_sha256=digest(HERE / "stderr.txt"), probe_sha256=digest(HERE / "probe.py"),
        contract="DEEPEYE-HUMAN-LOCK-20261014/revision1", requirements_sha256=human_hash,
        design_commit="1011259415a0916054eb580687612580bc1e5f09",
        exclusions="No B implementation/scripts/oracle; no production/runtime/ABI/clock/units/schedule/board acceptance",
    )
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

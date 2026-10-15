"""Capture exact software-test bytes and immutable A fixtures; stdlib only.

Run with an interpreter that already provides jsonschema for A's unchanged
reference validator. The production C adapter itself uses only stdlib.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
WORKTREE = PRODUCT.parents[1]
DEPLOYMENT = WORKTREE.parents[1]
COMMIT = "d5bf26adcf76f8c9af3165cdd7043cb3ff19649b"
LOCK = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"


def save_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def hashes(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}


def references(source):
    destination = HERE / "reference"
    base = json.loads((source / "reference-manifest.json").read_bytes())
    assert base["commit"] == COMMIT
    assert base["requirements_sha256"] == LOCK
    entries = base["files"] + json.loads((source / "supplementary-manifest.json").read_bytes())
    fixed = []
    for entry in entries:
        raw = (source / entry["local_file"]).read_bytes()
        actual = hashes(raw)
        for key in ("sha256", "git_blob_sha1", "bytes"):
            assert actual[key] == entry[key], (entry["path"], key)
        relative = Path(entry["path"]).relative_to("competition/deepeye")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        fixed.append({"source_path": entry["path"], "fixture_path": relative.as_posix(), **actual})
    for name in ("reference-manifest.json", "supplementary-manifest.json"):
        shutil.copyfile(source / name, destination / name)
    save_json(destination / "manifest.json", {
        "repository": base["repository"], "pull_request": 24, "commit": COMMIT,
        "frozen_base": base["frozen_base"], "contract_id": base["contract_id"],
        "requirements_sha256": LOCK,
        "purpose": "Unchanged exact A bytes for software interoperability only; no runtime proof",
        "files": fixed})


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-source", type=Path)
    arguments = parser.parse_args()
    if arguments.reference_source is not None:
        references(arguments.reference_source)
    serial = 1
    while (HERE / f"run_{serial:03d}").exists():
        serial += 1
    output = HERE / f"run_{serial:03d}"
    output.mkdir()
    python = [sys.executable, "-B", "-X", "utf8"]
    commands = [
        ("scope", WORKTREE, python + ["docs/competition/deepeye-2026/verify_immutable_scope.py",
                                      "--expected-sha", LOCK], 0),
        ("review_repair1_negative_control", PRODUCT,
            python + [str(HERE / "review_repair1/negative_control.py")], 1),
        ("motion_request", PRODUCT, python + ["-m", "unittest", "discover", "-s",
                  "tests/ai/control_broker", "-p", "test_motion_request.py", "-v"], 0),
        ("mailbox_regression", PRODUCT, python + ["-m", "unittest", "discover", "-s",
                  "tests/ai/control_broker", "-p", "test_mailbox.py", "-v"], 0),
        ("deadline_regression", PRODUCT, python + ["-m", "unittest", "discover", "-s",
                  "tests/ai/control_broker", "-p", "test_deadlines.py", "-v"], 0),
    ]
    records = []
    for name, cwd, command, expected_exit_code in commands:
        started = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False)
        (output / f"{name}.stdout.txt").write_bytes(result.stdout)
        (output / f"{name}.stderr.txt").write_bytes(result.stderr)
        record = {"name": name, "cwd": str(cwd), "command": command,
                  "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
                  "exit_code": result.returncode, "expected_exit_code": expected_exit_code,
                  "stdout": {"path": f"{name}.stdout.txt", **hashes(result.stdout)},
                  "stderr": {"path": f"{name}.stderr.txt", **hashes(result.stderr)}}
        records.append(record)
        print(f"{name}: exit {result.returncode}")
    sources = [PRODUCT / "ai_pc/control_broker/motion_request.py",
               PRODUCT / "ai_pc/control_broker/mailbox.py",
               PRODUCT / "ai_pc/control_broker/deadlines.py",
               PRODUCT / "tests/ai/control_broker/test_motion_request.py", Path(__file__),
               PRODUCT / "tests/ai/control_broker/test_mailbox.py",
               PRODUCT / "tests/ai/control_broker/test_deadlines.py",
               WORKTREE / "docs/competition/deepeye-2026/immutable_scope.md",
               WORKTREE / "docs/competition/deepeye-2026/immutable_scope.json",
               WORKTREE / "docs/competition/deepeye-2026/verify_immutable_scope.py",
               HERE / "README.md", HERE / "reference/manifest.json",
               HERE / "review_repair1/README.md", HERE / "review_repair1/negative_control.py",
               HERE / "review_repair1/pre_repair/motion_request.py",
               HERE / "review_repair1/pre_repair/test_motion_request.py"]
    snapshot = [{"path": path.relative_to(WORKTREE).as_posix(), **hashes(path.read_bytes())}
                for path in sources]
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=WORKTREE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    save_json(output / "manifest.json", {
        "work_id": "C-motion-request-adapter-review-repair1-20261015-v1",
        "parent_work_id": "C-motion-request-adapter-20261015-v1",
        "task_id": "DEEPEYE-IMPLEMENTATION-20261014", "task_version": 1,
        "base_commit": git.stdout.decode().strip(), "A_reference_commit": COMMIT,
        "contract_id": "DEEPEYE-HUMAN-LOCK-20261014/revision1", "requirements_sha256": LOCK,
        "frozen_design": "1011259415a0916054eb580687612580bc1e5f09",
        "python": sys.version, "python_executable": sys.executable,
        "platform": platform.platform(), "reference_dependency_jsonschema": importlib.metadata.version("jsonschema"),
        "commands": records, "source_hashes": snapshot,
        "stages": {"software_tests": "passed" if all(r["exit_code"] == r["expected_exit_code"] for r in records) else "failed",
                   "authenticated_runtime_clock_source_liveness": "not_run",
                   "HIL_execution": "not_run", "PC_DIRECT_execution": "not_run",
                   "physical_board": "not_run", "system_acceptance": "not_run"},
        "limitations": ["Runtime verifier is absent by default; test verifier is deliberately fake.",
                        "No live transport, process ACL, source liveness, measured clock or holdover proof.",
                        "No A motion_grant, physical capture, hardware or complete-route claim.",
                        "Single adapter/allocator lifetime must be integrated for each negotiated session."]})
    print(output.relative_to(WORKTREE).as_posix())
    return int(any(record["exit_code"] != record["expected_exit_code"] for record in records))


if __name__ == "__main__":
    raise SystemExit(run())

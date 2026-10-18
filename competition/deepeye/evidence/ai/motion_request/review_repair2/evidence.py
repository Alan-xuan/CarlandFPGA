"""Byte-preserving capture for the bounded 2026-10-18 callback repair."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[3]
WORKTREE = PRODUCT.parents[1]
DEPLOYMENT = WORKTREE.parents[1]
BASE = "31267d6c4ae284b8788ebb457f49c4ae5a49c60c"
WORK_ID = "C-motion-adapter-verifier-reentrancy-fix-20261018-v1"
LOCK = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
SOURCES = ("competition/deepeye/ai_pc/control_broker/motion_request.py",
           "competition/deepeye/tests/ai/control_broker/test_motion_request.py")


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}


def save(path, value):
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def source_hashes():
    return [{"path": path, **identity((WORKTREE / path).read_bytes())} for path in SOURCES]


def run_command(label, expected, cwd, command):
    metadata_path = HERE / (label + ".command.json")
    if metadata_path.exists():
        raise ValueError("refusing to overwrite an evidence command")
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False)
    stdout_path = HERE / (label + ".stdout.txt")
    stderr_path = HERE / (label + ".stderr.txt")
    stdout_path.write_bytes(result.stdout)
    stderr_path.write_bytes(result.stderr)
    save(metadata_path, {"work_id": WORK_ID, "cwd": str(cwd), "command": command,
        "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
        "actual_exit_code": result.returncode, "expected_exit_code": expected,
        "expected_result": result.returncode == expected,
        "source_hashes": source_hashes(),
        "stdout": {"path": stdout_path.name, **identity(result.stdout)},
        "stderr": {"path": stderr_path.name, **identity(result.stderr)}})
    print(f"{label}: exit {result.returncode}, expected {expected}")
    return int(result.returncode != expected)


def capture():
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE).decode().strip()
    assert actual == BASE, actual
    destination = HERE / "pre_repair"
    destination.mkdir()
    files = []
    for relative in SOURCES:
        raw = (WORKTREE / relative).read_bytes()
        blob_raw = subprocess.check_output(["git", "show", f"{BASE}:{relative}"], cwd=WORKTREE)
        assert raw == blob_raw, f"working bytes differ from original Git blob: {relative}"
        target = destination / Path(relative).name
        target.write_bytes(raw)
        files.append({"source_path": relative, "preserved_path": target.relative_to(HERE).as_posix(),
                      **identity(raw)})
    save(HERE / "original_manifest.json", {"task_id": "DEEPEYE-IMPLEMENTATION-20261014",
        "task_version": 1, "work_id": WORK_ID, "base_commit": BASE,
        "contract_id": "DEEPEYE-HUMAN-LOCK-20261014/revision1", "requirements_sha256": LOCK,
        "frozen_design_commit": "1011259415a0916054eb580687612580bc1e5f09",
        "python": sys.version, "python_executable": sys.executable, "files": files})
    for label, endpoint in (
        ("A_feedback_6206605911", "repos/carolwjade/CarlandFPGA/issues/comments/6206605911"),
        ("A_prior_approval_5541868728", "repos/carolwjade/CarlandFPGA/pulls/25/reviews/5541868728")):
        if run_command(label, 0, DEPLOYMENT, ["gh", "api", endpoint]):
            return 1
    return 0


def finalize():
    commands = []
    for path in sorted(HERE.glob("*.command.json")):
        record = json.loads(path.read_bytes())
        commands.append({"path": path.name, "actual_exit_code": record["actual_exit_code"],
                         "expected_exit_code": record["expected_exit_code"],
                         "expected_result": record["expected_result"]})
    required = {name + ".command.json" for name in (
        "scope", "red_original", "green_targeted", "green_adapter_full",
        "green_mailbox", "green_deadlines", "red_original_replay")}
    verified = required <= {item["path"] for item in commands} and all(
        item["expected_result"] for item in commands)
    artifacts = []
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            artifacts.append({"path": path.relative_to(HERE).as_posix(), **identity(path.read_bytes())})
    save(HERE / "manifest.json", {"task_id": "DEEPEYE-IMPLEMENTATION-20261014", "task_version": 1,
        "work_id": WORK_ID, "base_commit": BASE, "source_hashes": source_hashes(),
        "contract_id": "DEEPEYE-HUMAN-LOCK-20261014/revision1", "requirements_sha256": LOCK,
        "frozen_design_commit": "1011259415a0916054eb580687612580bc1e5f09",
        "python": sys.version, "python_executable": sys.executable,
        "jsonschema_version_for_A_fixture_only": importlib.metadata.version("jsonschema"),
        "commands": commands, "artifacts": artifacts,
        "stages": {"software_red_green": "passed" if verified else "incomplete",
                   "measured_clock_source_liveness": "not_run", "transport_runtime": "not_run",
                   "PC_DIRECT_execution": "not_run", "HIL_execution": "not_run",
                   "physical_board": "not_run", "system_acceptance": "not_run"},
        "limits": "Software callback/state tests only; no authenticated runtime or movement proof."})
    print(json.dumps(source_hashes()))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "run", "finalize"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parsed = parser.parse_args()
    if parsed.mode == "capture":
        raise SystemExit(capture())
    if parsed.mode == "finalize":
        raise SystemExit(finalize())
    label, expected, cwd, *command = parsed.args
    if command and command[0] == "--":
        command = command[1:]
    raise SystemExit(run_command(label, int(expected), Path(cwd), command))

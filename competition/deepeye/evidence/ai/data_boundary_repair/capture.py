"""Record exact subprocess bytes and exit codes for this bounded repair."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
WORKTREE = PRODUCT.parents[1]
DEPLOYMENT = WORKTREE.parents[1]
SOURCES = (
    "data/force_inventory.py",
    "data/force_preprocess.py",
    "tests/ai/data_model/test_force_inventory.py",
    "tests/ai/data_model/test_force_preprocess.py",
    "tests/ai/data_model/test_verify_data.py",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot():
    destination = HERE / "original"
    destination.mkdir(exist_ok=False)
    records = {}
    for relative in SOURCES:
        raw = (PRODUCT / relative).read_bytes()
        saved = destination / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(raw)
        records[relative] = {"bytes": len(raw), "sha256": sha(raw)}
    # Canonical artifacts are read and hashed only; never generated or refitted.
    unchanged = (
        "tools/verify_data.py", "data/source_inventory.json", "data/force_wells.json",
        "data/splits.json", "data/split_policy.json", "data/label_schema.json",
        "data/preprocessing.json", "data/grouping.py",
    )
    metadata = {
        "base_commit": "31267d6c4ae284b8788ebb457f49c4ae5a49c60c",
        "original_sources": records,
        "untouched_artifacts": {
            relative: {"sha256": sha((PRODUCT / relative).read_bytes()),
                       "bytes": (PRODUCT / relative).stat().st_size}
            for relative in unchanged
        },
    }
    (HERE / "original_sha256.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def capture(label, command, cwd=WORKTREE):
    if any((HERE / (label + suffix)).exists() for suffix in (".stdout.txt", ".stderr.txt", ".result.json")):
        raise RuntimeError("evidence label already exists: " + label)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True)
    (HERE / (label + ".stdout.txt")).write_bytes(proc.stdout)
    (HERE / (label + ".stderr.txt")).write_bytes(proc.stderr)
    result = {
        "command": command, "cwd": str(cwd), "started_utc": started,
        "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "exit_code": proc.returncode, "python": sys.version,
        "TEMP": os.environ.get("TEMP"), "TMP": os.environ.get("TMP"),
        "archive_override_set": bool(os.environ.get("DEEPEYE_FORCE_ARCHIVE")),
        "stdout_sha256": sha(proc.stdout), "stderr_sha256": sha(proc.stderr),
        "sources": {relative: sha((PRODUCT / relative).read_bytes()) for relative in SOURCES},
    }
    (HERE / (label + ".result.json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(label, "exit", proc.returncode, "stdout", len(proc.stdout), "stderr", len(proc.stderr))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.label == "snapshot":
        snapshot()
    else:
        capture(args.label, args.command)

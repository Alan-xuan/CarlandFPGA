"""Capture bounded verification evidence; no historical helper execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
PROJECT = PRODUCT.parents[3]
FROZEN = ("source_inventory", "force_wells", "splits", "split_policy", "label_schema", "preprocessing")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

parser = argparse.ArgumentParser()
parser.add_argument("name")
parser.add_argument("--real-archive", action="store_true")
parser.add_argument("arguments", nargs=argparse.REMAINDER)
args = parser.parse_args()
arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("DEEPEYE_FORCE_ARCHIVE", None)
if args.real_archive:
    archive = PROJECT / ".local/datasets/force-2020/LAS_files_Force_2020_all_wells_train_test_blind_hidden_final.zip"
    assert archive.is_file(), archive
    env["DEEPEYE_FORCE_ARCHIVE"] = str(archive)
before = {"data/" + name + ".json": digest(PRODUCT / "data" / (name + ".json")) for name in FROZEN}
command = [sys.executable, "-B", "-X", "utf8"] + arguments
start = datetime.now(timezone.utc).isoformat()
response = subprocess.run(command, cwd=PRODUCT, env=env, capture_output=True)
after = {name: digest(PRODUCT / name) for name in before}
assert before == after, "frozen documents changed"
for stream in ("stdout", "stderr"):
    (HERE / (args.name + "." + stream + ".txt")).write_bytes(getattr(response, stream))
record = {"started_utc": start, "finished_utc": datetime.now(timezone.utc).isoformat(), "command": command,
          "cwd": str(PRODUCT), "python": sys.version, "exit_code": response.returncode,
          "archive_environment": env.get("DEEPEYE_FORCE_ARCHIVE"),
          "stdout_sha256": hashlib.sha256(response.stdout).hexdigest(), "stderr_sha256": hashlib.sha256(response.stderr).hexdigest(),
          "frozen_documents_before": before, "frozen_documents_after": after,
          "tool_sha256": digest(PRODUCT / "tools/verify_data.py"),
          "test_sha256": digest(PRODUCT / "tests/ai/data_model/test_verify_data.py")}
(HERE / (args.name + ".command.json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"name": args.name, "exit_code": response.returncode, "stdout_sha256": record["stdout_sha256"],
                  "stderr_sha256": record["stderr_sha256"], "stderr_tail": response.stderr.decode("utf-8", "replace")[-1800:]}))
raise SystemExit(response.returncode)

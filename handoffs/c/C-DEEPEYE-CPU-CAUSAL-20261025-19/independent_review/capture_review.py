import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

out = Path(__file__).resolve().parent
root = Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c")
argv = [str(root / ".local/cpu-model-env-20261024/Scripts/python.exe"), "-B", "-X", "utf8", str(out / "review_frozen_artifacts.py")]
command = {"argv": argv, "cwd": str(root), "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
(out / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
with (out / "stdout.txt").open("wb") as stdout, (out / "stderr.txt").open("wb") as stderr:
    completed = subprocess.run(argv, cwd=root, stdout=stdout, stderr=stderr)
result = {**command, "exit_code": completed.returncode, "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
for stream in ("stdout", "stderr"):
    raw = (out / (stream + ".txt")).read_bytes()
    result[stream] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
(out / "execution-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
print((out / "stdout.txt").read_text(encoding="utf-8"))
if completed.returncode:
    print((out / "stderr.txt").read_text(encoding="utf-8"), file=sys.stderr)
raise SystemExit(completed.returncode)

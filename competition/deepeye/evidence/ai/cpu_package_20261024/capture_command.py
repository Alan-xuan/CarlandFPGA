"""Worker-local exact command capture; no background jobs or peer transport."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

folder = Path(sys.argv[1]).resolve()
folder.mkdir(parents=True, exist_ok=False)
command = sys.argv[2:]
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
(folder / "command.json").write_text(json.dumps({"argv": command, "cwd": os.getcwd(), "start_utc": start,
    "explicit_test_model_manifest_sha256": os.environ.get("DEEPEYE_CPU_EXPECTED_MANIFEST_SHA256")}, indent=2) + "\n", encoding="utf-8")
result = subprocess.run(command, capture_output=True)
(folder / "stdout.txt").write_bytes(result.stdout)
(folder / "stderr.txt").write_bytes(result.stderr)
record = {"exit_code": result.returncode, "end_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(), "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}
(folder / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
if len(result.stdout) <= 8192:
    sys.stdout.buffer.write(result.stdout)
else:
    print("stdout preserved:", str(folder / "stdout.txt"), len(result.stdout), "bytes")
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)

"""Bounded worker capture for new stdlib trajectory tests only."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
folder = Path(sys.argv[1]).resolve()
folder.mkdir(parents=True, exist_ok=False)
command = sys.argv[2:]
sources = ["competition/deepeye/ai_pc/planning/trajectory_candidates.py",
           "competition/deepeye/ai_pc/planning/swept_capsule.py",
           "competition/deepeye/tests/ai/planning/test_trajectory_candidates.py",
           "competition/deepeye/tests/ai/planning/test_swept_capsule.py"]
pins = {}
for source in sources:
    raw = (root / source).read_bytes()
    target = folder / "source-before" / source
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    pins[source] = hashlib.sha256(raw).hexdigest()
record = {"argv": command, "cwd": str(root), "sources_before": pins,
          "utc_start": datetime.datetime.now(datetime.timezone.utc).isoformat()}
(folder / "command.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
result = subprocess.run(command, capture_output=True)
(folder / "stdout.txt").write_bytes(result.stdout)
(folder / "stderr.txt").write_bytes(result.stderr)
record = {"exit_code": result.returncode, "utc_end": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
          "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}
(folder / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)

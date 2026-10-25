"""Capture only the new bounded-init constructor controls and current sources."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

folder = Path(sys.argv[1]).resolve()
folder.mkdir(parents=True, exist_ok=False)
sources = ("competition/deepeye/ai_pc/cpu_package/stream_core.py",
           "competition/deepeye/ai_pc/cpu_package/STREAM_CORE.md",
           "competition/deepeye/tests/ai/cpu/test_stream_core.py",
           "competition/deepeye/tests/ai/cpu/test_stream_init_bounds.py")
pins = {}
for name in sources:
    data = Path(name).read_bytes()
    target = folder / "source-before" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    pins[name] = hashlib.sha256(data).hexdigest()
command = sys.argv[2:]
(folder / "command.json").write_text(json.dumps({"argv": command, "cwd": str(Path.cwd()),
    "source_sha256_before": pins, "start_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}, indent=2) + "\n", encoding="utf-8")
result = subprocess.run(command, capture_output=True)
(folder / "stdout.txt").write_bytes(result.stdout)
(folder / "stderr.txt").write_bytes(result.stderr)
record = {"exit_code": result.returncode, "end_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(), "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}
(folder / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)

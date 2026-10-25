import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

here = Path(__file__).resolve().parent
name, cwd, *argv = sys.argv[1:]
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
command = {'argv': argv, 'cwd': cwd, 'started_utc': started}
(here / (name + '.command.json')).write_text(json.dumps(command, indent=2) + '\n', encoding='utf-8')
with (here / (name + '.stdout.txt')).open('wb') as out, (here / (name + '.stderr.txt')).open('wb') as err:
    result = subprocess.run(argv, cwd=cwd, stdout=out, stderr=err)
command.update(exit_code=result.returncode, finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
for channel in ('stdout', 'stderr'):
    raw = (here / (name + '.' + channel + '.txt')).read_bytes()
    command[channel] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
(here / (name + '.result.json')).write_text(json.dumps(command, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'name': name, 'exit_code': result.returncode}), flush=True)
sys.exit(result.returncode)

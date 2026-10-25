from pathlib import Path
import datetime as dt
import hashlib
import json
import subprocess

here=Path(__file__).resolve().parent
root=here.parents[3]
argv=[str(root/'.local/cpu-model-env-20261024/Scripts/python.exe'),'-B','-X','utf8',
      str(here/'main_probe.py'),'--root',str(root/'.local/deepeye-implementation-c'),
      '--controls',str(here/'analytic-controls.json')]
command={'argv':argv,'cwd':str(root),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
with (here/'command.json').open('x',encoding='utf-8') as f: json.dump(command,f,indent=2)
r=subprocess.run(argv,cwd=root,capture_output=True)
for name,data in [('stdout.txt',r.stdout),('stderr.txt',r.stderr)]:
    with (here/name).open('xb') as f: f.write(data)
result={'argv':argv,'exit_code':r.returncode,'finished_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()}
with (here/'execution-result.json').open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
print(json.dumps(result))
if r.returncode: print(r.stderr.decode('utf-8','replace'))
raise SystemExit(r.returncode)

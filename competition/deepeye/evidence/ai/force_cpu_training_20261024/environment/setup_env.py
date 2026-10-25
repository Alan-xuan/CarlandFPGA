import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
HERE = pathlib.Path(__file__).resolve().parent
ENV = ROOT / '.local/cpu-model-env-20261024'

def run(name, args):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (HERE / (name + '.command.json')).write_text(json.dumps({'argv': args, 'started_utc': started}, indent=2) + '\n', encoding='utf-8')
    with (HERE / (name + '.stdout.txt')).open('wb') as out, (HERE / (name + '.stderr.txt')).open('wb') as err:
        result = subprocess.run(args, stdout=out, stderr=err, cwd=ROOT)
    data = {'argv': args, 'started_utc': started, 'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'exit_code': result.returncode}
    for channel in ('stdout', 'stderr'):
        raw = (HERE / (name + '.' + channel + '.txt')).read_bytes()
        data[channel] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    (HERE / (name + '.result.json')).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(name, result.returncode, flush=True)
    if result.returncode:
        sys.exit(result.returncode)

assert ROOT.name == 'CarlandFPGA-node-c', ROOT
if ENV.exists():
    raise SystemExit('Refuse to overwrite an existing environment; inspect actual state first')
run('venv', [sys.executable, '-m', 'venv', str(ENV)])
run('pip-install', [str(ENV / 'Scripts/python.exe'), '-m', 'pip', 'install', '--disable-pip-version-check', '--index-url', 'https://download.pytorch.org/whl/cpu', '--report', str(HERE / 'pip-report.json'), 'torch==2.9.0'])
run('env-check', [str(ENV / 'Scripts/python.exe'), '-c', 'import torch,sys,json; print(json.dumps({"python":sys.version,"torch":torch.__version__,"cuda_available":torch.cuda.is_available(),"threads":torch.get_num_threads()}))'])

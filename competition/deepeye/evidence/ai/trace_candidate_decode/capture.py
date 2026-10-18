"""Capture raw child stdout/stderr and command/exit/hash evidence; no shell."""
import datetime
import hashlib
import json
import pathlib
import platform
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[6]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(label, arguments, cwd):
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    process = subprocess.run(arguments, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finish = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output = HERE/'captures'/label
    output.with_suffix('.stdout.txt').write_bytes(process.stdout)
    output.with_suffix('.stderr.txt').write_bytes(process.stderr)
    record = dict(label=label, args=arguments, cwd=str(cwd), started_utc=start, finished_utc=finish,
                  exit_code=process.returncode, stdout_sha256=hashlib.sha256(process.stdout).hexdigest(),
                  stderr_sha256=hashlib.sha256(process.stderr).hexdigest(),
                  sources={p.name:sha(p) for p in HERE.glob('*.py')})
    output.with_suffix('.command.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(record, sort_keys=True))
    return process.returncode


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'replay-01'
    if label.startswith('scope'):
        return run(label, [sys.executable, '-B', '-X', 'utf8', str(ROOT/'.local/deepeye-implementation-c/docs/competition/deepeye-2026/verify_immutable_scope.py'),
                           '--expected-sha', 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',
                           '--base', str(HERE/'inputs')], ROOT)
    if label.startswith('preflight'):
        return run(label, [sys.executable, '-B', '-X', 'utf8', str(ROOT/'.agents/skills/pynq-z2-single-node/scripts/preflight.py')], ROOT)
    if label.startswith('provenance'):
        return run(label, [sys.executable, '-B', '-X', 'utf8', str(HERE/'provenance.py'), '--source-root', str(ROOT)], ROOT)
    (HERE/'source_versions.json').write_text(json.dumps(dict(python=sys.version, executable=sys.executable,
          platform=platform.platform(), implementation=platform.python_implementation(),
          installed_multi_node_role=json.loads((ROOT/'.agents/skills/fpga-multi-node/skill-role.json').read_bytes()),
          installed_single_node_role=json.loads((ROOT/'.agents/skills/pynq-z2-single-node/skill-role.json').read_bytes()),
          input_head='781be78d9da77a75ea711cf690eeea6523733d3a',
          base_local_commit='cdbb6b4daef1ae1df324accd4d5086b48d005c6b',
          operation='B-DEEPEYE-TRACE-CANDIDATE-20261017-05',
          request_hash='abe52729c5bb46944ec8c55dd92481af9362b4d5a92b0bdefd13d1061038de4a'), indent=2)+'\n', encoding='utf-8', newline='\n')
    return run(label, [sys.executable, '-B', '-X', 'utf8', str(HERE/'replay.py')], ROOT)


if __name__ == '__main__':
    sys.exit(main())

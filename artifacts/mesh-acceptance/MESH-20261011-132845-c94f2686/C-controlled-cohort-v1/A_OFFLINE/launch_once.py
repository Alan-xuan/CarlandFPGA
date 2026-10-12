"""Exact one-shot Scheduler entrypoint for the C A_OFFLINE participation contract.

No original service mutation. Registration attempts are durable and not replayed.
Actual program isolation is established by its existing specific Windows Job API.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
ROUND = 'MESH-20261011-132845-c94f2686'


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--execute', action='store_true')
    parser.add_argument('--go-payload-sha256')
    args = parser.parse_args()
    review = json.loads((OUT / 'parent-review.json').read_text(encoding='utf-8'))
    assert review['status'] == 'PREPARATION_REVIEWED_NOT_ARMED'
    for filename in ('participate.py', 'launch_once.py', 'contract.json'):
        assert digest(OUT / filename) == review['hashes'][filename], 'reviewed file changed'
    mode = 'prepare' if args.prepare else 'execute'
    if args.prepare:
        assert args.go_payload_sha256 is None
    else:
        assert re.fullmatch('[0-9a-f]{64}', args.go_payload_sha256 or '')
        state = ROOT / '.local/deployment/node-c/.local/node-c/state.sqlite'
        with sqlite3.connect(state.as_uri() + '?mode=ro', uri=True) as db:
            row = db.execute('SELECT payload FROM inbound WHERE message_id=?',
                             ('C:' + ROUND + '-A-C-A_OFFLINE-participant-GO-v1',)).fetchone()
        assert row and hashlib.sha256(row[0].encode()).hexdigest() == args.go_payload_sha256
        envelope = json.loads(row[0])
        assert all(envelope.get(key) == expected for key, expected in {
            'source':'astra', 'kind':'agent_report', 'sender':'A/Astra-A',
            'recipient':'C/Astra-C', 'project_id':'fpga-main',
            'task_id':ROUND + '-controlled-cohort-C', 'task_version':1}.items())
    task = 'FPGA-Mesh-C-AOFF-' + ('Prepare' if args.prepare else 'Observe') + '-c94f2686-v1'
    command = '-X utf8 -B "' + str(OUT / 'participate.py') + '" --' + mode
    if args.execute:
        command += ' --go-payload-sha256 ' + args.go_payload_sha256
    # One timed trigger. No Start call, no recurrence, no restart, no elevation.
    script = r"""$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
$original=Get-ScheduledTask -TaskName 'FPGA-Mesh-Node-C' -TaskPath '\'
if($original.State.ToString() -ne 'Running'){throw 'Original C service not Running'}
if(Get-ScheduledTask -TaskName TASKNAME -TaskPath '\' -ErrorAction SilentlyContinue){throw 'Task already exists; inspect only'}
$principal=New-ScheduledTaskPrincipal -UserId $original.Principal.UserId -LogonType $original.Principal.LogonType -RunLevel $original.Principal.RunLevel
$action=New-ScheduledTaskAction -Execute PYTHON -Argument ARGUMENTS -WorkingDirectory ROOTDIR
$trigger=New-ScheduledTaskTrigger -Once -At ([DateTime]::Now.AddSeconds(8))
$settings=New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::FromSeconds(650)) -MultipleInstances IgnoreNew
$registered=Register-ScheduledTask -TaskName TASKNAME -TaskPath '\' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'C A_OFFLINE one-shot ordinary participant; never stop/start any service.'
$xml=Export-ScheduledTask -TaskName TASKNAME -TaskPath '\'
@{task_name=$registered.TaskName;state=$registered.State.ToString();principal=$registered.Principal.UserId;logon=$registered.Principal.LogonType.ToString();runlevel=$registered.Principal.RunLevel.ToString();trigger_count=@($registered.Triggers).Count;restart_count=$registered.Settings.RestartCount;multiple_instances=$registered.Settings.MultipleInstances.ToString();xml=$xml}|ConvertTo-Json -Depth 5 -Compress
"""
    for key, value in {'TASKNAME':task, 'PYTHON':ROOT / '.local/venv/Scripts/pythonw.exe',
                       'ARGUMENTS':command, 'ROOTDIR':ROOT}.items():
        script = script.replace(key, quote(value))
    save(mode + '-registration-attempt.json', {'at_utc':datetime.now(timezone.utc).isoformat(),
         'task_name':task, 'mode':mode, 'go_payload_sha256':args.go_payload_sha256,
         'program_sha256':digest(OUT / 'participate.py'), 'NoStop':True})
    process = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                             capture_output=True, encoding='utf-8-sig', timeout=40)
    save(mode + '-registration-result.json', {'exit_code':process.returncode,
         'stdout':process.stdout, 'stderr':process.stderr, 'unknown_on_error':process.returncode != 0})
    if process.returncode:
        raise RuntimeError('Registration refused/unknown; inspect original attempt, never rerun')
    registered = json.loads(process.stdout)
    save(mode + '-registered.json', registered)
    print(json.dumps({k:v for k,v in registered.items() if k != 'xml'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

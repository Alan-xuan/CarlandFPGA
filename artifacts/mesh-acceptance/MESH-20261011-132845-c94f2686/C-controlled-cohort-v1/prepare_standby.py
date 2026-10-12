"""One-shot, unarmed Scheduler observer. No stop/start or model capability.

Writes measured isolation, awaits the existing main terminal event, then submits
the parent's single reviewed READY through the original resident outbox.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(OUT / 'reference'))
from service_job_isolation import verify_service_job_isolation
from fpga_mesh.child_control import LocalControlFileClient
from fpga_mesh.project_cli import discovery

TASK_ID = 'MESH-20261011-132845-c94f2686-controlled-cohort-C'
MESSAGE = 'C:MESH-20261011-132845-c94f2686-A-C-controlled-cohort-prepare-v1'
OP = 'MESH-20261011-132845-c94f2686-C-controlled-cohort-ready-v1'
TASK = 'FPGA-Mesh-Node-C'

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save_once(name, value):
    with (OUT / name).open('xb') as f:
        f.write((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode())
        f.flush()
        os.fsync(f.fileno())

def ps(script):
    p = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
                        "$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"+script],
                       capture_output=True, encoding='utf-8-sig', timeout=30)
    if p.returncode:
        raise RuntimeError('Read-only PowerShell probe failed: '+str(p.returncode))
    return json.loads(p.stdout)

def capture():
    sup = json.loads((ROOT/'.local/deployment/node-c/supervisor.json').read_text())
    supervisor, worker = sup['supervisor_pid'], sup['worker_pid']
    raw = ps("$t=Get-ScheduledTask -TaskName 'FPGA-Mesh-Node-C' -TaskPath '\\';"
             "$p=@(Get-CimInstance Win32_Process | Where-Object {$_.ProcessId -gt 0 -and $_.CreationDate} | ForEach-Object {"
             "@{pid=[int]$_.ProcessId;parent_pid=[int]$_.ParentProcessId;"
             "created_at_utc=$_.CreationDate.ToUniversalTime().ToString('o');command=$_.CommandLine}});"
             "@{task_name=$t.TaskName;task_path=$t.TaskPath;state=$t.State.ToString();"
             "xml=(Export-ScheduledTask -TaskName 'FPGA-Mesh-Node-C' -TaskPath '\\');"
             "principal=@{user=$t.Principal.UserId;logon=$t.Principal.LogonType.ToString();"
             "runlevel=$t.Principal.RunLevel.ToString()};processes=$p}|ConvertTo-Json -Depth 5 -Compress")
    assert raw['task_name'] == TASK and raw['task_path'] == '\\' and raw['state'] == 'Running'
    procs = {p['pid']: p for p in raw.pop('processes')}
    launcher = procs[supervisor]['parent_pid']
    expected = str(ROOT / '.local/deployment/node-c/runtime_bootstrap.py')
    assert expected.lower() in (procs[launcher]['command'] or '').lower()
    ids = {launcher}
    while True:
        more = {p['pid'] for p in procs.values() if p['parent_pid'] in ids}
        if more <= ids: break
        ids |= more
    assert {supervisor, worker} <= ids
    original = [{k:v for k,v in procs[pid].items() if k != 'command'} for pid in sorted(ids)]
    isolation = verify_service_job_isolation(supervisor, worker)
    assert isolation['pid'] == os.getpid() and isolation['isolation_verified'] is True
    assert all(set(j['job_member_pids']) <= ids for j in isolation['jobs'])
    xml = raw.pop('xml')
    raw['xml_sha256'] = sha(xml.encode())
    # XML remains local; no credentials or scheduler definition is transmitted.
    if not (OUT/'original-task.xml').exists():
        with (OUT/'original-task.xml').open('xb') as f: f.write(xml.encode())
    assert sha((OUT/'original-task.xml').read_bytes()) == raw['xml_sha256']
    return dict(at_utc=now(), pid=os.getpid(), helper_process=procs[os.getpid()] | {'command':None},
                task=raw, task_root_pid=launcher, supervisor_pid=supervisor, worker_pid=worker,
                original_processes=original, job_isolation=isolation, armed=False,
                preparation_only=True, model_calls=0, service_mutations=0)

async def main():
    assert OUT.name == 'C-controlled-cohort-v1' and ROOT.name == 'CarlandFPGA-node-c'
    save_once('standby-admission.json', dict(pid=os.getpid(), at_utc=now(), armed=False))
    evidence = capture()
    save_once('standby-isolation.json', evidence)
    control = LocalControlFileClient(discovery(ROOT))
    result = await asyncio.wait_for(control.call('main_wait', {
        'message_id':MESSAGE, 'timeout_seconds':1800}), timeout=1810)
    save_once('preparation-controller-terminal.json', result)
    if result.get('status') != 'completed':
        raise RuntimeError('Preparation main not successfully terminal')
    approval = json.loads((OUT/'parent-review.json').read_text())
    assert approval['status'] == 'PREPARATION_REVIEWED_UNARMED' and approval['armed'] is False
    for rel,digest in approval['program_sha256'].items():
        assert sha((OUT/rel).read_bytes()) == digest, 'Reviewed program changed'
    current = capture()
    assert current['supervisor_pid'] == evidence['supervisor_pid']
    assert current['worker_pid'] == evidence['worker_pid']
    health = await asyncio.wait_for(control.call('health',{}), timeout=20)
    selected = {k:health.get(k) for k in ('node_id','project_id','pid','started','feishu_connected',
                                         'network_enabled','peer_error','peer_presence','pending_inbound')}
    assert selected['started'] is True and selected['feishu_connected'] is True
    assert selected['network_enabled'] is True and selected['peer_error'] is None
    old = json.loads((OUT/'reused-obligations.json').read_text())
    report = dict(operation_id=OP, task_id=TASK_ID, task_version=1,
                  work_id='C-controlled-cohort-preparation-v1', status='READY_UNARMED', armed=False,
                  quality_model=approval['quality_model'], quality_effort=approval['quality_effort'],
                  program_sha256=approval['program_sha256'], pid=os.getpid(),
                  job_isolation=current['job_isolation'], original_service={k:current[k] for k in
                    ('task_root_pid','supervisor_pid','worker_pid','task')}, health=selected,
                  preparation_terminal_status=result['status'],
                  pr=dict(review_id=old['pr']['review_id'],state=old['pr']['review_state'],
                          head=old['pr']['pr_head'],original_readback_reused=True),
                  exact_old_receipts=old['receipts'],
                  limits='No ARM/nonce, no service stop/start, no final scenario executed. Future ARM requires fresh immutable bounded plan and dedicated guard readiness. No ACK requested.')
    # Unique durable claim: unknown send outcome is never replayed by this helper.
    save_once('ready-send-claim.json', report)
    delivery = await asyncio.wait_for(control.call('fpga_peer_send', {
        'peer_id':'A','task_id':TASK_ID,'task_version':1,'operation_id':OP,
        'text':json.dumps(report,ensure_ascii=False,sort_keys=True)}),timeout=30)
    save_once('ready-delivery.json',delivery)
    save_once('READY.json',report)
    # Bounded unarmed standby. No ARM reader and no stop/start calls exist here.
    await asyncio.sleep(1800)
    save_once('standby-ended.json',dict(at_utc=now(),pid=os.getpid(),armed=False,service_mutations=0))

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as exc:
        try: save_once('standby-failure.json',dict(at_utc=now(),pid=os.getpid(),error_type=type(exc).__name__,detail=str(exc)[:300],armed=False))
        except Exception: pass
        raise

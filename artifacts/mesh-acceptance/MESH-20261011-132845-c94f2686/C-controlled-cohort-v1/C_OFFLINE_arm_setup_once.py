"""Exact C_OFFLINE ARM setup authorization; never invokes the Stop driver.

One ordinary external Scheduler lifetime owns the reviewed recovery watcher.
Await the exact parent terminal event, snapshot actual idle, create one immutable
plan, launch the existing guard once, and send the sole ARMED_COFF status once.
"""
import asyncio
from contextlib import ExitStack, closing
from datetime import timedelta
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(OUT / 'derived'))
import c_outage_guard_v1 as guard
import prepare_standby as prep
from fpga_mesh.child_control import LocalControlFileClient
from fpga_mesh.project_cli import discovery
from fpga_mesh.update import _IDLE_CHECKS, _has_pending_work

ROUND = 'MESH-20261011-132845-c94f2686'
MESSAGE = 'C:' + ROUND + '-A-C-C_OFFLINE-arm-setup-v1'
NONCE = 'CF_c94f2686_e184b176'
PLAN_OP = ROUND + '-C_OFFLINE-armed-plan-v1'
REPORT_OP = ROUND + '-C-C_OFFLINE-armed-ready-v1'
CONFIG = ROOT / '.local/deployment/node-c/node-c.toml'
STATE = ROOT / '.local/deployment/node-c/.local/node-c'
PINNED = {
    'derived/c_outage_guard_v1.py':'f734770d257aa2fd85c6ddd189a949214e2706685a69c3f4c1fc796c59c7a7c4',
    'derived/service_job_isolation.py':'dfd68ca927161727d105454517a63e8e3aac97d51a78570f5e903d29ca378f75',
    'prepare_standby.py':'6f58011dd72482ea42f9f9e8881aa304d19deb658c4f171c2b3123bc4beafa8f',
    'reference/service_job_isolation.py':'57a2a1ff9cf808954bee83ce20d1cd5db12732110d2eaaf5004bfd5b5c1c4ade',
    'stop_prepared_c.py':'9baa77d413218891a936d376a7ed13169df19e8a2f8b851ac9af2dbee9aa12a4',
}


def save(name, value):
    guard.exclusive(OUT / name, value)


def idle_snapshot(action=None):
    # Same three writer admissions and actual idle conditions as original fence;
    # this setup never supplies a Stop callback or alters source ledgers.
    with ExitStack() as stack:
        records = []
        for filename, table, condition in _IDLE_CHECKS:
            path = STATE / filename
            if not path.is_file():
                raise ValueError('missing original ledger')
            db = stack.enter_context(closing(sqlite3.connect(path.as_uri()+'?mode=rw', uri=True, timeout=0)))
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table',table)).fetchone():
                raise ValueError('missing original ledger table')
            records.append((db,filename,table,condition))
        if any(_has_pending_work(db,table,condition) for db,_,table,condition in records):
            raise ValueError('original ledgers are not all idle')
        result = dict(allledgerIdle=True,at_utc=guard.utc_now().isoformat(),
                      three_writer_locks=True,ledgers=[r[1] for r in records])
        if action is not None:
            action(result)
        return result


async def main():
    guard.verify_fixed_layout()
    assert OUT == guard.OUT
    for rel,digest in PINNED.items():
        if guard.sha((OUT/rel).read_bytes()) != digest:
            raise ValueError('reviewed source changed: '+rel)
    save('C_OFFLINE-arm-admission-v1.json',dict(pid=os.getpid(),at_utc=guard.utc_now().isoformat(),NoStop=True))
    # Prove the actual Scheduler process is outside the original service Job.
    first = prep.capture()
    save('C_OFFLINE-arm-helper-isolation-v1.json',first)
    client = LocalControlFileClient(discovery(ROOT))
    terminal = await asyncio.wait_for(client.call('main_wait',dict(message_id=MESSAGE,timeout_seconds=1200)),timeout=1210)
    save('C_OFFLINE-arm-parent-terminal-v1.json',terminal)
    if terminal.get('status') != 'completed':
        raise ValueError('ARM setup parent not completed')
    # main_wait observes main completion just before inbound processed_at is set.
    await asyncio.sleep(0.5)
    forbidden = [guard.FILES[k] for k in ('plan','phase','attempt','ready')]
    forbidden += ['c-stop-claim-v1.json','C_OFFLINE-guard-launch-claim-v1.json','C_OFFLINE-armed-send-claim-v1.json']
    if any((OUT/n).exists() for n in forbidden):
        raise ValueError('existing immutable plan/claim/READY: inspect only, no replay')
    prepared = {}
    def create_plan(idle):
        fresh = prep.capture()
        now = guard.utc_now()
        mono = time.monotonic()
        identity = dict(round_id=ROUND,node_id='C',task_id=guard.TASK_ID,task_version=1,
                        work_id=guard.WORK_ID,operation_id=PLAN_OP,nonce=NONCE)
        plan = dict(identity,schema=guard.PLAN_SCHEMA,phase='C_OFFLINE',armed=True,
                    out_dir=str(OUT),task_name=guard.TASK_NAME,
                    prepared_at_utc=now.isoformat(),restore_at_utc=(now+timedelta(seconds=600)).isoformat(),
                    expires_at_utc=(now+timedelta(seconds=690)).isoformat(),
                    task_xml_sha256=fresh['task']['xml_sha256'],task_root_pid=fresh['task_root_pid'],
                    supervisor_pid=fresh['supervisor_pid'],worker_pid=fresh['worker_pid'],
                    original_processes=fresh['original_processes'],service_config=str(CONFIG),state_dir=str(STATE),
                    wait_stopped_timeout_seconds=20,health_timeout_seconds=60)
        phase = dict(identity,schema=guard.PHASE_SCHEMA,phase='C_OFFLINE',armed=True,state='PREPARED')
        guard.validate(plan,phase)
        save('C_OFFLINE-fresh-original-evidence-v1.json',fresh)
        save('C_OFFLINE-plan-idle-snapshot-v1.json',idle)
        save(guard.FILES['plan'],plan)
        save(guard.FILES['phase'],phase)
        prepared.update(plan=plan,phase=phase,monotonic_restore=mono+600,monotonic_expiry=mono+690)
    idle_snapshot(create_plan)
    plan = prepared['plan']
    raw_hash = guard.sha((OUT/guard.FILES['plan']).read_bytes())
    save('C_OFFLINE-plan-binding-v1.json',dict(plan_sha256=raw_hash,nonce=NONCE,operation_id=PLAN_OP,
        phase='C_OFFLINE',monotonic_restore=prepared['monotonic_restore'],monotonic_expiry=prepared['monotonic_expiry']))
    save('C_OFFLINE-guard-launch-claim-v1.json',dict(plan_sha256=raw_hash,at_utc=guard.utc_now().isoformat(),NoStop=True))
    command = [str(ROOT/'.local/venv/Scripts/python.exe'),'-B',str(OUT/'derived/c_outage_guard_v1.py'),
               '--execute-watch','--plan-sha256',raw_hash]
    with (OUT/'C_OFFLINE-guard-stdout-v1.txt').open('xb') as stdout, (OUT/'C_OFFLINE-guard-stderr-v1.txt').open('xb') as stderr:
        process = subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                                   creationflags=0x08000000)
        save('C_OFFLINE-guard-launched-v1.json',dict(launcher_pid=process.pid,plan_sha256=raw_hash))
        # Keep this external Scheduler lifetime alive through watcher completion.
        # A failure after launch leaves the watcher running to its bounded expiry.
        try:
            ready_path = OUT/guard.FILES['ready']
            while not ready_path.exists():
                if process.poll() is not None:
                    raise RuntimeError('reviewed guard exited before READY; no replay')
                if time.monotonic() >= prepared['monotonic_restore']-30:
                    raise TimeoutError('guard READY not reached with >=30 seconds remaining')
                await asyncio.sleep(0.2)
            ready = json.loads(ready_path.read_bytes())
            if ready.get('plan_sha256') != raw_hash or ready.get('schema') != guard.READY_SCHEMA:
                raise ValueError('guard READY binding mismatch')
            live = guard.read_process_identity_probe(ready['pid'])
            if any(live[k] != ready['helper_process'][k] for k in ('pid','parent_pid','created_at_utc')):
                raise ValueError('guard PID creation/parent changed')
            proof = ready['job_isolation']
            if proof.get('pid') != ready['pid'] or not proof.get('isolation_verified') or not proof.get('jobs'):
                raise ValueError('guard specific Job proof absent')
            if proof['supervisor_pid'] != plan['supervisor_pid'] or proof['worker_pid'] != plan['worker_pid']:
                raise ValueError('guard Job bound to different service')
            if any(j.get('current_process_in_service_job') is not False for j in proof['jobs']):
                raise ValueError('guard is not isolated')
            if guard.sha((OUT/guard.FILES['plan']).read_bytes()) != raw_hash:
                raise ValueError('immutable plan changed')
            current_phase=json.loads((OUT/guard.FILES['phase']).read_bytes())
            if current_phase != prepared['phase']:
                raise ValueError('PREPARED phase changed without GO')
            idle = idle_snapshot()
            remaining = min(prepared['monotonic_restore']-time.monotonic(),
                            (guard.timestamp(plan['restore_at_utc'])-guard.utc_now()).total_seconds())
            if remaining < 30 or process.poll() is not None:
                raise ValueError('guard no longer live/fresh')
            next_route = json.loads((OUT/'C_OFFLINE-selected-next-route-v1.json').read_text())
            report = dict(phase='C_OFFLINE',nonce=NONCE,operation_id=PLAN_OP,plan_sha256=raw_hash,
                guard_pid=ready['pid'],creation=live['created_at_utc'],parent=live['parent_pid'],jobproof=proof,
                restoreUTC=plan['restore_at_utc'],expireUTC=plan['expires_at_utc'],remainingMonotonic=remaining,
                GOauthority=dict(sender='A/Astra-A',source='astra',kind='agent_report',task_id=guard.TASK_ID,
                    task_version=1,message_id='C:'+ROUND+'-A-C-C_OFFLINE-GO-v1',
                    operation_id=ROUND+'-A-C-C_OFFLINE-GO-v1',nonce=NONCE,plan_sha256=raw_hash,
                    rule='Exact GO only; original reviewed stop driver once, outside original Job, after GO parent terminal and original three-writer idle fence'),
                selectednextRoute=next_route,currentmainTerminal='completed',allledgerIdle=idle,NoStop=True)
            report['originalTaskXML/PIDs']=dict(xml_sha256=plan['task_xml_sha256'],task_root_pid=plan['task_root_pid'],
                supervisor_pid=plan['supervisor_pid'],worker_pid=plan['worker_pid'],processes=plan['original_processes'])
            save('C_OFFLINE-armed-ready-v1.json',report)
            save('C_OFFLINE-armed-send-claim-v1.json',dict(operation_id=REPORT_OP,plan_sha256=raw_hash,at_utc=guard.utc_now().isoformat()))
            result=await asyncio.wait_for(client.call('fpga_peer_send',dict(peer_id='A',task_id=guard.TASK_ID,
                task_version=1,operation_id=REPORT_OP,text='ARMED_COFF '+json.dumps(report,separators=(',',':')))),timeout=30)
            save('C_OFFLINE-armed-delivery-v1.json',result)
        finally:
            code = await asyncio.to_thread(process.wait)
            save('C_OFFLINE-guard-exit-v1.json',dict(exit_code=code,at_utc=guard.utc_now().isoformat(),plan_sha256=raw_hash))


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as exc:
        try: save('C_OFFLINE-arm-refused-or-unknown-v1.json',dict(error_type=type(exc).__name__,
            detail=str(exc)[:300],at_utc=guard.utc_now().isoformat(),NoStop=True))
        except FileExistsError: pass
        raise

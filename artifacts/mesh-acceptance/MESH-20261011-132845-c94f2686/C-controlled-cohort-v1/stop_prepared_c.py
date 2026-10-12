"""Future-ARM-only C stop driver; never used during preparation.

Must itself run outside the original service Job. The sole Stop command is
inside original stop_idle_node's three writer locks, held until leases/PIDs
are absent. Unknown outcomes are durably latched and never retried.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(OUT / 'derived'))
import c_outage_guard_v1 as guard
from service_job_isolation import verify_service_job_isolation
from fpga_mesh.update import stop_idle_node


def stop_once(expected_sha):
    raw = (OUT / guard.FILES['plan']).read_bytes()
    if not expected_sha or guard.sha(raw) != expected_sha:
        raise ValueError('original immutable armed plan required')
    plan = json.loads(raw)
    phase = json.loads((OUT / guard.FILES['phase']).read_bytes())
    _, restore_at, expires, config, state, _, _ = guard.validate(plan, phase)
    if phase['state'] != 'PREPARED':
        raise ValueError('phase not PREPARED; no replay')
    if not all((state / f).is_file() for f in ('state.sqlite','main_sessions.sqlite','child_jobs.sqlite')):
        raise ValueError('all three existing ledgers required')
    ready = json.loads((OUT / guard.FILES['ready']).read_bytes())
    if ready.get('plan_sha256') != expected_sha or ready.get('schema') != guard.READY_SCHEMA:
        raise ValueError('matching armed guard READY required')
    current = guard.read_process_identity_probe(ready['pid'])
    if any(current[k] != ready['helper_process'][k] for k in ('pid','parent_pid','created_at_utc')):
        raise ValueError('armed recovery guard process changed')
    isolation = verify_service_job_isolation(plan['supervisor_pid'], plan['worker_pid'])
    if not isolation['isolation_verified'] or isolation['pid'] != os.getpid():
        raise ValueError('stop driver not isolated from original Job')
    bound = {p['pid'] for p in plan['original_processes']}
    if any(not set(j['job_member_pids']) <= bound for j in isolation['jobs']):
        raise ValueError('new original service Job members not bound by plan')
    remaining = (restore_at - guard.utc_now()).total_seconds()
    if not 30 <= remaining <= 600:
        raise ValueError('insufficient fixed stop/recovery window')
    mono_end = time.monotonic() + remaining

    def fenced_stop():
        if guard.sha((OUT / guard.FILES['plan']).read_bytes()) != expected_sha:
            raise ValueError('plan changed before Stop')
        if time.monotonic() >= mono_end - 20 or guard.utc_now() >= restore_at:
            raise ValueError('Stop window exhausted')
        task = guard.read_task_probe()
        if task['state'] != 'Running' or task['xml_sha256'] != plan['task_xml_sha256']:
            raise ValueError('original Task changed')
        for p in plan['original_processes']:
            live = guard.read_process_identity_probe(p['pid'])
            if any(live[k] != p[k] for k in ('pid','parent_pid','created_at_utc')):
                raise ValueError('original service process changed')
        if time.monotonic() >= mono_end - 20 or guard.utc_now() >= restore_at:
            raise ValueError('Stop probes consumed window')
        guard.exclusive(OUT / 'c-stop-claim-v1.json', dict(
            plan_sha256=expected_sha, at_utc=guard.utc_now().isoformat(), pid=os.getpid(),
            status='STOP_ATTEMPT_CLAIMED', three_writer_locks_held=True))
        phase.update(state='STOP_ATTEMPTED',stop_attempted_at_utc=guard.utc_now().isoformat())
        temp = OUT / 'c-stop-phase-v1.tmp'
        guard.exclusive(temp, phase)
        os.replace(temp, OUT / guard.FILES['phase'])
        p = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
            "$ErrorActionPreference='Stop';Stop-ScheduledTask -TaskName 'FPGA-Mesh-Node-C' -TaskPath '\\'"],
            capture_output=True,timeout=15)
        if p.returncode:
            raise RuntimeError('Stop outcome unknown; no retry')
        guard.wait_stopped_via_service(config,20)
        if any(guard.read_process_probe(p['pid']) for p in plan['original_processes']):
            raise RuntimeError('old service PIDs still present; no success claim')
        guard.exclusive(OUT / 'c-stop-confirmed-v1.json',dict(
            plan_sha256=expected_sha,at_utc=guard.utc_now().isoformat(),
            leases_released=True,all_bound_old_pids_absent=True,three_writer_locks_held=True))

    # The original implementation acquires BEGIN IMMEDIATE on ALL three ledgers
    # and verifies every main/child/inbound idle condition before this callback.
    stop_idle_node(config,node='C',stop=fenced_stop)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--armed-plan-sha256',required=True)
    args = parser.parse_args()
    try:
        stop_once(args.armed_plan_sha256)
    except Exception as exc:
        try: guard.exclusive(OUT/'c-stop-refused-or-unknown-v1.json',dict(
            error_type=type(exc).__name__,detail=str(exc)[:300],at_utc=guard.utc_now().isoformat()))
        except FileExistsError: pass
        raise

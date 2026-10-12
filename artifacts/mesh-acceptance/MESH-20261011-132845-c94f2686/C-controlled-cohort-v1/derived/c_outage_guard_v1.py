"""C fixed-node outage restoration guard v1 (derived from A reference v2).

Bounded watch-and-restore only: refuses unless the round plan/phase name this
exact C cohort, both carry armed=true, the identity matches the fixed C
task/work identity, and the immutable plan bytes are unchanged. No stop
capability: this guard never stops, ends, disables or reconfigures the Task,
the service or any process. It only (a) runs read-only probes, (b) waits for
the service to be stopped via the repo service helper, (c) writes the single
durable exclusive start claim, (d) issues exactly one Start-ScheduledTask for
the fixed C Task, and (e) health-checks the running service. Unknown start and
unknown health outcomes are recorded and never replayed.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.dont_write_bytecode = True

ROUND = 'MESH-20261011-132845-c94f2686'
NODE_ID = 'C'
TASK_NAME = 'FPGA-Mesh-Node-C'
TASK_ID = ROUND + '-controlled-cohort-C'
WORK_ID = 'C-controlled-cohort-preparation-v1'
TASK_VERSION = 1

PLAN_SCHEMA = 'mesh-c-outage-plan/v1'
PHASE_SCHEMA = 'mesh-c-outage-phase/v1'
ATTEMPT_SCHEMA = 'mesh-c-outage-restore/v1'
READY_SCHEMA = 'mesh-c-watch-ready/v1'

HERE = Path(__file__).resolve().parent
COHORT = HERE.parent
ROUND_DIR = COHORT.parent
ACCEPTANCE_DIR = ROUND_DIR.parent
ARTIFACTS_DIR = ACCEPTANCE_DIR.parent
NODE_ROOT = ARTIFACTS_DIR.parent
OUT = COHORT
COHORT_DIRNAME = 'C-controlled-cohort-v1'

FILES = {'plan': 'c-outage-plan-v1.json', 'phase': 'c-outage-phase-v1.json',
         'attempt': 'c-outage-restore-attempt-v1.json', 'ready': 'c-outage-watch-ready-v1.json',
         'log': 'c-outage-watch-v1.jsonl'}
IDENTITY = ('round_id', 'node_id', 'task_id', 'task_version', 'work_id', 'operation_id', 'nonce')

PROBE_TIMEOUT_SECONDS = 15
WAIT_STOPPED_TIMEOUT_DEFAULT = 20.0
WAIT_STOPPED_TIMEOUT_MAX = 300.0
HEALTH_TIMEOUT_DEFAULT = 60.0
HEALTH_TIMEOUT_MAX = 600.0


def fixed_layout_problem():
    expected = ((HERE, 'derived'), (COHORT, COHORT_DIRNAME), (ROUND_DIR, ROUND),
                (ACCEPTANCE_DIR, 'mesh-acceptance'), (ARTIFACTS_DIR, 'artifacts'),
                (NODE_ROOT, 'CarlandFPGA-node-c'))
    for path, name in expected:
        if path.name != name:
            return 'fixed C cohort layout violated at: ' + str(path)
    return None


def verify_fixed_layout():
    problem = fixed_layout_problem()
    if problem:
        raise RuntimeError(problem)


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed.astimezone(timezone.utc)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def exclusive(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def append_record(path, value):
    with path.open('ab') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def log(value, out_dir=OUT):
    with (Path(out_dir) / FILES['log']).open('ab') as stream:
        stream.write(canonical(dict(at_utc=utc_now().isoformat(), **value)) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def inside(root, path):
    return path == root or root in path.parents


def bounded(fn, *args):
    try:
        return True, fn(*args)
    except Exception as exc:  # noqa: BLE001 - every probe failure is an unknown
        return False, {'error_type': type(exc).__name__, 'detail': str(exc)[:300]}


def bounded_seconds(plan, key, default, maximum):
    value = plan.get(key, default)
    if type(value) not in (int, float) or isinstance(value, bool) or not 0 < value <= maximum:
        raise ValueError('invalid bounded timeout: ' + key)
    return float(value)

def validate(plan, phase, out_dir=OUT, node_root=NODE_ROOT):
    root = Path(out_dir).resolve(strict=True)
    node = Path(node_root).resolve(strict=True)
    if root.name != COHORT_DIRNAME:
        raise ValueError('wrong fixed C cohort output directory')
    if plan.get('schema') != PLAN_SCHEMA or phase.get('schema') != PHASE_SCHEMA:
        raise ValueError('schema mismatch')
    if not Path(plan.get('out_dir', '')).is_absolute() or Path(plan['out_dir']).resolve(strict=True) != root:
        raise ValueError('foreign out_dir')
    for name in FILES.values():
        if (root / name).resolve().parent != root:
            raise ValueError('reparse path outside round')
    for key in IDENTITY:
        if not plan.get(key) or phase.get(key) != plan[key]:
            raise ValueError('identity missing or mismatch: ' + key)
    if plan['round_id'] != ROUND or plan['node_id'] != NODE_ID:
        raise ValueError('wrong fixed round/node identity')
    if type(plan['task_version']) is not int or plan['task_version'] != TASK_VERSION:
        raise ValueError('wrong fixed task version identity')
    if plan.get('task_name') != TASK_NAME or plan.get('task_id') != TASK_ID or plan.get('work_id') != WORK_ID:
        raise ValueError('wrong fixed C task/work identity')
    if plan.get('armed') is not True or phase.get('armed') is not True:
        raise ValueError('plan/phase not armed: explicit armed=true required')
    nonce = plan.get('nonce')
    if not isinstance(nonce, str) or len(nonce.strip()) < 8 or phase.get('nonce') != nonce:
        raise ValueError('arm nonce missing or too short')
    expected = plan.get('task_xml_sha256', '')
    if len(expected) != 64 or any(x not in '0123456789abcdef' for x in expected):
        raise ValueError('full original Task fingerprint required')
    processes = plan.get('original_processes')
    if not isinstance(processes, list) or not processes:
        raise ValueError('original process proof required')
    ids = []
    for process in processes:
        pid = process.get('pid')
        if type(pid) is not int or pid <= 0 or not process.get('created_at_utc'):
            raise ValueError('invalid original process identity')
        timestamp(process['created_at_utc'])
        ids.append(pid)
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate original PID')
    supervisor = plan.get('supervisor_pid')
    worker = plan.get('worker_pid')
    if type(supervisor) is not int or type(worker) is not int or supervisor == worker or supervisor not in ids or worker not in ids:
        raise ValueError('original supervisor/worker must be bound to process identities')
    by_pid = {p['pid']: p for p in processes}
    task_root = plan.get('task_root_pid')
    if type(task_root) is not int or task_root not in by_pid:
        raise ValueError('original Task launcher PID required')
    for process in processes:
        parent = process.get('parent_pid')
        if type(parent) is not int or parent <= 0:
            raise ValueError('original parent identity missing')
        cursor, visited = process['pid'], set()
        while cursor != task_root:
            if cursor in visited or cursor not in by_pid:
                raise ValueError('original process chain incomplete or cyclic')
            visited.add(cursor)
            cursor = by_pid[cursor].get('parent_pid')
    if by_pid[task_root]['parent_pid'] in by_pid:
        raise ValueError('original Task root parent is inside its own tree')
    prepared = timestamp(plan['prepared_at_utc'])
    deadline = timestamp(plan['restore_at_utc'])
    expires = timestamp(plan['expires_at_utc'])
    if not prepared < deadline <= prepared + timedelta(minutes=10) or not deadline < expires <= deadline + timedelta(minutes=2):
        raise ValueError('unbounded timer')
    if phase.get('state') == 'STOP_ATTEMPTED':
        stopped = timestamp(phase['stop_attempted_at_utc'])
        if not prepared <= stopped < deadline:
            raise ValueError('stop outside planned window')
    elif phase.get('state') != 'PREPARED':
        raise ValueError('unknown phase')
    config = plan.get('service_config')
    state = plan.get('state_dir')
    for label, value in (('service_config', config), ('state_dir', state)):
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError('absolute ' + label + ' required')
    config_path = Path(config).resolve(strict=True)
    state_path = Path(state).resolve(strict=True)
    if not config_path.is_file():
        raise ValueError('service_config is not a file')
    if not state_path.is_dir():
        raise ValueError('state_dir is not a directory')
    expected_config = node / '.local/deployment/node-c/node-c.toml'
    expected_state = node / '.local/deployment/node-c/.local/node-c'
    if config_path != expected_config or state_path != expected_state:
        raise ValueError('service path is not the original fixed C path')
    wait_timeout = bounded_seconds(plan, 'wait_stopped_timeout_seconds', WAIT_STOPPED_TIMEOUT_DEFAULT, WAIT_STOPPED_TIMEOUT_MAX)
    health_timeout = bounded_seconds(plan, 'health_timeout_seconds', HEALTH_TIMEOUT_DEFAULT, HEALTH_TIMEOUT_MAX)
    return root, deadline, expires, config_path, state_path, wait_timeout, health_timeout


def powershell(script):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, encoding='utf-8-sig', timeout=PROBE_TIMEOUT_SECONDS)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError('readonly powershell probe failed')
    return json.loads(result.stdout)


def read_task_probe():
    value = powershell("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
                       "$t=Get-ScheduledTask -TaskPath '\\' -TaskName '" + TASK_NAME + "'; "
                       "$x=Export-ScheduledTask -TaskPath '\\' -TaskName '" + TASK_NAME + "'; "
                       "@{task_name=$t.TaskName;task_path=$t.TaskPath;state=$t.State.ToString();xml=$x} | ConvertTo-Json -Compress")
    if not isinstance(value, dict) or not isinstance(value.get('xml'), str) or not value['xml'].strip():
        raise ValueError('empty full Task probe')
    value['xml_sha256'] = sha(value.pop('xml').encode('utf-8'))
    return value


def read_process_probe(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError('invalid PID')
    value = powershell("$ErrorActionPreference='Stop'; $p=@(Get-CimInstance Win32_Process -Filter 'ProcessId = " + str(pid) +
                       "' -ErrorAction Stop); @{pid=" + str(pid) +
                       ";alive=($p.Count -ne 0);probe_ok=$true} | ConvertTo-Json -Compress")
    if not isinstance(value, dict) or value.get('pid') != pid or value.get('probe_ok') is not True or type(value.get('alive')) is not bool:
        raise ValueError('process probe unknown')
    return value['alive']


def read_process_identity_probe(pid):
    value = powershell("$ErrorActionPreference='Stop'; $p=@(Get-CimInstance Win32_Process -Filter 'ProcessId = " + str(pid) +
                       "' -ErrorAction Stop); if($p.Count -ne 1){throw 'Original process not uniquely present'}; "
                       "@{pid=[int]$p[0].ProcessId;parent_pid=[int]$p[0].ParentProcessId;created_at_utc=$p[0].CreationDate.ToUniversalTime().ToString('o');probe_ok=$true} | ConvertTo-Json -Compress")
    if not isinstance(value, dict) or value.get('probe_ok') is not True or value.get('pid') != pid:
        raise ValueError('original process identity query unknown')
    return value


def start_scheduled_task():
    # Only this fixed original C Task is allowed; no registration/configuration API.
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                             "$ErrorActionPreference='Stop'; Start-ScheduledTask -TaskPath '\\' -TaskName '" + TASK_NAME + "'"],
                            capture_output=True, timeout=PROBE_TIMEOUT_SECONDS)
    return result.returncode


def repo_python(node_root):
    python = Path(node_root) / '.local' / 'venv' / 'Scripts' / 'python.exe'
    if not python.is_file():
        raise FileNotFoundError('fixed repo venv python missing: ' + str(python))
    return python


def wait_stopped_via_service(config, timeout, node_root=NODE_ROOT):
    """Read-only wait for supervisor/resident leases to be released. Never stops anything."""
    python = repo_python(node_root)
    command = [str(python), '-m', 'fpga_mesh.service', '--wait-stopped', '--config', str(config),
               '--timeout', str(round(float(timeout), 3))]
    try:
        result = subprocess.run(command, cwd=str(node_root), capture_output=True,
                                encoding='utf-8', errors='replace', timeout=float(timeout) + 5.0)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError('wait-stopped exceeded its bounded timeout') from exc
    if result.returncode != 0:
        raise RuntimeError('wait-stopped did not confirm the service is stopped')


def health_via_project_cli(state_dir, node_root=NODE_ROOT):
    """Real local health action of the running resident service (no external send)."""
    python = repo_python(node_root)
    control = Path(state_dir) / 'main-control.json'
    if not control.is_file():
        raise FileNotFoundError('service control file not present yet: ' + str(control))
    command = [str(python), '-m', 'fpga_mesh.project_cli', 'health', '--control-file', str(control)]
    result = subprocess.run(command, cwd=str(node_root), capture_output=True,
                            encoding='utf-8', errors='replace', timeout=PROBE_TIMEOUT_SECONDS)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError('local health action failed')
    lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    value = json.loads(lines[-1])
    if not isinstance(value, dict):
        raise ValueError('local health action returned no object')
    return value

def await_health(plan, *, health_probe, task_probe, process_probe, now_fn, monotonic_fn,
                 sleep_fn, until_utc, until_mono):
    original_pids = {p['pid'] for p in plan['original_processes']}
    answered = False
    last_answer = None
    while now_fn() < until_utc and monotonic_fn() < until_mono:
        ok, value = bounded(health_probe, str(plan['state_dir']))
        if ok and isinstance(value, dict):
            pid = value.get('pid')
            checks = {
                'node_project': value.get('node_id') == 'C' and value.get('project_id') == 'fpga-main',
                'pid_changed': type(pid) is int and pid > 0 and pid not in original_pids,
                'started': value.get('started') is True,
                'feishu_connected': value.get('feishu_connected') is True,
                'network_enabled': value.get('network_enabled') is True,
                'transport': (type(value.get('peer_listen_port')) is int and value['peer_listen_port'] > 0
                              and value.get('peer_error') is None and value.get('feishu_error') is None),
            }
            answered = True
            if all(checks.values()):
                ok_pid, alive = bounded(process_probe, pid)
                checks['resident_process_alive'] = bool(ok_pid and alive is True)
                ok_task, task = bounded(task_probe)
                checks['task_running_same_xml'] = bool(
                    ok_task and isinstance(task, dict) and task.get('task_name') == TASK_NAME
                    and task.get('task_path') == '\\' and task.get('state') == 'Running'
                    and task.get('xml_sha256') == plan['task_xml_sha256'])
                if all(checks.values()) and now_fn() < until_utc and monotonic_fn() < until_mono:
                    return {'status': 'START_HEALTH_VERIFIED', 'start_attempted': True,
                            'health_verified': True, 'resident_pid': pid, 'checks': checks}
            last_answer = {key: bool(item) for key, item in checks.items()}
        sleep_fn(1.0)
    if answered:
        return {'status': 'START_STARTED_UNHEALTHY', 'start_attempted': True,
                'health_verified': False, 'checks': last_answer}
    return {'status': 'START_HEALTH_UNKNOWN', 'start_attempted': True, 'health_verified': None}


def restore_once(plan, phase, *, out_dir=OUT, node_root=NODE_ROOT,
                 now_fn=None, monotonic_fn=time.monotonic, sleep_fn=time.sleep,
                 task_probe=None, process_probe=None, start_task=None,
                 wait_stopped=None, health_probe=None, monotonic_deadline=None,
                 immutable_plan_check=None):
    now_fn = now_fn or utc_now
    task_probe = task_probe or read_task_probe
    process_probe = process_probe or read_process_probe
    start_task = start_task or start_scheduled_task
    if wait_stopped is None:
        wait_stopped = lambda config, timeout: wait_stopped_via_service(config, timeout, node_root)
    if health_probe is None:
        health_probe = lambda state_dir: health_via_project_cli(state_dir, node_root)
    claimed = False
    try:
        root, deadline, expires, config_path, state_path, wait_timeout_plan, health_timeout_plan = validate(plan, phase, out_dir, node_root)
        attempt = root / FILES['attempt']
        if immutable_plan_check is not None and not immutable_plan_check():
            raise ValueError('immutable plan bytes changed before restoration')
        if attempt.exists():
            return {'status': 'NO_REPLAY', 'start_attempted': False}
        if now_fn() > expires:
            return {'status': 'EXPIRED', 'start_attempted': False}
        if phase['state'] != 'STOP_ATTEMPTED':
            return {'status': 'NO_STOP', 'start_attempted': False}
        if now_fn() < deadline:
            return {'status': 'WAITING', 'start_attempted': False}
        mono = monotonic_fn()
        if monotonic_deadline is None:
            monotonic_deadline = mono + (expires - now_fn()).total_seconds()
        if mono >= monotonic_deadline:
            return {'status': 'REFUSED_MONOTONIC_LIMIT', 'start_attempted': False}
        # Restoration wait precedes the final Task Ready/XML and PID checks.
        remaining = min((expires - now_fn()).total_seconds(), monotonic_deadline - monotonic_fn())
        await_timeout = min(wait_timeout_plan, max(0.0, remaining - 1.0))
        if await_timeout <= 0:
            return {'status': 'EXPIRED_BEFORE_WAIT', 'start_attempted': False}
        ok, value = bounded(wait_stopped, str(config_path), await_timeout)
        if not ok:
            return {'status': 'STOP_WAIT_UNKNOWN', 'start_attempted': False, 'health_verified': False, **value}
        if now_fn() >= expires:
            return {'status': 'EXPIRED_AFTER_WAIT', 'start_attempted': False}
        if monotonic_fn() >= monotonic_deadline:
            return {'status': 'REFUSED_MONOTONIC_LIMIT', 'start_attempted': False}
        ok, observed = bounded(task_probe)
        if not ok:
            return {'status': 'TASK_PROBE_UNKNOWN', 'start_attempted': False, 'health_verified': False, **observed}
        if observed.get('task_name') != TASK_NAME or observed.get('task_path') != '\\' or observed.get('xml_sha256') != plan['task_xml_sha256']:
            raise ValueError('original full C Task changed')
        if observed.get('state') == 'Running':
            return {'status': 'STILL_RUNNING', 'start_attempted': False}
        if observed.get('state') != 'Ready':
            raise ValueError('original C Task not Ready')
        for original in plan['original_processes']:
            ok, alive = bounded(process_probe, original['pid'])
            if not ok or type(alive) is not bool:
                return {'status': 'PROCESS_PROBE_UNKNOWN', 'start_attempted': False, 'health_verified': False}
            if alive:
                return {'status': 'OLD_PID_PRESENT', 'start_attempted': False}
        final_task = task_probe()
        if (final_task.get('task_name') != TASK_NAME or final_task.get('task_path') != '\\'
                or final_task.get('state') != 'Ready'
                or final_task.get('xml_sha256') != plan['task_xml_sha256']):
            raise ValueError('original Task changed during final PID probes')
        if now_fn() >= expires:
            return {'status': 'EXPIRED_AFTER_PROBES', 'start_attempted': False}
        if monotonic_fn() >= monotonic_deadline:
            return {'status': 'REFUSED_MONOTONIC_LIMIT', 'start_attempted': False}
        if immutable_plan_check is not None and not immutable_plan_check():
            raise ValueError('immutable plan bytes changed after probes')
        record = {key: plan[key] for key in IDENTITY}
        record.update(schema=ATTEMPT_SCHEMA, node_id=NODE_ID, task_name=TASK_NAME, task_id=TASK_ID, work_id=WORK_ID,
                      plan_sha256=sha(canonical(plan)), phase_sha256=sha(canonical(phase)),
                      task_xml_sha256=plan['task_xml_sha256'], original_processes=plan['original_processes'],
                      attempted_at_utc=now_fn().isoformat(), status='START_ATTEMPTED', health_verified=False)
        try:
            exclusive(attempt, record)
            claimed = True
        except FileExistsError:
            return {'status': 'NO_REPLAY', 'start_attempted': False}
        except Exception as exc:  # claim may exist on disk; never start blindly
            return {'status': 'CLAIM_UNKNOWN', 'start_attempted': False,
                    'claim_may_exist': True, 'error_type': type(exc).__name__}
        # The durable exclusive claim precedes the only permitted mutation.
        if now_fn() >= expires:
            outcome = {'status': 'EXPIRED_AFTER_CLAIM', 'start_attempted': False, 'health_verified': False}
            append_record(attempt, outcome)
            return outcome
        if monotonic_fn() >= monotonic_deadline:
            outcome = {'status': 'REFUSED_MONOTONIC_LIMIT', 'start_attempted': False, 'health_verified': False}
            append_record(attempt, outcome)
            return outcome
        if immutable_plan_check is not None and not immutable_plan_check():
            outcome = {'status': 'REFUSED_PLAN_CHANGED', 'start_attempted': False, 'health_verified': False}
            append_record(attempt, outcome)
            return outcome
        try:
            code = start_task()
            outcome = {'status': 'START_COMMAND_RETURNED' if code == 0 else 'START_OUTCOME_UNKNOWN',
                       'start_attempted': True, 'exit_code': code, 'health_verified': False}
        except Exception as exc:  # noqa: BLE001 - unknown outcome, no retry
            outcome = {'status': 'START_OUTCOME_UNKNOWN', 'start_attempted': True,
                       'error_type': type(exc).__name__, 'health_verified': False}
        append_record(attempt, outcome)
        if outcome['status'] != 'START_COMMAND_RETURNED':
            return outcome
        health = await_health(plan, health_probe=health_probe, task_probe=task_probe,
                              process_probe=process_probe, now_fn=now_fn, monotonic_fn=monotonic_fn,
                              sleep_fn=sleep_fn,
                              until_utc=min(expires, now_fn() + timedelta(seconds=health_timeout_plan)),
                              until_mono=min(monotonic_deadline, monotonic_fn() + health_timeout_plan))
        append_record(attempt, health)
        return health
    except Exception as exc:
        return {'status': 'START_OUTCOME_UNKNOWN' if claimed else 'REFUSED',
                'start_attempted': claimed, 'error_type': type(exc).__name__,
                'detail': str(exc)[:300], 'health_verified': False}

def run_execute_watch(args, *, out_dir=OUT, node_root=NODE_ROOT,
                      now_fn=None, monotonic_fn=time.monotonic, sleep_fn=time.sleep,
                      task_probe=None, process_probe=None, process_identity_probe=None,
                      isolation_probe=None, start_task=None,
                      wait_stopped=None, health_probe=None):
    verify_fixed_layout()
    now_fn = now_fn or utc_now
    task_probe = task_probe or read_task_probe
    process_probe = process_probe or read_process_probe
    process_identity_probe = process_identity_probe or read_process_identity_probe
    start_task = start_task or start_scheduled_task
    if isolation_probe is None:
        from service_job_isolation import verify_service_job_isolation
        isolation_probe = verify_service_job_isolation
    if wait_stopped is None:
        wait_stopped = lambda config, timeout: wait_stopped_via_service(config, timeout, node_root)
    if health_probe is None:
        health_probe = lambda state_dir: health_via_project_cli(state_dir, node_root)
    root = Path(out_dir).resolve(strict=True)
    raw = (root / FILES['plan']).read_bytes()
    if not args.plan_sha256 or sha(raw) != args.plan_sha256:
        raise ValueError('immutable plan bytes changed')
    plan = json.loads(raw)
    phase = json.loads((root / FILES['phase']).read_bytes())
    root, deadline, expires, config_path, state_path, wait_timeout_plan, health_timeout_plan = validate(plan, phase, root, node_root)
    if (root / FILES['attempt']).exists():
        raise ValueError('existing restoration attempt; no new READY or replay')
    ready_at = now_fn()
    if timestamp(plan['prepared_at_utc']) > ready_at or not timedelta(seconds=30) <= deadline - ready_at <= timedelta(minutes=10) or ready_at >= expires:
        raise ValueError('no valid bounded remaining preparation window')
    initial_mono = monotonic_fn()
    monotonic_deadline = initial_mono + (expires - ready_at).total_seconds()
    monotonic_restore_at = initial_mono + (deadline - ready_at).total_seconds()
    isolation = isolation_probe(plan['supervisor_pid'], plan['worker_pid'])
    if (not isinstance(isolation, dict) or isolation.get('isolation_verified') is not True
            or isolation.get('supervisor_pid') != plan['supervisor_pid']
            or isolation.get('worker_pid') != plan['worker_pid']
            or isolation.get('pid') != os.getpid() or not isolation.get('jobs')
            or any(p.get('current_process_in_service_job') is not False for p in isolation['jobs'])):
        raise ValueError('specific original Job isolation not positively verified')
    bound = {p['pid'] for p in plan['original_processes']}
    if any(not set(p.get('job_member_pids', [])).issubset(bound) for p in isolation['jobs']):
        raise ValueError('original Job members omitted from process identities')
    for original in plan['original_processes']:
        current = process_identity_probe(original['pid'])
        if current.get('parent_pid') != original['parent_pid'] or timestamp(current['created_at_utc']) != timestamp(original['created_at_utc']):
            raise ValueError('original process identity or parent changed')
    initial = task_probe()
    if initial.get('xml_sha256') != plan['task_xml_sha256'] or initial.get('state') != 'Running':
        raise ValueError('watch preparation original C Task mismatch')
    if deadline - now_fn() < timedelta(seconds=30) or now_fn() >= expires or monotonic_fn() >= monotonic_deadline:
        raise ValueError('watch preparation consumed the valid remaining window')
    helper_process = process_identity_probe(os.getpid())
    if helper_process.get('pid') != os.getpid() or not helper_process.get('created_at_utc') or not helper_process.get('parent_pid'):
        raise ValueError('guard process identity missing')
    exclusive(root / FILES['ready'], {'schema': READY_SCHEMA, 'node_id': NODE_ID, 'pid': os.getpid(), 'helper_process': helper_process,
              'plan_sha256': args.plan_sha256, 'at_utc': now_fn().isoformat(), 'task': initial, 'job_isolation': isolation})
    log({'status': 'WATCH_READY', 'pid': os.getpid()}, out_dir=root)
    # Waiting invokes no model, transport sender or service mutation.
    while now_fn() < deadline or monotonic_fn() < monotonic_restore_at:
        if monotonic_fn() >= monotonic_deadline:
            log({'status': 'REFUSED_MONOTONIC_LIMIT'}, out_dir=root)
            return {'status': 'REFUSED_MONOTONIC_LIMIT', 'start_attempted': False}, 2
        if sha((root / FILES['plan']).read_bytes()) != args.plan_sha256:
            log({'status': 'REFUSED_PLAN_CHANGED'}, out_dir=root)
            return {'status': 'REFUSED_PLAN_CHANGED', 'start_attempted': False}, 2
        sleep_fn(0.5)
    if monotonic_fn() >= monotonic_deadline:
        log({'status': 'REFUSED_MONOTONIC_LIMIT'}, out_dir=root)
        return {'status': 'REFUSED_MONOTONIC_LIMIT', 'start_attempted': False}, 2
    if sha((root / FILES['plan']).read_bytes()) != args.plan_sha256:
        log({'status': 'REFUSED_PLAN_CHANGED'}, out_dir=root)
        return {'status': 'REFUSED_PLAN_CHANGED', 'start_attempted': False}, 2
    if now_fn() >= expires:
        log({'status': 'REFUSED_EXPIRED_WATCH'}, out_dir=root)
        return {'status': 'REFUSED_EXPIRED_WATCH', 'start_attempted': False}, 2
    phase = json.loads((root / FILES['phase']).read_bytes())
    result = restore_once(plan, phase, out_dir=root, node_root=node_root,
                          now_fn=now_fn, monotonic_fn=monotonic_fn, sleep_fn=sleep_fn,
                          task_probe=task_probe, process_probe=process_probe, start_task=start_task,
                          wait_stopped=wait_stopped, health_probe=health_probe,
                          monotonic_deadline=monotonic_deadline,
                          immutable_plan_check=lambda: sha((root / FILES['plan']).read_bytes()) == args.plan_sha256)
    log(result, out_dir=root)
    accepted = result.get('status') in ('START_HEALTH_VERIFIED', 'STILL_RUNNING', 'NO_STOP')
    return result, (0 if accepted else 2)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute-watch', action='store_true')
    parser.add_argument('--plan-sha256')
    args = parser.parse_args(argv)
    if not args.execute_watch:
        print(json.dumps({'mode': 'READ_ONLY', 'node': NODE_ID, 'task': read_task_probe(), 'pid': os.getpid()}))
        return 0
    result, code = run_execute_watch(args)
    print(json.dumps(result))
    return code


def entrypoint():
    # Error reporting in default mode remains genuinely read-only.
    watch_mode = '--execute-watch' in sys.argv[1:]
    try:
        result = main()
    except Exception as exc:
        failure = {'status': 'WATCH_FAILED', 'error_type': type(exc).__name__, 'detail': str(exc)[:300], 'pid': os.getpid()}
        if watch_mode:
            try:
                log(failure)
            except Exception:
                pass
        print(json.dumps(failure))
        result = 2
    return result


if __name__ == '__main__':
    raise SystemExit(entrypoint())

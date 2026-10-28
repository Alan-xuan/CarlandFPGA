"""Run only the new C24 controls in a bounded Windows CPU process tree.

Limits are committed memory, not resident RAM. No breakaway flags are enabled.
References: Microsoft Learn, jobobject_extended_limit_information;
jobobject_basic_limit_information; AssignProcessToJobObject; Nested Jobs.
This executable does not run old tests, models, board or endpoint processes.
"""
from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes as wt
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

WALL_SECONDS = 30
CLEANUP_RESERVE_SECONDS = 2
OUTPUT_CAP_BYTES = 65536
PROCESS_MEMORY = 512 * 1024 * 1024
JOB_MEMORY = 1024 * 1024 * 1024
FLAGS = 0x00000004 | 0x00000008 | 0x00000100 | 0x00000200 | 0x00002000
CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
STARTF_USESTDHANDLES = 0x00000100
WAIT_TIMEOUT = 258
WAIT_FAILED = 0xFFFFFFFF


class BasicLimits(ct.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ct.c_longlong),
                ("PerJobUserTimeLimit", ct.c_longlong), ("LimitFlags", wt.DWORD),
                ("MinimumWorkingSetSize", ct.c_size_t),
                ("MaximumWorkingSetSize", ct.c_size_t),
                ("ActiveProcessLimit", wt.DWORD), ("Affinity", ct.c_size_t),
                ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD)]


class IOCounters(ct.Structure):
    _fields_ = [(name, ct.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class ExtendedLimits(ct.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IOCounters),
                ("ProcessMemoryLimit", ct.c_size_t), ("JobMemoryLimit", ct.c_size_t),
                ("PeakProcessMemoryUsed", ct.c_size_t), ("PeakJobMemoryUsed", ct.c_size_t)]


class Accounting(ct.Structure):
    _fields_ = [(name, ct.c_longlong) for name in (
        "TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
    _fields_ += [(name, wt.DWORD) for name in (
        "TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]


class StartupInfo(ct.Structure):
    _fields_ = [("cb", wt.DWORD), ("lpReserved", wt.LPWSTR), ("lpDesktop", wt.LPWSTR),
                ("lpTitle", wt.LPWSTR), ("dwX", wt.DWORD), ("dwY", wt.DWORD),
                ("dwXSize", wt.DWORD), ("dwYSize", wt.DWORD),
                ("dwXCountChars", wt.DWORD), ("dwYCountChars", wt.DWORD),
                ("dwFillAttribute", wt.DWORD), ("dwFlags", wt.DWORD),
                ("wShowWindow", wt.WORD), ("cbReserved2", wt.WORD),
                ("lpReserved2", ct.POINTER(ct.c_ubyte)), ("hStdInput", wt.HANDLE),
                ("hStdOutput", wt.HANDLE), ("hStdError", wt.HANDLE)]


class ProcessInfo(ct.Structure):
    _fields_ = [("hProcess", wt.HANDLE), ("hThread", wt.HANDLE),
                ("dwProcessId", wt.DWORD), ("dwThreadId", wt.DWORD)]


class StartupInfoEx(ct.Structure):
    _fields_ = [("StartupInfo", StartupInfo), ("lpAttributeList", ct.c_void_p)]


class MemoryCounters(ct.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)]
    _fields_ += [(name, ct.c_size_t) for name in (
        "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
        "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save_json(path: Path, value: dict) -> None:
    with path.open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def bind_api():
    kernel = ct.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([ct.c_void_p, wt.LPCWSTR], wt.HANDLE),
        'SetInformationJobObject': ([wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD], wt.BOOL),
        'QueryInformationJobObject': ([wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD, ct.c_void_p], wt.BOOL),
        'AssignProcessToJobObject': ([wt.HANDLE, wt.HANDLE], wt.BOOL),
        'CreateProcessW': ([wt.LPCWSTR, wt.LPWSTR, ct.c_void_p, ct.c_void_p, wt.BOOL,
                            wt.DWORD, ct.c_void_p, wt.LPCWSTR,
                            ct.POINTER(StartupInfo), ct.POINTER(ProcessInfo)], wt.BOOL),
        'ResumeThread': ([wt.HANDLE], wt.DWORD),
        'WaitForSingleObject': ([wt.HANDLE, wt.DWORD], wt.DWORD),
        'GetExitCodeProcess': ([wt.HANDLE, ct.POINTER(wt.DWORD)], wt.BOOL),
        'TerminateJobObject': ([wt.HANDLE, wt.UINT], wt.BOOL),
        'TerminateProcess': ([wt.HANDLE, wt.UINT], wt.BOOL),
        'CloseHandle': ([wt.HANDLE], wt.BOOL),
        'InitializeProcThreadAttributeList': ([ct.c_void_p, wt.DWORD, wt.DWORD, ct.POINTER(ct.c_size_t)], wt.BOOL),
        'UpdateProcThreadAttribute': ([ct.c_void_p, wt.DWORD, ct.c_size_t, ct.c_void_p, ct.c_size_t, ct.c_void_p, ct.c_void_p], wt.BOOL),
        'DeleteProcThreadAttributeList': ([ct.c_void_p], None),
        'GetCurrentProcess': ([], wt.HANDLE),
        'K32GetProcessMemoryInfo': ([wt.HANDLE, ct.c_void_p, wt.DWORD], wt.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return kernel


def check(result, operation):
    if not result:
        raise ct.WinError(ct.get_last_error(), operation)
    return result


def digest_file(path: Path) -> dict:
    digest = hashlib.sha256()
    count = 0
    with path.open('rb') as stream:
        while count <= OUTPUT_CAP_BYTES and (chunk := stream.read(min(8192, OUTPUT_CAP_BYTES+1-count))):
            count += len(chunk)
            digest.update(chunk)
    if count > OUTPUT_CAP_BYTES:
        return {'sha256': None, 'bytes': path.stat().st_size, 'within_cap': False,
                'prefix_sha256': digest.hexdigest(), 'reason': 'cap_exceeded; full raw file retained, not fully read or hashed in batch'}
    return {'sha256': digest.hexdigest(), 'bytes': count, 'within_cap': True}


def stopped_evidence(k, job, process, assigned: bool, deadline: float) -> dict:
    """Observe the original process and all job members; uncertainty never passes."""
    evidence = {'termination_requests': [], 'original_process_signaled': not bool(process.hProcess),
                'original_process_id': int(process.dwProcessId) if process.hProcess else None,
                'active_job_members': None, 'cleanup_unknown': True}
    try:
        if process.hProcess:
            wait = int(k.WaitForSingleObject(process.hProcess, 0))
            evidence['initial_process_wait'] = wait
            account = Accounting()
            query_ok = bool(k.QueryInformationJobObject(job, 1, ct.byref(account), ct.sizeof(account), None)) if job else False
            active = int(account.ActiveProcesses) if query_ok else None
            if wait != 0 or active not in (0, None):
                method = 'TerminateJobObject' if assigned and job else 'TerminateProcess'
                target = job if method == 'TerminateJobObject' else process.hProcess
                ok = bool(getattr(k, method)(target, 126))
                evidence['termination_requests'].append({'method': method, 'ok': ok,
                                                         'winerror_if_failed': None if ok else ct.get_last_error()})
            remaining = max(0, min(1500, int((deadline-time.monotonic())*1000)))
            wait = int(k.WaitForSingleObject(process.hProcess, remaining))
            evidence['final_process_wait'] = wait
            evidence['original_process_signaled'] = wait == 0
            code = wt.DWORD()
            if k.GetExitCodeProcess(process.hProcess, ct.byref(code)):
                evidence['original_process_exit_code'] = int(code.value)
        if job:
            while True:
                account = Accounting()
                ok = bool(k.QueryInformationJobObject(job, 1, ct.byref(account), ct.sizeof(account), None))
                evidence['job_accounting_query_ok'] = ok
                evidence['active_job_members'] = int(account.ActiveProcesses) if ok else None
                if not ok or account.ActiveProcesses == 0 or time.monotonic() >= deadline:
                    break
                time.sleep(min(0.01, max(0, deadline-time.monotonic())))
        evidence['cleanup_unknown'] = not (evidence['original_process_signaled'] and
                                           (not job or evidence['active_job_members'] == 0))
    except BaseException as exc:
        evidence['cleanup_error'] = {'type': type(exc).__name__, 'message': str(exc)}
    return evidence


def run(python: Path, expected_python_sha256: str, base_python: Path,
        expected_base_sha256: str, output: Path, guard: Path) -> dict:
    started = time.monotonic()
    if os.name != 'nt':
        raise ValueError('This C24 resource wrapper requires Windows Job Objects')
    import msvcrt

    here = Path(__file__).resolve().parent
    module, controls = here/'causal_data.py', here/'test_causal_data.py'
    python = python.resolve(strict=True)
    if sha(python.read_bytes()) != expected_python_sha256:
        raise ValueError('CPU interpreter hash mismatch; no child created')
    base_python = base_python.resolve(strict=True)
    if sha(base_python.read_bytes()) != expected_base_sha256:
        raise ValueError('Base CPU interpreter hash mismatch; no child created')
    if not module.is_file() or not controls.is_file():
        raise ValueError('Only the two named new C24 source files may be used')
    output = output.resolve()
    if output == here or here in output.parents:
        raise ValueError('Raw control outputs must be outside the product directory')
    output.mkdir(parents=True, exist_ok=False)
    guard = guard.resolve()
    if guard == here or here in guard.parents:
        raise ValueError('Batch guard must be in private operation evidence, outside product files')
    guard.parent.mkdir(parents=True, exist_ok=True)
    save_json(guard, {'operation_id': 'C-DEEPEYE-CAUSAL-DATA-PREPARATION-20261028-24',
                      'batch_version': 1, 'output': str(output),
                      'state': 'intent_consumed; no automatic retry even at a different output path',
                      'caller_scope': 'unique main binds this fixed guard path to its recorded assignment'})
    if any(p.stat().st_size > 65536 for p in [module, controls, here/'run_controls.py']):
        raise ValueError('New source exceeds its small-file cap; no child created')
    source_pins = {p.name: {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
                   for p in [module, controls, here/'run_controls.py']}
    argv = [str(python), '-I', '-S', '-B', '-X', 'utf8', str(controls),
            '--module', str(module), '--work-dir', str(output/'synthetic-work')]
    report = {'scope': 'one new tiny synthetic-definition CPU control batch, not physical/model acceptance',
              'argv': argv, 'cwd': str(here), 'source_pins': source_pins,
              'python_sha256': expected_python_sha256, 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'base_python': str(base_python), 'base_python_sha256': expected_base_sha256,
              'batch_guard': str(guard), 'parent_wrapper_outside_new_job': True,
              'resource_scope': 'queried limits cover assigned control child/descendants; wrapper parent separately measured; committed memory, not RSS or a generic sandbox',
              'requested_limits': {'wall_seconds': WALL_SECONDS, 'job_user_cpu_seconds': WALL_SECONDS,
                                   'per_process_commit_bytes': PROCESS_MEMORY, 'job_commit_bytes': JOB_MEMORY,
                                   'active_processes': 4, 'breakaway': False},
              'output_cap_bytes_per_stream': OUTPUT_CAP_BYTES,
              'output_cap_scope': '100ms size polling and bounded digest reads; detection cap, not a hard disk quota',
              'cleanup_reserve_seconds': CLEANUP_RESERVE_SECONDS,
              'status': 'not_started', 'child_created': False, 'child_assigned_before_resume': False,
              'child_resumed': False, 'timeout': False, 'child_exit_code': None,
              'all_old_tests_models_training_PDE_endpoint_owner_board_executions': 0}
    save_json(output/'intent.json', report)
    k = bind_api()
    job = None
    process = ProcessInfo()
    pending_interrupt = None
    try:
        job = check(k.CreateJobObjectW(None, None), 'CreateJobObjectW')
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = FLAGS
        limits.BasicLimitInformation.PerJobUserTimeLimit = WALL_SECONDS * 10_000_000
        limits.BasicLimitInformation.ActiveProcessLimit = 4
        limits.ProcessMemoryLimit, limits.JobMemoryLimit = PROCESS_MEMORY, JOB_MEMORY
        check(k.SetInformationJobObject(job, 9, ct.byref(limits), ct.sizeof(limits)), 'SetInformationJobObject')
        observed = ExtendedLimits()
        check(k.QueryInformationJobObject(job, 9, ct.byref(observed), ct.sizeof(observed), None), 'QueryJobLimits')
        if (observed.BasicLimitInformation.LimitFlags & FLAGS != FLAGS or
                observed.ProcessMemoryLimit != PROCESS_MEMORY or observed.JobMemoryLimit != JOB_MEMORY or
                observed.BasicLimitInformation.PerJobUserTimeLimit != WALL_SECONDS * 10_000_000 or
                observed.BasicLimitInformation.ActiveProcessLimit != 4):
            raise RuntimeError('Queried job limits differ; no child launched')
        report['queried_limits'] = {'flags': int(observed.BasicLimitInformation.LimitFlags),
                                   'process_commit_bytes': int(observed.ProcessMemoryLimit),
                                   'job_commit_bytes': int(observed.JobMemoryLimit),
                                   'job_user_time_100ns': int(observed.BasicLimitInformation.PerJobUserTimeLimit),
                                   'active_processes': int(observed.BasicLimitInformation.ActiveProcessLimit)}
        with open(os.devnull, 'rb') as stdin, (output/'stdout.txt').open('xb') as stdout, (output/'stderr.txt').open('xb') as stderr:
            for stream in [stdin, stdout, stderr]:
                os.set_inheritable(stream.fileno(), True)
            startup = StartupInfoEx()
            startup.StartupInfo.cb = ct.sizeof(startup)
            startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES
            handles = [msvcrt.get_osfhandle(stream.fileno()) for stream in [stdin, stdout, stderr]]
            startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput, startup.StartupInfo.hStdError = handles
            size = ct.c_size_t()
            k.InitializeProcThreadAttributeList(None, 1, 0, ct.byref(size))
            if not size.value:
                raise ct.WinError(ct.get_last_error(), 'AttributeListSize')
            attributes = ct.create_string_buffer(size.value)
            check(k.InitializeProcThreadAttributeList(attributes, 1, 0, ct.byref(size)), 'InitializeAttributeList')
            startup.lpAttributeList = ct.cast(attributes, ct.c_void_p)
            handle_list = (wt.HANDLE*3)(*handles)
            try:
                check(k.UpdateProcThreadAttribute(attributes, 0, 0x00020002, ct.byref(handle_list),
                                                  ct.sizeof(handle_list), None, None), 'SetHandleList')
                command = ct.create_unicode_buffer(subprocess.list2cmdline(argv))
                check(k.CreateProcessW(str(python), command, None, None, True,
                                       CREATE_SUSPENDED | CREATE_NO_WINDOW | EXTENDED_STARTUPINFO_PRESENT,
                                       None, str(here), ct.byref(startup.StartupInfo), ct.byref(process)), 'CreateProcessW')
            finally:
                k.DeleteProcThreadAttributeList(attributes)
            report['child_created'], report['child_pid'] = True, int(process.dwProcessId)
            check(k.AssignProcessToJobObject(job, process.hProcess), 'AssignProcessToJobObject')
            report['child_assigned_before_resume'] = True
            resume_count = int(k.ResumeThread(process.hThread))
            report['previous_suspend_count'] = resume_count
            if resume_count != 1:
                raise RuntimeError('Unexpected ResumeThread count; reconcile original process before any retry')
            report['child_resumed'] = True
            deadline = started + WALL_SECONDS - CLEANUP_RESERVE_SECONDS
            while True:
                remaining_ms = max(0, int((deadline-time.monotonic())*1000))
                wait = k.WaitForSingleObject(process.hProcess, min(100, remaining_ms))
                if any((output/name).stat().st_size > OUTPUT_CAP_BYTES for name in ['stdout.txt', 'stderr.txt']):
                    raise RuntimeError('New control output cap exceeded; terminate own job')
                if wait != WAIT_TIMEOUT or time.monotonic() >= deadline:
                    break
            if wait == WAIT_TIMEOUT:
                report['timeout'] = True
                raise TimeoutError('Control wait deadline reached; reserved cleanup follows')
            elif wait != 0:
                raise ct.WinError(ct.get_last_error(), 'WaitForSingleObject')
            code = wt.DWORD()
            check(k.GetExitCodeProcess(process.hProcess, ct.byref(code)), 'GetExitCodeProcess')
            report['child_exit_code'] = int(code.value)
            observed = ExtendedLimits()
            account = Accounting()
            check(k.QueryInformationJobObject(job, 9, ct.byref(observed), ct.sizeof(observed), None), 'QueryJobPeaks')
            check(k.QueryInformationJobObject(job, 1, ct.byref(account), ct.sizeof(account), None), 'QueryJobAccounting')
            report['measured'] = {'elapsed_wall_seconds': time.monotonic()-started,
                                  'peak_process_commit_bytes': int(observed.PeakProcessMemoryUsed),
                                  'peak_job_commit_bytes': int(observed.PeakJobMemoryUsed),
                                  'job_user_cpu_100ns': int(account.TotalUserTime),
                                  'job_kernel_cpu_100ns': int(account.TotalKernelTime),
                                  'total_processes': int(account.TotalProcesses),
                                  'active_processes_after_child': int(account.ActiveProcesses)}
            if account.ActiveProcesses:
                raise RuntimeError('Unexpected control descendants remained; reconcile own job')
            good = (code.value == 0 and not report['timeout'] and
                    report['measured']['elapsed_wall_seconds'] <= WALL_SECONDS and
                    observed.PeakProcessMemoryUsed <= PROCESS_MEMORY and observed.PeakJobMemoryUsed <= JOB_MEMORY and
                    account.TotalUserTime <= WALL_SECONDS*10_000_000)
            report['status'] = 'passed' if good else 'failed'
    except BaseException as exc:
        report['status'], report['error'] = 'failed', {'type': type(exc).__name__, 'message': str(exc)}
        if not isinstance(exc, Exception):
            pending_interrupt = exc
    finally:
        cleanup_started = time.monotonic()
        report['cleanup'] = stopped_evidence(k, job, process, report['child_assigned_before_resume'], started+WALL_SECONDS-0.5)
        report['cleanup_elapsed_wall_seconds'] = time.monotonic()-cleanup_started
        if report['cleanup']['cleanup_unknown']:
            report['status'] = 'failed'
        memory = MemoryCounters()
        memory.cb = ct.sizeof(memory)
        memory_ok = bool(k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ct.byref(memory), ct.sizeof(memory)))
        report['parent_memory_query_ok'] = memory_ok
        report['parent_peak_commit_bytes'] = int(memory.PeakPagefileUsage) if memory_ok else None
        report['parent_memory_scope'] = 'wrapper peak commit through cleanup query; parent is outside test Job, bounded metadata hashing follows'
        if not memory_ok or memory.PeakPagefileUsage > PROCESS_MEMORY:
            report['status'] = 'failed'
        report['handle_closes'] = []
        for handle in [process.hThread, process.hProcess, job]:
            if handle:
                ok = bool(k.CloseHandle(handle))
                report['handle_closes'].append({'ok': ok, 'winerror_if_failed': None if ok else ct.get_last_error()})
                if not ok:
                    report['status'] = 'failed'
    report['raw_outputs'] = {}
    for name in ['stdout.txt', 'stderr.txt']:
        path = output/name
        if path.exists():
            report['raw_outputs'][name] = digest_file(path)
            if not report['raw_outputs'][name]['within_cap']:
                report['status'] = 'failed'
    report['source_bytes_unchanged_after_batch'] = all(
        sha((here/name).read_bytes()) == pin['sha256'] for name, pin in source_pins.items())
    memory = MemoryCounters()
    memory.cb = ct.sizeof(memory)
    memory_ok = bool(k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ct.byref(memory), ct.sizeof(memory)))
    report['parent_memory_query_ok'] = memory_ok
    report['parent_peak_commit_bytes'] = int(memory.PeakPagefileUsage) if memory_ok else None
    report['parent_memory_scope'] = 'wrapper peak commit through post-digest/source-check query; excludes final result serialization and exit; parent outside test Job'
    measured_job_peak = report.get('measured', {}).get('peak_job_commit_bytes')
    report['combined_peak_commit_through_parent_query'] = (measured_job_peak + report['parent_peak_commit_bytes']
                                                        if measured_job_peak is not None and report['parent_peak_commit_bytes'] is not None else None)
    if (not memory_ok or memory.PeakPagefileUsage > PROCESS_MEMORY or
            report['combined_peak_commit_through_parent_query'] is None or
            report['combined_peak_commit_through_parent_query'] > JOB_MEMORY):
        report['status'] = 'failed'
    report['evidence_checkpoint_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    report['elapsed_through_evidence_checkpoint_seconds'] = time.monotonic()-started
    report['elapsed_scope'] = 'through bounded log digests, source rehash and parent memory query; excludes final serialization/exit; external supervisor must measure complete original command'
    if (not report['source_bytes_unchanged_after_batch'] or
            report['elapsed_through_evidence_checkpoint_seconds'] > WALL_SECONDS):
        report['status'] = 'failed'
    save_json(output/'result.json', report)
    if pending_interrupt is not None:
        raise pending_interrupt
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--expected-python-sha256', required=True)
    parser.add_argument('--base-python', type=Path, required=True)
    parser.add_argument('--expected-base-python-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--guard', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args.python, args.expected_python_sha256, args.base_python,
                     args.expected_base_python_sha256, args.output, args.guard)
    except Exception as exc:
        guard_consumed = args.guard.exists()
        print(json.dumps({'status': 'execution_or_evidence_unknown' if guard_consumed else 'not_run',
                          'guard_consumed': guard_consumed, 'may_have_run': guard_consumed,
                          'definite_no_child': not guard_consumed,
                          'error': {'type': type(exc).__name__, 'message': str(exc)},
                          'recovery': 'inspect original guard, intent, process and raw evidence; no automatic retry'}))
        return 2
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

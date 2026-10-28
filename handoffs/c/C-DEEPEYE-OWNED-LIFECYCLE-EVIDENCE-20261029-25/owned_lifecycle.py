"""C25 two-case original-HANDLE/Job observer; only root may execute.

No Win32 DLL/API is loaded until run_batch. No PID lookup, old case, model,
endpoint, persistent owner or generic command runner is provided.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

PROCESS_LIMIT = 512 * 1024 * 1024
JOB_LIMIT = 1024 * 1024 * 1024
OUTPUT_LIMIT = 1024 * 1024
STREAM_LIMIT = 4096
OWNER_JSON_LIMIT = 65536
MAX_EVENTS = 256
OBSERVER_SECONDS = 24.0
CLEANUP_RESERVE_SECONDS = 4.0
JOB_FLAGS = 0x0000230C  # JOB_TIME|ACTIVE_PROCESS|PROCESS_MEMORY|JOB_MEMORY|KILL_ON_JOB_CLOSE
CREATE_FLAGS = 0x08080004  # NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT|SUSPENDED
EXPECTED_LINES = {'primary': b'C25_PRIMARY\n', 'owned-residual': b'C25_OWNED_RESIDUAL\n'}
_USED = False


class ObservationError(ValueError):
    pass


def _json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def _hash_file(path, cap):
    with path.open('rb') as stream:
        data = stream.read(cap + 1)
    if len(data) > cap:
        raise ObservationError('pin_size')
    return len(data), hashlib.sha256(data).hexdigest(), data[:2]


def _plain_path(path):
    if type(path) is not type(Path()) or not path.is_absolute() or len(str(path)) > 1024:
        raise ObservationError('path_type')
    if any(char in str(path) for char in ('"', '\0', '\r', '\n')):
        raise ObservationError('path_characters')
    for component in reversed((path,) + tuple(path.parents)):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
            raise ObservationError('reparse_path')
    return path.resolve(strict=True)


class _Events:
    def __init__(self, started):
        self.started, self.rows, self.bytes, self.lost = started, [], 0, False

    def add(self, case, api, **fields):
        # Logging must never prevent cleanup. A lost/overflowed event vetoes PASS.
        try:
            row = dict(index=len(self.rows), elapsed_ns=time.monotonic_ns()-self.started, case=case, api=api, **fields)
            size = len(_json(row))
            if len(self.rows) >= MAX_EVENTS or self.bytes + size > 44000:
                self.lost = True
                return
            self.rows.append(row)
            self.bytes += size
        except BaseException:
            self.lost = True


class _API:
    """Fixed Win64 ABI, loaded only inside the authorized invocation."""
    def __init__(self):
        import ctypes as c
        self.c = c
        if c.sizeof(c.c_void_p) != 8:
            raise ObservationError('win64_required')
        H, D, B, Z, Q, L = c.c_void_p, c.c_uint32, c.c_int32, c.c_size_t, c.c_uint64, c.c_int64
        class SA(c.Structure):
            _fields_ = [('nLength', D), ('lpSecurityDescriptor', H), ('bInheritHandle', B)]
        class SI(c.Structure):
            _fields_ = [('cb', D), ('lpReserved', c.c_wchar_p), ('lpDesktop', c.c_wchar_p),
                        ('lpTitle', c.c_wchar_p), ('dwX', D), ('dwY', D), ('dwXSize', D),
                        ('dwYSize', D), ('dwXCountChars', D), ('dwYCountChars', D),
                        ('dwFillAttribute', D), ('dwFlags', D), ('wShowWindow', c.c_uint16),
                        ('cbReserved2', c.c_uint16), ('lpReserved2', H),
                        ('hStdInput', H), ('hStdOutput', H), ('hStdError', H)]
        class SIX(c.Structure):
            _fields_ = [('StartupInfo', SI), ('lpAttributeList', H)]
        class PI(c.Structure):
            _fields_ = [('hProcess', H), ('hThread', H), ('dwProcessId', D), ('dwThreadId', D)]
        class BASIC(c.Structure):
            _fields_ = [('PerProcessUserTimeLimit', L), ('PerJobUserTimeLimit', L), ('LimitFlags', D),
                        ('MinimumWorkingSetSize', Z), ('MaximumWorkingSetSize', Z),
                        ('ActiveProcessLimit', D), ('Affinity', Z), ('PriorityClass', D), ('SchedulingClass', D)]
        class IO(c.Structure):
            _fields_ = [(name, Q) for name in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                                               'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]
        class EXT(c.Structure):
            _fields_ = [('BasicLimitInformation', BASIC), ('IoInfo', IO), ('ProcessMemoryLimit', Z),
                        ('JobMemoryLimit', Z), ('PeakProcessMemoryUsed', Z), ('PeakJobMemoryUsed', Z)]
        class ACCOUNT(c.Structure):
            _fields_ = [('TotalUserTime', L), ('TotalKernelTime', L), ('ThisPeriodTotalUserTime', L),
                        ('ThisPeriodTotalKernelTime', L), ('TotalPageFaultCount', D),
                        ('TotalProcesses', D), ('ActiveProcesses', D), ('TotalTerminatedProcesses', D)]
        class PIDS(c.Structure):
            _fields_ = [('NumberOfAssignedProcesses', D), ('NumberOfProcessIdsInList', D), ('ProcessIdList', Z * 2)]
        class MEMORY(c.Structure):
            _fields_ = [('cb', D), ('PageFaultCount', D)] + [(name, Z) for name in
                ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
                 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]
        self.SA, self.SIX, self.PI, self.EXT, self.ACCOUNT, self.PIDS, self.MEMORY = SA, SIX, PI, EXT, ACCOUNT, PIDS, MEMORY
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ([H, c.c_wchar_p], H),
            'SetInformationJobObject': ([H, c.c_int32, H, D], B),
            'QueryInformationJobObject': ([H, c.c_int32, H, D, c.POINTER(D)], B),
            'CreatePipe': ([c.POINTER(H), c.POINTER(H), c.POINTER(SA), D], B),
            'SetHandleInformation': ([H, D, D], B),
            'CreateFileW': ([c.c_wchar_p, D, D, c.POINTER(SA), D, D, H], H),
            'InitializeProcThreadAttributeList': ([H, D, D, c.POINTER(Z)], B),
            'UpdateProcThreadAttribute': ([H, D, Z, H, Z, H, c.POINTER(Z)], B),
            'DeleteProcThreadAttributeList': ([H], None),
            'CreateProcessW': ([c.c_wchar_p, c.c_wchar_p, H, H, B, D, H, c.c_wchar_p, c.POINTER(SIX), c.POINTER(PI)], B),
            'AssignProcessToJobObject': ([H, H], B),
            'ResumeThread': ([H], D),
            'WaitForSingleObject': ([H, D], D),
            'GetExitCodeProcess': ([H, c.POINTER(D)], B),
            'TerminateJobObject': ([H, D], B),
            'TerminateProcess': ([H, D], B),
            'CloseHandle': ([H], B),
            'PeekNamedPipe': ([H, H, D, c.POINTER(D), c.POINTER(D), c.POINTER(D)], B),
            'ReadFile': ([H, H, D, c.POINTER(D), H], B),
            'GetCurrentProcess': ([], H),
            'K32GetProcessMemoryInfo': ([H, c.POINTER(MEMORY), D], B),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.kernel, name)
            fn.argtypes, fn.restype = args, result
            setattr(self, name, fn)
        sizes = dict(SA=c.sizeof(SA), SIX=c.sizeof(SIX), PI=c.sizeof(PI), BASIC=c.sizeof(BASIC),
                     EXT=c.sizeof(EXT), ACCOUNT=c.sizeof(ACCOUNT), PIDS=c.sizeof(PIDS), MEMORY=c.sizeof(MEMORY))
        if sizes != dict(SA=24, SIX=112, PI=24, BASIC=64, EXT=144, ACCOUNT=48, PIDS=24, MEMORY=80):
            raise ObservationError('abi_size_mismatch')
        self.sizes = sizes


class _Case:
    def __init__(self, api, events, name, directory, base, actor, work_deadline, hard_deadline):
        self.a, self.c, self.log = api, api.c, events
        self.name, self.directory, self.base, self.actor = name, directory, base, actor
        self.work_deadline, self.hard_deadline = work_deadline, hard_deadline
        self.job, self.actors, self.close_rows = None, [], []
        self.job_close_attempted = self.terminate_attempted = False
        self.failed = self.output_unknown = False
        self.peak_process = self.peak_job = 0
        self.final_snapshot = None
        self.result = dict(name=name, attempted=True, lifecycle_gate_passed=False, expected_rejection=False,
                           control_passed=False, reason='incomplete', primary_exit_code=None,
                           before_deadline=None, after_deadline=None, final_job_zero=False,
                           all_original_handles_signaled=False, all_closes_succeeded=False)

    def _budget(self):
        if time.monotonic() >= self.work_deadline or self.log.lost:
            raise ObservationError('work_deadline_or_evidence_bound')

    def _call(self, name, *args, inputs=None):
        self.c.set_last_error(0)
        returned = getattr(self.a, name)(*args)
        error = self.c.get_last_error()
        self.log.add(self.name, name, inputs=inputs or {}, returned=returned, last_error=error)
        return returned, error

    def _close(self, handle, label):
        if not handle or handle == self.c.c_void_p(-1).value:
            return True
        try:
            returned, error = self._call('CloseHandle', handle, inputs=dict(handle=handle, label=label))
            okay = bool(returned)
            row = dict(label=label, handle=handle, returned=returned, last_error=error, succeeded=okay)
        except BaseException as exc:
            okay = False
            row = dict(label=label, handle=handle, succeeded=False, exception_type=type(exc).__name__)
            self.log.add(self.name, 'CloseHandle_exception', **row)
        self.close_rows.append(row)
        if not okay:
            self.failed = True
        return okay

    def _wait(self, member, milliseconds):
        handle = member['pi'].hProcess
        if not handle:
            return None
        result, _error = self._call('WaitForSingleObject', handle, milliseconds,
                                    inputs=dict(handle=handle, role=member['role'], milliseconds=milliseconds))
        if result not in (0, 258):
            raise ObservationError('wait_failed')
        if result == 0:
            member['signaled'] = True
            code = self.c.c_uint32()
            okay, _error = self._call('GetExitCodeProcess', handle, self.c.byref(code), inputs=dict(handle=handle))
            self.log.add(self.name, 'original_exit_code', handle=handle, succeeded=bool(okay), exit_code=code.value if okay else None)
            if not okay:
                raise ObservationError('exit_code_unknown')
            member['exit_code'] = code.value
        return result

    def _snapshot(self, label):
        sample_started = time.monotonic()
        calls, values = [], {}
        for info_class, typ, key in ((1, self.a.ACCOUNT, 'accounting'), (3, self.a.PIDS, 'pid_list'), (9, self.a.EXT, 'extended')):
            value, length = typ(), self.c.c_uint32()
            self.c.set_last_error(0)
            okay = self.a.QueryInformationJobObject(self.job, info_class, self.c.byref(value), self.c.sizeof(value), self.c.byref(length))
            error = self.c.get_last_error()
            call = dict(info_class=info_class, buffer_bytes=self.c.sizeof(value), returned=okay,
                        returned_length=length.value, last_error=error)
            calls.append(call)
            if okay:
                if key == 'accounting':
                    values[key] = dict(active=value.ActiveProcesses, total_processes_cumulative=value.TotalProcesses,
                                       terminated_cumulative=value.TotalTerminatedProcesses,
                                       user_time_100ns=value.TotalUserTime, kernel_time_100ns=value.TotalKernelTime)
                elif key == 'pid_list':
                    count = value.NumberOfProcessIdsInList
                    values[key] = dict(assigned=value.NumberOfAssignedProcesses, count=count,
                                       pids=list(value.ProcessIdList)[:min(count, 2)], complete=bool(count == value.NumberOfAssignedProcesses and count <= 2))
                else:
                    basic = value.BasicLimitInformation
                    values[key] = dict(limit_flags=basic.LimitFlags, active_limit=basic.ActiveProcessLimit,
                                       job_user_time_limit_100ns=basic.PerJobUserTimeLimit,
                                       process_commit_limit=value.ProcessMemoryLimit, job_commit_limit=value.JobMemoryLimit,
                                       peak_process_commit_bytes=value.PeakProcessMemoryUsed, peak_job_commit_bytes=value.PeakJobMemoryUsed)
                    self.peak_process = max(self.peak_process, value.PeakProcessMemoryUsed)
                    self.peak_job = max(self.peak_job, value.PeakJobMemoryUsed)
        snapshot = dict(label=label, job_handle=self.job, calls=calls,
                        sample_started_monotonic=sample_started,
                        sample_completed_monotonic=time.monotonic(), **values)
        self.log.add(self.name, 'QueryInformationJobObject', **snapshot)
        if len(values) != 3 or not values['pid_list']['complete']:
            raise ObservationError('job_query_unknown_or_more_than_two')
        known = {member['pi'].dwProcessId for member in self.actors if member['pi'].hProcess}
        if set(values['pid_list']['pids']) - known:
            raise ObservationError('job_membership_unknown')
        limits = values['extended']
        if (limits['limit_flags'] != JOB_FLAGS or limits['active_limit'] != 2
                or limits['job_user_time_limit_100ns'] != 200000000
                or limits['process_commit_limit'] != PROCESS_LIMIT or limits['job_commit_limit'] != JOB_LIMIT
                or self.peak_process > PROCESS_LIMIT or self.peak_job > JOB_LIMIT
                or values['accounting']['active'] > 2 or values['accounting']['user_time_100ns'] > 200000000):
            raise ObservationError('job_resource_gate')
        return snapshot

    @staticmethod
    def _zero(snapshot):
        return snapshot['accounting']['active'] == 0 and snapshot['pid_list']['assigned'] == 0 and snapshot['pid_list']['pids'] == []

    def _job_zero_by(self, deadline, label):
        # Fixed bounded polling of this original Job, never a model/PID scan.
        for index in range(12):
            if time.monotonic() >= deadline:
                return False
            snapshot = self._snapshot(label + ':' + str(index))
            self.final_snapshot = snapshot
            if time.monotonic() <= deadline and self._zero(snapshot):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.1, remaining))
        return False

    def _spawn(self, role):
        self._budget()
        member = dict(role=role, pi=self.a.PI(), read=self.c.c_void_p(), write=self.c.c_void_p(),
                      stdin=None, assigned=False, resumed=False, signaled=False, exit_code=None,
                      data=bytearray(), eof=False, capture_stopped=False, sink=None, close_attempted=set())
        # Register the native output structures BEFORE Create*. finally reads
        # their original HANDLE fields even if Python success flags never set.
        self.actors.append(member)
        sink_path = self.directory / (role + '.combined.bin')
        member['sink_path'] = sink_path
        member['sink'] = sink_path.open('xb', buffering=0)
        security = self.a.SA(self.c.sizeof(self.a.SA), None, 1)
        okay, _error = self._call('CreatePipe', self.c.byref(member['read']), self.c.byref(member['write']),
                                   self.c.byref(security), 4096, inputs=dict(role=role, size=4096))
        self.log.add(self.name, 'original_pipe_handles', role=role, read=member['read'].value, write=member['write'].value)
        if not okay:
            raise ObservationError('create_pipe')
        okay, _error = self._call('SetHandleInformation', member['read'], 1, 0,
                                   inputs=dict(handle=member['read'].value, mask=1, flags=0))
        if not okay:
            raise ObservationError('read_handle_inherit')
        member['stdin'], _error = self._call('CreateFileW', 'NUL', 0x80000000, 3, self.c.byref(security), 3, 0x80, None,
                                             inputs=dict(name='NUL', role=role, desired_access=0x80000000))
        if not member['stdin'] or member['stdin'] == self.c.c_void_p(-1).value:
            raise ObservationError('create_NUL')
        size = self.c.c_size_t()
        okay, error = self._call('InitializeProcThreadAttributeList', None, 1, 0, self.c.byref(size), inputs=dict(sizing=True, count=1))
        self.log.add(self.name, 'attribute_buffer_required', bytes=size.value)
        if okay or error != 122 or not 1 <= size.value <= 65536:
            raise ObservationError('attribute_size')
        buffer = self.c.create_string_buffer(size.value)
        initialized = delete_attempted = False
        try:
            self.c.set_last_error(0)
            initialized = bool(self.a.InitializeProcThreadAttributeList(buffer, 1, 0, self.c.byref(size)))
            error = self.c.get_last_error()
            self.log.add(self.name, 'InitializeProcThreadAttributeList', returned=initialized, last_error=error, buffer_bytes=size.value)
            if not initialized:
                raise ObservationError('attribute_init')
            allowed = (self.c.c_void_p * 2)(member['write'].value, member['stdin'])
            okay, _error = self._call('UpdateProcThreadAttribute', buffer, 0, 0x00020002,
                                       self.c.cast(allowed, self.c.c_void_p), self.c.sizeof(allowed), None, None,
                                       inputs=dict(attribute='HANDLE_LIST', handles=[member['write'].value, member['stdin']]))
            if not okay:
                raise ObservationError('attribute_handle_list')
            startup = self.a.SIX()
            startup.StartupInfo.cb = self.c.sizeof(startup)
            startup.StartupInfo.dwFlags = 0x101  # USESTDHANDLES|USESHOWWINDOW
            startup.StartupInfo.wShowWindow = 0
            startup.StartupInfo.hStdInput = member['stdin']
            startup.StartupInfo.hStdOutput = startup.StartupInfo.hStdError = member['write'].value
            startup.lpAttributeList = self.c.cast(buffer, self.c.c_void_p)
            argv = [str(self.base), '-I', '-S', '-B', '-X', 'utf8', str(self.actor), role]
            command_line = self.c.create_unicode_buffer(' '.join('"' + item + '"' for item in argv))
            # PI is already in self.actors; do not gate cleanup on returned/created.
            self.c.set_last_error(0)
            returned = self.a.CreateProcessW(str(self.base), command_line, None, None, 1, CREATE_FLAGS,
                                              None, str(self.directory), self.c.byref(startup), self.c.byref(member['pi']))
            error = self.c.get_last_error()
            self.log.add(self.name, 'CreateProcessW', argv=argv, flags=CREATE_FLAGS, returned=returned, last_error=error,
                         process_handle=member['pi'].hProcess, thread_handle=member['pi'].hThread,
                         pid=member['pi'].dwProcessId, tid=member['pi'].dwThreadId,
                         parentage='direct child of observer; not a child of primary')
            if not returned or not member['pi'].hProcess or not member['pi'].hThread:
                raise ObservationError('create_process')
        finally:
            if initialized and not delete_attempted:
                delete_attempted = True
                self.a.DeleteProcThreadAttributeList(buffer)
                self.log.add(self.name, 'DeleteProcThreadAttributeList', returned=None, success_contract='void; returned without exception')
        okay, _error = self._call('AssignProcessToJobObject', self.job, member['pi'].hProcess,
                                   inputs=dict(job_handle=self.job, process_handle=member['pi'].hProcess,
                                               pid=member['pi'].dwProcessId, before_resume=True))
        member['assigned'] = bool(okay)
        if not okay:
            raise ObservationError('assign_before_resume_failed')
        # The child holds its restricted duplicates. Parent endpoints are
        # attempted once; failed Close remains unknown and vetoes the case.
        for key, handle in (('write', member['write'].value), ('stdin', member['stdin'])):
            member['close_attempted'].add(key)
            if not self._close(handle, role + ':' + key):
                raise ObservationError('parent_endpoint_close')
        return member

    def _resume(self, member):
        self._budget()
        if not member['assigned']:
            raise ObservationError('unassigned_resume_forbidden')
        count, _error = self._call('ResumeThread', member['pi'].hThread,
                                   inputs=dict(thread_handle=member['pi'].hThread, role=member['role']))
        member['resumed'] = count == 1
        if count != 1:
            raise ObservationError('resume_count')

    def _drain(self, member):
        if member['eof'] or member['capture_stopped'] or not member['read'].value:
            return
        # At most one tiny fixed line is lawful. Every read is <=remaining cap.
        for _index in range(3):
            available = self.c.c_uint32()
            okay, error = self._call('PeekNamedPipe', member['read'], None, 0, None, self.c.byref(available), None,
                                      inputs=dict(read_handle=member['read'].value, role=member['role']))
            self.log.add(self.name, 'pipe_available', role=member['role'], bytes=available.value)
            if not okay:
                if error == 109:
                    member['eof'] = True
                    return
                raise ObservationError('pipe_peek_failed')
            if available.value == 0:
                return
            remaining = STREAM_LIMIT - len(member['data'])
            if available.value > remaining:
                member['capture_stopped'] = True
                self.output_unknown = True
                raise ObservationError('output_cap')
            requested = min(available.value, remaining)
            buffer, count = self.c.create_string_buffer(requested), self.c.c_uint32()
            okay, _error = self._call('ReadFile', member['read'], buffer, requested, self.c.byref(count), None,
                                       inputs=dict(read_handle=member['read'].value, role=member['role'], requested=requested))
            self.log.add(self.name, 'pipe_read_count', role=member['role'], returned_bytes=count.value)
            if not okay or not 1 <= count.value <= requested:
                member['capture_stopped'] = self.output_unknown = True
                raise ObservationError('pipe_read_failed')
            raw = buffer.raw[:count.value]
            member['data'].extend(raw)
            try:
                returned = member['sink'].write(raw)
            except BaseException:
                member['capture_stopped'] = self.output_unknown = True
                raise
            self.log.add(self.name, 'raw_file_write', role=member['role'], requested=len(raw), returned=returned,
                         sha256=hashlib.sha256(raw).hexdigest())
            if type(returned) is not int or returned != len(raw):
                self.output_unknown = True
                raise ObservationError('raw_write_unknown')

    def _residual_ready(self, member):
        deadline = min(time.monotonic() + 2.0, self.work_deadline)
        for _index in range(21):
            self._budget()
            self._drain(member)
            if bytes(member['data']) == EXPECTED_LINES['owned-residual']:
                return
            if time.monotonic() >= deadline:
                break
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        raise ObservationError('residual_line_deadline')

    def _cleanup(self):
        # Cleanup never depends on created/assigned Python flags: original PI
        # HANDLEs are authoritative owned resources, even after interrupted calls.
        all_signaled, final_zero = True, False
        required_closes = {}
        try:
            if self.job:
                need_terminate = not self.result.get('primary0_to_job0_observed', False)
                if need_terminate and not self.terminate_attempted:
                    self.terminate_attempted = True
                    try:
                        returned, _error = self._call('TerminateJobObject', self.job, 0xC250,
                                                       inputs=dict(job_handle=self.job, exit_code=0xC250))
                        self.result['terminate_job_returned'] = bool(returned)
                        if not returned:
                            self.failed = True
                    except BaseException as exc:
                        self.failed = True
                        self.log.add(self.name, 'TerminateJobObject_exception', exception_type=type(exc).__name__)
            for member in self.actors:
                if not member['pi'].hProcess:
                    continue
                try:
                    state = self._wait(member, 0)
                    if state != 0:
                        # Normal assigned negative uses original Job termination.
                        # Unassigned/interrupted/failed Job cleanup may terminate
                        # only this originally returned process HANDLE, never PID.
                        if not member['assigned'] or not self.result.get('terminate_job_returned', False):
                            okay, _error = self._call('TerminateProcess', member['pi'].hProcess, 0xC251,
                                                       inputs=dict(process_handle=member['pi'].hProcess, cleanup_only=True))
                            if not okay:
                                self.failed = True
                        milliseconds = max(0, min(3000, math.floor((self.hard_deadline-time.monotonic())*1000)))
                        state = self._wait(member, milliseconds)
                    if state != 0:
                        all_signaled = False
                except BaseException as exc:
                    all_signaled, self.failed = False, True
                    self.log.add(self.name, 'original_handle_cleanup_exception', role=member['role'], exception_type=type(exc).__name__)
            if self.job:
                try:
                    final_zero = self._job_zero_by(self.hard_deadline, 'cleanup_job0')
                except BaseException as exc:
                    self.failed = True
                    self.log.add(self.name, 'cleanup_job_query_exception', exception_type=type(exc).__name__)
            for member in self.actors:
                try:
                    self._drain(member)
                except BaseException as exc:
                    self.failed = self.output_unknown = True
                    self.log.add(self.name, 'cleanup_drain_exception', role=member['role'], exception_type=type(exc).__name__)
        finally:
            for member in self.actors:
                slots = [('thread', member['pi'].hThread), ('process', member['pi'].hProcess),
                         ('write', member['write'].value), ('read', member['read'].value), ('stdin', member['stdin'])]
                for key, handle in slots:
                    if handle and handle != self.c.c_void_p(-1).value:
                        required_closes[member['role'] + ':' + key] = handle
                    if key not in member['close_attempted']:
                        member['close_attempted'].add(key)  # no retry after unknown Close
                        try:
                            self._close(handle, member['role'] + ':' + key)
                        except BaseException as exc:
                            self.failed = True
                            self.log.add(self.name, 'close_step_exception', role=member['role'], slot=key, exception_type=type(exc).__name__)
                if member['sink'] is not None:
                    try:
                        member['sink'].close()
                        self.log.add(self.name, 'raw_file_close', role=member['role'], succeeded=True)
                    except BaseException as exc:
                        self.failed = self.output_unknown = True
                        self.log.add(self.name, 'raw_file_close', role=member['role'], succeeded=False, exception_type=type(exc).__name__)
            if self.job and not self.job_close_attempted:
                required_closes['original_job'] = self.job
                self.job_close_attempted = True
                self._close(self.job, 'original_job')
        successful_closes = {row['label']: row['handle'] for row in self.close_rows if row['succeeded']}
        closed_every_created_handle = bool(required_closes) and all(successful_closes.get(label) == handle for label, handle in required_closes.items())
        self.result.update(final_job_zero=final_zero, all_original_handles_signaled=all_signaled,
                           all_closes_succeeded=closed_every_created_handle and all(row['succeeded'] for row in self.close_rows),
                           closes=self.close_rows, final_job_snapshot=self.final_snapshot,
                           peak_process_commit_bytes=self.peak_process, peak_job_commit_bytes=self.peak_job,
                           cleanup_elapsed_within_observer_budget=time.monotonic() <= self.hard_deadline)
        exact_output = not self.output_unknown and all(member['eof'] for member in self.actors)
        self.result['output'] = dict(stream_scope='combined stdout+stderr from each created actor pipe',
                                    captured_bytes=sum(len(member['data']) for member in self.actors),
                                    total_output_bytes=sum(len(member['data']) for member in self.actors) if exact_output else None,
                                    exact_total_known=exact_output,
                                    streams=[dict(role=member['role'], path=str(member['sink_path']),
                                                  bytes=len(member['data']), sha256=hashlib.sha256(member['data']).hexdigest(),
                                                  eof=member['eof'], exact_expected_line=bytes(member['data']) == EXPECTED_LINES[member['role']])
                                             for member in self.actors])
        self.result['owned_members'] = [dict(role=member['role'], pid=member['pi'].dwProcessId,
                                              process_handle=member['pi'].hProcess, thread_handle=member['pi'].hThread,
                                              assigned_before_resume=member['assigned'], resumed=member['resumed'],
                                              original_handle_signaled=member['signaled'], exit_code=member['exit_code'],
                                              parentage='direct child of observer') for member in self.actors]

    def run(self):
        gate = rejected = False
        try:
            self._budget()
            self.directory.mkdir()
            self.log.add(self.name, 'fixed_case_configuration_before_Create',
                         work_deadline_monotonic=self.work_deadline, hard_deadline_monotonic=self.hard_deadline,
                         primary_wait_seconds=5.0, residual_ready_seconds=2.0,
                         normal_exit_to_job0_seconds=1.0, negative_after_primary0_seconds=0.25,
                         cleanup_reserve_seconds=4.0, attempts=1)
            self.job, _error = self._call('CreateJobObjectW', None, None, inputs=dict(unnamed=True, inherit=False))
            if not self.job:
                raise ObservationError('create_job')
            limits = self.a.EXT()
            limits.BasicLimitInformation.LimitFlags = JOB_FLAGS
            limits.BasicLimitInformation.ActiveProcessLimit = 2
            limits.BasicLimitInformation.PerJobUserTimeLimit = 200000000
            limits.ProcessMemoryLimit, limits.JobMemoryLimit = PROCESS_LIMIT, JOB_LIMIT
            okay, _error = self._call('SetInformationJobObject', self.job, 9, self.c.byref(limits), self.c.sizeof(limits),
                                       inputs=dict(job_handle=self.job, info_class=9, flags=JOB_FLAGS,
                                                   active_limit=2, process_commit=PROCESS_LIMIT, job_commit=JOB_LIMIT, user_cpu_100ns=200000000))
            if not okay or not self._zero(self._snapshot('initial_job0')):
                raise ObservationError('job_limits_or_initial_zero')
            primary = self._spawn('primary')
            residual = self._spawn('owned-residual') if self.name == 'owned-residual' else None
            self._snapshot('all_assigned_before_resume')
            if residual is not None:
                self._resume(residual)
                self._residual_ready(residual)
            self._resume(primary)
            primary_deadline = min(time.monotonic() + 5.0, self.work_deadline)
            wait_ms = max(0, math.floor((primary_deadline-time.monotonic())*1000))
            self.log.add(self.name, 'primary_wait_deadline', absolute_monotonic=primary_deadline, requested_ms=wait_ms)
            if self._wait(primary, wait_ms) != 0 or time.monotonic() > primary_deadline or primary['exit_code'] != 0:
                raise ObservationError('primary_exit_gate')
            primary_exit_observed = time.monotonic()
            self.result['primary_exit_code'] = primary['exit_code']
            self._drain(primary)
            if residual is None:
                deadline = primary_exit_observed + 1.0
                if deadline > self.work_deadline:
                    raise ObservationError('normal_observation_budget')
                self.log.add(self.name, 'normal_gate_deadline', primary_exit_observed_monotonic=primary_exit_observed,
                             absolute_monotonic=deadline, relative_seconds=1.0)
                self.result['exit_to_job0_deadline_elapsed_ns'] = int((deadline - primary_exit_observed) * 1e9)
                gate = self._job_zero_by(deadline, 'normal_exit_to_job0')
                self.result['primary0_to_job0_observed'] = gate
                self.result['after_deadline'] = self.final_snapshot
                if not gate:
                    raise ObservationError('normal_job0_deadline')
                self.result['reason'] = 'primary0_and_original_job0'
            else:
                deadline = primary_exit_observed + 0.25
                if deadline > self.work_deadline:
                    raise ObservationError('negative_observation_budget')
                self.log.add(self.name, 'negative_gate_deadline_before_first_snapshot',
                             primary_exit_observed_monotonic=primary_exit_observed,
                             absolute_monotonic=deadline, relative_seconds=0.25,
                             work_deadline_monotonic=self.work_deadline, hard_deadline_monotonic=self.hard_deadline)
                self.result['before_deadline'] = self._snapshot('negative_before_deadline')
                if self.result['before_deadline']['sample_completed_monotonic'] > deadline:
                    raise ObservationError('negative_before_deadline_snapshot_late')
                wait_ms = max(0, math.ceil((deadline-time.monotonic())*1000))
                self.log.add(self.name, 'negative_gate_deadline_before_wait', primary_exit_observed_monotonic=primary_exit_observed,
                             absolute_monotonic=deadline, relative_seconds=0.25,
                             work_deadline_monotonic=self.work_deadline, hard_deadline_monotonic=self.hard_deadline)
                residual_wait = self._wait(residual, wait_ms)
                self.result['after_deadline'] = self._snapshot('negative_after_deadline')
                post_gate_wait = self._wait(residual, 0)
                self.result['residual_wait_at_deadline'] = residual_wait
                self.result['residual_original_handle_wait_after_gate_snapshot'] = post_gate_wait
                def original_residual_only(snapshot):
                    return (snapshot['accounting']['active'] == 1 and snapshot['pid_list']['assigned'] == 1
                            and snapshot['pid_list']['pids'] == [residual['pi'].dwProcessId])
                rejected = (residual_wait == 258 and post_gate_wait == 258 and time.monotonic() >= deadline
                            and self.result['before_deadline']['sample_completed_monotonic'] <= deadline
                            and self.result['after_deadline']['sample_started_monotonic'] >= deadline
                            and original_residual_only(self.result['before_deadline'])
                            and original_residual_only(self.result['after_deadline']))
                self.result['expected_rejection'] = rejected
                self.result['reason'] = 'owned_residual_lifecycle_success_rejected' if rejected else 'negative_oracle_not_established'
                self.result['primary0_to_job0_observed'] = False
                if not rejected:
                    self.failed = True
        except BaseException as exc:
            self.failed = True
            self.result['reason'] = str(exc) if type(exc) is ObservationError else type(exc).__name__
            self.log.add(self.name, 'case_exception', exception_type=type(exc).__name__, reason=self.result['reason'])
        finally:
            try:
                self._cleanup()
            except BaseException as exc:
                self.failed = True
                self.log.add(self.name, 'cleanup_exception', exception_type=type(exc).__name__)
        cleanup_okay = (self.result['final_job_zero'] and self.result['all_original_handles_signaled']
                        and self.result['all_closes_succeeded'] and self.result.get('cleanup_elapsed_within_observer_budget', False))
        output_okay = (self.result.get('output', {}).get('exact_total_known', False)
                       and all(item['exact_expected_line'] for item in self.result.get('output', {}).get('streams', [])))
        self.result['lifecycle_gate_passed'] = bool(gate and cleanup_okay and output_okay and not self.failed and not self.log.lost)
        self.result['control_passed'] = bool((gate if self.name == 'normal' else rejected) and cleanup_okay and output_okay and not self.failed and not self.log.lost)
        return self.result


def _owner_memory(api, log, phase):
    c = api.c
    handle = api.GetCurrentProcess()  # this process pseudo HANDLE only, never OpenProcess/PID
    counters = api.MEMORY()
    counters.cb = c.sizeof(counters)
    c.set_last_error(0)
    returned = api.K32GetProcessMemoryInfo(handle, c.byref(counters), c.sizeof(counters))
    error = c.get_last_error()
    row = dict(phase=phase, pseudo_handle=handle, returned=returned, last_error=error,
               current_private_commit_bytes=counters.PrivateUsage if returned else None,
               peak_private_commit_bytes=counters.PeakPagefileUsage if returned else None,
               scope='current observer lifetime peak committed private memory sampled now; not later serialization/driver lifetime')
    log.add('observer', 'K32GetProcessMemoryInfo', **row)
    if not returned or counters.PeakPagefileUsage <= 0 or counters.PrivateUsage <= 0:
        raise ObservationError('owner_peak_unknown')
    return row


def _pins(base_python, expected_base_sha256, expected_source_pins):
    base = _plain_path(base_python)
    if type(expected_base_sha256) is not str or re.fullmatch('[0-9a-f]{64}', expected_base_sha256) is None:
        raise ObservationError('base_pin_type')
    base_bytes, base_sha, magic = _hash_file(base, 64 * 1024 * 1024)
    if base_sha != expected_base_sha256 or magic != b'MZ' or base.suffix.lower() != '.exe':
        raise ObservationError('base_PE_pin')
    names = {'owned_lifecycle.py', 'case_actor.py', 'README.md', 'run_once.py'}
    if type(expected_source_pins) is not dict or expected_source_pins.keys() != names:
        raise ObservationError('source_pin_fields')
    package = _plain_path(Path(__file__)).parent
    sources, total = {}, 0
    for name in sorted(names):
        pin = expected_source_pins[name]
        if (type(pin) is not dict or pin.keys() != {'bytes', 'sha256'} or type(pin['bytes']) is not int
                or not 1 <= pin['bytes'] <= 262144 or type(pin['sha256']) is not str
                or re.fullmatch('[0-9a-f]{64}', pin['sha256']) is None):
            raise ObservationError('source_pin_shape')
        path = _plain_path(package / name)
        count, sha, _magic = _hash_file(path, 262144)
        total += count
        if count != pin['bytes'] or sha != pin['sha256'] or total > 262144:
            raise ObservationError('source_pin_mismatch')
        sources[name] = dict(bytes=count, sha256=sha)
    return base, package / 'case_actor.py', dict(base_path=str(base), base_bytes=base_bytes,
                                               base_sha256=base_sha, sources=sources)


def run_batch(*, base_python: Path, expected_base_sha256: str, output: Path, expected_source_pins: dict) -> dict:
    """Root-only single invocation: two new cases, at most one attempt each."""
    global _USED
    started_ns, started = time.monotonic_ns(), time.monotonic()
    log = _Events(started_ns)
    result = dict(schema_version=1, operation_id='C-DEEPEYE-OWNED-LIFECYCLE-EVIDENCE-20261029-25',
                  all_cases_passed=False, status='blocked', cases=[],
                  budgets=dict(observer_wall_seconds=24, outer_wall_seconds=30, cleanup_reserve_seconds=4,
                               actor_process_commit_bytes=PROCESS_LIMIT, actor_job_commit_bytes=JOB_LIMIT,
                               actor_job_active_process_limit=2, actor_job_user_cpu_seconds=20,
                               combined_output_limit_bytes=OUTPUT_LIMIT, stream_capture_limit_bytes=STREAM_LIMIT,
                               owner_JSON_limit_bytes=OWNER_JSON_LIMIT, event_limit=MAX_EVENTS),
                  cleanup=dict(all_cases_final_job_zero=False, all_original_handles_signaled=False,
                               all_closes_succeeded=False, stopped_before_next_case=False),
                  evidence=dict(events=log.rows, source_pins=None, owner_memory_samples=[], actual_output_bytes=None,
                                output_exact_known=False, max_actor_job_peak_commit_bytes=None,
                                owner_peak_commit_bytes=None, conservative_sum_peak_bytes=None,
                                memory_scope='actor Job peaks plus current observer PSAPI sample; observer not governed by child Job limits'),
                  C24_validation_upgraded=False, formal_acceptance='not_run')
    try:
        if _USED:
            raise ObservationError('invocation_already_consumed')
        _USED = True
        if os.name != 'nt':
            raise ObservationError('Windows_required')
        base, actor, pins = _pins(base_python, expected_base_sha256, expected_source_pins)
        result['evidence']['source_pins'] = pins
        output = _plain_path(output)
        if not output.is_dir() or next(output.iterdir(), None) is not None:
            raise ObservationError('output_must_be_existing_empty_directory')
        hard_deadline = started + OBSERVER_SECONDS
        work_deadline = hard_deadline - CLEANUP_RESERVE_SECONDS
        if time.monotonic() >= work_deadline:
            raise ObservationError('preflight_deadline')
        api = _API()
        log.add('observer', 'ABI_sizes', sizes=api.sizes)
        initial_memory = _owner_memory(api, log, 'before_cases')
        result['evidence']['owner_memory_samples'].append(initial_memory)
        if initial_memory['peak_private_commit_bytes'] > PROCESS_LIMIT:
            raise ObservationError('owner_process_commit_gate')
        previous_clean = True
        for name in ('normal', 'owned-residual'):
            if not previous_clean or time.monotonic() >= work_deadline:
                break
            case = _Case(api, log, name, output / name, base, actor, work_deadline, hard_deadline)
            outcome = case.run()
            result['cases'].append(outcome)
            previous_clean = (outcome['control_passed'] and outcome['final_job_zero']
                              and outcome['all_original_handles_signaled'] and outcome['all_closes_succeeded'])
            owner_memory = _owner_memory(api, log, 'after_' + name + '_cleanup_and_Close')
            result['evidence']['owner_memory_samples'].append(owner_memory)
            max_job = max(item.get('peak_job_commit_bytes', 0) for item in result['cases'])
            if owner_memory['peak_private_commit_bytes'] > PROCESS_LIMIT or max_job + owner_memory['peak_private_commit_bytes'] > JOB_LIMIT:
                previous_clean = False
                result['status'] = 'resource_gate_failed'
                break
        if len(result['cases']) < 2:
            result['cases'].append(dict(name='owned-residual', attempted=False, lifecycle_gate_passed=False,
                                        expected_rejection=False, control_passed=False, reason='prior_gate_or_budget_blocked'))
        cases = result['cases']
        completed = len(cases) == 2 and all(item.get('attempted') for item in cases)
        result['cleanup'] = dict(all_cases_final_job_zero=completed and all(item.get('final_job_zero', False) for item in cases),
                                 all_original_handles_signaled=completed and all(item.get('all_original_handles_signaled', False) for item in cases),
                                 all_closes_succeeded=completed and all(item.get('all_closes_succeeded', False) for item in cases),
                                 stopped_before_next_case=completed and all(cases[0].get(key, False) for key in ('final_job_zero', 'all_original_handles_signaled', 'all_closes_succeeded')))
        exact = completed and all(item.get('output', {}).get('exact_total_known', False) for item in cases)
        result['evidence']['output_exact_known'] = exact
        result['evidence']['actual_output_bytes'] = sum(item['output']['total_output_bytes'] for item in cases) if exact else None
        result['evidence']['max_actor_job_peak_commit_bytes'] = max((item.get('peak_job_commit_bytes', 0) for item in cases), default=0)
        # Materialize the bounded report before the last owner-memory sample.
        _json(result)
        final_memory = _owner_memory(api, log, 'after_cases_and_initial_report_materialization')
        result['evidence']['owner_memory_samples'].append(final_memory)
        owner_peak = max(item['peak_private_commit_bytes'] for item in result['evidence']['owner_memory_samples'])
        result['evidence']['owner_peak_commit_bytes'] = owner_peak
        result['evidence']['conservative_sum_peak_bytes'] = owner_peak + result['evidence']['max_actor_job_peak_commit_bytes']
        memory_okay = owner_peak <= PROCESS_LIMIT and result['evidence']['conservative_sum_peak_bytes'] <= JOB_LIMIT
        result['evidence']['owner_peak_within_process_limit'] = owner_peak <= PROCESS_LIMIT
        result['evidence']['conservative_peak_sum_within_job_limit'] = result['evidence']['conservative_sum_peak_bytes'] <= JOB_LIMIT
        result['all_cases_passed'] = bool(completed and all(item['control_passed'] for item in cases)
                                          and all(result['cleanup'].values()) and memory_okay and exact
                                          and result['evidence']['actual_output_bytes'] <= OUTPUT_LIMIT
                                          and not log.lost and time.monotonic() <= hard_deadline)
        result['status'] = 'control_passed' if result['all_cases_passed'] else 'control_failed'
    except BaseException as exc:
        result['all_cases_passed'] = False
        result['status'] = 'blocked_or_failed'
        result['reason'] = str(exc) if type(exc) is ObservationError else type(exc).__name__
        log.add('observer', 'batch_exception', exception_type=type(exc).__name__, reason=result['reason'])
    result['evidence']['event_loss_or_overflow'] = log.lost
    result['evidence']['events_recorded'] = len(log.rows)
    result['evidence']['observer_elapsed_ns'] = time.monotonic_ns()-started_ns
    if result['evidence']['observer_elapsed_ns'] > 24000000000 or log.lost:
        result['all_cases_passed'] = False
        result['status'] = 'observer_budget_or_evidence_failed'
    encoded = _json(result)
    if len(encoded) + 1 > OWNER_JSON_LIMIT:
        # Do not return an over-budget payload or silently certify lost proof.
        return dict(schema_version=1, all_cases_passed=False, status='owner_JSON_bound_failed',
                    cases=[dict(name=item.get('name'), lifecycle_gate_passed=False,
                                expected_rejection=item.get('expected_rejection', False), control_passed=False)
                           for item in result['cases']], cleanup=result['cleanup'],
                    budgets=result['budgets'], evidence=dict(original_JSON_bytes=len(encoded), events_lost=True),
                    C24_validation_upgraded=False, formal_acceptance='not_run')
    result['evidence']['observer_elapsed_ns'] = time.monotonic_ns()-started_ns
    if result['evidence']['observer_elapsed_ns'] > 24000000000:
        result['all_cases_passed'] = False
        result['status'] = 'observer_budget_or_evidence_failed'
    return result

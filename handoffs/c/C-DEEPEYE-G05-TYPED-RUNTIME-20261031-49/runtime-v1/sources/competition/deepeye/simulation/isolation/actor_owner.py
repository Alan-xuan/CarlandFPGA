"""Retained, single-authority-thread actor acquisition; no Run registration.

Only the trusted composition root may construct a registry or supply policy and
verified BOOT. Python privacy/types are not an OS security boundary. Test seams
are module-internal; production always selects the existing native backend and
legacy clock or exact fresh-run QPC binding. A record, PID or serialized receipt
cannot adopt a process.
"""
from dataclasses import asdict, dataclass
from functools import wraps
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import threading
from time import monotonic_ns
import uuid

from .owned_resources import OwnedResources, error_info
from .policy import create_run_directory, minimal_environment
from .resource_cleanup import Provenance
from .windows_cleanup import WindowsCleanupBackend
from ...integration import host_clock as clocks

CONTRACT = 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
_FACTORY = object()


def _native_api():
    from . import win32
    return win32


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('strict nonnegative integer required')
    return value


def _relative(value):
    if type(value) is not str or not value or '\\' in value or ':' in value:
        raise ValueError('simple relative stage path required')
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(
            part in ('', '.', '..') or part[-1:] in (' ', '.') or
            any(c in part for c in '<>"|?*\0') or
            part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}
            for part in path.parts):
        raise ValueError('unsafe stage path')
    return path


def _no_alias(path):
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()) or getattr(part.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('stage aliases/reparse points forbidden')


@dataclass(frozen=True)
class ActorPolicy:
    """Explicit trusted launch inputs, not controller data or authentication."""
    run_id: str
    evidence_parent: Path
    source_root: Path
    files: tuple[tuple[str, str], ...]
    executable: str
    arguments: tuple[str, ...]
    system_root: str
    local_appdata: str
    max_stage_bytes: int
    output_limit: int
    readiness_timeout_ns: int
    lifetime_timeout_ns: int
    sample_age_cap_ns: int
    max_probe_ns: int

    def _validate(self):
        if any(type(v) is not str or not v or '\0' in v for v in
               (self.run_id, self.system_root, self.local_appdata)):
            raise ValueError('explicit trusted identity/environment required')
        for name in ('max_stage_bytes', 'output_limit', 'readiness_timeout_ns',
                     'lifetime_timeout_ns', 'sample_age_cap_ns', 'max_probe_ns'):
            _integer(getattr(self, name), 1)
        if self.output_limit > 8192 or self.max_stage_bytes > 268435456:
            raise ValueError('stage/output budget exceeds retained launcher limit')
        if not self.max_probe_ns < self.sample_age_cap_ns <= self.lifetime_timeout_ns:
            raise ValueError('ordered explicit probe/sample/lifetime budgets required')
        if self.readiness_timeout_ns > self.lifetime_timeout_ns:
            raise ValueError('readiness must fit fixed lifetime')
        if type(self.files) is not tuple or not self.files:
            raise ValueError('nonempty immutable staged file manifest required')
        names = set()
        for pair in self.files:
            if type(pair) is not tuple or len(pair) != 2:
                raise ValueError('immutable file/hash pair required')
            name, digest = pair
            _relative(name)
            if type(digest) is not str or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('exact lowercase SHA256 required')
            if name.casefold() in names: raise ValueError('duplicate case-insensitive stage path')
            names.add(name.casefold())
        _relative(self.executable)
        if self.executable not in dict(self.files): raise ValueError('executable must be explicitly manifested')
        if type(self.arguments) is not tuple or len(self.arguments) > 128 or any(
                type(x) is not str or '\0' in x for x in self.arguments):
            raise ValueError('bounded immutable arguments required')
        if sum(len(x) for x in self.arguments) > 16384: raise ValueError('argument budget exceeded')
        for path in (self.evidence_parent, self.source_root):
            if not isinstance(path, Path) or not path.is_absolute() or not path.is_dir():
                raise ValueError('existing absolute trusted parent/source required')
            _no_alias(path)


def _persist(owner):
    """Private ACL-contained receipt. Never expose this to the controller."""
    if owner._root is None or not owner._acl_ready:
        raise RuntimeError('private evidence ACL not established')
    document = dict(schema=1, instance_id=owner.instance_id, state=owner.state,
        requirements_sha256=CONTRACT, resources=owner._resources.summary(),
        provenance=asdict(owner._resources.provenance),
        primary_error=None if owner._primary_error is None else asdict(error_info('primary', owner._primary_error)),
        callback_errors=[asdict(error_info('revocation', e)) for e in owner._callback_errors],
        evidence_errors=[asdict(error_info('evidence', e)) for e in owner._evidence_errors],
        owner_errors=[asdict(e) for e in owner._resources.errors],
        cleanup=None if owner._cleanup_result is None else dict(
            resources_complete=owner._cleanup_result.resources_complete,
            evidence_complete=owner._cleanup_result.evidence_complete,
            success=owner._cleanup_result.success,
            cleanup_errors=[asdict(e) for e in owner._cleanup_result.cleanup_errors]),
        evidence_complete=not owner._evidence_errors, cleanup_attempted=owner._cleanup_attempted,
        overlapped=None if owner._pending_io is None else dict(
            process_acquisition=owner._pending_io.process_state,
            stop_claim=asdict(owner._pending_io.stop_claim),
            operations=[op.diagnostic() for op in owner._pending_io.operations],
            errors=[type(error).__name__ for error in owner._pending_io.errors],
            native_acquisitions_registered=owner._pending_io.acquisitions_registered,
            process_pair_registered=owner._pending_io.process_pair_registered,
            private_acquisitions=owner._pending_io.private_acquisition_diagnostics(),
            invocation=None if owner._invocation is None else owner._invocation.snapshot()))
    if owner._invocation_series is not None:
        document['serial_invocations']=owner._invocation_series.summary()
    temporary = owner._root / ('receipt.' + uuid.uuid4().hex + '.pending')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    temporary.replace(owner._root / 'receipt.json')


def _entry(method):
    @wraps(method)
    def call(self, /, *args, **kwargs):
        if type(self) is not ActorOwner:
            raise ValueError('original registry owner required')
        if threading.get_ident() != self._thread:
            self._foreign_call.set()
            raise ValueError('authority owner thread required')
        if not self._registry._contains(self):
            self._revoke('owner detached from acquisition registry')
            raise ValueError('original registry ownership lost')
        if self._busy:
            self._revoke('reentrant actor entry')
            raise ValueError('reentrant actor entry')
        self._busy = True
        try:
            if self._foreign_call.is_set() and method.__name__ not in ('close', 'poll_teardown', 'invocation_snapshot'):
                raise ValueError('foreign-thread entry pending')
            return method(self, *args, **kwargs)
        except BaseException as error:
            if self._primary_error is None: self._primary_error = error
            self._revoke('actor entry rejected')
            if self._pending_io is not None and method.__name__ != '_launch':
                try: self._close_internal('overlapped actor entry rejected')
                except BaseException as cleanup_error: self._cleanup_error = cleanup_error
            if isinstance(error, TypeError) and error.__traceback__.tb_next is None:
                raise ValueError('invalid actor call or dependency result') from error
            raise
        finally:
            self._busy = False
    return call


class ActorRegistry:
    """Trusted same-thread composition root; retains live and quarantine owners."""
    def __init__(self, *, host_clock=None):
        binding = clocks._require_binding(host_clock)
        self._clock_binding = binding
        self._api, self._clock = _native_api(), monotonic_ns if binding is None else binding
        self._thread = threading.get_ident()
        self._owners, self._used_sessions, self._generations = [], set(), {}
        self._namespace = uuid.uuid4().hex
        self._ordinal, self._high, self._launching = 0, 0, None

    def _contains(self, owner): return any(item is owner for item in self._owners)

    def launch(self, /, *args, **kwargs):
        if threading.get_ident() != self._thread:
            for owner in self._owners: owner._foreign_call.set()
            raise ValueError('authority owner thread required')
        if self._launching is not None:
            self._launching._revoke('reentrant launch')
            raise ValueError('reentrant registry launch')
        if len(args) != 1 or kwargs or type(args[0]) is not ActorPolicy:
            raise ValueError('one explicit trusted ActorPolicy required; adoption forbidden')
        policy = args[0]; policy._validate()
        self._ordinal += 1
        actor = ActorOwner(_FACTORY, self, policy, self._ordinal)
        self._owners.append(actor)  # Strong ownership before clock, disk or native acquisition.
        self._launching = actor
        try:
            actor._launch()
            return actor
        finally:
            self._launching = None


    def launch_overlapped(self, /, *args, **kwargs):
        """Fresh trusted-root acquisition, never an upgrade/adoption of an actor."""
        if threading.get_ident() != self._thread:
            for owner in self._owners: owner._foreign_call.set()
            raise ValueError('authority owner thread required')
        if self._launching is not None:
            self._launching._revoke('reentrant launch')
            raise ValueError('reentrant registry launch')
        if len(args) != 1 or kwargs or type(args[0]) is not ActorPolicy:
            raise ValueError('one original policy required; adoption forbidden')
        policy = args[0]; policy._validate()
        self._ordinal += 1
        actor = ActorOwner(_FACTORY, self, policy, self._ordinal)
        self._owners.append(actor)
        from .actor_pipe_io import _new
        actor._pending_io = _new(actor)
        actor._resources._pending_io = actor._pending_io
        self._launching = actor
        try:
            actor._launch()
            return actor
        finally:
            self._launching = None


class ActorOwner:
    """Factory-acquired actor; no public process-adoption constructor.

    bind_verified_boot is a trusted composition operation, not a verifier. The
    caller must already authenticate original readiness/BOOT/channel evidence.
    """
    def __init__(self, key, registry=None, policy=None, ordinal=None):
        if key is not _FACTORY or type(registry) is not ActorRegistry:
            raise ValueError('only registry acquisition creates an actor owner')
        self._registry, self._policy, self._thread = registry, policy, registry._thread
        self._instance = registry._namespace + ':' + str(ordinal)
        provenance = Provenance('DEEPEYE-IMPLEMENTATION-20261014/v1', self._instance, self._instance,
            (('requirements', CONTRACT),) + tuple(('stage:' + p, h) for p, h in policy.files))
        self._resources = OwnedResources(provenance)
        self._backend = WindowsCleanupBackend(registry._api, self._resources)
        self._api = registry._api
        self._state, self._epoch, self._busy = 'ALLOCATING', 0, False
        self._foreign_call = threading.Event()
        self._process = self._original_process = self._original_native = None
        self._root = self._stage = None
        self._acl_ready = False
        self._boot = self._stop = self._revoke_motion = None
        self._runtime_owner = self._executor_owner = None
        self._runtime_activation = self._executor_activation = None
        self._primary_error = self._cleanup_error = self._cleanup_result = None
        self._evidence_errors, self._callback_errors = [], []
        self._cleanup_attempted = False
        self._revoking = False
        self._pending_io = self._invocation = None
        self._invocation_claimed = False
        self._invocation_series = None  # Explicit opt-in; legacy invocation remains once-only.
        self._model_ready_reference = self._model_ready_native = None
        self._model_ready_launch_readback = None

    @property
    def instance_id(self): return self._instance

    @property
    def state(self): return self._state

    def _checkpoint(self, epoch=None):
        if self._foreign_call.is_set() or self._state in ('REVOKED', 'DRAINING', 'CLOSED', 'QUARANTINED'):
            raise ValueError('actor ownership retired')
        if epoch is not None and epoch != self._epoch: raise ValueError('actor epoch changed')

    def _time(self):
        epoch = self._epoch
        now = _integer(self._registry._clock())
        self._checkpoint(epoch)
        if now < self._registry._high: raise ValueError('monotonic clock regressed')
        self._registry._high = now
        return now

    def _report(self):
        try: _persist(self)
        except BaseException as error:
            self._evidence_errors.append(error)
            raise

    def _revoke(self, reason):
        # Retire first; neither callback failure nor caught reentry restores it.
        if self._state not in ('CLOSED', 'QUARANTINED', 'DRAINING'): self._state = 'REVOKED'
        self._epoch += 1
        if self._revoking: return
        self._revoking = True
        try:
            try:
                # Each exact activation is checked at its own dispatch boundary.
                # The first callback may advance the other authority meanwhile.
                if (self._stop is not None and self._runtime_owner is not None and
                        self._runtime_owner._boot is self._runtime_activation):
                    self._stop(reason)
            except BaseException as error:
                self._callback_errors.append(error)
            finally:
                try:
                    if (self._revoke_motion is not None and self._executor_owner is not None and
                            self._executor_owner._root.boot is self._executor_activation):
                        self._revoke_motion(reason)
                except BaseException as error:
                    self._callback_errors.append(error)
        finally:
            self._revoking = False

    def _stage_files(self):
        # Only immutable file preparation is parallel. No native actor API,
        # owner ledger, control IO or model call is reachable in a worker.
        from concurrent.futures import ThreadPoolExecutor
        total = 0
        checked_dirs = set()
        tasks = []
        def guard(part):
            if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()) or getattr(part.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('stage aliases/reparse points forbidden')
        for name, expected in self._policy.files:
            source = self._policy.source_root / name
            guard(source)
            for directory in source.parents:
                if directory not in checked_dirs:
                    guard(directory)
                    checked_dirs.add(directory)
            info = source.stat()
            if not source.is_file() or info.st_nlink != 1: raise ValueError('ordinary single-link source required')
            total += info.st_size
            if total > self._policy.max_stage_bytes: raise ValueError('approved stage size budget exceeded')
            tasks.append((source, self._stage / name, info.st_size, expected))
        def copy_file(item):
            source, target, size, expected = item
            guard(source)
            with source.open('rb') as stream:
                before = os.fstat(stream.fileno())
                raw = stream.read(size + 1)
                after = os.fstat(stream.fileno())
            def identity(info):
                return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_nlink,info.st_mode)
            if before.st_size != size or before.st_nlink != 1 or identity(before) != identity(after) or len(raw) != size or hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('approved stage hash or original fd identity mismatch')
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                if stream.write(raw) != len(raw): raise ValueError('short private stage write')
            return size
        pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix='DeepEyeStage')
        futures = []
        try:
            futures = [pool.submit(copy_file, item) for item in tasks]
            copied = 0
            for future in futures:
                copied += future.result()
                self._checkpoint()  # Authority thread only.
            if copied != total: raise ValueError('private stage total mismatch')
        except BaseException:
            for future in futures: future.cancel()
            raise
        finally:
            # Every worker is joined before return or original-owner cleanup.
            pool.shutdown(wait=True, cancel_futures=True)
        for directory in checked_dirs: guard(directory)

    @_entry
    def _launch(self):
        try:
            from .actor_lifetime import _sample
            start = self._time()
            self._run_deadline = start + self._policy.lifetime_timeout_ns
            self._ready_deadline = start + self._policy.readiness_timeout_ns
            self._root = create_run_directory(self._policy.evidence_parent, 'actor-' + uuid.uuid4().hex)
            user = self._api.user_sid(owner=self._resources); self._checkpoint()
            self._api.set_new_object_acl(self._root, self._root, user, owner=self._resources)
            self._checkpoint(); self._acl_ready = True; self._report()
            profile = self._api.create_profile('DeepEye.Actor.' + uuid.uuid4().hex, owner=self._resources)
            self._checkpoint()
            sid = self._api.sid_text(profile, owner=self._resources); self._checkpoint()
            path = self._api.profile_path(sid, owner=self._resources)
            self._resources.set_profile_path(path); self._checkpoint()
            self._stage = self._root / 'r'; self._stage.mkdir()
            self._api.set_new_object_acl(self._stage, self._root, user, sid, owner=self._resources)
            self._checkpoint(); self._stage_files()
            if self._pending_io is None:
                inp, write = self._api.pipe(owner=self._resources, read_label='input_read', write_label='input_write')
                self._checkpoint()
                read, out = self._api.pipe(owner=self._resources, read_label='output_read', write_label='output_write')
            else:
                inp, write, read, out = self._pending_io.acquire()
            self._checkpoint()
            for handle in (write, read):
                self._api.check(self._api.SetHandleInformation(handle, 1, 0), 'parent endpoint flags')
                self._checkpoint()
            flags = tuple(self._api.handle_flags(h) for h in (inp, out, write, read))
            self._checkpoint()
            if any(type(value) is not int for value in flags) or flags != (1, 1, 0, 0):
                raise ValueError('endpoint inheritance readback rejected')
            self._checkpoint()
            job = self._api.create_job(owner=self._resources); self._checkpoint()
            environment = minimal_environment(path / 'Temp', self._policy.system_root, self._policy.local_appdata)
            # NEW fixed NumPy policy before child interpreter/BLAS import.
            environment.update({name: '1' for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')})
            # NEW: single inherited readiness event; not wire data or BOOT.
            model_ready = self._api.model_ready_event(owner=self._resources)
            self._model_ready_reference = self._resources.find('model_ready')
            self._model_ready_native = model_ready
            ready_flags = self._api.handle_flags(model_ready)
            ready_wait = self._api.Wait(model_ready, 0)
            self._model_ready_launch_readback = dict(original_event_native=model_ready, initial_flags=ready_flags, initial_wait=ready_wait)
            if type(ready_flags) is not int or ready_flags != 1 or type(ready_wait) is not int or ready_wait != 258:
                raise ValueError('fresh inheritable nonsignaled model-ready event required')
            args = (*self._policy.arguments, str(model_ready), str(inp), str(out))
            pi = self._api.create_suspended(self._stage / self._policy.executable, args, self._stage,
                environment, profile, inp, out, owner=self._resources)
            self._api.check(self._api.SetHandleInformation(model_ready, 1, 0), 'parent model-ready inheritance off')
            ready_parent_flags = self._api.handle_flags(model_ready)
            self._model_ready_launch_readback['parent_flags_after_creation'] = ready_parent_flags
            if type(ready_parent_flags) is not int or ready_parent_flags != 0:
                raise ValueError('parent original model-ready event must be noninheritable')
            self._process = self._original_process = self._resources.find('process')
            self._original_native = self._process.native
            if self._pending_io is not None:
                if self._pending_io.resolve_process() is not self._process:
                    raise ValueError('original overlapped process acquisition not retained')
            self._state = 'SUSPENDED' if self._state == 'ALLOCATING' else self._state
            self._checkpoint()
            self._api.check(self._api.AssignJob(job, self._process.native), 'AssignProcessToJobObject')
            self._checkpoint()
            inspected = self._api.inspect_process(self._process.native, job, sid, owner=self._resources)
            self._checkpoint()
            required = ('is_appcontainer', 'sid_matches', 'win32k_disabled',
                        'child_process_restricted', 'in_job', 'job_limits_match')
            if any(inspected.get(key) is not True for key in required) or type(inspected.get('capability_count')) is not int or inspected['capability_count'] != 0:
                raise ValueError('suspended process policy inspection rejected')
            self._creation_filetime = _integer(inspected['creation_filetime'], 1)
            for label in ('input_read', 'output_write'):
                self._resources.release_checked(self._resources.find(label)); self._checkpoint()
            self._report(); self._checkpoint()
            if self._time() >= self._ready_deadline: raise ValueError('readiness deadline expired before resume')
            previous = self._api.ResumeThread(pi.hThread)
            self._checkpoint()
            if type(previous) is not int or previous != 1: raise ValueError('resume count rejected')
            self._state = 'RUNNING_UNBOUND'
            _sample(self)
            self._report(); self._checkpoint()
            _sample(self)  # Reporting cannot rejuvenate readiness or stale life.
        except BaseException as error:
            self._primary_error = error
            self._close_internal('launch failed')
            raise

    @_entry
    def bind_verified_boot(self, boot, *, runtime, executor):
        from ..authority.pc_direct_runtime import BootBinding, PcDirectRuntime, _is_binding
        from ..authority.motion_executor import OwnedMotionExecutor
        from ...integration import host_envelope as envelope, pc_direct_watchdog as watchdog
        from .actor_lifetime import _sample
        if self._state != 'RUNNING_UNBOUND': raise ValueError('actor activation is single use')
        if (not _is_binding(boot, executor=executor) or boot.run_id != self._policy.run_id or
                boot.ai_instance != self.instance_id or type(boot.context_json) is not bytes):
            raise ValueError('exact factory instance/run required')
        generation = _integer(boot.generation, 1)
        context = watchdog._context_copy(envelope._parse_message(boot.context_json))
        key = (boot.run_id, context['session'])
        if generation <= self._registry._generations.get(boot.run_id, 0) or key in self._registry._used_sessions:
            raise ValueError('retired BOOT/session')
        # Consume identity before subsequent clock/probe work can fail.
        self._registry._generations[boot.run_id] = generation
        self._registry._used_sessions.add(key)
        if type(runtime) is not PcDirectRuntime or type(executor) is not OwnedMotionExecutor:
            raise ValueError('original typed authority objects required')
        self._boot, self._stop, self._revoke_motion = boot, runtime.stop, executor.revoke
        self._runtime_owner, self._executor_owner = runtime, executor
        # A partial pair can still contain two different original activations.
        # Retain each separately; never let a delayed owner stop its successor.
        self._runtime_activation = runtime._boot
        self._executor_activation = executor._root.boot
        if runtime._boot is not boot or executor.authority_snapshot().boot is not boot:
            raise ValueError('already activated exact authority objects required')
        _sample(self)  # Still unbound: enforces fixed readiness deadline too.
        self._state = 'BOUND_ACTIVE'

    @_entry
    def ai_lease(self, boot, now_ns):
        from .actor_lifetime import _observe
        return _observe(self, boot, now_ns)

    @_entry
    def poll(self):
        from .actor_lifetime import _sample
        _sample(self)

    def _close_internal(self, reason):
        if self._pending_io is not None:
            return self._close_overlapped(reason)
        self._revoke(reason)
        if self._cleanup_attempted: return self._cleanup_result
        self._cleanup_attempted = True
        self._state = 'DRAINING'
        try:
            reader = next((ref for ref in self._resources.references if ref.label == 'output_read'), None)
            if reader is not None and not reader.attempted:
                try:
                    # Helper reads at most 8192; output_limit is post-read only.
                    output = self._api.available_output(reader.native)
                    if type(output) is not bytes or len(output) > self._policy.output_limit:
                        raise ValueError('bounded diagnostic output rejected')
                    # No raw child output is exported or treated as trusted evidence.
                except BaseException as error: self._evidence_errors.append(error)
            self._cleanup_result = self._resources.cleanup(self._backend, lambda event: self._report(), self._primary_error)
        except BaseException as error:
            self._cleanup_error = error
        complete = (self._cleanup_result is not None and self._cleanup_result.resources_complete and
            self._cleanup_result.evidence_complete and not self._resources.errors and
            not self._evidence_errors and not self._callback_errors and self._cleanup_error is None)
        self._state = 'CLOSED' if complete else 'QUARANTINED'
        try: self._report()
        except BaseException: self._state = 'QUARANTINED'
        return self._cleanup_result

    @_entry
    def close(self, reason):
        if type(reason) is not str or not reason: raise ValueError('explicit teardown reason required')
        return self._close_internal(reason)

    def _close_overlapped(self, reason):
        io = self._pending_io
        if io.cleanup_consumed or io.quarantined: return self._cleanup_result
        if not io.teardown_started:
            self._revoke(reason)
            self._cleanup_attempted = True  # Admission/life veto, not generic cleanup consumption.
        self._state = 'DRAINING'
        try:
            io.teardown()
        except BaseException as error:
            self._cleanup_error = error
            io.quarantined = True
        if io.cleanup_consumed:
            complete = (self._cleanup_result is not None and self._cleanup_result.resources_complete and
                self._cleanup_result.evidence_complete and not self._resources.errors and
                not self._evidence_errors and not self._callback_errors and not io.errors and
                self._cleanup_error is None)
            self._state = 'CLOSED' if complete else 'QUARANTINED'
        elif io.quarantined:
            self._state = 'QUARANTINED'
        try: self._report()
        except BaseException:
            self._state = 'QUARANTINED'
            io.quarantined = True
        return self._cleanup_result

    def _invocation_check(self):
        from .actor_lifetime import _sample
        self._checkpoint()
        if self._invocation_series is not None:
            from .actor_invocation_series import _OriginalSerialSeries
            if type(self._invocation_series) is not _OriginalSerialSeries or self._invocation_series.owner is not self:
                raise ValueError('exact original serial owner association required')
        if self._pending_io is None or self._state not in ('RUNNING_UNBOUND', 'BOUND_ACTIVE'):
            raise ValueError('original fresh overlapped actor required')
        self._pending_io.continuity()
        if self._invocation is not None and self._invocation._failed:
            raise ValueError('original invocation retired')
        _sample(self)
        now = self._time()
        if self._invocation is not None and now >= self._invocation.deadline:
            raise ValueError('original invocation deadline expired')
        return now

    @_entry
    def begin_serial_invocations(self, limits):
        """Choose finite same-owner framing policy before its first request."""
        from .actor_invocation_series import _new_original_series
        self._invocation_check()
        self._invocation_series=_new_original_series(self,limits)
        self._invocation_series._check()
        self._report()

    def _prepare_raw_invocation(self, identity, *, request_raw, journal_name,
                                max_output_bytes, max_reads, read_size, io_deadline_ns):
        from ...integration.cpu_invocation_transcript import _new_actor_record
        options=dict(request_raw=request_raw,journal_name=journal_name,
            max_output_bytes=max_output_bytes,max_reads=max_reads,read_size=read_size,
            io_deadline_ns=io_deadline_ns)
        series=self._invocation_series
        ticket=None if series is None else series.reserve(identity,**options)
        self._invocation=_new_actor_record(self,identity,**options)
        if series is not None:series.retain(ticket,self._invocation)
        self._invocation_check()
        self._invocation.prepare()
        self._invocation_check()

    @_entry
    def prepare_invocation(self, identity, *, request_raw, journal_name,
                           max_output_bytes, max_reads, read_size, io_deadline_ns):
        if self._invocation_claimed: raise ValueError('original invocation slot consumed')
        self._invocation_claimed = True  # Before clock, validation, journal or native event.
        self._invocation_check()
        self._prepare_raw_invocation(identity, request_raw=request_raw,
            journal_name=journal_name, max_output_bytes=max_output_bytes, max_reads=max_reads,
            read_size=read_size, io_deadline_ns=io_deadline_ns)

    @_entry
    def prepare_next_invocation(self, identity, *, request_raw, journal_name,
                                max_output_bytes, max_reads, read_size, io_deadline_ns):
        """New ticket after an observed raw frame; never resets legacy claims."""
        if self._invocation_series is None or not self._invocation_claimed:
            raise ValueError('explicit original serial policy and first invocation required')
        self._invocation_check()
        self._prepare_raw_invocation(identity,request_raw=request_raw,journal_name=journal_name,
            max_output_bytes=max_output_bytes,max_reads=max_reads,read_size=read_size,
            io_deadline_ns=io_deadline_ns)

    @_entry
    def seal_serial_invocation_frame(self):
        """Observe one original frame; does not verify semantic AI completion."""
        if self._invocation_series is None:
            raise ValueError('explicit original serial framing policy required')
        self._invocation_check()
        return self._invocation_series.seal_current()

    @_entry
    def seal_serial_invocation_response_pair(self):
        """Observe an original two-frame raw response, not an AI completion."""
        if self._invocation_series is None:
            raise ValueError('explicit original serial framing policy required')
        self._invocation_check()
        return self._invocation_series.seal_current('ready_result_frames_v1')

    def _require_invocation(self):
        if self._invocation is None: raise ValueError('original prepared invocation required')
        return self._invocation

    @_entry
    def dispatch_invocation_once(self):
        record = self._require_invocation()
        if self._invocation_series is None:
            if self._pending_io.write_reserved: raise ValueError('original write reserved; no replay')
        else:
            self._invocation_series.claim_write(record)
        self._pending_io.write_reserved = True
        row = record.start_dispatch()
        row['started_marker_ns'] = self._invocation_check()
        record._append(row)  # fsync before the sole original request WriteFile.
        op = self._pending_io.operation(self._pending_io.endpoints['input_write'][0],
                                        'write', len(record.request), record.request)
        op.row = row
        op.record = record
        row['raw_call_bracket_ns'][0] = self._invocation_check()
        try:
            self._pending_io.issue(op)
        finally:
            self._pending_io.account(op, journal=False)
        if op.result_bool: self._pending_io.observe(op)
        self._pending_io.account(op)
        row['raw_call_bracket_ns'][1] = self._invocation_check()
        if op.settled and (op.error != 0 or op.count != len(record.request)):
            raise ValueError('original write failed/short; remainder prohibited')
        record._append(row)
        return record.snapshot()

    @_entry
    def read_invocation_once(self):
        record = self._require_invocation()
        self._invocation_check()
        if record.dispatch is None or record.dispatch.get('bytes_written') != len(record.request):
            raise ValueError('original completed recorded write required before read')
        if any(op.kind == 'read' and op.issued and not op.settled for op in self._pending_io.operations):
            return record.snapshot()  # Same reader remains pending; no second read/budget.
        row = record.start_read()
        record._append(row)
        op = self._pending_io.operation(self._pending_io.endpoints['output_read'][0],
                                        'read', row['requested_bytes'])
        op.row = row
        op.record = record
        row['raw_call_bracket_ns'][0] = self._invocation_check()
        try:
            self._pending_io.issue(op)
        finally:
            self._pending_io.account(op, journal=False)
        if op.result_bool: self._pending_io.observe(op)
        self._pending_io.account(op)
        row['raw_call_bracket_ns'][1] = self._invocation_check()
        record._append(row)
        if op.settled and op.error not in (0, 109): raise ValueError('original read failed')
        if record._eof: self._close_internal('original output EOF')
        elif record._zero_read_stop: self._close_internal('original zero-byte read, progress not proved')
        return record.snapshot()

    @_entry
    def poll_invocation(self):
        record = self._require_invocation()
        self._invocation_check()
        for op in self._pending_io.operations:
            if op.kind == 'connect' or not op.issued or op.settled: continue
            self._pending_io.observe(op)
            self._pending_io.account(op)
            if op.settled and ((op.error != 0 and not (op.kind == 'read' and op.error == 109)) or
                               (op.kind == 'write' and op.count != len(record.request))):
                raise ValueError('original asynchronous IO failed/short')
        self._invocation_check()
        if record._eof: self._close_internal('original output EOF')
        elif record._zero_read_stop: self._close_internal('original zero-byte read, progress not proved')
        return record.snapshot()

    @_entry
    def poll_teardown(self):
        if self._pending_io is None or not self._cleanup_attempted:
            raise ValueError('only retired original overlapped teardown can be observed')
        return self._close_overlapped('observe original teardown only')

    @_entry
    def invocation_snapshot(self):
        return (dict(schema=2, prepared=False, authenticated=False, completion_verified=False)
                if self._invocation is None else self._invocation.snapshot())

    @_entry
    def diagnostics(self):
        return dict(state=self._state, instance_id=self.instance_id,
            evidence_complete=self._acl_ready and not self._evidence_errors,
            cleanup_complete=bool(self._cleanup_result and self._cleanup_result.resources_complete))


__all__ = ['ActorRegistry', 'ActorOwner', 'ActorPolicy']

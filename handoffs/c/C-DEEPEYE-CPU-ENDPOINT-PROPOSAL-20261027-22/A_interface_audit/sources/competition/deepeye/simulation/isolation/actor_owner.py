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
        evidence_complete=not owner._evidence_errors, cleanup_attempted=owner._cleanup_attempted)
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
            if self._foreign_call.is_set() and method.__name__ != 'close':
                raise ValueError('foreign-thread entry pending')
            return method(self, *args, **kwargs)
        except BaseException as error:
            if self._primary_error is None: self._primary_error = error
            self._revoke('actor entry rejected')
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
        total = 0
        for name, expected in self._policy.files:
            source = self._policy.source_root / name
            _no_alias(source)
            stat = source.stat()
            if not source.is_file() or stat.st_nlink != 1: raise ValueError('ordinary single-link source required')
            total += stat.st_size
            if total > self._policy.max_stage_bytes: raise ValueError('approved stage size budget exceeded')
            with source.open('rb') as stream:
                raw = stream.read(self._policy.max_stage_bytes - total + stat.st_size + 1)
            if len(raw) != stat.st_size or hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('approved stage hash mismatch')
            target = self._stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream: stream.write(raw)
            self._checkpoint()

    @_entry
    def _launch(self):
        from .actor_lifetime import _sample
        try:
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
            inp, write = self._api.pipe(owner=self._resources, read_label='input_read', write_label='input_write')
            self._checkpoint()
            read, out = self._api.pipe(owner=self._resources, read_label='output_read', write_label='output_write')
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
            args = (*self._policy.arguments, str(inp), str(out))
            pi = self._api.create_suspended(self._stage / self._policy.executable, args, self._stage,
                environment, profile, inp, out, owner=self._resources)
            self._process = self._original_process = self._resources.find('process')
            self._original_native = self._process.native
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
        from ..authority.pc_direct_runtime import BootBinding, PcDirectRuntime
        from ..authority.motion_executor import OwnedMotionExecutor
        from ...integration import host_envelope as envelope, pc_direct_watchdog as watchdog
        from .actor_lifetime import _sample
        if self._state != 'RUNNING_UNBOUND': raise ValueError('actor activation is single use')
        if (type(boot) is not BootBinding or boot.run_id != self._policy.run_id or
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

    @_entry
    def diagnostics(self):
        return dict(state=self._state, instance_id=self.instance_id,
            evidence_complete=self._acl_ready and not self._evidence_errors,
            cleanup_complete=bool(self._cleanup_result and self._cleanup_result.resources_complete))


__all__ = ['ActorRegistry', 'ActorOwner', 'ActorPolicy']

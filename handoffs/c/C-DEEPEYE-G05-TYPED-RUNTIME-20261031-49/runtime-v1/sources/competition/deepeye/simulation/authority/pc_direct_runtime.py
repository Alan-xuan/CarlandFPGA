"""Single-owner PC_DIRECT authority adapter with explicit trusted dependencies.

This module does not implement transport authentication, real board observation
provenance, AI process monitoring or physics. AuthorityDependencies must do those
jobs in the trusted authority process; no permissive/default provider exists.
Dataclass records are local results of those verifiers, never credentials.
See docs/pc_direct_runtime.md before connecting a real executor.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from functools import wraps
import json
import threading

from ...integration import host_envelope as envelope
from ...integration import pc_direct_watchdog as watchdog
from ...integration import wire

# Read status offsets from the existing frozen ABI instead of introducing a
# second response layout. Structural/CRC/context validation still runs first.
_FRAMES = json.loads(envelope.SCHEMA_PATH.with_name('interface.json').read_bytes())['frames']
_RESPONSE_STATUS = {frame['type']: tuple(field for field in frame.get('fields', ())
                    if field['name'] in ('phase', 'fault_flags')) for frame in _FRAMES.values()}


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(label + ' must be a strict bounded integer')
    return value


def _runtime_entry(method):
    """Record invalid call shapes that Python rejects before the body runs.

    Opaque channel data is still checked by the existing guards. This wrapper
    only prevents a caught missing/unknown argument TypeError in a trusted
    callback from bypassing the runtime's veto-generation transaction fence.
    """
    @wraps(method)
    def call(self, /, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except TypeError as error:
            self._trip('invalid_runtime_call')
            raise ValueError('invalid runtime call arguments; STOP latched') from error
    return call


def _is_binding(value, *, executor=None):
    if type(value) is BootBinding:
        return True
    from .g05p_runtime_v1 import is_original_binding
    return is_original_binding(value, executor=executor)


class _NoActiveCommand(ValueError):
    """Normal stopped idle/expiry polling, not malformed input or a veto."""


@dataclass(frozen=True)
class BootBinding:
    run_id: str
    generation: int
    context_json: bytes
    ai_instance: str


@dataclass(frozen=True)
class VerifiedEnvelope:
    boot: BootBinding
    raw: bytes


@dataclass(frozen=True)
class VerifiedObservation:
    boot: BootBinding
    raw: bytes
    sample_lower_ns: int


@dataclass(frozen=True)
class AiLease:
    boot: BootBinding
    instance_id: str
    deadline_ns: int


@dataclass(frozen=True)
class StepFence:
    """One synchronous executor check result; not a reusable motion grant."""
    boot: BootBinding
    command_seq: int
    checked_ns: int
    step_end_ns: int
    deadline_ns: int


@dataclass(frozen=True)
class CommitReceipt:
    """Trusted executor's atomic-CAS receipt, not independently measured motion."""
    boot: BootBinding
    command_seq: int
    pose_revision: int
    start_ns: int
    end_ns: int


@dataclass(frozen=True)
class StepResult:
    committed: bool
    reason: str
    receipt: CommitReceipt | None = None


@dataclass(frozen=True)
class ExpiryStatus:
    """Owner-only stop diagnostic; neither readiness nor motion permission."""
    stop_required: bool
    reason: str


class AuthorityDependencies(ABC):
    """Trusted in-process boundary. All missing/rejected evidence must raise.

    verify_* authenticate their ORIGINAL opaque channel events and bind them to
    an independently completed BOOT/run/generation; constructing these records
    alone proves nothing. verify_observation must verify actual FPGA reception,
    quality, measured clock/source timing and original native sample age.
    ai_lease must inspect actual current process identity/life, with a bounded
    deadline; no cached alive boolean is sufficient. It must never resurrect an
    AI process inside a BOOT by assigning it the old instance identity.

    prepare_step performs full-volume geometry/kinematics/phase checks with no
    pose mutation. commit_step must invoke before_commit EXACTLY ONCE, inside
    the authority's atomic pose-CAS critical section, immediately before its
    only pose update. The update must use that checked step interval, stop at
    its end and bind the prepared geometry, command and expected pose revision.
    There must be no wait, asynchronous work or untrusted call after the fence.
    It returns CommitReceipt only after successful atomic commit. Failure or
    uncertainty raises; late/delayed commit requires preparation/checks again.
    """
    @abstractmethod
    def verify_boot(self, event) -> BootBinding: ...

    @abstractmethod
    def verify_board(self, event, boot: BootBinding) -> VerifiedEnvelope: ...

    @abstractmethod
    def verify_observation(self, event, boot: BootBinding) -> VerifiedObservation: ...

    @abstractmethod
    def verify_command(self, event, boot: BootBinding) -> VerifiedEnvelope: ...

    @abstractmethod
    def ai_lease(self, boot: BootBinding, now_ns: int) -> AiLease: ...

    @abstractmethod
    def prepare_step(self, boot: BootBinding, command_raw: bytes,
                     expected_pose_revision: int, dt_ns: int): ...

    @abstractmethod
    def commit_step(self, prepared, before_commit) -> CommitReceipt: ...


@dataclass(frozen=True)
class _Observation:
    raw: bytes
    sample_lower_ns: int


@dataclass(frozen=True)
class _Command:
    raw: bytes
    sequence: int
    observed_seq: int
    deadline_ns: int


class PcDirectRuntime:
    """Serialize channel events and every synchronous physics step on one thread.

    Every validation error latches STOP. A new independently verified BOOT with
    an unused session and increasing generation is the only recovery path.
    Ordinary command expiration clears only that action; a newer command may
    run against still-fresh evidence. There are no untrusted grant setters.
    """
    def __init__(self, *, run_id, dependencies, clock, heartbeat_timeout_ns, g05p_profile=None):
        if type(run_id) is not str or not run_id:
            raise ValueError('nonempty run_id required')
        if not isinstance(dependencies, AuthorityDependencies) or not callable(clock):
            raise ValueError('trusted authority dependencies and monotonic clock required')
        self._timeout = _integer(heartbeat_timeout_ns, 'heartbeat_timeout_ns', 1)
        self._g05p_profile = g05p_profile
        if g05p_profile is not None:
            from .g05p_runtime_v1 import G05Profile
            if type(g05p_profile) is not G05Profile:
                raise ValueError('exact explicit G05 profile required')
            g05p_profile.check()
        self._run_id, self._deps, self._clock = run_id, dependencies, clock
        self._owner = threading.get_ident()
        self._now = _integer(clock(), 'clock')
        self._boot = None
        self._guard = None
        self._latched = True
        self._reason = 'missing_boot'
        self._veto_generation = 0
        self._guard_latch_observed = False
        self._generation = 0
        self._used_sessions = set()
        self._observations = OrderedDict()
        self._last_observed_seq = None
        self._last_command = None
        self._command = None
        self._busy = False
        self._stepping = False
        self._pose_revision = None
        self._executed_until_ns = 0

    def _trip(self, reason):
        # Count every new veto, including repeated STOP while already latched.
        # BOOT must distinguish its inherited recovery state from an event
        # raised during the current verifier/activation transaction.
        self._veto_generation += 1
        if not self._latched or self._reason == 'missing_boot':
            self._reason = reason
        self._latched = True
        self._command = None

    def _advance(self):
        if threading.get_ident() != self._owner:
            raise ValueError('runtime must stay on its owner thread')
        now = _integer(self._clock(), 'clock')
        if now < self._now:
            raise ValueError('monotonic clock regressed')
        self._now = now
        if self._guard is not None:
            decision = self._guard.check(now_ns=now)
            if decision.latched and not self._guard_latch_observed:
                self._guard_latch_observed = True
                self._trip(decision.reason)
        if self._command is not None and now >= self._command.deadline_ns:
            self._command = None
        return now

    def _active(self):
        if self._latched or self._boot is None:
            raise ValueError('stopped: ' + self._reason)

    def _event(self, function, *, boot=False):
        entered = False
        try:
            if self._busy or self._stepping:
                raise ValueError('reentrant channel event forbidden during an event or physics step')
            self._busy = True
            entered = True
            self._advance()
            if not boot:
                self._active()
            return function()
        except Exception as error:
            self._trip('invalid_event')
            raise ValueError('runtime rejected event; STOP latched') from error
        finally:
            if entered:
                self._busy = False

    def _record(self, record, expected_type):
        if type(record) is not expected_type or not self._same_boot(record.boot) or type(record.raw) is not bytes:
            raise ValueError('verified record type or active BOOT/run/generation mismatch')
        return record

    def _allowed_binding(self, value):
        if self._g05p_profile is None:
            return type(value) is BootBinding
        from .g05p_runtime_v1 import is_original_binding
        return (is_original_binding(value) and
                value._channel._config.g05p_profile is self._g05p_profile)

    def _same_boot(self, value):
        return (self._allowed_binding(value) and type(value.run_id) is str
                and type(value.generation) is int and type(value.context_json) is bytes
                and type(value.ai_instance) is str and value == self._boot)

    @_runtime_entry
    def boot(self, event):
        # Fence the entire call, including the entry clock callback, not merely
        # the verifier body. No veto raised by this call is inherited recovery.
        veto_generation = self._veto_generation
        def activate():
            proposed = self._deps.verify_boot(event)
            if (not self._allowed_binding(proposed) or type(proposed.run_id) is not str or proposed.run_id != self._run_id
                    or type(proposed.context_json) is not bytes
                    or type(proposed.ai_instance) is not str or not proposed.ai_instance):
                raise ValueError('invalid independently verified BOOT binding')
            _integer(proposed.generation, 'BOOT generation', 1)
            if proposed.generation <= self._generation:
                raise ValueError('BOOT generation must increase')
            # Reuse the strict context validator and topology check, not JSON
            # schema identity inference or a permissive dict comparison.
            context = watchdog._context_copy(envelope._parse_message(proposed.context_json))
            if context['session'] in self._used_sessions:
                raise ValueError('BOOT session was already used by this runtime')
            # Retirement precedes every activation clock/guard operation.
            # Once a verified, structurally valid identity reaches activation,
            # any later exception must not leave its handshake replayable.
            self._used_sessions.add(context['session'])
            self._generation = proposed.generation
            now = self._advance()
            if self._g05p_profile is None:
                guard = watchdog.PcDirectWatchdog(context=context, heartbeat_timeout_ns=self._timeout, now_ns=now)
            else:
                from .g05p_runtime_v1 import G05HealthGate
                guard = G05HealthGate(binding=proposed, heartbeat_timeout_ns=self._timeout, now_ns=now)
            new_context = guard.context
            if self._veto_generation != veto_generation:
                raise ValueError('BOOT activation invalidated by an intervening veto')
            # No dependency or clock callbacks follow this activation fence.
            self._boot, self._guard = proposed, guard
            self._guard_latch_observed = False
            self._context = new_context
            self._started_ns = now
            self._observations.clear()
            self._last_observed_seq = None
            self._last_command = self._command = None
            self._latched = False
            self._reason = 'missing_heartbeat'
        return self._event(activate, boot=True)

    @_runtime_entry
    def board(self, event):
        def receive():
            if self._g05p_profile is not None:
                from .g05p_runtime_v1 import G05Health, G05HealthGate
                record = self._deps.verify_board(event, self._boot)
                if (type(record) is not G05Health or record.binding is not self._boot
                        or type(self._guard) is not G05HealthGate):
                    raise ValueError('original typed G05 health required')
                now = self._advance(); self._active()
                self._guard.ingest_g05(record, now_ns=now)
                return 'g05_typed_health'
            record = self._record(self._deps.verify_board(event, self._boot), VerifiedEnvelope)
            now = self._advance(); self._active()
            parsed = envelope.validate_message(record.raw, producer='hardware_bridge',
                consumer='world_authority', context=self._context, now_ns=now)
            if parsed.kind != 'board_response':
                raise ValueError('board channel requires board_response')
            frame = wire.decode(bytes.fromhex(parsed.document['wire_frame_hex']))
            if frame.type_id == 8:
                decision = self._guard.ingest_heartbeat(record.raw, producer='hardware_bridge',
                    consumer='world_authority', now_ns=now)
                if decision.latched:
                    self._guard_latch_observed = True
                    self._trip(decision.reason)
            else:
                for field in _RESPONSE_STATUS[frame.type_id]:
                    start = field['payload_offset']
                    value = int.from_bytes(frame.payload[start:start + field['bytes']], 'little')
                    if ((field['name'] == 'fault_flags' and value)
                            or (field['name'] == 'phase' and value == 4)):
                        self._trip('board_response_fault_or_rejected')
            # Other healthy responses never refresh STATE8 or create capture.
            return parsed.kind
        return self._event(receive)

    @_runtime_entry
    def observe(self, event):
        def admit():
            record = self._record(self._deps.verify_observation(event, self._boot), VerifiedObservation)
            now = self._advance(); self._active()
            parsed = envelope.validate_message(record.raw, producer='hardware_bridge',
                consumer='world_authority', context=self._context, now_ns=now)
            if parsed.kind not in ('telem_observation', 'event_observation'):
                raise ValueError('observation channel requires TELEM/EVENT')
            doc = parsed.document
            mapped = doc['adc_last_interval_ns'] if parsed.kind == 'telem_observation' else doc['trigger_sample_interval_ns']
            sample = _integer(record.sample_lower_ns, 'verified sample lower bound')
            if mapped is None or sample > mapped['lower_ns'] or sample > now:
                raise ValueError('unknown/nonconservative acquisition mapping')
            native = doc.get('native_em_interval_ns')
            if native is not None and sample > native['lower_ns']:
                raise ValueError('held/native sample age must remain conservative')
            if doc['receipt_interval_ns']['lower_ns'] < self._started_ns or sample + self._age_cap <= now:
                raise ValueError('observation predates BOOT or is stale')
            seq = doc['observed_seq']
            old = self._observations.get(seq)
            if old is not None and old == _Observation(record.raw, sample):
                return  # No receipt/age/ordering renewal for exact duplicate.
            if self._last_observed_seq is not None and seq <= self._last_observed_seq:
                raise ValueError('observation replay, changed key or sequence wrap')
            self._observations[seq] = _Observation(record.raw, sample)
            self._last_observed_seq = seq
            if len(self._observations) > 4:
                self._observations.popitem(last=False)
        return self._event(admit)

    @property
    def _age_cap(self):
        return 1_500_000_000 if self._context['transport_profile_id'] == 1 else 12_000_000_000

    def _ai(self, now, end_ns):
        lease = self._deps.ai_lease(self._boot, now)
        if (type(lease) is not AiLease or not self._same_boot(lease.boot)
                or type(lease.instance_id) is not str or lease.instance_id != self._boot.ai_instance):
            raise ValueError('AI process identity changed or lacks trusted liveness record')
        _integer(lease.deadline_ns, 'AI liveness deadline')
        if now >= lease.deadline_ns or end_ns > lease.deadline_ns:
            raise ValueError('AI liveness does not cover requested step')
        return lease.deadline_ns

    @_runtime_entry
    def command(self, event):
        def admit():
            record = self._record(self._deps.verify_command(event, self._boot), VerifiedEnvelope)
            now = self._advance(); self._active()
            parsed = envelope.validate_message(record.raw, producer='control_broker',
                consumer='world_authority', context=self._context, now_ns=now)
            if parsed.kind != 'motion_request':
                raise ValueError('broker channel requires motion_request')
            doc = parsed.document
            if doc['target']['action'] == 0:
                self._trip('broker_stop')
                return
            observation = self._observations.get(doc['observation']['observed_seq'])
            if observation is None:
                raise ValueError('command has no admitted actual observation')
            deadline = min(doc['host_issue_monotonic_ns'] + doc['target']['duration_ms'] * 1_000_000,
                           observation.sample_lower_ns + self._age_cap)
            seq = doc['command_seq']
            previous = self._last_command
            if previous is not None and seq <= previous.sequence:
                if seq != previous.sequence or record.raw != previous.raw or self._command is None:
                    raise ValueError('retired/changed/replayed command identity')
                deadline = min(deadline, previous.deadline_ns)
            if deadline <= now:
                raise ValueError('command expired before admission')
            self._ai(now, now)
            # Provider work may consume time or deliver a reentrant STOP.
            now = self._advance(); self._active()
            self._guard.track_authority_command(command_seq=seq, deadline_ns=deadline, now_ns=now)
            self._last_command = self._command = _Command(record.raw, seq, doc['observation']['observed_seq'], deadline)
        return self._event(admit)

    @_runtime_entry
    def stop(self, reason):
        """Any operator/config/mode/restart/source/AI loss may always stop safely."""
        self._trip(reason if type(reason) is str and reason else 'external_stop')

    @_runtime_entry
    def check_expiry(self):
        """Observe original expiry without dependencies, preparation or motion.

        No expiry requirement is only a diagnostic: an uncommanded runtime may
        still lack heartbeat, observations or liveness. Normal command expiry
        remains non-latching here; the composed owner retires that activation.
        """
        entered = False
        try:
            if self._busy or self._stepping:
                raise ValueError('reentrant expiry check forbidden during an event or physics step')
            self._busy = True
            entered = True
            now = self._advance()
            if self._latched:
                return ExpiryStatus(True, self._reason)
            # _advance or a prior channel event may already have cleared the
            # current action. Only fresh verified BOOT resets this history.
            if self._last_command is not None and now >= self._last_command.deadline_ns:
                return ExpiryStatus(True, 'command_deadline')
            return ExpiryStatus(False, 'no_expiry_requirement')
        except BaseException:
            self._trip('expiry_check_failed')
            raise
        finally:
            if entered:
                self._busy = False

    def _ready(self, dt_ns):
        now = self._advance(); self._active()
        if now < self._executed_until_ns:
            raise ValueError('physics interval overlaps a previously committed interval')
        command = self._command
        if command is None:
            raise _NoActiveCommand('no current command')
        observation = self._observations.get(command.observed_seq)
        if observation is None or now >= observation.sample_lower_ns + self._age_cap:
            raise ValueError('observation missing, retired or stale')
        decision = self._guard.check(now_ns=now)
        if decision.stop_required or decision.active_command_seq != command.sequence:
            raise ValueError('watchdog veto')
        deadline = min(command.deadline_ns, decision.heartbeat_deadline_ns,
                       observation.sample_lower_ns + self._age_cap)
        end = now + dt_ns
        if now >= deadline or end > deadline:
            raise ValueError('physics interval crosses validity deadline')
        ai_deadline = self._ai(now, end)
        # Liveness verification must be synchronous/nonblocking. Recheck time
        # and any STOP it raised before issuing the one-time commit fence.
        checked = self._advance(); self._active()
        if self._command is not command:
            raise ValueError('command expired during liveness check')
        final = self._guard.check(now_ns=checked)
        deadline = min(deadline, ai_deadline)
        if final.stop_required or checked >= deadline or checked + dt_ns > deadline:
            raise ValueError('validity expired during liveness check')
        return StepFence(self._boot, command.sequence, checked, checked + dt_ns, deadline)

    @_runtime_entry
    def step(self, *, expected_pose_revision, dt_ns):
        """Prepare and conditionally commit one bounded interval; errors STOP.

        committed=True reports the trusted executor receipt only. The adapter
        supplies no physics, no grant envelope and no independent motion proof.
        """
        entered = False
        try:
            if self._busy or self._stepping:
                self._trip('reentrant_step')
                raise ValueError('recursive/concurrent step forbidden')
            _integer(expected_pose_revision, 'pose revision')
            _integer(dt_ns, 'dt_ns', 1)
            if self._pose_revision is not None and expected_pose_revision != self._pose_revision:
                raise ValueError('pose revision does not match the last atomic commit')
            self._stepping = True
            entered = True
            self._ready(dt_ns)
            command = self._command
            prepared = self._deps.prepare_step(self._boot, command.raw, expected_pose_revision, dt_ns)
            self._ready(dt_ns)
            fenced = []
            open_fence = True
            attempted_fence = False
            def before_commit():
                nonlocal attempted_fence
                if not open_fence or attempted_fence:
                    self._trip('reused_commit_fence')
                    raise ValueError('commit fence is single use and synchronous')
                attempted_fence = True
                try:
                    checked = self._ready(dt_ns)
                    if self._command is not command:
                        raise ValueError('active command changed during prepare/commit')
                    fenced.append(checked)
                    return checked
                except Exception:
                    self._trip('commit_fence_veto')
                    raise
            try:
                receipt = self._deps.commit_step(prepared, before_commit)
            finally:
                open_fence = False
            if len(fenced) != 1 or type(receipt) is not CommitReceipt:
                raise ValueError('executor omitted fence or atomic commit receipt')
            self._active()
            check = fenced[0]
            if (not self._same_boot(receipt.boot) or type(receipt.command_seq) is not int
                    or receipt.command_seq != check.command_seq
                    or type(receipt.pose_revision) is not int or receipt.pose_revision != expected_pose_revision + 1
                    or type(receipt.start_ns) is not int or receipt.start_ns != check.checked_ns
                    or type(receipt.end_ns) is not int or receipt.end_ns != check.step_end_ns):
                raise ValueError('executor receipt does not bind checked interval and pose CAS')
            self._pose_revision = receipt.pose_revision
            self._executed_until_ns = receipt.end_ns
            return StepResult(True, 'trusted_executor_receipt', receipt)
        except _NoActiveCommand as error:
            # Only actual idle/normal command expiry is a non-latching poll.
            return StepResult(False, str(error))
        except Exception as error:
            self._trip('step_veto')
            return StepResult(False, str(error))
        finally:
            if entered:
                self._stepping = False


__all__ = ['PcDirectRuntime', 'AuthorityDependencies', 'BootBinding', 'VerifiedEnvelope',
           'VerifiedObservation', 'AiLease', 'StepFence', 'CommitReceipt', 'StepResult',
           'ExpiryStatus']

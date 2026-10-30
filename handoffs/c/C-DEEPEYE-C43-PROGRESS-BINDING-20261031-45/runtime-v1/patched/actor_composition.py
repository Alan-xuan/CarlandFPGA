"""Closed trusted composition library; production activation is unavailable.

No real readiness/channel/model provider is installed. The production gate
rejects before registry construction, stage or native acquisition. Private
test seams establish software sequencing only; see docs/actor_composition.md.
"""
from dataclasses import dataclass
from functools import wraps
import threading
from time import monotonic_ns

from ..isolation.actor_owner import ActorPolicy, ActorRegistry
from .motion_executor import OwnedMotionExecutor
from .candidate_owner import _CandidateOwner, _CompletedInference, _InputTransaction
from .pc_direct_runtime import (AiLease, AuthorityDependencies, BootBinding, PcDirectRuntime,
                                VerifiedEnvelope, VerifiedObservation)
from ...integration import host_envelope
from ...integration.candidate_mailbox import PcDirectWindowV2, _validate_interval_candidate
from ...integration import host_clock as clocks


class ActivationUnavailable(ValueError):
    """The original authenticated production dependencies do not exist yet."""


class CompositionRejected(ValueError):
    """Sanitized public refusal; private exceptions stay with the owner."""


@dataclass(frozen=True)
class AuthorityConfig:
    """Explicit trusted-main configuration, not a credential or controller input."""
    actor_policy: ActorPolicy
    initial_state: object
    scene: object
    model: object
    budget: object
    heartbeat_timeout_ns: int
    max_slices: int
    progress_max_age_ns: int
    ai_model_sha256: str
    pc_direct_window_v2: PcDirectWindowV2 | None = None
    enable_completion_interval_v2: bool = False


@dataclass(frozen=True)
class CompositionStatus:
    state: str


@dataclass(frozen=True)
class StepOutcome:
    committed: bool
    pose_revision: int | None


_FACTORY = object()
_STOPPED = object()
_RETAINED = []  # Strong recovery ownership before any acquisition; no auto-eviction.
_MAX_NS = (1 << 63) - 1  # Existing host_contract integer bound.


def _bounded(value, minimum=0):
    if type(value) is not int or not minimum <= value <= _MAX_NS:
        raise ValueError('strict bounded progress integer required')
    return value


@dataclass(frozen=True)
class _BoundProgress:
    request_raw: bytes
    candidate_raw: bytes
    command_seq: int
    candidate_id: int
    invocation_id: int
    dispatch_lower_ns: int
    completion_lower_ns: int
    completion_upper_ns: int
    deadline_ns: int
    observed_interval_v2: object = None


class _ProgressGate:
    """One activation, one current command, irreversible expiry/revocation."""
    def __init__(self, boot, source, clock_domain, model_hash, max_age, now, *,
                 enable_completion_interval_v2=False):
        if type(enable_completion_interval_v2) is not bool:
            raise ValueError('strict interval opt-in required')
        self.enable_completion_interval_v2 = enable_completion_interval_v2
        self.boot, self.source, self.clock_domain = boot, source, clock_domain
        self.model_hash, self.max_age = model_hash, _bounded(max_age, 1)
        self.started = self.high_water = _bounded(now)
        self.initial_deadline = _bounded(now + max_age)
        self.context = host_envelope._parse_message(boot.context_json)
        self.generation, self.revoked, self.bound = 0, False, None

    def revoke(self):
        self.generation += 1
        self.revoked = True  # Keep the original record for diagnosis, no reset.

    def observe_time(self, now):
        try:
            _bounded(now)
            if self.revoked or now < self.high_water:
                raise ValueError('progress retired or monotonic clock regressed')
            self.high_water = now  # Retain even if subsequent validation fails.
            deadline = self.initial_deadline if self.bound is None else self.bound.deadline_ns
            if now >= deadline:
                raise ValueError('fixed inference progress deadline expired')
            return now
        except BaseException:
            self.revoke()
            raise

    def admit(self, proof, request_raw, now):
        try:
            self._admit(proof, request_raw, now)
        except BaseException:
            self.revoke()
            raise

    def _admit(self, proof, request_raw, now):
        self.observe_time(now)
        if (type(proof) is not _CompletedInference or proof.boot is not self.boot or
                proof.source is not self.source or proof.clock_domain is not self.clock_domain or
                type(proof.candidate_raw) is not bytes or type(request_raw) is not bytes):
            raise ValueError('original verified inference association required')
        request = host_envelope.validate_message(request_raw, producer='control_broker',
            consumer='world_authority', context=self.context, now_ns=now)
        if self.enable_completion_interval_v2:
            candidate = _validate_interval_candidate(proof, self.context, now, self.max_age)
        else:
            if proof.observed_interval_v2 is not None:
                raise ValueError('observed interval requires explicit progress opt-in')
            candidate = host_envelope.validate_message(proof.candidate_raw, producer='ai_controller',
                consumer='control_broker', context=self.context, now_ns=now)
        interval_deadline = candidate.valid_until_ns if self.enable_completion_interval_v2 else None
        if request.kind != 'motion_request' or candidate.kind != 'model_candidate':
            raise ValueError('original candidate and motion request required')
        request, candidate = request.document, candidate.document
        if (request['target']['action'] == 0 or candidate['model_sha256'] != self.model_hash or
                any(request[key] != candidate[key] for key in ('candidate_id', 'observation', 'target'))):
            raise ValueError('completion does not match approved model and causal command')
        invocation = _bounded(proof.invocation_id, 1)
        dispatch = _bounded(proof.dispatch_lower_ns)
        lower, upper = _bounded(proof.completion_lower_ns), _bounded(proof.completion_upper_ns)
        issue = _bounded(request['host_issue_monotonic_ns'])
        sequence, candidate_id = _bounded(request['command_seq']), _bounded(candidate['candidate_id'])
        if self.enable_completion_interval_v2:
            if not self.started <= dispatch <= lower <= upper <= issue <= now:
                raise ValueError('observation interval lacks ordered original host-time bounds')
            deadline = _bounded(interval_deadline)
        else:
            claimed = _bounded(candidate['completed_monotonic_ns'])
            if not self.started <= dispatch <= lower <= claimed <= upper <= issue <= now:
                raise ValueError('completion interval lacks ordered original host-time bounds')
            deadline = _bounded(lower + self.max_age)
        if now >= deadline:
            raise ValueError('original inference completion already stale')
        proposed = _BoundProgress(request_raw, proof.candidate_raw, sequence, candidate_id,
            invocation, dispatch, lower, upper, deadline, proof.observed_interval_v2)
        old = self.bound
        if old is not None:
            if sequence == old.command_seq:
                if proposed != old:
                    raise ValueError('changed duplicate inference/command association')
                return  # Exact original bytes/bounds; receipt cannot renew.
            if (sequence < old.command_seq or candidate_id <= old.candidate_id or
                    invocation <= old.invocation_id):
                raise ValueError('retired inference/candidate/command replay')
        self.bound = proposed
        self.generation += 1

    def deadline_for(self, request_raw, now):
        self.observe_time(now)
        if self.bound is None or request_raw != self.bound.request_raw:
            self.revoke()
            raise ValueError('no original command-bound inference completion')
        return self.bound.deadline_ns


def _production_channels(config, *, host_clock=None):
    # No callable/provider supplied by a caller can bypass this gate.
    raise ActivationUnavailable('original authenticated AI/channel/package unavailable')


def _entry(method):
    @wraps(method)
    def call(self, /, *args, **kwargs):
        if type(self) is not ActorComposition:
            raise CompositionRejected('original composition required')
        if threading.get_ident() != self._thread:
            self._foreign.set()  # No cross-thread native/authority operations.
            raise CompositionRejected('authority owner thread required')
        if self._busy:
            error = CompositionRejected('reentrant composition entry')
            self._remember(error)
            self._retire('reentrant composition entry')
            raise error
        self._busy = True
        terminal = method.__name__ in ('close', 'stop', 'status')
        step_link = self._world_action_link if method.__name__ == 'step' else None
        previous_step_slot = None if step_link is None else step_link.slot
        source_custody = source_transition = None
        try:
            if self._foreign.is_set():
                if not terminal: raise CompositionRejected('foreign-thread veto pending')
                self._retire('foreign-thread veto pending')
            epoch = self._veto
            if not terminal:
                self._checkpoint()
            if method.__name__ in ('accept_boot', 'accept_command') and self._world_action_link is not None:
                book = self._world_action_link.book
                if book is None or book._actor_custody is None:
                    raise CompositionRejected('original actor source lineage required')
                source_custody = book._actor_custody
                source_transition = source_custody.reserve(self,
                    'BOOT' if method.__name__ == 'accept_boot' else 'COMMAND')
            result = method(self, *args, **kwargs)
            if result is _STOPPED:
                if source_custody is not None:
                    source_custody.abort(source_transition, 'original actor STOP')
                return None
            if type(result) is StepOutcome:
                if result.committed:
                    try:
                        self._checkpoint(epoch)
                    except BaseException as error:
                        # A veto after the actual CAS retires future admission;
                        # it cannot relabel an observed commit as no side effect.
                        self._remember(error)
                        self._retire('veto after completed commit')
                return result
            if not terminal:
                self._checkpoint(epoch)
            if source_custody is not None:
                source_custody.finish_nonspatial(source_transition)
            return result
        except BaseException as error:
            if source_custody is not None:
                source_custody.abort(source_transition, 'original actor transition rejected')
            self._remember(error)
            try:
                self._retire('composition entry rejected')
            except BaseException as retirement_error:
                self._errors.append(retirement_error)
                self._retired = True
                self._world_pending_stop = True
            if method.__name__ == 'step':
                link = self._world_action_link
                slot = None if link is None else link.slot
                if (link is step_link and slot is not previous_step_slot
                        and slot is not None and slot.committed and slot.receipt is not None):
                    return StepOutcome(True, slot.receipt.pose_revision)
                return StepOutcome(False, None)
            raise CompositionRejected('composition rejected; admission retired') from None
        finally:
            self._input_transaction = None
            self._busy = False
            if self._retired:
                if self._world_pending_stop:
                    self._world_pending_stop = False
                    try:
                        if self._candidates is not None:
                            self._candidates.retire()
                        if self._progress is not None and not self._progress.revoked:
                            self._progress.revoke()
                    except BaseException as retirement_error:
                        self._errors.append(retirement_error)
                    self._dispatch_stop('original world veto')
                self._cleanup()
    return call


class _Dependencies(AuthorityDependencies):
    """Fixed actor/executor targets. Channel verifiers cannot supply either."""
    def __init__(self, owner): self._owner = owner

    def verify_boot(self, event):
        owner = self._owner
        owner._checkpoint()
        if (owner._state != 'ACTIVATING' or event is not owner._boot_event or owner._boot_taken):
            raise ValueError('original single-use activation event required')
        owner._boot_taken = True
        return owner._boot

    def _verify(self, name, event, boot, kind):
        owner = self._owner
        owner._active()
        if boot is not owner._boot: raise ValueError('original composition BOOT required')
        epoch = owner._veto
        record = getattr(owner._channels, name)(event, boot)
        owner._checkpoint(epoch)
        owner._progress_time()
        owner._checkpoint(epoch)
        if type(record) is not kind or record.boot is not boot or type(record.raw) is not bytes:
            raise ValueError('original verified channel record required')
        return record

    def verify_board(self, event, boot):
        return self._verify('verify_board', event, boot, VerifiedEnvelope)

    def verify_observation(self, event, boot):
        record = self._verify('verify_observation', event, boot, VerifiedObservation)
        transaction = self._owner._input_transaction
        if transaction is None or transaction.kind != 'observation':
            raise ValueError('original observation transaction required')
        transaction.observation_record = record
        return record

    def verify_command(self, event, boot):
        record = self._verify('verify_command', event, boot, VerifiedEnvelope)
        owner = self._owner
        epoch = owner._veto
        now = owner._progress_time()
        command = host_envelope.validate_message(record.raw, producer='control_broker',
            consumer='world_authority', context=owner._progress.context, now_ns=now)
        if command.kind != 'motion_request':
            raise ValueError('broker command must be a motion request')
        if command.document['target']['action'] != 0:
            transaction = owner._input_transaction
            if transaction is None or transaction.kind != 'command':
                raise ValueError('original command transaction required')
            proof = owner._candidates.duplicate_proof(record.raw)
            if proof is None:
                grant = owner._channels.verify_slot(transaction.slot_event, boot)
                owner._checkpoint(epoch)
                now = owner._progress_time()
                owner._checkpoint(epoch)
                proof = owner._candidates.select(record.raw, grant, now)
            owner._progress.admit(proof, record.raw, now)
            transaction.selected_proof, transaction.request_raw = proof, record.raw
        owner._checkpoint(epoch)
        owner._command_record = record
        return record

    def ai_lease(self, boot, now_ns):
        owner = self._owner
        owner._active()
        epoch = owner._veto
        gate = owner._progress
        generation = gate.generation
        # The only lifetime target: no channel/provider fallback or cached lease.
        result = owner._actor.ai_lease(boot, now_ns)
        owner._checkpoint(epoch)
        if (owner._progress is not gate or gate.generation != generation or
                type(result) is not AiLease or result.boot is not boot or
                type(result.instance_id) is not str or result.instance_id != boot.ai_instance):
            raise ValueError('original life/progress activation changed during sample')
        _bounded(result.deadline_ns)
        record = owner._command_record
        if record is None or record.boot is not boot:
            raise ValueError('missing original admitted command for progress')
        if owner._runtime._stepping:
            command = owner._runtime._command
            if command is None or command.raw != record.raw:
                raise ValueError('runtime command differs from bound progress')
        deadline = gate.deadline_for(record.raw, now_ns)
        return AiLease(result.boot, result.instance_id, min(result.deadline_ns, deadline))

    def prepare_step(self, boot, command_raw, expected_pose_revision, dt_ns):
        owner = self._owner
        owner._active(); epoch = owner._veto
        if owner._progress.bound is None or command_raw != owner._progress.bound.request_raw:
            raise ValueError('geometry command differs from bound progress')
        result = owner._executor.prepare_step(boot, command_raw, expected_pose_revision, dt_ns)
        owner._checkpoint(epoch)
        return result

    def commit_step(self, prepared, before_commit):
        owner = self._owner
        owner._active()
        link = owner._world_action_link
        if link is None:
            return owner._executor.commit_step(prepared, before_commit)
        from .original_world_actor_link import _commit_once
        return _commit_once(link, owner, prepared, before_commit)


class ActorComposition:
    """One owner thread, one acquisition, one closed activation transaction.

    Only create_authority constructs this library owner. These Python objects
    must remain authority-private; naming/frozen dataclasses are not isolation.
    """
    def __init__(self, key, config, channels, *, host_clock=None):
        if key is not _FACTORY: raise CompositionRejected('trusted factory required')
        self._thread = threading.get_ident()
        self._config, self._channels = config, channels
        self._host_clock = clocks._require_binding(host_clock)
        self._clock = monotonic_ns if self._host_clock is None else self._host_clock
        self._foreign = threading.Event()
        self._state, self._busy, self._retired = 'STARTING', False, False
        self._veto, self._revoking, self._cleanup_attempted = 0, False, False
        self._registry = self._actor = self._runtime = self._executor = None
        self._world_action_link = None
        self._world_pending_stop = False
        self._runtime_activation = self._executor_activation = None
        self._boot = self._boot_event = self._command_record = None
        self._progress = None
        self._candidates = self._input_transaction = None
        self._boot_taken = False
        self._primary_error, self._errors, self._last_step = None, [], None

    def _remember(self, error):
        if self._primary_error is None: self._primary_error = error

    def _checkpoint(self, epoch=None):
        if self._foreign.is_set() or self._retired or (epoch is not None and epoch != self._veto):
            raise CompositionRejected('composition activation vetoed')

    def _active(self):
        self._checkpoint()
        if self._state != 'ACTIVE': raise ValueError('complete activation required')

    def _dispatch_stop(self, reason):
        if self._revoking: return
        self._revoking = True
        try:
            try:
                if (self._runtime_activation is not None and self._runtime is not None and
                        self._runtime._boot is self._runtime_activation):
                    self._runtime.stop(reason)
            except BaseException as error:
                self._errors.append(error)
            finally:
                try:
                    # Check AFTER STOP; its callback can activate a successor.
                    if (self._executor_activation is not None and self._executor is not None and
                            self._executor._root.boot is self._executor_activation):
                        self._executor.revoke(reason)
                except BaseException as error:
                    self._errors.append(error)
        finally:
            self._revoking = False

    def _retire(self, reason):
        self._veto += 1
        self._retired = True  # Gate first, before callbacks or cleanup.
        self._input_transaction = None
        link = self._world_action_link
        if (link is not None and link.owner._actor_links.get(id(link)) is link
                and link.owner._actor_link is link and not link.owner._vetoed):
            link.owner._veto('original actor retired')
        self._world_pending_stop = False
        if self._candidates is not None:
            self._candidates.retire()
        if self._progress is not None:
            self._progress.revoke()
        if self._state not in ('CLOSED', 'QUARANTINED'): self._state = 'RETIRED'
        self._dispatch_stop(reason)

    def _cleanup(self):
        if self._cleanup_attempted: return
        self._cleanup_attempted = True
        # A failed registry.launch can own a process before returning an actor.
        actors = tuple(self._registry._owners) if self._registry is not None else ()
        complete = True
        for actor in actors:
            try:
                actor.close('composition retired')
                if actor.state != 'CLOSED': complete = False
            except BaseException as error:
                self._errors.append(error); complete = False
        self._state = 'CLOSED' if complete and not self._errors else 'QUARANTINED'

    @_entry
    def _start(self):
        config = self._config
        self._registry = ActorRegistry(host_clock=self._host_clock)
        self._checkpoint()
        if self._world_action_link is None:
            self._executor = OwnedMotionExecutor(initial_state=config.initial_state, scene=config.scene,
                model=config.model, budget=config.budget, max_slices=config.max_slices)
        else:
            self._world_action_link._registered()
            self._executor = self._world_action_link.executor
        self._runtime = PcDirectRuntime(run_id=config.actor_policy.run_id,
            dependencies=_Dependencies(self), clock=self._clock,
            heartbeat_timeout_ns=config.heartbeat_timeout_ns)
        self._checkpoint()
        self._actor = self._registry.launch(config.actor_policy)
        self._checkpoint()
        if self._world_action_link is not None:
            self._world_action_link._registered()
        self._state = 'RUNNING_UNBOUND'

    @_entry
    def accept_boot(self, event):
        if self._state != 'RUNNING_UNBOUND': raise ValueError('activation is single use')
        epoch = self._veto
        proposed = self._channels.verify_boot(event, run_id=self._config.actor_policy.run_id,
                                             instance_id=self._actor.instance_id)
        self._checkpoint(epoch)
        if (type(proposed) is not BootBinding or proposed.run_id != self._config.actor_policy.run_id or
                proposed.ai_instance != self._actor.instance_id):
            raise ValueError('original independently verified binding required')
        self._boot, self._boot_event = proposed, event
        self._progress = _ProgressGate(proposed, self._channels, self._clock,
            self._config.ai_model_sha256, self._config.progress_max_age_ns, self._clock(),
            enable_completion_interval_v2=self._config.enable_completion_interval_v2)
        self._checkpoint(epoch)
        self._state = 'ACTIVATING'
        # Intended original activations are captured before either call; never
        # adopt whatever successor an exceptional callback leaves behind.
        self._runtime_activation = self._executor_activation = proposed
        self._runtime.boot(event)
        self._checkpoint(epoch)
        self._executor.activate_boot(proposed)
        self._checkpoint(epoch)
        self._actor.bind_verified_boot(proposed, runtime=self._runtime, executor=self._executor)
        self._checkpoint(epoch)
        self._channels.checkpoint()
        self._checkpoint(epoch)
        self._progress_time()
        activation = self._channels.mailbox_activation_for_boot(proposed)
        self._checkpoint(epoch)
        now = self._progress_time()
        self._checkpoint(epoch)
        self._candidates = _CandidateOwner(proposed, self._channels, self._clock,
            self._config.ai_model_sha256, self._config.progress_max_age_ns,
            self._progress.started, activation, now,
            pc_direct_window_v2=self._config.pc_direct_window_v2,
            enable_completion_interval_v2=self._config.enable_completion_interval_v2)
        self._progress_time()
        self._checkpoint(epoch)
        self._actor.poll()
        self._checkpoint(epoch)
        self._state = 'ACTIVE'

    def _channel_health(self):
        epoch = self._veto
        self._channels.checkpoint()
        self._checkpoint(epoch)
        if self._progress is not None:
            self._progress_time()

    def _progress_time(self):
        epoch = self._veto
        now = self._clock()
        self._checkpoint(epoch)
        return self._progress.observe_time(now)

    def _runtime_active(self):
        if self._runtime._latched: raise ValueError('runtime stopped')

    @_entry
    def accept_board(self, event):
        self._active(); self._channel_health()
        self._runtime.board(event)
        self._runtime_active()

    @_entry
    def accept_observation(self, event):
        self._active(); self._channel_health()
        self._input_transaction = _InputTransaction('observation')
        self._runtime.observe(event)
        self._runtime_active()
        now = self._progress_time()
        transaction = self._input_transaction
        if transaction is None or transaction.observation_record is None:
            raise ValueError('original runtime-admitted observation missing')
        self._candidates.observe(transaction.observation_record, now)

    @_entry
    def accept_completion(self, event):
        self._active(); self._channel_health()
        epoch = self._veto
        proof = self._channels.verify_completion(event, self._boot)
        self._checkpoint(epoch)
        now = self._progress_time()
        self._checkpoint(epoch)
        return self._candidates.offer(proof, now)

    @_entry
    def accept_command(self, event, *, slot_event=None):
        self._active(); self._channel_health()
        self._input_transaction = _InputTransaction('command', slot_event=slot_event)
        self._command_record = None
        self._runtime.command(event)
        self._checkpoint()
        record = self._command_record
        if record is None: raise ValueError('original command admission missing')
        document = host_envelope._parse_message(record.raw)
        if document['target']['action'] == 0:
            self._retire('broker STOP')
            return _STOPPED
        self._runtime_active()
        self._executor.admit_command(self._boot, record.raw)
        self._checkpoint()
        transaction = self._input_transaction
        if transaction is None or transaction.request_raw != record.raw:
            raise ValueError('original command transaction lost after admission')
        self._candidates.commit(record.raw, transaction.selected_proof)

    @_entry
    def step(self, *, expected_pose_revision, dt_ns):
        original_link = self._world_action_link
        previous_slot = None if original_link is None else original_link.slot
        self._active(); self._channel_health()
        result = self._runtime.step(expected_pose_revision=expected_pose_revision, dt_ns=dt_ns)
        self._last_step = result  # Private; raw geometry failure is never public.
        if not result.committed:
            link = self._world_action_link
            slot = None if link is None else link.slot
            self._retire('runtime step did not commit')
            if (link is original_link and slot is not previous_slot
                    and slot is not None and slot.committed and slot.receipt is not None):
                return StepOutcome(True, slot.receipt.pose_revision)
            return StepOutcome(False, None)
        return StepOutcome(True, result.receipt.pose_revision)

    @_entry
    def poll(self):
        self._channel_health()
        self._actor.poll()
        if self._state == 'ACTIVE':
            # Sample actual runtime time after the original actor's poll. This
            # observes stopping only; step() could prepare and publish motion.
            expiry = self._runtime.check_expiry()
            if expiry.stop_required:
                self._retire(expiry.reason)
                return _STOPPED

    @_entry
    def stop(self, reason):
        if type(reason) is not str or not reason: raise ValueError('explicit reason required')
        self._retire('external STOP')

    @_entry
    def close(self, reason):
        if type(reason) is not str or not reason: raise ValueError('explicit reason required')
        self._retire('composition close')

    @_entry
    def status(self):
        return CompositionStatus(self._state)


def create_authority(config, *, host_clock=None):
    """Production factory: unavailable authentication rejects before acquisition.

    No public dependency/verifier/provider/adoption options. Tests patch only
    module-private factories and the existing fake native boundary.
    """
    binding = clocks._require_binding(host_clock)
    if type(config) is not AuthorityConfig or type(config.actor_policy) is not ActorPolicy:
        raise CompositionRejected('explicit trusted authority configuration required')
    _bounded(config.progress_max_age_ns, 1)
    if type(config.enable_completion_interval_v2) is not bool:
        raise CompositionRejected('strict interval opt-in required')
    policy = config.pc_direct_window_v2
    if policy is not None:
        if type(policy) is not PcDirectWindowV2:
            raise CompositionRejected('explicit PC_DIRECT v2 policy required')
        _bounded(policy.consume_window_ns, 1)
    digest = config.ai_model_sha256
    if (type(digest) is not str or len(digest) != 64 or
            any(character not in '0123456789abcdef' for character in digest)):
        raise CompositionRejected('explicit approved inference model hash required')
    channels = _production_channels(config,host_clock=binding)  # Must precede registry construction.
    owner = ActorComposition(_FACTORY, config, channels,host_clock=binding)
    _RETAINED.append(owner)
    owner._start()
    return owner


__all__ = ['AuthorityConfig', 'CompositionStatus', 'StepOutcome', 'create_authority',
           'ActivationUnavailable', 'CompositionRejected']


def _create_authority_for_original_world(config, capability, *, host_clock=None):
    """Fixed production channel first; consume only the exact registered world."""
    binding = clocks._require_binding(host_clock)
    channels = _production_channels(config, host_clock=binding)
    from .original_world_actor_link import _OriginalWorldActorLink
    if (type(config) is not AuthorityConfig or type(config.actor_policy) is not ActorPolicy
            or type(capability) is not _OriginalWorldActorLink):
        raise CompositionRejected('original registered world capability required')
    _bounded(config.progress_max_age_ns, 1)
    if type(config.enable_completion_interval_v2) is not bool:
        raise CompositionRejected('strict interval opt-in required')
    if (type(config.ai_model_sha256) is not str or len(config.ai_model_sha256) != 64
            or any(c not in '0123456789abcdef' for c in config.ai_model_sha256)):
        raise CompositionRejected('explicit approved inference model hash required')
    if config.pc_direct_window_v2 is not None:
        if type(config.pc_direct_window_v2) is not PcDirectWindowV2:
            raise CompositionRejected('explicit PC_DIRECT v2 policy required')
        _bounded(config.pc_direct_window_v2.consume_window_ns, 1)
    capability._claim(config, binding)
    owner = ActorComposition(_FACTORY, config, channels, host_clock=binding)
    owner._world_action_link = capability
    capability.composition = owner
    _RETAINED.append(owner)
    owner._start()
    return owner

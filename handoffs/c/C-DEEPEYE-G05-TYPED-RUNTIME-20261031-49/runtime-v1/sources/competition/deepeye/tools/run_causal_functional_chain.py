"""Root-private causal source/projection orchestration; never supplies receipts.

Only an already-initialized retained production Root is accepted. The caller
owns the native lifecycle, real channel receipts, C46 invocation and cleanup.
"""
import hashlib
import json
import math
from pathlib import Path
import threading
import time

from ..integration import host_clock
from ..simulation.sensors.owned_world_field import OwnedWorldField
from ..simulation.authority import _world_loop, _root_jit_kernel, actor_composition
from ..simulation.authority import _owned_godot, _world_values
from ..simulation.authority.pc_direct_runtime import BootBinding, _is_binding
from ..simulation.isolation.actor_owner import ActorRegistry, ActorOwner
from ..simulation.authority.motion import gate_geometry, workspace_boundaries
from ..simulation.authority.world_initial_pose import initial_pose_for_layout
from ..simulation.authority.root_world_service import RootWorldService
from ..simulation.authority.source_projection_v1.provider import ProjectionSession
from ..simulation.authority.source_projection_v1.source_poll import poll_after_finished_transition
from .diagnostic.causal_pl_exchange import CausalSourcePump


def required_external_bindings():
    raise NotImplementedError('Root production factory, genuine board receipts and fixed C46 invocation provider are required')


_SNAPSHOT_LIMITS = dict(nodes=4096, objects=30, surfaces=64, unique_vertices=1000000,
                        indices=3000000, snapshot_bytes=134217728, chunks=3072, depth=32)
_REGISTRY_OBSERVATION_KEY = object()


class _RegistryView:
    __slots__ = ('_refs', '_state', '_sealed')
    def __init__(self, key, refs, state):
        if key is not _REGISTRY_OBSERVATION_KEY:
            raise ValueError('fixed original registry observation required')
        object.__setattr__(self, '_refs', refs)
        object.__setattr__(self, '_state', state)
        object.__setattr__(self, '_sealed', True)
    def __setattr__(self, name, value):
        raise AttributeError('original observation is immutable')


class _RegistryHold:
    __slots__ = ('view', 'lower_qpc_ns', 'upper_qpc_ns', 'getter_end_qpc_ns',
                 'context_attached', 'unavailable_reason')
    def __init__(self, key, view, lower, upper, getter_end):
        if key is not _REGISTRY_OBSERVATION_KEY:
            raise ValueError('fixed original registry hold required')
        for name, value in (('view', view), ('lower_qpc_ns', lower), ('upper_qpc_ns', upper),
                            ('getter_end_qpc_ns', getter_end), ('context_attached', False),
                            ('unavailable_reason', 'original_boot_to_c42_context_binding_unavailable')):
            object.__setattr__(self, name, value)
    def __setattr__(self, name, value):
        raise AttributeError('original hold is immutable')


def _check_registry_stable(before, after):
    before_refs, before_state = before
    after_refs, after_state = after
    if (len(before_refs) != len(after_refs)
            or any(a is not b for a, b in zip(before_refs, after_refs))
            or before_state != after_state):
        raise ValueError('original registry or transition changed during getter')


def _check_registry_interval(current, lower, upper):
    if type(current) is not dict or type(current.get('pose_read')) is not dict:
        raise ValueError('actual original getter interval required')
    begin = current['pose_read'].get('begin_qpc_ns')
    end = current['pose_read'].get('end_qpc_ns')
    at = current.get('at_qpc_ns')
    if (any(type(x) is not int for x in (lower, upper, begin, end, at))
            or not 0 <= lower <= begin <= end == at <= upper):
        raise ValueError('actual getter lies outside original registry hold')
    return end


def _native_closed(record):
    slots = record['slots']
    return (record.get('state') == 'CLOSED'
            and (slots['process']['state'] == 'NOT_ACQUIRED'
                 or (record['wait_result'] == 0 and type(record['exit_code']) is int))
            and (slots['job']['state'] == 'NOT_ACQUIRED' or record['job_active_processes'] == 0)
            and all(item['state'] in ('NOT_ACQUIRED', 'CLOSED') for item in slots.values()))


def _check_initial_view(owner, view):
    if (owner._commits or owner._diagnostic_used or view.kind != 'INITIAL_VIEW'
            or view.revision != 0 or not view.resolved or view.state != 'APPLIED'
            or view.readback is None or view.readback_ns is None
            or view.readback_ns >= view.deadline_ns or type(view.differences) is not dict
            or set(view.differences) != {'local', 'global_transform'}
            or any(type(view.differences[key]) is not tuple or len(view.differences[key]) != 12
                   for key in ('local', 'global_transform'))):
        raise ValueError('actual original initial view/getter not accepted')


def _pump_world(owner, predicate, deadline):
    while True:
        owner.poll()
        if owner._clock() >= deadline:
            raise TimeoutError('original world deadline expired')
        if owner._vetoed:
            raise ValueError('original world vetoed')
        if predicate():
            return
        time.sleep(.001)


class FunctionalBootstrapError(RuntimeError):
    """Carries the original error and the retained cleanup observations."""
    def __init__(self, cause, lifecycle):
        super().__init__('original functional world bootstrap failed')
        self.cause, self.lifecycle = cause, lifecycle


class FunctionalWorld:
    """Lifecycle of one original world; owner and observations remain private."""
    def __init__(self, clock, operation_id, output_dir):
        self.clock, self.operation_id, self.output_dir = clock, operation_id, output_dir
        self._thread = threading.get_ident()
        self.owner = self.binding = self.initial_view = self.source = None
        self.close_history, self.cleanup_errors = [], []
        self.actor_cleanup = None
        self._close_attempted = False

    def close(self, reason):
        if threading.get_ident() != self._thread or type(reason) is not str or not reason:
            raise ValueError('original lifecycle thread and explicit reason required')
        if self._close_attempted:
            return self.close_history
        self._close_attempted = True
        source = self.source
        if source is not None and source.composition is not None:
            try:
                source.composition.close(reason)
                composition = source.composition
                actors = (() if composition._registry is None else tuple(composition._registry._owners))
                self.actor_cleanup = dict(composition_state=composition.status().state,
                    errors=[type(error).__name__ for error in composition._errors],
                    owners=[dict(state=actor.state, resources=actor._resources.summary())
                            for actor in actors])
            except BaseException as error:
                self.cleanup_errors.append(('actor_close', type(error).__name__))
        if source is not None and source.source.state != 'RETIRED':
            try:
                source.source.retire(reason)
            except BaseException as error:
                self.cleanup_errors.append(('source_retire', type(error).__name__))
        owner = self.owner
        if owner is not None and getattr(owner, '_native', None) is not None:
            deadline = None
            while True:
                try:
                    record = owner.close(reason)
                    self.close_history.append(record)
                    if (_native_closed(record) or any(item['state'] in ('UNKNOWN', 'RELEASE_UNKNOWN')
                                                      for item in record['slots'].values())):
                        break
                    now = self.clock()
                    if deadline is None:
                        deadline = now + 5_000_000_000
                    elif now >= deadline:
                        break
                    time.sleep(.01)
                except BaseException as error:
                    self.cleanup_errors.append(('world_close', type(error).__name__))
                    break
        return self.close_history

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close('functional world context exit; resource cleanup')
        return False


def acquire_functional_world(spec, policy, initial_standoff_m, *, operation_id,
                             output_dir, field_policy, jit_runtime=None, clock=None):
    """Acquire one original world and prepare, but do not start, its source."""
    if (type(spec) is not _owned_godot.ApprovedLaunchSpec
            or type(policy) is not _world_values.ValuePolicy
            or policy.run_id != spec.run_id or policy.source_bundle_sha256 != spec.source_bundle_sha256
            or type(operation_id) is not str or not operation_id or not operation_id.isascii()
            or len(operation_id) > 192 or not isinstance(output_dir, Path) or not output_dir.is_absolute()
            or type(field_policy) is not dict or type(initial_standoff_m) not in (int, float)
            or not math.isfinite(initial_standoff_m) or initial_standoff_m <= 0):
        raise ValueError('exact original launch, policy, private output and standoff required')
    output = output_dir.resolve()
    for target in (spec.stdout_path, spec.stderr_path):
        if not isinstance(target, Path) or target.resolve().parent != output:
            raise ValueError('original native logs must be inside this new output directory')
    if clock is None:
        clock = host_clock.qpc_clock_for_new_run()
    if type(clock) is not host_clock.QpcHostClock:
        raise ValueError('original QPC binding required')
    host_clock._require_binding(clock)
    if jit_runtime is not None and (type(jit_runtime) is not _root_jit_kernel._Verified
            or jit_runtime._signature is None or jit_runtime._entry is None):
        raise ValueError('verified warmed original JIT runtime required before acquisition')
    output.mkdir(parents=True, exist_ok=False)
    lifecycle = FunctionalWorld(clock, operation_id, output)
    retained_before = len(_world_loop._RETAINED)
    try:
        with (output / 'operation.json').open('xb') as stream:
            stream.write(json.dumps(dict(operation_id=operation_id, run_id=spec.run_id,
                source_bundle_sha256=spec.source_bundle_sha256,
                raw_layout_sha256=spec.raw_layout_sha256), sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode('utf8'))
        start = clock()
        deadline = start + spec.containment_timeout_ns
        lifecycle.owner = owner = _world_loop._acquire_root_world(spec, clock)
        _pump_world(owner, lambda: owner._hello is not None,
                    min(deadline, start + spec.startup_timeout_ns))
        limits_raw = json.dumps(_SNAPSHOT_LIMITS, sort_keys=True, separators=(',', ':'),
                                ensure_ascii=False, allow_nan=False).encode('utf8')
        owner.request_freeze(snapshot_limits_sha256=hashlib.sha256(limits_raw).hexdigest(),
                             model_policy_sha256=_world_values._digest(policy))
        _pump_world(owner, lambda: owner._state == 'FROZEN', deadline)
        epoch = owner.frozen_epoch()
        with (output / 'original-snapshot.json').open('xb') as stream:
            stream.write(epoch.snapshot_raw)
        gates = [gate_geometry.Gate(item.face, _world_values._decode_bits(item.u_bits, 64),
                                   _world_values._decode_bits(item.v_bits, 64))
                 for item in epoch.snapshot.workspace.gates]
        pose = initial_pose_for_layout(workspace_boundaries.Layout(*gates),
                                       standoff_m=initial_standoff_m)
        lifecycle.binding = binding = owner.construct_and_bind(epoch, policy, initial_pose=pose)
        lifecycle.initial_view = view = owner.initialize_view(binding)
        _pump_world(owner, lambda: owner._initialized, min(deadline, view.deadline_ns))
        _check_initial_view(owner, view)
        lifecycle.source = FunctionalSource(owner, binding, field_policy=field_policy,
                                            jit_runtime=jit_runtime)
        return lifecycle
    except BaseException as error:
        if lifecycle.owner is None and len(_world_loop._RETAINED) == retained_before + 1:
            candidate = _world_loop._RETAINED[-1]
            if type(candidate) is _world_loop._RootWorldOwner and candidate._clock is clock:
                lifecycle.owner = candidate
        lifecycle.close('functional world bootstrap failed; original cleanup')
        raise FunctionalBootstrapError(error, lifecycle) from error


class FunctionalSource:
    """One original world/source/book association, confined to its owner thread."""
    def __init__(self, owner, binding, *, field_policy, jit_runtime=None):
        if (type(owner) is not _world_loop._RootWorldOwner or owner._test is not False
                or not any(owner is item for item in _world_loop._RETAINED)
                or owner._binding is not binding or type(owner._clock) is not host_clock.QpcHostClock
                or type(field_policy) is not dict):
            raise ValueError('initialized retained original world and exact binding required')
        _world_loop._RootWorldOwner._known_binding(owner, binding)
        owner.require_source_pose_current()
        if jit_runtime is not None and (type(jit_runtime) is not _root_jit_kernel._Verified
                or jit_runtime._signature is None or jit_runtime._entry is None):
            raise ValueError('verified warmed original JIT runtime required')
        self._thread = threading.get_ident()
        self.owner, self.binding, self.clock = owner, binding, owner._clock
        self.field = OwnedWorldField(binding.executor, **field_policy)
        self.source = CausalSourcePump(self.field.pose_reader, self.field.sample_sigma)
        self.scope = _world_loop._make_original_em_scope_factory(owner, binding, self.field, self.source)
        self.source.bind_original_em_scope(self.scope)
        self.backend = None
        if jit_runtime is not None:
            self.backend = _root_jit_kernel._make_original_backend(self.scope, jit_runtime)
            self.source.bind_original_jit_backend(self.backend)
            owner.poll()
            self.scope._check(None)
        self.service = RootWorldService(self.clock, owner, self.source)
        self.link = owner.actor_link(self.service)
        self.book = owner.actor_source_book(self.link)
        self.source.bind_original_source_book(self.book)
        self.source.enable_completed_sample_handoff()
        self.source.prepare()
        self.session = ProjectionSession.attach_original(owner, self.link, self.book)
        self._pending = None
        self._retained_samples = []
        self._registry_observations = []
        self._last_transition = None
        self.composition = None
        self._activation_attempted = False
        self._start_attempted = False

    def _check_thread(self):
        if threading.get_ident() != self._thread:
            raise ValueError('original functional source thread required')

    def start(self):
        """Start the prepared original source once, after external readiness."""
        self._check_thread()
        if self._start_attempted or self.source.state != 'NEW':
            raise ValueError('prepared source may start only once')
        self._start_attempted = True
        self.source.start(self.clock(), self.clock)

    def activate_original_authority(self, config):
        self._check_thread()
        if self._activation_attempted:
            raise ValueError('original authority is single-use')
        self._activation_attempted = True
        # This fixed factory independently checks original production channels;
        # unavailable channels reject instead of acquiring an actor.
        try:
            self.composition = actor_composition._create_authority_for_original_world(
                config, self.link, host_clock=self.clock)
        except BaseException:
            matches = [item for item in actor_composition._RETAINED
                       if getattr(item, '_world_action_link', None) is self.link]
            if len(matches) == 1:
                self.composition = matches[0]
            raise
        return self.composition

    def observe_config(self, original_ref, fields):
        self._check_thread(); self.session.observe_config(original_ref, fields)

    def observe_admission(self, original_ref, fields):
        self._check_thread(); self.session.observe_admission(original_ref, fields)

    def observe_finished_transition(self, transition, *, successor_root, slot=None, fields):
        self._check_thread()
        if self._pending is not None:
            raise ValueError('completed sample must be captured before transition attachment')
        self.session.observe_finished_transition(transition, successor_root=successor_root,
                                                 slot=slot, fields=fields)
        self._last_transition = transition

    def poll_sample(self):
        self._check_thread()
        if not self._start_attempted or self.source.state != 'RUNNING':
            raise ValueError('prepared original source must be started first')
        if self._pending is not None:
            raise ValueError('completed original sample still held')
        if len(self._retained_samples) >= 1001:
            raise ValueError('original source record cap exhausted')
        self.session._check()
        transitions = self.book._actor_custody.transitions
        if transitions:
            if transitions[-1] is not self._last_transition:
                raise ValueError('latest original transition not attached')
            pair = poll_after_finished_transition(self.session, self._last_transition)
        else:
            payload = self.source.poll()
            pair = None if payload is None else (payload, self.source.claim_completed_sample(payload))
        if pair is not None:
            self._pending = pair
            payload, token = pair
            self.source._handoff_check(payload, True)
            self._retained_samples.append(dict(book=self.book, payload=payload, token=token,
                raw=self.source._handoff_bytes(payload), released=False, captured=False))
        return pair

    def _retained_sample(self, payload):
        matches = [item for item in self._retained_samples if item['payload'] is payload]
        if (len(matches) != 1 or matches[0]['book'] is not self.book
                or self.source._source_book is not self.book
                or self.source._handoff_bytes(payload) != matches[0]['raw']):
            raise ValueError('unchanged retained original sample required')
        return matches[0]

    def release_sample(self, payload):
        """Release the occupied source slot, retaining its original token."""
        self._check_thread()
        entry = self._retained_sample(payload)
        if (entry['released'] or self._pending is None or self._pending[0] is not payload
                or self._pending[1] is not entry['token']):
            raise ValueError('held original source sample required')
        self.source._handoff_check(payload, True)
        self.source.release_completed_sample(payload)
        entry['released'] = True
        self._pending = None

    def capture(self, original_ref, payload, *, candidate, fields):
        self._check_thread()
        entry = self._retained_sample(payload)
        if entry['captured']:
            raise ValueError('original sample capture already attached')
        self.session._check()
        if not entry['released']:
            if self._pending is None or self._pending[0] is not payload or self._pending[1] is not entry['token']:
                raise ValueError('original source slot changed')
            self.source._handoff_check(payload, True)
        self.session.observe_capture(original_ref, entry['token'], candidate=candidate, fields=fields)
        entry['captured'] = True
        if not entry['released']:
            self.release_sample(payload)

    def attach_registry(self, original_view, context, generation, *, as_of_qpc_ns, observation_ref):
        self._check_thread()
        self.session.attach_registry(original_view, context, generation,
                                     as_of_qpc_ns=as_of_qpc_ns, observation_ref=observation_ref)

    def _registry_snapshot(self):
        """Observe fixed original identities, with strong references and no callbacks."""
        self._check_thread()
        self.session._check()
        self.book._check()
        owner, link, book, comp = self.owner, self.link, self.book, self.composition
        custody = book._actor_custody
        if type(comp) is not actor_composition.ActorComposition:
            raise ValueError('active original composition required')
        registry, actor, boot, runtime, executor = (comp._registry, comp._actor, comp._boot,
                                                    comp._runtime, comp._executor)
        if (type(registry) is not ActorRegistry or type(actor) is not ActorOwner
                or not _is_binding(boot, executor=executor) or comp._state != 'ACTIVE' or comp._retired
                or comp._busy or comp._foreign.is_set() or actor._foreign_call.is_set()
                or registry._thread != self._thread or registry._clock_binding is not self.clock
                or registry._launching is not None or not any(item is actor for item in registry._owners)
                or actor._registry is not registry or actor._boot is not boot
                or actor._thread != self._thread or comp._thread != self._thread
                or comp._host_clock is not self.clock or comp._clock is not self.clock
                or boot.run_id != actor._policy.run_id or boot.ai_instance != actor.instance_id
                or registry._generations.get(boot.run_id) != boot.generation
                or actor._runtime_owner is not runtime or actor._executor_owner is not executor
                or actor._runtime_activation is not boot or actor._executor_activation is not boot
                or comp._runtime_activation is not boot or comp._executor_activation is not boot
                or actor._state != 'BOUND_ACTIVE' or runtime is None or runtime._boot is not boot
                or runtime._latched or runtime._generation != boot.generation
                or executor is not link.executor or executor._root.boot is not boot
                or comp._world_action_link is not link or link.composition is not comp or not link.claimed
                or link.owner is not owner or link.book is not book or link.source is not self.source
                or owner._actor_link is not link or owner._actor_links.get(id(link)) is not link
                or book._source is not self.source or self.source._source_book is not book
                or custody is None or custody.book is not book or custody.link is not link
                or custody.pending is not None or book._root is not executor._root):
            raise ValueError('live original actor registry and book association required')
        legacy_context = actor_composition.host_envelope._parse_message(boot.context_json)
        if ((boot.run_id, legacy_context.get('session')) not in registry._used_sessions
                or legacy_context.get('topology_id') != 2):
            raise ValueError('original BOOT registry session/topology required')
        config = self.session._producer._config
        config_ref, config_fields = (None, None) if config is None else config
        config_bytes = None if config_fields is None else json.dumps(
            config_fields, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
            allow_nan=False).encode('utf8')
        transitions = tuple(custody.transitions)
        transition_bytes = tuple(json.dumps(item.record, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False).encode('utf8') for item in transitions)
        link_items = tuple(sorted(owner._actor_links.items()))
        actor_owners = tuple(registry._owners)
        refs = (owner, link, book, comp, registry, actor, boot, runtime, executor, executor._root,
                custody, self.clock, self.source, self.session, self.session._producer,
                config_ref, config_fields, comp._boot_event, link.slot, owner._publication,
                *transitions, *(item[1] for item in link_items), *actor_owners)
        state = (tuple(item[0] for item in link_items), len(transitions), len(actor_owners),
                 transition_bytes, config_bytes, boot.context_json, boot.generation,
                 owner._veto_generation, comp._veto, runtime._veto_generation, runtime._generation,
                 registry._ordinal, tuple(sorted(registry._generations.items())),
                 frozenset(registry._used_sessions), actor._state)
        return refs, state

    def read_current_with_registry(self):
        """Return a real getter and fixed registry hold, with C42 context unbound.

        The original BOOT context and C42's extended context have no fixed
        authenticated mapping. A later real board provider must bind that context.
        """
        self._check_thread()
        if len(self._registry_observations) >= 32:
            raise ValueError('original registry observation cap exhausted')
        before = self._registry_snapshot()
        lower = self.clock()
        current = self.session.read_current()
        after = self._registry_snapshot()
        upper = self.clock()
        _check_registry_stable(before, after)
        end = _check_registry_interval(current, lower, upper)
        view = _RegistryView(_REGISTRY_OBSERVATION_KEY, after[0], after[1])
        hold = _RegistryHold(_REGISTRY_OBSERVATION_KEY, view, lower, upper, end)
        self._registry_observations.append((current, view, hold))
        return current, view, hold

    def read_current(self):
        self._check_thread(); return self.session.read_current()

    def export(self, *, current_read, registry_ref, candidate_ref, history_refs=(), enabled=False):
        self._check_thread()
        return self.session.export(current_read=current_read, registry_ref=registry_ref,
                                   candidate_ref=candidate_ref, history_refs=history_refs, enabled=enabled)

"""Bounded R03 candidate-to-slot policy, never authentication or motion authority.

The serialized owner supplies original independently verified source, clock,
BOOT, completion and slot-grant associations. Identity objects and these local
dataclasses are NOT credentials or proof of measurement. Unknown inputs cannot
be consumed. No transport, inference, process, board or product activation occurs.
PC_DIRECT decision epochs emit no HIL wire command or physical capture fact.
"""
from collections import OrderedDict
from dataclasses import dataclass
from fractions import Fraction
from functools import wraps
import json

if __package__:
    from . import boot_profile as boot, host_envelope as envelope
else:
    import boot_profile as boot
    import host_envelope as envelope

NS_PER_MS = 1_000_000
MAX_ACTIVATIONS = 64
MAX_OBSERVATIONS = 4
MAX_TIME = (1 << 63) - 1


def _integer(value, label, low=0, high=MAX_TIME):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + ' must be a strict bounded integer')
    return value


def _entry(method):
    @wraps(method)
    def call(self, /, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            self._halt('invalid_' + method.__name__)
            raise ValueError(str(error)) from error
    return call


@dataclass(frozen=True)
class TransferBounds:
    """Explicit verifier-supplied costs; construction does not authenticate them."""
    usb_upper_ns: int
    packing_upper_ns: int


@dataclass(frozen=True)
class PcDirectWindowV2:
    """Trusted activation policy, not a measured scheduler or motion deadline."""
    consume_window_ns: int


@dataclass(frozen=True)
class ObservedIntervalBoundsV2:
    """Original verifier-retained lifetime bounds; labels/types grant no authority."""
    max_age_ns: int
    source_deadline_ns: int
    dispatch_deadline_ns: int
    previous_deadline_ns: int | None


def _validate_interval_candidate(record, context, now, max_age=None):
    bounds = record.observed_interval_v2
    if type(bounds) is not ObservedIntervalBoundsV2:
        raise ValueError('original observed-interval bounds required')
    age = _integer(bounds.max_age_ns, 'max_age_ns', 1, 100_000_000)
    if max_age is not None and age != max_age:
        raise ValueError('original configured progress age differs')
    _integer(bounds.source_deadline_ns, 'source_deadline_ns')
    _integer(bounds.dispatch_deadline_ns, 'dispatch_deadline_ns')
    if bounds.previous_deadline_ns is not None:
        _integer(bounds.previous_deadline_ns, 'previous_deadline_ns')
    dispatch = _integer(record.dispatch_lower_ns, 'dispatch_lower_ns')
    lower = _integer(record.completion_lower_ns, 'completion_lower_ns')
    upper = _integer(record.completion_upper_ns, 'completion_upper_ns')
    if not dispatch <= lower <= upper <= now:
        raise ValueError('original observed interval is not ordered')
    parsed = envelope.validate_message(record.candidate_raw, producer='ai_controller',
        consumer='control_broker', context=context, now_ns=now,
        enable_completion_interval=True, completion_bounds=dict(max_age_ns=age,
            source_deadline_ns=bounds.source_deadline_ns,
            dispatch_deadline_ns=bounds.dispatch_deadline_ns,
            previous_deadline_ns=bounds.previous_deadline_ns))
    doc = parsed.document
    if (doc['basis'] != 'host_dispatch_to_complete_result_observed_v1' or
            doc['completion_observed_interval_ns']['lower_ns'] != dispatch or
            doc['completion_observed_interval_ns']['upper_ns'] != upper):
        raise ValueError('candidate differs from retained original dispatch/RESULT bounds')
    return parsed


@dataclass(frozen=True)
class Completion:
    generation: int
    source: object
    clock_domain: object
    candidate_raw: bytes
    invocation_id: int
    dispatch_lower_ns: int
    completion_lower_ns: int
    completion_upper_ns: int
    deadline_ns: int
    observed_interval_v2: ObservedIntervalBoundsV2 | None = None


@dataclass(frozen=True)
class SlotGrant:
    """One verified activation/window association, not a caller credential."""
    generation: int
    window_index: int


@dataclass(frozen=True)
class Selection:
    generation: int
    context_raw: bytes
    mode: str
    window_index: int
    slot_start_ns: int
    deadline_ns: int
    ready_ns: int
    sample_lower_ns: int
    candidate_id: int
    invocation_id: int
    candidate_raw: bytes


@dataclass(frozen=True)
class PcDirectWindowSelection(Selection):
    consumed_at_ns: int
    window_close_ns: int


@dataclass(frozen=True)
class _Observation:
    raw: bytes
    sample_lower_ns: int | None
    receipt_upper_ns: int


@dataclass(frozen=True)
class _Completed:
    record: Completion
    observed_seq: int
    candidate_id: int
    fingerprint: tuple


class LatestCompletedMailbox:
    """Single serialized owner, one pending result and bounded identity history.

    STOP never reactivates an old session. A new object cannot independently
    establish global/restart session uniqueness; the real BOOT provider must.
    plan() is diagnostic scheduling only. consume() additionally requires exact
    selected-slot time; its return still grants no permission to send or move.
    """
    def __init__(self, profile_document):
        errors = boot.validate_document(profile_document)
        if errors:
            raise ValueError('; '.join(errors))
        self._document = json.loads(boot.canonical_bytes(profile_document))
        self._digest = boot.canonical_sha256(self._document).hex()
        self._sessions = set()
        self._generation = 0
        self._time_high = 0
        self._stopped = True
        self._reason = 'not_activated'
        self._observations = OrderedDict()
        self._last_observed = None
        self._pending = self._completed = None
        self._last_slot = -1
        self._pc_direct_window_v2 = None

    def _halt(self, reason):
        self._stopped, self._reason = True, reason
        self._pending = None
        self._observations.clear()

    def _time(self, now):
        _integer(now, 'now_ns')
        if now < self._time_high:
            raise ValueError('host clock regressed')
        self._time_high = now
        return now

    def _active(self):
        if self._stopped:
            raise ValueError('activation is stopped')

    @_entry
    def activate(self, context_raw, *, generation, slot_origin_ns, source,
                 clock_domain, bounds, now_ns, pc_direct_window_v2=None,
                 enable_completion_interval_v2=False):
        self._halt('activation_replaced')
        if type(enable_completion_interval_v2) is not bool:
            raise ValueError('strict interval opt-in required')
        self._enable_completion_interval_v2 = enable_completion_interval_v2
        now = self._time(now_ns)
        generation = _integer(generation, 'generation', 1)
        origin = _integer(slot_origin_ns, 'slot_origin_ns')
        if generation <= self._generation or origin > now:
            raise ValueError('fresh generation and established slot origin required')
        if type(context_raw) is not bytes:
            raise ValueError('immutable context bytes required')
        context = envelope._parse_message(context_raw)
        envelope._check_context_argument(context, envelope._validators()[1])
        if (context['boot_sha256'] != self._digest or context['topology_id'] not in (1, 2)
                or context['session'] in self._sessions or len(self._sessions) >= MAX_ACTIVATIONS):
            raise ValueError('new session, matching full BOOT and supported mode required')
        if bounds is not None:
            if type(bounds) is not TransferBounds:
                raise ValueError('explicit bounds record required')
            _integer(bounds.usb_upper_ns, 'usb_upper_ns')
            _integer(bounds.packing_upper_ns, 'packing_upper_ns')
        profile = 'fast_9600' if context['transport_profile_id'] == 1 else 'stress_300'
        if pc_direct_window_v2 is not None:
            if type(pc_direct_window_v2) is not PcDirectWindowV2 or context['topology_id'] != 2:
                raise ValueError('explicit PC_DIRECT v2 activation policy required')
            width = _integer(pc_direct_window_v2.consume_window_ns, 'consume_window_ns', 1)
            first = _integer(boot.slot_start_ms(self._document, profile, 'control_primary') * NS_PER_MS,
                             'first slot offset')
            period = _integer(self._document['profiles'][profile]['window_ms'] * NS_PER_MS,
                              'window period', 1)
            if width >= period:
                raise ValueError('consume window must be shorter than fixed period')
            _integer(origin + first + width, 'first window close')
            self._window_first, self._window_period = first, period
        self._pc_direct_window_v2 = pc_direct_window_v2
        self._sessions.add(context['session'])
        self._generation, self._origin, self._started = generation, origin, now
        self._context_raw, self._context = bytes(context_raw), context
        self._source, self._clock_domain, self._bounds = source, clock_domain, bounds
        self._profile = 'fast_9600' if context['transport_profile_id'] == 1 else 'stress_300'
        self._mode = 'HIL_PC_FPGA' if context['topology_id'] == 1 else 'PC_DIRECT'
        self._age_cap = (1500 if context['transport_profile_id'] == 1 else 12000) * NS_PER_MS
        self._observations.clear()
        self._last_observed = None
        self._pending = self._completed = None
        self._last_slot = -1
        self._stopped, self._reason = False, 'active_no_completion'

    @_entry
    def observe(self, raw, *, sample_lower_ns, now_ns):
        now = self._time(now_ns)
        self._active()
        if type(raw) is not bytes:
            raise ValueError('immutable observation bytes required')
        parsed = envelope.validate_message(raw, producer='hardware_bridge',
            consumer='world_authority', context=self._context, now_ns=now)
        if parsed.kind not in ('telem_observation', 'event_observation'):
            raise ValueError('TELEM/EVENT observation required')
        doc = parsed.document
        mapped = doc['adc_last_interval_ns'] if parsed.kind == 'telem_observation' else doc['trigger_sample_interval_ns']
        if sample_lower_ns is not None:
            _integer(sample_lower_ns, 'sample_lower_ns')
            native = doc.get('native_em_interval_ns')
            if (mapped is None or sample_lower_ns > mapped['lower_ns'] or sample_lower_ns > now
                    or (native is not None and sample_lower_ns > native['lower_ns'])):
                raise ValueError('unknown/nonconservative acquisition mapping')
        receipt = doc['receipt_interval_ns']
        if receipt['lower_ns'] < self._started or receipt['upper_ns'] > now:
            raise ValueError('observation outside activation or host receipt time')
        seq = doc['observed_seq']
        observation = _Observation(raw, sample_lower_ns, receipt['upper_ns'])
        if seq in self._observations:
            if self._observations[seq] != observation:
                raise ValueError('changed duplicate observation')
            return False
        if self._last_observed is not None:
            advance = seq - self._last_observed
            if not 0 < advance < 32768:
                raise ValueError('old, half-range or wrapped observation sequence')
        self._observations[seq] = observation
        self._last_observed = seq
        if len(self._observations) > MAX_OBSERVATIONS:
            self._observations.popitem(last=False)
        return True

    @_entry
    def complete(self, record, *, now_ns):
        now = self._time(now_ns)
        self._active()
        if (type(record) is not Completion or record.generation != self._generation
                or type(record.generation) is not int or record.source is not self._source
                or record.clock_domain is not self._clock_domain or type(record.candidate_raw) is not bytes):
            raise ValueError('original activation/source/clock/completion association required')
        for name in ('invocation_id','dispatch_lower_ns','completion_lower_ns','completion_upper_ns','deadline_ns'):
            _integer(getattr(record, name), name, 1 if name == 'invocation_id' else 0)
        if self._enable_completion_interval_v2:
            parsed = _validate_interval_candidate(record, self._context, now)
            if record.deadline_ns != parsed.valid_until_ns:
                raise ValueError('completion deadline differs from retained original caps')
        else:
            if record.observed_interval_v2 is not None:
                raise ValueError('observed interval requires explicit activation opt-in')
            parsed = envelope.validate_message(record.candidate_raw, producer='ai_controller',
                consumer='control_broker', context=self._context, now_ns=now)
        if parsed.kind != 'model_candidate' or parsed.document['target']['action'] == 0:
            raise ValueError('non-STOP model candidate required; STOP is a separate event')
        doc = parsed.document
        seq = doc['observation']['observed_seq']
        fingerprint = (record.generation, record.candidate_raw, record.invocation_id,
            record.dispatch_lower_ns, record.completion_lower_ns, record.completion_upper_ns, record.deadline_ns)
        if self._enable_completion_interval_v2:
            fingerprint += (record.observed_interval_v2,)
        last = self._completed
        if last is not None:
            if fingerprint == last.fingerprint:
                return False  # Preserved after consume; never reinstalls pending.
            if doc['candidate_id'] == last.candidate_id or record.invocation_id == last.record.invocation_id:
                raise ValueError('conflicting duplicate completion identity')
            if (seq < last.observed_seq or doc['candidate_id'] < last.candidate_id
                    or record.invocation_id < last.record.invocation_id):
                return False  # Delayed old completion cannot displace a newer result.
            if seq - last.observed_seq >= 32768:
                raise ValueError('ambiguous observation ordering')
        observation = self._observations.get(seq)
        if observation is None:
            raise ValueError('completion lacks retained original observation')
        if self._enable_completion_interval_v2:
            if observation.sample_lower_ns is None:
                raise ValueError('original observation acquisition bound unavailable')
            source_cap = _integer(observation.sample_lower_ns + self._age_cap, 'source cap')
            if record.observed_interval_v2.source_deadline_ns > source_cap:
                raise ValueError('source bound exceeds original observation lifetime')
            completion_ordered = record.completion_lower_ns <= record.completion_upper_ns
        else:
            completion_ordered = record.completion_lower_ns <= doc['completed_monotonic_ns'] <= record.completion_upper_ns
        if not (self._started <= record.dispatch_lower_ns <= record.completion_lower_ns
                and completion_ordered and record.completion_upper_ns <= now
                and observation.receipt_upper_ns <= record.dispatch_lower_ns
                and now < record.deadline_ns):
            raise ValueError('original causal completion timeline/deadline required')
        entry = _Completed(record, seq, doc['candidate_id'], fingerprint)
        self._pending = self._completed = entry
        self._reason = 'completion_pending'
        return True

    def _plan(self, now, grant):
        if self._stopped or self._pending is None:
            return None
        if grant is None:
            return None
        if type(grant) is not SlotGrant:
            raise ValueError('activation/window grant association required')
        _integer(grant.generation, 'grant generation', 1)
        _integer(grant.window_index, 'grant window')
        if (grant.generation != self._generation or self._source is None
                or self._clock_domain is None or self._bounds is None):
            return None
        entry = self._pending
        observation = self._observations.get(entry.observed_seq)
        if observation is None or observation.sample_lower_ns is None:
            return None
        record = entry.record
        deadline = min(record.deadline_ns, observation.sample_lower_ns + self._age_cap)
        ready = record.completion_upper_ns + self._bounds.usb_upper_ns + self._bounds.packing_upper_ns
        if max(now, ready) >= deadline:
            return None
        relative_ready = Fraction(max(now, ready) - self._origin, NS_PER_MS)
        relative_deadline = Fraction(deadline - self._origin, NS_PER_MS)
        action = boot.late_candidate_action(self._document, self._profile,
            relative_ready, relative_deadline)
        if action['action'] == 'stop':
            return None
        start_ms = action['start_ms'] if action['action'] == 'send' else action['deferred_start_ms']
        start_ns = self._origin + start_ms * NS_PER_MS
        if Fraction(start_ns).denominator != 1:
            raise ValueError('legal slot cannot be represented in integer nanoseconds')
        start_ns = int(start_ns)
        # late_candidate_action's ready<=start branch does NOT check deadline.
        if start_ns >= deadline or start_ns < max(now, ready):
            return None
        first_ms = boot.slot_start_ms(self._document, self._profile, 'control_primary')
        window_ms = self._document['profiles'][self._profile]['window_ms']
        window = Fraction(start_ms - first_ms, window_ms)
        if window.denominator != 1 or window < 0:
            raise ValueError('not a complete fixed legal slot')
        window = int(window)
        if window != grant.window_index or window <= self._last_slot:
            return None
        return Selection(self._generation, self._context_raw, self._mode, window,
            start_ns, deadline, ready, observation.sample_lower_ns, entry.candidate_id,
            record.invocation_id, record.candidate_raw)

    @_entry
    def plan(self, now_ns, *, grant=None):
        if self._pc_direct_window_v2 is not None:
            raise ValueError('legacy plan cannot use a PC_DIRECT v2 activation')
        return self._plan(self._time(now_ns), grant)

    @_entry
    def consume(self, now_ns, *, grant=None):
        if self._pc_direct_window_v2 is not None:
            raise ValueError('legacy consume cannot use a PC_DIRECT v2 activation')
        selected = self._plan(self._time(now_ns), grant)
        if selected is None or now_ns != selected.slot_start_ns:
            return None
        self._last_slot = selected.window_index
        self._pending = None
        self._reason = 'completion_consumed'
        return selected

    @_entry
    def consume_pc_direct_v2(self, now_ns, *, grant=None):
        now = self._time(now_ns)
        if self._pc_direct_window_v2 is None:
            raise ValueError('PC_DIRECT v2 consume requires its activation policy')
        if self._stopped or self._pending is None or grant is None:
            return None
        if type(grant) is not SlotGrant:
            raise ValueError('activation/window grant association required')
        generation = _integer(grant.generation, 'grant generation', 1)
        window = _integer(grant.window_index, 'grant window')
        if (generation != self._generation or self._source is None
                or self._clock_domain is None or self._bounds is None or window <= self._last_slot):
            return None
        # Only the original grant index locates the window. now/ready never
        # choose another slot, move origin, or renew any original deadline.
        offset = _integer(window * self._window_period, 'window offset')
        start = _integer(self._origin + self._window_first + offset, 'window start')
        close = _integer(start + self._pc_direct_window_v2.consume_window_ns, 'window close')
        entry = self._pending
        observation = self._observations.get(entry.observed_seq)
        if observation is None or observation.sample_lower_ns is None:
            return None
        record = entry.record
        sample_deadline = _integer(observation.sample_lower_ns + self._age_cap, 'sample deadline')
        deadline = min(record.deadline_ns, sample_deadline)
        ready = _integer(record.completion_upper_ns + self._bounds.usb_upper_ns
                         + self._bounds.packing_upper_ns, 'ready time')
        if ready > start or not start <= now < min(close, deadline):
            return None
        selected = PcDirectWindowSelection(self._generation, self._context_raw, self._mode,
            window, start, deadline, ready, observation.sample_lower_ns, entry.candidate_id,
            record.invocation_id, record.candidate_raw, now, close)
        self._last_slot = window
        self._pending = None
        self._reason = 'completion_consumed'
        return selected

    @_entry
    def stop(self, reason='stop'):
        self._halt(reason if type(reason) is str else 'stop')

    def snapshot(self):
        return {'stopped':self._stopped, 'reason':self._reason,
            'generation':self._generation, 'retired_session_count':len(self._sessions),
            'observation_count':len(self._observations),
            'observation_sequences':list(self._observations),
            'pending_candidate_id':None if self._pending is None else self._pending.candidate_id,
            'candidate_high_water':None if self._completed is None else self._completed.candidate_id,
            'last_consumed_window':self._last_slot, 'host_time_high_water_ns':self._time_high}

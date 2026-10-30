"""Private PC_DIRECT original-event adapter; no production providers installed.

Records here are correlation containers, never authentication. The composition
alone supplies its original verifier results and refreshed owner-clock readings.
The adopted mailbox remains policy, and the runtime/executor remain authority.
"""
from dataclasses import dataclass
from pathlib import Path

from ...integration import boot_profile, candidate_mailbox as mailbox, host_envelope
from .pc_direct_runtime import BootBinding

_MAX_NS = (1 << 63) - 1


def _bounded(value, minimum=0):
    if type(value) is not int or not minimum <= value <= _MAX_NS:
        raise ValueError('strict bounded candidate-owner integer required')
    return value


@dataclass(frozen=True)
class _CompletedInference:
    """Original completion-verifier output; source/domain are identity checks."""
    boot: BootBinding
    source: object
    clock_domain: object
    candidate_raw: bytes
    invocation_id: int
    dispatch_lower_ns: int
    completion_lower_ns: int
    completion_upper_ns: int
    observed_interval_v2: mailbox.ObservedIntervalBoundsV2 | None = None


@dataclass(frozen=True)
class _MailboxActivation:
    """Original BOOT schedule/transfer verifier output; no inferred defaults."""
    boot: BootBinding
    source: object
    clock_domain: object
    slot_origin_ns: int
    usb_upper_ns: int
    packing_upper_ns: int


@dataclass(frozen=True)
class _VerifiedSlot:
    """Original current-window verifier output; construction grants nothing."""
    boot: BootBinding
    source: object
    clock_domain: object
    window_index: int


@dataclass
class _InputTransaction:
    """One synchronous observation or command transaction, cleared on exit."""
    kind: str
    slot_event: object = None
    observation_record: object = None
    selected_proof: object = None
    request_raw: bytes | None = None


class _CandidateOwner:
    """One pending original proof, one committed association; no reset/recovery."""
    def __init__(self, boot, source, clock_domain, model_hash, max_age, started,
                 activation, now, *, pc_direct_window_v2=None,
                 enable_completion_interval_v2=False):
        self._boot, self._source, self._clock = boot, source, clock_domain
        self._model, self._age, self._started = model_hash, _bounded(max_age,1), _bounded(started)
        if type(enable_completion_interval_v2) is not bool:
            raise ValueError('strict interval opt-in required')
        self._enable_completion_interval_v2 = enable_completion_interval_v2
        self._pending = self._current = None
        self._retired = False
        if (type(activation) is not _MailboxActivation or activation.boot is not boot
                or activation.source is not source or activation.clock_domain is not clock_domain):
            raise ValueError('original BOOT schedule/source/clock evidence required')
        origin = _bounded(activation.slot_origin_ns)
        bounds = mailbox.TransferBounds(_bounded(activation.usb_upper_ns),
                                        _bounded(activation.packing_upper_ns))
        self._context = host_envelope._parse_message(boot.context_json)
        if self._context['topology_id'] != 2:
            raise ValueError('candidate owner is PC_DIRECT only; no HIL capture authority')
        document = boot_profile.load_document(Path(__file__).resolve().parents[2] / 'docs/boot_profiles.json')
        self._mailbox = mailbox.LatestCompletedMailbox(document)
        self._mailbox.activate(boot.context_json,generation=boot.generation,slot_origin_ns=origin,
            source=source,clock_domain=clock_domain,bounds=bounds,now_ns=_bounded(now),
            pc_direct_window_v2=pc_direct_window_v2,
            enable_completion_interval_v2=enable_completion_interval_v2)
        self._pc_direct_window_v2 = pc_direct_window_v2

    def _active(self):
        if self._retired:
            raise ValueError('candidate owner permanently retired')

    def retire(self):
        self._retired = True
        self._pending = self._current = None
        self._mailbox.stop('composition retired')

    def observe(self, record, now):
        self._active()
        if record.boot is not self._boot:
            raise ValueError('original runtime-admitted observation required')
        return self._mailbox.observe(record.raw,sample_lower_ns=record.sample_lower_ns,now_ns=now)

    def offer(self, proof, now):
        self._active()
        if (type(proof) is not _CompletedInference or proof.boot is not self._boot
                or proof.source is not self._source or proof.clock_domain is not self._clock
                or type(proof.candidate_raw) is not bytes):
            raise ValueError('original verified completion/source/clock required')
        now = _bounded(now)
        invocation = _bounded(proof.invocation_id,1)
        dispatch = _bounded(proof.dispatch_lower_ns)
        lower,upper = _bounded(proof.completion_lower_ns),_bounded(proof.completion_upper_ns)
        if self._enable_completion_interval_v2:
            parsed = mailbox._validate_interval_candidate(proof, self._context, now, self._age)
        else:
            if proof.observed_interval_v2 is not None:
                raise ValueError('observed interval requires explicit owner opt-in')
            parsed = host_envelope.validate_message(proof.candidate_raw,producer='ai_controller',
                consumer='control_broker',context=self._context,now_ns=now)
        if parsed.kind != 'model_candidate' or parsed.document['model_sha256'] != self._model:
            raise ValueError('original approved-model candidate required')
        if self._enable_completion_interval_v2:
            if not self._started <= dispatch <= lower <= upper <= now:
                raise ValueError('original ordered observation timeline required')
            deadline = _bounded(parsed.valid_until_ns)
        else:
            claimed = _bounded(parsed.document['completed_monotonic_ns'])
            if not self._started <= dispatch <= lower <= claimed <= upper <= now:
                raise ValueError('original ordered completion timeline required')
            deadline = _bounded(lower + self._age)
        projected = mailbox.Completion(self._boot.generation,self._source,self._clock,
            proof.candidate_raw,invocation,dispatch,lower,upper,deadline,proof.observed_interval_v2)
        accepted = self._mailbox.complete(projected,now_ns=now)
        if accepted:
            self._pending = proof  # Retain exactly the original verifier object.
        return accepted

    def duplicate_proof(self, raw):
        self._active()
        if self._current is not None and raw == self._current[0]:
            return self._current[1]
        return None

    def select(self, raw, grant, now):
        self._active()
        if (type(grant) is not _VerifiedSlot or grant.boot is not self._boot
                or grant.source is not self._source or grant.clock_domain is not self._clock):
            raise ValueError('original current-slot/source/clock evidence required')
        window = _bounded(grant.window_index)
        consume = (self._mailbox.consume if self._pc_direct_window_v2 is None
                   else self._mailbox.consume_pc_direct_v2)
        selected = consume(now,grant=mailbox.SlotGrant(self._boot.generation,window))
        if selected is None:
            raise ValueError('no proposal at the configured current legal slot/window')
        proof,self._pending = self._pending,None  # Consumption is irreversible.
        if (proof is None or selected.mode != 'PC_DIRECT'
                or selected.generation != self._boot.generation
                or selected.context_raw != self._boot.context_json
                or selected.candidate_raw != proof.candidate_raw
                or selected.invocation_id != proof.invocation_id):
            raise ValueError('selected proposal lost its original completion identity')
        # The unchanged ProgressGate additionally verifies complete broker bytes,
        # candidate/observation/target equality and original issue/interval bounds.
        return proof

    def commit(self, raw, proof):
        self._active()
        if type(raw) is not bytes or type(proof) is not _CompletedInference:
            raise ValueError('original admitted command/proof required')
        if self._current is not None and raw == self._current[0]:
            if proof is not self._current[1]:
                raise ValueError('duplicate lost original committed proof identity')
            return
        self._current = (raw,proof)

"""C46 private original-owner bridge; Python identity is not a security boundary.

Only original trusted admission code may retain the association. No public
factory accepts callbacks, PIDs, authority JSON, snapshots or foreign completions.
Default composition production channels remain unavailable.
"""
from dataclasses import dataclass
import hashlib,json,threading
from .mechanics import need,uint,encode,pair_state,quantize_target,BASIS
from .fixed import projection,verifier
from ....integration import host_clock,host_envelope,completion_interval,motion,candidate_mailbox
from ....integration.cpu_invocation_transcript import InvocationIdentity,_ActorRecord
from ...isolation.actor_owner import ActorOwner
from ...isolation.actor_invocation_series import SerialInvocationLimits,_OriginalSerialSeries
from ..candidate_owner import _InputTransaction,_CompletedInference
from ..pc_direct_runtime import VerifiedObservation
from ..source_projection_v1.provider import ProjectionSession
from ..source_projection_v1.assembler import Producer,_root

MANIFEST='cb971d321bcdd3dcb6a7b85fdd9e08171c995feb62fab3f995bc7f50fdf97a8a'
FILES={'c37_entry.py':'899b843111a1b9278e4c5ee16b11d4493c35c1cb0bca328a57f164c3f0c11c74','c37_package.py':'60e26bc8ae9ee0ba1fba8bcea358b4bfad8be2f3a58ccb360e767b6886d62f16','frozen_c28.py':'70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4','package-manifest.json':MANIFEST}
_KEY=object()

@dataclass(frozen=True)
class OwnedInvocationPolicy:
    operation_id:str
    request_hash:str
    tested_commit:str
    max_invocations:int
    max_reads:int
    max_polls:int
    duration_ms:int
    def check(self):
        need(type(self) is OwnedInvocationPolicy,'exact owned policy')
        need(type(self.max_invocations) is int and 2<=self.max_invocations<=16,'original serial K2..16')
        need(type(self.max_reads) is int and 1<=self.max_reads<=256,'finite reads1..256')
        need(type(self.max_polls) is int and 1<=self.max_polls<=65536,'finite polls1..65536')
        need(type(self.duration_ms) is int and 1<=self.duration_ms<=100,'prospective duration1..100ms')
        InvocationIdentity(self.operation_id,self.request_hash,self.tested_commit,MANIFEST,'check',1,'check')

class _Association:
    def __setattr__(self,name,value):raise AttributeError('retained association is immutable')
    def __init__(self,key,**values):
        need(key is _KEY,'original admission callsite required');self.__dict__.update(values)

class _CompletionEvent:
    __slots__=()
    def __init__(self,key):need(key is _KEY,'original pair required')

def _root_guard(owner,association):
    session=association.session;session._check()
    link=session._link;book=session._book;executor=link.executor;root=executor._root
    need(link is owner._world_action_link and link.composition is owner and executor is owner._executor,'original Root/link/executor')
    need(book._root is root and root is not None,'original current Root required')
    return (link,book,executor,root,encode(_root(root)))

def _same_root(owner,association,guard):
    actual=_root_guard(owner,association)
    need(all(x is y for x,y in zip(actual[:4],guard[:4])) and actual[4]==guard[4],'pending Root/pose/revocation changed')


def _retain_original_association(owner,event,record,*,session,capture_ref,sample_ref,
        current_read,registry_ref,history_refs,mapping_receipt,source_bound_receipt,
        dispatch_bound_receipt,source_deadline_ns,dispatch_deadline_ns,
        previous_action,previous_deadline_ns):
    """Original hardware/provider admission hook ONLY; not a verifier API.

    Root must already possess the actual cross-format mapping and bound receipts
    at this callsite. This function retains identities/bytes; it cannot establish
    that an arbitrary object is a real physical/source fact. No installed default
    provider calls it. Do not expose it to controller or child IPC.
    """
    from ..actor_composition import ActorComposition
    need(type(owner) is ActorComposition and owner._busy and owner._state=='ACTIVE','active original composition entry')
    tx=owner._input_transaction
    need(type(tx) is _InputTransaction and tx.kind=='observation' and tx.original_event is event and tx.owned_association is None,'original active observation allocation')
    need(type(record) is VerifiedObservation and record.boot is owner._boot,'exact original verified observation')
    need(type(session) is ProjectionSession and type(session._producer) is Producer,'original C42 session/producer')
    session._check();need(session._link is owner._world_action_link and session._link.composition is owner,'same original world link')
    rows=[r for r in session._producer._captures if r[0] is capture_ref]
    need(len(rows)==1 and rows[0][1] is sample_ref,'same retained capture/sample')
    need(all(x is not None for x in (mapping_receipt,source_bound_receipt,dispatch_bound_receipt)),'original mapping and bound receipts required')
    need(type(history_refs) is tuple and len(history_refs)<=31,'fixed original history')
    for x in (source_deadline_ns,dispatch_deadline_ns):uint(x,1)
    if previous_deadline_ns is None:need(previous_action is None,'explicit no prior same-action cap')
    else:
        uint(previous_deadline_ns,1)
        need(previous_action is owner._progress.bound and previous_action is not None and previous_action.deadline_ns==previous_deadline_ns,'actual same-action previous bound')
    candidate=rows[0][2];fields=rows[0][3]
    # Full original bytes and identities are held, not caller hash-only proof.
    capture_raw=fields.get('capture_raw');need(type(capture_raw) is str,'original raw capture required')
    identity=candidate['observation_identity']
    need(hashlib.sha256(capture_raw.encode()).hexdigest()==identity['capture_sha256'],'capture bytes changed')
    observation=host_envelope._parse_message(record.raw)
    need(observation['context']==host_envelope._parse_message(owner._boot.context_json),'original observation BOOT context')
    # Context namespaces differ: preserve both; never relabel raw4 as TELEM means.
    tx.owned_association=_Association(_KEY,owner=owner,tx=tx,event=event,record=record,
        session=session,capture_ref=capture_ref,sample_ref=sample_ref,current_read=current_read,
        registry_ref=registry_ref,history_refs=history_refs,mapping_receipt=mapping_receipt,
        source_bound_receipt=source_bound_receipt,dispatch_bound_receipt=dispatch_bound_receipt,
        source_deadline_ns=source_deadline_ns,dispatch_deadline_ns=dispatch_deadline_ns,
        previous_action=previous_action,previous_deadline_ns=previous_deadline_ns,
        candidate_bytes=encode(candidate),capture_bytes=capture_raw.encode(),observation_bytes=record.raw,
        observation_key=encode({'context':observation['context'],'observed_seq':observation['observed_seq']}),
        source=owner._channels,clock=owner._clock,boot=owner._boot,used=False)

class _OwnedInvocationAdapter:
    def __init__(self,key,owner):
        from ..actor_composition import ActorComposition
        need(key is _KEY and type(owner) is ActorComposition,'composition private factory')
        self.owner=owner;self.actor=owner._actor;self.source=owner._channels;self.clock=owner._clock
        self.policy=owner._config.owned_invocation_v1;self.policy.check()
        self.pending=None;self.ready=None;self._retained=None;self.records=[];self.associations=[];self.failed=False
        self.thread=threading.get_ident();self._check()
        actor=self.actor
        need(actor._invocation is None and actor._invocation_series is None,'fresh original serial actor only')
        actor.begin_serial_invocations(SerialInvocationLimits(self.policy.max_invocations,
            self.policy.max_invocations*16384,self.policy.max_invocations*18440,
            self.policy.max_invocations*self.policy.max_reads,'ready_result_frames_v1'))
        self.series=actor._invocation_series

    def _check(self):
        o=self.owner;a=self.actor
        need(not self.failed and threading.get_ident()==self.thread and o._busy,'same live owner entry')
        need(o._actor is a and type(a) is ActorOwner and a._registry is o._registry and a._registry._contains(a),'original composition actor')
        need(o._channels is self.source and o._clock is self.clock and type(self.clock) is host_clock.QpcHostClock and o._host_clock is self.clock and a._registry._clock_binding is self.clock,'same fixed QPC/source')
        need(a._boot is o._boot and a._runtime_owner is o._runtime and a._executor_owner is o._executor,'same original boot/runtime/executor')
        need(o._config.enable_completion_interval_v2 is True and o._config.ai_model_sha256==FILES['frozen_c28.py'],'explicit fixed interval/core identity')
        need(o._config.owned_invocation_v1 is self.policy,'policy replacement')
        need(a._policy is o._config.actor_policy and a._policy.executable=='runtime/python.exe','fixed original executable')
        need(a._policy.arguments==('-I','-B','c37_entry.py','--actor-stdio-v2','--max-invocations',str(self.policy.max_invocations),'--request-bytes','16384'),'fixed finite original entry')
        staged=dict(a._policy.files);need(all(staged.get(k)==v for k,v in FILES.items()),'fixed C44 package bytes')
        o._active();o._checkpoint();self.clock._check()
        return o._progress_time()

    def begin(self,tx):
        try:
            now=self._check();o=self.owner
            need(self.pending is None and self.ready is None and len(self.records)<self.policy.max_invocations,'one bounded serial invocation')
            need(type(tx) is _InputTransaction and o._input_transaction is tx and tx.kind=='observation','active original transaction')
            a=tx.owned_association
            need(type(a) is _Association and a.owner is o and a.tx is tx and not any(a is x for x in self.associations) and a.record is tx.observation_record,'original admitted mapping required')
            need(a.source is self.source and a.clock is self.clock and a.boot is o._boot and a.event is tx.original_event,'source/clock/event replacement')
            need(not any(x.record is a.record or x.observation_bytes==a.observation_bytes for x in self.associations),'observation already reserved')
            obs=host_envelope._parse_message(a.observation_bytes);stored=o._runtime._observations.get(obs['observed_seq'])
            need(stored is not None and stored.raw==a.record.raw==a.observation_bytes and stored.sample_lower_ns==a.record.sample_lower_ns,'runtime did not retain exact admitted observation')
            a.session._check();rows=[r for r in a.session._producer._captures if r[0] is a.capture_ref]
            need(len(rows)==1 and rows[0][1] is a.sample_ref and encode(rows[0][2])==a.candidate_bytes and rows[0][3]['capture_raw'].encode()==a.capture_bytes,'original selected capture changed')
            guard=_root_guard(o,a)
            assembled=a.session.export(current_read=a.current_read,registry_ref=a.registry_ref,candidate_ref=a.capture_ref,history_refs=a.history_refs,enabled=True)
            need(assembled['status']=='ASSEMBLED_UNVALIDATED' and assembled['proof'] is not None,'original full proof unavailable')
            full=assembled['proof'];need(encode(full['candidate'])==a.candidate_bytes,'unrelated selected projection')
            projected=json.loads(projection.project_interval_json(encode(full)))
            need(projected['input_status']=='PROJECTED' and projected['core_ran'] is False and projected['authorization']=='none','no complete host projection')
            _same_root(o,a,guard)
            public=projected['public_input'];verifier.validate_public(public)
            candidate=json.loads(a.candidate_bytes);identity=candidate['observation_identity']
            need(public['observation']['sample_id']==identity['capture_sha256'] and public['observation']['counts']==candidate['channel_counts'] and public['observation']['quality']==candidate['quality'],'projection capture/count/quality mismatch')
            src=public['observation'];need(a.record.sample_lower_ns<=src['adc_qpc_ns'] and (src['em_qpc_ns'] is None or a.record.sample_lower_ns<=src['em_qpc_ns']),'original observation sample lower is not conservative')
            need(now<a.source_deadline_ns<=a.record.sample_lower_ns+o._runtime._age_cap and now<a.dispatch_deadline_ns<=self.actor._run_deadline,'original finite source/dispatch bounds')
            need(a.previous_deadline_ns is None or (a.previous_action is o._progress.bound and a.previous_action.deadline_ns==a.previous_deadline_ns and now<a.previous_deadline_ns),'same action cap changed/expired')
            index=len(self.records)+1
            ident=InvocationIdentity(self.policy.operation_id,self.policy.request_hash,self.policy.tested_commit,MANIFEST,o._boot.run_id,index,self.actor.instance_id)
            ids={k:getattr(ident,k) for k in ('operation_id','run_id','actor_instance_id','invocation_id','tested_commit','package_manifest_sha256')}
            wire=verifier.fixed_request(encode(dict(abi=verifier.ABI,kind='recommend',echo_ids=ids,enabled=True,input=public)))
            # Consume association before journal/write; no failed-operation replay.
            self.associations.append(a)
            options=dict(request_raw=wire,journal_name='c46-invocation-'+str(index)+'.jsonl',max_output_bytes=18440,max_reads=self.policy.max_reads,read_size=8192,io_deadline_ns=a.dispatch_deadline_ns)
            prepare=self.actor.prepare_invocation if index==1 else self.actor.prepare_next_invocation
            prepare(ident,**options);record=self.actor._invocation
            need(type(record) is _ActorRecord and record.owner is self.actor and record.request==wire and record.identity is ident and record.deadline==a.dispatch_deadline_ns,'original invocation identity/deadline')
            self.records.append(record);self.pending=dict(association=a,record=record,wire=wire,ids=ids,public=encode(public),proof=encode(full),caps=(a.source_deadline_ns,a.dispatch_deadline_ns,a.previous_deadline_ns),guard=guard,polls=0)
            self.actor.dispatch_invocation_once()
            return 'PENDING'
        except BaseException:
            self.retire();raise

    def advance(self):
        try:
            now=self._check();p=self.pending
            need(p is not None and self.ready is None,'original pending invocation required')
            a,r=p['association'],p['record'];p['polls']+=1
            need(p['polls']<=self.policy.max_polls and self.actor._invocation is r and r.request==p['wire'] and r.owner is self.actor,'pending owner/budget/request changed')
            need((a.source_deadline_ns,a.dispatch_deadline_ns,a.previous_deadline_ns)==p['caps'] and now<min(x for x in p['caps'] if x is not None),'original cap changed/expired')
            need(a.record.raw==a.observation_bytes and a.source is self.source and a.clock is self.clock,'retained source changed')
            _same_root(self.owner,a,p['guard'])
            self.actor.poll_invocation()
            io=self.actor._pending_io
            if not io.all_settled:return 'PENDING'
            need(type(self.actor._invocation_series) is _OriginalSerialSeries and self.actor._invocation_series is self.series,'original series replaced')
            self.series._known_io(r)
            raw=b''.join(bytes.fromhex(row['raw_hex']) for row in r.reads)
            if pair_state(raw)=='PARTIAL':
                self.actor.read_invocation_once();return 'PENDING'
            # Only original OS-backed pair seal can close the read transcript.
            self.actor.seal_serial_invocation_response_pair()
            ticket=self.series.ledger.tickets[-1]
            need(ticket.record is r and ticket.sealed_frame==raw and ticket.sealed_pair is not None and r._close_attempted and r._close_error is None,'original pair/journal not sealed')
            _same_root(self.owner,a,p['guard'])
            pair=verifier.verify_pair(p['wire'],raw,expected_ids=p['ids'])
            need(pair.result['status']=='RESULT' and pair.result['core_ran'] is True,'child has no usable candidate')
            lower=uint(r.dispatch['raw_call_bracket_ns'][0]);read_lower=uint(r.reads[0]['raw_call_bracket_ns'][0]);upper=uint(ticket.observed_qpc_ns)
            now=self._check();need(lower<=read_lower<=upper<=now,'actual original ordered observation interval')
            public=json.loads(p['public']);target=quantize_target(pair.result['result'],public,host_envelope._profile_name(json.loads(self.owner._boot.context_json)),self.policy.duration_ms,motion)
            doc=dict(schema_version=2,kind='model_candidate',context=json.loads(self.owner._boot.context_json),candidate_id=r.identity.invocation_id,model_sha256=FILES['frozen_c28.py'],observation=json.loads(a.observation_key),target=target,basis=BASIS,completion_observed_interval_ns=dict(lower_ns=lower,upper_ns=upper))
            candidate_raw=encode(doc);caps=dict(max_age_ns=self.owner._config.progress_max_age_ns,source_deadline_ns=p['caps'][0],dispatch_deadline_ns=p['caps'][1],previous_deadline_ns=p['caps'][2])
            validated=completion_interval.validate_message(candidate_raw,legacy=host_envelope,producer='ai_controller',consumer='control_broker',context=doc['context'],now_ns=now,enable_interval=True,bounds=caps)
            issue=self._check();finite=completion_interval.adapt_action_candidate(validated,host_issue_ns=issue,now_ns=issue,previous_deadline_ns=p['caps'][2])
            bounds=candidate_mailbox.ObservedIntervalBoundsV2(**caps)
            proof=_CompletedInference(self.owner._boot,self.source,self.clock,candidate_raw,r.identity.invocation_id,lower,read_lower,upper,bounds)
            _same_root(self.owner,a,p['guard'])
            self.ready=_CompletionEvent(_KEY)
            self._retained=(self.ready,r,proof,finite,p,candidate_raw,bounds)
            self.pending=None
            return self.ready
        except BaseException:
            self.retire();raise

    def _completion(self,event,boot):
        try:
            self.actor._invocation_check()
            now=self._check();held=self._retained
            need(held is not None and type(event) is _CompletionEvent and event is self.ready is held[0] and boot is self.owner._boot,'exact unused original completion event')
            _,record,proof,finite,p,raw,bounds=held
            need(record is self.records[-1] is self.actor._invocation and record.request==p['wire'] and proof.boot is boot and proof.source is self.source and proof.clock_domain is self.clock and proof.candidate_raw==raw and proof.observed_interval_v2 is bounds,'independent retained completion changed')
            _same_root(self.owner,p['association'],p['guard'])
            need(now<min(x for x in p['caps'] if x is not None),'original completion cap expired')
            need(now<finite.candidate.valid_until_ns,'candidate dispatch-age validity expired')
            need(finite.deadline_ns is None or now<finite.deadline_ns,'fixed finite action duration expired')
            return proof,finite
        except BaseException:
            self.retire();raise

    def inspect_candidate(self,event,boot):
        return self._completion(event,boot)[1]

    def verify_completion(self,event,boot):
        proof,_=self._completion(event,boot)
        self.ready=None;self._retained=None
        return proof

    def retire(self):
        self.failed=True;self.pending=None;self.ready=None;self._retained=None


def _from_composition(owner):return _OwnedInvocationAdapter(_KEY,owner)


def _validate_config(config,binding):
    policy=config.owned_invocation_v1
    need(type(policy) is OwnedInvocationPolicy,'exact default-off owned policy')
    policy.check();need(type(binding) is host_clock.QpcHostClock,'original fixed QPC required')
    need(config.enable_completion_interval_v2 is True and 0<config.progress_max_age_ns<=100_000_000,'explicit C45 interval policy')
    need(config.ai_model_sha256==FILES['frozen_c28.py'],'fixed C28 model identity')
    staged=dict(config.actor_policy.files)
    need(all(staged.get(k)==v for k,v in FILES.items()),'fixed C44 manifest/package/core required')
    need(config.actor_policy.executable=='runtime/python.exe' and config.actor_policy.arguments==('-I','-B','c37_entry.py','--actor-stdio-v2','--max-invocations',str(policy.max_invocations),'--request-bytes','16384'),'fixed original package entry')

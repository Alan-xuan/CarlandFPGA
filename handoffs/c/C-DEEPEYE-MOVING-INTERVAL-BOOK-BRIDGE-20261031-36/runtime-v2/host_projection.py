"""C36 host-only interval validation/projection; no planner, clocks or authority.

The full proof is untrusted. A's original provider retains actual provenance.
This module never loads C28 and never creates a completion or movement grant.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace

NOT_VERIFIED_BY_C36_STRUCTURAL_PROJECTION = ('original_receipt_digest_getter_binding', 'original_live_owner_source_BOOT_capture_authentication', 'dispatch_read_completion_freshness_and_one_use_invocation')

CORE_SHA256 = '70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'
MAX_BYTES = 1048576
AGE_NS = 100000000
NS_MS = 1000000
MAX_U63 = (1 << 63)-1
_BASE = Path(__file__).resolve().parent

def _load(name, pin):
    b = (_BASE/name).read_bytes()
    if hashlib.sha256(b).hexdigest() != pin:
        raise ImportError('C36 fixed dependency mismatch')
    return b

_SCHEMA = json.loads(_load('request.schema.json', 'ab1b432e9f337523fd75057fec4647f5eda2569de308e7c777507e05907bdd70'))
_PUBLIC = json.loads(_load('public-view.schema.json', '046b863c6bc07bbaa5396c5b7dfc55fb1febf7bbd0bda29ef79cbd5119f981ed'))
_pred = {}
exec(compile(_load('frozen_source_predicates.py', '7f4eaa649f1669e3f475d6cdbfb92a7ab7dfe1324cfb42719eb34c15f479ccf4'), 'C36_fixed_pure_predicates', 'exec'), _pred)
P = SimpleNamespace(**_pred)

class Rejected(ValueError):
    """A fixed diagnostic code, never source/private error text."""

def _need(condition, code='TEMPORAL_CONTRADICTION'):
    if not condition:
        raise Rejected(code)

def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')

def _tree(x, depth=0, budget=None):
    if budget is None: budget=[0]
    budget[0]+=1
    _need(depth<=16 and budget[0]<=65536, 'BUDGET_EXCEEDED')
    if type(x) is dict:
        _need(len(x)<=32 and all(type(k) is str and len(k)<=96 for k in x), 'BUDGET_EXCEEDED')
        for y in x.values(): _tree(y,depth+1,budget)
    elif type(x) is list:
        _need(len(x)<=1001, 'BUDGET_EXCEEDED')
        for y in x:_tree(y,depth+1,budget)
    elif type(x) is float:_need(math.isfinite(x),'INVALID_JSON')
    else:_need(type(x) in (str,int,bool,type(None)), 'INVALID_JSON')

def _shape(x, spec, doc=_SCHEMA):
    """Only the finite keyword subset in our hash-pinned schema; no remote refs."""
    if '$ref' in spec:return _shape(x,doc['$defs'][spec['$ref'].split('/')[-1]],doc)
    choices=spec.get('anyOf',spec.get('oneOf'))
    if choices is not None:
        matches=0
        for choice in choices:
            try:_shape(x,choice,doc);matches+=1
            except Rejected:pass
        _need(matches==1 if 'oneOf' in spec else matches>0,'INVALID_SHAPE');return
    if 'const' in spec:_need(type(x) is type(spec['const']) and x==spec['const'],'INVALID_SHAPE')
    if 'enum' in spec:_need(any(type(x) is type(y) and x==y for y in spec['enum']),'INVALID_SHAPE')
    typ=spec.get('type')
    if typ is None:return
    expected={'object':dict,'array':list,'string':str,'integer':int,'boolean':bool,'null':type(None)}
    _need(((type(x) is int and abs(x)<=1.7976931348623157e308) or (type(x) is float and math.isfinite(x))) if typ=='number' else type(x) is expected[typ],'INVALID_SHAPE')
    if typ=='object':
        _need(set(spec.get('required',[]))<=set(x) and set(x)<=set(spec['properties']),'INVALID_SHAPE')
        for k,y in x.items():_shape(y,spec['properties'][k],doc)
    elif typ=='array':
        _need(spec.get('minItems',0)<=len(x)<=spec.get('maxItems',32),'BUDGET_EXCEEDED')
        for y in x:_shape(y,spec['items'],doc)
    elif typ=='string':
        _need(spec.get('minLength',0)<=len(x)<=spec.get('maxLength',192),'BUDGET_EXCEEDED')
        if 'pattern' in spec:_need(re.fullmatch(spec['pattern'],x) is not None,'INVALID_SHAPE')
    elif typ in ('integer','number'):
        _need(x>=spec.get('minimum',-math.inf) and x<=spec.get('maximum',math.inf),'INVALID_SHAPE')
        if 'exclusiveMinimum' in spec:_need(x>spec['exclusiveMinimum'],'INVALID_SHAPE')

def _parse(raw):
    _need(type(raw) is bytes and 0<len(raw)<=MAX_BYTES,'BUDGET_EXCEEDED')
    def pairs(items):
        d={}
        for k,v in items:
            _need(k not in d,'INVALID_JSON');d[k]=v
        return d
    def constant(_):raise Rejected('INVALID_JSON')
    try:x=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
    except (UnicodeError,ValueError,RecursionError) as e:
        if isinstance(e,Rejected):raise
        raise Rejected('INVALID_JSON') from None
    _tree(x);_shape(x,_SCHEMA);return x

def _same(a,b,code='IDENTITY_CONTRADICTION'):
    if a is not None and b is not None:_need(a==b,code)

def _le(a,b):
    if a is not None and b is not None:_need(a<=b)

def _eqfields(a,b,fields,code='IDENTITY_CONTRADICTION'):
    if a is not None and b is not None:
        for k in fields:_same(a.get(k),b.get(k),code)

class Check:
    def __init__(self,request):
        self.r=request;self.now=request['now_qpc_ns'];self.missing=set();self.stale=False
        self.spans=[];self.pose_values={};self.root_values={};self.samplemap={};self.emmap={}
    def want(self,value,code='MISSING_ORIGINAL_ASSOCIATION'):
        if value is None:self.missing.add(code)
        return value
    def time(self,t):
        if t is not None:_need(t<=self.now)
    def bracket(self,b):
        if b is None:return
        a,z=b['begin_qpc_ns'],b['end_qpc_ns'];self.time(a);self.time(z);_le(a,z)
    def pose(self,p,rev=None,root=None,revoke=None):
        if p is not None:
            P._pose(p)
            if rev is not None:
                if rev in self.pose_values:_same(p,self.pose_values[rev],'LINEAGE_CONTRADICTION')
                self.pose_values[rev]=p
        if root is not None:
            values=(rev,p,revoke)
            if root in self.root_values:
                for a,b in zip(values,self.root_values[root]):_same(a,b,'LINEAGE_CONTRADICTION')
            old=self.root_values.get(root,(None,None,None))
            self.root_values[root]=tuple(a if a is not None else b for a,b in zip(values,old))
    def span(self,s):
        if s is None:return
        a,z=s['from_qpc_ns'],s['through_qpc_ns'];self.time(a);self.time(z);_le(a,z)
        if 'root_revision' in s:self.pose(None,s['pose_revision'],s['root_revision'])
    def cover(self,span,times,code='SOURCE_TIME_IN_TRANSITION_GAP'):
        if self.want(span) is None:return
        self.span(span)
        a,z=span['from_qpc_ns'],span['through_qpc_ns']
        for endpoint in (a,z):self.want(endpoint)
        for t in times:
            if t is not None and ((a is not None and t<a) or(z is not None and t>z)):self.missing.add(code)
    def usable(self,span):
        if span is not None:
            self.span(span);self.spans.append(span)
    def read(self,x,span=None):
        if x is None:return
        self.bracket(x);self.pose(x['pose'],x['pose_revision'],x['root_revision'],x['revoke_generation'])
        if x['postcheck_complete'] is not True:self.missing.add('MISSING_ORIGINAL_ASSOCIATION')
        for y in x.values():self.want(y)
        if span is not None:
            _eqfields(x,span,('root_revision','pose_revision'),'LINEAGE_CONTRADICTION')
    def scan(self,x):
        """Every supplied time/pose checked even on a missing/default-off path."""
        if isinstance(x,dict):
            if set(x)=={'position_m','orientation_xyzw'}:self.pose(x)
            if 'begin_qpc_ns' in x and 'end_qpc_ns' in x:self.bracket(x)
            if 'from_qpc_ns' in x and 'through_qpc_ns' in x:self.span(x)
            for k,v in x.items():
                if k.endswith('_qpc_ns') or k in ('source_start_monotonic_ns','admission_received_monotonic_ns'):
                    if type(v) is int:self.time(v)
                self.scan(v)
        elif isinstance(x,list):
            for y in x:self.scan(y)
    def source(self,book):
        if self.want(book) is None:return
        if book['state']!='RUNNING' or book['source_state']!='RUNNING':self.missing.add('ACTOR_PENDING_OR_FAILED')
        origin=self.want(book['source_origin_qpc_ns']);self.want(book['snapshot_sha256'])
        previous=None
        for index,s in enumerate(book['samples']):
            key=s['source_sha256'];_need(key not in self.samplemap,'IDENTITY_CONTRADICTION');self.samplemap[key]=s
            _need(s['source_count']==index+1 and s['tick_ms']%10==0 and s['tick_ms']<=10000,'LINEAGE_CONTRADICTION')
            if previous is None:_need(s['tick_ms']==0,'LINEAGE_CONTRADICTION')
            else:_need(s['tick_ms']>previous['tick_ms'],'LINEAGE_CONTRADICTION');_le(previous['finish_qpc_ns'],s['opened_qpc_ns'])
            if origin is not None:_same(s['nominal_qpc_ns'],origin+s['tick_ms']*NS_MS)
            n=s['nominal_qpc_ns'];observed=self.want(s['observed_source_qpc_ns']);opened=self.want(s['opened_qpc_ns']);finish=self.want(s['finish_qpc_ns'])
            if observed is not None:_need(n<=observed<n+10000000)
            _le(observed,opened);_le(opened,finish)
            if s['status']!='complete':self.missing.add('ACTOR_PENDING_OR_FAILED')
            span=self.want(s['numerical_pose_span']);self.usable(span)
            adc=self.want(s['adc']);read=self.want(s['pose_reads']['adc']);emread=s['pose_reads']['em']
            for rr in (read,emread):
                if rr is None:continue
                self.read(rr,span);_le(opened,rr['begin_qpc_ns']);_le(n,rr['begin_qpc_ns'])
                self.cover(span,[n,rr['begin_qpc_ns'],rr['end_qpc_ns']])
            if s['tick_ms']%50==0:self.want(emread)
            else:_need(emread is None,'LINEAGE_CONTRADICTION')
            if adc is not None:
                self.bracket(adc)
                _same(adc['previous_adc_tick_ms'],None if previous is None else previous['tick_ms'])
                if previous is None:_need(adc['previous_adc_tick_ms'] in (None,-1),'LINEAGE_CONTRADICTION')
                if adc['profile_tick_observed'] is not True or adc['postcheck_complete'] is not True:self.missing.add('MISSING_ORIGINAL_ASSOCIATION')
                for k in ('begin_qpc_ns','end_qpc_ns','end_attempt_qpc_ns'):self.want(adc[k])
                _same(adc['end_attempt_qpc_ns'],adc['end_qpc_ns']);_le(opened,adc['begin_qpc_ns']);_le(adc['end_qpc_ns'],finish)
                if read is not None:_le(read['end_qpc_ns'],adc['begin_qpc_ns'])
                self.cover(span,[n,adc['begin_qpc_ns'],adc['end_qpc_ns'],finish])
            held=s['held_em_association']
            if held is not None:
                em=self.want(held['original_em'])
                if em is not None:
                    _same(em['source_origin_qpc_ns'],origin);_need(em['tick_ms']%50==0 and em['tick_ms']<=s['tick_ms'],'HELD_ORIGIN_CONTRADICTION')
                    _need(held['held']==(em['tick_ms']<s['tick_ms']),'HELD_ORIGIN_CONTRADICTION')
                    _same(em['nominal_qpc_ns'],None if origin is None else origin+em['tick_ms']*NS_MS)
                    self.read(em['pose_read'],em['numerical_pose_span']);self.usable(em['numerical_pose_span'])
                    _eqfields(em,em['pose_read'],('root_revision','pose_revision','revoke_generation'),'HELD_ORIGIN_CONTRADICTION')
                    _le(em['nominal_qpc_ns'],em['pose_read']['begin_qpc_ns']);_le(em['pose_read']['end_qpc_ns'],em['call']['begin_qpc_ns']);_le(em['call']['end_qpc_ns'],em['scope_closed_qpc_ns'])
                    _le(em['scope_closed_qpc_ns'],None if adc is None else adc['begin_qpc_ns'])
                    self.cover(em['numerical_pose_span'],[em['nominal_qpc_ns'],em['pose_read']['begin_qpc_ns'],em['pose_read']['end_qpc_ns'],em['call']['begin_qpc_ns'],em['call']['end_qpc_ns'],em['scope_closed_qpc_ns']])
                    self.want(em['scope_closed_qpc_ns'])
                    ek=(em['tick_ms'],em['source_count'])
                    if ek in self.emmap:_need(self.emmap[ek]==em,'HELD_ORIGIN_CONTRADICTION')
                    else:self.emmap[ek]=em
                    if not held['held']:
                        _same(em['source_count'],s['source_count']);_same(em['pose_read'],emread,'HELD_ORIGIN_CONTRADICTION')
            previous=s
        for em in self.emmap.values():
            count=em['source_count']
            if not 1<=count<=len(book['samples']):self.missing.add('MISSING_ORIGINAL_ASSOCIATION');continue
            original=book['samples'][count-1]
            _same(original['tick_ms'],em['tick_ms'],'HELD_ORIGIN_CONTRADICTION')
            _same(original['pose_reads']['em'],em['pose_read'],'HELD_ORIGIN_CONTRADICTION')
            self.want(original['held_em_association'])
        if not book['samples']:self.missing.add('MISSING_ORIGINAL_ASSOCIATION')
        current=book['current_read']
        if self.want(current,'MISSING_CURRENT_READ') is not None:
            _same(current['at_qpc_ns'],self.now);_same(current['pose_read']['end_qpc_ns'] if current['pose_read'] else None,self.now)
            span=current['valid_span'];self.usable(span);self.want(current['pose']);self.want(current['pose_revision']);self.want(current['pose_read'])
            if span is not None:_same(span['through_qpc_ns'],current['at_qpc_ns'])
            self.pose(current['pose'],current['pose_revision'],None if span is None else span['root_revision'])
            if span is not None:_same(span['pose_revision'],current['pose_revision'],'LINEAGE_CONTRADICTION')
            points=[self.now]+([] if current['pose_read'] is None else list(current['pose_read'].values()))
            self.cover(span,points)
            envelope=book['current_pose_interval'];self.want(envelope)
            if envelope is not None:
                _eqfields(span,envelope,('root_revision','pose_revision'),'LINEAGE_CONTRADICTION')
                self.cover(envelope,points)


def _raw_shape(record):
    for name in ('request_raw','capture_raw'):
        if record[name] is None:continue
        _,x=P._raw(record[name])
        if name=='request_raw':
            P._obj(x,set('schema kind context request_seq source_id source values qualities original_host_qpc_ns'.split()),'raw')
            _need(type(x['schema']) is int and x['schema']==1 and x['kind']=='diagnostic_scan' and type(x['source_id']) is int and x['source_id']==4 and x['source']=='software_fixture','INVALID_SHAPE')
            for field,bits in (('values',16),('qualities',8),('original_host_qpc_ns',63)):
                _need(type(x[field]) is list and len(x[field])==4,'INVALID_SHAPE')
                for z in x[field]:P._uint(z,bits)
        else:
            P._obj(x,set('schema kind context request_seq request_sha256 generation trigger_id captures final_counters'.split()),'raw')
            _need(type(x['schema']) is int and x['schema']==1 and x['kind']=='diagnostic_capture','INVALID_SHAPE')
            P._hash(x['request_sha256']);P._uint(x['generation'],32);P._uint(x['trigger_id'],32);P._counter(x['final_counters'])
            _need(type(x['captures']) is list and len(x['captures'])==4,'INVALID_SHAPE')
            for lane in x['captures']:
                P._obj(lane,{'channel','raw_words','pipeline_counters','ack_returned'},'lane');P._uint(lane['channel'],32);P._counter(lane['pipeline_counters'])
                _need(lane['ack_returned'] is True and type(lane['raw_words']) is list and len(lane['raw_words'])==10,'INVALID_SHAPE')
                for word in lane['raw_words']:P._uint(word,32)
        P._context(x['context']);P._uint(x['request_seq'],32)

# Exact C34 pure predicates appended below at build time; globals are isolated.
_C32=P
def _raw_intrinsics(record, config, namespace, now):
    """Relations between supplied raw objects do not need a missing candidate."""
    request = capture = None
    request_digest = None
    if record['request_raw'] is not None:
        raw,request = _C32._raw(record['request_raw']); request_digest = hashlib.sha256(raw).hexdigest()
        _need(_C32._json_bytes(request,True) == raw, 'C34 intrinsic request canonical bytes')
        _need(request['request_seq'] > 0, 'C34 intrinsic positive request sequence')
        ticks = request['original_host_qpc_ns']
        _need(0 < ticks[0] <= ticks[1] <= ticks[2] <= ticks[3] <= now, 'C34 intrinsic original request times')
        if namespace is not None:
            _need(request['context'] == namespace[0], 'C34 intrinsic request supplied namespace mismatch')
    if record['capture_raw'] is not None:
        raw,capture = _C32._raw(record['capture_raw'])
        _need(hashlib.sha256(raw).hexdigest() == record['capture_sha256'], 'C34 intrinsic capture hash mismatch')
        if namespace is not None:
            _need(capture['context'] == namespace[0] and capture['generation'] == namespace[1],
                  'C34 intrinsic capture supplied namespace mismatch')
        seq = capture['request_seq']; final = capture['final_counters']
        _need(capture['generation'] > 0, 'C34 intrinsic positive capture generation')
        captured_ticks = []
        for ch, lane in enumerate(capture['captures']):
            words = lane['raw_words']
            _need(words[4:9] == [4*(seq-1),4*seq-1,capture['context']['tag'],capture['trigger_id'],capture['generation']] and
                  words[1] & 255 == ch, 'C34 intrinsic capture identity words')
            captured_ticks.append(words[2] | words[3] << 32)
        _need(0 < captured_ticks[0] <= captured_ticks[1] <= captured_ticks[2] <= captured_ticks[3] <= now,
              'C34 intrinsic original capture times')
        _need(seq > 0 and all(v >= inc for v,inc in zip(final,(4*seq,seq,4*seq))), 'C34 intrinsic negative counter baseline')
        for ch,lane in enumerate(capture['captures']):
            _need(lane['channel'] == ch and lane['pipeline_counters'][:2] == final[:2] and
                  lane['pipeline_counters'][2]+3-ch == final[2], 'C34 intrinsic lane/final counters')
        if config is not None:
            base = config['baseline_counters']
            _need(final == [base[0]+4*seq,base[1]+seq,base[2]+4*seq] and
                  capture['trigger_id'] == config['initial_trigger_id']+seq,
                  'C34 intrinsic original config/counter/trigger mismatch')
    if request is not None and capture is not None:
        _need(capture['request_sha256'] == request_digest and capture['context'] == request['context'] and
              capture['request_seq'] == request['request_seq'], 'C34 supplied raw pair mismatch')
        seq = capture['request_seq']
        for ch,lane in enumerate(capture['captures']):
            ticks = request['original_host_qpc_ns'][ch]
            expected = [request['values'][ch],ch | request['qualities'][ch]<<8,ticks & 0xffffffff,ticks>>32,
                4*(seq-1),4*seq-1,capture['context']['tag'],capture['trigger_id'],capture['generation']]
            _need(lane['raw_words'][:9] == expected, 'C34 supplied raw pair words mismatch')

def _record_counter_consistency(records):
    """Necessary shared-baseline feasibility only; never manufacture a baseline.

    Runs after each actual line passed shape and intrinsic checks. A separate
    namespace/generation is not silently merged into a different capture group.
    """
    previous = {}
    for record in records.values():
        if record['capture_raw'] is None:
            continue
        _, capture = _C32._raw(record['capture_raw'])
        key = (_json(capture['context']), capture['generation'])
        if key in previous:
            prior = previous[key]
            delta = capture['request_seq'] - prior['request_seq']
            _need([b-a for a,b in zip(prior['final_counters'],capture['final_counters'])] ==
                  [4*delta,delta,4*delta], 'C34 supplied records cross-capture counter mismatch')
        previous[key] = capture

def _source_checks(check,candidates,root):
    """All supplied wire/admission/config checks run before missing evidence exit."""
    c=check
    config=None if root is None else root['config']
    records=[] if root is None or root['captures'] is None else root['captures']
    admissions=None if root is None else root['source_admissions']
    current=None if root is None else root['current_pose']
    registry=None if root is None else root['actor_registry']
    contexts=[];generations=[];anchors=[];bycandidate={};byrecord={}
    for candidate in candidates:
        P._candidate(candidate)
        ident=candidate['observation_identity'];t=candidate['source_time'];key=ident['capture_sha256']
        _need(key not in bycandidate,'IDENTITY_CONTRADICTION');bycandidate[key]=candidate
        contexts.append(ident['context']);generations.append(ident['generation']);anchors.append(t)
        _le(ident['receiver_upper_qpc_ns'],c.now)
        if len(bycandidate)>1:
            prev=candidates[len(bycandidate)-2]['observation_identity']
            _need(prev['request_seq']<ident['request_seq'] and prev['source_admission_index']<ident['source_admission_index'],'IDENTITY_CONTRADICTION')
            _need(prev['original_host_injection_qpc_ns'][-1]<ident['original_host_injection_qpc_ns'][0]);_le(prev['receiver_upper_qpc_ns'],ident['receiver_upper_qpc_ns'])
        adc=P._source_ns(t,t['adc_tick_ms']);em=P._source_ns(t,t['em_tick_ms'])
        c.stale |= c.now-adc>AGE_NS or(em is not None and c.now-em>AGE_NS)
    for item in (config,current,registry):
        if item is not None:contexts.append(item['context']);generations.append(item['generation'])
    if config is not None:
        _need(config['generation']>0,'IDENTITY_CONTRADICTION');anchors.append(config)
        for k in ('receipt_id','pose_book_id','owner_binding_id'):c.want(config[k])
        P._tick(config['source_start_tick_ms'],10)
    else:c.missing.add('MISSING_ORIGINAL_ASSOCIATION')
    for record in records:
        if record is None:c.missing.add('MISSING_NATIVE_CAPTURE');continue
        key=record['capture_sha256'];_need(key not in byrecord,'IDENTITY_CONTRADICTION');byrecord[key]=record
        _raw_shape(record)
        for rawname in ('request_raw','capture_raw'):
            if record[rawname] is None:c.missing.add('MISSING_NATIVE_CAPTURE');continue
            _,obj=P._raw(record[rawname]);contexts.append(obj['context'])
            if rawname=='capture_raw':generations.append(obj['generation'])
    if contexts:_need(all(x==contexts[0] for x in contexts),'IDENTITY_CONTRADICTION')
    if generations:_need(all(x==generations[0] for x in generations),'IDENTITY_CONTRADICTION')
    for a in anchors:
        for k in ('source_start_tick_ms','source_start_monotonic_ns'):_same(a[k],anchors[0][k])
    anchor=anchors[0] if anchors else None
    book=c.r['actor_book']
    if book is not None and anchor is not None:
        _same(anchor['source_start_tick_ms'],0);_same(anchor['source_start_monotonic_ns'],book['source_origin_qpc_ns'])
    ns=(contexts[0],generations[0]) if contexts and generations else None
    for record in byrecord.values():
        _raw_intrinsics(record,config,ns,c.now)
        if record['capture_sha256'] in bycandidate:
            P._returned(bycandidate[record['capture_sha256']],record,config,[])
        elif c.r['candidate'] is not None:_need(False,'IDENTITY_CONTRADICTION')
        else:c.missing.add('MISSING_ORIGINAL_ASSOCIATION')
    _record_counter_consistency(byrecord)
    if admissions is None or not admissions:c.missing.add('MISSING_SOURCE_ADMISSION')
    else:
        previous=None;last_native=None;consecutive=0
        for index,a in enumerate(admissions):
            _need(a['index']==index,'IDENTITY_CONTRADICTION');P._quality(a['channel_counts'],a['quality'],a['adc_tick_ms'],a['em_tick_ms'])
            if previous is not None:_need(a['adc_tick_ms']>previous['adc_tick_ms']);_le(previous['received_qpc_ns'],a['received_qpc_ns'])
            consecutive=(min(10,consecutive+1) if previous is not None and a['adc_tick_ms']-previous['adc_tick_ms']==10 else 1)
            _need(bool(a['quality']&8)==(consecutive==10),'IDENTITY_CONTRADICTION')
            new=a['em_tick_ms'] is not None and a['em_tick_ms']!=last_native
            _need(a['new_em_sample']==new,'HELD_ORIGIN_CONTRADICTION')
            if new:_need(a['em_tick_ms']==a['adc_tick_ms'] and(last_native is None or a['em_tick_ms']>last_native),'HELD_ORIGIN_CONTRADICTION');last_native=a['em_tick_ms']
            elif a['em_tick_ms'] is not None:
                _need(previous is not None and previous['em_tick_ms']==a['em_tick_ms'] and previous['channel_counts'][:3]==a['channel_counts'][:3] and previous['quality']&0x70==a['quality']&0x70,'HELD_ORIGIN_CONTRADICTION')
            previous=a
        if anchor is not None:_,late=P._admissions(admissions,anchor);c.stale|=late
    # Full supplied source prefix is validated, not only captures selected for the child.
    if book is not None and admissions is not None:
        admission_ticks={a['adc_tick_ms']:a for a in admissions}
        for sample in book['samples']:
            admission=admission_ticks.get(sample['tick_ms'])
            if admission is None:
                c.missing.add('MISSING_SOURCE_ADMISSION');continue
            _same(admission['index']+1,sample['source_count'],'IDENTITY_CONTRADICTION')
            held=sample['held_em_association']
            if admission['em_tick_ms'] is None:
                _need(held is None,'HELD_ORIGIN_CONTRADICTION');continue
            if held is None or held['original_em'] is None:
                c.missing.add('MISSING_ORIGINAL_ASSOCIATION');continue
            em=held['original_em']
            _same(admission['em_tick_ms'],em['tick_ms'],'HELD_ORIGIN_CONTRADICTION')
            _same(admission['new_em_sample'],not held['held'],'HELD_ORIGIN_CONTRADICTION')
            for lane,value in enumerate(em['channel_values']):
                lo,hi=(math.log10(.2),math.log10(.2)+4) if lane==0 else(-2,2)
                quantized=round((min(hi,max(lo,value))-lo)*4095/(hi-lo))
                _same(quantized,admission['channel_counts'][lane],'HELD_ORIGIN_CONTRADICTION')
                _same(em['channel_saturated'][lane],bool(admission['quality']&(1<<(4+lane))),'HELD_ORIGIN_CONTRADICTION')
            _le(sample['finish_qpc_ns'],admission['received_qpc_ns'])
    if root is not None:_same(root['evidence_scope'],c.r['evidence_scope'])
    for item,timekey in ((current,'at_qpc_ns'),(registry,'as_of_qpc_ns')):
        if item is not None:_same(item[timekey],c.now);c.want(item['receipt_id'])
    if current is not None:
        c.pose(current['pose'],current['pose_revision'],current['root_revision']);c.usable(None if current['valid_span'] is None else dict(current['valid_span'],root_revision=current['root_revision'],pose_revision=current['pose_revision']))
        for name in ('pose','root_revision','pose_revision','pose_read','valid_span'):c.want(current[name],'MISSING_CURRENT_READ')
        if current['valid_span'] is not None:c.want(current['valid_span']['receipt_id'])
        if current['valid_span'] is not None:_same(current['valid_span']['through_qpc_ns'],current['at_qpc_ns'])
        times=[c.now]+([]if current['pose_read'] is None else list(current['pose_read'].values()))
        c.cover(current['valid_span'],times)
        if current['pose_read'] is not None:_same(current['pose_read']['end_qpc_ns'],c.now)
        bc=None if book is None else book['current_read']
        if bc is not None:
            _eqfields(current,bc,('pose','pose_revision','at_qpc_ns','pose_read'),'LINEAGE_CONTRADICTION')
            if bc['valid_span'] is not None:_same(current['root_revision'],bc['valid_span']['root_revision'],'LINEAGE_CONTRADICTION')
            _eqfields(current['valid_span'],bc['valid_span'],('from_qpc_ns','through_qpc_ns'))
            if bc['valid_span'] is not None:_same(current['root_revision'],bc['valid_span']['root_revision'],'LINEAGE_CONTRADICTION')
    else:c.missing.add('MISSING_CURRENT_READ')
    return config,admissions,bycandidate,byrecord

def _receipt(check,receipt,read,span,index,nominal,call):
    c=check
    if receipt is None:c.missing.add('MISSING_ORIGINAL_ASSOCIATION');return
    for name in ('receipt_id','pose','pose_revision','pose_read','valid_span'):c.want(receipt[name])
    _same(receipt['source_admission_index'],index);_same(receipt['nominal_source_qpc_ns'],nominal)
    if read is not None:
        _eqfields(receipt,read,('pose','pose_revision'),'LINEAGE_CONTRADICTION')
        if receipt['pose_read'] is not None:_eqfields(receipt['pose_read'],read,('begin_qpc_ns','end_qpc_ns'))
    if receipt['valid_span'] is not None:
        c.want(receipt['valid_span']['receipt_id'])
        _eqfields(receipt['valid_span'],span,('from_qpc_ns','through_qpc_ns'))
    actual=receipt['pose_read'];times=[nominal]
    if actual is not None:
        _le(nominal,actual['begin_qpc_ns']);times+=list(actual.values())
        if call is not None:_le(actual['end_qpc_ns'],call['begin_qpc_ns'])
    if call is not None:times+=[call['begin_qpc_ns'],call['end_qpc_ns']]
    c.cover(receipt['valid_span'],times)

def _captures(check,config,admissions,bycandidate,records):
    c=check;observations=[]
    for key,candidate in bycandidate.items():
        ident=candidate['observation_identity'];t=candidate['source_time'];index=ident['source_admission_index']
        rec=records.get(key)
        adm=admissions[index] if admissions is not None and index<len(admissions) else None
        if adm is None:c.missing.add('MISSING_SOURCE_ADMISSION')
        else:
            _same(adm['quality'],candidate['quality']);_same(adm['channel_counts'],candidate['channel_counts'])
            _same(adm['adc_tick_ms'],t['adc_tick_ms']);_same(adm['em_tick_ms'],t['em_tick_ms']);_same(adm['received_qpc_ns'],t['admission_received_monotonic_ns'])
        if rec is None:c.missing.add('MISSING_NATIVE_CAPTURE');continue
        if adm is not None:_same(rec['source_record_sha256'],adm['source_record_sha256'])
        sample=c.samplemap.get(rec['adc_book_source_sha256'])
        if sample is None:c.missing.add('MISSING_ORIGINAL_ASSOCIATION')
        adc_ns=P._source_ns(t,t['adc_tick_ms']);em_ns=P._source_ns(t,t['em_tick_ms'])
        read=None if sample is None else sample['pose_reads']['adc'];span=None if sample is None else sample['numerical_pose_span']
        call=c.want(rec['adc_call'])
        if sample is not None:
            _same(sample['tick_ms'],t['adc_tick_ms']);_same(sample['nominal_qpc_ns'],adc_ns)
            if read is not None:_same(rec['adc_root_revision'],read['root_revision'],'LINEAGE_CONTRADICTION')
            _eqfields(call,sample['adc'],('begin_qpc_ns','end_qpc_ns'))
        c.want(rec['adc_root_revision'])
        if call is not None:_le(call['end_qpc_ns'],t['admission_received_monotonic_ns'])
        _receipt(c,rec['adc_pose'],read,span,index,adc_ns,call)
        if em_ns is None:
            _need(all(rec[n] is None for n in ('em_pose','em_origin_capture_sha256','em_book_source_sha256','em_root_revision','original_em_call','original_em_scope_closed_qpc_ns')),'HELD_ORIGIN_CONTRADICTION')
            if sample is not None:_need(sample['held_em_association'] is None,'HELD_ORIGIN_CONTRADICTION')
            em_pose=None
        else:
            original=c.samplemap.get(rec['em_book_source_sha256']);origin=records.get(rec['em_origin_capture_sha256']);held=None if sample is None else sample['held_em_association'];em=None if held is None else held['original_em']
            for x in (original,origin,held,em,rec['em_pose'],rec['em_root_revision'],rec['original_em_call'],rec['original_em_scope_closed_qpc_ns']):c.want(x,'MISSING_NATIVE_CAPTURE')
            ni=next((a['index'] for a in admissions or[] if a['new_em_sample'] and a['em_tick_ms']==t['em_tick_ms']),None)
            if ni is None:c.missing.add('MISSING_SOURCE_ADMISSION')
            if original is not None:
                _same(original['tick_ms'],t['em_tick_ms'],'HELD_ORIGIN_CONTRADICTION')
                if original['pose_reads']['em'] is not None:_same(rec['em_root_revision'],original['pose_reads']['em']['root_revision'],'HELD_ORIGIN_CONTRADICTION')
                if em is not None:_same(em['pose_read'],original['pose_reads']['em'],'HELD_ORIGIN_CONTRADICTION');_same(em['source_count'],original['source_count'],'HELD_ORIGIN_CONTRADICTION')
            if origin is not None:
                _same(origin['em_origin_capture_sha256'],origin['capture_sha256'],'HELD_ORIGIN_CONTRADICTION')
                _same(origin['adc_book_source_sha256'],rec['em_book_source_sha256'],'HELD_ORIGIN_CONTRADICTION')
                _same(origin['em_pose'],rec['em_pose'],'HELD_ORIGIN_CONTRADICTION')
                _same(origin['original_em_call'],rec['original_em_call'],'HELD_ORIGIN_CONTRADICTION')
                _same(origin['original_em_scope_closed_qpc_ns'],rec['original_em_scope_closed_qpc_ns'],'HELD_ORIGIN_CONTRADICTION')
                oc=bycandidate.get(origin['capture_sha256'])
                if oc is None:c.missing.add('MISSING_NATIVE_CAPTURE')
                else:
                    _same(oc['source_time']['adc_tick_ms'],t['em_tick_ms'],'HELD_ORIGIN_CONTRADICTION');_same(oc['source_time']['em_tick_ms'],t['em_tick_ms'],'HELD_ORIGIN_CONTRADICTION')
                    _same(oc['channel_counts'][:3],candidate['channel_counts'][:3],'HELD_ORIGIN_CONTRADICTION');_same(oc['quality']&0x70,candidate['quality']&0x70,'HELD_ORIGIN_CONTRADICTION')
            if adm is not None and adm['new_em_sample']:_same(rec['em_origin_capture_sha256'],key,'HELD_ORIGIN_CONTRADICTION')
            if em is not None:
                _same(em['nominal_qpc_ns'],em_ns,'HELD_ORIGIN_CONTRADICTION');_same(em['root_revision'],rec['em_root_revision'],'HELD_ORIGIN_CONTRADICTION');_same(em['call'],rec['original_em_call']);_same(em['scope_closed_qpc_ns'],rec['original_em_scope_closed_qpc_ns'])
                for n,value in enumerate(em['channel_values']):
                    lo,hi=(math.log10(.2),math.log10(.2)+4) if n==0 else(-2,2)
                    quantized=round((min(hi,max(lo,value))-lo)*4095/(hi-lo))
                    _same(quantized,candidate['channel_counts'][n],'HELD_ORIGIN_CONTRADICTION')
                    _same(em['channel_saturated'][n],bool(candidate['quality']&(1<<(4+n))),'HELD_ORIGIN_CONTRADICTION')
            _receipt(c,rec['em_pose'],None if em is None else em['pose_read'],None if em is None else em['numerical_pose_span'],ni,em_ns,rec['original_em_call'])
            em_pose=None if rec['em_pose'] is None else rec['em_pose']['pose']
        observations.append(dict(sample_id=key,counts=candidate['channel_counts'],quality=candidate['quality'],adc_qpc_ns=adc_ns,em_qpc_ns=em_ns,adc_pose=None if rec['adc_pose'] is None else rec['adc_pose']['pose'],em_pose=em_pose))
    return observations

def _transition_key(t):return tuple(t[k] for k in ('kind','before_root_revision','from_pose_revision','lower_observed_qpc_ns'))

def _consistent_supplied(values,code='LINEAGE_CONTRADICTION'):
    """Compare actual supplied values only; never create or complete a receipt."""
    known=[value for value in values if value is not None]
    for value in known[1:]:_same(known[0],value,code)

def _actors(check,root,bycandidate,records):
    c=check;book=c.r['actor_book'];intervals=None if book is None else book['actor_pose_intervals']
    registry=None if root is None else root['actor_registry'];associations=None if registry is None else registry['associations']
    transitions=[] if intervals is None else intervals['transitions'];closed=[] if intervals is None else intervals['closed_spans']
    if intervals is None or associations is None:c.missing.add('MISSING_TRANSITION_RECEIPT')
    if intervals is not None:
        if intervals['pending'] is not None:c.missing.add('ACTOR_PENDING_OR_FAILED')
        _need(len(closed)==len(transitions),'LINEAGE_CONTRADICTION')
    transition_map={};previous=None;matched_closed=set()
    for t in transitions:
        k=_transition_key(t);_need(k not in transition_map,'LINEAGE_CONTRADICTION');transition_map[k]=t
        if t['kind']=='STEP':
            for lower in ('lower_observed_qpc_ns','pre_cas_qpc_ns','post_cas_observed_qpc_ns'):
                _le(t.get(lower),t.get('getter_readback_qpc_ns'))
        if previous is not None:
            _le(previous['lower_observed_qpc_ns'],t['lower_observed_qpc_ns']);_le(previous['completion_observed_qpc_ns'],t['lower_observed_qpc_ns'])
            if 'after_root_revision' in previous:_same(previous['after_root_revision'],t['before_root_revision'],'LINEAGE_CONTRADICTION');_same(previous['to_pose_revision'],t['from_pose_revision'],'LINEAGE_CONTRADICTION')
        if t['state']!='COMPLETE':c.missing.add('ACTOR_PENDING_OR_FAILED')
        else:
            _le(t['lower_observed_qpc_ns'],t['completion_observed_qpc_ns']);c.want(t['completion_observed_qpc_ns'])
            if t['kind']=='STEP':
                _need(t['after_root_revision']==t['before_root_revision']+1 and t['to_pose_revision']==t['from_pose_revision']+1,'LINEAGE_CONTRADICTION')
                _le(t['lower_observed_qpc_ns'],t['pre_cas_qpc_ns']);_le(t['pre_cas_qpc_ns'],t['post_cas_observed_qpc_ns']);_le(t['post_cas_observed_qpc_ns'],t['completion_observed_qpc_ns']);_le(t['model_executed_until_qpc_ns'],t['completion_observed_qpc_ns']);_le(t['getter_readback_qpc_ns'],t['completion_observed_qpc_ns'])
            elif t['kind']=='BOOT':_need(t['after_root_revision']==t['before_root_revision']+1 and t['to_pose_revision']==t['from_pose_revision'],'LINEAGE_CONTRADICTION')
            else:_need(t['after_root_revision'] in (t['before_root_revision'],t['before_root_revision']+1) and t['to_pose_revision']==t['from_pose_revision'],'LINEAGE_CONTRADICTION')
        old=c.want(t['old_pose_span'],'MISSING_TRANSITION_RECEIPT')
        compatible_closed=[(i,s) for i,s in enumerate(closed)
            if (s['root_revision'] is None or s['root_revision']==t['before_root_revision'])
            and (s['pose_revision'] is None or s['pose_revision']==t['from_pose_revision'])
            and (s['through_qpc_ns'] is None or s['through_qpc_ns']<t['lower_observed_qpc_ns'])]
        _need(bool(compatible_closed),'LINEAGE_CONTRADICTION')
        if old is not None:
            c.usable(old)
            for value in old.values():c.want(value,'MISSING_TRANSITION_RECEIPT')
            _same(old['root_revision'],t['before_root_revision'],'LINEAGE_CONTRADICTION')
            _same(old['pose_revision'],t['from_pose_revision'],'LINEAGE_CONTRADICTION')
            if old['through_qpc_ns'] is not None:_need(old['through_qpc_ns']<t['lower_observed_qpc_ns'])
            possible=[(i,s) for i,s in compatible_closed if all(
                s[key] is None or value is None or s[key]==value for key,value in old.items())
                and (s['root_revision'] is None or s['root_revision']==t['before_root_revision'])
                and (s['pose_revision'] is None or s['pose_revision']==t['from_pose_revision'])]
            _need(bool(possible),'LINEAGE_CONTRADICTION')
            exact=[i for i,s in possible if all(value is not None for value in old.values()) and s==old]
            _need(len(exact)<=1,'LINEAGE_CONTRADICTION')
            if exact:
                _need(exact[0] not in matched_closed,'LINEAGE_CONTRADICTION');matched_closed.add(exact[0])
            else:c.missing.add('MISSING_TRANSITION_RECEIPT')
        earliest=t['lower_observed_qpc_ns']
        for s in c.spans:
            if s.get('root_revision')==t['before_root_revision'] and s['through_qpc_ns'] is not None and s['through_qpc_ns']>=earliest:c.missing.add('INTERVAL_BOUNDARY_UNAVAILABLE')
            if t.get('after_root_revision') is not None and s.get('root_revision')==t['after_root_revision'] and t['after_root_revision']!=t['before_root_revision']:
                if s['from_qpc_ns'] is not None and t['completion_observed_qpc_ns'] is not None and s['from_qpc_ns']<t['completion_observed_qpc_ns']:c.missing.add('SOURCE_TIME_IN_TRANSITION_GAP')
        previous=t
    if intervals is not None and all(t['state']=='COMPLETE' for t in transitions):
        if not transitions:_need(len(c.root_values)<=1,'LINEAGE_CONTRADICTION')
        else:
            vertices={t['before_root_revision'] for t in transitions}|{t['after_root_revision'] for t in transitions}
            _need(set(c.root_values)<=vertices,'LINEAGE_CONTRADICTION')
    for a in c.spans:
        for b in c.spans:
            ar,br=a.get('root_revision'),b.get('root_revision')
            if ar is not None and br is not None and ar<br:
                if a['through_qpc_ns'] is not None and b['from_qpc_ns'] is not None:_need(a['through_qpc_ns']<b['from_qpc_ns'],'LINEAGE_CONTRADICTION')
    byaction={};seen=set();actions=[];matched=set();previous_before=None
    for field in ('pose_book_id','owner_binding_id','actor_composition_id','original_world_actor_link_id'):
        _consistent_supplied([a['custody'][field] for a in associations or [] if a['custody'] is not None],'IDENTITY_CONTRADICTION')
    for a in associations or []:
        k=_transition_key(a['transition_key']);_need(k not in seen,'LINEAGE_CONTRADICTION');seen.add(k)
        t=transition_map.get(k);kind=a['transition_key']['kind'];lower=a['transition_key']['lower_observed_qpc_ns']
        before=a['from_root'];after=a['to_root'];candidate=a['candidate_root'];custody=a['custody'];step=a['step_receipt'];pub=a['publication'];non=a['nonspatial_receipt']
        for value in (a['receipt_id'],before,after,custody):c.want(value,'MISSING_TRANSITION_RECEIPT')
        if previous_before is not None:_need(a['transition_key']['before_root_revision']>=previous_before,'LINEAGE_CONTRADICTION')
        previous_before=a['transition_key']['before_root_revision']
        for rv in (before,after,candidate):
            if rv is not None:c.pose(rv['pose'],rv['pose_revision'],rv['root_revision'],rv['revoke_generation'])
        if before is not None:
            _same(before['root_revision'],a['transition_key']['before_root_revision'],'LINEAGE_CONTRADICTION');_same(before['pose_revision'],a['transition_key']['from_pose_revision'],'LINEAGE_CONTRADICTION')
        if before is not None and after is not None:
            if kind=='STEP':_need(after['root_revision']==before['root_revision']+1 and after['pose_revision']==before['pose_revision']+1 and after['revoke_generation']==before['revoke_generation'],'LINEAGE_CONTRADICTION')
            else:
                _same(before['pose'],after['pose'],'LINEAGE_CONTRADICTION');_same(before['pose_revision'],after['pose_revision'],'LINEAGE_CONTRADICTION')
                if kind=='BOOT':_need(after['root_revision']==before['root_revision']+1 and after['revoke_generation']==before['revoke_generation']+1,'LINEAGE_CONTRADICTION')
                else:_need(after['root_revision'] in (before['root_revision'],before['root_revision']+1) and after['revoke_generation']==before['revoke_generation'],'LINEAGE_CONTRADICTION')
        if custody is not None:
            c.want(custody['receipt_id'],'MISSING_CUSTODY')
            _same(custody['before_root_revision'],a['transition_key']['before_root_revision'],'LINEAGE_CONTRADICTION')
            if before is not None:_same(custody['revoke_generation_before'],before['revoke_generation'],'LINEAGE_CONTRADICTION')
            if after is not None:_same(custody['after_root_revision'],after['root_revision'],'LINEAGE_CONTRADICTION');_same(custody['revoke_generation_after'],after['revoke_generation'],'LINEAGE_CONTRADICTION')
            config=None if root is None else root['config']
            if config is not None:_eqfields(custody,config,('pose_book_id','owner_binding_id'))
            if custody['cancel_state']!='clear' or custody['revoke_state']!='clear' or custody['successor_state']=='unknown':c.missing.add('MISSING_CUSTODY')
            if custody['successor_state']!='unknown':_same(custody['successor_state'],'original_candidate' if kind=='STEP' else 'original_nonspatial','LINEAGE_CONTRADICTION')
        if t is None:c.missing.add('MISSING_TRANSITION_RECEIPT')
        else:
            matched.add(k)
            if after is not None and t['state']=='COMPLETE':_same(after['root_revision'],t['after_root_revision'],'LINEAGE_CONTRADICTION');_same(after['pose_revision'],t['to_pose_revision'],'LINEAGE_CONTRADICTION')
        if kind=='STEP':
            _need(non is None,'LINEAGE_CONTRADICTION')
            complete=t if t is not None and t['state']=='COMPLETE' else None
            root_revisions=[rv['root_revision'] for rv in (candidate,after) if rv is not None]
            pose_revisions=[rv['pose_revision'] for rv in (candidate,after,step,pub) if rv is not None]
            if custody is not None:root_revisions.append(custody['after_root_revision'])
            if complete is not None:
                root_revisions.append(complete['after_root_revision']);pose_revisions.append(complete['to_pose_revision'])
            _consistent_supplied(root_revisions);_consistent_supplied(pose_revisions)
            for revision in root_revisions:_same(revision,a['transition_key']['before_root_revision']+1,'LINEAGE_CONTRADICTION')
            for revision in pose_revisions:_same(revision,a['transition_key']['from_pose_revision']+1,'LINEAGE_CONTRADICTION')
            revoke_generations=[rv['revoke_generation'] for rv in (before,candidate,after) if rv is not None]
            if custody is not None:revoke_generations.extend((custody['revoke_generation_before'],custody['revoke_generation_after']))
            _consistent_supplied(revoke_generations)
            for value in (a['action_id'],a['observation_capture_sha256'],candidate,step,pub):c.want(value,'MISSING_TRANSITION_RECEIPT')
            if a['action_id'] is not None:_need(a['action_id'] not in byaction,'IDENTITY_CONTRADICTION');byaction[a['action_id']]=(a,t)
            observed=bycandidate.get(a['observation_capture_sha256'])
            if observed is None:c.missing.add('MISSING_NATIVE_CAPTURE')
            else:_le(observed['observation_identity']['receiver_upper_qpc_ns'],lower)
            if candidate is not None and after is not None:_same(candidate,after,'LINEAGE_CONTRADICTION')
            if step is not None:
                _same(step['boot_id'],registry['context']['boot_id'],'IDENTITY_CONTRADICTION')
                for key in ('receipt_id','candidate_receipt_id','returned_receipt_id','effect_witness_id'):c.want(step[key],'MISSING_RETURNED_RECEIPT')
                _same(step['candidate_receipt_id'],step['returned_receipt_id'],'LINEAGE_CONTRADICTION')
                if not step['returned_receipt_observed'] or step['effect_observation']!='candidate_root_current':c.missing.add('MISSING_RETURNED_RECEIPT')
                if step['returned_receipt_observed'] is False and step['returned_receipt_id'] is not None:_need(False,'LINEAGE_CONTRADICTION')
                _le(step['model_start_qpc_ns'],step['model_executed_until_qpc_ns'])
                if after is not None:_same(step['pose_revision'],after['pose_revision'],'LINEAGE_CONTRADICTION')
                if t is not None and t['state']=='COMPLETE':_same(step['model_executed_until_qpc_ns'],t['model_executed_until_qpc_ns']);_le(t['pre_cas_qpc_ns'],step['model_executed_until_qpc_ns'])
            if pub is not None:
                _le(lower,pub['getter_readback_qpc_ns'])
                if t is not None:
                    for field in ('pre_cas_qpc_ns','post_cas_observed_qpc_ns'):_le(t.get(field),pub['getter_readback_qpc_ns'])
                for key in ('receipt_id','getter_receipt_id','getter_policy_receipt_id'):c.want(pub[key],'MISSING_GETTER_PUBLICATION')
                if pub['state']!='APPLIED':c.missing.add('MISSING_GETTER_PUBLICATION')
                _need(pub['local_error_bound_m']<=pub['frozen_getter_cap_m'] and pub['global_error_bound_m']<=pub['frozen_getter_cap_m'],'LINEAGE_CONTRADICTION')
                if after is not None:_same(pub['pose_revision'],after['pose_revision'],'LINEAGE_CONTRADICTION')
                if t is not None and t['state']=='COMPLETE':_same(pub['operation_id'],t['publication_operation_id']);_same(pub['getter_readback_qpc_ns'],t['getter_readback_qpc_ns'])
            if before is not None and after is not None and a['action_id'] is not None:actions.append(dict(action_id=a['action_id'],from_pose=before['pose'],to_pose=after['pose']))
        else:
            _need(step is None and pub is None and candidate is None and a['action_id'] is None and a['observation_capture_sha256'] is None,'LINEAGE_CONTRADICTION')
            if c.want(non,'MISSING_TRANSITION_RECEIPT') is not None:
                c.want(non['receipt_id']);c.want(non['boot_receipt_id'])
                if kind=='BOOT':_need(non['command_receipt_id'] is None and non['command_seq'] is None and non['command_sha256'] is None and not non['duplicate_command'],'LINEAGE_CONTRADICTION')
                else:
                    for field in ('command_receipt_id','command_seq','command_sha256'):c.want(non[field])
                    if before is not None and after is not None:_same(non['duplicate_command'],before['root_revision']==after['root_revision'],'LINEAGE_CONTRADICTION')
    if set(transition_map)!=matched:c.missing.add('MISSING_TRANSITION_RECEIPT')
    for rec in records.values():
        if rec['cause_action_id'] is None:continue
        pair=byaction.get(rec['cause_action_id'])
        if pair is None:c.missing.add('MISSING_TRANSITION_RECEIPT');continue
        a,t=pair
        nominal=None
        if rec['capture_sha256'] in bycandidate:
            candidate=bycandidate[rec['capture_sha256']];nominal=P._source_ns(candidate['source_time'],candidate['source_time']['adc_tick_ms'])
        sample=c.samplemap.get(rec['adc_book_source_sha256'])
        if sample is not None:_same(nominal,sample['nominal_qpc_ns']);nominal=sample['nominal_qpc_ns']
        if t is not None and nominal is not None and t['completion_observed_qpc_ns'] is not None:_need(t['completion_observed_qpc_ns']<nominal)
    if book is not None and transitions and transitions[-1]['state']=='COMPLETE':
        last=transitions[-1];cur=book['current_pose_interval']
        if cur is not None:_same(cur['root_revision'],last['after_root_revision'],'LINEAGE_CONTRADICTION');_same(cur['pose_revision'],last['to_pose_revision'],'LINEAGE_CONTRADICTION')
    return actions

def _project(request):
    c=Check(request);c.scan(request)
    candidates=request['history']+([]if request['candidate'] is None else[request['candidate']])
    c.want(request['candidate']);root=c.want(request['root_receipt']);book=request['actor_book']
    records=[]if root is None or root['captures'] is None else root['captures']
    reg=None if root is None else root['actor_registry'];associations=[]if reg is None or reg['associations'] is None else reg['associations']
    stepcount=sum(a['transition_key']['kind']=='STEP' for a in associations)
    _need(max(len(candidates),len(records))+stepcount<=32,'BUDGET_EXCEEDED')
    c.source(book)
    config,admissions,bycandidate,byrecord=_source_checks(c,candidates,root)
    observations=_captures(c,config,admissions,bycandidate,byrecord)
    actions=_actors(c,root,bycandidate,byrecord)
    # Validate pose receipt internal ordering even without candidate/book selection.
    for rec in byrecord.values():
        for name in ('adc_pose','em_pose'):
            p=rec[name]
            if p is None:continue
            read=p['pose_read'];nominal=p['nominal_source_qpc_ns']
            if read is not None:_le(nominal,read['begin_qpc_ns'])
            if name=='adc_pose' and read is not None and rec['adc_call'] is not None:_le(read['end_qpc_ns'],rec['adc_call']['begin_qpc_ns'])
            c.pose(p['pose'],p['pose_revision'],rec['adc_root_revision'] if name=='adc_pose' else rec['em_root_revision'])
    result=dict(schema_version=2,abi_id='moving_interval_book_projection_v2',diagnostic_only=True,authorization='none',claim='numerical_immutable_committed_root_only',native_interval_atomic=False,core_sha256=CORE_SHA256,core_ran=False,input_status='INPUT_UNAVAILABLE',status='STOP',reason='MISSING_ORIGINAL_ASSOCIATION',public_input=None)
    if request['evidence_scope']=='unassociated_diagnostic':c.missing.add('MISSING_ORIGINAL_ASSOCIATION')
    if c.missing:
        order=['INTERVAL_BOUNDARY_UNAVAILABLE','SOURCE_TIME_IN_TRANSITION_GAP','ACTOR_PENDING_OR_FAILED','MISSING_CURRENT_READ','MISSING_SOURCE_ADMISSION','MISSING_NATIVE_CAPTURE','MISSING_TRANSITION_RECEIPT','MISSING_RETURNED_RECEIPT','MISSING_GETTER_PUBLICATION','MISSING_CUSTODY','MISSING_ORIGINAL_ASSOCIATION']
        result['reason']=next(x for x in order if x in c.missing);return result
    if not request.get('enabled',False):result.update(input_status='DISABLED',reason='disabled');return result
    if c.stale:result['reason']='ORIGINAL_SOURCE_EXPIRED';return result
    public=dict(schema_version=1,projection_id='c36_c28_public_view_v1',enabled=True,now_qpc_ns=c.now,pose=root['current_pose']['pose'],goal_m=config['goal_m'],observation=observations[-1],history=observations[:-1],executed_actions=actions)
    _shape(public,_PUBLIC,_PUBLIC)
    _need(len(_json(public))<=16380,'PROOF_ENVELOPE_TOO_LARGE')
    result.update(input_status='PROJECTED',status='PROJECTION_READY',reason='validated_diagnostic_projection',public_input=public)
    return result

def project_interval_json(full_proof):
    """Strict full proof -> host-only projection result; C28 is never called."""
    request=_parse(full_proof)
    try:result=_project(request)
    except P.Rejected:
        raise Rejected('IDENTITY_CONTRADICTION') from None
    raw=_json(result);_need(len(raw)<=32768,'BUDGET_EXCEEDED')
    return raw

"""NEW C34 controls. Frozen example JSON is data; no prior test suite is run."""
import copy, hashlib, importlib.util, json, sys, traceback
from pathlib import Path

P = Path(__file__).resolve().parent
H = P.parent
spec = importlib.util.spec_from_file_location('new_c34_under_test', P/'root_book_stale_composition_v1.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
data = (H/'C-DEEPEYE-ROOT-BOOK-C30-PROJECTION-20261030-31/interface-examples.json').read_bytes()
assert hashlib.sha256(data).hexdigest() == '8db30425213f590b531ce8d3b9e554ffe91402c94fc74843b4d533d3c9e538fd'
EXAMPLES = json.loads(data)['examples']
LAST_INPUT = None

def fresh(index=0):
    q = copy.deepcopy(EXAMPLES[index]['input'])
    q['adapter_id'] = M.ADAPTER_ID
    q['external']['config']['goal_m'] = [0.25,0.0,2.0]
    return q

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

def line(value):
    return (encode(value)+b'\n').decode()

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def call(q, core=0, c32=1):
    global LAST_INPUT
    LAST_INPUT = copy.deepcopy(q)
    counts = {'core':0,'c32':0,'wrong_core_object':0}
    original = M._C32._ORIGINAL
    module = M._C32._CORE_MODULE
    assert original is module.recommend
    before = {k:id(v) for k,v in original.__globals__.items()}
    def trace(frame,event,arg):
        if event == 'call':
            if frame.f_code is original.__code__: counts['core'] += 1
            elif frame.f_code.co_name == 'recommend' and frame.f_code.co_filename.endswith('candidate_four_channel_planner_v1.py'):
                counts['wrong_core_object'] += 1
            if frame.f_code is M._C32.recommend_json.__code__: counts['c32'] += 1
        return trace
    sys.setprofile(trace)
    try:
        result = json.loads(M.project_json(encode(q)))
    finally:
        sys.setprofile(None)
    assert counts == {'core':core,'c32':c32,'wrong_core_object':0}, counts
    assert before == {k:id(v) for k,v in original.__globals__.items()}
    assert result['core_ran'] == bool(core)
    assert result['authorization'] == 'none' and not result['native_interval_atomic']
    return result

def reject(q, contains=None):
    global LAST_INPUT
    LAST_INPUT = copy.deepcopy(q)
    core = [0]
    def trace(frame,event,arg):
        if event == 'call' and frame.f_code is M._C32._ORIGINAL.__code__: core[0] += 1
    sys.setprofile(trace)
    try:
        try: M.project_json(encode(q))
        except M.Rejected as error:
            if contains: assert contains in str(error), str(error)
        else: raise AssertionError('expected Rejected')
    finally: sys.setprofile(None)
    assert core[0] == 0

def unavailable(q,c32=1):
    r = call(q,c32=c32)
    assert r['input_status'] == 'INPUT_UNAVAILABLE' and r['status'] == 'STOP'
    assert r['projection'] is None and r['c32_result'] is None
    return r

def change_now(q,now):
    q['external']['now_qpc_ns'] = now
    q['external']['action_registry']['as_of_qpc_ns'] = now
    q['book_current']['at_qpc_ns'] = now
    q['book_current']['pose_read'] = {'begin_qpc_ns':now-2000,'end_qpc_ns':now}
    q['book_current']['valid_span']['through_qpc_ns'] = now
    q['book']['fixed_root_interval']['through_qpc_ns'] = now

def raw_rehash(q,request,capture):
    c = q['external']['candidate']; r = q['external']['captures'][0]
    r['request_raw'] = line(request)
    capture['request_sha256'] = digest(r['request_raw'])
    r['capture_raw'] = line(capture)
    old = r['capture_sha256']; r['capture_sha256'] = digest(r['capture_raw'])
    c['observation_identity']['request_sha256'] = capture['request_sha256']
    c['observation_identity']['capture_sha256'] = r['capture_sha256']
    if r['em_origin_capture_sha256'] == old: r['em_origin_capture_sha256'] = r['capture_sha256']

def delayed_latest(q,age,admission=False):
    c = q['external']['candidate']; t = c['source_time']; ident = c['observation_identity']
    nominal = t['source_start_monotonic_ns']+t['adc_tick_ms']*1000000
    at = nominal+age
    if admission:
        t['admission_received_monotonic_ns'] = at
        q['external']['source_admissions'][-1]['received_qpc_ns'] = at
        ident['original_host_injection_qpc_ns'] = [at]*4
        r = q['external']['captures'][0]
        request = json.loads(r['request_raw']); capture = json.loads(r['capture_raw'])
        request['original_host_qpc_ns'] = [at]*4
        for lane in capture['captures']:
            lane['raw_words'][2:4] = [at & 0xffffffff, at>>32]
        raw_rehash(q,request,capture)
    ident['receiver_upper_qpc_ns'] = at
    t['adc_source_age_ns'] = t['em_source_age_ns'] = age
    flags = c['diagnostic_flags']; flags['source_fresh_at_capture'] = age <= 100000000
    flags['injection_to_receiver_upper_ns'] = at-ident['original_host_injection_qpc_ns'][0]
    flags['target100ms_met'] = flags['injection_to_receiver_upper_ns'] <= 100000000
    change_now(q,at)

def bare():
    q = fresh(); q['book'] = q['book_current'] = q['binding'] = None
    e = q['external']
    for key in ('candidate','config','source_admissions','captures','current_pose','action_registry'): e[key] = None
    e['history'] = []
    return q

def records_pair(clash=False):
    q = bare(); first = copy.deepcopy(fresh()['external']['captures'][0]); second = copy.deepcopy(first)
    for r in (first,second):
        for key in ('adc_pose','em_pose','adc_book_source_sha256','em_book_source_sha256','em_origin_capture_sha256'): r[key] = None
    req = json.loads(second['request_raw']); cap = json.loads(second['capture_raw'])
    req['request_seq'] = cap['request_seq'] = 2; cap['trigger_id'] += 1
    second['request_raw'] = line(req); cap['request_sha256'] = digest(second['request_raw'])
    cap['final_counters'] = [9 if clash else 8,2,8]
    for ch,lane in enumerate(cap['captures']):
        lane['pipeline_counters'] = [cap['final_counters'][0],2,5+ch]
        lane['raw_words'][4:6] = [4,7]; lane['raw_words'][7] += 1
    second['capture_raw'] = line(cap); second['capture_sha256'] = digest(second['capture_raw'])
    q['external']['captures'] = [first,second]
    return q

def test_core_default_and_single_object():
    q = fresh(); original = copy.deepcopy(q)
    r = call(q,core=1)
    assert r['input_status'] == 'COMPLETE_DIAGNOSTIC'
    assert r['projection']['root_receipt']['captures'][0]['adc_pose']['pose_revision'] == 0
    assert q == original
    q.pop('enabled'); r = call(q)
    assert r['input_status'] == 'DISABLED' and r['projection']['enabled'] is False
    assert r['projection']['now_qpc_ns'] > 2**53
    assert M._C32._ORIGINAL.__code__ is M._C32._CORE_MODULE.recommend.__code__

def test_held_and_null_valid_zero():
    q = fresh(1); r = call(q,core=1)
    entries = r['projection']['root_receipt']['captures']
    assert entries[-1]['em_pose'] == entries[0]['em_pose']
    assert q['external']['candidate']['channel_counts'][-1] == 0
    assert q['external']['source_admissions'][0]['channel_counts'][-1] is None

def test_stage_missing_c32_call_and_null_empty():
    q = fresh(); q['book'] = None; unavailable(q)
    q = fresh(); q['external']['captures'] = None; unavailable(q)
    q['external']['captures'] = []; reject(q,'one Root association')
    q['external']['captures'] = [None]; unavailable(q)

def test_missing_raw_and_admission_contradiction():
    q = fresh(); q['book'] = None; q['external']['config'] = None
    cap = json.loads(q['external']['captures'][0]['capture_raw'])
    cap['captures'][2]['pipeline_counters'][0] += 1
    req = json.loads(q['external']['captures'][0]['request_raw']); raw_rehash(q,req,cap)
    reject(q,'counter')
    q = fresh(); q['book'] = None; q['external']['captures'] = None
    q['external']['source_admissions'][-1]['new_em_sample'] = False
    reject(q,'native')

def test_partial_current_and_action_conflicts():
    q = fresh(); q['binding'] = None; q['external']['current_pose']['receipt_id'] = None
    q['book_current']['pose']['position_m'][0] = 0.5
    reject(q,'same revision')
    q = bare(); pose = fresh()['book_current']['pose']; now = q['external']['now_qpc_ns']
    registry = copy.deepcopy(fresh()['external']['action_registry'])
    registry['actions'] = [dict(receipt_id=None,action_id='new-partial-1',state='executed',
        observation_capture_sha256='1'*64,at_qpc_ns=now-1,from_pose=pose,to_pose=pose,
        from_pose_revision=7,to_pose_revision=None),dict(receipt_id=None,action_id='new-partial-2',state='executed',
        observation_capture_sha256='2'*64,at_qpc_ns=now,from_pose=pose,to_pose=pose,
        from_pose_revision=6,to_pose_revision=None)]
    q['external']['action_registry'] = registry; reject(q,'revision reversal')
    registry['actions'][1]['from_pose_revision'] = 8; unavailable(q,c32=0)

def test_records_only_counter_consistency():
    unavailable(records_pair(),c32=0)
    reject(records_pair(True),'records cross-capture counter')
    q = records_pair(); q['external']['captures'][1]['request_raw'] = None
    unavailable(q,c32=0)

def test_absent_current_config_history_anchor():
    q = bare(); q['external']['config'] = copy.deepcopy(fresh()['external']['config'])
    q['external']['config']['generation'] = 0; reject(q,'positive supplied config')
    q = fresh(); q['external']['history'] = [q['external']['candidate']]; q['external']['candidate'] = None
    unavailable(q,c32=0)
    q['external']['config']['source_start_monotonic_ns'] += 1
    q['book'] = None; reject(q,'original anchor')

def test_high_qpc_now_boundary():
    q = fresh(); t = q['external']['candidate']['source_time']; nominal=t['source_start_monotonic_ns']+100000000
    change_now(q,nominal+100000000); call(q,core=1)
    change_now(q,nominal+100000001); r=call(q)
    assert r['c32_result']['reason'] == 'original_source_expired_now'

def test_high_qpc_capture_boundary():
    q = fresh(); delayed_latest(q,100000000); call(q,core=1)
    q = fresh(); delayed_latest(q,100000001); r=call(q)
    assert r['c32_result']['reason'] == 'original_source_expired_at_capture'

def test_high_qpc_admission_boundary_and_late_conflict():
    q = fresh(); delayed_latest(q,100000000,True); call(q,core=1)
    q = fresh(); delayed_latest(q,100000001,True); r=call(q)
    assert r['c32_result']['reason'] == 'original_source_expired_at_admission'
    q.pop('enabled'); assert call(q)['input_status'] == 'DISABLED'
    q['book'] = None; q['external']['source_admissions'][-1]['new_em_sample'] = False
    reject(q,'native')

def prefix(q,count):
    origin=fresh()['external']['config']['source_start_monotonic_ns']
    q['external']['config']=copy.deepcopy(fresh()['external']['config'])
    q['external']['now_qpc_ns']=origin+11000000000
    items=[]
    for i in range(count):
        tick=i*10; em=(tick//50)*50; quality=(15 if i>=9 else 7) | (0x700 if em!=tick else 0)
        items.append(dict(index=i,adc_tick_ms=tick,em_tick_ms=em,channel_counts=[1740,2048,2048,0 if i>=9 else None],
            quality=quality,source_record_sha256=hashlib.sha256(str(i).encode()).hexdigest(),
            received_qpc_ns=origin+tick*1000000+3000000,new_em_sample=em==tick))
    q['external']['source_admissions']=items

def test_prefix_and_window_caps():
    q=bare(); prefix(q,1001); unavailable(q,c32=0)
    q['external']['source_admissions'][-1]['index']=999; reject(q,'prefix')
    q=bare(); prefix(q,1002); reject(q,'array budget')
    q=bare(); prefix(q,1001); a=q['external']['source_admissions'][-1]
    a['adc_tick_ms']=10010; a['quality'] |= 0x700; a['new_em_sample']=False
    a['received_qpc_ns']+=10000000; reject(q,'source window')

def test_combined_null_array_and_strict_json():
    q=bare(); q['external']['captures']=[None]*32; unavailable(q,c32=0)
    registry=copy.deepcopy(fresh()['external']['action_registry']); pose=fresh()['book_current']['pose']
    registry['actions']=[dict(receipt_id=None,action_id='new-over32',state='executed',observation_capture_sha256='1'*64,
        at_qpc_ns=q['external']['now_qpc_ns'],from_pose=pose,to_pose=pose,from_pose_revision=None,to_pose_revision=None)]
    q['external']['action_registry']=registry; reject(q,'combined')
    for raw in (b'{"x":0,"x":1}',b'{"x":NaN}',b' '*1048577):
        try: M.project_json(raw)
        except M.Rejected: pass
        else: raise AssertionError('strict JSON accepted')
    q=bare(); q['external']['history']=[None]*33; reject(q,'array budget')

def test_source_contract_archive_and_schema():
    q=bare(); unavailable(q,c32=0)
    q['book_source_commit']='4dc91fd24531b3df53fc916e8b7f509ad524592c'; reject(q,'pinned source')
    q=fresh(); q['book']['schema']=2; reject(q,'schema')
    raw=(H/'C-DEEPEYE-ACTOR-COMPLETION-TIME-SEMANTICS-20261030-33/retired-source70.json').read_bytes()
    counts=[0]
    def trace(frame,event,arg):
        if event=='call' and frame.f_code in (M._C32.recommend_json.__code__,M._C32._ORIGINAL.__code__): counts[0]+=1
    sys.setprofile(trace)
    try: r=M.inspect_retired_source70(raw)
    finally: sys.setprofile(None)
    assert counts==[0] and r['original_runtime_commit'].startswith('4dc91') and r['book_schema_version']==1
    assert not any(k in r for k in ('now_qpc_ns','candidate','context','owner_binding_id'))
    for bad in (raw+b' ',raw[:-1]+b' ',raw.decode()):
        try: M.inspect_retired_source70(bad)
        except M.Rejected: pass
        else: raise AssertionError('archive gate accepted changed bytes/type')

def test_absent_candidate_request_sequence():
    q=records_pair(); q['external']['captures']=q['external']['captures'][:1]
    r=q['external']['captures'][0]; r['capture_raw']=None
    raw=json.loads(r['request_raw']); raw['request_seq']=0; r['request_raw']=line(raw)
    reject(q,'request sequence')

def test_absent_candidate_request_future_or_reversed():
    q=records_pair(); q['external']['captures']=q['external']['captures'][:1]
    r=q['external']['captures'][0]; r['capture_raw']=None
    raw=json.loads(r['request_raw']); raw['original_host_qpc_ns']=[q['external']['now_qpc_ns']+1]*4
    r['request_raw']=line(raw); reject(q,'request times')
    raw['original_host_qpc_ns']=[100,99,100,100]; r['request_raw']=line(raw); reject(q,'request times')

def test_absent_request_valid_counterpart_and_same_chain():
    q=records_pair(); q['external']['captures']=q['external']['captures'][:1]
    q['external']['captures'][0]['capture_raw']=None
    unavailable(q,c32=0)
    call(fresh(),core=1)
    q=fresh(); q.pop('enabled'); assert call(q)['input_status']=='DISABLED'

def capture_only_mutation(word,increment=1):
    q=records_pair(); q['external']['captures']=q['external']['captures'][:1]
    r=q['external']['captures'][0]; r['request_raw']=None
    cap=json.loads(r['capture_raw']); cap['captures'][0]['raw_words'][word]+=increment
    r['capture_raw']=line(cap); r['capture_sha256']=digest(r['capture_raw'])
    return q

def test_capture_only_actual_identity_words():
    for word,delta in ((4,1),(5,1),(6,-1),(7,1),(8,1),(1,1)):
        reject(capture_only_mutation(word,delta),'capture identity words')

def test_capture_only_actual_qpc():
    q=capture_only_mutation(3,1)
    reject(q,'capture times')
    q=records_pair(); q['external']['captures']=q['external']['captures'][:1]
    q['external']['captures'][0]['request_raw']=None
    unavailable(q,c32=0)

def test_capture_generation_and_final_core_chain():
    q=records_pair(); q['external']['captures']=q['external']['captures'][:1]
    r=q['external']['captures'][0]; r['request_raw']=None
    cap=json.loads(r['capture_raw']); cap['generation']=0
    for lane in cap['captures']: lane['raw_words'][8]=0
    r['capture_raw']=line(cap); r['capture_sha256']=digest(r['capture_raw'])
    reject(q,'positive capture generation')
    call(fresh(),core=1)
    q=fresh(1); q['book']=None; unavailable(q)
    unavailable(records_pair(),c32=0)

def large_projection(padded):
    q=fresh(); prefix(q,1001); q['enabled']=False
    origin=q['external']['config']['source_start_monotonic_ns']; now=q['external']['now_qpc_ns']
    change_now(q,now)
    samples=[]; candidates=[]; records=[]
    template=fresh(); ts=template['book']['samples'][-1]
    for i in range(32):
        index=100+i*5; tick=index*10; nominal=origin+tick*1000000; shift=(tick-100)*1000000
        sample=copy.deepcopy(ts); sample['tick_ms']=tick; sample['source_count']=i+1
        sample['nominal_qpc_ns']=nominal; sample['source_sha256']=hashlib.sha256(('new-book-'+str(i)).encode()).hexdigest()
        for key in ('payload','canonical_source_hex'): sample.pop(key,None)
        for read in sample['pose_reads'].values():
            read['begin_qpc_ns']+=shift; read['end_qpc_ns']+=shift
        for key in ('begin_qpc_ns','end_qpc_ns','end_attempt_qpc_ns'): sample['adc'][key]+=shift
        sample['numerical_pose_span']['through_qpc_ns']+=shift
        samples.append(sample)
        c=copy.deepcopy(template['external']['candidate']); t=c['source_time']; ident=c['observation_identity']
        t['adc_tick_ms']=t['em_tick_ms']=tick; t['admission_received_monotonic_ns']=nominal+3000000
        ident['request_seq']=i+1; ident['trigger_id']=4001+i; ident['source_admission_index']=index
        ident['original_host_injection_qpc_ns']=[nominal+3500000+j for j in range(4)]
        ident['receiver_upper_qpc_ns']=nominal+4000000
        r=copy.deepcopy(template['external']['captures'][0]); req=json.loads(r['request_raw']); cap=json.loads(r['capture_raw'])
        req['request_seq']=cap['request_seq']=i+1; req['original_host_qpc_ns']=ident['original_host_injection_qpc_ns']
        r['request_raw']=line(req); cap['request_sha256']=digest(r['request_raw']); cap['trigger_id']=4001+i
        cap['final_counters']=[4*(i+1),i+1,4*(i+1)]
        for ch,lane in enumerate(cap['captures']):
            at=ident['original_host_injection_qpc_ns'][ch]
            lane['pipeline_counters']=[4*(i+1),i+1,4*i+ch+1]
            lane['raw_words'][2:6]=[at & 0xffffffff,at>>32,4*i,4*(i+1)-1]
            lane['raw_words'][7]=4001+i
        encoded=encode(cap)
        r['capture_raw']=(encoded+(b' '*(15000-len(encoded)-1) if padded else b'')+b'\n').decode()
        r['capture_sha256']=digest(r['capture_raw']); r['source_record_sha256']=q['external']['source_admissions'][index]['source_record_sha256']
        ident['capture_sha256']=r['capture_sha256']; ident['request_sha256']=cap['request_sha256']
        r['em_origin_capture_sha256']=r['capture_sha256']
        r['adc_book_source_sha256']=r['em_book_source_sha256']=sample['source_sha256']
        for kind in ('adc','em'):
            r[kind+'_pose']['source_admission_index']=index; r[kind+'_pose']['receipt_id']='new-'+kind+'-'+str(i)
        candidates.append(c); records.append(r)
    q['book']['samples']=samples; q['external']['candidate']=candidates[-1]; q['external']['history']=candidates[:-1]
    q['external']['captures']=records
    return q

def test_aggregate_output_cap():
    q=large_projection(False); r=call(q)
    assert r['input_status']=='DISABLED' and len(r['projection']['root_receipt']['captures'])==32
    q=large_projection(True); assert len(encode(q))<1048576
    reject(q,'encoded output budget')

GROUPS={
    'repair-expectations':[test_stage_missing_c32_call_and_null_empty,test_prefix_and_window_caps],
    'raw-missing':[test_absent_candidate_request_sequence,test_absent_candidate_request_future_or_reversed],
    'raw-fix':[test_absent_candidate_request_sequence,test_absent_candidate_request_future_or_reversed,
        test_absent_request_valid_counterpart_and_same_chain],
    'capture-only':[test_capture_only_actual_identity_words,test_capture_only_actual_qpc],
    'capture-fix':[test_capture_only_actual_identity_words,test_capture_only_actual_qpc,
        test_capture_generation_and_final_core_chain],
    'aggregate':[test_aggregate_output_cap],
    'core':[test_core_default_and_single_object,test_held_and_null_valid_zero],
    'partial':[test_stage_missing_c32_call_and_null_empty,test_missing_raw_and_admission_contradiction,
        test_partial_current_and_action_conflicts,test_records_only_counter_consistency,test_absent_current_config_history_anchor],
    'time':[test_high_qpc_now_boundary,test_high_qpc_capture_boundary,test_high_qpc_admission_boundary_and_late_conflict],
    'caps':[test_prefix_and_window_caps,test_combined_null_array_and_strict_json,test_source_contract_archive_and_schema],
}

if __name__=='__main__':
    group=sys.argv[1]; results=[]
    for test in GROUPS[group]:
        try:
            test(); results.append({'test':test.__name__,'passed':True})
        except Exception:
            results.append({'test':test.__name__,'passed':False,'traceback':traceback.format_exc(),'last_input':LAST_INPUT})
    print(json.dumps({'group':group,'runtime_sha256':hashlib.sha256((P/'root_book_stale_composition_v1.py').read_bytes()).hexdigest(),
                      'results':results},ensure_ascii=True))
    sys.exit(0 if all(r['passed'] for r in results) else 1)

"""NEW C32-R1 counter controls only; no earlier suite import or case replay."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
ORIGIN = (1 << 55) + 123
POSE = {'position_m': [0., 0., 0.], 'orientation_xyzw': [0., 0., 0., 1.]}
PATH = Path(__file__).with_name('private_raw4_time_association_v2.py')
SPEC = importlib.util.spec_from_file_location('C32_counter_repair', PATH)
abi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(abi)

def sha(value):
    return hashlib.sha256(abi._json_bytes(value)).hexdigest()

def bracket(begin, end):
    return {'begin_qpc_ns': begin, 'end_qpc_ns': end}

def span(begin, end, label='synthetic-span'):
    return {'receipt_id': label, 'from_qpc_ns': begin, 'through_qpc_ns': end}

def pose_receipt(index, nominal, role):
    begin = nominal + (500000 if role == 'em' else 2000000)
    return {'receipt_id': 'synthetic-'+role+'-read-'+str(index), 'source_admission_index': index,
            'nominal_source_qpc_ns': nominal, 'pose': copy.deepcopy(POSE), 'pose_revision': 0,
            'pose_read': bracket(begin, begin+100000), 'valid_span': span(nominal, nominal+2800000)}

def fixture(tick=100, held=False):
    """Completely synthetic original book; none of these receipts came from A."""
    context = dict(operation_id='synthetic-C30', request_hash='1'*64, tested_commit='2'*40,
                   build_manifest_sha256='3'*64, boot_id='synthetic-kernel-instance',
                   session_id='S'*192, tag=(1 << 32)-1, clock_domain_id='4'*32)
    generation = (1 << 31)+9
    config = dict(receipt_id='synthetic-config', context=context, generation=generation,
        profile_id=abi.PROFILE, producer_sha256=abi.PRODUCER_SHA256,
        source_policy='candidate_causal_source_v1', quality_encoding=abi.ENCODING,
        source_mode='twin_fixture', transport_source='software_fixture',
        source_start_tick_ms=0, source_start_monotonic_ns=ORIGIN, goal_m=[0., 0., 2.],
        baseline_counters=[0, 0, 0], initial_trigger_id=4000,
        pose_book_id='synthetic-original-book', owner_binding_id='synthetic-owner-binding')
    admissions = []
    for index, adc in enumerate(range(0, tick+1, 10)):
        em = adc//50*50
        counts = [1740, 2048, 2048, 0 if adc >= 90 else None]
        quality = 7 | (8 if adc >= 90 else 0) | (0x700 if adc > em else 0)
        admissions.append(dict(index=index, adc_tick_ms=adc, em_tick_ms=em,
            channel_counts=counts, quality=quality, source_record_sha256=sha(['synthetic-source', adc, counts, quality]),
            received_qpc_ns=ORIGIN+adc*1000000+3000000, new_em_sample=(adc == em)))
    selected = [tick//50*50, tick] if held else [tick]
    candidates, records = [], []
    for seq, tick in enumerate(selected, 1):
        adm = admissions[tick//10]; em = adm['em_tick_ms']; q = adm['quality']; nominal = ORIGIN+tick*1000000
        times = [nominal+3500000+i for i in range(4)]
        lane_quality = [((q >> i) & 1) | (((q >> (4+i)) & 1) << 1) |
                        (((q >> (8+i)) & 1) << 2) | (((q >> 12) & 1) << 3) for i in range(4)]
        request = dict(schema=1, kind='diagnostic_scan', context=context, request_seq=seq,
            source_id=4, source='software_fixture', values=[0 if v is None else v for v in adm['channel_counts']],
            qualities=lane_quality, original_host_qpc_ns=times)
        request_raw = abi._json_bytes(request, True)
        trigger = 4000+seq
        capture = dict(schema=1, kind='diagnostic_capture', context=context, request_seq=seq,
            request_sha256=hashlib.sha256(request_raw).hexdigest(), generation=generation, trigger_id=trigger,
            captures=[dict(channel=i, ack_returned=True,
                raw_words=[request['values'][i], i | lane_quality[i] << 8, times[i] & 0xffffffff, times[i] >> 32,
                           4*(seq-1), 4*seq-1, context['tag'], trigger, generation, 123],
                pipeline_counters=[4*seq, seq, 4*(seq-1)+i+1]) for i in range(4)],
            final_counters=[4*seq, seq, 4*seq])
        capture_raw = abi._json_bytes(capture, True); frame = hashlib.sha256(capture_raw).hexdigest()
        receiver = nominal+4000000
        candidate = dict(schema=1, kind='candidate_four_channel_input', profile_id=abi.PROFILE,
            profile_status='candidate_only', profile_note=abi.NOTE, source_mode='twin_fixture',
            quality_encoding=abi.ENCODING, source_id=4, transport_source='software_fixture',
            channel_names=list(abi.CHANNELS), channel_counts=list(adm['channel_counts']), quality=q,
            source_time=dict(adc_tick_ms=tick, em_tick_ms=em, source_start_tick_ms=0,
                source_start_monotonic_ns=ORIGIN, admission_received_monotonic_ns=adm['received_qpc_ns'],
                adc_source_age_ns=4000000, em_source_age_ns=receiver-(ORIGIN+em*1000000), time_basis=abi.TIME_BASIS),
            observation_identity=dict(context=copy.deepcopy(context), request_seq=seq,
                request_sha256=capture['request_sha256'], capture_sha256=frame, generation=generation,
                trigger_id=trigger, source_admission_index=tick//10,
                original_host_injection_qpc_ns=times, receiver_upper_qpc_ns=receiver),
            diagnostic_flags=dict(source_fresh_at_capture=True, all_channels_valid=q & 15 == 15,
                injection_to_receiver_upper_ns=500000, target100ms_met=True,
                target100ms_scope='conservative_receiver_upper_bound', formal_100ms_acceptance='not_run',
                formal_H12='not_run', transport_authenticated=False, BOOT_authenticated=False,
                physical_sample_authenticated=False, compression_verified=False,
                CPU_completion_created=False, movement_authorized=False))
        candidates.append(candidate)
        records.append(dict(capture_sha256=frame, source_record_sha256=adm['source_record_sha256'],
            request_raw=request_raw.decode(), capture_raw=capture_raw.decode(),
            adc_pose=pose_receipt(tick//10, nominal, 'adc'),
            em_pose=(pose_receipt(tick//10, nominal, 'em') if em == tick else copy.deepcopy(records[0]['em_pose'])),
            em_origin_capture_sha256=(frame if em == tick else records[0]['capture_sha256']),
            cause_action_id=None, adc_call=bracket(nominal+2200000, nominal+2800000)))
    now = ORIGIN+selected[-1]*1000000+5000000
    root = dict(kind='c30_root_time_association_v1', evidence_scope='synthetic_diagnostic_fixture',
        config=config, source_admissions=admissions, captures=records,
        current_pose=dict(receipt_id='synthetic-current-read', context=copy.deepcopy(context), generation=generation,
            at_qpc_ns=now, pose=copy.deepcopy(POSE), pose_revision=0,
            pose_read=bracket(now-2000, now-1000), valid_span=span(ORIGIN, now)),
        action_registry=dict(receipt_id='synthetic-explicit-empty-actions', context=copy.deepcopy(context),
            generation=generation, as_of_qpc_ns=now, actions=[]))
    return dict(schema_version=1, abi_id=abi.ABI, diagnostic_only=True, enabled=True,
        evidence_scope='synthetic_diagnostic_fixture', now_qpc_ns=now,
        candidate=candidates[-1], history=candidates[:-1], root_receipt=root)

def set_now(req, now):
    req['now_qpc_ns'] = now
    cur = req['root_receipt']['current_pose']; cur['at_qpc_ns'] = now
    cur['pose_read'] = bracket(now-2000, now-1000); cur['valid_span']['through_qpc_ns'] = now
    req['root_receipt']['action_registry']['as_of_qpc_ns'] = now

def late_admission(age_ns=100000001, held=False, zero_transport=False):
    """Original source stays fixed; actual admission/transport occurs later."""
    req = fixture(110, True) if held else fixture()
    candidate = req['candidate']; root = req['root_receipt']; rec = root['captures'][-1]
    nominal = ORIGIN+candidate['source_time']['adc_tick_ms']*1000000; received = nominal+age_ns
    root['source_admissions'][-1]['received_qpc_ns'] = received
    candidate['source_time']['admission_received_monotonic_ns'] = received
    times = [received]*4 if zero_transport else [received+500000+i for i in range(4)]
    upper = received if zero_transport else received+1000000
    request = json.loads(rec['request_raw']); request['original_host_qpc_ns'] = times
    req_raw = abi._json_bytes(request, True); req_hash = hashlib.sha256(req_raw).hexdigest()
    capture = json.loads(rec['capture_raw']); capture['request_sha256'] = req_hash
    for i, lane in enumerate(capture['captures']):
        lane['raw_words'][2:4] = [times[i] & 0xffffffff, times[i] >> 32]
    cap_raw = abi._json_bytes(capture, True); cap_hash = hashlib.sha256(cap_raw).hexdigest()
    rec.update(request_raw=req_raw.decode(), capture_raw=cap_raw.decode(), capture_sha256=cap_hash)
    if not held:
        rec['em_origin_capture_sha256'] = cap_hash
    candidate['observation_identity'].update(request_sha256=req_hash, capture_sha256=cap_hash,
        original_host_injection_qpc_ns=times, receiver_upper_qpc_ns=upper)
    candidate['source_time']['adc_source_age_ns'] = upper-nominal
    candidate['source_time']['em_source_age_ns'] = upper-(ORIGIN+candidate['source_time']['em_tick_ms']*1000000)
    candidate['diagnostic_flags']['source_fresh_at_capture'] = candidate['source_time']['em_source_age_ns'] <= abi.AGE_NS
    candidate['diagnostic_flags']['injection_to_receiver_upper_ns'] = upper-times[0]
    set_now(req, upper if zero_transport else upper+1000000)
    return req


def rewrite_capture(req, index, mutate):
    records = req['root_receipt']['captures']; rec = records[index]
    c = (req['history']+[req['candidate']])[index]; old = rec['capture_sha256']
    capture = json.loads(rec['capture_raw']); mutate(capture)
    raw = abi._json_bytes(capture, True); new = hashlib.sha256(raw).hexdigest()
    rec['capture_raw'] = raw.decode(); rec['capture_sha256'] = new
    c['observation_identity']['capture_sha256'] = new
    for item in records:
        if item is not None and item['em_origin_capture_sha256'] == old:
            item['em_origin_capture_sha256'] = new


def counters(capture, seq, base):
    for ch, lane in enumerate(capture['captures']):
        lane['pipeline_counters'] = [base[0]+4*seq, base[1]+seq, base[2]+4*(seq-1)+ch+1]
    capture['final_counters'] = [base[0]+4*seq, base[1]+seq, base[2]+4*seq]


def resequence(req, index, seq, base=(0,0,0)):
    rec = req['root_receipt']['captures'][index]; c = (req['history']+[req['candidate']])[index]
    request = json.loads(rec['request_raw']); request['request_seq'] = seq
    raw = abi._json_bytes(request, True); digest = hashlib.sha256(raw).hexdigest()
    rec['request_raw'] = raw.decode()
    trigger = req['root_receipt']['config']['initial_trigger_id']+seq
    c['observation_identity'].update(request_seq=seq, request_sha256=digest, trigger_id=trigger)
    def change(capture):
        capture.update(request_seq=seq, request_sha256=digest, trigger_id=trigger)
        for lane in capture['captures']:
            lane['raw_words'][4:6] = [4*(seq-1),4*seq-1]; lane['raw_words'][7] = trigger
        counters(capture, seq, base)
    rewrite_capture(req, index, change)


def three_captures():
    parts = [fixture(t) for t in (100,150,200)]; req = parts[-1]
    req['history'] = [part['candidate'] for part in parts[:-1]]
    req['root_receipt']['captures'] = [part['root_receipt']['captures'][0] for part in parts]
    for index in range(3): resequence(req,index,index+1)
    return req


def run(output):
    output.mkdir(exist_ok=True); rows = []
    def check(name, req, expected):
        raw = abi._json_bytes(req); before = copy.deepcopy(req); original_globals = dict(abi._ORIGINAL.__globals__)
        (output/(name+'.input.json')).write_bytes(raw); count = [0]
        def profile(frame,event,arg):
            if event=='call' and frame.f_code is abi._ORIGINAL.__code__: count[0] += 1
        row = dict(name=name,expected=expected,input_sha256=hashlib.sha256(raw).hexdigest(),input_bytes=len(raw))
        sys.setprofile(profile)
        try:
            result = json.loads(abi.recommend_json(raw))
            row['actual'] = {k:result[k] for k in ('input_status','status','reason','core_ran')}
            (output/(name+'.output.json')).write_bytes(abi._json_bytes(result))
            row['passed'] = result['input_status']==expected and result['authorization']=='none'
            row['passed'] &= result['root_receipt']==req['root_receipt'] and result['candidate']==req['candidate']
            row['passed'] &= (result['core_ran'] and count[0]==1) if expected=='COMPLETE_DIAGNOSTIC' else (not result['core_ran'] and count[0]==0)
        except abi.Rejected as exc:
            row['actual'] = {'exception':'Rejected','reason':str(exc)}; row['passed'] = expected=='Rejected' and count[0]==0
        except Exception as exc:
            row['actual'] = {'unexpected_exception':type(exc).__name__,'reason':str(exc)}; row['passed'] = False
        finally: sys.setprofile(None)
        row['core_calls'] = count[0]; row['passed'] &= req==before and original_globals==abi._ORIGINAL.__globals__
        rows.append(row)

    for enabled in (True, False):
        for defect in ('second-lane', 'third-step', 'final-first', 'negative-first', 'negative-second', 'negative-third'):
            req = late_admission(); req['enabled'] = enabled
            def change(capture):
                if defect=='second-lane': capture['captures'][2]['pipeline_counters'][1] += 1
                elif defect=='third-step': capture['captures'][2]['pipeline_counters'][2] += 1
                elif defect=='final-first': capture['final_counters'][0] += 1
                else:
                    base = [0,0,0]; base[('negative-first','negative-second','negative-third').index(defect)] = -1
                    counters(capture,1,base)
            rewrite_capture(req,0,change); req['root_receipt']['config'] = None
            check('new-'+defect+'-'+str(enabled),req,'Rejected')
        req = late_admission(); req['enabled'] = enabled; req['root_receipt']['config'] = None
        check('stale-consistent-missing-config-'+str(enabled),req,'INPUT_UNAVAILABLE' if enabled else 'DISABLED')
    for base in ((0,0,0), ((1<<32)-5,(1<<32)-2,(1<<32)-5)):
        req = fixture(); req['root_receipt']['config']['baseline_counters'] = list(base)
        resequence(req,0,1,base); label='zero' if base==(0,0,0) else 'uint32-high'
        check('complete-feasible-'+label,req,'COMPLETE_DIAGNOSTIC')
        req['root_receipt']['config'] = None; check('missing-feasible-'+label,req,'INPUT_UNAVAILABLE')
    req = fixture(); resequence(req,0,1,(3,5,7))
    check('provided-config-still-required-to-match',req,'Rejected')
    req = fixture(110,True); resequence(req,1,5)
    check('actual-seq-gap-four-complete',req,'COMPLETE_DIAGNOSTIC')
    req['root_receipt']['config'] = None; check('actual-seq-gap-four-missing',req,'INPUT_UNAVAILABLE')
    for component in range(3):
        req = fixture(110,True); base=[0,0,0]; base[component] = 1
        resequence(req,1,5,base); req['root_receipt']['config'] = None
        check('cross-capture-component-'+str(component),req,'Rejected')
    for defect in (False, True):
        req = three_captures()
        if defect: resequence(req,2,3,(0,1,0))
        req['root_receipt']['captures'][1]['capture_raw'] = None; req['root_receipt']['config'] = None
        check('missing-middle-capture-'+str(defect),req,'Rejected' if defect else 'INPUT_UNAVAILABLE')
    req = fixture(110,True); resequence(req,1,2,(0,0,1))
    req['root_receipt']['captures'][1]['request_raw'] = None; req['root_receipt']['config'] = None
    check('missing-request-keeps-cross-capture-comparison',req,'Rejected')
    report={'scope':'NEW_C32_R1_COUNTER_ONLY','candidate_sha256':hashlib.sha256(PATH.read_bytes()).hexdigest(),
        'total':len(rows),'passed':all(r['passed'] for r in rows),'cases':rows,'old_suites_run':False,'original_four_RED_replayed':False}
    print(json.dumps(report)); return 0 if report['passed'] else 1


if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Supply the new counter-control evidence directory.')
    raise SystemExit(run(Path(sys.argv[1])))

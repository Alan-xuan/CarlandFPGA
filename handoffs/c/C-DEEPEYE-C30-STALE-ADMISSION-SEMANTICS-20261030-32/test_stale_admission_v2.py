"""NEW C32 controls. Fixture construction only was adapted; no old suite import/run."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
ORIGIN = (1 << 55) + 123
POSE = {'position_m': [0., 0., 0.], 'orientation_xyzw': [0., 0., 0., 1.]}
abi = None

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


def baseline_red(output_directory):
    global abi
    path = Path(__file__).resolve().parent.parent/'C-DEEPEYE-PRIVATE-RAW4-TIME-ASSOCIATION-20261030-30'/'private_raw4_time_association_v1.py'
    expected = 'abaa06d10ab68f0bee721bf1a6d9278fc000446112ac559362079ad63afc686d'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location('frozen_C30_C32_red', path)
    abi = importlib.util.module_from_spec(spec); spec.loader.exec_module(abi)
    req = late_admission(); raw = abi._json_bytes(req)
    output_directory.mkdir(exist_ok=True)
    (output_directory/'new-stale-input.json').write_bytes(raw)
    report = {'case':'NEW_C32_legal_native_admission_100ms_plus_1ns', 'synthetic':True,
        'runtime_sha256':expected, 'input_sha256':hashlib.sha256(raw).hexdigest(), 'input_bytes':len(raw),
        'original_origin_qpc_ns':ORIGIN, 'nominal_qpc_ns':ORIGIN+100000000,
        'admission_received_qpc_ns':req['candidate']['source_time']['admission_received_monotonic_ns'],
        'admission_age_ns':100000001, 'expected':'INPUT_UNAVAILABLE/STOP/core_ran=false',
        'recommend_calls':1, 'old_suites_run':False}
    try:
        result = abi.recommend(req)
        report['actual'] = {k:result[k] for k in ('input_status','status','core_ran','reason')}
        report['passed'] = result['input_status']=='INPUT_UNAVAILABLE' and result['status']=='STOP' and result['core_ran'] is False
    except abi.Rejected as exc:
        report.update(actual={'exception':'Rejected','reason':str(exc)}, passed=False)
    print(json.dumps(report))
    return 0 if report['passed'] else 1


def new_controls(output_directory):
    global abi
    path = Path(__file__).with_name('private_raw4_time_association_v2.py')
    spec = importlib.util.spec_from_file_location('new_C32_candidate', path)
    abi = importlib.util.module_from_spec(spec); spec.loader.exec_module(abi)
    output_directory.mkdir(exist_ok=True)
    rows = []

    def check(name, req, expected, raw=None):
        original = copy.deepcopy(req); before_globals = dict(abi._ORIGINAL.__globals__)
        data = abi._json_bytes(req) if raw is None else raw
        (output_directory/(name+'.input.json')).write_bytes(data)
        calls = []
        def profile(frame, event, arg):
            if event == 'call' and frame.f_code is abi._ORIGINAL.__code__:
                calls.append(frame.f_code)
        row = {'name':name, 'expected':expected, 'input_sha256':hashlib.sha256(data).hexdigest(), 'input_bytes':len(data)}
        sys.setprofile(profile)
        try:
            result = abi.recommend(req) if raw is None else json.loads(abi.recommend_json(raw))
            row['actual'] = {k:result[k] for k in ('input_status','status','core_ran','reason','independent_em_count')}
            row['passed'] = result['input_status']==expected
            if expected == 'COMPLETE_DIAGNOSTIC':
                row['passed'] &= result['core_ran'] and len(calls)==1
                row['original_map_qpc_ns'] = result['map_cells'][0]['original_em_qpc_ns']
                row['passed'] &= row['original_map_qpc_ns']==ORIGIN+req['candidate']['source_time']['em_tick_ms']*1000000
                if req['history']:
                    row['passed'] &= result['map_cells'][0]['em_pose_receipt']==req['root_receipt']['captures'][0]['em_pose']
            else:
                row['passed'] &= not result['core_ran'] and result['status']=='STOP' and not calls
            row['passed'] &= result['authorization']=='none' and result['candidate']==original['candidate']
            (output_directory/(name+'.output.json')).write_bytes(abi._json_bytes(result))
            result['candidate']['channel_counts'][0] = -1
        except abi.Rejected as exc:
            row['actual'] = {'exception':'Rejected','reason':str(exc)}
            row['passed'] = expected=='Rejected' and not calls
        except Exception as exc:
            row['actual'] = {'unexpected_exception':type(exc).__name__,'reason':str(exc)}
            row['passed'] = False
        finally:
            sys.setprofile(None)
        row['core_calls'] = len(calls)
        row['passed'] &= req==original and abi._ORIGINAL.__globals__==before_globals
        rows.append(row)

    for held in (False, True):
        check('fresh-held' if held else 'fresh-native', fixture(110, True) if held else fixture(), 'COMPLETE_DIAGNOSTIC')
        for delta in (0, 1):
            req = late_admission((90000000 if held else 100000000)+delta, held, True)
            check(('held-em' if held else 'native-adc')+'-100ms-plus-'+str(delta), req,
                  'COMPLETE_DIAGNOSTIC' if delta==0 else 'INPUT_UNAVAILABLE')
    for enabled in (False, True):
        req = late_admission(); req['enabled'] = enabled
        check('pure-stale-'+str(enabled), req, 'INPUT_UNAVAILABLE' if enabled else 'DISABLED')
        for missing in ('config','current_pose','source_admissions','captures'):
            req = late_admission(); req['enabled'] = enabled; req['root_receipt'][missing] = None
            check('missing-'+missing+'-'+str(enabled), req, 'INPUT_UNAVAILABLE' if enabled else 'DISABLED')
        for change in ('prefix-hole','source-hash','capture-hash','raw-context','future-read','negative-age','candidate-source','combined33'):
            req = late_admission(); req['enabled'] = enabled; root = req['root_receipt']; root['config'] = None
            rec = root['captures'][0]
            if change == 'prefix-hole': root['source_admissions'][5]['index'] += 1
            elif change == 'source-hash': rec['source_record_sha256'] = 'f'*64
            elif change == 'capture-hash': rec['capture_raw'] = rec['capture_raw'].replace('123','124')
            elif change == 'raw-context':
                raw_obj = json.loads(rec['request_raw']); raw_obj['context']['boot_id'] += '-wrong'
                rec['request_raw'] = abi._json_bytes(raw_obj, True).decode()
            elif change == 'future-read': rec['adc_pose']['pose_read']['end_qpc_ns'] = req['now_qpc_ns']+1
            elif change == 'negative-age': root['source_admissions'][0]['received_qpc_ns'] = ORIGIN-1
            elif change == 'candidate-source':
                root['captures'] = None; root['source_admissions'][-1]['channel_counts'][0] += 1
            else:
                root['captures'] = [None]*32
                root['action_registry']['actions'] = [dict(receipt_id=None,action_id='missing',state='executed',
                    observation_capture_sha256=req['candidate']['observation_identity']['capture_sha256'],at_qpc_ns=req['now_qpc_ns'],
                    from_pose=copy.deepcopy(POSE),to_pose=copy.deepcopy(POSE),from_pose_revision=None,to_pose_revision=None)]
            check('stale-missing-'+change+'-'+str(enabled), req, 'Rejected')
        for change in ('index','C3','received'):
            req = late_admission(); req['enabled'] = enabled; admissions = req['root_receipt']['source_admissions']
            for adm in admissions[:-1]: adm['received_qpc_ns'] = ORIGIN+101000000
            if change == 'index': admissions[5]['index'] += 1
            elif change == 'C3': admissions[9]['quality'] &= ~8; admissions[9]['channel_counts'][3] = None
            else: admissions[5]['received_qpc_ns'] -= 1
            check('earlier-stale-later-'+change+'-'+str(enabled), req, 'Rejected')
    req = late_admission(); del req['enabled']; check('omitted-enabled-stale', req, 'DISABLED')
    req = late_admission(); req['root_receipt']['source_admissions'].pop()
    check('missing-legal-tail', req, 'INPUT_UNAVAILABLE')
    req = late_admission(90000001, True, True)
    req['history'] = []; req['root_receipt']['captures'] = req['root_receipt']['captures'][1:]
    check('held-missing-original', req, 'INPUT_UNAVAILABLE')
    req = late_admission(90000001, True, True); req['root_receipt']['config'] = None
    req['root_receipt']['captures'][1]['em_pose']['receipt_id'] += '-altered'
    check('held-stale-missing-config-changed-original', req, 'Rejected')
    for absent, broken in (('request_raw','capture_raw'), ('capture_raw','request_raw')):
        req = late_admission(); req['root_receipt']['config'] = None; rec = req['root_receipt']['captures'][0]
        rec[absent] = None; rec[broken] += ' '
        check('missing-'+absent+'-bad-'+broken, req, 'Rejected')
    req = late_admission(); req['root_receipt']['current_pose'] = None
    action = dict(receipt_id=None,action_id='same',state='executed',
        observation_capture_sha256=req['candidate']['observation_identity']['capture_sha256'],at_qpc_ns=req['now_qpc_ns'],
        from_pose=copy.deepcopy(POSE),to_pose=copy.deepcopy(POSE),from_pose_revision=None,to_pose_revision=None)
    req['root_receipt']['action_registry']['actions'] = [action,copy.deepcopy(action)]
    check('stale-missing-current-duplicate-action', req, 'Rejected')
    req = late_admission(); req['root_receipt']['captures'] = None
    req['root_receipt']['config']['initial_trigger_id'] += 1
    check('missing-captures-trigger-conflict', req, 'Rejected')
    req = late_admission(); req['root_receipt']['captures'][0]['adc_pose']['valid_span'] = None
    req['root_receipt']['action_registry']['actions'] = [dict(action, at_qpc_ns=ORIGIN)]
    check('missing-span-action-before-observation', req, 'Rejected')
    req = fixture(10000); check('source-prefix1001', req, 'COMPLETE_DIAGNOSTIC')
    req = fixture(10010, True); check('source-prefix1002', req, 'Rejected')
    req = late_admission(); raw = abi._json_bytes(req); raw = b'{"enabled":true,'+raw[1:]
    check('stale-duplicate-key', req, 'Rejected', raw)
    req = late_admission(); check('bytes-over-limit', req, 'Rejected', b' '*(abi.MAX_BYTES+1))
    for label, value in (('nodes', {'root_receipt':{'source_admissions':[[None]*32 for _ in range(1001)]}}),
                         ('depth', [[[[[[[[[[[[[[[[[None]]]]]]]]]]]]]]]]])):
        try:
            if label=='nodes': abi._tree(value, nodes=[40000])
            else: abi._tree(value)
            passed = False
        except abi.Rejected: passed = True
        rows.append({'name':'tree-'+label,'expected':'Rejected','passed':passed,'core_calls':0})
    report = {'scope':'NEW_C32_ONLY','candidate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'core_sha256':hashlib.sha256(abi._CORE_PATH.read_bytes()).hexdigest(),
        'total':len(rows),'passed':all(r['passed'] for r in rows),'cases':rows,'old_suites_run':False}
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--baseline-red':
        raise SystemExit(baseline_red(Path(sys.argv[2])))
    if len(sys.argv)==3 and sys.argv[1]=='--new-controls':
        raise SystemExit(new_controls(Path(sys.argv[2])))
    raise SystemExit('Select a NEW C32 control mode; no old suite entry is exposed.')

"""NEW C31 synthetic projection controls; no old suite or actual Root run."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('c31_local_controls', HERE/'root_book_projection_v1.py')
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def fixture():
    """Saved frozen synthetic JSON is data, never import/execute old tests.

    New book/binding metadata and link hashes are explicitly synthetic. Payload
    is a private marker, not a claim to have run SourceRecord/producer/native.
    """
    path = HERE.parent/'C-DEEPEYE-PRIVATE-RAW4-TIME-ASSOCIATION-20261030-30/interface-examples.json'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'a0bd1ca6e1d770698c2d881d2ed280b8ed43d66c453b86d3f99a8bdd002fc7a4'
    old = json.loads(raw)['examples'][0]['input']
    root = old['root_receipt']; config = root['config']; now = old['now_qpc_ns']
    origin = config['source_start_monotonic_ns']; pose = root['current_pose']['pose']
    start = origin-1000
    samples = []
    for adm in root['source_admissions']:
        tick = adm['adc_tick_ms']; nominal = origin+tick*1000000
        def read(delta):
            return dict(begin_qpc_ns=nominal+delta, end_qpc_ns=nominal+delta+100000,
                        pose=copy.deepcopy(pose), root_revision=7, pose_revision=0,
                        revoke_generation=0, postcheck_complete=True)
        reads = {'adc': read(2000000)}
        if tick % 50 == 0:
            reads['em'] = read(500000)
        payload = {'synthetic_private_marker': True, 'original_tick': tick}
        samples.append(dict(tick_ms=tick, source_count=adm['index']+1,
            nominal_qpc_ns=nominal, observed_source_qpc_ns=nominal+100,
            opened_qpc_ns=nominal+200, pose_reads=reads,
            adc=dict(begin_qpc_ns=nominal+2200000, end_qpc_ns=nominal+2800000,
                     previous_adc_tick_ms=tick-10 if tick else None,
                     profile_tick_observed=True, postcheck_complete=True,
                     end_attempt_qpc_ns=nominal+2800000), status='complete',
            payload=payload, canonical_source_hex=encoded(payload).hex(),
            source_sha256=sha(payload), numerical_pose_span=dict(from_qpc_ns=start,
                through_qpc_ns=nominal+2800000, root_revision=7, pose_revision=0),
            numerical_pose_span_status='available;fixed_numerical_root_only',
            held_em_association='unavailable;original_native_em_association_not_implemented',
            finish_qpc_ns=nominal+2800000, actual_adc_end_minus_nominal_ns=2800000,
            baseline_span=dict(begin_qpc_ns=start, end_qpc_ns=nominal+2800000,
                root_revision=7, pose_revision=0,
                observation='same committed Root value at checks; not atomic native pose')))
    book = dict(schema=1, state='RUNNING', source_state='RUNNING', failure_reason=None,
        retire_reason=None, source_origin_qpc_ns=origin, start_observed_qpc_ns=origin+1,
        baseline=dict(begin_qpc_ns=start, end_qpc_ns=origin-900, pose=copy.deepcopy(pose),
                      root_revision=7, pose_revision=0, revoke_generation=0),
        samples=samples, partial_samples=[], active_sample=None,
        fixed_root_interval=dict(from_qpc_ns=start, through_qpc_ns=now,
            root_revision=7, pose_revision=0, claim=adapter.CLAIM),
        action_association='unavailable;fixed_revision_only', native_interval_atomic=False,
        source_scope='Root private candidate observations',
        adc_call_evidence='trusted caller bracket and retained profile tick progression')
    current = dict(pose=copy.deepcopy(pose), pose_revision=0, at_qpc_ns=now,
        pose_read=dict(begin_qpc_ns=now-2000, end_qpc_ns=now),
        valid_span=copy.deepcopy(book['fixed_root_interval']), claim=adapter.CLAIM,
        native_interval_atomic=False)
    del current['valid_span']['claim']
    captures = []
    for rec in root['captures']:
        item = {k: copy.deepcopy(rec[k]) for k in ('capture_sha256','source_record_sha256','request_raw',
                    'capture_raw','em_origin_capture_sha256','cause_action_id')}
        for name in ('adc_pose', 'em_pose'):
            old_pose = rec[name]
            item[name] = dict(receipt_id=old_pose['receipt_id'],
                source_admission_index=old_pose['source_admission_index'],
                valid_span_receipt_id=old_pose['valid_span']['receipt_id'])
        item['adc_book_source_sha256'] = samples[-1]['source_sha256']
        item['em_book_source_sha256'] = samples[-1]['source_sha256']
        captures.append(item)
    cur = root['current_pose']
    external = dict(evidence_scope=old['evidence_scope'], now_qpc_ns=now,
        candidate=old['candidate'], history=old['history'], config=config,
        source_admissions=root['source_admissions'], captures=captures,
        current_pose=dict(receipt_id=cur['receipt_id'],context=cur['context'],
            generation=cur['generation'],valid_span_receipt_id=cur['valid_span']['receipt_id']),
        action_registry=root['action_registry'])
    binding = dict(context=copy.deepcopy(config['context']),generation=config['generation'],
        pose_book_id=config['pose_book_id'],owner_binding_id=config['owner_binding_id'],
        committed_pose=copy.deepcopy(pose),pose_revision=0,root_revision=7,
        claim=adapter.CLAIM,native_interval_atomic=False)
    return dict(schema_version=1,adapter_id=adapter.ADAPTER_ID,diagnostic_only=True,enabled=True,
        book_source_commit=adapter.BOOK_SOURCE_COMMIT,book=book,book_current=current,
        binding=binding,external=external)


def held_fixture():
    value = fixture(); ext = value['external']; original = ext['candidate']; old = ext['captures'][0]
    candidate = copy.deepcopy(original); record = copy.deepcopy(old)
    step = 10000000; quality = 0x70f
    candidate['quality'] = quality
    time = candidate['source_time']; time['adc_tick_ms'] = 110
    time['admission_received_monotonic_ns'] += step
    time['em_source_age_ns'] += step
    ident = candidate['observation_identity']; ident['request_seq'] = 2
    ident['trigger_id'] += 1; ident['source_admission_index'] = 11
    ident['original_host_injection_qpc_ns'] = [x+step for x in ident['original_host_injection_qpc_ns']]
    ident['receiver_upper_qpc_ns'] += step
    request = json.loads(record['request_raw']); request['request_seq'] = 2
    request['qualities'] = [5,5,5,1]
    request['original_host_qpc_ns'] = ident['original_host_injection_qpc_ns']
    request_raw = encoded(request)+b'\n'; ident['request_sha256'] = hashlib.sha256(request_raw).hexdigest()
    capture = json.loads(record['capture_raw']); capture['request_seq'] = 2
    capture['request_sha256'] = ident['request_sha256']; capture['trigger_id'] = ident['trigger_id']
    for i,lane in enumerate(capture['captures']):
        ticks = ident['original_host_injection_qpc_ns'][i]
        lane['raw_words'] = [request['values'][i],i | request['qualities'][i]<<8,ticks & 0xffffffff,ticks>>32,
            4,7,ident['context']['tag'],ident['trigger_id'],ident['generation'],123]
        lane['pipeline_counters'] = [8,2,5+i]
    capture['final_counters'] = [8,2,8]
    capture_raw = encoded(capture)+b'\n'; ident['capture_sha256'] = hashlib.sha256(capture_raw).hexdigest()
    record.update(capture_sha256=ident['capture_sha256'],request_raw=request_raw.decode(),capture_raw=capture_raw.decode(),
        source_record_sha256=sha(['synthetic-wire-source',110]),
        adc_pose=dict(receipt_id='synthetic-C31-held-adc',source_admission_index=11,valid_span_receipt_id='synthetic-C31-held-span'))
    adm = copy.deepcopy(ext['source_admissions'][-1]); adm.update(index=11,adc_tick_ms=110,quality=quality,
        received_qpc_ns=time['admission_received_monotonic_ns'],new_em_sample=False,source_record_sha256=record['source_record_sha256'])
    ext['source_admissions'].append(adm)
    sample = copy.deepcopy(value['book']['samples'][-1]); sample.update(tick_ms=110,source_count=12)
    for k in ('nominal_qpc_ns','observed_source_qpc_ns','opened_qpc_ns','finish_qpc_ns'):
        sample[k] += step
    sample['pose_reads'].pop('em')
    for k in ('begin_qpc_ns','end_qpc_ns'):
        sample['pose_reads']['adc'][k] += step
        sample['adc'][k] += step
    sample['adc']['end_attempt_qpc_ns'] += step; sample['adc']['previous_adc_tick_ms'] = 100
    sample['numerical_pose_span']['through_qpc_ns'] += step
    sample['baseline_span']['end_qpc_ns'] += step
    sample['payload'] = {'synthetic_private_marker':True,'original_tick':110}
    sample['canonical_source_hex'] = encoded(sample['payload']).hex(); sample['source_sha256'] = sha(sample['payload'])
    value['book']['samples'].append(sample); record['adc_book_source_sha256'] = sample['source_sha256']
    ext['history'] = [original]; ext['candidate'] = candidate; ext['captures'].append(record)
    ext['now_qpc_ns'] += step; ext['action_registry']['as_of_qpc_ns'] += step
    value['book']['fixed_root_interval']['through_qpc_ns'] += step
    cur = value['book_current']; cur['at_qpc_ns'] += step; cur['valid_span']['through_qpc_ns'] += step
    for k in ('begin_qpc_ns','end_qpc_ns'):
        cur['pose_read'][k] += step
    return value


def invoke(value):
    raw = encoded(value); calls = [0,0]
    def trace(frame,event,arg):
        if event == 'call':
            if frame.f_code is adapter._C30._ORIGINAL.__code__:
                calls[0] += 1
            if frame.f_code is adapter._C30.recommend_json.__code__:
                calls[1] += 1
        return trace
    sys.settrace(trace)
    try:
        output = adapter.project_json(raw)
    except adapter.Rejected as exc:
        print(json.dumps(dict(input_sha256=hashlib.sha256(raw).hexdigest(),input_bytes=len(raw),
            outcome='Rejected',reason=str(exc),core_calls=calls[0],c30_calls=calls[1])))
        raise
    finally:
        sys.settrace(None)
    result = json.loads(output)
    assert calls == [int(result['core_ran']),int(result['c30_called'])], (calls,result)
    print(json.dumps(dict(input_sha256=hashlib.sha256(raw).hexdigest(),input_bytes=len(raw),
        output_sha256=hashlib.sha256(output).hexdigest(),output_bytes=len(output),
        input_status=result['input_status'],core_calls=calls[0],c30_calls=calls[1])))
    return result


class ProjectionControls(unittest.TestCase):
    def test01_fresh_real_json_and_exact_core(self):
        value = fixture(); snapshot = copy.deepcopy(value)
        result = invoke(value)
        self.assertTrue(result['c30_called']); self.assertTrue(result['core_ran'])
        self.assertEqual(result['projection']['candidate'],value['external']['candidate'])
        self.assertEqual(value,snapshot)
        direct = json.loads(adapter._C30.recommend_json(encoded(result['projection'])))
        self.assertEqual(result['c30_result'],direct)
        self.assertEqual(result['claim'],adapter.CLAIM); self.assertFalse(result['native_interval_atomic'])
        self.assertNotIn('synthetic_private_marker',json.dumps(result))
        result['projection']['candidate']['quality'] = -1
        self.assertEqual(value,snapshot)

    def test02_default_disabled(self):
        value = fixture(); value.pop('enabled')
        result = invoke(value)
        self.assertTrue(result['c30_called']); self.assertFalse(result['core_ran'])
        self.assertEqual(result['input_status'],'DISABLED')

    def test03_missing_each_association_never_calls_c30(self):
        paths = [('book',),('book_current',),('binding',),('external','config'),
            ('external','candidate'),('external','source_admissions'),('external','captures'),
            ('external','current_pose'),('external','action_registry'),
            ('external','action_registry','actions'),('binding','committed_pose'),
            ('external','captures',0,'adc_book_source_sha256'),('external','captures',0,'em_book_source_sha256'),
            ('external','captures',0,'adc_pose'),('external','captures',0,'em_pose'),
            ('external','captures',0,'em_origin_capture_sha256'),('external','captures',0,'request_raw'),
            ('external','captures',0,'adc_pose','valid_span_receipt_id')]
        for path in paths:
            with self.subTest(path=path):
                value=fixture(); target=value
                for k in path[:-1]: target=target[k]
                target[path[-1]]=None
                if path==('external','candidate'):
                    value['external']['captures']=None
                result=invoke(value)
                self.assertFalse(result['c30_called']); self.assertFalse(result['core_ran'])
                self.assertIsNone(result['projection']); self.assertIsNone(result['c30_result'])

    def test04_hidden_book_discard_external_reject(self):
        value=fixture(); value['book']['scene_private']={'secret_seed':42}
        result=invoke(value)
        self.assertNotIn('secret_seed',json.dumps(result))
        value=fixture(); value['external']['scene_private']={'secret_seed':42}
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test05_nominal_and_actual_tamper(self):
        for name in ('nominal','reversed_read','late_adc'):
            value=fixture(); sample=value['book']['samples'][-1]
            if name=='nominal': sample['nominal_qpc_ns']+=1
            elif name=='reversed_read': sample['pose_reads']['adc']['begin_qpc_ns']=sample['pose_reads']['adc']['end_qpc_ns']+1
            else: sample['adc']['end_qpc_ns']=value['external']['candidate']['source_time']['admission_received_monotonic_ns']+1
            with self.assertRaises(adapter.Rejected): invoke(value)

    def test06_committed_binding_cannot_be_inferred(self):
        value=fixture(); value['binding']['committed_pose']=None
        self.assertFalse(invoke(value)['c30_called'])
        for field in ('pose_revision','root_revision'):
            value=fixture(); value['binding'][field]+=1
            with self.assertRaises(adapter.Rejected): invoke(value)

    def test07_held_uses_original_sample_and_call(self):
        value=held_fixture(); result=invoke(value)
        self.assertTrue(result['core_ran'])
        records=result['projection']['root_receipt']['captures']
        self.assertEqual(records[0]['em_pose'],records[1]['em_pose'])
        self.assertLess(records[1]['em_pose']['valid_span']['through_qpc_ns'],records[1]['adc_call']['begin_qpc_ns'])

    def test08_held_dual_origin_conflict(self):
        for field in ('em_book_source_sha256','em_origin_capture_sha256'):
            value=held_fixture(); record=value['external']['captures'][-1]
            record[field]=record['adc_book_source_sha256'] if field=='em_book_source_sha256' else record['capture_sha256']
            with self.assertRaises(adapter.Rejected): invoke(value)

    def test09_hash_namespaces_not_equal(self):
        value=fixture(); record=value['external']['captures'][0]
        self.assertNotEqual(record['source_record_sha256'],record['adc_book_source_sha256'])
        result=invoke(value)
        self.assertEqual(result['projection']['root_receipt']['captures'][0]['source_record_sha256'],record['source_record_sha256'])
        record['adc_book_source_sha256']=record['source_record_sha256']
        with self.assertRaises(adapter.Rejected): invoke(value)
        record['em_book_source_sha256']=record['source_record_sha256']
        self.assertFalse(invoke(value)['c30_called'])

    def test10_duplicate_book_hash_and_current_now(self):
        value=fixture(); value['book']['samples'][0]['source_sha256']=value['book']['samples'][-1]['source_sha256']
        with self.assertRaises(adapter.Rejected): invoke(value)
        value=fixture(); value['book_current']['at_qpc_ns']-=1
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test11_missing_does_not_hide_malformed(self):
        for enabled in (False,True):
            value=fixture(); value['enabled']=enabled; value['binding']=None
            value['external']['candidate']['observation_identity']['context']['tag']=False
            with self.assertRaises(adapter.Rejected): invoke(value)
            value=fixture(); value['enabled']=enabled; value['book']=None
            value['external']['captures'][0]['adc_pose']['source_admission_index']=9
            with self.assertRaises(adapter.Rejected): invoke(value)

    def test12_combined_budget_before_missing(self):
        value=fixture(); value['book']=None
        value['external']['captures']*=32
        value['external']['action_registry']['actions']=[{}]
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test13_prefix_and_original_origin(self):
        value=fixture(); value['external']['source_admissions'][0]['index']=1; value['binding']=None
        with self.assertRaises(adapter.Rejected): invoke(value)
        value=fixture(); value['external']['config']['source_start_monotonic_ns']+=1
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test14_book_unavailable_and_weak_claim(self):
        value=fixture(); value['book']['samples'][-1]['numerical_pose_span']=None
        self.assertFalse(invoke(value)['c30_called'])
        value=fixture(); value['book']['state']='FAILED'; value['book']['failure_reason']='original_failure'
        self.assertFalse(invoke(value)['c30_called'])
        value=fixture(); value['binding']['native_interval_atomic']=True
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test15_caps_duplicates_and_deepcopy_core_globals(self):
        original=dict(adapter._C30._ORIGINAL.__globals__)
        value=fixture(); value['book']['samples']*=100
        with self.assertRaises(adapter.Rejected): invoke(value)
        with self.assertRaises(adapter.Rejected): adapter.project_json(b'{"x":1,"x":2}')
        value=fixture(); node=value['book']
        for _ in range(18): node['extra']={}; node=node['extra']
        with self.assertRaises(adapter.Rejected): invoke(value)
        self.assertEqual(original,adapter._C30._ORIGINAL.__globals__)

    def test16_high_original_qpc_no_rebase(self):
        value=fixture(); result=invoke(value)
        self.assertGreater(value['external']['now_qpc_ns'],2**53)
        projected=result['projection']; self.assertEqual(projected['now_qpc_ns'],value['external']['now_qpc_ns'])
        self.assertEqual(projected['root_receipt']['config']['source_start_monotonic_ns'],value['book']['source_origin_qpc_ns'])

    def test17_known_old_shape_is_unavailable_not_healthy(self):
        # New synthetic shape of the known stale/null-C3 facts; NOT actual A run.
        for tick in (0,470):
            value=fixture(); ext=value['external']; c=ext['candidate']; t=c['source_time']; ident=c['observation_identity']
            origin=t['source_start_monotonic_ns']; em=tick//50*50; now=origin+tick*1000000+473319100
            c['quality']=7|(0x700 if em<tick else 0); c['channel_counts'][3]=None
            t.update(adc_tick_ms=tick,em_tick_ms=em,admission_received_monotonic_ns=now-100,
                adc_source_age_ns=473319100,em_source_age_ns=now-(origin+em*1000000))
            ident.update(source_admission_index=tick//10,receiver_upper_qpc_ns=now,
                original_host_injection_qpc_ns=[now-90+i for i in range(4)])
            c['diagnostic_flags'].update(source_fresh_at_capture=False,all_channels_valid=False,
                injection_to_receiver_upper_ns=90,target100ms_met=True)
            value.update(book=None,book_current=None,binding=None)
            ext.update(now_qpc_ns=now,config=None,source_admissions=None,captures=None,current_pose=None,action_registry=None)
            result=invoke(value)
            self.assertFalse(result['c30_called']); self.assertEqual(result['status'],'STOP')
            self.assertIsNone(c['channel_counts'][3]); self.assertEqual(t['adc_source_age_ns'],473319100)

    def test18_complete_stale_preserves_frozen_c30_rejected(self):
        value=fixture(); ext=value['external']; c=ext['candidate']; ident=c['observation_identity']; t=c['source_time']
        step=100000000; t['admission_received_monotonic_ns']+=step
        t['adc_source_age_ns']+=step; t['em_source_age_ns']+=step
        ident['original_host_injection_qpc_ns']=[x+step for x in ident['original_host_injection_qpc_ns']]
        ident['receiver_upper_qpc_ns']+=step; c['diagnostic_flags']['source_fresh_at_capture']=False
        rec=ext['captures'][0]; raw=json.loads(rec['request_raw']); raw['original_host_qpc_ns']=ident['original_host_injection_qpc_ns']
        request_raw=encoded(raw)+b'\n'; ident['request_sha256']=hashlib.sha256(request_raw).hexdigest()
        capture=json.loads(rec['capture_raw']); capture['request_sha256']=ident['request_sha256']
        for i,lane in enumerate(capture['captures']):
            qpc=ident['original_host_injection_qpc_ns'][i]; lane['raw_words'][2]=qpc & 0xffffffff; lane['raw_words'][3]=qpc>>32
        capture_raw=encoded(capture)+b'\n'; ident['capture_sha256']=hashlib.sha256(capture_raw).hexdigest()
        rec.update(request_raw=request_raw.decode(),capture_raw=capture_raw.decode(),capture_sha256=ident['capture_sha256'],em_origin_capture_sha256=ident['capture_sha256'])
        ext['source_admissions'][-1]['received_qpc_ns']+=step
        ext['now_qpc_ns']+=step; ext['action_registry']['as_of_qpc_ns']+=step
        value['book']['fixed_root_interval']['through_qpc_ns']+=step
        cur=value['book_current']; cur['at_qpc_ns']+=step; cur['valid_span']['through_qpc_ns']+=step
        cur['pose_read']={k:v+step for k,v in cur['pose_read'].items()}
        for enabled in (True,False):
            value['enabled']=enabled
            with self.assertRaisesRegex(adapter.Rejected,'source admission original age'): invoke(value)

    def test19_new_byte_node_and_prefix_bounds(self):
        value=fixture()
        for i in range(6):
            value['book']['discarded_large_'+str(i)]=[{str(j):'x'*192 for j in range(32)} for _ in range(32)]
        with self.assertRaisesRegex(adapter.Rejected,'bytes budget'): invoke(value)
        value=fixture()
        for i in range(2): value['book']['discarded_nodes_'+str(i)]=[[[None]*32 for _ in range(32)] for _ in range(32)]
        with self.assertRaisesRegex(adapter.Rejected,'depth/node budget'): invoke(value)
        value=fixture(); value['external']['source_admissions']=[value['external']['source_admissions'][0]]*1002
        with self.assertRaisesRegex(adapter.Rejected,'array budget'): invoke(value)

    def test20_supplied_canonical_source_hash_mismatch(self):
        value=fixture(); value['binding']=None
        value['book']['samples'][-1]['canonical_source_hex']=encoded({'synthetic_private_marker':False,'original_tick':100}).hex()
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test21_supplied_raw_mismatch_with_missing_other_proof(self):
        for absent in ('config','request_raw','capture_raw'):
            with self.subTest(absent=absent):
                value=fixture(); ext=value['external']; rec=ext['captures'][0]
                if absent=='config': ext['config']=None
                else: rec[absent]=None
                supplied='capture_raw' if absent=='request_raw' else 'request_raw'
                raw=json.loads(rec[supplied])
                raw['context']['boot_id']='contradictory-existing-identity'
                rec[supplied]=(encoded(raw)+b'\n').decode()
                with self.assertRaises(adapter.Rejected): invoke(value)

    def test22_supplied_prefix_mismatch_with_missing_config(self):
        for field,bad in (('index',1),('new_em_sample',False)):
            with self.subTest(field=field):
                value=fixture(); value['external']['config']=None
                value['external']['source_admissions'][0][field]=bad
                with self.assertRaises(adapter.Rejected): invoke(value)

    def test23_supplied_candidate_admission_mismatch_without_receipt(self):
        value=fixture(); value['external']['captures']=None
        value['external']['candidate']['channel_counts'][0]+=1
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test24_v2_unicode_canonical_fresh_single_core(self):
        value=fixture(); sample=value['book']['samples'][-1]
        payload={'synthetic_private_marker':'数值Root','original_tick':100}
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')
        sample.update(payload=payload,canonical_source_hex=raw.hex(),source_sha256=hashlib.sha256(raw).hexdigest())
        rec=value['external']['captures'][0]
        rec['adc_book_source_sha256']=rec['em_book_source_sha256']=sample['source_sha256']
        original_globals=dict(adapter._C30._ORIGINAL.__globals__)
        result=invoke(value)
        self.assertTrue(result['core_ran']); self.assertNotIn('数值Root',json.dumps(result,ensure_ascii=False))
        self.assertEqual(original_globals,adapter._C30._ORIGINAL.__globals__)

    def test25_v2_hash_consistent_raw_lane_conflict(self):
        for kind in ('request_raw','capture_raw'):
            with self.subTest(kind=kind):
                value=fixture(); ext=value['external']; ext['config']=None
                rec=ext['captures'][0]; ident=ext['candidate']['observation_identity']
                if kind=='request_raw':
                    rec['capture_raw']=None; data=json.loads(rec[kind]); data['values'][0]+=1
                    raw=encoded(data)+b'\n'; ident['request_sha256']=hashlib.sha256(raw).hexdigest()
                else:
                    rec['request_raw']=None; data=json.loads(rec[kind]); data['captures'][0]['raw_words'][0]+=1
                    raw=encoded(data)+b'\n'; ident['capture_sha256']=hashlib.sha256(raw).hexdigest()
                    rec['capture_sha256']=rec['em_origin_capture_sha256']=ident['capture_sha256']
                rec[kind]=raw.decode()
                with self.assertRaisesRegex(adapter.Rejected,'lanes mismatch|words/candidate mismatch'): invoke(value)

    def test26_v2_partial_valid_raws_stay_unavailable(self):
        for missing in ('config','request_raw','capture_raw'):
            value=fixture()
            if missing=='config': value['external']['config']=None
            else: value['external']['captures'][0][missing]=None
            result=invoke(value)
            self.assertFalse(result['c30_called']); self.assertEqual(result['input_status'],'INPUT_UNAVAILABLE')

    def test27_v2_canonical_duplicate_and_private_payload_conflict(self):
        value=fixture(); sample=value['book']['samples'][-1]
        raw=b'{"x":1,"x":2}'; sample['canonical_source_hex']=raw.hex(); sample['source_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(adapter.Rejected,'duplicate JSON key'): invoke(value)
        value=fixture(); value['book']['samples'][-1]['payload']['original_tick']=99
        with self.assertRaisesRegex(adapter.Rejected,'payload/canonical mismatch'): invoke(value)

    def test28_v2_disabled_missing_receipt_cannot_hide_admission_conflict(self):
        value=fixture(); value['enabled']=False; value['external']['captures']=None
        value['external']['candidate']['source_time']['admission_received_monotonic_ns']+=1
        with self.assertRaisesRegex(adapter.Rejected,'admission/capture/candidate mismatch'): invoke(value)

    def test29_missing_config_counters_cannot_require_negative_baseline(self):
        value=fixture(); ext=value['external']; ext['config']=None
        rec=ext['captures'][0]; raw=json.loads(rec['capture_raw'])
        for lane in raw['captures']: lane['pipeline_counters'][0]=3
        raw['final_counters'][0]=3; data=encoded(raw)+b'\n'; digest=hashlib.sha256(data).hexdigest()
        rec['capture_raw']=data.decode(); rec['capture_sha256']=rec['em_origin_capture_sha256']=digest
        ext['candidate']['observation_identity']['capture_sha256']=digest
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test30_missing_config_cross_capture_counter_progression(self):
        value=held_fixture(); ext=value['external']; ext['config']=None
        rec=ext['captures'][-1]; raw=json.loads(rec['capture_raw'])
        for lane in raw['captures']: lane['pipeline_counters'][0]+=1
        raw['final_counters'][0]+=1; data=encoded(raw)+b'\n'; digest=hashlib.sha256(data).hexdigest()
        rec['capture_raw']=data.decode(); rec['capture_sha256']=digest
        ext['candidate']['observation_identity']['capture_sha256']=digest
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test31_new_positive_retained_request_gap_without_config(self):
        value=held_fixture(); ext=value['external']; ext['config']=None
        rec=ext['captures'][-1]; ident=ext['candidate']['observation_identity']
        request=json.loads(rec['request_raw']); request['request_seq']=3
        raw=encoded(request)+b'\n'; ident['request_seq']=3; ident['trigger_id']+=1
        ident['request_sha256']=hashlib.sha256(raw).hexdigest(); rec['request_raw']=raw.decode()
        capture=json.loads(rec['capture_raw']); capture.update(request_seq=3,trigger_id=ident['trigger_id'],request_sha256=ident['request_sha256'])
        for i,lane in enumerate(capture['captures']):
            lane['raw_words'][4:6]=[8,11]; lane['raw_words'][7]=ident['trigger_id']
            lane['pipeline_counters']=[12,3,9+i]
        capture['final_counters']=[12,3,12]; raw=encoded(capture)+b'\n'
        ident['capture_sha256']=hashlib.sha256(raw).hexdigest(); rec['capture_raw']=raw.decode(); rec['capture_sha256']=ident['capture_sha256']
        result=invoke(value)
        self.assertFalse(result['c30_called']); self.assertEqual(result['input_status'],'INPUT_UNAVAILABLE')

    def test32_new_positive_nonzero_actual_counter_baseline_core(self):
        value=fixture(); ext=value['external']; ext['config']['baseline_counters']=[2,3,5]
        rec=ext['captures'][0]; capture=json.loads(rec['capture_raw'])
        for i,lane in enumerate(capture['captures']): lane['pipeline_counters']=[6,4,6+i]
        capture['final_counters']=[6,4,9]; raw=encoded(capture)+b'\n'; digest=hashlib.sha256(raw).hexdigest()
        rec['capture_raw']=raw.decode(); rec['capture_sha256']=rec['em_origin_capture_sha256']=digest
        ext['candidate']['observation_identity']['capture_sha256']=digest
        result=invoke(value); self.assertTrue(result['core_ran'])
        self.assertEqual(result['projection']['root_receipt']['config']['baseline_counters'],[2,3,5])

    def test33_private_payload_types_must_match_canonical_bytes(self):
        value=fixture(); value['binding']=None
        value['book']['samples'][-1]['payload']['synthetic_private_marker']=1
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test34_only_candidate_missing_retained_receipt_is_unavailable(self):
        value=fixture(); value['external']['candidate']=None
        result=invoke(value)
        self.assertFalse(result['c30_called']); self.assertEqual(result['input_status'],'INPUT_UNAVAILABLE')

    def test35_missing_current_receipt_and_binding_do_not_hide_namespace(self):
        value=fixture(); value['binding']=None
        value['external']['current_pose']['receipt_id']=None
        value['external']['current_pose']['context']['boot_id']='contradictory-supplied-current'
        with self.assertRaises(adapter.Rejected): invoke(value)

    def test36_candidate_missing_raw_pair_contradiction_still_rejected(self):
        value=fixture(); ext=value['external']; ext['candidate']=None; ext['config']=None
        rec=ext['captures'][0]; capture=json.loads(rec['capture_raw']); capture['captures'][0]['raw_words'][0]+=1
        raw=encoded(capture)+b'\n'; rec['capture_raw']=raw.decode()
        rec['capture_sha256']=rec['em_origin_capture_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(adapter.Rejected,'raw pair words mismatch'): invoke(value)

    def test37_positive_missing_current_receipt_known_namespace(self):
        value=fixture(); value['binding']=None
        value['external']['current_pose']['valid_span_receipt_id']=None
        result=invoke(value)
        self.assertFalse(result['c30_called']); self.assertIsNone(result['projection'])

    def test38_new_positive_goal_after_intrinsic_validation(self):
        value=fixture(); value['external']['config']['goal_m']=[0.2,0.1,2.0]
        result=invoke(value)
        self.assertTrue(result['core_ran'])
        self.assertEqual(result['projection']['root_receipt']['config']['goal_m'],[0.2,0.1,2.0])


if __name__ == '__main__':
    unittest.main(verbosity=2)

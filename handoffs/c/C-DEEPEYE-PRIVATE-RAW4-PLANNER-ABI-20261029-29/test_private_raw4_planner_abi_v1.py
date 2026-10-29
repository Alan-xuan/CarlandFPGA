"""NEW local synthetic diagnostic controls only. Never board/model/old suites."""
import concurrent.futures
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest
from unittest import mock

PATH = Path(__file__).with_name('private_raw4_planner_abi_v1.py')
SPEC = importlib.util.spec_from_file_location('c29_local_controls', PATH)
abi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(abi)
ORIGIN = (1 << 55) + 123
POSE = {'position_m': [0., 0., 0.], 'orientation_xyzw': [0., 0., 0., 1.]}


def digest(value):
    return hashlib.sha256(abi._json_bytes(value)).hexdigest()


def fixture(tick=100, held=False, counts=None, session='s'*192):
    """Fabricated local evidence, deliberately labelled; grants no authority."""
    counts = [1740, 2048, 2048, 0] if counts is None else list(counts)
    ctx = dict(operation_id='fixture-operation/'+'o'*174, request_hash='1'*64,
               tested_commit='2'*40, build_manifest_sha256='3'*64,
               boot_id='synthetic Linux kernel instance', session_id=session,
               tag=(1 << 32)-1, clock_domain_id='4'*32)
    config = dict(receipt_id='synthetic-config-receipt', context=ctx,
        generation=(1 << 31)+19, profile_id=abi.PROFILE, producer_sha256=abi.PRODUCER_SHA256,
        source_policy='candidate_causal_source_v1', quality_encoding=abi.ENCODING,
        source_mode='twin_fixture', transport_source='software_fixture',
        source_start_tick_ms=0, source_start_monotonic_ns=ORIGIN,
        goal_m=[0., 0., 2.], baseline_counters=[7, 8, 9], initial_trigger_id=4000)
    admissions = []
    for index, adc in enumerate(range(0, tick+1, 10)):
        em = adc//50*50
        cc = list(counts); cc[3] = counts[3] if adc >= 90 else None
        q = 7 | (8 if adc >= 90 else 0) | (0x700 if adc > em else 0)
        admissions.append(dict(index=index, adc_tick_ms=adc, em_tick_ms=em,
            channel_counts=cc, quality=q, source_record_sha256=digest(['synthetic-source', adc, cc, q]),
            received_qpc_ns=ORIGIN+adc*1000000+1000000, new_em_sample=(adc == em)))
    selected = [tick//50*50, tick] if held else [tick]
    candidates, records = [], []
    for seq, adc in enumerate(selected, 1):
        adm = admissions[adc//10]; em = adm['em_tick_ms']; q = adm['quality']
        samples = [ORIGIN+adc*1000000+1500000+i for i in range(4)]
        request = dict(schema=1, kind='diagnostic_scan', context=ctx, request_seq=seq,
            source_id=4, source='software_fixture', values=[0 if x is None else x for x in adm['channel_counts']],
            qualities=[((q >> ch) & 1) | (((q >> (4+ch)) & 1) << 1) |
                       (((q >> (8+ch)) & 1) << 2) | (((q >> 12) & 1) << 3) for ch in range(4)],
            original_host_qpc_ns=samples)
        request_raw = abi._json_bytes(request, True)
        trigger = config['initial_trigger_id']+seq; generation = config['generation']
        capture = dict(schema=1, kind='diagnostic_capture', context=ctx, request_seq=seq,
            request_sha256=hashlib.sha256(request_raw).hexdigest(), generation=generation,
            trigger_id=trigger, captures=[], final_counters=[7+4*seq, 8+seq, 9+4*seq])
        for ch in range(4):
            capture['captures'].append(dict(channel=ch, ack_returned=True,
                raw_words=[request['values'][ch], ch | request['qualities'][ch] << 8,
                    samples[ch] & 0xffffffff, samples[ch] >> 32, 4*(seq-1), 4*seq-1,
                    ctx['tag'], trigger, generation, 123],
                pipeline_counters=[7+4*seq, 8+seq, 9+4*(seq-1)+ch+1]))
        capture_raw = abi._json_bytes(capture, True); frame_hash = hashlib.sha256(capture_raw).hexdigest()
        receiver = ORIGIN+adc*1000000+2000000
        c = dict(schema=1, kind='candidate_four_channel_input', profile_id=abi.PROFILE,
            profile_status='candidate_only', profile_note=abi.NOTE, source_mode='twin_fixture',
            quality_encoding=abi.ENCODING, source_id=4, transport_source='software_fixture',
            channel_names=list(abi.CHANNELS), channel_counts=list(adm['channel_counts']), quality=q,
            source_time=dict(adc_tick_ms=adc, em_tick_ms=em, source_start_tick_ms=0,
                source_start_monotonic_ns=ORIGIN, admission_received_monotonic_ns=adm['received_qpc_ns'],
                adc_source_age_ns=receiver-(ORIGIN+adc*1000000),
                em_source_age_ns=receiver-(ORIGIN+em*1000000), time_basis=abi.TIME_BASIS),
            observation_identity=dict(context=copy.deepcopy(ctx), request_seq=seq,
                request_sha256=capture['request_sha256'], capture_sha256=frame_hash,
                generation=generation, trigger_id=trigger, source_admission_index=adc//10,
                original_host_injection_qpc_ns=samples, receiver_upper_qpc_ns=receiver),
            diagnostic_flags=dict(source_fresh_at_capture=True, all_channels_valid=(q & 15 == 15),
                injection_to_receiver_upper_ns=receiver-samples[0], target100ms_met=True,
                target100ms_scope='conservative_receiver_upper_bound', formal_100ms_acceptance='not_run',
                formal_H12='not_run', transport_authenticated=False, BOOT_authenticated=False,
                physical_sample_authenticated=False, compression_verified=False,
                CPU_completion_created=False, movement_authorized=False))
        candidates.append(c)
        records.append(dict(capture_sha256=frame_hash, source_record_sha256=adm['source_record_sha256'],
            request_raw=request_raw.decode(), capture_raw=capture_raw.decode(),
            adc_pose=dict(receipt_id='synthetic-adc-pose-'+str(adc), source_admission_index=adc//10,
                          acquisition_qpc_ns=ORIGIN+adc*1000000, pose=copy.deepcopy(POSE)),
            em_pose=dict(receipt_id='synthetic-em-pose-'+str(em), source_admission_index=em//10,
                         acquisition_qpc_ns=ORIGIN+em*1000000, pose=copy.deepcopy(POSE)),
            em_origin_capture_sha256=(frame_hash if adc == em else records[0]['capture_sha256']),
            cause_action_id=None))
    now = ORIGIN+tick*1000000+3000000
    root = dict(kind='c29_root_association_v1', evidence_scope='synthetic_diagnostic_fixture',
        config=config, source_admissions=admissions, captures=records,
        current_pose=dict(receipt_id='synthetic-current-pose', context=copy.deepcopy(ctx),
                          generation=config['generation'], at_qpc_ns=now, pose=copy.deepcopy(POSE)),
        action_registry=dict(receipt_id='synthetic-empty-occurred-action-registry', context=copy.deepcopy(ctx),
                             generation=config['generation'], as_of_qpc_ns=now, actions=[]))
    return dict(schema_version=1, abi_id=abi.ABI, diagnostic_only=True,
                evidence_scope='synthetic_diagnostic_fixture', enabled=True, now_qpc_ns=now,
                candidate=candidates[-1], history=candidates[:-1], root_receipt=root)


def now_at(req, now):
    req['now_qpc_ns'] = now
    req['root_receipt']['current_pose']['at_qpc_ns'] = now
    req['root_receipt']['action_registry']['as_of_qpc_ns'] = now


def actual_shape_unassociated():
    """Shape example only, no copied A run or claim of actual bytes."""
    req = fixture(50)
    req['evidence_scope'] = 'unassociated_diagnostic'; req['root_receipt'] = None
    c = req['candidate']; receiver = ORIGIN+50000000+222552400
    req['now_qpc_ns'] = receiver
    c['observation_identity']['receiver_upper_qpc_ns'] = receiver
    c['source_time']['adc_source_age_ns'] = c['source_time']['em_source_age_ns'] = 222552400
    flags = c['diagnostic_flags']; flags['source_fresh_at_capture'] = flags['target100ms_met'] = False
    flags['injection_to_receiver_upper_ns'] = receiver-c['observation_identity']['original_host_injection_qpc_ns'][0]
    return req


def replace_native_quality(req, q, counts, em):
    """Rebuild every correlated synthetic byte; never a production repair."""
    c = req['candidate']; rec = req['root_receipt']['captures'][-1]
    adm = req['root_receipt']['source_admissions'][-1]
    adm.update(quality=q, channel_counts=counts, em_tick_ms=em, new_em_sample=(em is not None))
    adm['source_record_sha256'] = digest(['synthetic-rebuilt-source', adm['index'], q, counts, em])
    rec['source_record_sha256'] = adm['source_record_sha256']
    c.update(quality=q, channel_counts=counts); c['source_time']['em_tick_ms'] = em
    if em is None:
        c['source_time']['em_source_age_ns'] = None
        rec['em_pose'] = None; rec['em_origin_capture_sha256'] = None
    raw_request = json.loads(rec['request_raw'])
    raw_request['values'] = [0 if v is None else v for v in counts]
    raw_request['qualities'] = [((q >> ch) & 1) | (((q >> (4+ch)) & 1) << 1) |
                               (((q >> (8+ch)) & 1) << 2) | (((q >> 12) & 1) << 3) for ch in range(4)]
    rec['request_raw'] = abi._json_bytes(raw_request, True).decode()
    rh = hashlib.sha256(rec['request_raw'].encode()).hexdigest()
    c['observation_identity']['request_sha256'] = rh
    raw_capture = json.loads(rec['capture_raw']); raw_capture['request_sha256'] = rh
    for ch, lane in enumerate(raw_capture['captures']):
        lane['raw_words'][:2] = [raw_request['values'][ch], ch | raw_request['qualities'][ch] << 8]
    rec['capture_raw'] = abi._json_bytes(raw_capture, True).decode()
    chash = hashlib.sha256(rec['capture_raw'].encode()).hexdigest()
    c['observation_identity']['capture_sha256'] = rec['capture_sha256'] = chash
    if em is not None:
        rec['em_origin_capture_sha256'] = chash
    c['diagnostic_flags']['all_channels_valid'] = q & 15 == 15
    c['diagnostic_flags']['source_fresh_at_capture'] = em is not None and not q & 0x1000


class NewC29Controls(unittest.TestCase):
    def unavailable(self, req, reason=None):
        result = abi.recommend(req)
        self.assertFalse(result['core_ran']); self.assertEqual(result['status'], 'STOP')
        self.assertEqual(result['input_status'], 'INPUT_UNAVAILABLE')
        if reason:
            self.assertEqual(result['reason'], reason)
        return result

    def test01_default_disabled_actual_context(self):
        req = actual_shape_unassociated(); del req['enabled']
        out = abi.recommend(req)
        self.assertFalse(out['core_ran']); self.assertEqual(out['reason'], 'disabled')
        self.assertEqual(out['candidate'], req['candidate'])
        self.assertEqual(out['kernel_boot_id'], req['candidate']['observation_identity']['context']['boot_id'])

    def test02_complete_reuses_code(self):
        req = fixture(); expected = abi._association(req, [req['candidate']])
        before = dict(abi._ORIGINAL.__globals__)
        bound = abi._bind_core(expected)
        self.assertIs(bound.__code__, abi._ORIGINAL.__code__)
        self.assertIsNot(bound.__globals__, abi._ORIGINAL.__globals__)
        self.assertEqual(abi._ORIGINAL.__globals__, before)
        self.assertIs(bound.__globals__['_poses_applicable'], abi._ORIGINAL.__globals__['_poses_applicable'])
        out = abi.recommend(req)
        self.assertTrue(out['core_ran']); self.assertEqual(out['status'], 'ADVISE')
        self.assertEqual(out['independent_em_count'], 1)
        self.assertEqual(out['map_cells'][0]['original_em_qpc_ns'], ORIGIN+100000000)
        self.assertEqual(hashlib.sha256(abi._CORE_PATH.read_bytes()).hexdigest(), abi.CORE_SHA256)

    def test03_missing_each_association(self):
        for field in ('config', 'source_admissions', 'captures', 'current_pose', 'action_registry'):
            with self.subTest(field=field):
                req = fixture(); req['root_receipt'][field] = None
                self.unavailable(req)
        for field in ('request_raw', 'capture_raw', 'adc_pose', 'em_pose', 'em_origin_capture_sha256'):
            with self.subTest(field=field):
                req = fixture(); req['root_receipt']['captures'][0][field] = None
                self.unavailable(req)
        self.unavailable(actual_shape_unassociated(), 'missing_root_receipt')

    def test04_exact_large_qpc_age(self):
        for age in (99999999, 100000000, 100000001, 222552400, 224765500):
            req = fixture(); now_at(req, ORIGIN+100000000+age)
            out = abi.recommend(req)
            self.assertEqual(out['now_qpc_ns'], ORIGIN+100000000+age)
            self.assertEqual(out['core_ran'], age <= 100000000)
            if age > 100000000:
                self.assertEqual(out['reason'], 'original_source_expired_now')

    def test05_native_and_held(self):
        req = fixture(110, held=True)
        req['root_receipt']['captures'][-1]['adc_pose']['pose']['position_m'][0] = .1
        req['root_receipt']['current_pose']['pose']['position_m'][0] = .2
        out = abi.recommend(req)
        self.assertTrue(out['core_ran']); self.assertEqual(out['independent_em_count'], 1)
        self.assertEqual(out['map_cells'][0]['pose'], POSE)
        self.assertEqual(out['candidate'], req['candidate'])
        req['history'] = []; req['root_receipt']['captures'] = req['root_receipt']['captures'][-1:]
        self.unavailable(req, 'missing_retained_native_board_origin')

    def test06_held_tampering_and_fault_revival(self):
        req = fixture(110, held=True)
        req['root_receipt']['captures'][-1]['em_pose']['pose']['position_m'][0] = .1
        with self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(110, held=True)
        req['root_receipt']['source_admissions'][-1]['new_em_sample'] = True
        with self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(120, held=True)
        adm = req['root_receipt']['source_admissions'][11]
        adm.update(em_tick_ms=None, quality=0x1008, channel_counts=[None, None, None, 0], new_em_sample=False)
        with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test07_raw_context_count_quality_identity(self):
        paths = [('channel_counts', 0), ('quality', None), ('observation_identity', 'trigger_id'),
                 ('observation_identity', 'source_admission_index'), ('observation_identity', 'request_seq')]
        for key, sub in paths:
            req = fixture()
            if sub is None: req['candidate'][key] ^= 0x10
            else: req['candidate'][key][sub] += 1
            with self.subTest(key=key, sub=sub), self.assertRaises(abi.Rejected): abi.recommend(req)
        for field in ('session_id', 'boot_id', 'clock_domain_id'):
            req = fixture(); req['candidate']['observation_identity']['context'][field] = 'a'*32
            with self.subTest(field=field), self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(); rec = req['root_receipt']['captures'][0]
        raw = json.loads(rec['capture_raw']); raw['captures'][0]['raw_words'][0] += 1
        rec['capture_raw'] = abi._json_bytes(raw, True).decode()
        with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test08_timestamp_namespace(self):
        req = fixture(0); out = abi.recommend(req)
        self.assertTrue(out['core_ran']); self.assertEqual(out['reason'], 'invalid_faulted_or_saturated')
        self.assertIsNone(out['candidate']['channel_counts'][3])
        for field in ('adc_source_age_ns', 'source_start_monotonic_ns'):
            req = fixture(); req['candidate']['source_time'][field] += 1
            with self.subTest(field=field), self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(); req['root_receipt']['captures'][0]['em_pose']['acquisition_qpc_ns'] += 1
        with self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(); req['now_qpc_ns'] -= 2000000
        with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test09_original_pose_envelope_and_roll(self):
        for angle in (90, 180):
            req = fixture(); rad = math.radians(angle)/2
            req['root_receipt']['current_pose']['pose']['orientation_xyzw'] = [0., math.sin(rad), 0., math.cos(rad)]
            out = abi.recommend(req)
            self.assertTrue(out['core_ran']); self.assertEqual(out['reason'], 'original_observation_pose_inapplicable')
        req = fixture(); req['root_receipt']['current_pose']['pose']['position_m'][0] = 10.
        self.assertEqual(abi.recommend(req)['reason'], 'original_observation_pose_inapplicable')
        req = fixture(); req['root_receipt']['current_pose']['pose']['orientation_xyzw'] = [0., 0., 1., 0.]
        self.assertEqual(abi.recommend(req)['status'], 'ADVISE')
        for x, expected in ((.25, 'ADVISE'), (.25000001, 'STOP')):
            req = fixture(); req['root_receipt']['current_pose']['pose']['position_m'][0] = x
            self.assertEqual(abi.recommend(req)['status'], expected)

    def test10_real_decision_contrast_and_direction(self):
        left = abi.recommend(fixture(counts=[2500, 700, 2048, 0]))
        right = abi.recommend(fixture(counts=[2500, 3400, 2048, 0]))
        self.assertNotEqual(left['direction_world'], right['direction_world'])
        risk = abi.recommend(fixture(counts=[4095, 2048, 2048, 4095]))
        self.assertEqual(risk['status'], 'STOP')
        for result in (left, right):
            self.assertGreaterEqual(result['direction_world'][2], math.cos(math.radians(30)))
            self.assertGreater(result['speed_limit_m_s'], 0)

    def test11_actions_require_occurred_evidence(self):
        req = fixture(110, held=True); first = req['history'][0]['observation_identity']
        action = dict(receipt_id='synthetic-execution-receipt', action_id='act', state='executed',
            observation_capture_sha256=first['capture_sha256'], at_qpc_ns=ORIGIN+105000000,
            from_pose=copy.deepcopy(POSE), to_pose=copy.deepcopy(POSE))
        req['root_receipt']['action_registry']['actions'] = [action]
        req['root_receipt']['captures'][-1]['cause_action_id'] = 'act'
        self.assertTrue(abi.recommend(req)['core_ran'])
        for value in ('proposed', 'unknown', 'failed'):
            bad = copy.deepcopy(req); bad['root_receipt']['action_registry']['actions'][0]['state'] = value
            with self.assertRaises(abi.Rejected): abi.recommend(bad)
        bad = copy.deepcopy(req); bad['root_receipt']['action_registry']['actions'][0]['receipt_id'] = None
        self.unavailable(bad, 'missing_action_execution_receipt')
        bad = copy.deepcopy(req); bad['root_receipt']['action_registry']['actions'][0]['at_qpc_ns'] = ORIGIN+111000000
        with self.assertRaises(abi.Rejected): abi.recommend(bad)
        bad = copy.deepcopy(req); bad['root_receipt']['action_registry']['actions'][0]['observation_capture_sha256'] = 'f'*64
        self.unavailable(bad, 'missing_action_observation')

    def test12_strict_json_and_detachment(self):
        req = fixture(); before = copy.deepcopy(req)
        encoded = abi.recommend_json(abi._json_bytes(req)); out = json.loads(encoded)
        self.assertEqual(req, before); self.assertEqual(out['candidate'], req['candidate'])
        out['candidate']['channel_counts'][0] = 0
        self.assertEqual(req, before)
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'['*100+b']'*100):
            with self.assertRaises(abi.Rejected): abi.recommend_json(raw)
        for mutate in (lambda r: r.update(enabled=1), lambda r: r.update(hidden_world={}),
                       lambda r: r.update(now_qpc_ns=float(r['now_qpc_ns'])),
                       lambda r: r['candidate']['channel_counts'].__setitem__(0, True)):
            bad = fixture(); mutate(bad)
            with self.assertRaises(abi.Rejected): abi.recommend(bad)

    def test13_concurrent_full_identity_no_crossover(self):
        inputs = [fixture(session=('A' if i % 2 else 'B')*192) for i in range(8)]
        before = dict(abi._ORIGINAL.__globals__)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            outputs = list(pool.map(abi.recommend, inputs))
        for req, result in zip(inputs, outputs):
            self.assertEqual(result['candidate']['observation_identity'], req['candidate']['observation_identity'])
        self.assertEqual(abi._ORIGINAL.__globals__, before)

    def test14_disabled_never_enters_core(self):
        req = fixture(); req['enabled'] = False
        original = abi._bind_core
        try:
            def forbidden(_): raise AssertionError('unexpected core entry')
            abi._bind_core = forbidden
            self.assertFalse(abi.recommend(req)['core_ran'])
            self.unavailable(actual_shape_unassociated())
        finally:
            abi._bind_core = original

    def test15_disabled_and_missing_strict_shapes(self):
        for enabled in (False, True):
            for where in ('root', 'config', 'pose', 'raw'):
                req = fixture(); req['enabled'] = enabled
                if where == 'root': req['root_receipt']['world_truth'] = 1
                elif where == 'config': req['root_receipt']['config']['receipt_id'] = {'hidden': 1}
                elif where == 'pose': req['root_receipt']['captures'][0]['em_pose']['pose']['truth'] = 1
                else:
                    rec = req['root_receipt']['captures'][0]
                    raw = json.loads(rec['capture_raw']); raw['truth'] = 1
                    rec['capture_raw'] = abi._json_bytes(raw, True).decode()
                    req['root_receipt']['config'] = None
                with self.subTest(enabled=enabled, where=where), self.assertRaises(abi.Rejected):
                    abi.recommend(req)
        for req in (actual_shape_unassociated(), fixture()):
            req['enabled'] = False
            result = abi.recommend(req)
            self.assertLessEqual(len(abi._json_bytes(result)), abi.MAX_BYTES)
            abi._tree(result)

    def test16_pose_thresholds_and_full_3d(self):
        for angle, status in ((15., 'ADVISE'), (15.00001, 'STOP')):
            req = fixture(); rad = math.radians(angle)/2
            req['root_receipt']['current_pose']['pose']['orientation_xyzw'] = [0., math.sin(rad), 0., math.cos(rad)]
            self.assertEqual(abi.recommend(req)['status'], status)
        up = abi.recommend(fixture(counts=[2500, 2048, 700, 0]))
        down = abi.recommend(fixture(counts=[2500, 2048, 3400, 0]))
        self.assertNotEqual(up['direction_world'][1], down['direction_world'][1])

    def test17_history_and_fabricated_legacy_fields(self):
        req = fixture(); req['history'] = [copy.deepcopy(req['candidate'])]*32
        with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test18_legal_quality_semantics(self):
        req = fixture(); replace_native_quality(req, 0x1008, [None, None, None, 0], None)
        out = abi.recommend(req)
        self.assertTrue(out['core_ran']); self.assertEqual(out['reason'], 'invalid_faulted_or_saturated')
        self.assertEqual(out['candidate']['channel_counts'], [None, None, None, 0])
        req = fixture(); replace_native_quality(req, 0x8f, [1740, 2048, 2048, 1500], 100)
        out = abi.recommend(req)
        self.assertTrue(out['core_ran']); self.assertEqual(out['status'], 'STOP')
        self.assertEqual(out['candidate']['channel_counts'][3], 1500)
        req = fixture(); replace_native_quality(req, 0x8f, [1740, 2048, 2048, 100], 100)
        with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test19_dependency_hash_fails_closed(self):
        spec = importlib.util.spec_from_file_location('c29_bad_dependency_control', PATH)
        candidate = importlib.util.module_from_spec(spec)
        with mock.patch.object(Path, 'read_bytes', return_value=b'wrong frozen bytes'):
            with self.assertRaises(ImportError): spec.loader.exec_module(candidate)

    def test20_goal_and_unequal_native_time(self):
        forward = abi.recommend(fixture())
        req = fixture(); req['root_receipt']['config']['goal_m'] = [1., 0., 2.]
        self.assertNotEqual(abi.recommend(req)['direction_world'], forward['direction_world'])
        req = fixture(); req['root_receipt']['config']['goal_m'] = [0., 0., -2.]
        self.assertEqual(abi.recommend(req)['reason'], 'no_forward_goal_progress')
        req = fixture(110, held=True)
        req['root_receipt']['source_admissions'][-1]['new_em_sample'] = True
        with self.assertRaises(abi.Rejected): abi.recommend(req)
        for field in ('config_epoch', 'topology_id', 'protocol_BOOT', 'board_verified'):
            req = fixture(); req['candidate']['observation_identity']['context'][field] = 1
            with self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(); req['root_receipt']['source_admissions'][0]['index'] = 32
        with self.assertRaises(abi.Rejected): abi.recommend(req)


    def test21_missing_admission_prefix_outcome(self):
        # C29-R1: missing tail is unavailable, never a fabricated admission.
        for enabled in (False, True):
            for retained in (None, 0, 1, 10):
                with self.subTest(enabled=enabled, retained=retained):
                    req = fixture(); req['enabled'] = enabled
                    req['root_receipt']['source_admissions'] = (None if retained is None else
                        req['root_receipt']['source_admissions'][:retained])
                    before = copy.deepcopy(req)
                    out = abi.recommend(req)
                    self.assertEqual(req, before)
                    self.assertEqual(out['status'], 'STOP'); self.assertFalse(out['core_ran'])
                    self.assertEqual(out['input_status'], 'INPUT_UNAVAILABLE' if enabled else 'DISABLED')
                    expected = ('missing_source_admissions' if retained in (None, 0) else
                                'missing_source_admission_index') if enabled else 'disabled'
                    self.assertEqual(out['reason'], expected)
                    self.assertEqual(json.loads(abi.recommend_json(abi._json_bytes(req))), out)
        complete = abi.recommend(fixture())
        self.assertTrue(complete['core_ran']); self.assertEqual(complete['status'], 'ADVISE')
        for enabled in (False, True):
            for contradiction in ('nonzero_start', 'interior_gap', 'held_value', 'candidate_value'):
                with self.subTest(enabled=enabled, contradiction=contradiction):
                    req = fixture(); req['enabled'] = enabled
                    admissions = req['root_receipt']['source_admissions']
                    if contradiction == 'nonzero_start':
                        del admissions[0]
                    elif contradiction == 'interior_gap':
                        del admissions[5]
                    elif contradiction == 'held_value':
                        del admissions[10:]
                        admissions[-1]['channel_counts'][0] += 1
                    else:
                        req['candidate']['channel_counts'][0] += 1
                    with self.assertRaises(abi.Rejected):
                        abi.recommend(req)


if __name__ == '__main__':
    unittest.main(verbosity=2)

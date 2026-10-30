"""NEW C30 focused synthetic controls. No old suite/A/Root/engine execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).with_name('private_raw4_time_association_v1.py')
SPEC = importlib.util.spec_from_file_location('c30_focused_local', PATH)
abi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(abi)
ORIGIN = (1 << 55) + 123
POSE = {'position_m': [0., 0., 0.], 'orientation_xyzw': [0., 0., 0., 1.]}


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


def moved_held():
    req = fixture(110, True); root = req['root_receipt']
    for record in (root['captures'][-1]['adc_pose'], root['current_pose']):
        record['pose_revision'] = 1; record['pose']['position_m'][0] = .1
        record['valid_span']['from_qpc_ns'] = ORIGIN+110000000
    return req


def action_fixture():
    req = moved_held(); root = req['root_receipt']; current = root['current_pose']
    root['action_registry']['actions'] = [dict(receipt_id='synthetic-execution', action_id='action-one',
        state='executed', observation_capture_sha256=req['history'][0]['observation_identity']['capture_sha256'],
        at_qpc_ns=ORIGIN+105000000, from_pose=copy.deepcopy(POSE), to_pose=copy.deepcopy(current['pose']),
        from_pose_revision=0, to_pose_revision=1)]
    root['captures'][-1]['cause_action_id'] = 'action-one'
    return req


def actual_shape_missing_book():
    """Synthetic illustration of A fields; never presented as actual A bytes."""
    req = fixture(50); req['root_receipt'] = None; req['evidence_scope'] = 'unassociated_diagnostic'
    candidate = req['candidate']; age = 317000000
    now = ORIGIN+50000000+age; req['now_qpc_ns'] = now
    candidate['observation_identity']['receiver_upper_qpc_ns'] = now
    candidate['source_time']['adc_source_age_ns'] = candidate['source_time']['em_source_age_ns'] = age
    flags = candidate['diagnostic_flags']; flags['source_fresh_at_capture'] = flags['target100ms_met'] = False
    flags['injection_to_receiver_upper_ns'] = now-candidate['observation_identity']['original_host_injection_qpc_ns'][0]
    return req


class NewC30FocusedControls(unittest.TestCase):
    def unavailable(self, req):
        result = abi.recommend(req)
        self.assertEqual(result['input_status'], 'INPUT_UNAVAILABLE')
        self.assertEqual(result['status'], 'STOP'); self.assertFalse(result['core_ran'])
        return result

    def test01_separate_actual_brackets_and_nominal(self):
        req = fixture(); original = copy.deepcopy(req); out = abi.recommend(req)
        self.assertTrue(out['core_ran']); self.assertEqual(out['status'], 'ADVISE')
        self.assertEqual(req, original); self.assertEqual(out['root_receipt'], req['root_receipt'])
        native = out['map_cells'][0]
        self.assertEqual(native['original_em_qpc_ns'], ORIGIN+100000000)
        self.assertGreater(native['em_pose_receipt']['pose_read']['begin_qpc_ns'], native['original_em_qpc_ns'])
        self.assertEqual(json.loads(abi.recommend_json(abi._json_bytes(req))), out)

    def test02_missing_coverage_and_brackets_never_fill(self):
        for field in ('pose_read', 'valid_span', 'pose_revision'):
            for kind in ('adc_pose', 'em_pose'):
                req = fixture(); req['root_receipt']['captures'][0][kind][field] = None
                self.unavailable(req)
        for field in ('pose_read', 'valid_span', 'pose_revision'):
            req = fixture(); req['root_receipt']['current_pose'][field] = None
            self.unavailable(req)
        req = fixture(); req['root_receipt']['captures'][0]['adc_call'] = None
        self.unavailable(req)
        for key in ('pose_book_id', 'owner_binding_id'):
            req = fixture(); req['root_receipt']['config'][key] = None; self.unavailable(req)
        for kind in ('adc_pose', 'em_pose'):
            req = fixture(); receipt = req['root_receipt']['captures'][0][kind]
            receipt['valid_span']['from_qpc_ns'] = receipt['nominal_source_qpc_ns']+1
            self.unavailable(req)  # later equal pose does not prove nominal validity
        req = fixture(); req['root_receipt']['current_pose']['valid_span']['through_qpc_ns'] -= 1
        self.unavailable(req)
        self.unavailable(actual_shape_missing_book())

    def test03_bracket_order_future_and_closed_endpoint(self):
        req = fixture(); self.assertTrue(abi.recommend(req)['core_ran'])
        for kind in ('adc_pose', 'em_pose'):
            req = fixture(); req['root_receipt']['captures'][0][kind]['valid_span']['through_qpc_ns'] -= 1
            self.unavailable(req)  # call end is no longer covered
        for role in ('adc', 'em', 'call', 'span', 'future', 'read_after_call', 'call_after_admission'):
            req = fixture(); record = req['root_receipt']['captures'][0]
            if role in ('adc', 'em'):
                b = record[role+'_pose']['pose_read']; b['begin_qpc_ns'] = b['end_qpc_ns']+1
            elif role == 'call': record['adc_call']['begin_qpc_ns'] = record['adc_call']['end_qpc_ns']+1
            elif role == 'span': record['adc_pose']['valid_span']['from_qpc_ns'] = record['adc_pose']['valid_span']['through_qpc_ns']+1
            elif role == 'future': req['root_receipt']['current_pose']['valid_span']['through_qpc_ns'] += 1
            elif role == 'read_after_call': record['adc_pose']['pose_read']['end_qpc_ns'] = record['adc_call']['begin_qpc_ns']+1
            else: record['adc_call']['end_qpc_ns'] = req['candidate']['source_time']['admission_received_monotonic_ns']+1
            with self.subTest(role=role), self.assertRaises(abi.Rejected): abi.recommend(req)

    def test04_revision_pose_overlap_and_chronology(self):
        req = fixture(); req['root_receipt']['current_pose']['pose']['position_m'][0] = .1
        with self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(); req['root_receipt']['current_pose']['pose_revision'] = 1
        with self.assertRaises(abi.Rejected): abi.recommend(req)  # even identical numeric pose overlaps
        req = fixture(); current = req['root_receipt']['current_pose']
        current['valid_span']['from_qpc_ns'] = ORIGIN+104000000
        for key in ('adc_pose', 'em_pose'):
            req['root_receipt']['captures'][0][key]['pose_revision'] = 2
        with self.assertRaises(abi.Rejected): abi.recommend(req)  # disjoint later revision0
        req = fixture(); req['root_receipt']['captures'][0]['em_pose']['pose_revision'] = 1
        with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test05_held_retains_original_call_and_revision(self):
        req = moved_held(); out = abi.recommend(req)
        self.assertTrue(out['core_ran']); self.assertEqual(out['independent_em_count'], 1)
        original = req['root_receipt']['captures'][0]
        self.assertLess(original['em_pose']['valid_span']['through_qpc_ns'], req['root_receipt']['captures'][1]['adc_call']['begin_qpc_ns'])
        self.assertEqual(out['map_cells'][0]['pose'], POSE)
        req['root_receipt']['captures'][1]['em_pose']['valid_span']['receipt_id'] += '-changed'
        with self.assertRaises(abi.Rejected): abi.recommend(req)
        req = moved_held(); req['history'] = []; req['root_receipt']['captures'] = req['root_receipt']['captures'][1:]
        self.unavailable(req)

    def test06_action_revisions_and_nominal_cause(self):
        req = action_fixture(); self.assertTrue(abi.recommend(req)['core_ran'])
        for change in ('missing_registry', 'missing_revision', 'latest_after_current', 'equal_different_pose', 'after_nominal', 'reverse'):
            req = action_fixture(); root = req['root_receipt']; action = root['action_registry']['actions'][0]
            if change == 'missing_registry': root['action_registry'] = None
            elif change == 'missing_revision': action['to_pose_revision'] = None
            elif change == 'latest_after_current': action['to_pose_revision'] = 2
            elif change == 'equal_different_pose': action['to_pose']['position_m'][0] = .2
            elif change == 'after_nominal': action['at_qpc_ns'] = ORIGIN+111000000
            else: action['from_pose_revision'] = 2
            if change in ('missing_registry', 'missing_revision'): self.unavailable(req)
            else:
                with self.subTest(change=change), self.assertRaises(abi.Rejected): abi.recommend(req)

    def test07_exact_high_qpc_age_and_read_not_refreshing(self):
        for age in (100000000, 100000001, 317000000):
            req = fixture(); set_now(req, ORIGIN+100000000+age)
            out = abi.recommend(req); self.assertEqual(out['core_ran'], age == 100000000)
            self.assertEqual(out['candidate'], req['candidate'])
        req = fixture(); req['root_receipt']['captures'][0]['adc_pose']['nominal_source_qpc_ns'] += 1
        with self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(); req['root_receipt']['captures'][0]['adc_call']['begin_qpc_ns'] = float(ORIGIN)
        with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test08_full_prefix1001_and_tail(self):
        req = fixture(10000); encoded = abi._json_bytes(req)
        self.assertLess(len(encoded), abi.MAX_BYTES)
        out = abi.recommend(req)
        self.assertTrue(out['core_ran']); self.assertEqual(len(out['root_receipt']['source_admissions']), 1001)
        self.assertLess(len(abi._json_bytes(out)), abi.MAX_BYTES)
        req['root_receipt']['source_admissions'].pop(); self.unavailable(req)
        for prefix in (None, []):
            req = fixture(); req['root_receipt']['source_admissions'] = prefix; self.unavailable(req)
        for mode in ('1002', 'nonzero', 'interior', 'quality'):
            req = fixture(10010, held=True) if mode == '1002' else fixture(100)
            admissions = req['root_receipt']['source_admissions']
            if mode == 'nonzero': del admissions[0]
            elif mode == 'interior': del admissions[5]
            elif mode == 'quality': admissions[9]['quality'] &= ~8; admissions[9]['channel_counts'][3] = None
            with self.subTest(mode=mode), self.assertRaises(abi.Rejected): abi.recommend(req)

    def test09_path_specific_limits_and_hidden_data(self):
        abi._tree({'root_receipt': {'source_admissions': [None]*1001}})
        bad = [
            {'source_admissions': [None]*33},
            {'outer': {'root_receipt': {'source_admissions': [None]*33}}},
            {'root_receipt': {'captures': [None]*33}},
            {'root_receipt': {'action_registry': {'actions': [None]*33}}},
            {'root_receipt': {'source_admissions': [{'source_admissions': [None]*33}]}},
        ]
        for value in bad:
            with self.assertRaises(abi.Rejected): abi._tree(value)
        with self.assertRaises(abi.Rejected):
            abi._raw(abi._json_bytes({'root_receipt': {'source_admissions': [None]*33}}, True).decode())
        for enabled in (False, True):
            req = fixture(); req['enabled'] = enabled; req['root_receipt']['captures'][0]['adc_pose']['hidden_layout'] = []
            with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test10_disabled_missing_still_checks_conflicts(self):
        req = actual_shape_missing_book(); del req['enabled']
        out = abi.recommend(req); self.assertFalse(out['core_ran']); self.assertEqual(out['reason'], 'disabled')
        req = fixture(); req['enabled'] = False; req['root_receipt']['captures'][0]['adc_pose']['pose_read'] = None
        self.assertFalse(abi.recommend(req)['core_ran'])
        req['root_receipt']['current_pose']['pose_read']['end_qpc_ns'] = req['now_qpc_ns']+1
        with self.assertRaises(abi.Rejected): abi.recommend(req)
        req = fixture(); req['root_receipt']['source_admissions'] = None
        req['root_receipt']['config']['generation'] += 1
        with self.assertRaises(abi.Rejected): abi.recommend(req)

    def test11_budget_and_single_core(self):
        req = fixture(); view = abi._association(req, [req['candidate']]); before = dict(abi._ORIGINAL.__globals__)
        bound = abi._bind_core(view)
        self.assertIs(bound.__code__, abi._ORIGINAL.__code__)
        self.assertEqual([k for k in bound.__globals__ if bound.__globals__[k] is not before[k]], ['_validate'])
        self.assertEqual(abi._ORIGINAL.__globals__, before)
        with self.assertRaises(abi.Rejected): abi.recommend_json(b' '* (abi.MAX_BYTES+1))
        with self.assertRaises(abi.Rejected): abi._tree(None, nodes=[65536])
        deep = None
        for _ in range(17): deep = {'x': deep}
        with self.assertRaises(abi.Rejected): abi._tree(deep)
        with self.assertRaises(abi.Rejected): abi._finish({'x': 'x'*193})

    def test12_executed_commit_point_vs_proven_spans(self):
        for mode in ('old_after_commit', 'to_before_commit'):
            req = action_fixture(); root = req['root_receipt']
            at = root['action_registry']['actions'][0]['at_qpc_ns']
            if mode == 'old_after_commit':
                for receipt in (root['captures'][0]['adc_pose'], root['captures'][0]['em_pose'], root['captures'][1]['em_pose']):
                    receipt['valid_span']['through_qpc_ns'] = at
            else:
                root['captures'][1]['adc_pose']['valid_span']['from_qpc_ns'] = at-1
            with self.subTest(mode=mode), self.assertRaises(abi.Rejected): abi.recommend(req)
        req = action_fixture(); at = req['root_receipt']['action_registry']['actions'][0]['at_qpc_ns']
        req['root_receipt']['captures'][1]['adc_pose']['valid_span']['from_qpc_ns'] = at
        self.assertTrue(abi.recommend(req)['core_ran'])

    def test13_missing_book_does_not_mask_supplied_time_conflicts(self):
        for enabled in (False, True):
            for kind in ('adc', 'em', 'admission'):
                req = fixture(); req['enabled'] = enabled; root = req['root_receipt']
                root['config'] = None; record = root['captures'][0]
                if kind == 'admission':
                    record['adc_call']['end_qpc_ns'] = req['candidate']['source_time']['admission_received_monotonic_ns']+1
                else:
                    record[kind+'_pose']['pose_read']['end_qpc_ns'] = record['adc_call']['begin_qpc_ns']+1
                with self.subTest(enabled=enabled, kind=kind), self.assertRaises(abi.Rejected): abi.recommend(req)
        for make in (fixture, action_fixture):
            req = make(); self.assertTrue(abi.recommend(req)['core_ran'])
            req['root_receipt']['config'] = None; self.unavailable(req)

    def test14_combined_budget_precedes_missing_and_disabled(self):
        def actions(req, count):
            return [dict(receipt_id=None, action_id='missing-execution-'+str(i), state='executed',
                observation_capture_sha256=req['candidate']['observation_identity']['capture_sha256'],
                at_qpc_ns=req['now_qpc_ns'], from_pose=copy.deepcopy(POSE), to_pose=copy.deepcopy(POSE),
                from_pose_revision=None, to_pose_revision=None) for i in range(count)]

        def expect_no_core(req):
            result = abi.recommend(req)
            self.assertFalse(result['core_ran']); self.assertEqual(result['status'], 'STOP')
            self.assertEqual(result['input_status'], 'INPUT_UNAVAILABLE' if req['enabled'] else 'DISABLED')

        for enabled in (False, True):
            for missing in ('config', 'current_pose', 'source_admissions', 'captures', 'pose_book_id', 'adc_call', 'execution_receipt'):
                for count in (31, 32):
                    req = fixture(); req['enabled'] = enabled; root = req['root_receipt']
                    root['action_registry']['actions'] = actions(req, count)
                    if missing == 'pose_book_id': root['config']['pose_book_id'] = None
                    elif missing == 'adc_call': root['captures'][0]['adc_call'] = None
                    elif missing != 'execution_receipt': root[missing] = None
                    with self.subTest(enabled=enabled, missing=missing, combined=count+1):
                        if count == 32:
                            with self.assertRaisesRegex(abi.Rejected, 'combined supplied capture/action bound'): abi.recommend(req)
                        else: expect_no_core(req)
            # Receipt count also bounds memory even when missing config prevents association.
            for receipt_count in (31, 32):
                req = fixture(); req['enabled'] = enabled; root = req['root_receipt']; root['config'] = None
                root['captures'] = [None]*receipt_count
                root['action_registry']['actions'] = actions(req, 1)
                if receipt_count == 32:
                    with self.assertRaisesRegex(abi.Rejected, 'combined supplied capture/action bound'): abi.recommend(req)
                else: expect_no_core(req)
            # The candidate count wins when supplied receipts are missing or shorter.
            req = fixture(); req['enabled'] = enabled; req['history'] = [copy.deepcopy(req['candidate'])]
            req['root_receipt']['captures'] = None
            req['root_receipt']['action_registry']['actions'] = actions(req, 31)
            with self.assertRaisesRegex(abi.Rejected, 'combined supplied capture/action bound'): abi.recommend(req)
            # Null is zero supplied items for budgeting, never evidence of an empty registry.
            for missing_registry in (True, False):
                req = fixture(); req['enabled'] = enabled
                if missing_registry: req['root_receipt']['action_registry'] = None
                else: req['root_receipt']['action_registry']['actions'] = None
                expect_no_core(req)


if __name__ == '__main__':
    unittest.main(verbosity=2)

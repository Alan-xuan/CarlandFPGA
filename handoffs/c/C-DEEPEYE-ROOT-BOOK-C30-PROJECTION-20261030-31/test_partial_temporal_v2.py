"""NEW narrow C31 partial temporal controls; saved synthetic JSON only."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('c31_partial_temporal', HERE/'root_book_projection_v1.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def fixture():
    raw = (HERE/'interface-examples.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '8db30425213f590b531ce8d3b9e554ffe91402c94fc74843b4d533d3c9e538fd'
    value = json.loads(raw)['examples'][0]['input']
    value['enabled'] = False
    return value


def action(value, **changes):
    c = value['external']['candidate']
    pose = value['book_current']['pose']
    result = dict(receipt_id=None, action_id='new-v2-local-action', state='executed',
        observation_capture_sha256=c['observation_identity']['capture_sha256'],
        at_qpc_ns=value['external']['now_qpc_ns'], from_pose=copy.deepcopy(pose),
        to_pose=copy.deepcopy(pose), from_pose_revision=None, to_pose_revision=None)
    result.update(changes)
    value['external']['action_registry']['actions'].append(result)
    return result


def actions_only(value, keep_current=False):
    value['book'] = None; value['binding'] = None
    if not keep_current: value['book_current'] = None
    ext = value['external']
    ext['candidate'] = None; ext['history'] = []; ext['captures'] = None
    ext['config'] = None; ext['source_admissions'] = None; ext['current_pose'] = None


class PartialTemporal(unittest.TestCase):
    def checked(self, value, expected=None):
        calls = []
        original = adapter._C30.recommend_json
        def forbidden(_):
            calls.append(True)
            raise AssertionError('partial input must not call C30 JSON')
        adapter._C30.recommend_json = forbidden
        try:
            if expected:
                with self.assertRaisesRegex(adapter.Rejected, expected):
                    adapter.project_json(adapter._json(value))
            else:
                out = json.loads(adapter.project_json(adapter._json(value)))
                self.assertEqual(out['input_status'], 'INPUT_UNAVAILABLE')
                self.assertEqual(out['status'], 'STOP')
                self.assertFalse(out['c30_called']); self.assertFalse(out['core_ran'])
                self.assertIsNone(out['projection']); self.assertIsNone(out['c30_result'])
            self.assertEqual(calls, [])
        finally:
            adapter._C30.recommend_json = original

    def test_01_partial_begin_future_disabled(self):
        v = fixture(); call = v['book']['samples'][-1]['adc']
        call['end_qpc_ns'] = None; call['begin_qpc_ns'] = v['external']['now_qpc_ns']+17
        self.checked(v, 'C31 supplied ADC begin')

    def test_02_partial_begin_before_nominal_without_reads(self):
        v = fixture(); s = v['book']['samples'][-1]; s['pose_reads'] = None
        s['adc']['end_qpc_ns'] = None; s['adc']['begin_qpc_ns'] = s['nominal_qpc_ns']-3
        self.checked(v, 'C31 supplied ADC begin')

    def test_03_partial_begin_read_order_disabled(self):
        v = fixture(); s = v['book']['samples'][0]; s['adc']['end_qpc_ns'] = None
        s['adc']['begin_qpc_ns'] = s['pose_reads']['adc']['end_qpc_ns']-7
        self.checked(v, 'C31 read after ADC call begin')

    def test_04_partial_current_conflict_no_binding_or_receipts(self):
        v = fixture(); v['binding'] = None; v['external']['current_pose'] = None
        v['book_current']['pose']['position_m'][1] = 0.125
        self.checked(v, 'C31 actual same revision')

    def test_05_partial_current_span_action_missing_receipt(self):
        v = fixture(); v['external']['current_pose']['valid_span_receipt_id'] = None
        a = action(v, from_pose_revision=0, to_pose_revision=2)
        # Remove sample spans: actual current span alone proves the conflict.
        for s in v['book']['samples']: s['numerical_pose_span'] = None
        self.checked(v, 'C31 actual span contradicts')

    def test_06_no_config_action_before_receiver(self):
        v = fixture(); v['external']['config'] = None
        action(v, at_qpc_ns=v['external']['candidate']['observation_identity']['receiver_upper_qpc_ns']-13)
        self.checked(v, 'C31 action before supplied observation')

    def test_07_no_candidate_book_cause_future(self):
        v = fixture(); a = action(v)
        r = v['external']['captures'][-1]; r['cause_action_id'] = a['action_id']
        v['external']['candidate'] = None; v['external']['history'] = []
        self.checked(v, 'C31 supplied action cause')

    def test_08_no_candidate_reversed_action(self):
        v = fixture(); action(v, from_pose_revision=3, to_pose_revision=1)
        v['external']['candidate'] = None; v['external']['history'] = []
        self.checked(v, 'C31 actual action revision')

    def test_09_no_candidate_nonexecuted(self):
        v = fixture(); action(v, state='proposed')
        v['external']['candidate'] = None; v['external']['history'] = []
        self.checked(v, 'C31 actual action must be executed')

    def test_10_no_candidate_duplicate_ids(self):
        v = fixture(); a = action(v)
        v['external']['action_registry']['actions'].append(copy.deepcopy(a))
        v['external']['candidate'] = None; v['external']['history'] = []
        self.checked(v, 'C31 duplicate actual action')

    def test_11_no_candidate_action_order(self):
        v = fixture(); action(v); action(v, action_id='new-v2-second', at_qpc_ns=v['external']['now_qpc_ns']-1)
        v['external']['candidate'] = None; v['external']['history'] = []
        self.checked(v, 'C31 actual action time reversal')

    def test_12_partial_valid_begin_stays_unavailable(self):
        v = fixture(); v['book']['samples'][0]['adc']['end_qpc_ns'] = None
        self.checked(v)

    def test_13_unknown_action_observation_stays_unavailable(self):
        v = fixture(); action(v, observation_capture_sha256='c'*64)
        v['external']['candidate'] = None; v['external']['history'] = []
        self.checked(v)

    def test_14_partial_current_consistent_stays_unavailable(self):
        v = fixture(); v['external']['current_pose']['receipt_id'] = None; v['binding'] = None
        self.checked(v)

    def test_15_new_partial_equal_read_boundary_enabled(self):
        v = fixture(); v['enabled'] = True; s = v['book']['samples'][0]
        s['adc']['end_qpc_ns'] = None
        s['adc']['begin_qpc_ns'] = max(r['end_qpc_ns'] for r in s['pose_reads'].values())
        self.checked(v)

    def test_16_new_unknown_references_no_invented_action_evidence(self):
        v = fixture(); v['enabled'] = True
        action(v, observation_capture_sha256='d'*64)
        v['external']['captures'][0]['cause_action_id'] = 'absent-v2-cause'
        v['external']['candidate'] = None; v['external']['history'] = []
        self.checked(v)

    def test_17_actual_sample_without_source_hash_still_checked(self):
        v = fixture(); v['binding'] = None; v['external']['current_pose'] = None
        s = v['book']['samples'][0]; s['source_sha256'] = None
        s['pose_reads']['adc']['pose']['position_m'][2] = 0.0625
        self.checked(v, 'C31 actual same revision')

    def test_18_new_complete_goal_exact_json_and_core(self):
        v = fixture(); v['enabled'] = True; v['external']['config']['goal_m'] = [0.06, 0.025, 0.0]
        calls = []; original_json = adapter._C30.recommend_json; original_bind = adapter._C30._bind_core
        def json_call(raw):
            calls.append('json'); return original_json(raw)
        def bind_call(view):
            bound = original_bind(view)
            def core_call(request):
                calls.append('core'); return bound(request)
            return core_call
        adapter._C30.recommend_json = json_call; adapter._C30._bind_core = bind_call
        try:
            out = json.loads(adapter.project_json(adapter._json(v)))
            self.assertEqual(calls, ['json', 'core'])
            self.assertTrue(out['c30_called']); self.assertTrue(out['core_ran'])
            self.assertEqual(out['input_status'], 'COMPLETE_DIAGNOSTIC')
            self.assertEqual(out['claim'], 'numerical_immutable_committed_root_only')
            self.assertFalse(out['native_interval_atomic'])
        finally:
            adapter._C30.recommend_json = original_json; adapter._C30._bind_core = original_bind

    def test_19_v3_unknown_after_before_reversal(self):
        v = fixture(); now = v['external']['now_qpc_ns']
        action(v, from_pose_revision=11, at_qpc_ns=now-3)
        action(v, action_id='v3-next', from_pose_revision=10, at_qpc_ns=now-2)
        actions_only(v)
        self.checked(v, 'C31 actual action revision')

    def test_20_v3_unknown_after_equal_current(self):
        v = fixture(); action(v, from_pose_revision=11)
        v['book_current']['pose_revision'] = 11; v['book_current']['valid_span'] = None
        actions_only(v, keep_current=True)
        self.checked(v, 'C31 actual current predates executed revision')

    def test_21_v3_unknown_after_unrepresentable(self):
        v = fixture(); action(v, from_pose_revision=(1<<63)-1)
        actions_only(v)
        self.checked(v, 'C31 actual action revision')

    def test_22_v3_unknown_after_old_span(self):
        v = fixture(); action(v, from_pose_revision=0)
        v['book_current'] = None; v['external']['current_pose'] = None; v['binding'] = None
        self.checked(v, 'C31 actual span contradicts')

    def test_23_v3_valid_increasing_unknown_after_current_greater(self):
        v = fixture(); now = v['external']['now_qpc_ns']
        action(v, from_pose_revision=11, at_qpc_ns=now-3)
        action(v, action_id='v3-valid-next', from_pose_revision=12, at_qpc_ns=now-2)
        v['book_current']['pose_revision'] = 13; v['book_current']['valid_span'] = None
        actions_only(v, keep_current=True); original = copy.deepcopy(v)
        self.checked(v)
        self.assertEqual(v, original)
        self.assertTrue(all(a['to_pose_revision'] is None for a in v['external']['action_registry']['actions']))

    def test_24_v3_last_representable_unknown_successor(self):
        v = fixture(); action(v, from_pose_revision=(1<<63)-2)
        v['book_current']['pose_revision'] = (1<<63)-1; v['book_current']['valid_span'] = None
        actions_only(v, keep_current=True); original = copy.deepcopy(v)
        self.checked(v)
        self.assertEqual(v, original)

    def test_25_v3_lower_bound_not_actual_after_span(self):
        v = fixture(); now = v['external']['now_qpc_ns']
        action(v, from_pose_revision=0, at_qpc_ns=now)
        v['binding'] = None; v['book_current'] = None; v['external']['current_pose'] = None
        # Revision 1 may be before the unknown actual after (>1). Its old span
        # must not be forced to start at commit merely because lower bound=1.
        v['book']['fixed_root_interval']['pose_revision'] = 1
        v['book']['fixed_root_interval']['through_qpc_ns'] = now-1
        for s in v['book']['samples']:
            s['numerical_pose_span']['pose_revision'] = 1
            for r in s['pose_reads'].values(): r['pose_revision'] = 1
        v['external']['candidate'] = None; v['external']['history'] = []
        self.checked(v)


if __name__ == '__main__':
    unittest.main(verbosity=2)

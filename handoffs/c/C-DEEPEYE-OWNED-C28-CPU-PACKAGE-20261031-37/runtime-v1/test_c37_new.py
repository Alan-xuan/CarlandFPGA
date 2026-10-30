"""NEW C37 offline controls only. No original actor, native API or old suite."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / 'c37-owned-cpu-package'
spec = importlib.util.spec_from_file_location('new_c37_entry', PACKAGE / 'c37_entry.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)
p = entry.load_package()
BASE = (1 << 62) + 123456789


def pose(x=0):
    return {'position_m': [x, 0, 0], 'orientation_xyzw': [0, 0, 0, 1]}


def fixture(enabled=True):
    obs = dict(sample_id='a'*64, counts=[1740, 2048, 2048, 0], quality=15,
               adc_qpc_ns=BASE, em_qpc_ns=BASE, adc_pose=pose(), em_pose=pose())
    return dict(schema_version=1, projection_id='c36_c28_public_view_v1', enabled=enabled,
                now_qpc_ns=BASE, pose=pose(), goal_m=[0, 0, 10], observation=obs,
                history=[], executed_actions=[])


IDS = dict(operation_id='C37-new-synthetic', run_id='synthetic-not-host-proof',
           actor_instance_id='synthetic-not-owned', invocation_id=(1 << 63)-1,
           tested_commit='a'*40, package_manifest_sha256='b'*64)


def wire(view, enabled=None):
    if enabled is None:
        enabled = view['enabled']
    envelope = dict(abi=p.ABI, kind='recommend', echo_ids=IDS, enabled=enabled, input=view)
    raw = json.dumps(envelope, separators=(',', ':')).encode()
    return len(raw).to_bytes(4, 'little') + raw


def output(raw):
    result, offset = [], 0
    while offset < len(raw):
        n = int.from_bytes(raw[offset:offset+4], 'little')
        result.append(json.loads(raw[offset+4:offset+4+n]))
        offset += n+4
    assert offset == len(raw) and len(result) == 2
    return result


def run_case(raw):
    calls = []
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code is p._FROZEN.recommend.__code__:
            calls.append(frame.f_globals)
    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        responses = output(p.process_wire(raw))
    finally:
        sys.setprofile(previous)
    return responses, calls


class FakeTransport:
    def __init__(self, raw, fragment=8192, short_write=False):
        self.raw, self.fragment, self.short_write = raw, fragment, short_write
        self.offset, self.output, self.events = 0, bytearray(), []

    def signal_ready(self):
        self.events.append('event')

    def read(self, size):
        assert 0 < size <= 8192
        self.events.append(('read', size))
        count = min(size, self.fragment)
        data = self.raw[self.offset:self.offset+count]
        self.offset += len(data)
        return data

    def write(self, raw):
        assert self.offset == len(self.raw), 'unsolicited stdout'
        assert 0 < len(raw) <= 8192
        self.events.append(('write', len(raw)))
        self.output.extend(raw)
        return len(raw)-1 if self.short_write else len(raw)

    def close(self):
        self.events.append('close')


class NewC37Controls(unittest.TestCase):
    def test01_same_code_only_private_validator_and_one_core(self):
        self.assertIs(p._CORE.__code__, p._FROZEN.recommend.__code__)
        a, b = p._CORE.__globals__, p._FROZEN.recommend.__globals__
        self.assertEqual(set(a), set(b))
        self.assertEqual([k for k in a if a[k] is not b[k]], ['_validate'])
        replies, calls = run_case(wire(fixture()))
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0], a)
        ready, result = replies
        self.assertEqual((ready['kind'], result['kind']), ('READY', 'RESULT'))
        self.assertTrue(result['core_ran'])
        self.assertEqual(result['result']['status'], 'ADVISE')
        self.assertEqual(result['result']['observation'], fixture()['observation'])
        self.assertEqual(result['authority'], 'none')
        self.assertFalse(result['completion_grant'])

    def test02_high_qpc_exact_100ms_and_one_ns_late(self):
        for age, expected in ((100_000_000, 'bounded_observation_goal_search'),
                              (100_000_001, 'original_sample_expired')):
            view = fixture(); view['now_qpc_ns'] += age
            replies, calls = run_case(wire(view))
            result = replies[1]
            self.assertEqual(len(calls), 1)
            self.assertEqual(result['result']['reason'], expected)
            self.assertEqual(result['result']['map_cells'][0]['em_qpc_ns'], BASE) if age == 100_000_000 else None
            self.assertEqual(result['result']['observation']['em_qpc_ns'], BASE)

    def test03_null_fault_and_null_C3_legal_STOP(self):
        for q, counts in ((0x1008, [None, None, None, 0]), (0x1000, [None]*4),
                          (7, [1740, 2048, 2048, None])):
            v = fixture(); o = v['observation']; o.update(quality=q, counts=counts)
            if q & 0x1000: o.update(em_qpc_ns=None, em_pose=None)
            replies, calls = run_case(wire(v))
            self.assertEqual(len(calls), 1)
            self.assertEqual(replies[1]['result']['reason'], 'invalid_faulted_or_saturated')
            self.assertEqual(replies[1]['result']['observation'], o)

    def test04_C3_saturation_not_fullscale(self):
        v = fixture(); v['observation']['quality'] |= 0x80; v['observation']['counts'][3] = 1300
        replies, calls = run_case(wire(v))
        self.assertEqual(len(calls), 1)
        self.assertEqual(replies[1]['result']['status'], 'STOP')

    def test05_held_exact_origin_one_map_and_no_revival(self):
        v = fixture(); origin = copy.deepcopy(v['observation']); v['history'] = [origin]
        v['observation'].update(sample_id='b'*64, adc_qpc_ns=BASE+1, quality=0x70f, adc_pose=pose(.1))
        v['now_qpc_ns'] += 1; v['pose'] = pose(.1)
        replies, calls = run_case(wire(v))
        self.assertEqual(len(calls), 1)
        self.assertEqual(replies[1]['result']['independent_em_count'], 1)
        self.assertEqual(replies[1]['result']['map_cells'][0]['pose'], origin['em_pose'])
        self.assertEqual(replies[1]['result']['map_cells'][0]['em_qpc_ns'], BASE)
        fault = dict(sample_id='c'*64, counts=[None]*4, quality=0x1000, adc_qpc_ns=BASE+1,
                     em_qpc_ns=None, adc_pose=pose(), em_pose=None)
        v['history'].append(fault); v['observation']['adc_qpc_ns'] = BASE+2; v['now_qpc_ns'] = BASE+2
        replies, calls = run_case(wire(v))
        self.assertEqual(len(calls), 0); self.assertEqual(replies[1]['reason'], 'HELD_ORIGIN')

    def test06_disabled_still_validates_and_inner_required(self):
        v = fixture(False)
        replies, calls = run_case(wire(v))
        self.assertEqual((replies[1]['status'], len(calls)), ('DISABLED', 0))
        v['truth'] = {'seed': 1}
        replies, calls = run_case(wire(v))
        self.assertEqual((replies[1]['status'], len(calls)), ('REJECTED', 0))
        del v['truth']; del v['enabled']
        replies, calls = run_case(wire(v, False))
        self.assertEqual((replies[1]['status'], len(calls)), ('REJECTED', 0))

    def test07_frame_total_boundary_and_trailing(self):
        raw = wire(fixture(False)); body = raw[4:]
        padded = body + b' '*(16380-len(body))
        maximum = len(padded).to_bytes(4, 'little') + padded
        replies, calls = run_case(maximum)
        self.assertEqual(replies[1]['status'], 'DISABLED'); self.assertFalse(calls)
        with self.assertRaises(p.Rejected): p.process_wire(maximum+b' ')
        for bad in (raw+b'x', raw[:-1], b'\0\0\0\0', b'\xff\xff\xff\xffx'):
            replies, calls = run_case(bad)
            self.assertEqual(replies[1]['status'], 'REJECTED'); self.assertFalse(calls)

    def test08_json_duplicate_nonfinite_type_and_enabled_conflict(self):
        base = wire(fixture(False))[4:]
        duplicates = base[:-1]+b',"enabled":false}'
        for body in (duplicates, b'{"x":NaN}', b'\xef\xbb\xbf{}'):
            replies, calls = run_case(len(body).to_bytes(4, 'little')+body)
            self.assertEqual(replies[1]['status'], 'REJECTED'); self.assertFalse(calls)
        for modify in (lambda v: v.update(now_qpc_ns=True), lambda v: v['observation'].update(quality=True),
                       lambda v: v['observation']['counts'].__setitem__(0, None)):
            v = fixture(False); modify(v)
            replies, calls = run_case(wire(v))
            self.assertEqual(replies[1]['status'], 'REJECTED'); self.assertFalse(calls)
        replies, calls = run_case(wire(fixture(), False))
        self.assertEqual(replies[1]['reason'], 'ENABLED_CONFLICT'); self.assertFalse(calls)

    def test09_32_combined_and_33_refused(self):
        v = fixture(); v['executed_actions'] = [dict(action_id=str(i), from_pose=pose(), to_pose=pose()) for i in range(31)]
        replies, calls = run_case(wire(v)); self.assertEqual(len(calls), 1)
        v['executed_actions'].append(dict(action_id='32', from_pose=pose(), to_pose=pose()))
        replies, calls = run_case(wire(v)); self.assertFalse(calls)
        self.assertEqual(replies[1]['reason'], 'COMBINED_BUDGET')

    def test10_new_fake_entry_fragments_no_EOF_no_unsolicited(self):
        raw = wire(fixture()); transport = FakeTransport(raw, fragment=3)
        entry.serve(transport, len(raw), 1, p)
        self.assertEqual(transport.events[0], 'event')
        self.assertEqual(transport.events[-1], 'close')
        self.assertEqual(transport.offset, len(raw))
        self.assertEqual(output(bytes(transport.output))[1]['result']['status'], 'ADVISE')
        self.assertLessEqual(len(transport.output), 18440)

    def test11_short_io_terminal_no_retry_and_multi_refused(self):
        raw = wire(fixture())
        transport = FakeTransport(raw[:-1])
        with self.assertRaises(ValueError): entry.serve(transport, len(raw), 1, p)
        self.assertEqual(transport.events[-1], 'close'); self.assertFalse(transport.output)
        transport = FakeTransport(raw, short_write=True)
        with self.assertRaises(ValueError): entry.serve(transport, len(raw), 1, p)
        self.assertEqual(sum(isinstance(e, tuple) and e[0]=='write' for e in transport.events), 1)
        self.assertEqual(transport.events[-1], 'close')
        self.assertEqual(entry.main(['--actor-stdio-v1', '--max-invocations', '2', '--request-bytes', str(len(raw)), '10', '11', '12']), 64)

    def test12_missing_public_projection_no_bytes_no_dispatch(self):
        # Integration boundary test only: no real C36/provider provenance is claimed.
        dispatched = []
        with self.assertRaises(p.Rejected):
            raw = p.make_request(IDS, None, enabled=True)
            dispatched.append(raw)
        self.assertEqual(dispatched, [])

    def test13_pose_unsupported_and_roll_supported(self):
        v = fixture(); v['pose']['orientation_xyzw'] = [0, 1, 0, 0]
        replies, calls = run_case(wire(v))
        self.assertEqual(len(calls), 1)
        self.assertEqual(replies[1]['result']['reason'], 'original_observation_pose_inapplicable')
        v['pose']['orientation_xyzw'] = [0, 0, 1, 0]
        replies, calls = run_case(wire(v))
        self.assertEqual(replies[1]['result']['status'], 'ADVISE')

    def test14_output_budget_truthful_core_flag(self):
        original = p._dump
        large_once = [True]
        def encode(value):
            if value.get('kind') == 'RESULT' and large_once[0]:
                large_once[0] = False
                return b' '*16385
            return original(value)
        # Encoder fault injection only; original planner/globals/helpers unchanged.
        with patch.object(p, '_dump', encode):
            replies, calls = run_case(wire(fixture()))
        self.assertEqual(len(calls), 1)
        self.assertTrue(replies[1]['core_ran'])
        self.assertEqual(replies[1]['reason'], 'OUTPUT_TOO_LARGE')
        self.assertIsNone(replies[1]['result'])

    def test15_no_Fraction_or_legacy_time_on_wire(self):
        replies, calls = run_case(wire(fixture()))
        raw = json.dumps(replies)
        self.assertNotIn('tick_ms', raw); self.assertNotIn('Fraction', raw)
        self.assertEqual(replies[1]['request_wire_sha256'], hashlib.sha256(wire(fixture())).hexdigest())
        self.assertEqual(replies[1]['echo_ids']['invocation_id'], (1 << 63)-1)

    def test16_core_dependency_hash_fails_before_import(self):
        target = ROOT / 'test-artifacts' / 'corrupt-package'
        target.mkdir(parents=True, exist_ok=False)
        for name in ('c37_entry.py', 'c37_package.py', 'frozen_c28.py', 'package-manifest.json'):
            (target/name).write_bytes((PACKAGE/name).read_bytes())
        with (target/'frozen_c28.py').open('ab') as stream: stream.write(b'\n# corrupt control\n')
        spec = importlib.util.spec_from_file_location('corrupt_entry', target/'c37_entry.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with self.assertRaisesRegex(ValueError, 'package hash mismatch'): module.load_package()


if __name__ == '__main__':
    print(json.dumps({'suite':'NEW-C37-only', 'synthetic':True,
                      'fixture_wire_sha256':hashlib.sha256(wire(fixture())).hexdigest(),
                      'core_sha256':p.CORE_SHA256, 'original_actor_native_model_board_runs':0}))
    unittest.main(verbosity=2)

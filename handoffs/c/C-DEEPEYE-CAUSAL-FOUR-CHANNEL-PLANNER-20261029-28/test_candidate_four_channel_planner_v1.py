"""New C28 local function controls only; every input is labelled synthetic here."""
import copy
import json
import math
import unittest

import candidate_four_channel_planner_v1 as planner


def fixture(c0=1.0, c1=0.0, c2=0.0, c3=0.0):
    binding = dict(run_id='local-fixture-only', build_sha256='a'*64, boot_sha256='b'*64,
                   session=1, config_epoch=1, clock_domain='fixture-tick-ms', source_id=4,
                   source_mode='twin_fixture', profile_id=planner.PROFILE,
                   producer_sha256=planner.PRODUCER_SHA256, topology_id=2)
    pose = dict(position_m=[0.0, 0.0, 0.0], orientation_xyzw=[0.0, 0.0, 0.0, 1.0])
    values = (c0, c1, c2, c3)
    lows = (math.log10(0.2), -2, -2, 0)
    spans = (4, 4, 4, 2)
    obs = dict(binding=copy.deepcopy(binding), sample_id='fixture-100', trigger_id='fixture-trigger-100',
               sequence=10, board_frame_sha256='c'*64, source_record_sha256='d'*64,
               adc_tick_ms=100, em_tick_ms=100, em_origin_sample_id='fixture-100',
               counts=[round((v-low)/span*4095) for v, low, span in zip(values, lows, spans)],
               quality=15, adc_pose=copy.deepcopy(pose), em_pose=copy.deepcopy(pose), cause_action_id=None)
    return dict(schema_version=1, enabled=False, binding=binding, now_tick_ms=100,
                pose=pose, goal_m=[0.0, 0.0, 10.0], observation=obs, history=[], executed_actions=[])


def enabled(*values):
    req = fixture(*values)
    req['enabled'] = True
    return req


def held_request():
    req = enabled(0.0, 1.0, 1.0, 0.0)
    req['history'] = [copy.deepcopy(req['observation'])]
    obs = req['observation']
    obs.update(sample_id='fixture-110', trigger_id='fixture-trigger-110', sequence=11,
               adc_tick_ms=110, quality=0x70F, board_frame_sha256='e'*64,
               source_record_sha256='f'*64)
    req['now_tick_ms'] = 110
    return req


def yaw_pose(degrees):
    half = math.radians(degrees)/2
    return [0.0, math.sin(half), 0.0, math.cos(half)]


class PlannerTests(unittest.TestCase):
    def reject(self, req):
        with self.assertRaises(planner.Rejected):
            planner.recommend(req)

    def test_disabled_and_positive_both_h12(self):
        self.assertEqual(planner.recommend(fixture())['reason'], 'disabled')
        for topology in (1, 2):
            req = enabled()
            req['binding']['topology_id'] = topology
            req['observation']['binding']['topology_id'] = topology
            got = planner.recommend(req)
            self.assertEqual(got['status'], 'ADVISE')
            self.assertEqual(got['authorization'], 'none')
            self.assertGreater(got['speed_limit_m_s'], 0)
            self.assertLessEqual(got['speed_limit_m_s'], 0.25)
            self.assertAlmostEqual(sum(v*v for v in got['direction_world']), 1)

    def test_counts_exact_mapping_and_null(self):
        got = planner.decode_counts([0, 0, 4095, 4095])
        self.assertEqual(got, [math.log10(0.2), -2, 2, 2])
        self.assertEqual(planner.decode_counts([None]*4), [None]*4)
        self.assertLess(planner.decode_counts([0, 2047, 0, 0])[1], 0)
        self.assertGreater(planner.decode_counts([0, 2048, 0, 0])[1], 0)

    def test_same_goal_contrast_3d_signs_and_vibration(self):
        right_up = planner.recommend(enabled(0, 1.2, 1.2, 0))
        left_down = planner.recommend(enabled(0, -1.2, -1.2, 0))
        self.assertEqual(right_up['status'], 'ADVISE')
        self.assertEqual(left_down['status'], 'ADVISE')
        self.assertGreater(right_up['direction_world'][0], 0)
        self.assertGreater(right_up['direction_world'][1], 0)
        self.assertLess(left_down['direction_world'][0], 0)
        self.assertLess(left_down['direction_world'][1], 0)
        self.assertNotEqual(right_up['direction_world'], left_down['direction_world'])
        hard = planner.recommend(enabled(2, 1.2, 1.2, 0))
        self.assertLess(hard['direction_world'][0], 0)
        self.assertLess(hard['direction_world'][1], 0)
        self.assertEqual(planner.recommend(enabled(1, 0, 0, 1))['reason'], 'contact_vibration_risk')

    def test_goal_changes_advice_and_no_arrival_claim(self):
        left, right = enabled(), enabled()
        left['goal_m'] = [-8, 0, 10]
        right['goal_m'] = [8, 0, 10]
        self.assertLess(planner.recommend(left)['direction_world'][0], 0)
        self.assertGreater(planner.recommend(right)['direction_world'][0], 0)
        left['goal_m'] = [0, 0, -10]
        self.assertEqual(planner.recommend(left)['reason'], 'no_forward_goal_progress')
        left['goal_m'] = [0, 0, 0]
        self.assertEqual(planner.recommend(left)['reason'], 'goal_near_requires_authority_completion')

    def test_source_fault_c3_valid_and_saturation_are_legal_stop(self):
        req = enabled()
        req['observation'].update(counts=[None, None, None, 0], quality=0x1008,
                                  em_tick_ms=None, em_origin_sample_id=None, em_pose=None)
        self.assertEqual(planner.recommend(req)['reason'], 'invalid_faulted_or_saturated')
        req = enabled(1, 0, 0, 0.7)
        req['observation']['quality'] |= 0x80
        self.assertEqual(planner.recommend(req)['status'], 'STOP')
        req = enabled(math.log10(0.2), 0, 0, 0)
        req['observation']['quality'] |= 0x10
        self.assertEqual(planner.recommend(req)['status'], 'STOP')

    def test_original_age_exact100_and_expiry(self):
        req = held_request()
        req['observation']['adc_tick_ms'] = 200
        req['now_tick_ms'] = 200
        self.assertEqual(planner.recommend(req)['status'], 'ADVISE')
        req['now_tick_ms'] = 201
        self.assertEqual(planner.recommend(req)['reason'], 'original_sample_expired')
        req['observation']['adc_tick_ms'] = 210
        req['now_tick_ms'] = 210
        self.reject(req)

    def test_held_no_new_evidence_preserves_original_pose(self):
        req = held_request()
        req['pose']['position_m'] = [0, 0, 0.2]
        req['observation']['adc_pose']['position_m'] = [0, 0, 0.1]
        got = planner.recommend(req)
        self.assertEqual(got['independent_em_count'], 1)
        self.assertEqual(got['map_cells'][0]['pose']['position_m'], [0, 0, 0])
        fresh = enabled(0, 1, 1, 0)
        self.assertGreater(got['uncertainty'], planner.recommend(fresh)['uncertainty'])
        for field, value in [('counts', [2000, 1, 2, 0]), ('em_pose', req['observation']['adc_pose'])]:
            bad = copy.deepcopy(req); bad['observation'][field] = value
            self.reject(bad)
        req['history'] = []
        self.reject(req)

    def test_original_direction_frame_not_current_frame(self):
        req = held_request()
        # Current drill rolls180degrees; original positiveX/Y observations stay
        # in original world directions. A current-pose substitution flips both.
        req['pose']['orientation_xyzw'] = [0, 0, 1, 0]
        req['observation']['adc_pose']['orientation_xyzw'] = [0, 0, 1, 0]
        got = planner.recommend(req)
        self.assertGreater(got['direction_world'][0], 0)
        self.assertGreater(got['direction_world'][1], 0)

    def test_old_forward_cannot_advise_yaw180_or_yaw90(self):
        for degrees in (90, -90, 180):
            req = held_request()
            req['pose']['orientation_xyzw'] = yaw_pose(degrees)
            req['observation']['adc_pose']['orientation_xyzw'] = yaw_pose(degrees)
            req['goal_m'] = [10*math.sin(math.radians(degrees)), 0,
                             10*math.cos(math.radians(degrees))]
            got = planner.recommend(req)
            self.assertEqual(got['reason'], 'original_observation_pose_inapplicable')
            self.assertEqual(got['status'], 'STOP')
            self.assertEqual(got['speed_limit_m_s'], 0)
            self.assertEqual(got['direction_world'], [0, 0, 0])
            self.assertEqual(got['risk'], 1)
            self.assertEqual(got['uncertainty'], 1)
            self.assertEqual(got['map_cells'][0]['pose']['orientation_xyzw'], [0, 0, 0, 1])

    def test_reuse_angular_boundary_pairwise_and_roll(self):
        for degrees in (0, 10, 15):
            req = held_request()
            req['pose']['orientation_xyzw'] = yaw_pose(degrees)
            req['observation']['adc_pose']['orientation_xyzw'] = yaw_pose(degrees)
            self.assertEqual(planner.recommend(req)['status'], 'ADVISE')
        req['pose']['orientation_xyzw'] = yaw_pose(15.000001)
        self.assertEqual(planner.recommend(req)['reason'], 'original_observation_pose_inapplicable')
        req = held_request()
        req['pose']['orientation_xyzw'] = yaw_pose(-14)
        req['observation']['adc_pose']['orientation_xyzw'] = yaw_pose(14)
        self.assertEqual(planner.recommend(req)['status'], 'STOP')
        # Roll alone can differ arbitrarily; original world contrast stays fixed.
        req = held_request()
        req['pose']['orientation_xyzw'] = [0, 0, 1, 0]
        got = planner.recommend(req)
        self.assertEqual(got['status'], 'ADVISE')
        self.assertGreater(got['direction_world'][0], 0)
        self.assertGreater(got['direction_world'][1], 0)

    def test_reuse_translation_boundary_and_each_pose_pair(self):
        req = held_request()
        req['pose']['position_m'] = [0, 0, 0.25]
        self.assertEqual(planner.recommend(req)['status'], 'ADVISE')
        req['pose']['position_m'][2] = math.nextafter(0.25, math.inf)
        self.assertEqual(planner.recommend(req)['reason'], 'original_observation_pose_inapplicable')
        for change_current, change_adc in ((True, False), (False, True), (True, True)):
            req = held_request()
            if change_current:
                req['pose']['position_m'] = [10, 0, 0]
            if change_adc:
                req['observation']['adc_pose']['position_m'] = [10, 0, 0]
            self.assertEqual(planner.recommend(req)['status'], 'STOP')
        req = held_request()
        req['pose']['position_m'] = [0.2, 0, 0]
        req['observation']['adc_pose']['position_m'] = [-0.2, 0, 0]
        self.assertEqual(planner.recommend(req)['status'], 'STOP')
        req = held_request()
        req['pose']['position_m'] = [0, 0, 0.2]
        req['observation']['adc_pose']['position_m'] = [0, 0, 0.1]
        self.assertEqual(planner.recommend(req)['status'], 'ADVISE')

    def test_each_advised_direction_inside_original_central_cone(self):
        req = held_request()
        req['pose']['orientation_xyzw'] = yaw_pose(15)
        req['observation']['adc_pose']['orientation_xyzw'] = yaw_pose(15)
        req['goal_m'] = [10, 0, 5]
        got = planner.recommend(req)
        self.assertEqual(got['status'], 'ADVISE')
        self.assertGreaterEqual(got['direction_world'][2], math.cos(math.radians(30))-1e-12)

    def test_quality_schema_time_identity_rejections(self):
        changes = [('quality', True), ('quality', 0x800F), ('quality', 0x80F),
                   ('quality', 14), ('quality', 31), ('counts', [True, 1, 2, 3]),
                   ('counts', [4096, 1, 2, 3]), ('counts', [None, 1, 2, 3]),
                   ('adc_tick_ms', 101), ('em_tick_ms', 150), ('em_tick_ms', None),
                   ('source_record_sha256', 'invalid')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                req = enabled(); req['observation'][key] = value; self.reject(req)
        for key, value in [('build_sha256', 'e'*64), ('source_id', 3), ('profile_id', 'sim_em_v2')]:
            req = enabled(); req['observation']['binding'][key] = value; self.reject(req)
        req = enabled(); req['observation']['truth'] = {}; self.reject(req)
        req = enabled(); req['pose']['position_m'][0] = float('nan'); self.reject(req)
        req = enabled(); req['now_tick_ms'] = 99; self.reject(req)

    def test_duplicate_order_and_budget(self):
        req = enabled(); req['history'] = [copy.deepcopy(req['observation'])]; self.reject(req)
        req = held_request(); req['observation']['sequence'] = 9; self.reject(req)
        req = enabled(); req['history'] = [copy.deepcopy(req['observation'])]*32; self.reject(req)
        req = enabled(); req['pose']['position_m'][0] = 1001; self.reject(req)

    def test_fault_revival_and_full_history_bound(self):
        req = held_request()
        fault = copy.deepcopy(req['history'][0])
        fault.update(sample_id='fixture-fault', sequence=11, adc_tick_ms=110,
                     counts=[None, None, None, 0], quality=0x1008,
                     em_tick_ms=None, em_origin_sample_id=None, em_pose=None)
        req['history'].append(fault)
        req['observation'].update(sample_id='fixture-120', sequence=12, adc_tick_ms=120)
        req['now_tick_ms'] = 120
        self.reject(req)
        req = enabled()
        records = []
        for index in range(32):
            item = copy.deepcopy(req['observation'])
            tick = 100 + index*50
            item.update(sample_id='fixture-native-' + str(index), sequence=index,
                        adc_tick_ms=tick, em_tick_ms=tick,
                        em_origin_sample_id='fixture-native-' + str(index))
            records.append(item)
        req.update(history=records[:-1], observation=records[-1], now_tick_ms=1650)
        got = planner.recommend(req)
        self.assertEqual(got['independent_em_count'], 32)
        self.assertEqual(len(got['map_cells']), 32)

    def test_executed_action_causal_binding(self):
        req = held_request()
        action = dict(binding=copy.deepcopy(req['binding']), action_id='fixture-executed-1',
                      observation_sample_id='fixture-100', at_tick_ms=105,
                      from_pose=copy.deepcopy(req['pose']), to_pose=copy.deepcopy(req['pose']))
        action['to_pose']['position_m'] = [0, 0, 0.01]
        req['executed_actions'] = [action]
        req['observation']['cause_action_id'] = action['action_id']
        self.assertEqual(planner.recommend(req)['status'], 'ADVISE')
        req['executed_actions'][0]['at_tick_ms'] = 110
        self.reject(req)

    def test_determinism_detached_no_mutation_and_strict_json(self):
        req = enabled(); original = copy.deepcopy(req)
        a, b = planner.recommend(req), planner.recommend(req)
        self.assertEqual(a, b); self.assertEqual(req, original)
        a['observation']['counts'][0] = 0
        self.assertEqual(req, original)
        raw = json.dumps(req).encode()
        self.assertEqual(json.loads(planner.recommend_json(raw)), b)
        for bad in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b' '*262145,
                    b'['*1001+b']'*1001):
            with self.assertRaises(planner.Rejected):
                planner.recommend_json(bad)


if __name__ == '__main__':
    unittest.main(verbosity=2)

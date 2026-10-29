"""Portable C28 synthetic pure-function checks; no board or control claim.

Usage: python -B independent_checks.py PUBLIC_DIRECTORY
Reads that directory; never writes candidate source or imports its test suite.
"""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
PUBLIC = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location('c28_independent_candidate', PUBLIC/'candidate_four_channel_planner_v1.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
PRODUCER = '6a5f70a6acdaa6de52fc72d678d452956861370e1d143b70219ced107c5a04c9'
RESULTS = {}

def fixture(values=(1.,0.,0.,0.), tick=100):
    binding = dict(run_id='independent-synthetic', build_sha256='1'*64, boot_sha256='2'*64,
        session=23, config_epoch=7, clock_domain='independent-fixture-ms', source_id=4,
        source_mode='twin_fixture', profile_id='deepeye_forward_profile_candidate_v1',
        producer_sha256=PRODUCER, topology_id=2)
    pose = dict(position_m=[0.,0.,0.], orientation_xyzw=[0.,0.,0.,1.])
    counts = [round((v-lo)*4095/span) for v,lo,span in zip(values,
        (math.log10(.2),-2.,-2.,0.), (4.,4.,4.,2.))]
    obs = dict(binding=copy.deepcopy(binding), sample_id=f'native-{tick}', trigger_id=f'trigger-{tick}',
        sequence=tick//10, board_frame_sha256='3'*64, source_record_sha256='4'*64,
        adc_tick_ms=tick, em_tick_ms=tick, em_origin_sample_id=f'native-{tick}',
        counts=counts, quality=15, adc_pose=copy.deepcopy(pose), em_pose=copy.deepcopy(pose), cause_action_id=None)
    return dict(schema_version=1,enabled=True,binding=binding,now_tick_ms=tick,pose=pose,
        goal_m=[0.,0.,10.],observation=obs,history=[],executed_actions=[])

def held(values=(1.,0.,0.,0.), tick=110):
    r=fixture(values)
    r['history']=[copy.deepcopy(r['observation'])]
    r['observation'].update(sample_id=f'held-{tick}',trigger_id=f'trigger-{tick}',
        sequence=tick//10,adc_tick_ms=tick,quality=0x70f)
    r['now_tick_ms']=tick
    return r

def fault(obs):
    obs.update(counts=[None,None,None,0],quality=0x1008,em_tick_ms=None,
        em_origin_sample_id=None,em_pose=None)

class IndependentChecks(unittest.TestCase):
    def reject(self,r):
        with self.assertRaises(p.Rejected): p.recommend(r)

    def test_01_counts_independent_inverse_and_half_bins(self):
        for q in (0,1,2047,2048,4094,4095):
            decoded=p.decode_counts([q]*4)
            for got,lo,span in zip(decoded,(math.log10(.2),-2,-2,0),(4,4,4,2)):
                self.assertAlmostEqual(got,lo+span*q/4095,places=14)
        self.assertEqual(p.decode_counts([None]*4),[None]*4)
        for q in (True,False,-1,4096,1.0):
            with self.assertRaises(p.Rejected): p.decode_counts([q,0,0,0])
        for q in (2047,2048):
            r=fixture();r['observation']['counts'][1:3]=[q,q]
            got=p.recommend(r)
            self.assertEqual(got['direction_world'],[0.,0.,1.])

    def test_02_quality_legal_zero_and_poor_stop(self):
        r=fixture();r['observation']['counts']=[0,0,0,0]
        p.recommend(r) # zero is valid, even if resulting risk causes STOP
        for q in (0,4095):
            r=fixture();r['observation']['counts'][0]=q
            p.recommend(r)
            r['observation']['quality']|=16
            self.assertEqual(p.recommend(r)['status'],'STOP')
        for c3 in (1295,2048,4095):
            r=fixture();r['observation']['counts'][3]=c3;r['observation']['quality']|=128
            self.assertEqual(p.recommend(r)['status'],'STOP')
        r=fixture();fault(r['observation'])
        self.assertEqual(p.recommend(r)['status'],'STOP')
        r=fixture(tick=0);r['observation']['quality']=7;r['observation']['counts'][3]=None
        self.assertEqual(p.recommend(r)['status'],'STOP')

    def test_03_quality_contradictions(self):
        for quality in (14,0x100f,0x80f,0x200f,True,31):
            r=fixture();r['observation']['quality']=quality;self.reject(r)
        r=fixture();r['observation']['counts'][0]=None;self.reject(r)
        r=fixture();fault(r['observation']);r['observation']['quality']|=16;self.reject(r)
        r=fixture();r['observation']['quality']|=128;r['observation']['counts'][3]=1294;self.reject(r)
        r=fixture(tick=50);self.reject(r)

    def test_04_original_age_grid_future(self):
        r=held(tick=200);self.assertEqual(p.recommend(r)['status'],'ADVISE')
        r['now_tick_ms']=201;self.assertEqual(p.recommend(r)['reason'],'original_sample_expired')
        r=held(tick=210);self.reject(r)
        for field,value in (('adc_tick_ms',109),('em_tick_ms',150),('em_tick_ms',None),('em_tick_ms',True)):
            r=held();r['observation'][field]=value;self.reject(r)
        r=fixture();r['now_tick_ms']=99;self.reject(r)

    def test_05_held_no_extra_confidence_and_original_pose(self):
        r=held((0,1.2,1.2,0));g1=p.recommend(r)
        r['history'].append(copy.deepcopy(r['observation']))
        r['observation'].update(sample_id='held-120',adc_tick_ms=120,sequence=12)
        r['now_tick_ms']=120;r['pose']['position_m']=[0,0,.1]
        r['observation']['adc_pose']['position_m']=[0,0,.1]
        g2=p.recommend(r)
        self.assertEqual(g2['independent_em_count'],1)
        self.assertEqual(g2['map_cells'],g1['map_cells'])
        self.assertGreaterEqual(g2['uncertainty'],g1['uncertainty'])
        r['pose']['orientation_xyzw']=[0,0,1,0]
        g=p.recommend(r)
        self.assertGreater(g['direction_world'][0],0);self.assertGreater(g['direction_world'][1],0)
        for field in ('counts','em_pose','quality'):
            bad=copy.deepcopy(r)
            if field=='counts': bad['observation']['counts'][1]+=1
            elif field=='em_pose': bad['observation']['em_pose']['position_m'][0]=.1
            else: bad['observation']['quality']|=16;bad['observation']['counts'][0]=0
            self.reject(bad)

    def test_06_fault_revival_origin_eviction_replay(self):
        r=held(tick=120);f=copy.deepcopy(r['history'][0]);fault(f)
        f.update(sample_id='fault-110',adc_tick_ms=110,sequence=11)
        r['history'].append(f);self.reject(r)
        r=held();r['history']=[];self.reject(r)
        r=fixture();r['history']=[copy.deepcopy(r['observation'])];self.reject(r)
        r=held();r['observation']['sequence']=10;self.reject(r)

    def test_07_same_goal_actual_decisions_and_signs(self):
        outputs=[]
        for values in ((0,1.2,1.2,0),(0,-1.2,-1.2,0),(2,1.2,1.2,0),(0,1.2,1.2,1)):
            outputs.append(p.recommend(fixture(values)))
        self.assertGreater(outputs[0]['direction_world'][0],0)
        self.assertGreater(outputs[0]['direction_world'][1],0)
        self.assertLess(outputs[1]['direction_world'][0],0)
        self.assertLess(outputs[1]['direction_world'][1],0)
        self.assertLess(outputs[2]['direction_world'][0],0)
        self.assertLess(outputs[2]['direction_world'][1],0)
        self.assertEqual(outputs[3]['status'],'STOP')
        RESULTS['same_goal_decisions']=[{k:g[k] for k in ('status','direction_world','speed_limit_m_s','risk','uncertainty')} for g in outputs]

    def test_08_context_and_hidden_inputs(self):
        for field,value in (('source_id',3),('source_id',1),('source_mode','sensor_live'),
                ('profile_id','sim_em_v2'),('producer_sha256','a'*64),('boot_sha256','a'*64),
                ('session',24),('clock_domain','different')):
            r=fixture();r['observation']['binding'][field]=value;self.reject(r)
        for field in ('obstacles','seed','collision_oracle','board_verified'):
            r=fixture();r[field]=True;self.reject(r)
        for topology in (1,2):
            r=fixture();r['binding']['topology_id']=topology;r['observation']['binding']['topology_id']=topology
            self.assertEqual(p.recommend(r)['authorization'],'none')

    def test_09_actions_causal_and_unconfirmed_shape(self):
        r=held()
        a=dict(binding=copy.deepcopy(r['binding']),action_id='executed-105',
            observation_sample_id='native-100',at_tick_ms=105,
            from_pose=copy.deepcopy(r['pose']),to_pose=copy.deepcopy(r['pose']))
        a['to_pose']['position_m'][2]=.01
        r['executed_actions']=[a];r['observation']['cause_action_id']=a['action_id']
        p.recommend(r)
        for field,value in (('at_tick_ms',110),('at_tick_ms',99),('at_tick_ms',111),
                            ('observation_sample_id','held-110')):
            bad=copy.deepcopy(r);bad['executed_actions'][0][field]=value;self.reject(bad)
        bad=copy.deepcopy(r);bad['executed_actions'][0]['status']='proposed';self.reject(bad)
        bad=copy.deepcopy(r);bad['executed_actions']=[];self.reject(bad)

    def test_10_budget_and_eviction(self):
        r=fixture();rows=[fixture(tick=100+i*50)['observation'] for i in range(32)]
        r.update(history=rows[:-1],observation=rows[-1],now_tick_ms=1650)
        g=p.recommend(r);self.assertEqual(len(g['map_cells']),32)
        r['history'].insert(0,copy.deepcopy(rows[0]));self.reject(r)
        r=fixture();r['history']=[None]*257;self.reject(r)
        r=held();r['history']=[];self.reject(r)

    def test_11_strict_json_detached_and_deterministic(self):
        r=held();original=copy.deepcopy(r)
        a=p.recommend(r);b=p.recommend(r)
        self.assertEqual(a,b);self.assertEqual(r,original)
        a['map_cells'][0]['pose']['position_m'][0]=99;a['observation']['binding']['run_id']='mutated'
        self.assertEqual(r,original)
        self.assertEqual(json.loads(p.recommend_json(json.dumps(r).encode())),b)
        for bad in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'\xff',
                    b' '*262145,b'['*1001+b']'*1001):
            with self.assertRaises(p.Rejected):p.recommend_json(bad)
        for value in (float('nan'),float('inf'),True,10**100):
            r=fixture();r['pose']['position_m'][0]=value;self.reject(r)
        r=fixture();r['history'].append(r);self.reject(r)

    def test_12_defaults_goal_and_no_arrival(self):
        r=fixture();r['enabled']=False
        g=p.recommend(r);self.assertEqual(g['reason'],'disabled');self.assertEqual(g['speed_limit_m_s'],0)
        del r['enabled'];self.reject(r)
        r=fixture();r['goal_m']=[0,0,0]
        self.assertEqual(p.recommend(r)['reason'],'goal_near_requires_authority_completion')
        r['goal_m']=[0,0,-10];self.assertEqual(p.recommend(r)['status'],'STOP')

    def test_13_all_saved_examples_exact(self):
        data=json.loads((PUBLIC/'interface-examples.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(data['status'],'synthetic_local_function_fixtures_only')
        for ex in data['examples']:
            with self.subTest(example=ex['name']):
                self.assertEqual(p.recommend(ex['request']),ex['actual_local_function_output'])
        RESULTS['examples_verified']=[e['name'] for e in data['examples']]

    def test_14_original_forward_support_not_reused_behind(self):
        # The original producer samples forward lobes only. Their values cannot
        # establish low directional risk in the opposite, unobserved hemisphere.
        r=held()
        r['pose']['orientation_xyzw']=[0,1,0,0]
        r['observation']['adc_pose']['orientation_xyzw']=[0,1,0,0]
        r['goal_m']=[0,0,-10]
        g=p.recommend(r)
        RESULTS['opposite_native_forward_probe']={k:g[k] for k in ('status','risk','uncertainty','direction_world','speed_limit_m_s')}
        RESULTS['opposite_native_forward_reproducer']={'request':r,'actual_output':g}
        self.assertEqual(g['map_cells'][0]['pose']['orientation_xyzw'],[0.,0.,0.,1.])
        self.assertEqual(g['status'],'STOP','Old forward lobes must not authorize low-risk advice behind their acquisition frame')

    def stopped_for_support(self,r):
        old=copy.deepcopy(r)
        g=p.recommend(r)
        self.assertEqual(g['status'],'STOP')
        self.assertEqual(g['reason'],'original_observation_pose_inapplicable')
        self.assertEqual(g['risk'],1);self.assertEqual(g['uncertainty'],1)
        self.assertEqual(g['direction_world'],[0,0,0]);self.assertEqual(g['speed_limit_m_s'],0)
        self.assertEqual(g['observation'],r['observation']);self.assertEqual(r,old)
        return g

    def yaw(self,degrees):
        return [0,math.sin(math.radians(degrees)/2),0,math.cos(math.radians(degrees)/2)]

    def test_15_yaw90_180_each_pose_field(self):
        records=[]
        for degrees in (-180,-90,90,180):
            for change_current,change_adc in ((True,False),(False,True),(True,True)):
                r=held()
                if change_current:r['pose']['orientation_xyzw']=self.yaw(degrees)
                if change_adc:r['observation']['adc_pose']['orientation_xyzw']=self.yaw(degrees)
                r['goal_m']=[10*math.sin(math.radians(degrees)),0,10*math.cos(math.radians(degrees))]
                g=self.stopped_for_support(r)
                records.append(dict(yaw=degrees,current=change_current,adc=change_adc,status=g['status']))
        RESULTS['yaw_rejections']=records

    def test_16_ten_metre_displacement_each_pose_field(self):
        records=[]
        for change_current,change_adc in ((True,False),(False,True),(True,True)):
            r=held()
            if change_current:r['pose']['position_m']=[10,0,0]
            if change_adc:r['observation']['adc_pose']['position_m']=[10,0,0]
            r['goal_m']=[10,0,10]
            g=self.stopped_for_support(r)
            self.assertEqual(g['map_cells'][0]['pose']['position_m'],[0,0,0])
            records.append(dict(request=r,actual_output=g))
        RESULTS['translation_reproducers']=records
        r=fixture();r['pose']['position_m']=[10,0,0];self.stopped_for_support(r)

    def test_17_position_boundary_and_pairwise_offsets(self):
        for displacement in (.249999999,.25):
            r=held();r['pose']['position_m']=[displacement,0,0]
            self.assertEqual(p.recommend(r)['status'],'ADVISE')
        for displacement in (math.nextafter(.25,math.inf),.250001):
            r=held();r['pose']['position_m']=[displacement,0,0];self.stopped_for_support(r)
        r=held();r['pose']['position_m']=[.125,0,0];r['observation']['adc_pose']['position_m']=[-.125,0,0]
        self.assertEqual(p.recommend(r)['status'],'ADVISE')
        r['pose']['position_m']=[.2,0,0];r['observation']['adc_pose']['position_m']=[-.2,0,0]
        self.stopped_for_support(r)
        # Native differs from both other fields; the retained origin must match it.
        r=held()
        for o in r['history']+[r['observation']]:o['em_pose']['position_m']=[10,0,0]
        r['history'][0]['adc_pose']['position_m']=[10,0,0]
        self.stopped_for_support(r)

    def test_18_fifteen_degree_inclusive_and_pairwise(self):
        records=[]
        for angle in (14.999999,15,15.000001):
            r=held();r['pose']['orientation_xyzw']=self.yaw(angle)
            r['observation']['adc_pose']['orientation_xyzw']=self.yaw(angle)
            g=p.recommend(r)
            expected='ADVISE' if angle<=15 else 'STOP'
            self.assertEqual(g['status'],expected)
            records.append(dict(angle=angle,status=g['status'],direction=g['direction_world']))
        r=held();r['pose']['orientation_xyzw']=self.yaw(7.5)
        r['observation']['adc_pose']['orientation_xyzw']=self.yaw(-7.5)
        self.assertEqual(p.recommend(r)['status'],'ADVISE')
        r['pose']['orientation_xyzw']=self.yaw(10);r['observation']['adc_pose']['orientation_xyzw']=self.yaw(-10)
        self.stopped_for_support(r)
        RESULTS['fifteen_degree_boundary']=records

    def test_19_thirty_degree_real_candidate_boundary(self):
        # A lateral primitive's native angle is yaw + atan(0.35). Drive goal
        # beyond it so that this exact primitive is preferred when eligible.
        base=30-math.degrees(math.atan(.35))
        records=[]
        for offset in (-.000001,0,.000001):
            r=held();q=self.yaw(base+offset)
            r['pose']['orientation_xyzw']=q;r['observation']['adc_pose']['orientation_xyzw']=copy.deepcopy(q)
            r['goal_m']=[10,0,10]
            g=p.recommend(r);self.assertEqual(g['status'],'ADVISE')
            v=g['direction_world'];angle=math.degrees(math.acos(max(-1,min(1,v[2]/math.sqrt(sum(x*x for x in v))))))
            self.assertLessEqual(angle,30+1e-8)
            if offset<=0:self.assertAlmostEqual(angle,30+offset,places=7)
            else:self.assertLess(angle,29)
            records.append(dict(offset_degrees=offset,direction=v,native_angle_degrees=angle))
        RESULTS['thirty_degree_boundary']=records

    def test_20_roll_small_displacement_and_quaternion_sign(self):
        for roll in (45,90,180,270):
            r=held((0,1.2,1.2,0))
            r['pose']['orientation_xyzw']=[0,0,math.sin(math.radians(roll)/2),math.cos(math.radians(roll)/2)]
            r['pose']['position_m']=[0,0,.2];r['observation']['adc_pose']['position_m']=[0,0,.1]
            g=p.recommend(r);self.assertEqual(g['status'],'ADVISE')
            self.assertGreater(g['direction_world'][0],0);self.assertGreater(g['direction_world'][1],0)
            r['pose']['orientation_xyzw']=[-v for v in r['pose']['orientation_xyzw']]
            self.assertEqual(p.recommend(r)['direction_world'],g['direction_world'])

    def test_21_native_world_frame_rotated_equivalence(self):
        r=held((0,1.2,1.2,0));base=p.recommend(r)
        q=self.yaw(65);theta=math.radians(65)
        r['pose']['orientation_xyzw']=q;r['goal_m']=[10*math.sin(theta),0,10*math.cos(theta)]
        for obs in r['history']+[r['observation']]:
            obs['adc_pose']['orientation_xyzw']=copy.deepcopy(q)
            obs['em_pose']['orientation_xyzw']=copy.deepcopy(q)
        g=p.recommend(r);self.assertEqual(g['status'],'ADVISE')
        x,y,z=base['direction_world']
        expected=[math.cos(theta)*x+math.sin(theta)*z,y,-math.sin(theta)*x+math.cos(theta)*z]
        for a,b in zip(g['direction_world'],expected):self.assertAlmostEqual(a,b,places=12)

if __name__=='__main__':
    run=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentChecks))
    RESULTS.update(tests_run=run.testsRun, failures=len(run.failures), errors=len(run.errors),
        candidate_sha256=hashlib.sha256((PUBLIC/'candidate_four_channel_planner_v1.py').read_bytes()).hexdigest(),
        evidence_scope='synthetic_local_function_only')
    print(json.dumps(RESULTS,sort_keys=True,indent=2))
    sys.exit(0 if run.wasSuccessful() else 1)

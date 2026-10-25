"""Phase2 selected independent black-box controls against phase1-frozen oracles."""
import dataclasses
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback
import types

node=Path(sys.argv[1])
root=node/'.local/deepeye-implementation-c'
out=Path(__file__).resolve().parent
oracle_path=out.parent/'phase1-oracles.json'
assert hashlib.sha256(oracle_path.read_bytes()).hexdigest()=='f7c59eff96eaaad2fad3506f9cf9b2777ca31d62c68d1436cd8d757004235ff9'
expected=json.loads(oracle_path.read_text(encoding='utf-8-sig'))
pins={
 'kinematics.py':'770f8b4e1ff1e626df385bf220f79a8f4be8a9e9cd05c8070cd0d0dc8c01561a',
 'trajectory_candidates.py':'ede34dfa38f093c7ba0858ca211b824e08268447846a0859b9a69cb4cb7a0c15',
 'swept_capsule.py':'765b83405a4773c2e4da4806d9d42bd39bc66bda6e78f0a4acf9e3d86eba5b4a',
}
folder=root/'competition/deepeye/ai_pc/planning'
package=types.ModuleType('independent_geometry_target')
package.__path__=[str(folder)]
sys.modules[package.__name__]=package
loaded={}
for name,pin in pins.items():
    path=folder/name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pin
    module_name=package.__name__+'.'+path.stem
    spec=importlib.util.spec_from_file_location(module_name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[module_name]=module
    spec.loader.exec_module(module)
    loaded[path.stem]=module
t=loaded['trajectory_candidates']; g=loaded['swept_capsule']
results=[]
def control(name,fn):
    try:
        detail=fn()
        results.append({'name':name,'passed':True,'detail':detail})
    except Exception as exc:
        traceback.print_exc()
        results.append({'name':name,'passed':False,'error_type':type(exc).__name__,'error':str(exc)})
def error(a,b): return max(abs(x-y) for x,y in zip(a,b))
def orientation_error(a,b):
    return min(error(a,b),error(a,tuple(-x for x in b)))
def forward(q):
    x,y,z,w=q
    return (2*(x*z+w*y),2*(y*z-w*x),1-2*(x*x+y*y))
I=(0.,0.,0.,1.)
definitions=[
 ('straight_steady',.25,20,0,0,200,(1.,2.,3.),I,'fast_9600'),
 ('straight_acceleration',0.,20,0,0,150,(0.,0.,0.),I,'fast_9600'),
 ('target_hit_inside_one_10ms_step',.249,20,0,0,1,(0.,0.,0.),I,'fast_9600'),
 ('straight_stop_and_hold',.25,0,0,0,150,(0.,0.,0.),I,'fast_9600'),
 ('combined_yaw3000_pitch4000',.25,20,3000,4000,200,(0.,0.,0.),I,'fast_9600'),
 ('yaw_negative_pitch_positive',.25,20,-3000,4000,200,(0.,0.,0.),I,'fast_9600'),
 ('yaw_positive_pitch_negative',.25,20,3000,-4000,200,(0.,0.,0.),I,'fast_9600'),
 ('combined_world_roll90',.25,20,3000,4000,200,(0.,0.,0.),(0.,0.,math.sqrt(.5),math.sqrt(.5)),'fast_9600'),
 ('combined_acceleration',0.,20,3000,4000,150,(0.,0.,0.),I,'fast_9600'),
 ('curved_deceleration_to_speed10',.25,10,1200,1600,100,(0.,0.,0.),I,'fast_9600'),
 ('stress_speed20_yaw30_pitch40',.002,20,30,40,100,(0.,0.,0.),I,'stress_300'),
]
def numeric_case(row):
    name,v0,code,yaw,pitch,ticks,p,q,profile=row
    candidate=t.Candidate('numeric',(t.Command(profile,code,yaw,pitch,ticks),))
    trajectory=t.rollout_candidate(t.Pose3(p,q),v0,candidate)
    assert trajectory.status=='completed' and trajectory.movement_authorized is False
    last=trajectory.samples[-1]; target=expected['numeric_cases'][name]
    pe=error(last.pose.position,target['p'])
    qe=orientation_error(last.pose.quaternion_xyzw,target['q_xyzw'])
    fe=error(forward(last.pose.quaternion_xyzw),target['forward'])
    se=abs(last.travelled_m-target['distance_m'])
    assert pe<=2e-9 and qe<=2e-9 and fe<=2e-9 and se<=2e-10,(pe,qe,fe,se)
    assert abs(last.speed_m_s-target['speed_m_s'])<=2e-12
    assert abs(last.time_s-ticks*.01)<=2e-12
    assert all(s.interval_rotation_rad<=math.pi/3600+1e-15 and s.interval_travel_m>=0 for s in trajectory.samples)
    return {'position_max_error_m':pe,'quaternion_max_error_mod_sign':qe,'forward_max_error':fe,'distance_error_m':se,'substeps':trajectory.substeps_used,'distance_m':last.travelled_m,'movement_authorized':trajectory.movement_authorized}
for row in definitions:
    control(row[0],lambda row=row:numeric_case(row))
def sequence_case():
    candidate=t.Candidate('sequence',(t.Command('fast_9600',20,5000,0,100),t.Command('fast_9600',20,0,5000,100)))
    result=t.rollout_candidate(t.Pose3((0.,0.,0.),I),.25,candidate)
    target=expected['numeric_cases']['two_primitive_non_coplanar']['second']
    last=result.samples[-1]
    pe=error(last.pose.position,target['p']);qe=orientation_error(last.pose.quaternion_xyzw,target['q_xyzw'])
    assert result.status=='completed' and pe<2e-9 and qe<2e-9
    return {'position_error_m':pe,'quaternion_error':qe,'phase1_four_point_determinant_m3':expected['numeric_cases']['two_primitive_non_coplanar']['four_point_signed_determinant_m3']}
control('two_primitive_non_coplanar',sequence_case)

pose=t.Pose3((10.,10.,10.),I)
still=t.Candidate('still',(t.Command('fast_9600',0,0,0,1),))
moving=t.Candidate('positive',(t.Command('fast_9600',20,3000,4000,20),))
cube=g.Box((0.,0.,0.),(30.,30.,30.))
free=g.Region('free','free',g.Box((5.,5.,5.),(15.,15.,15.)))
def fixture(*regions): return g.FixtureMap(cube,(free,)+tuple(regions))
def checked(candidate=moving,at=pose,speed=.25,map_=None,**kwargs):
    result=g.check_candidate(at,speed,candidate,fixture() if map_ is None else map_,**kwargs)
    assert result.movement_authorized is False
    return result
def positive():
    result=checked()
    assert result.status=='clear_for_supplied_fixture' and len(result.supports)>1
    return {'status':result.status,'supports':len(result.supports),'movement_authorized':False}
control('positive_nonempty_3D_fixture',positive)
def overlap(name,lower,upper,at=pose):
    region=g.Region(name,'occupied',g.Box(lower,upper))
    result=checked(candidate=still,at=at,speed=0.,map_=fixture(region))
    assert result.status=='conservative_occupied_overlap'
    return {'status':result.status,'blocking_interval':result.blocking_interval}
for name,lo,hi in (
 ('initial_overlap',(9.99,9.99,9.99),(10.01,10.01,10.01)),
 ('side_contact',(10.1199,9.9999,9.9999),(10.1201,10.0001,10.0001)),
 ('rear_body_contact',(10.099,9.999,9.619),(10.101,10.001,9.621)),
 ('true_surface_tangency',(10.12,9.99,9.99),(10.13,10.01,10.01)),
):
    control(name,lambda name=name,lo=lo,hi=hi:overlap(name,lo,hi))
def thin_tail():
    case=expected['thin_rotating_tail_between_10ms_endpoints']
    point=case['occupied_aabb_center'];half=case['occupied_aabb_half_width_m']
    obstacle=g.Region('phase1_thin_tail','occupied',g.Box(tuple(x-half for x in point),tuple(x+half for x in point)))
    candidate=t.Candidate('thin_tail',(t.Command('fast_9600',20,5000,0,1),))
    result=checked(candidate=candidate,map_=fixture(obstacle))
    assert result.status=='conservative_occupied_overlap'
    return {'status':result.status,'blocking_interval':result.blocking_interval,'independent_endpoint_box_clearance_lower_bounds_m':case['box_clearance_lower_bound_start_end_m'],'independent_midpoint_penetration_m':-case['point_minus_capsule_radius_start_mid_end_m'][1],'interpretation':'not false-clear; AABB may reject before the actual capsule contact; not a collision localization or numerical continuity proof'}
control('phase1_between_endpoints_thin_tail',thin_tail)
def unknown_controls():
    empty=checked(map_=g.FixtureMap(cube))
    explicit=g.Region('uncertain','unknown',g.Box((9.99,9.99,9.99),(10.01,10.01,10.01)))
    unknown=checked(map_=fixture(explicit))
    halves=g.FixtureMap(cube,(
        g.Region('left','free',g.Box((5.,5.,5.),(10.,15.,15.))),
        g.Region('right','free',g.Box((10.,5.,5.),(15.,15.,15.))),
    ))
    union=checked(map_=halves)
    assert empty.status=='unknown_missing_coverage' and unknown.status=='conservative_unknown_overlap' and union.status=='unknown_missing_coverage'
    return {'empty':empty.status,'explicit_unknown_with_free':unknown.status,'union_only':union.status}
control('unknown_coverage_and_priority',unknown_controls)
def boundary_control():
    result=checked(candidate=still,at=t.Pose3((.12,10.,10.),I),speed=0.)
    assert result.status=='conservative_boundary_overlap'
    return {'status':result.status}
control('closed_cube_tangency',boundary_control)
def monotonic():
    near=g.Region('near','occupied',g.Box((10.13,9.99,9.99),(10.14,10.01,10.01)))
    statuses=[]
    for uncertainty in (g.Uncertainty(),g.Uncertainty(initial_position_m=.02),g.Uncertainty(initial_orientation_rad=.02),g.Uncertainty(occupancy_inflation_m=.02)):
        statuses.append(checked(candidate=still,speed=0.,map_=fixture(near),uncertainty=uncertainty).status)
    assert statuses[0]=='clear_for_supplied_fixture' and all(x=='conservative_occupied_overlap' for x in statuses[1:])
    return statuses
control('uncertainty_and_occupancy_inflation',monotonic)
def budgets():
    rollout=t.rollout_candidate(pose,.25,moving,max_substeps=0)
    geometry=checked(max_geometry_checks=0)
    substeps=checked(max_substeps=0)
    batch=t.rollout_candidates(pose,.25,(still,moving),max_total_substeps=1)
    fan=t.generate_candidates(profile='fast_9600',speed_codes=[20],yaw_codes=[0,3000],pitch_codes=[0,4000],duration_ticks=1,max_candidates=1)
    assert rollout.status==geometry.status==substeps.status==batch.status==fan.status=='budget_exhausted'
    assert not rollout.samples and not geometry.supports and not substeps.supports and not batch.trajectories and not fan.candidates
    return {'all_status':'budget_exhausted','all_partial_outputs_empty':True}
control('explicit_budgets_no_partial_clear',budgets)
def types_and_aliases():
    rejects=0
    calls=[
      lambda:t.Pose3((True,10.,10.),I),
      lambda:t.Pose3((10.,10.,10.),(0.,0.,0.,.5)),
      lambda:t.Command('fast_9600',True,0,0,1),
      lambda:t.Command('fast_9600',20,15000,15000,1),
      lambda:g.Uncertainty(initial_position_m=float('nan')),
      lambda:g.FixtureMap(cube,(),source_domain='live'),
      lambda:checked(max_geometry_checks=True),
    ]
    for call in calls:
        try: call()
        except t.TrajectoryError: rejects+=1
        else: raise AssertionError('invalid finite/type/code/source input accepted')
    p=[10.,10.,10.];q=list(I);created=t.Pose3(p,q)
    regions=[free];map_=g.FixtureMap(cube,regions)
    p[0]=999.;q[3]=.5;regions.clear()
    assert created.position==(10.,10.,10.) and created.quaternion_xyzw==I and len(map_.regions)==1
    first=checked(map_=map_);again=checked(map_=map_)
    assert first==again
    return {'invalid_inputs_rejected':rejects,'mutable_aliases_detached':True,'repeat_result_identical':True}
control('strict_types_aliases_determinism',types_and_aliases)

output={'work_id':'C-3D-TRAJECTORY-INDEPENDENT-REVIEW-20261025-v1','phase':2,
 'source_pins':pins,'phase1_oracle_sha256':'f7c59eff96eaaad2fad3506f9cf9b2777ca31d62c68d1436cd8d757004235ff9',
 'controls':results,'passed':all(r['passed'] for r in results),
 'product_source_modified':False,'author_suite_repeated':False,'CPU_training_inference_heldout_executed':False,
 'authority':'software_fixture only; movement_authorized remains false; no gate/runtime/product acceptance'}
print(json.dumps(output,indent=2,allow_nan=False))
raise SystemExit(0 if output['passed'] else 1)


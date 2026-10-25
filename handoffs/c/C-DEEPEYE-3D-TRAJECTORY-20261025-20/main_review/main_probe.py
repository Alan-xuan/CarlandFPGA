"""Bounded root controls against independently frozen high-precision results."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True, type=Path)
ap.add_argument('--controls', required=True, type=Path)
args = ap.parse_args()
root = args.root.resolve()
pins = {
    'competition/deepeye/ai_pc/planning/trajectory_candidates.py': 'ede34dfa38f093c7ba0858ca211b824e08268447846a0859b9a69cb4cb7a0c15',
    'competition/deepeye/ai_pc/planning/swept_capsule.py': '765b83405a4773c2e4da4806d9d42bd39bc66bda6e78f0a4acf9e3d86eba5b4a',
    'competition/deepeye/ai_pc/planning/kinematics.py': '770f8b4e1ff1e626df385bf220f79a8f4be8a9e9cd05c8070cd0d0dc8c01561a',
}
for path, pin in pins.items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest() == pin, path
assert hashlib.sha256(args.controls.read_bytes()).hexdigest() == '0eee01da3b7082aa9926621a24ed47df919350310cdca83a168d270326195ecf'
sys.path.insert(0, str(root/'competition/deepeye'))
from ai_pc.planning.trajectory_candidates import Pose3, Command, Candidate, TrajectoryError, rollout_candidate
from ai_pc.planning.swept_capsule import Box, Region, FixtureMap, Uncertainty, check_candidate

controls = json.loads(args.controls.read_bytes())['cases']
cube = Box((-15,-15,-15),(15,15,15))
free = Region('free', 'free', Box((-14,-14,-14),(14,14,14)))
known = FixtureMap(cube, (free,))
rows = []
for item in controls:
    x = item['input']
    pose = Pose3(tuple(map(float,x['position'])), tuple(map(float,x['orientation_xyzw'])))
    commands = tuple(Command(x['profile'], c['speed_code'], c['yaw_q'], c['pitch_q'], c['duration_ticks']) for c in x['commands'])
    candidate = Candidate(item['name'], commands)
    result = rollout_candidate(pose, float(x['speed']), candidate)
    assert result.status == 'completed' and result.movement_authorized is False
    final = result.samples[-1]
    expected = item['expected']
    p_error = max(abs(a-float(b)) for a,b in zip(final.pose.position,expected['position']))
    eq = tuple(map(float,expected['orientation_xyzw']))
    q_error = min(max(abs(a-sign*b) for a,b in zip(final.pose.quaternion_xyzw,eq)) for sign in (-1,1))
    s_error = abs(final.travelled_m-float(expected['travelled_length']))
    v_error = abs(final.speed_m_s-float(expected['speed']))
    assert p_error < 1e-10 and q_error < 1e-10 and s_error < 1e-10 and v_error < 1e-12, item['name']
    assert all(s.interval_rotation_rad <= math.pi/3600+1e-15 for s in result.samples)
    swept = check_candidate(pose, float(x['speed']), candidate, known)
    assert swept.status == 'clear_for_supplied_fixture' and swept.movement_authorized is False
    rows.append({'name':item['name'],'position_error_m':p_error,'quaternion_error':q_error,
                 'travel_error_m':s_error,'speed_error_m_s':v_error,'substeps':result.substeps_used})

pose = Pose3((0,0,0),(0,0,0,1))
command = Command('fast_9600',20,0,0,1)
candidate = Candidate('probe', (command,))
checks = []
def status(name, fixture, expected, **kwargs):
    r = check_candidate(pose,.25,candidate,fixture,**kwargs)
    assert r.status == expected, (name,r.status,expected)
    assert r.movement_authorized is False
    if expected == 'budget_exhausted':
        assert r.supports == ()
    checks.append({'name':name,'status':r.status})

status('no_free_default', FixtureMap(cube), 'unknown_missing_coverage')
status('rollout_budget', known, 'budget_exhausted', max_substeps=0)
status('geometry_budget', known, 'budget_exhausted', max_geometry_checks=0)
unknown = Region('unknown','unknown',Box((-.01,-.01,-.01),(.01,.01,.01)))
status('unknown_overrides_free', FixtureMap(cube,(free,unknown)), 'conservative_unknown_overlap')
side = Region('side','occupied',Box((.119,-.01,-.01),(.12,.01,.01)))
status('full_body_side',FixtureMap(cube,(free,side)),'conservative_occupied_overlap')
far = Region('near','occupied',Box((.14,-.01,-.1),(.16,.01,.1)))
status('base_clear',FixtureMap(cube,(free,far)),'clear_for_supplied_fixture')
status('position_uncertainty_rejects',FixtureMap(cube,(free,far)),
       'conservative_occupied_overlap',uncertainty=Uncertainty(initial_position_m=.03))
status('occupancy_inflation_rejects',FixtureMap(cube,(free,far)),
       'conservative_occupied_overlap',uncertainty=Uncertainty(occupancy_inflation_m=.03))

rejected = []
for name, fn in [
    ('real_source_label',lambda:Candidate('reject',(command,),source_domain='twin_fixture')),
    ('map_real_label',lambda:FixtureMap(cube,(),source_domain='geo_replay')),
    ('oversized_orientation_error',lambda:Uncertainty(initial_orientation_rad=math.pi+1e-6)),
    ('bool_position',lambda:Pose3((True,0,0),(0,0,0,1))),
    ('nan_position',lambda:Pose3((float('nan'),0,0),(0,0,0,1))),
    ('nonunit_quaternion',lambda:Pose3((0,0,0),(0,0,0,2))),
    ('mixed_profile',lambda:Candidate('reject',(command,Command('stress_300',20,0,0,1)))),
    ('constructor_permission',lambda:Candidate('reject',(command,),movement_authorized=True)),
]:
    try:
        fn()
    except (TrajectoryError,TypeError):
        rejected.append(name)
    else:
        raise AssertionError('must reject '+name)
position = [0,0,0]
attitude = [0,0,0,1]
commands = [command]
aliased_pose=Pose3(position,attitude)
aliased_candidate=Candidate('alias',commands)
before=rollout_candidate(aliased_pose,.25,aliased_candidate)
position[0]=99; attitude[3]=0; commands[0]=None
after=rollout_candidate(aliased_pose,.25,aliased_candidate)
assert before==after
print(json.dumps({'passed':True,'python':sys.version,'analytic_controls':rows,
    'fixture_checks':checks,'invalid_inputs_rejected':rejected,'mutable_input_alias_control':True,
    'source_pins':pins,'source_unchanged':True,'old_author_or_model_suites_repeated':False,
    'formal_acceptance_promoted':False},sort_keys=True))

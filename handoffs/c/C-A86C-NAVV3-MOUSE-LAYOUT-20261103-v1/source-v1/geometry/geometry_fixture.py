"""NEW standalone CPU geometry fixture; stdlib only, no product import or route.
Narrow checks on this axis-aligned parameter artifact, not an engine validator.
"""
import ast,copy,hashlib,json,math,pathlib
from fractions import Fraction as F
D=pathlib.Path(__file__).resolve().parent
W=D.parent
S=W/'main/A-e470-source'
R=W.parents[2]
LOCK='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(n,x):(D/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def canon(x):
    # Our fixture uses only integral geometry; canonical normalized float text
    # therefore equals its integer text under LayoutCodec String.num(...,6).
    if type(x) is dict:return '{'+','.join(json.dumps(k)+':'+canon(x[k]) for k in sorted(x))+'}'
    if type(x) is list:return '['+','.join(map(canon,x))+']'
    if type(x) is str:return json.dumps(x,ensure_ascii=False)
    if type(x) in (int,float) and math.isfinite(x) and x==int(x):return str(int(x))
    raise ValueError('fixture canonical domain only; not generic Godot emulation')
paths=['simulation/authority/navigation_session_profile.py','simulation/authority/g05_csr_projection_v1.py',
       'simulation/authority/world_initial_pose.py','simulation/authority/_world_values.py',
       'simulation/authority/_owned_godot.py','simulation/authority/motion/gate_geometry.py',
       'simulation/authority/motion/gate_clearance.py','simulation/authority/motion/workspace_boundaries.py',
       'simulation/authority/motion/passage_phase.py','simulation/authority/motion/kinematics.py',
       'simulation/authority/motion/demo_motion_profile.py','integration/motion.py',
       'simulator/editor/layout_codec.gd','simulator/editor/layout_store.gd',
       'simulator/editor/scene_document.gd','simulator/viewer/main.gd',
       'simulator/runtime/owned_world_start.gd','simulator/runtime/world_motion_bridge.gd',
       'tools/run_causal_functional_chain.py']
index=json.loads((W/'main/A-e470-verified-inputs.json').read_bytes())
allpins={e['path']:e for e in index['files']}
pins=[]
for rel in paths:
    name='competition/deepeye/'+rel;b=(S/name).read_bytes();p=allpins[name]
    assert (len(b),sha(b),hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest())==(p['bytes'],p['sha256'],p['git_blob'])
    pins.append(p)
scope=json.loads((R/'.local/plan-20261014-final-c/immutable-f5989cd/immutable_scope.json').read_bytes())
req=json.dumps(scope['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
assert sha(req)==LOCK and [e['id'] for e in scope['requirements']]==['H%02d'%i for i in range(1,16)]
# Parse literal constants without executing original module/function/class.
tree=ast.parse((S/'competition/deepeye/simulation/authority/navigation_session_profile.py').read_bytes())
const={}
for n in tree.body:
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name):
        key=n.targets[0].id
        if key=='_SOURCE_PINS':const[key]=ast.literal_eval(n.value)
        if key=='_VALUES':const[key]=tuple(const[e.id] if isinstance(e,ast.Name) else ast.literal_eval(e) for e in n.value.elts)
nav_sha=sha(json.dumps(('DEEPEYE-TYPED-NAVIGATION-PROFILE-V3',*const['_VALUES']),separators=(',',':')).encode('ascii'))
assert nav_sha=='5a3679f80be3668aaa1765ecdb157776f38c661ce1bb9d40d5dac8b447967d17'
fields=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NavigationSessionProfile')
names=[n.target.id for n in fields.body if isinstance(n,ast.AnnAssign) and n.target.id!='sha256']
dump('source-pins.json',dict(source_commit=index['source_commit'],files=pins,requirements_sha256=sha(req),requirements_bytes=len(req),nav_logical_sha256=nav_sha,nav_values=dict(zip(names,const['_VALUES'])),note='File SHA and profile logical SHA are distinct; AST literal read only; not original module execution.'))
def vec(x,y,z):return dict(x=x,y=y,z=z)
layout=dict(obstacles=[dict(object_id=1,kind='water',position=vec(8,9,0),rotation_deg=vec(0,0,0),size=vec(3,2,1),priority=2),dict(object_id=2,kind='hard_rock',position=vec(10,10,0),rotation_deg=vec(0,0,0),size=vec(1,1,1),priority=1)],gates=dict(entry=dict(face='top',u=12,v=0),exit=dict(face='right',u=0,v=12)))
packed=dict(schema=1,contract='DEEPEYE-HUMAN-LOCK-20261014/revision1',requirements_sha256=LOCK,units='m',layout=layout,layout_hash=sha(canon(layout).encode()))
dump('layout-software-fixture.json',packed)
# Test reads actual saved bytes; no product codec was imported or run.
raw=(D/'layout-software-fixture.json').read_bytes();p=json.loads(raw);l=p['layout']
ASSUMED=F(1,1000)
H=F(.4);BODY_R=F(.12);GATE_R=F(.15);GUARD=F(1,10**12)
def center(g):
    return (F(g['u']),F(15),F(g['v'])) if g['face']=='top' else (F(15),F(g['v']),F(g['u']))
def gate_valid(g):
    return g['face'] in ('top','right') and all(abs(F(g[k]))+GATE_R<=15 for k in ('u','v'))
def box(o):
    assert all(v==0 for v in o['rotation_deg'].values())
    return tuple((F(o['position'][k])-F(o['size'][k])/2,F(o['position'][k])+F(o['size'][k])/2) for k in ('x','y','z'))
def separated(a,b,margin):return any(x[1]+margin<y[0] or y[1]+margin<x[0] for x,y in zip(a,b))
def corridor(g):
    # AABB enclosing the original one-metre inward, .15-radius cylinder.
    c=center(g);axis=1 if g['face']=='top' else 0
    return tuple((q-1,q) if i==axis else (q-GATE_R,q+GATE_R) for i,q in enumerate(c))
def capsule_box(pos,axis,inflation):
    return tuple((F(q)-(H if i==axis else 0)-BODY_R-inflation,F(q)+(H if i==axis else 0)+BODY_R+inflation) for i,q in enumerate(pos))
def entire_outside(pos,axis,budget):return F(pos[axis])-15-H-BODY_R-budget>GUARD
def goal(g,numeric,asset):
    c=center(g);axis=1 if g['face']=='top' else 0
    result=list(map(float,c));result[axis]=math.nextafter(float(c[axis]+H+BODY_R+numeric+asset+F(.05)),math.inf)
    return result
checks=[]
def check(name,value):
    ok=value is True;checks.append(dict(name=name,passed=ok));assert ok,name
check('actual_bytes_exact_fields_and_layout_hash',set(p)=={'schema','contract','requirements_sha256','units','layout','layout_hash'} and p['layout_hash']==sha(canon(l).encode()))
check('integral_fixture_canonical_roundtrip',canon(l)==canon(json.loads(canon(l))))
check('positive_adjacent_gate_coordinates',all(gate_valid(g) for g in l['gates'].values()) and l['gates']['entry']['face']!=l['gates']['exit']['face'])
check('positive_edge_limit',gate_valid(dict(face='top',u=14.85,v=0)))
check('negative_next_float_beyond_edge',not gate_valid(dict(face='top',u=math.nextafter(14.85,math.inf),v=0)))
check('obstacle_nominal_boxes_inside_workspace',all(all(-15<a<b<15 for a,b in box(o)) for o in l['obstacles']))
check('water_and_rock_exact_kind_size_priority',l['obstacles'][0]['kind']=='water' and l['obstacles'][0]['size']==vec(3,2,1) and l['obstacles'][0]['priority']==2 and l['obstacles'][1]['kind']=='hard_rock' and l['obstacles'][1]['size']==vec(1,1,1) and l['obstacles'][1]['priority']==1)
check('positive_inner_corridor_AABB_sufficient_separation',all(separated(corridor(g),box(o),3*ASSUMED) for g in l['gates'].values() for o in l['obstacles']))
bad=copy.deepcopy(l['obstacles'][1]);bad['position']=vec(12,14,0)
check('negative_obstacle_intersecting_blue_inner_corridor',not separated(corridor(l['gates']['entry']),box(bad),3*ASSUMED))
start=[12,15.6,0];start_box=capsule_box(start,1,3*ASSUMED)
check('positive_initial_full_outside_other_five_inside',entire_outside(start,1,3*ASSUMED) and all(-15<start_box[i][0] and start_box[i][1]<15 for i in (0,2)) and start_box[1][0]>-15)
check('positive_initial_body_box_obstacle_separation',all(separated(start_box,box(o),0) for o in l['obstacles']))
check('negative_standoff_smaller_than_full_support',not entire_outside([12,15.5,0],1,3*ASSUMED))
check('positive_axis_aligned_gate_section_with_assumed_budget',BODY_R+3*ASSUMED+GUARD<GATE_R)
check('negative_gate_radial_tangency',not (BODY_R+(GATE_R-BODY_R)+GUARD<GATE_R))
g=goal(l['gates']['exit'],ASSUMED,ASSUMED)
check('positive_full_support_external_goal',entire_outside(g,0,2*ASSUMED) and F(g[0])-15-H-BODY_R-2*ASSUMED>F(.05))
check('negative_red_center_plus_point05_only',not entire_outside([15.05,12,0],0,2*ASSUMED))
check('negative_center_on_red_plane_is_not_full_exit',not entire_outside([15,12,0],0,2*ASSUMED))
check('negative_point_target_cannot_establish_aperture_history',entire_outside([g[0],14,0],0,2*ASSUMED) and F(2)+BODY_R>GATE_R)
summary=dict(software_fixture=True,not_mouse_authored=True,engine_codec_run=False,source_commit=index['source_commit'],layout_sha256=sha(raw),layout_hash=p['layout_hash'],nav_logical_sha256=nav_sha,checks=checks,passed=len(checks),failed=0,static_geometry_only=True,online_reachability=False,route_generated=False,actual_actor_decisions=0,board_operations=0,formal_acceptance=False)
dump('geometry-results.json',summary)
dump('parameters.json',dict(software_fixture=True,not_mouse_authored=True,layout_input_scope='Simulator/Root private layout only; never controller observations or AI map',blue_center_m=list(map(float,center(l['gates']['entry']))),red_center_m=list(map(float,center(l['gates']['exit']))),gate_radius_m=.15,gate_diameter_m=.30,drill_half_segment_m=.4,drill_radius_m=.12,drill_diameter_m=.24,drill_total_envelope_length_m=1.04,initial_standoff_m=.6,initial_position_m=start,initial_body_axis=[0,-1,0],external_goal_formula='red_center+outward*(half_segment+radius+ACTUAL_numeric+ACTUAL_asset+0.05), component nextafter outward',synthetic_budget_example=dict(numeric_m=.001,asset_m=.001,obstacle_m=.001,note='CPU boundary assumptions only, not measured or selected production policy',external_goal_m=g),required_original_facts=['Original snapshot-derived numeric/asset/obstacle errors and positive getter cap','Original full mesh containment, corridor certification and initial passage witness','Actual original motion/observation/AI/command/CAS/final fences and ordered full-volume passage history'],short_scene_note='3m from shared edge; static scale suggestion, not shortest-route proof',nav_max_commands=16,nav_max_scans=16,nav_max_public_items=24,required_fresh_decisions='each must be actual original pipeline decision; profile limit and this fixture do not execute any'))
print(json.dumps(summary,ensure_ascii=False,indent=2))

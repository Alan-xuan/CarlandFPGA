"""Phase1 independent closed-form oracles; stdlib only, never imports product code."""
import hashlib
import json
import math
from pathlib import Path
import sys

node=Path(sys.argv[1])
tree=node/'.local/deepeye-implementation-c'
expected={
 'competition/deepeye/ai_pc/planning/kinematics.py':'770f8b4e1ff1e626df385bf220f79a8f4be8a9e9cd05c8070cd0d0dc8c01561a',
 'docs/competition/deepeye-2026/taskbook_final.md':'7f5c94f7fc73698236be954ae7818266d6dfe8b4949d1752dd045d76f4b71f18',
}
pins={}
for path,pin in expected.items():
    actual=hashlib.sha256((tree/path).read_bytes()).hexdigest()
    assert actual==pin
    pins[path]=actual
scope=json.loads((tree/'docs/competition/deepeye-2026/immutable_scope.json').read_text(encoding='utf-8-sig'))
scope_sha=hashlib.sha256(json.dumps(scope['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert scope_sha=='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
assert {r['id'] for r in scope['requirements']}=={'H%02d'%i for i in range(1,16)}

def add(a,b): return tuple(x+y for x,y in zip(a,b))
def mul(s,a): return tuple(s*x for x in a)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def norm(a): return math.sqrt(dot(a,a))
def qmul(a,b):
    x,y,z,w=a; X,Y,Z,W=b
    return (w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z)
def rotate(q,v):
    r=qmul(qmul(q,(*v,0.0)),(-q[0],-q[1],-q[2],q[3]))
    return r[:3]
def distance(v0,vt,T):
    acceleration=.25
    tau=min(T,abs(vt-v0)/acceleration)
    sign=0 if vt==v0 else (1 if vt>v0 else -1)
    length=v0*tau+sign*.5*acceleration*tau*tau+vt*(T-tau)
    velocity=vt if tau<T else v0+sign*acceleration*tau
    return length,velocity
def sample(v0,vt,yaw,pitch,T,p=(0.,0.,0.),q=(0.,0.,0.,1.)):
    assert vt>0 or yaw==pitch==0
    assert yaw*yaw+pitch*pitch<=math.floor((vt*180000/(2*math.pi))**2)
    s,v=distance(v0,vt,T)
    ky=yaw*math.pi/(180000*vt) if vt else 0.
    kp=pitch*math.pi/(180000*vt) if vt else 0.
    K=math.hypot(ky,kp)
    if K:
        angle=K*s
        local=(ky/(K*K)*(1-math.cos(angle)),kp/(K*K)*(1-math.cos(angle)),math.sin(angle)/K)
        half=math.sin(angle/2)/K
        dq=(-kp*half,ky*half,0.,math.cos(angle/2))
    else:
        angle=0.;local=(0.,0.,s);dq=(0.,0.,0.,1.)
    finalq=qmul(q,dq)
    return {'p':add(p,rotate(q,local)),'q_xyzw':finalq,'forward':rotate(finalq,(0.,0.,1.)),
            'distance_m':s,'speed_m_s':v,'angle_rad':angle,'curvature_rad_per_m':K}
cases={
 'straight_steady':sample(.25,.25,0,0,2.,(1.,2.,3.)),
 'straight_acceleration':sample(0.,.25,0,0,1.5),
 'target_hit_inside_one_10ms_step':sample(.249,.25,0,0,.01),
 'straight_stop_and_hold':sample(.25,0.,0,0,1.5),
 'combined_yaw3000_pitch4000':sample(.25,.25,3000,4000,2.),
 'yaw_negative_pitch_positive':sample(.25,.25,-3000,4000,2.),
 'yaw_positive_pitch_negative':sample(.25,.25,3000,-4000,2.),
 'combined_world_roll90':sample(.25,.25,3000,4000,2.,q=(0.,0.,math.sqrt(.5),math.sqrt(.5))),
 'combined_acceleration':sample(0.,.25,3000,4000,1.5),
 'curved_deceleration_to_speed10':sample(.25,.125,1200,1600,1.),
 'stress_speed20_yaw30_pitch40':sample(.002,.002,30,40,1.),
}
assert abs(cases['straight_acceleration']['distance_m']-.25)<1e-15
assert abs(cases['target_hit_inside_one_10ms_step']['distance_m']-.002498)<1e-15
assert abs(cases['straight_stop_and_hold']['distance_m']-.125)<1e-15
assert abs(cases['curved_deceleration_to_speed10']['distance_m']-.15625)<1e-15
assert abs(cases['combined_yaw3000_pitch4000']['angle_rad']-math.pi/18)<1e-15
first=sample(.25,.25,5000,0,1.)
firstmid=sample(.25,.25,5000,0,.5)
second=sample(.25,.25,0,5000,1.,first['p'],first['q_xyzw'])
a,b,c=firstmid['p'],first['p'],second['p']
cross=(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
det=dot(cross,c)
assert abs(det)>1e-8
cases['two_primitive_non_coplanar']={'first':first,'second':second,'four_point_signed_determinant_m3':det}

# A valid 10ms positive-speed yaw arc. The tiny obstacle intersects only mid-sweep.
start=sample(.25,.25,5000,0,0.,(10.,10.,10.))
middle=sample(.25,.25,5000,0,.005,(10.,10.,10.))
end=sample(.25,.25,5000,0,.01,(10.,10.,10.))
R=1/middle['curvature_rad_per_m']
center=(10.+R,10.,10.)
tail=add(middle['p'],mul(-.4,middle['forward']))
radial=add(tail,mul(-1.,center))
radial=mul(1/norm(radial),radial)
point=add(tail,mul(.12-1e-6,radial))
def segment_distance(point,pose):
    low=add(pose['p'],mul(-.4,pose['forward']))
    high=add(pose['p'],mul(.4,pose['forward']))
    axis=add(high,mul(-1,low))
    t=max(0.,min(1.,dot(add(point,mul(-1,low)),axis)/dot(axis,axis)))
    return norm(add(point,mul(-1,add(low,mul(t,axis)))))
gaps=[segment_distance(point,pose)-.12 for pose in (start,middle,end)]
half=2e-7
assert gaps[0]>math.sqrt(3)*half and gaps[2]>math.sqrt(3)*half and gaps[1]<0
tail_case={'initial':start,'middle':middle,'end':end,'occupied_aabb_center':point,'occupied_aabb_half_width_m':half,
 'point_minus_capsule_radius_start_mid_end_m':gaps,'box_clearance_lower_bound_start_end_m':[gaps[0]-math.sqrt(3)*half,gaps[2]-math.sqrt(3)*half],
 'expected':'reject/not-clear: occupied mid-sweep even though both endpoint capsules are disjoint from the entire tiny box',
 'full_pose_angular_change_deg':end['angle_rad']*180/math.pi}
print(json.dumps({'work_id':'C-3D-TRAJECTORY-INDEPENDENT-REVIEW-20261025-v1','phase':1,'sources_sha256':pins,
 'requirements_sha256':scope_sha,'author_source_read':False,'author_tests_executed':False,
 'numeric_cases':cases,'thin_rotating_tail_between_10ms_endpoints':tail_case,
 'bounds_example':{'rotation_displacement_0_05deg_m':2*.52*math.sin(math.radians(.05)/2),
 'rotational_baseline_m':.0005,'general_path_length_half_bound_for_2_5mm_m':.0025/2,
 'circle_sagitta_for_same_arc_m':R*(1-math.cos(end['angle_rad']/2))},
 'acceptance_limits':'software_fixture geometry preparation only; no gates, learned model, sim_em, runtime, motion authority, board or C02/C03 formal acceptance'},indent=2,allow_nan=False))


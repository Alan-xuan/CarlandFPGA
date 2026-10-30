"""C46 finite public mechanics; no origin authentication, IO or planner."""
import json,math
from fractions import Fraction

UINT63=(1<<63)-1
BASIS='host_dispatch_to_complete_result_observed_v1'
def need(ok,reason):
    if not ok:raise ValueError(reason)
def uint(x,lo=0):
    need(type(x) is int and lo<=x<=UINT63,'strict uint63 required');return x
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def pair_state(raw):
    """PARTIAL or COMPLETE only; malformed/trailing/oversize is terminal."""
    need(type(raw) is bytes and len(raw)<=18440,'pair budget')
    at=0
    for limit in (2048,16384):
        if len(raw)-at<4:return 'PARTIAL'
        n=int.from_bytes(raw[at:at+4],'little');need(1<=n<=limit,'pair frame budget')
        if len(raw)<at+4+n:return 'PARTIAL'
        at+=4+n
    need(at==len(raw),'unsolicited trailing bytes')
    return 'COMPLETE'

def _body_direction(q,v):
    # Inverse of body-to-world unit xyzw; frozen kinematics uses body +Z forward.
    x,y,z,w=(-q[0],-q[1],-q[2],q[3]);a,b,c=v
    tx,ty,tz=2*(y*c-z*b),2*(z*a-x*c),2*(x*b-y*a)
    return (a+w*tx+y*tz-z*ty,b+w*ty+z*tx-x*tz,c+w*tz+x*ty-y*tx)

def quantize_target(advice,public,profile,duration_ms,motion):
    """Explicit fixed-duration candidate, not authority or a trajectory oracle.

    Angular error is pursued over that duration then clipped to the original
    combined curvature ROM. Truncation is toward zero, never a larger speed.
    Saturation/quantization can leave heading error; no accuracy claim is made.
    """
    uint(duration_ms,1);need(duration_ms<=100,'prospective duration1..100ms required')
    stop=dict(action=0,yaw_q=0,pitch_q=0,speed_code=0,duration_ms=0)
    if advice['status']=='STOP':return stop
    need(advice['status']=='ADVISE','unsupported result status')
    limit=advice['speed_limit_m_s'];need(type(limit) in (int,float) and math.isfinite(limit) and limit>=0,'speed bound')
    step=Fraction(motion.SPEED_STEP[profile]);code=min(20,int(Fraction(limit)//step))
    if code==0:return stop
    x,y,z=_body_direction(public['pose']['orientation_xyzw'],advice['direction_world'])
    need(all(math.isfinite(t) for t in (x,y,z)) and z>0,'forward body direction required')
    # Positive yaw steers +X; positive pitch steers +Y (body rotation -pitch,+yaw,0).
    yaw=math.degrees(math.atan2(x,z))*1_000_000/duration_ms
    pitch=math.degrees(math.atan2(y,math.hypot(x,z)))*1_000_000/duration_ms
    n=math.hypot(yaw,pitch);rom=motion.curvature_limit_squared(profile,code)
    cap=min(15000,math.sqrt(rom))
    factor=1 if n<=cap or n==0 else cap/n
    yq,pq=math.trunc(yaw*factor),math.trunc(pitch*factor)
    # Floating clipping must never escape the exact original integer ROM.
    while yq*yq+pq*pq>rom:
        if abs(yq)>=abs(pq):yq-=1 if yq>0 else -1
        else:pq-=1 if pq>0 else -1
    motion.validate(profile,code,yq,pq)
    need(Fraction(motion.SPEED_STEP[profile])*code<=Fraction(limit),'upward speed quantization')
    return dict(action=1,yaw_q=yq,pitch_q=pq,speed_code=code,duration_ms=duration_ms)

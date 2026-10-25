"""High-precision frozen mathematical controls; no author/product imports."""
from decimal import Decimal as D, getcontext
from pathlib import Path
import hashlib
import json

getcontext().prec = 80
PI = D('3.14159265358979323846264338327950288419716939937510582097494459230781640628620899')
A = D('0.25')
OUT = Path(__file__).resolve().parent

def sin(x):
    term = x
    total = x
    for n in range(1, 100):
        term *= -x*x / D((2*n)*(2*n+1))
        total += term
        if abs(term) < D('1e-76'):
            return total
    raise AssertionError('sin convergence')

def cos(x):
    term = D(1)
    total = term
    for n in range(1, 100):
        term *= -x*x / D((2*n-1)*(2*n))
        total += term
        if abs(term) < D('1e-76'):
            return total
    raise AssertionError('cos convergence')

def multiply(a, b):
    x,y,z,w = a
    i,j,k,h = b
    return (w*i+x*h+y*k-z*j, w*j-x*k+y*h+z*i,
            w*k+x*j-y*i+z*h, w*h-x*i-y*j-z*k)

def transform(q, p):
    x,y,z,w=q
    a,b,c=p
    return ((1-2*(y*y+z*z))*a+2*(x*y-z*w)*b+2*(x*z+y*w)*c,
            2*(x*y+z*w)*a+(1-2*(x*x+z*z))*b+2*(y*z-x*w)*c,
            2*(x*z-y*w)*a+2*(y*z+x*w)*b+(1-2*(x*x+y*y))*c)

def command(position, q, speed, profile, codes, ticks):
    code,yaw,pitch = codes
    target=D(code)*({'fast_9600':D('.0125'),'stress_300':D('.0001')}[profile])
    time=D(ticks)/100
    if speed==target:
        length=speed*time
        final_speed=target
    else:
        sign=D(1) if target>speed else D(-1)
        ramp=min(time, abs(target-speed)/A)
        length=speed*ramp+sign*A*ramp*ramp/2+target*(time-ramp)
        final_speed=speed+sign*A*ramp
    if code==0:
        ky=kp=D(0)
    else:
        ky=D(yaw)*PI/(180000*target)
        kp=D(pitch)*PI/(180000*target)
    k=(ky*ky+kp*kp).sqrt()
    if k==0:
        body=(D(0),D(0),length)
        increment=(D(0),D(0),D(0),D(1))
    else:
        angle=k*length
        side=(1-cos(angle))/k
        body=(ky/k*side,kp/k*side,sin(angle)/k)
        increment=(-kp/k*sin(angle/2),ky/k*sin(angle/2),D(0),cos(angle/2))
    delta=transform(q, body)
    return tuple(a+b for a,b in zip(position,delta)),multiply(q,increment),final_speed,length

R=D(1)/D(2).sqrt()
identity=(D(0),D(0),D(0),D(1))
cases=[
    ('straight_accelerate', 'fast_9600', (0,0,0), identity, '0', [((20,0,0),200)]),
    ('yaw_arc', 'fast_9600', (0,0,0), identity, '.25', [((20,6000,0),200)]),
    ('negative_pitch_arc', 'fast_9600', (0,0,0), identity, '.25', [((20,0,-6000),100)]),
    ('combined_global_rotation', 'fast_9600', (1,2,3), (D(0),R,D(0),R), '.25', [((20,3000,4000),100)]),
    ('noncoplanar_sequence', 'fast_9600', (0,0,0), identity, '.25', [((20,6000,0),100),((20,0,6000),100)]),
    ('ramp_turn', 'fast_9600', (0,0,0), identity, '0', [((20,6000,0),50)]),
    ('brake_to_stop', 'fast_9600', (0,0,0), identity, '.25', [((0,0,0),200)]),
    ('zero_stays_zero', 'fast_9600', (1,2,3), (D(0),R,D(0),R), '0', [((0,0,0),100)]),
    ('stress_combined', 'stress_300', (0,0,0), identity, '.002', [((20,50,20),800)]),
]
records=[]
for name,profile,p0,q0,s0,commands in cases:
    p=tuple(D(v) for v in p0)
    q=q0
    speed=D(s0)
    total=D(0)
    for codes,ticks in commands:
        p,q,speed,length=command(p,q,speed,profile,codes,ticks)
        total+=length
    assert abs(sum(v*v for v in q)-1)<D('1e-72')
    records.append({'name':name,'input':{'profile':profile,'position':[str(v) for v in p0],
        'orientation_xyzw':[str(v) for v in q0],'speed':s0,
        'commands':[{'speed_code':c[0],'yaw_q':c[1],'pitch_q':c[2],'duration_ticks':t} for c,t in commands]},
        'expected':{'position':[str(v) for v in p],'orientation_xyzw':[str(v) for v in q],
                    'speed':str(speed),'travelled_length':str(total)},
        'future_float_tolerance':{'position_abs_m':1e-10,'orientation_component_abs':1e-10,'speed_abs_m_s':1e-12}})
payload={'method':'80-digit Decimal independent sin/cos series and piecewise speed integral, body rotation matrix and right quaternion product',
    'author_or_product_modules_imported':False,'cases':records,
    'scope':'Analytic pure-software control, not motion/perception/clock/board acceptance'}
raw=(json.dumps(payload,indent=2)+'\n').encode()
with (OUT/'analytic-controls.json').open('xb') as stream:
    stream.write(raw)
print(json.dumps({'cases':len(records),'sha256':hashlib.sha256(raw).hexdigest(),'product_imports':False}))

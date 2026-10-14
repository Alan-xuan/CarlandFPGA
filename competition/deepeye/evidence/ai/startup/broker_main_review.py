from pathlib import Path
from datetime import datetime,timezone
import hashlib,itertools,json,platform,random,subprocess,sys
ROOT=Path.cwd();OUT=ROOT/'.local/plan-20261014-final-c/director-startup';P=ROOT/'.local/deepeye-implementation-c/competition/deepeye'
sys.path.insert(0,str(P));from ai_pc.control_broker import deadlines as D,mailbox as M
commands=[]
for name in ('test_deadlines.py','test_mailbox.py'):
    cmd=[sys.executable,'-X','utf8','-B',str(P/'tests/ai/control_broker'/name)];r=subprocess.run(cmd,capture_output=True,timeout=30)
    (OUT/('broker-repair3-'+name+'.stdout')).write_bytes(r.stdout);(OUT/('broker-repair3-'+name+'.stderr')).write_bytes(r.stderr)
    commands.append({'command':cmd,'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()});assert r.returncode==0,r.stderr
rng=random.Random(20261015)
for i in range(1000):
    profile=('fast_9600','stress_300')[i%2];cap={'fast_9600':3_000_000_000,'stress_300':12_000_000_000}[profile];age={'fast_9600':1_500_000_000,'stress_300':12_000_000_000}[profile]
    first=rng.randrange(10**12);sample=rng.randrange(first+1);ttl=rng.randrange(cap+1);receipt=first+rng.randrange(cap*2);remaining=rng.randrange(cap+1);serial,usb,clock=[rng.randrange(cap) for _ in range(3)];previous=rng.randrange(10**12)
    expected=min(first+ttl,receipt+max(0,remaining-serial-usb-clock),sample+age,previous)
    d=D.hil_deadline(first_send_ns=first,original_ttl_ns=ttl,referenced_sample_time_lower_ns=sample,profile=profile,receipt_ns=receipt,current_remaining_ttl_ns=remaining,serialized_frame_duration_ns=serial,usb_processing_upper_bound_ns=usb,clock_error_upper_bound_ns=clock,previous_deadline_ns=previous)
    assert d.deadline_ns==expected and d.expired_at(expected)
    if expected:assert not d.expired_at(expected-1)
    direct=D.pc_direct_deadline(first_host_issue_ns=first,requested_duration_ns=ttl,referenced_sample_time_lower_ns=sample,profile=profile,previous_deadline_ns=previous)
    assert direct.deadline_ns==min(first+ttl,sample+age,previous)
B=M.BrokerBinding('run','session','fast_9600',1)
for order in itertools.permutations(range(4)):
    box=M.ControlMailbox(binding=B);obs=[M.ObservationRef(str(i),i,i,i) for i in range(4)]
    for o in obs:box.register_sent_observation(o)
    for i in order:box.offer(M.Candidate(B,obs[i],1,bytes([i+1]),10+i))
    result=box.consume(consumed_at_ns=100,slot_deadline_ns=100,age_limit_ns=1000);assert result.candidate.observation==obs[3] and result.movement_authorized is False
    assert box.offer(M.Candidate(B,obs[3],1,b'\x04',20))==M.OFFER_DUPLICATE_IGNORED and box.pending is None
checks=[]
def expect_error(label,fn):
    try:fn()
    except D.BrokerError as e:checks.append({'case':label,'outcome':'rejected','message':str(e)})
    else:raise AssertionError('unexpected acceptance: '+label)
for state in ('empty','missed_slot','aged_out','evicted','future_completion'):
    box=M.ControlMailbox(binding=B);o=M.ObservationRef('o',1,0,1)
    if state!='empty':
        box.register_sent_observation(o);box.offer(M.Candidate(B,o,1,b'route',700 if state=='future_completion' else 200))
    if state=='evicted':
        for i in range(2,6):box.register_sent_observation(M.ObservationRef(str(i),i,0,i))
    def first():return box.consume(consumed_at_ns=500,slot_deadline_ns=100 if state=='missed_slot' else 500,age_limit_ns=400 if state=='aged_out' else 1000)
    if state=='future_completion':expect_error(state+' first',first)
    else:first()
    assert box.last_consumed_now_ns==500
    saved=(box.pending,box.high_water_key,box.high_water_digest,box.observation_ordinals)
    expect_error(state+' regressing clock',lambda:box.consume(consumed_at_ns=300,slot_deadline_ns=300,age_limit_ns=1000))
    assert saved==(box.pending,box.high_water_key,box.high_water_digest,box.observation_ordinals) and box.last_consumed_now_ns==500
    expect_error(state+' bad age does not advance clock',lambda:box.consume(consumed_at_ns=900,slot_deadline_ns=900,age_limit_ns=10**20))
    assert box.last_consumed_now_ns==500
for profile,limit in [('fast_9600',1_500_000_000),('stress_300',12_000_000_000)]:
    b=M.BrokerBinding('run','session',profile,1)
    for age in (1,limit-1,limit):
        box=M.ControlMailbox(binding=b);o=M.ObservationRef('o',0,0,0);box.register_sent_observation(o);box.offer(M.Candidate(b,o,0,b'x',0))
        assert box.consume(consumed_at_ns=age,slot_deadline_ns=age,age_limit_ns=age).reason==M.CONSUME_OBSERVATION_AGE_EXCEEDED
    box=M.ControlMailbox(binding=b)
    expect_error(profile+' oversized age',lambda:box.consume(consumed_at_ns=0,slot_deadline_ns=0,age_limit_ns=limit+1))
    assert box.last_consumed_now_ns is None
# Independent clock-state reference for empty mailbox, including malformed arguments.
box=M.ControlMailbox(binding=B);reference=None
for i in range(1000):
    now=rng.randrange(0,10000);age=rng.choice((100,1_500_000_000,1_500_000_001));legal=age<=1_500_000_000 and (reference is None or now>=reference)
    try:answer=box.consume(consumed_at_ns=now,slot_deadline_ns=now,age_limit_ns=age)
    except D.BrokerError:assert not legal
    else:assert legal and answer.candidate is None;reference=now
    assert box.last_consumed_now_ns==reference
# Enumerate all mode/name subsets, independently specify the intended structural contract.
names=('first_send_plus_original_ttl','sample_lower_plus_age_limit','receipt_plus_remaining_budget','previous_deadline','first_host_issue_plus_requested_duration','arbitrary')
term_cases=0
for mode,mandatory,allowed in [(D.HIL_MODE,{names[0],names[1]},set(names[:4])),(D.PC_DIRECT_MODE,{names[4],names[1]},{names[4],names[1],names[3]})]:
    for flags in itertools.product((False,True),repeat=len(names)):
        selected={n for n,f in zip(names,flags) if f};legal=mandatory<=selected<=allowed;terms=tuple((n,100) for n in names if n in selected);term_cases+=1
        try:d=D.LeaseDeadline(mode,100,False,None,terms)
        except D.BrokerError:assert not legal,(mode,selected)
        else:assert legal and d.expired_at(100),(mode,selected)
box=M.ControlMailbox(binding=B)
for i in range(2000):
    box.register_sent_observation(M.ObservationRef('cyclic-'+str(i%5),i,i,i));assert len(box._registered)<=4 and len(box._observations)<=4
owned=json.loads((OUT/'broker-repair3-result.json').read_text())['ownership'];hashes={}
for rel in owned:
    p=ROOT/rel;hashes[p.relative_to(P).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
terminal=json.loads((OUT/'broker-repair3-terminal.json').read_text())[0]
result={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'contract_id':'DEEPEYE-HUMAN-LOCK-20261014/revision1','requirements_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804','design_commit':'1011259415a0916054eb580687612580bc1e5f09','job_id':terminal['job_id'],'actual_executor':{k:terminal['result'].get(k) for k in ('provider','model','reasoning_effort')},'at_utc':datetime.now(timezone.utc).isoformat(),'tool_versions':{'python':sys.version,'platform':platform.platform()},'commands':commands,'unit_tests':78,'independent_deadline_pairs':1000,'completion_order_permutations':24,'independent_clock_calls':1000,'term_subset_cases':term_cases,'bounded_registrations':2000,'focused_rejections':checks,'source_sha256':hashes,'review_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'acceptance':'passed_software_foundation_only','closed_findings':['B01','B02','B03','B04','BR21','BR22','BR23'],'C05':'not_run','stages':{s:'not_run' for s in ('simulation','synthesis','implementation','board','system')},'limits':['Pure deadline/mailbox helpers only, no I/O, no wire adapter or motion authorization.','A-owned schema, scheduler timing, measured clock/USB bounds and runtime authority not accepted; no C05 or actual3D/board/system success.','Historic source snapshots and failures remain retained; terminal completion alone was never acceptance.']}
(OUT/'broker-repair3-main-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:result[k] for k in ('acceptance','unit_tests','independent_deadline_pairs','completion_order_permutations','independent_clock_calls','term_subset_cases','bounded_registrations')}))

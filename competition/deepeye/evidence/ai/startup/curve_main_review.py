from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace
import hashlib,json,math,random,shutil,subprocess,sys
ROOT=Path.cwd();OUT=ROOT/'.local/plan-20261014-final-c/director-startup';P=ROOT/'.local/deepeye-implementation-c/competition/deepeye'
sys.path.insert(0,str(P));from ai_pc.model import curve_input as C
snapshot=OUT/'curve-repair1-before-main-review';snapshot.mkdir(exist_ok=False);hashes={}
for rel in json.loads((OUT/'curve-repair1-result.json').read_text())['ownership']:
    p=ROOT/rel;t=snapshot/p.relative_to(P);t.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,t);hashes[p.relative_to(P).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
cmd=[sys.executable,'-X','utf8','-B',str(P/'tests/ai/data_model/test_curve_input.py')];r=subprocess.run(cmd,capture_output=True,timeout=45)
(OUT/'curve-repair1-main-tests.stdout').write_bytes(r.stdout);(OUT/'curve-repair1-main-tests.stderr').write_bytes(r.stderr);assert r.returncode==0,r.stderr
raw=(P/'data/preprocessing.json').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef'
document=json.loads(raw);scaler=C.CurveScaler.from_document_bytes(raw,expected_sha256=digest);binding=C.CurveBinding('main-independent','software_fixture',digest)
builder=C.CurveWindowBuilder(scaler=scaler,binding=binding);rng=random.Random(20261015);sequence=0;history={};previous=[]
for i in range(1000):
    sequence+=rng.choice((1,1,1,2,127,128,129,10**9));values=(rng.uniform(-100,300),rng.uniform(-2,5),rng.uniform(-.1,1),rng.choice((0,-1,10**rng.uniform(-3,4))));valid=tuple(rng.choice((True,False)) for _ in range(4));obs=C.CurveObservation(binding,sequence,values,valid);builder.observe(obs);window=builder.snapshot()
    expected=[];mask=[]
    for k in range(4):
        if not valid[k] or (k==3 and values[k]<=0):expected.append(0.0);mask.append(0.0)
        else:
            x=math.log10(values[k]) if k==3 else values[k];stats=document['channels'][k];expected.append((x-stats['mean'])/stats['effective_scale']);mask.append(1.0)
    history[sequence]=tuple(expected+mask)
    for col in range(128):
        ref=history.get(sequence-127+col,(0.0,)*8)
        assert tuple(channel[col] for channel in window.features)==ref,(i,col)
    assert len(builder._slots)<=128
    if i%50==0:previous.append((window,window.features))
    if i%13==0:
        builder.observe(obs);assert builder.snapshot().features==window.features
    for snap,features in previous:assert snap.features==features
rejections=[]
def rejected(name, call):
    try:call()
    except (C.CurveInputError,TypeError):rejections.append(name)
    else:raise AssertionError('accepted invalid construction: '+name)
altered=list(scaler.channels);altered[0]=replace(altered[0],mean=altered[0].mean+10)
rejected('CP01 legacy hash and channels',lambda:C.CurveScaler(preprocessing_sha256=digest,channels=tuple(altered)))
rejected('CP01 dataclasses.replace',lambda:replace(scaler,channels=tuple(altered)))
for i in range(100):
    forged_doc=json.loads(raw);forged_doc['channels'][i%4]['mean']+=i+1
    forged_raw=json.dumps(forged_doc).encode();forged_sha=hashlib.sha256(forged_raw).hexdigest()
    rejected('CP01 changed bytes production hash '+str(i),lambda:C.CurveScaler(forged_raw,expected_sha256=digest))
    alternate=C.CurveScaler(forged_raw,expected_sha256=forged_sha)
    rejected('CP01 alternate digest mismatches binding '+str(i),lambda:C.CurveWindowBuilder(scaler=alternate,binding=binding))
original_stats=scaler.channels
for convert in (bytes,bytearray,memoryview):
    buf=bytearray(raw);material=bytes(buf) if convert is bytes else buf if convert is bytearray else memoryview(buf)
    fresh=C.CurveScaler(material,expected_sha256=digest);buf[:]=b'x'*len(buf)
    assert fresh.channels==original_stats and fresh.preprocessing_sha256==digest
for i in range(100):
    names=['v%d_%d'%(i,k) for k in range(4)];valids=['m%d_%d'%(i,k) for k in range(4)]
    original_names=tuple(names);original_valids=tuple(valids)
    schema=C.CurveSchema(values=names,valid=valids);b=C.CurveWindowBuilder(scaler=scaler,binding=binding,schema=schema)
    names[0]='renamed_value';valids[1]='renamed_valid';names.append('extra');valids.clear()
    assert schema.values==original_names and schema.valid==original_valids
    record={'run_id':binding.run_id,'source_domain':binding.source_domain,'profile_id':binding.profile_id,'preprocessing_sha256':digest,'sequence':0,**dict(zip(original_names,(100,2,.2,10))),**{v:True for v in original_valids}}
    b.observe(record);before=b.snapshot();wrong=dict(record);wrong['renamed_value']=wrong.pop(original_names[0]);wrong['sequence']=1
    rejected('CP02 changed mapping '+str(i),lambda:b.observe(wrong));assert b.snapshot()==before
    record['sequence']=1;b.observe(record);assert b.snapshot().metadata.filled_slots==2

# Independent bounded raw-data replay: read one already-selected training member,
# verify its full bytes/ZIP CRC, then parse only the four sensor columns in 256 rows.
import zipfile
member=document['fitting_wells'][0];archive=ROOT/'.local/datasets/force-2020/LAS_files_Force_2020_all_wells_train_test_blind_hidden_final.zip'
with zipfile.ZipFile(archive) as z:las=z.read(member['member'])
assert hashlib.sha256(las).hexdigest()==member['member_sha256']
section='';curves=[];rows=[];null=None
for line in las.decode('utf-8-sig').splitlines():
    line=line.strip()
    if not line or line.startswith('#'):continue
    if line.startswith('~'):section=line[1:2].upper();continue
    if section=='W' and line.split('.',1)[0].strip().upper()=='NULL':null=float(line.split('.',1)[1].split(':',1)[0].strip())
    elif section=='C':curves.append(line.split('.',1)[0].strip().upper())
    elif section=='A':
        rows.append(line.split())
        if len(rows)==256:break
assert null is not None and len(rows)==256
indexes=[curves.index(name) for name in C.CHANNEL_NAMES]
realbinding=C.CurveBinding('main-train-first256','geo_replay',digest);b=C.CurveWindowBuilder(scaler=scaler,binding=realbinding)
real_history=[];valid_counts=[0]*4
for seq,row in enumerate(rows):
    assert len(row)==len(curves)
    values=tuple(float(row[k]) for k in indexes);valid=tuple(v!=null for v in values)
    b.observe(C.CurveObservation(realbinding,seq,values,valid));ref=[];mask=[]
    for k,v in enumerate(values):
        ok=valid[k] and (k!=3 or v>0);mask.append(float(ok));valid_counts[k]+=int(ok)
        ref.append(((math.log10(v) if k==3 else v)-document['channels'][k]['mean'])/document['channels'][k]['effective_scale'] if ok else 0.0)
    real_history.append(tuple(ref+mask));win=b.snapshot()
    for col in range(128):
        pos=seq-127+col;expected=real_history[pos] if pos>=0 else (0.0,)*8
        assert tuple(c[col] for c in win.features)==expected
assert valid_counts==[236,0,0,0]
child=json.loads((OUT/'curve-repair1-terminal.json').read_text())[0]['result']
result={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'contract_id':'DEEPEYE-HUMAN-LOCK-20261014/revision1','requirements_sha256':C.CONTRACT_REQUIREMENTS_SHA256,'design_commit':C.CONTRACT_DESIGN_COMMIT,'job_id':'child-962a94dfb9504ad7a6f3371e34167d05','at_utc':datetime.now(timezone.utc).isoformat(),'command':cmd,'exit_code':r.returncode,'python_version':sys.version,'raw_stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'raw_stderr_sha256':hashlib.sha256(r.stderr).hexdigest(),'unit_tests':28,'independent_reference_windows':1000,'compared_scalar_features':1024000,'provenance_counterexamples_rejected':202,'schema_mutation_cases':100,'mutable_byte_ingress_cases':3,'rejection_labels':rejections,'real_train_replay':{'member':member['member'],'sha256':member['member_sha256'],'rows':256,'window_scalar_comparisons':262144,'valid_samples':valid_counts,'heldout_wells_opened':0,'row_label_values_parsed':0,'limit':'only GR valid in this slice; other3channels all NULL; not four-channel real-data coverage'},'source_sha256':hashes,'preprocessing_sha256':digest,'closed_findings':['CP01','CP02'],'acceptance':'passed_software_foundation_only','snapshot':str(snapshot),'provider':child.get('provider'),'model':child.get('model'),'reasoning_effort':child.get('reasoning_effort'),'C01':'not_run','limits':['No trained model or four-channel real-data performance claim','No wire adapter or runtime future-label/truth isolation acceptance','No live sensor/sim_em_v2/domain gate acceptance','No board/AMD/system acceptance']}
(OUT/'curve-repair1-main-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('unit_tests','independent_reference_windows','provenance_counterexamples_rejected','schema_mutation_cases','real_train_replay','closed_findings','acceptance')}))

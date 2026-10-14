"""Independent main readback of fixed training coverage; no heldout member reads."""
from pathlib import Path
import argparse,hashlib,importlib.util,io,json,math,os,re,shutil,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from unittest.mock import patch

pa=argparse.ArgumentParser();pa.add_argument('--audit-dir',required=True);pa.add_argument('--product',required=True);pa.add_argument('--archive',required=True);pa.add_argument('--output',required=True);args=pa.parse_args()
audit_dir=Path(args.audit_dir).resolve();product=Path(args.product).resolve();archive=Path(args.archive).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
names=['scan_train_curves.py','test_scan_train_curves.py','audit.json','audit.log']
source={n:hashlib.sha256((audit_dir/n).read_bytes()).hexdigest() for n in names}
snap=out/'train-coverage-before-main-review';snap.mkdir(exist_ok=False)
for n in names:(snap/n).write_bytes((audit_dir/n).read_bytes())
product_before={p.relative_to(product).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in product.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
expected_pins={'splits.json':'f10ddb8f37e6bdf7c9663eed45d0f6554ef8992899724013a7e487ad3e3cef91','force_wells.json':'ace9a0eb9930f19c6b8125e151d07346fb23029b1455eac04964d15b97461e59','preprocessing.json':'cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef'}
docs={};buffers={}
for name,sha in expected_pins.items():
    b=(product/'data'/name).read_bytes();assert hashlib.sha256(b).hexdigest()==sha
    docs[name]=json.loads(b);buffers[name]=b
with archive.open('rb') as fh:assert hashlib.file_digest(fh,'sha256').hexdigest()=='042ef1d473100dc12768cae7107a8cead071a394f137af3bc1ddaf8a5d1b8dda'
assert archive.stat().st_size==169785172
splits=docs['splits.json']['rows'];train=sorted(x['member'] for x in splits if x['split']=='train');allowed=set(train);assert len(train)==82
roots={s:{x['root_id'] for x in splits if x['split']==s} for s in ('train','validation','test')}
assert len(roots['train'])==81 and not(roots['train']&roots['validation'] or roots['train']&roots['test'] or roots['validation']&roots['test'])
inventory={x['member']:x for x in docs['force_wells.json']['wells']}
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
scan=load('main_review_scan_train',audit_dir/'scan_train_curves.py')
child=json.loads((audit_dir/'audit.json').read_bytes())['audit']
original_open=zipfile.ZipFile.open
opened=[]
def guarded(z,name,*a,**kw):
    actual=name.filename if isinstance(name,zipfile.ZipInfo) else name
    if actual not in allowed:raise AssertionError('heldout member requested')
    opened.append(actual);return original_open(z,name,*a,**kw)
with patch.object(zipfile.ZipFile,'open',guarded):
    rerun=scan.run_audit(str(archive),str(product))
assert len(opened)==83 and len(set(opened))==82
for key in ['split_crosscheck','guard','wells','aggregate','parse_instrumentation','reconciliation','selection','replay','rows_measured_total']:
    assert rerun[key]==child[key],key
(out/'train-coverage-main-rerun.json').write_text(json.dumps(rerun,indent=2),encoding='utf-8')
print('guarded_child_rerun_complete',flush=True)

# Independent LAS parsing: bytes splitlines/header regex and per-row token projection.
# No child parser, inventory parser, run finder or expected-feature helper is used.
channels=('GR','RHOB','NPHI','RDEP');independent={};selected=None;selected_rows=[];total_rows=0;open_start=len(opened)
child_wells={x['member']:x for x in child['wells']}
with patch.object(zipfile.ZipFile,'open',guarded),zipfile.ZipFile(archive) as z:
    for member in train:
        raw=z.read(member);meta=inventory[member]
        assert hashlib.sha256(raw).hexdigest()==meta['member_sha256'] and len(raw)==meta['member_size_bytes']
        rows=raw.splitlines();section='';curve_names=[];null=None;ascii_start=None
        for i,b in enumerate(rows):
            text=b.decode('ascii').strip()
            if not text or text.startswith('#'):continue
            if text.startswith('~'):
                section=text[1:].split()[0].lower()
                if section in ('a','ascii'):ascii_start=i+1;break
                continue
            if section=='curve':curve_names.append(text.split('.',1)[0].strip())
            if section=='well' and re.match(r'^NULL\s*\.',text):null=float(text.split(':',1)[0].split('.',1)[1].strip())
        assert null is not None and ascii_start is not None and len(curve_names)==len(set(curve_names))
        idx={c:curve_names.index(c) if c in curve_names else None for c in channels}
        counts={c:{'present':idx[c] is not None,'rawvalid':0,'effectivevalid':0,'null':0,'nonfinite':0,'nonpositive':0,'absent_rows':0} for c in channels}
        n=0;run=maximum=all4=0;first=None;candidate=[];first_values=None
        for b in rows[ascii_start:]:
            b=b.strip()
            if not b or b.startswith(b'#'):continue
            assert not b.startswith(b'~'),'independent pinned-file parser found extra section'
            fields=b.split();assert len(fields)==len(curve_names);values=[];valid=True
            for c in channels:
                q=counts[c];j=idx[c]
                if j is None:q['absent_rows']+=1;values.append(None);valid=False;continue
                value=float(fields[j])
                if not math.isfinite(value):q['nonfinite']+=1;values.append(None);valid=False;continue
                if value==null:q['null']+=1;values.append(None);valid=False;continue
                q['rawvalid']+=1
                if c=='RDEP' and value<=0:q['nonpositive']+=1;values.append(None);valid=False;continue
                q['effectivevalid']+=1;values.append(value)
            if valid:
                all4+=1;run+=1;maximum=max(maximum,run)
                if first is None:
                    candidate.append((n,tuple(values)))
                    if run==128:first=n-127;first_values=candidate[:]
            else:
                run=0
                if first is None:candidate=[]
            n+=1
        assert n==meta['rows'];total_rows+=n
        value={'rows':n,'channels':counts,'all4_rows':all4,'first_run_start':first,'max_run_len':maximum}
        independent[member]=value
        for key,v in value.items():assert v==child_wells[member][key],(member,key)
        if selected is None and first is not None:selected=(member,first);selected_rows=first_values
assert total_rows==1634292 and len(opened)-open_start==82
assert selected==(child['selection']['member'],child['selection']['start_row'])
assert len(selected_rows)==128
print('independent_82well_readback_complete',flush=True)
curve=load('main_review_curve_input',product/'ai_pc/model/curve_input.py')
scaler=curve.CurveScaler(buffers['preprocessing.json'],expected_sha256=expected_pins['preprocessing.json'])
binding=curve.CurveBinding(run_id='independent-main-coverage',source_domain='geo_replay',preprocessing_sha256=expected_pins['preprocessing.json'])
builder=curve.CurveWindowBuilder(scaler=scaler,binding=binding)
norm=[];history=[];compared=0
stats=docs['preprocessing.json']['channels']
for seq,vals in selected_rows:
    norm.append(tuple(((math.log10(v) if i==3 else v)-stats[i]['mean'])/stats[i]['effective_scale'] for i,v in enumerate(vals)))
    builder.observe(curve.CurveObservation(binding=binding,sequence=seq,values=vals,valid=(True,)*4));actual=builder.snapshot()
    count=len(norm);pad=128-count
    want=tuple(tuple([0.0]*pad+[item[i] for item in norm]) for i in range(4))+tuple(tuple([0.0]*pad+[1.0]*count) for _ in range(4))
    assert actual.features==want;assert actual.metadata.latest_sequence==seq and actual.metadata.filled_slots==count
    compared+=1024;history.append(actual)
assert history[0].metadata.filled_slots==1 and sum(history[0].features[4])==1
input_hash=hashlib.sha256('\n'.join('%d|%r|%r|%r|%r'%(s,*v) for s,v in selected_rows).encode()).hexdigest()
final_hash=hashlib.sha256(repr(want).encode()).hexdigest()
assert input_hash==child['replay']['input_sha256'] and final_hash==child['replay']['actual_output_sha256']

# Additional independent random-mask/run and opaque-column cases on tiny bytes.
import random
rng=random.Random(2026101509);modules=scan.load_product_modules(str(product));random_cases=0
for case in range(160):
    flags=[rng.random()<.75 for _ in range(rng.randrange(1,450))]
    if case%3==0:flags.extend([True]*128)
    if case%4==0:flags[0:0]=[False]*4
    n=len(flags);header=b'~Version\nVERS. 2.0 : x\nWRAP. NO : x\n~Well\nUWI. synthetic : x\nNULL. -999.25 : x\n~Curve\nDEPT.m : x\nGR.gAPI : x\nLABEL. : x\nRHOB.g/cm3 : x\nCONF. : x\nNPHI.v/v : x\nRDEP.ohmm : x\n~ASCII\n'
    data=header+b''.join(('opaque_depth 60 label_%s 2.5 opaque_conf .25 %s\n'%(i,'10' if f else '-999.25')).encode() for i,f in enumerate(flags))
    got,_,actual_flags=scan.parse_member(io.BytesIO(data),'synthetic.las',len(data),modules)
    assert list(actual_flags)==list(map(int,flags));assert got['all4_rows']==sum(flags)
    starts=[i for i in range(max(0,n-127)) if all(flags[i:i+128])]
    segments=''.join('1' if f else '0' for f in flags).split('0');mx=max(map(len,segments))
    assert scan.first_run_reaching(actual_flags)==(starts[0] if starts else None,mx)
    random_cases+=1

commands=[]
def run(cmd,name,env=None):
    r=subprocess.run(cmd,capture_output=True,env=env,timeout=90)
    (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
    commands.append({'command':cmd,'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest(),'raw_prefix':name})
    assert r.returncode==0,r.stderr.decode(errors='replace');return r
env=dict(os.environ,DEEPEYE_PRODUCT_DIR=str(product),PYTHONDONTWRITEBYTECODE='1')
r=run([sys.executable,'-X','utf8','-B',str(audit_dir/'test_scan_train_curves.py')],'train-coverage-main-unit',env);assert b'Ran 27 tests' in r.stderr
portable=out/'train-coverage-portable';portable.mkdir(exist_ok=False)
for n in names[:2]:(portable/n).write_bytes((audit_dir/n).read_bytes())
prod=portable/'product'
for name in ['data/force_inventory.py','data/grouping.py','ai_pc/model/curve_input.py']:
    t=prod/name;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes((product/name).read_bytes())
r=run([sys.executable,'-X','utf8','-B',str(portable/'test_scan_train_curves.py')],'train-coverage-main-portable',dict(env,DEEPEYE_PRODUCT_DIR=str(prod)));assert b'Ran 27 tests' in r.stderr
assert source=={n:hashlib.sha256((audit_dir/n).read_bytes()).hexdigest() for n in names}
assert product_before=={p.relative_to(product).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in product.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
result={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'contract_id':'DEEPEYE-HUMAN-LOCK-20261014/revision1','requirements_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804','design_commit':'1011259415a0916054eb580687612580bc1e5f09','job_id':'child-c7dcf18e89bf4132918255a66d6f15b2','at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':source,'unit_tests':27,'portable_tests':27,'independent_opaque_run_cases':random_cases,'child_rerun_zip_opens':83,'independent_zip_opens':82,'heldout_opens':0,'train_wells':82,'train_parents':81,'train_rows':total_rows,'all4_valid_rows':sum(x['all4_rows'] for x in independent.values()),'all4_128run_wells':sum(x['first_run_start'] is not None for x in independent.values()),'aggregate':child['aggregate'],'selection':{'member':selected[0],'start_row':selected[1],'end_row':selected[1]+127,'policy':'lex-first fixed TRAIN member, earliest128all4effective-valid run; precommitted diagnostic only'},'independent_replay':{'windows':128,'values_compared':compared,'input_sha256':input_hash,'final_window_sha256':final_hash,'max_error':0.0,'snapshot_immutability':True},'numeric_parse_note':'6,537,168 is the first82-member scan only; replay second-open re-parses selected member. Nonselected data columns are never numerically parsed in reviewed scan/reference logic;160 opaque-column cases support this statement. This is not runtime future-label access evidence.','commands':commands,'product_bytes_unchanged':True,'python_version':sys.version,'provider':'deepseek','model':'deepseek-flash','reasoning_effort':'max','acceptance':'passed_train_only_offline_coverage_and_replay_evidence','C01':'not_run','C02':'not_run','limits':['Not model training, heldout evaluation, waterhazard/lithology performance or real sensor evidence','No resplit/refit or public runtime/3D/hardware acceptance','Private audit helper controlled CLI and specified input paths only; not accepted as production data verifier','All29productcards remain not_run']}
(out/'train-coverage-main-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(out/'train-coverage-independent-wells.json').write_text(json.dumps(independent,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['commands','source_sha256','aggregate']},indent=2),flush=True)

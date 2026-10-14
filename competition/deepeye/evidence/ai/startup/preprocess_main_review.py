from pathlib import Path
import copy, hashlib, importlib.util, io, json, math, platform, random, subprocess, sys, tempfile, zipfile
from datetime import datetime, timezone
from unittest.mock import patch

ROOT=Path.cwd(); OUT=ROOT/'.local/plan-20261014-final-c/director-startup'
P=ROOT/'.local/deepeye-implementation-c/competition/deepeye'
LOCK='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
source=P/'data/force_preprocess.py'; test=P/'tests/ai/data_model/test_force_preprocess.py'
assert sha(source)=='75b2015c0ec9deab9a94a2032b77117124085631f2bd758a54c7ea7fdfdf2848'
assert sha(test)=='a96529e9f3954379f23bb1c5d4806b750801a10c037101712effcdcb8d71bef4'
F=load('main_preprocess_review',source)
commands=[]
cmd=[sys.executable,'-X','utf8','-B',str(test)]
r=subprocess.run(cmd,capture_output=True,timeout=45)
(OUT/'preprocess-repair1-tests.stdout').write_bytes(r.stdout);(OUT/'preprocess-repair1-tests.stderr').write_bytes(r.stderr)
commands.append({'command':cmd,'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()})
assert r.returncode==0,r.stderr.decode()
# Independent hand-built LAS, varied placement of selected channels and opaque columns.
rng=random.Random(20261015); cases=[]
for case in range(100):
    columns=[('GR','gAPI'),('RHOB','g/cm3'),('NPHI','m3/m3'),('RDEP','ohm.m'),('LABEL','_'),('CONFIDENCE','_'),('X','m')];rng.shuffle(columns)
    selected={'GR':[-3.0,7.0,12.0],'RHOB':[2.0,2.3,2.6],'NPHI':[.1,-.05,.3],'RDEP':[.1,1.0,100.0]}
    lines=['~Version','VERS. 2.0 :','WRAP. NO :','~Well','NULL. -999.25 :','UWI. 1/2-3 :','WELL. independent :','~Curve','DEPT.m :']+[n+'.'+u+' :' for n,u in columns]+['~Ascii']
    for k in range(3):lines.append(str(k)+' '+' '.join(str(selected[n][k]) if n in selected else ('opaque_label','NaN','n/a')[k] for n,_ in columns))
    raw=('\n'.join(lines)+'\n').encode(); fits={n:F._ChannelFit(n) for n in F.CHANNELS}; parsed=[]; original=F._strict_number
    def numeric(token,what,member,line):
        assert what in ('depth',*F.CHANNELS);assert token not in ('opaque_label','NaN','n/a');parsed.append(what);return original(token,what,member,line)
    with patch.object(F,'_strict_number',numeric): result=F._fit_member(io.BytesIO(raw),'main-fixture.las',1+case,fits)
    assert result['rows']==3 and len(parsed)==15
    for n in F.CHANNELS:
        values=[math.log10(x) for x in selected[n]] if n=='RDEP' else selected[n]; mean=math.fsum(values)/3;variance=math.fsum((v-mean)**2 for v in values)/3
        assert math.isclose(fits[n].mean,mean,rel_tol=1e-12,abs_tol=1e-12)
        assert math.isclose(fits[n].m2/3,variance,rel_tol=1e-12,abs_tol=1e-12)
    cases.append({'case':case,'column_order':[n for n,_ in columns],'chunk_bytes':1+case,'sha256':hashlib.sha256(raw).hexdigest()})
# Reuse fixture serialization, but supply main-selected corruptions and fail before any member open.
T=load('main_preprocess_test_helpers',test); rejected=[]
with tempfile.TemporaryDirectory() as tmp:
    for case in ('cross_split','wrong_heldout_well','wrong_heldout_sha','unknown_parent','self_cycle','wrong_root','duplicate_row'):
        wells={'a.las':{'uwi':'1/2-3','rows':['0 1 30000 10 2 .1 1']},'b.las':{'uwi':'1/2-3 A' if case=='cross_split' else '4/5-6','rows':['0 1 30000 15 2 .1 1']}}
        scene=T._Scene(Path(tmp)/case,wells,{'a.las':('train','1/2-3'),'b.las':('validation','1/2-3' if case=='cross_split' else '4/5-6')})
        doc=scene.load_splits();a,b=doc['rows']
        if case=='wrong_heldout_well': b['well_id']='9/9-9'
        if case=='wrong_heldout_sha': b['member_sha256']='0'*64
        if case=='unknown_parent': b['derived_from']='missing'
        if case=='self_cycle': b['derived_from']=b['row_id']
        if case=='wrong_root': b['root_id']='9/9-9'
        if case=='duplicate_row': b['row_id']=a['row_id']
        scene.save_splits(doc)
        with patch.object(zipfile.ZipFile,'open',side_effect=AssertionError('invalid manifest opened member')):
            try: scene.fit()
            except T.force_preprocess.ForcePreprocessError as e: rejected.append({'case':case,'error':str(e)})
            else: raise AssertionError(case+' accepted')
# Real archive fit with independent read guard and exact statistics equality.
splits=json.loads((P/'data/splits.json').read_text()); train=[r['member'] for r in splits['rows'] if r['split']=='train'];opened=[]
zip_open=zipfile.ZipFile.open
def guarded(self,name,*args,**kwargs):
    assert isinstance(name,str) and name in train, 'held-out member opened';opened.append(name);return zip_open(self,name,*args,**kwargs)
original=json.loads((P/'data/preprocessing.json').read_text())
with patch.object(zipfile.ZipFile,'open',guarded): current=F.fit_preprocessing(out=OUT/'preprocess-main-recomputed.json',generated_utc=original['generated_utc'])
assert opened==train and len(opened)==82
assert current==original,'real current output differs from worker artifact'
before=json.loads((OUT/'preprocess-before-repair1/data/preprocessing.json').read_text())
for key in ('channels','train','fitting_wells'):assert current[key]==before[key],key
independent=json.loads((OUT/'independent-train-statistics.json').read_text());assert independent['status']=='passed_independent_numeric_readback_only'
assert independent['reference_preprocessing_sha256']==sha(OUT/'preprocess-before-repair1/data/preprocessing.json')
for channel in current['channels']:
    ref=independent['channels'][channel['name']]; assert ref['counts']==channel['counts']
    assert math.isclose(ref['mean_fsum'],channel['mean'],rel_tol=1e-10,abs_tol=1e-12)
    assert math.isclose(ref['population_variance_fsum'],channel['variance'],rel_tol=1e-9,abs_tol=1e-12)
result={'status':'passed_software_foundation_only','reviewer':'C quality main','job_id':'child-4b207693f8574ae0b82d2f32185550e3','task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'contract_id':'DEEPEYE-HUMAN-LOCK-20261014/revision1','requirements_sha256':LOCK,'design_commit':F.DESIGN_COMMIT,'at_utc':datetime.now(timezone.utc).isoformat(),'tool_versions':{'python':sys.version,'platform':platform.platform()},'commands':commands,'unit_tests':33,'independent_opaque_column_permutation_cases':cases,'independent_invalid_manifest_cases':rejected,'real_fit':{'opened_members':opened,'heldout_opened':0,'train':current['train'],'exact_current_output_equality':True,'prior_stats_bitwise_unchanged':True,'independent_fsum_readback_sha256':sha(OUT/'independent-train-statistics.json')},'source_sha256':{p.relative_to(P).as_posix():sha(p) for p in [source,test,P/'data/preprocessing.json',P/'data/grouping.py',P/'data/force_inventory.py']},'input_sha256':{name:sha(P/'data'/name) for name in ('force_wells.json','splits.json','split_policy.json','label_schema.json')},'review_script_sha256':sha(Path(__file__)),'product_C01':'not_run','stages':{k:'not_run' for k in ('simulation','synthesis','implementation','board','system')},'limits':['No causal curve replay windows, verify_data CLI, training, model accuracy or runtime isolation acceptance.','The independent numeric readback is reused because all statistics and fitting members remain bitwise equal.','PF01/PF02 original failures retained in private review evidence.']}
(OUT/'preprocess-repair1-main-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'unit_tests':33,'independent_cases':len(cases),'invalid_manifests':len(rejected),'real_train_wells':82,'real_train_rows':current['train']['data_rows'],'heldout_opened':0}))

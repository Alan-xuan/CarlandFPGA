from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace,fields
from unittest.mock import patch
import hashlib,importlib.util,json,os,re,shutil,subprocess,sys,zipfile
ROOT=Path.cwd();OUT=ROOT/'.local/plan-20261014-final-c/director-startup';P=ROOT/'.local/deepeye-implementation-c/competition/deepeye';sys.path.insert(0,str(P))
from tools import verify_data as V
archive=ROOT/'.local/datasets/force-2020'/V.ARCHIVE_BASENAME
snapshot=OUT/'verify-data-repair1-before-main-review';snapshot.mkdir(exist_ok=False);hashes={}
for rel in json.loads((OUT/'verify-data-repair1-result.json').read_text())['ownership']:
    src=ROOT/rel;dest=snapshot/src.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);hashes[src.relative_to(P).as_posix()]=hashlib.sha256(src.read_bytes()).hexdigest()
cases=OUT/'verify-data-repair1-independent-cases';cases.mkdir(exist_ok=False)
def copy_product(name,tests=False):
    dest=cases/name;dest.mkdir()
    paths=list(V.PINNED_ARTIFACTS)+['tools/verify_data.py']+(['tests/ai/data_model/test_verify_data.py'] if tests else [])
    for rel in paths:
        target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(P/rel,target)
    return dest
commands=[]
def command(args,name,env=None):
    cmd=[sys.executable,'-X','utf8','-B',*map(str,args)]
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=90,env=env)
    (OUT/(name+'.stdout')).write_bytes(r.stdout);(OUT/(name+'.stderr')).write_bytes(r.stderr)
    commands.append({'command':cmd,'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest(),'evidence_prefix':name})
    return r
env=dict(os.environ,DEEPEYE_FORCE_ARCHIVE=str(archive),PYTHONDONTWRITEBYTECODE='1')
r=command([P/'tests/ai/data_model/test_verify_data.py'],'verify-data-repair1-main-tests',env)
assert r.returncode==0 and b'Ran 48 tests' in r.stderr and b'skipped' not in r.stderr,r.stderr
clean=copy_product('portable-checkout',True);env.pop('DEEPEYE_FORCE_ARCHIVE',None)
r=command([clean/'tests/ai/data_model/test_verify_data.py'],'verify-data-repair1-main-portable-tests',env)
assert r.returncode==0 and b'Ran 48 tests' in r.stderr and b'skipped=3' in r.stderr,r.stderr
print('48 real tests/0 skips and48 portable tests/3 counted skips passed',flush=True)

# VD01: independently change each JSON between the first pin pass and load.
race=copy_product('checked-parsed-buffer');original_verify=V.verify_pins;race_cases=[]
for name,rel in V.DOCUMENT_PATHS.items():
    target=race/rel;before=target.read_bytes();doc=json.loads(before);doc['main_race_probe']='changed after pin pass';changed=json.dumps(doc).encode()
    def replace_after_hash(root,spec):
        records=original_verify(root,spec);target.write_bytes(changed);return records
    try:
        with patch.object(V,'verify_pins',replace_after_hash):report,code=V.run_verification(race,V.PRODUCTION_SPEC,scope='force-offline',archive_path=archive)
        assert code==1 and next(c for c in report['checks'] if c['id']=='pinned_documents_parse')['status']=='failed',name
        race_cases.append(name)
    finally:target.write_bytes(before)

# VD02: all ordered pairs of one corrupt and one missing artifact.
mixed=copy_product('mixed-pin-errors');relative=list(V.PINNED_ARTIFACTS);mixed_count=0
for corrupt in relative:
    for absent in relative:
        if corrupt==absent:continue
        bad=mixed/corrupt;missing=mixed/absent;backup=missing.with_name(missing.name+'.missing');before=bad.read_bytes()
        try:
            bad.write_bytes(b'corrupt input');missing.rename(backup)
            report,code=V.run_verification(mixed,V.PRODUCTION_SPEC,scope='force-offline',archive_path=archive)
            detail=next(c for c in report['checks'] if c['id']=='pinned_artifact_hashes')['detail']
            assert code==1 and 'missing' in detail and 'hash mismatch' in detail,(corrupt,absent)
            mixed_count+=1
        finally:bad.write_bytes(before);backup.rename(missing)

# VD03: every canonical spec field except its label is changed independently.
forged_count=0
for f in fields(V.PRODUCTION_SPEC):
    if f.name=='name':continue
    value=getattr(V.PRODUCTION_SPEC,f.name)
    if isinstance(value,str):changed=value+'-changed'
    elif isinstance(value,int):changed=value+1
    elif isinstance(value,tuple):changed=value+('changed',)
    else:
        changed=dict(value);k=next(iter(changed));v=changed[k];changed[k]=v+'-changed' if isinstance(v,str) else v+1
    forged=replace(V.PRODUCTION_SPEC,**{f.name:changed})
    with patch.object(V,'verify_pins',side_effect=AssertionError('forged spec read files')):
        report,code=V.run_verification(P,forged,scope='force-offline',archive_path=archive)
    assert code==1 and report['spec']=='rejected_forged_production' and report['production_provenance'] is False
    forged_count+=1
mapping_count=0
for key in ('pins','group_counts','well_counts','channel_transforms','fractions'):
    original=getattr(V.PRODUCTION_SPEC,key);caller=dict(original);spec=replace(V.PRODUCTION_SPEC,**{key:caller});first=next(iter(caller));caller[first]='changed'
    assert dict(getattr(spec,key))==dict(original)
    try:getattr(spec,key)[first]='changed'
    except TypeError:pass
    else:raise AssertionError('mutable spec map '+key)
    mapping_count+=1
spec_load=importlib.util.spec_from_file_location('verify_data_repair1_helpers',P/'tests/ai/data_model/test_verify_data.py');T=importlib.util.module_from_spec(spec_load);spec_load.loader.exec_module(T)
fixture=T.SyntheticFixture(cases/'synthetic-context');report,code=V.run_verification(fixture.root,fixture.spec(),scope='force-offline',archive_path=fixture.root/fixture.archive_rel)
assert code==0 and report['spec']=='synthetic_fixture' and report['production_provenance'] is False

# VD04: input protection probes use copies; even a regression cannot overwrite real inputs.
alias=copy_product('output-input-guards');tool=alias/'tools/verify_data.py';target=alias/'data/preprocessing.json'
guard_paths=[alias/rel for rel in relative]+[tool];probe_count=0
for path in guard_paths:
    assert V._protected_output_problem(path,alias,V.PRODUCTION_SPEC,archive,tool)
    assert V._protected_output_problem(path.parent/'..'/path.parent.name/path.name,alias,V.PRODUCTION_SPEC,archive,tool)
    probe_count+=2
assert V._protected_output_problem(archive,alias,V.PRODUCTION_SPEC,archive,tool);probe_count+=1
hardlink=alias/'hardlink-preprocessing.json';hardlink.hardlink_to(target)
for output in (target,target.parent/'..'/'data'/target.name,hardlink,tool):
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (target,hardlink,tool)}
    r=command([tool,'--scope','force-offline','--archive',archive,'--output',output],'verify-data-repair1-main-protect-'+str(len(commands)))
    doc=json.loads(r.stdout);assert r.returncode==1 and next(c for c in doc['checks'] if c['id']=='output_write')['status']=='failed'
    assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before}

real_output=cases/'actual-report.json'
r=command([P/'tools/verify_data.py','--scope','force-offline','--archive',archive,'--output',real_output],'verify-data-repair1-main-offline')
report=json.loads(r.stdout);assert r.returncode==0 and r.stdout==real_output.read_bytes() and report['status']=='passed_offline_identity_consistency_only'
assert report['counts']=={'inventory_members':118,'well_rows_total':2337639,'curves_total':2393,'parent_roots':117,'group_counts':{'train':81,'validation':17,'test':19},'well_counts':{'train':82,'validation':17,'test':19},'train_rows':1634292,'fitting_wells':82,'fitting_rows':1634292}
for args,name in (([],'full'),(['--scope','force-offline'],'missing-archive')):
    r=command([P/'tools/verify_data.py',*args],'verify-data-repair1-main-'+name);doc=json.loads(r.stdout)
    assert r.returncode==2 and doc['status']=='blocked' and doc['archive']['status']=='no_path' and len(doc['missing_full_gates'])==4
with patch.object(zipfile,'ZipFile',side_effect=AssertionError('ZIP member access')):
    guarded,code=V.run_verification(P,V.PRODUCTION_SPEC,scope='force-offline',archive_path=archive)
assert code==0 and guarded['software_facts']['zip_members_opened']==0 and guarded['unverified']['runtime_future_label_access']=='unknown_not_run'
child=json.loads((OUT/'verify-data-repair1-terminal.json').read_text())[0]['result']
result={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'contract_id':'DEEPEYE-HUMAN-LOCK-20261014/revision1','requirements_sha256':V.CONTRACT_REQUIREMENTS_SHA256,'design_commit':V.DESIGN_COMMIT,'job_id':'child-21d7bc6b0d79417487812570710ab15b','at_utc':datetime.now(timezone.utc).isoformat(),'unit_tests':48,'real_archive_skipped':0,'portable_tests':48,'portable_skipped':3,'json_race_cases':race_cases,'mixed_corruption_missing_cases':mixed_count,'canonical_spec_field_mutations':forged_count,'immutable_mapping_cases':mapping_count,'path_guard_probes':probe_count,'CLI_input_alias_cases':4,'commands':commands,'python_version':sys.version,'source_sha256':hashes,'real_offline_counts':report['counts'],'closed_findings':['VD01','VD02','VD03','VD04','VD05'],'acceptance':'passed_offline_software_foundation_only','C01':'not_run','default_full_exit_code':2,'remaining_full_gates':list(V.MISSING_FULL_GATES),'provider':child.get('provider'),'model':child.get('model'),'reasoning_effort':child.get('reasoning_effort'),'limits':['Byte stream hash and pinned metadata only, no LAS member parse or refit','No runtime future-label/truth or real/sim domain acceptance','No trained model/wire/board/AMD/system acceptance','Clean portable suite skips exactly3 real-archive cases; real C suite skips0']}
(OUT/'verify-data-repair1-main-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ('commands','source_sha256','limits')}))

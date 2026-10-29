"""C29-R1 narrow independent controls; no old suite execution.

python -B independent_r1_checks.py PUBLIC_DIR [--fixture-library PATH]
By default, keep the independent v1 fixture library independent_checks.py beside
this script. Only its fixture function is imported; its 66-check main is not run.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('public_directory',type=Path)
    parser.add_argument('--fixture-library',type=Path,default=Path(__file__).with_name('independent_checks.py'))
    args=parser.parse_args()
    module_path=args.public_directory.resolve()/'private_raw4_planner_abi_v1.py'
    fixture_lib=load('independent_fixture_only',args.fixture_library.resolve())
    module=load('c29_r1_frozen_subject',module_path)
    started=time.monotonic()
    rows=[]
    def run(name,enabled,mutate,expected):
        request=fixture_lib.fixture();request['enabled']=enabled;mutate(request)
        before=copy.deepcopy(request)
        record={'name':name,'enabled':enabled,'input_sha256':hashlib.sha256(fixture_lib.wire(request).encode()).hexdigest(),
                'expected':expected,'observed_core_calls':0}
        def profile(frame,event,arg):
            if event=='call' and frame.f_code is module._ORIGINAL.__code__:
                record['observed_core_calls']+=1
        old_profile=sys.getprofile()
        try:
            sys.setprofile(profile)
            result=module.recommend(request)
            record['output']={key:result[key] for key in ('status','reason','input_status','core_ran','independent_em_count')}
            if expected=='Rejected':raise AssertionError('malformed input returned result')
            assert all(result[k]==v for k,v in expected.items()),record['output']
            assert record['observed_core_calls']==int(result['core_ran'])
            assert result['authorization']=='none'
            assert result['candidate']==request['candidate']
            assert result['root_receipt']==request['root_receipt']
            assert json.loads(json.dumps(result,allow_nan=False))==result
            record['passed']=True
        except Exception as exc:
            record['exception']={'type':type(exc).__name__,'message':str(exc)}
            record['passed']=expected=='Rejected' and isinstance(exc,module.Rejected) and record['observed_core_calls']==0
        finally:
            sys.setprofile(old_profile)
        record['input_unchanged']=request==before
        record['passed']=record['passed'] and record['input_unchanged']
        rows.append(record)
    for enabled in (False,True):
        for retained in (None,0,1,5,10):
            def mutate(r,retained=retained):
                r['root_receipt']['source_admissions']=(None if retained is None else r['root_receipt']['source_admissions'][:retained])
            reason=('missing_source_admissions' if retained in (None,0) else 'missing_source_admission_index') if enabled else 'disabled'
            expected={'status':'STOP','input_status':'INPUT_UNAVAILABLE' if enabled else 'DISABLED','core_ran':False,'reason':reason}
            run('missing_prefix_'+str(retained),enabled,mutate,expected)
        for kind in ('nonzero_start','interior_gap','held_changed_in_prefix','complete_candidate_contradiction','wrong_registry_type','hidden_field_empty_prefix'):
            def malformed(r,kind=kind):
                a=r['root_receipt']['source_admissions']
                if kind=='nonzero_start':del a[0]
                elif kind=='interior_gap':del a[5]
                elif kind=='held_changed_in_prefix':
                    del a[10:];a[-1]['channel_counts'][0]+=1
                elif kind=='complete_candidate_contradiction':r['candidate']['channel_counts'][0]+=1
                elif kind=='wrong_registry_type':r['root_receipt']['source_admissions']={}
                else:
                    r['root_receipt']['source_admissions']=[]
                    r['root_receipt']['captures'][0]['hidden_truth']=1
            run(kind,enabled,malformed,'Rejected')
        expected={'status':'ADVISE' if enabled else 'STOP','core_ran':enabled,
                  'input_status':'COMPLETE_DIAGNOSTIC' if enabled else 'DISABLED'}
        run('complete_original_input',enabled,lambda _:None,expected)
    report={'scope':'SYNTHETIC_LOCAL_R1_ONLY_NO_AUTHENTICATION',
            'module_sha256':hashlib.sha256(module_path.read_bytes()).hexdigest(),
            'fixture_library_sha256':hashlib.sha256(args.fixture_library.read_bytes()).hexdigest(),
            'total_checks':len(rows),'passed':all(r['passed'] for r in rows),
            'elapsed_seconds':time.monotonic()-started,'cases':rows,
            'old_suites_run':False,'formal_acceptance':False}
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    sys.exit(main())

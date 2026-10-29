"""Narrow independent missing-association regression; CLI accepts public dir."""
import importlib.util
import json
from pathlib import Path
import sys
from independent_checks import fixture

public=Path(sys.argv[1]).resolve()
spec=importlib.util.spec_from_file_location('c29_missing_admission_subject',public/'private_raw4_planner_abi_v1.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
r=fixture()
# Keep the genuine original prefix0..9; current original candidate refers to10.
# No reindex, anchor reset, source mutation or omitted interior admission.
r['root_receipt']['source_admissions']=r['root_receipt']['source_admissions'][:-1]
result={'name':'valid_original_source_prefix_missing_referenced_tail', 'input':r,
        'expected':{'input_status':'INPUT_UNAVAILABLE','status':'STOP','core_ran':False}}
try:
    output=m.recommend(r)
    result['output']=output
    result['passed']=all(output.get(k)==v for k,v in result['expected'].items())
except Exception as exc:
    result['exception']={'type':type(exc).__name__,'message':str(exc)}
    result['passed']=False
print(json.dumps(result,indent=2))
sys.exit(0 if result['passed'] else 1)

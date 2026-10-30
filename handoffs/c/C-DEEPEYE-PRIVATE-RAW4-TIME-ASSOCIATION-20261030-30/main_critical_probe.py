"""Main's final limited public-example/identity audit, not an old test suite."""
from pathlib import Path
import copy, hashlib, importlib.util, json, sys
P=Path(sys.argv[1]).resolve()
spec=importlib.util.spec_from_file_location('main_c30_subject',P/'private_raw4_time_association_v1.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
examples=json.loads((P/'interface-examples.json').read_bytes())['examples']
results=[]
for example in examples:
 r=copy.deepcopy(example['input']); before=copy.deepcopy(r)
 calls=[]
 def profile(frame,event,arg):
  if event=='call' and frame.f_code is m._ORIGINAL.__code__:
   calls.append({'same_code':True,'private_globals':frame.f_globals is not m._ORIGINAL.__globals__,
                 'only_validate_replaced':all(frame.f_globals.get(k) is v for k,v in m._ORIGINAL.__globals__.items() if k!='_validate')})
 prior=sys.getprofile()
 try:sys.setprofile(profile); result=m.recommend_json(json.dumps(r,separators=(',',':')).encode())
 finally:sys.setprofile(prior)
 answer=json.loads(result)
 assert answer==example['output'], example['label']
 assert r==before and answer['authorization']=='none'
 assert len(calls)==int(answer['core_ran']) and all(all(c.values()) for c in calls)
 assert answer['candidate']['observation_identity']==r['candidate']['observation_identity']
 answer['candidate']['channel_counts'][0]=999
 assert r==before
 results.append({'example':example['label'],'output_exact':True,'json_roundtrip_full_identity':True,
                 'detached':True,'core_calls':calls,'bytes':len(result)})
print(json.dumps({'passed':True,'scope':'Four already published synthetic example payloads checked once through strict bytes entry on final source; no live Root',
 'source_sha256':hashlib.sha256((P/'private_raw4_time_association_v1.py').read_bytes()).hexdigest(),'checks':results,
 'full_chain':False,'formal_acceptance':False},indent=2))

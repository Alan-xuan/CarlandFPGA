"""Narrow C34 R1 checks. No old test/fixture imports.
Usage: python -B independent_r1_checks.py PUBLIC_DIR DATA_JSON OUTPUT_DIR
PUBLIC_DIR must retain the documented sibling frozen C32/C28 dependency layout.
DATA_JSON is the delivered independent-r1-data.json, containing exact old RED
bytes and synthetic input data. This script does not authenticate fixtures.
"""
import copy, hashlib, json, pathlib, sys, traceback, types

def enc(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x): return hashlib.sha256(x).hexdigest()
def line(x): return enc(x).decode()+'\n'

P=pathlib.Path(sys.argv[1]).resolve(); data_path=pathlib.Path(sys.argv[2]).resolve(); D=pathlib.Path(sys.argv[3]).resolve()
assert D!=P and P not in D.parents
D.mkdir(parents=True,exist_ok=True)
data=json.loads(data_path.read_bytes())
native_raw=data['synthetic_native_data_utf8'].encode()
assert sha(native_raw)==data['synthetic_native_sha256']
for c in data['original_red']:
 b=c['input_utf8'].encode(); assert len(b)==c['bytes'] and sha(b)==c['sha256']
path=P/'root_book_stale_composition_v1.py'; source=path.read_bytes()
assert sha(source)=='849d083885875668f2701fedd1c855e88c81174f312c6e0cfb0619706ef5e336'
loads=[]
def loading(f,e,a):
 if e=='call' and f.f_code.co_name=='<module>': loads.append(f.f_code.co_filename)
m=types.ModuleType('independent_c34_r1');m.__file__=str(path)
sys.setprofile(loading)
try: exec(compile(source,str(path),'exec'),m.__dict__)
finally: sys.setprofile(None)
assert sum(p.endswith('candidate_four_channel_planner_v1.py') for p in loads)==1
assert sum(p.endswith('private_raw4_time_association_v2.py') for p in loads)==1
assert not any(p.endswith(('root_book_projection_v1.py','private_raw4_time_association_v1.py')) for p in loads)
original=m._C32._ORIGINAL
assert original is m._C32._CORE_MODULE.recommend
global_ids={k:id(v) for k,v in original.__globals__.items()}
results=[]; journal=[]
def check(group,name,q,expected,needle=None,core=0,c32=0):
 raw=q if isinstance(q,bytes) else enc(q)
 counts={'core':0,'c32_json':0,'foreign_core':0}; output=None;result=None;error=None
 def observe(f,e,a):
  if e=='call':
   if f.f_code is original.__code__: counts['core']+=1
   elif f.f_code.co_name=='recommend' and f.f_code.co_filename.endswith('candidate_four_channel_planner_v1.py'): counts['foreign_core']+=1
   if f.f_code is m._C32.recommend_json.__code__: counts['c32_json']+=1
 sys.setprofile(observe)
 try:
  output=m.project_json(raw);result=json.loads(output);status=result['input_status']
 except m.Rejected as e: status='REJECT';error=str(e)
 except Exception: status='UNEXPECTED_EXCEPTION';error=traceback.format_exc()
 finally: sys.setprofile(None)
 passed=status==expected and counts=={'core':core,'c32_json':c32,'foreign_core':0}
 passed &= global_ids=={k:id(v) for k,v in original.__globals__.items()}
 if needle: passed &= error is not None and needle in error
 if result:
  passed &= result['authorization']=='none' and result['native_interval_atomic'] is False and result['core_ran']==bool(core)
  if expected=='INPUT_UNAVAILABLE': passed &= result['projection'] is None and result['c32_result'] is None
 entry={'group':group,'name':name,'expected':expected,'actual':status,'passed':bool(passed),'counts':counts,'error':error,'input_bytes':len(raw),'input_sha256':sha(raw),'output_bytes':len(output) if output else 0,'output_sha256':sha(output) if output else None}
 results.append(entry);journal.append({**entry,'input_utf8':raw.decode(),'output_utf8':output.decode() if output else None})
 (D/'input-output.json').write_bytes(enc(journal)+b'\n')
 print(json.dumps(entry,sort_keys=True),flush=True)
 if not passed:
  (D/(name+'.input.json')).write_bytes(raw)
  (D/(name+'.observed.json')).write_bytes(enc({**entry,'result':result})+b'\n')

for c in data['original_red']:
 check('exact_original_red',c['name'],c['input_utf8'].encode(),'REJECT','generation conflict' if 'generations' in c['name'] else 'context conflict')
base=json.loads(data['original_red'][0]['input_utf8'])
generation_case=json.loads(data['original_red'][2]['input_utf8'])
req=copy.deepcopy(base['external']['captures'][0])
cap=copy.deepcopy(generation_case['external']['captures'][1])
v=json.loads(cap['capture_raw']);v['generation']=json.loads(generation_case['external']['captures'][0]['capture_raw'])['generation']
for lane in v['captures']:lane['raw_words'][8]=v['generation']
cap['capture_raw']=line(v);cap['capture_sha256']=sha(cap['capture_raw'].encode())
def partial(records):
 q=copy.deepcopy(base);q['external']['captures']=copy.deepcopy(records);return q
check('new','new_mixed_request_then_capture',partial([None,req,cap]),'INPUT_UNAVAILABLE')
check('new','new_mixed_capture_then_request',partial([cap,None,req]),'INPUT_UNAVAILABLE')
native=json.loads(native_raw); config=copy.deepcopy(native['external']['config'])
q=partial([req]);q['external']['config']=copy.deepcopy(config)
check('new','new_request_without_generation_actual_config',q,'INPUT_UNAVAILABLE')
q=partial([cap]);q['external']['config']=copy.deepcopy(config);q['external']['config']['generation']+=3
check('new','new_capture_vs_external_generation',q,'REJECT','generation conflict')
q=partial([req]);q['enabled']=False;q['external']['config']=copy.deepcopy(config);q['external']['config']['context']['clock_domain_id']='5'*32
check('new','new_disabled_request_vs_external_clock',q,'REJECT','context conflict')
# A request without generation appears before two mutually conflicting capture
# generations. Its retained absent-capture hash differs from both present raws.
unknown=copy.deepcopy(base['external']['captures'][1]);u=json.loads(unknown['request_raw']);u['context']=json.loads(req['request_raw'])['context'];unknown['request_raw']=line(u)
q=partial([unknown]+generation_case['external']['captures'])
check('new','new_unknown_generation_does_not_hide_later_conflict',q,'REJECT','generation conflict')
native['external']['config']['goal_m']=[0.333,0.0625,2.625]
check('new','new_complete_goal_variant_single_original_core',native,'COMPLETE_DIAGNOSTIC',core=1,c32=1)
assert path.read_bytes()==source
summary={'runtime_sha256':sha(source),'data_sha256':sha(data_path.read_bytes()),'exact_red_cases':3,'new_cases':7,'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results),'results':results,'module_loads':loads,'old_suites_run':False,'jobs':[],'subprocesses':[]}
(D/'results.json').write_bytes(enc(summary)+b'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('results','module_loads')},sort_keys=True),flush=True)
sys.exit(int(summary['failed']>0))

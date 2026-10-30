"""Portable C30-R1 closure. CLI: python -B independent_r1_checks.py PUBLIC_DIR replay|new.
Requires adjacent independent_c30_checks.py and original-failed-inputs.json.
Imports only our independent fixture module; never imports author tests or runs old suites.
"""
import copy,hashlib,importlib.util,json,sys,time
from pathlib import Path
import independent_c30_checks as f

def many_actions(count):
 r=f.fixture();r['root_receipt']['action_registry']['actions']=[{'receipt_id':None,'action_id':'action-'+str(i),'state':'executed','observation_capture_sha256':r['candidate']['observation_identity']['capture_sha256'],'at_qpc_ns':r['now_qpc_ns'],'from_pose':f.pose(),'to_pose':f.pose(),'from_pose_revision':None,'to_pose_revision':None} for i in range(count)]
 return r

def replay_cases():
 cases=[]
 for missing in ('config','current_pose','source_admissions','captures','pose_book_id','adc_call'):
  for enabled in (True,False):
   r=many_actions(32);r['enabled']=enabled
   if missing=='pose_book_id':r['root_receipt']['config'][missing]=None
   elif missing=='adc_call':r['root_receipt']['captures'][0][missing]=None
   else:r['root_receipt'][missing]=None
   cases.append(('combined33_missing_'+missing+'_'+str(enabled),r,'Rejected'))
 return cases

def new_cases():
 cases=[]
 def add(name,r,want):cases.append((name,r,want))
 for enabled in (True,False):
  missing_status='INPUT_UNAVAILABLE' if enabled else 'DISABLED'
  for count in (31,32):
   r=many_actions(1);r['enabled']=enabled;root=r['root_receipt'];root['config']=None
   root['captures']=[copy.deepcopy(root['captures'][0]) for _ in range(count)]
   add('actual_receipts_'+str(count)+'_plus1action_'+str(enabled),r,missing_status if count==31 else 'Rejected')
  for nullpart in ('registry','actions'):
   r=f.fixture();r['enabled']=enabled;root=r['root_receipt']
   if nullpart=='registry':root['action_registry']=None
   else:root['action_registry']['actions']=None
   add('null_'+nullpart+'_remains_missing_'+str(enabled),r,missing_status)
   r=copy.deepcopy(r);root=r['root_receipt'];root['config']=None
   root['captures']=[copy.deepcopy(root['captures'][0]) for _ in range(32)]
   add('32receipts_null_'+nullpart+'_config_missing_'+str(enabled),r,missing_status)
  r=many_actions(31);r['enabled']=enabled;r['history']=[copy.deepcopy(r['candidate'])];r['root_receipt']['captures']=None
  add('candidate_count_dominates_missing_receipts_'+str(enabled),r,'Rejected')
  r=f.fixture();r['enabled']=enabled;r['root_receipt']['config']=None;r['root_receipt']['action_registry']=None
  r['root_receipt']['captures']=[None]*33
  add('33receipt_independent_cap_null_registry_'+str(enabled),r,'Rejected')
 # Nearby successful original-core paths; same independent receipt generator,
 # fresh source ticks120(native100 retained)/150(native) exercise the new guard.
 add('nearby_native150_single_core',f.fixture((150,)),'COMPLETE_DIAGNOSTIC')
 add('nearby_held100_120_single_original_em',f.fixture((100,120)),'COMPLETE_DIAGNOSTIC')
 return cases

def main():
 start=time.monotonic();public=Path(sys.argv[1]).resolve();mode=sys.argv[2]
 if mode not in ('replay','new'):raise ValueError('mode replay|new required')
 path=public/'private_raw4_time_association_v1.py'
 expected='abaa06d10ab68f0bee721bf1a6d9278fc000446112ac559362079ad63afc686d'
 assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
 spec=importlib.util.spec_from_file_location('c30_r1_frozen',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 original=m._ORIGINAL;oldglobals=dict(original.__globals__)
 original_failed=json.loads(Path(__file__).with_name('original-failed-inputs.json').read_text()) if mode=='replay' else {}
 selected=replay_cases() if mode=='replay' else new_cases();results=[]
 if mode=='replay':assert set(original_failed)=={x[0] for x in selected} and len(selected)==12
 for name,r,want in selected:
  before=copy.deepcopy(r);encoded=f.raw(r).encode();row={'name':name,'expected':want,'input_sha256':hashlib.sha256(encoded).hexdigest(),'input_bytes':len(encoded),'core_calls':0,'isolated_globals':True}
  if mode=='replay':
   row['matches_original_failed_input']=row['input_sha256']==original_failed[name]['input_sha256'] and row['input_bytes']==original_failed[name]['input_bytes']
   assert row['matches_original_failed_input'],'fixture changed before replay: '+name
  def profile(frame,event,arg):
   if event=='call' and frame.f_code is original.__code__:
    row['core_calls']+=1;row['isolated_globals'] &= frame.f_globals is not original.__globals__ and all(frame.f_globals.get(k) is v for k,v in oldglobals.items() if k!='_validate')
  previous=sys.getprofile()
  try:
   sys.setprofile(profile);out=m.recommend(r)
   row['result']={k:out[k] for k in ('input_status','status','core_ran','reason','independent_em_count')}
   assert out['input_status']==want
   assert out['authorization']=='none' and out['candidate']==r['candidate'] and out['root_receipt']==r['root_receipt']
   assert json.loads(json.dumps(out,allow_nan=False))==out
   assert out['candidate'] is not r['candidate'] and out['root_receipt'] is not r['root_receipt']
   if want=='COMPLETE_DIAGNOSTIC':
    assert out['status']=='ADVISE' and out['core_ran'] and row['core_calls']==1 and row['isolated_globals'] and out['independent_em_count']==1
    assert len(out['map_cells'])==1
    cell=out['map_cells'][0];native=r['history'][0] if r['history'] else r['candidate']
    assert cell['original_em_qpc_ns']==f.ANCHOR+native['source_time']['em_tick_ms']*f.NS
    assert cell['observation_identity']==native['observation_identity']
   else:assert out['status']=='STOP' and not out['core_ran'] and row['core_calls']==0
   row['passed']=True
  except Exception as e:
   row['exception']={'type':type(e).__name__,'message':str(e)}
   row['passed']=want=='Rejected' and isinstance(e,m.Rejected) and row['core_calls']==0
  finally:sys.setprofile(previous)
  row['input_unchanged']=r==before;row['globals_unchanged']=all(original.__globals__.get(k) is v for k,v in oldglobals.items())
  row['passed'] &= row['input_unchanged'] and row['globals_unchanged'];results.append(row)
 report={'scope':'C30_R1_NARROW_INDEPENDENT_CLOSURE','mode':mode,'source_sha256':expected,'total':len(results),'passed':all(x['passed'] for x in results),'elapsed_seconds':time.monotonic()-start,'cases':results,'old_suites_run':False,'author_tests_imported':False,'physical_or_actual_Root_run':False}
 print(json.dumps(report,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':sys.exit(main())

"""Prepared C32-R1 closure; run only after explicit main freeze activation.
python -B independent_counter_closure.py PUBLIC_DIR FROZEN_SHA replay|new OUTPUT_DIR
Only adjacent independent fixture builder is imported. No old cases/main/suite.
"""
import copy,hashlib,importlib.util,json,sys,time
from pathlib import Path
import independent_fixture as f

def replace_ref(obj,old,new):
 if isinstance(obj,dict):
  for k,v in obj.items():
   if v==old:obj[k]=new
   elif isinstance(v,(dict,list)):replace_ref(v,old,new)
 elif isinstance(obj,list):
  for i,v in enumerate(obj):
   if v==old:obj[i]=new
   elif isinstance(v,(dict,list)):replace_ref(v,old,new)

def edit_capture(r,index,edit):
 rec=r['root_receipt']['captures'][index];old=rec['capture_sha256'];cap=json.loads(rec['capture_raw']);edit(cap)
 rec['capture_raw']=f.raw(cap);replace_ref(r,old,f.sha(rec['capture_raw']))

def counter_baseline(cap,base):
 seq=cap['request_seq']
 for ch,lane in enumerate(cap['captures']):lane['pipeline_counters']=[base[0]+4*seq,base[1]+seq,base[2]+4*(seq-1)+ch+1]
 cap['final_counters']=[base[0]+4*seq,base[1]+seq,base[2]+4*seq]

def shift_component(cap,component,delta):
 for lane in cap['captures']:lane['pipeline_counters'][component]+=delta
 cap['final_counters'][component]+=delta

def new_cases():
 result=[]
 def add(name,r,want):result.append((name,f.raw(r).encode(),want))
 for enabled in (True,False):
  status='UNAVAILABLE' if enabled else 'DISABLED'
  r=f.fixture((250,));r['enabled']=enabled;r['root_receipt']['config']=None
  edit_capture(r,0,lambda c:c['captures'][2]['pipeline_counters'].__setitem__(2,c['captures'][2]['pipeline_counters'][2]+1))
  add('third_counter_lane_progression_'+str(enabled),r,'Rejected')
  r=f.fixture((250,));r['enabled']=enabled;r['root_receipt']['config']=None
  edit_capture(r,0,lambda c:c['captures'][1]['pipeline_counters'].__setitem__(1,c['captures'][1]['pipeline_counters'][1]+1))
  add('second_counter_lane_identity_'+str(enabled),r,'Rejected')
  for component in range(3):
   r=f.fixture((250,));r['enabled']=enabled;r['root_receipt']['config']=None;baseline=[0,0,0];baseline[component]=-1
   edit_capture(r,0,lambda c:counter_baseline(c,baseline))
   add('nonnegative_baseline_component_'+str(component)+'_'+str(enabled),r,'Rejected')
  r=f.fixture((250,));r['enabled']=enabled;r['root_receipt']['config']=None
  edit_capture(r,0,lambda c:counter_baseline(c,[0,0,0]))
  add('zero_feasible_baseline_missing_config_'+str(enabled),r,status)
 for component in range(3):
  r=f.fixture((250,260));r['root_receipt']['config']=None
  edit_capture(r,1,lambda c:shift_component(c,component,1))
  add('cross_capture_component_'+str(component)+'_internally_consistent_wrong_delta',r,'Rejected')
 r=f.fixture((250,260,270));r['root_receipt']['config']=None;r['root_receipt']['captures'][1]['capture_raw']=None
 edit_capture(r,2,lambda c:shift_component(c,0,1));add('missing_middle_raw_does_not_hide_first_last_counter_delta',r,'Rejected')
 r=f.fixture((250,260,270));r['history']=r['history'][:1];r['root_receipt']['captures']=[r['root_receipt']['captures'][0],r['root_receipt']['captures'][2]]
 add('actual_seq1_to3_gap_valid_config_present',r,'ADVISE')
 r=copy.deepcopy(r);r['root_receipt']['config']=None
 edit_capture(r,1,lambda c:shift_component(c,2,1));add('seq_gap_uses_actual_request_seq_delta',r,'Rejected')
 r=f.fixture((250,260));r['root_receipt']['config']=None;r['root_receipt']['captures'][0]['capture_raw']=None
 edit_capture(r,1,lambda c:c['final_counters'].__setitem__(0,c['final_counters'][0]+1));add('missing_first_raw_does_not_hide_later_internal_final_mismatch',r,'Rejected')
 r=f.fixture((250,260));r['root_receipt']['config']=None;add('consistent_capture_pair_missing_config_no_inferred_proof',r,'UNAVAILABLE')
 r=f.fixture((250,));r['root_receipt']['config']['baseline_counters']=[0,0,0]
 edit_capture(r,0,lambda c:counter_baseline(c,[0,0,0]));add('real_zero_baseline_fresh_native_core',r,'ADVISE')
 r=f.fixture((250,260));add('real_config_fresh_held_core',r,'ADVISE')
 r=f.fixture((250,));edit_capture(r,0,lambda c:shift_component(c,0,1));add('actual_config_absolute_mismatch_still_rejected',r,'Rejected')
 return result

def replay_cases():
 manifest=json.loads(Path(__file__).with_name('original-red-inputs.json').read_text());rows=[]
 for row in manifest['cases']:
  b=row['input_utf8'].encode('utf-8');assert len(b)==row['input_bytes'] and hashlib.sha256(b).hexdigest()==row['input_sha256']
  rows.append((row['name'],b,'Rejected'))
 assert len(rows)==4;return rows

def main():
 start=time.monotonic();public=Path(sys.argv[1]).resolve();sha=sys.argv[2];mode=sys.argv[3];O=Path(sys.argv[4]).resolve()
 assert mode in ('replay','new') and len(sha)==64 and sha!='30466fc69099112010c72cdaec7c097ce38c0b43a1307a6f18ad4c58390e6f77'
 p=public/'private_raw4_time_association_v2.py';assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
 O.mkdir(parents=True,exist_ok=True)
 spec=importlib.util.spec_from_file_location('frozen_c32_r1_closure',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 original=m._ORIGINAL;g=dict(original.__globals__);results=[]
 for i,(name,b,want) in enumerate(replay_cases() if mode=='replay' else new_cases(),1):
  r=json.loads(b);prefix=f'{i:02d}-{name}';(O/(prefix+'.input.json')).write_bytes(b)
  row={'name':name,'expected':want,'input_sha256':hashlib.sha256(b).hexdigest(),'input_bytes':len(b),'core_calls':0,'isolated_globals':True}
  def profile(frame,event,arg):
   if event=='call' and frame.f_code is original.__code__:
    row['core_calls']+=1;row['isolated_globals'] &= frame.f_globals is not original.__globals__ and all(frame.f_globals.get(k) is v for k,v in g.items() if k!='_validate')
  old=sys.getprofile()
  try:
   sys.setprofile(profile);out=json.loads(m.recommend_json(b));(O/(prefix+'.output.json')).write_text(json.dumps(out,indent=2),encoding='utf-8')
   row['result']={k:out[k] for k in ('input_status','status','core_ran','reason')}
   expected={'ADVISE':('COMPLETE_DIAGNOSTIC','ADVISE',True),'UNAVAILABLE':('INPUT_UNAVAILABLE','STOP',False),'DISABLED':('DISABLED','STOP',False)}
   assert want in expected and (out['input_status'],out['status'],out['core_ran'])==expected[want]
   assert out['root_receipt']==r['root_receipt'] and out['candidate']==r['candidate'] and out['authorization']=='none'
   assert row['core_calls']==int(out['core_ran']) and row['isolated_globals']
   if r['root_receipt']['config'] is None:assert out['root_receipt']['config'] is None and not out['core_ran']
   row['passed']=True
  except Exception as e:
   row['exception']={'type':type(e).__name__,'message':str(e)};(O/(prefix+'.exception.json')).write_text(json.dumps(row['exception'],indent=2),encoding='utf-8')
   row['passed']=want=='Rejected' and isinstance(e,m.Rejected) and row['core_calls']==0
  finally:sys.setprofile(old)
  row['globals_unchanged']=all(original.__globals__.get(k) is v for k,v in g.items());row['passed'] &= row['globals_unchanged'];results.append(row)
 report={'scope':'C32_R1_NARROW_NEW_INDEPENDENT_CLOSURE','mode':mode,'source_sha256':sha,'total':len(results),'passed':all(x['passed'] for x in results),'elapsed_seconds':time.monotonic()-start,'cases':results,'old_suites_run':False}
 print(json.dumps(report,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':sys.exit(main())

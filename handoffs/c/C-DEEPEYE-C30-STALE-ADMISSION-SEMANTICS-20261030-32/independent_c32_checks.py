"""Independent NEW C32 controls. python -B independent_c32_checks.py PUBLIC_DIR EVIDENCE_DIR
No author/old tests imported or called; only adjacent independent fixture builder.
Full raw requests/responses/exceptions are written under the requested evidence dir.
"""
import copy,hashlib,importlib.util,json,sys,time
from pathlib import Path
import independent_fixture as f
SHA='30466fc69099112010c72cdaec7c097ce38c0b43a1307a6f18ad4c58390e6f77'
def replace_ref(obj,old,new):
 if isinstance(obj,dict):
  for k,v in obj.items():
   if v==old:obj[k]=new
   elif isinstance(v,(dict,list)):replace_ref(v,old,new)
 elif isinstance(obj,list):
  for i,v in enumerate(obj):
   if v==old:obj[i]=new
   elif isinstance(v,(dict,list)):replace_ref(v,old,new)

def capture_edit(r,index,edit):
 rec=r['root_receipt']['captures'][index];old=rec['capture_sha256'];raw=json.loads(rec['capture_raw']);edit(raw)
 rec['capture_raw']=f.raw(raw);new=f.sha(rec['capture_raw']);replace_ref(r,old,new)

def late(kind='native',age=100000001):
 r=f.fixture((200,)) if kind=='native' else f.fixture((200,210))
 c=r['candidate'];rec=r['root_receipt']['captures'][-1];t=c['source_time'];nom=f.ANCHOR+t['em_tick_ms']*f.NS
 received=nom+age;r['root_receipt']['source_admissions'][-1]['received_qpc_ns']=received;t['admission_received_monotonic_ns']=received
 ident=c['observation_identity'];ident['original_host_injection_qpc_ns']=[received]*4;ident['receiver_upper_qpc_ns']=received
 t['adc_source_age_ns']=received-(f.ANCHOR+t['adc_tick_ms']*f.NS);t['em_source_age_ns']=age
 flags=c['diagnostic_flags'];flags['source_fresh_at_capture']=age<=100000000;flags['injection_to_receiver_upper_ns']=0;flags['target100ms_met']=True
 request=json.loads(rec['request_raw']);request['original_host_qpc_ns']=[received]*4;rec['request_raw']=f.raw(request);ident['request_sha256']=f.sha(rec['request_raw'])
 def edit(cap):
  cap['request_sha256']=ident['request_sha256']
  for lane in cap['captures']:lane['raw_words'][2:4]=[received&0xffffffff,received>>32]
 capture_edit(r,-1,edit);f.now_at(r,received);return r

def earlier_stale():
 r=f.fixture((200,));items=r['root_receipt']['source_admissions'];items[10]['received_qpc_ns']=f.ANCHOR+200000001
 for i in range(11,len(items)):items[i]['received_qpc_ns']=max(items[i]['received_qpc_ns'],items[i-1]['received_qpc_ns'])
 return r

def action(r,name='known-action'):
 return {'receipt_id':None,'action_id':name,'state':'executed','observation_capture_sha256':r['candidate']['observation_identity']['capture_sha256'],'at_qpc_ns':r['now_qpc_ns'],'from_pose':f.pose(),'to_pose':f.pose(),'from_pose_revision':None,'to_pose_revision':None}

def cases():
 out=[]
 def add(name,r,want):out.append((name,r,want))
 add('new_fresh_native200',f.fixture((200,)),'ADVISE');add('new_fresh_held200_210',f.fixture((200,210)),'ADVISE')
 for kind in ('native','held'):
  for age in (100000000,100000001):add(kind+'_admission_age_'+str(age),late(kind,age),'ADVISE' if age==100000000 else 'UNAVAILABLE')
 for enabled in (True,False):
  r=late();r['enabled']=enabled;r['root_receipt']['config']=None;add('stale_missing_config_'+str(enabled),r,'UNAVAILABLE' if enabled else 'DISABLED')
  r=late();r['enabled']=enabled;r['root_receipt']['config']=None;r['root_receipt']['captures'][0]['request_raw']=None
  capture_edit(r,0,lambda c:c['captures'][2]['raw_words'].__setitem__(0,1741))
  add('stale_missing_config_request_bad_returned_word_'+str(enabled),r,'Rejected')
  r=late();r['enabled']=enabled;r['root_receipt']['config']=None
  capture_edit(r,0,lambda c:c['captures'][1]['pipeline_counters'].__setitem__(0,c['captures'][1]['pipeline_counters'][0]+1))
  add('stale_missing_config_internal_lane_counter_disagreement_'+str(enabled),r,'Rejected')
  r=late();r['enabled']=enabled;r['root_receipt']['config']=None
  capture_edit(r,0,lambda c:c['final_counters'].__setitem__(2,c['final_counters'][2]+1))
  add('stale_missing_config_final_counter_disagrees_last_lane_'+str(enabled),r,'Rejected')
 r=late();r.pop('enabled');add('stale_default_disabled',r,'DISABLED')
 add('older_stale_prefix_latest_capture_fresh',earlier_stale(),'UNAVAILABLE')
 for fault in ('index','received_order','quality'):
  r=earlier_stale();r['root_receipt']['config']=None;a=r['root_receipt']['source_admissions'][18]
  if fault=='index':a['index']+=1
  elif fault=='received_order':a['received_qpc_ns']-=1
  else:a['quality']&=~8;a['channel_counts'][3]=None
  add('early_stale_missing_config_later_'+fault,r,'Rejected')
 r=late();r['root_receipt']['current_pose']=None;r['root_receipt']['captures'][0]['adc_pose']['pose_read']['end_qpc_ns']=r['now_qpc_ns']+1
 add('stale_missing_current_future_read',r,'Rejected')
 r=late();r['root_receipt']['config']=None;r['root_receipt']['source_admissions'][0]['received_qpc_ns']=f.ANCHOR-1
 add('stale_missing_config_negative_earlier_age',r,'Rejected')
 r=late();r['root_receipt']['captures'][0]['capture_raw']=None;req=json.loads(r['root_receipt']['captures'][0]['request_raw']);req['context']['session_id']='wrong-but-valid';r['root_receipt']['captures'][0]['request_raw']=f.raw(req)
 add('missing_capture_does_not_hide_supplied_request_identity',r,'Rejected')
 r=late('held');r['root_receipt']['config']=None;r['root_receipt']['captures'][0]['em_pose']['valid_span']=None;r['root_receipt']['captures'][-1]['em_pose']['pose_read']['end_qpc_ns']+=1
 add('stale_missing_config_native_span_held_read_changed',r,'Rejected')
 r=late('held');r['root_receipt']['config']=None;r['root_receipt']['captures'][-1]['em_origin_capture_sha256']=r['candidate']['observation_identity']['capture_sha256']
 add('stale_missing_config_held_origin_points_to_self',r,'Rejected')
 r=late('held');r['history']=[];r['root_receipt']['captures']=r['root_receipt']['captures'][1:]
 add('stale_native_origin_absent_still_missing',r,'UNAVAILABLE')
 r=late();r['root_receipt']['config']=None;a=action(r);r['root_receipt']['action_registry']['actions']=[a,copy.deepcopy(a)]
 add('stale_missing_config_execution_receipt_duplicate_action',r,'Rejected')
 r=late();r['root_receipt']['current_pose']=None;r['root_receipt']['action_registry']['actions']=[action(r)];r['root_receipt']['captures'][0]['cause_action_id']='known-action'
 add('stale_missing_current_execution_receipt_future_cause',r,'Rejected')
 r=late();r['root_receipt']['current_pose']=None;a=action(r);a['at_qpc_ns']=r['candidate']['observation_identity']['receiver_upper_qpc_ns']-1;r['root_receipt']['action_registry']['actions']=[a]
 add('stale_missing_current_execution_receipt_before_observation',r,'Rejected')
 r=late();r['enabled']=False;r['root_receipt']['config']=None;r['root_receipt']['action_registry']['actions']=[action(r,'a'+str(i)) for i in range(32)]
 add('stale_disabled_missing_config_combined33',r,'Rejected')
 r=late();r['enabled']=False;r['root_receipt']['config']=None;r['root_receipt']['captures']=[None]*32;r['root_receipt']['action_registry']['actions']=[action(r)]
 add('stale_disabled_receipt_count_combined33',r,'Rejected')
 r=f.fixture((10000,));r['root_receipt']['config']=None;r['root_receipt']['source_admissions'].append(copy.deepcopy(r['root_receipt']['source_admissions'][-1]));add('missing_config_original_prefix1002',r,'Rejected')
 r=late();r['root_receipt']['config']=None;r['root_receipt']['captures'][0]['adc_pose']['valid_span']['through_qpc_ns']=1<<63;add('uint63_endpoint_overflow',r,'Rejected')
 r=late();r['root_receipt']['config']=None;r['root_receipt']['captures'][0]['adc_pose']['pose_read']['begin_qpc_ns']=float(r['root_receipt']['captures'][0]['adc_pose']['pose_read']['begin_qpc_ns']);add('uint63_float_not_accepted',r,'Rejected')
 r=late();r['root_receipt']['config']=None;r['root_receipt']['captures'][0]['adc_pose']['pose_revision']=True;add('revision_bool_not_uint63',r,'Rejected')
 r=late();r['root_receipt']['captures'][0]['request_raw']='{"schema":1,'+r['root_receipt']['captures'][0]['request_raw'][1:];r['root_receipt']['config']=None;add('stale_missing_config_duplicate_raw_key',r,'Rejected')
 return out

def main():
 start=time.monotonic();public=Path(sys.argv[1]).resolve();O=Path(sys.argv[2]).resolve();O.mkdir(parents=True,exist_ok=True)
 p=public/'private_raw4_time_association_v2.py';assert hashlib.sha256(p.read_bytes()).hexdigest()==SHA
 spec=importlib.util.spec_from_file_location('frozen_c32_independent',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 original=m._ORIGINAL;g=dict(original.__globals__);results=[]
 for n,(name,r,want) in enumerate(cases(),1):
  raw=f.raw(r).encode();base=copy.deepcopy(r);prefix=f'{n:02d}-{name}';(O/(prefix+'.input.json')).write_bytes(raw)
  row={'name':name,'expected':want,'input_sha256':hashlib.sha256(raw).hexdigest(),'input_bytes':len(raw),'input_file':prefix+'.input.json','core_calls':0,'isolated_globals':True}
  def profile(frame,event,arg):
   if event=='call' and frame.f_code is original.__code__:
    row['core_calls']+=1;row['isolated_globals'] &= frame.f_globals is not original.__globals__ and all(frame.f_globals.get(k) is v for k,v in g.items() if k!='_validate')
  old=sys.getprofile()
  try:
   sys.setprofile(profile);ans=json.loads(m.recommend_json(raw))
   (O/(prefix+'.output.json')).write_text(json.dumps(ans,indent=2),encoding='utf-8')
   row['result']={k:ans[k] for k in ('input_status','status','core_ran','reason','independent_em_count')}
   status={'ADVISE':('COMPLETE_DIAGNOSTIC','ADVISE',True),'UNAVAILABLE':('INPUT_UNAVAILABLE','STOP',False),'DISABLED':('DISABLED','STOP',False)}
   assert want in status and (ans['input_status'],ans['status'],ans['core_ran'])==status[want]
   assert ans['candidate']==r['candidate'] and ans['root_receipt']==r['root_receipt'] and ans['authorization']=='none'
   assert row['core_calls']==int(ans['core_ran']) and row['isolated_globals']
   if want=='ADVISE':
    assert ans['independent_em_count']==1
    native=r['history'][0] if r['history'] else r['candidate'];cell=ans['map_cells'][0]
    assert cell['original_em_qpc_ns']==f.ANCHOR+native['source_time']['em_tick_ms']*f.NS and cell['observation_identity']==native['observation_identity']
   row['passed']=True
  except Exception as e:
   row['exception']={'type':type(e).__name__,'message':str(e)}
   (O/(prefix+'.exception.json')).write_text(json.dumps(row['exception'],indent=2),encoding='utf-8')
   row['passed']=want=='Rejected' and isinstance(e,m.Rejected) and row['core_calls']==0
  finally:sys.setprofile(old)
  row['input_unchanged']=base==r;row['globals_unchanged']=all(original.__globals__.get(k) is v for k,v in g.items());row['passed'] &= row['input_unchanged'] and row['globals_unchanged'];results.append(row)
 report={'scope':'NEW_C32_INDEPENDENT_FOCUSED','source_sha256':SHA,'total':len(results),'passed':all(x['passed'] for x in results),'elapsed_seconds':time.monotonic()-start,'cases':results,'author_or_old_suite_imported':False,'actual_Root_or_board_run':False}
 print(json.dumps(report,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':sys.exit(main())

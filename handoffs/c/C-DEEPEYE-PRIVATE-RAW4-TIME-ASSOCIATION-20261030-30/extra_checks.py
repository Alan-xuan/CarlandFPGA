"""Portable independent extra C30 probes. CLI: python -B extra_checks.py PUBLIC_DIR."""
from pathlib import Path
import sys,json,copy,importlib.util,hashlib,time
import independent_c30_checks as f

def main():
 p=Path(sys.argv[1]).resolve()/'private_raw4_time_association_v1.py'
 spec=importlib.util.spec_from_file_location('frozen_extra_c30',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 rows=[]
 def check(name,request,expected,bytes_entry=False):
  encoded=request if type(request) is bytes else f.raw(request).encode(); calls=[]
  def profile(frame,event,arg):
   if event=='call' and frame.f_code is m._ORIGINAL.__code__:calls.append(1)
  row={'name':name,'expected':expected,'input_sha256':hashlib.sha256(encoded).hexdigest(),'input_bytes':len(encoded)}
  old=sys.getprofile()
  try:
   sys.setprofile(profile);out=m.recommend_json(request) if bytes_entry else m.recommend(request)
   if type(out) is bytes:out=json.loads(out)
   row['result']={k:out[k] for k in ('input_status','status','core_ran','reason')};row['output_bytes']=len(m._json_bytes(out))
   row['passed']=expected==out['input_status']
  except Exception as e:
   row['exception']={'type':type(e).__name__,'message':str(e)};row['passed']=expected=='Rejected' and isinstance(e,m.Rejected)
  finally:sys.setprofile(old)
  row['core_calls']=len(calls);row['passed'] &= not calls;rows.append(row)
 def many_actions(count):
  r=f.fixture();root=r['root_receipt'];root['action_registry']['actions']=[{'receipt_id':None,'action_id':'action-'+str(i),'state':'executed','observation_capture_sha256':r['candidate']['observation_identity']['capture_sha256'],'at_qpc_ns':r['now_qpc_ns'],'from_pose':f.pose(),'to_pose':f.pose(),'from_pose_revision':None,'to_pose_revision':None} for i in range(count)]
  return r
 for missing in ('config','current_pose','source_admissions','captures','pose_book_id','adc_call'):
  for enabled in (True,False):
   r=many_actions(32);r['enabled']=enabled
   if missing=='pose_book_id':r['root_receipt']['config'][missing]=None
   elif missing=='adc_call':r['root_receipt']['captures'][0][missing]=None
   else:r['root_receipt'][missing]=None
   check('combined33_missing_'+missing+'_'+str(enabled),r,'Rejected')
 r=many_actions(32);check('combined33_complete_other_evidence',r,'Rejected')
 r=many_actions(31);check('combined32_missing_execution_receipt',r,'INPUT_UNAVAILABLE')
 for enabled in (True,False):
  r=f.fixture();r['enabled']=enabled
  b=f.raw(r).encode();b=b'{"schema_version":1,'+b[1:]
  check('duplicate_envelope_key_'+str(enabled),b,'Rejected',True)
  for field in ('request_raw','capture_raw'):
   r=f.fixture();r['enabled']=enabled;r['root_receipt']['config']=None
   line=r['root_receipt']['captures'][0][field];r['root_receipt']['captures'][0][field]='{"schema":1,'+line[1:]
   check('duplicate_'+field+'_missing_config_'+str(enabled),r,'Rejected')
 # Public early return deliberately supplies unavailable config, but otherwise
 # shape-valid original raw JSON with legal trailing whitespace. No core entry.
 r=f.fixture();r['enabled']=False;r['root_receipt']['config']=None
 base=copy.deepcopy(r['root_receipt']['captures'][0]);r['root_receipt']['captures']=[copy.deepcopy(base) for _ in range(32)]
 def sized(extra):
  v=copy.deepcopy(r);remaining=extra
  for rec in v['root_receipt']['captures']:
   for field in ('request_raw','capture_raw'):
    n=min(remaining,16384-len(rec[field].encode()));rec[field]=rec[field][:-1]+' '*n+'\n';remaining-=n
  assert remaining==0
  return v
 base_size=len(m._json_bytes(r));max_padding=sum(16384-len(rec[k].encode()) for rec in r['root_receipt']['captures'] for k in ('request_raw','capture_raw'))
 target=m.MAX_BYTES-100;assert 0<target-base_size<=max_padding
 near=sized(target-base_size);assert len(m._json_bytes(near))==target
 check('public_disabled_output_exceeds_1MiB_with_input_below_limit',near,'Rejected')
 # Adjacent lower size proves output budget is reachable and not a generic reject.
 below=sized(target-base_size-4096);check('public_disabled_output_4KiB_below_boundary',below,'DISABLED')
 out={'scope':'NEW_C30_EXTRA_CONTROLS_SYNTHETIC','source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'total':len(rows),'passed':all(x['passed'] for x in rows),'cases':rows,'old_suites_run':False}
 print(json.dumps(out,indent=2));return 0 if out['passed'] else 1
if __name__=='__main__':sys.exit(main())

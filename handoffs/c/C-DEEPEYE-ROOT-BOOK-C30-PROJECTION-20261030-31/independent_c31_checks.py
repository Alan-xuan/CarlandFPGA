"""NEW independent C31 checks; no author fixtures or old test imports.
CLI: python independent_c31_checks.py PUBLIC_DIR EXPECTED_SHA OUTPUT_DIR
The fixture file beside this script is the only local test dependency.
Runtime dependencies remain the unchanged C30/C28 sibling public directories.
"""
import copy, hashlib, json, pathlib, sys, types
from independent_c31_fixture import c31_fixture, action_for, pose, ANCHOR, NS, CLAIM, sha

def encoded(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()

def selected(r):
    h=r['external']['captures'][-1]['adc_book_source_sha256']
    return next(x for x in r['book']['samples'] if x['source_sha256']==h)

def cases():
    r=c31_fixture(); yield 'native_exact_original_single_core',r,'COMPLETE',None
    r=c31_fixture((250,270)); yield 'held_original_dual_origin',r,'COMPLETE',None
    r=c31_fixture(); del r['enabled']; yield 'default_disabled_complete',r,'DISABLED',None
    r=c31_fixture((0,)); yield 'null_C3_complete_STOP',r,'POOR',None
    r=c31_fixture(); r['binding']=None; yield 'equal_reads_missing_independent_binding',r,'UNAVAILABLE',None
    r=c31_fixture(); r['binding']['native_interval_atomic']=True; yield 'reject_upgraded_native_claim',r,'REJECT',None
    r=c31_fixture(); s=selected(r); s['canonical_source_hex']+='0a'; yield 'canonical_newline_not_book_bytes',r,'REJECT',None
    r=c31_fixture((250,270)); r['external']['captures'][-1]['em_book_source_sha256']=r['external']['captures'][-1]['adc_book_source_sha256']; yield 'held_wrong_book_half',r,'REJECT',None
    r=c31_fixture((250,270)); r['external']['captures'][-1]['em_origin_capture_sha256']=r['external']['captures'][-1]['capture_sha256']; yield 'held_wrong_capture_half',r,'REJECT',None
    r=c31_fixture(); s=selected(r); s['adc']['end_qpc_ns']=None; s['adc']['begin_qpc_ns']=r['external']['now_qpc_ns']+1
    yield 'missing_end_future_supplied_begin',r,'REJECT',None
    r=c31_fixture(); s=selected(r); s['adc']['end_qpc_ns']=None; s['adc']['begin_qpc_ns']=s['pose_reads']['adc']['end_qpc_ns']-1
    yield 'missing_end_begin_before_known_read_end',r,'REJECT',None
    r=c31_fixture(); r['external']['current_pose']['receipt_id']=None; r['external']['action_registry']['actions']=[action_for(r)]
    yield 'partial_current_metadata_does_not_hide_revision_span_conflict',r,'REJECT',None
    r=c31_fixture(); r['binding']=None; r['external']['current_pose']['receipt_id']=None; r['book_current']['pose']=pose(0.2)
    yield 'partial_current_does_not_hide_same_revision_pose_conflict',r,'REJECT',None
    r=c31_fixture(); r['external']['config']=None; a=action_for(r,after=None,before=None); r['external']['action_registry']['actions']=[a]; r['external']['captures'][-1]['cause_action_id']=a['action_id']
    yield 'missing_config_does_not_hide_future_action_cause',r,'REJECT',None
    r=c31_fixture(); r['external']['config']=None; a=action_for(r,at=r['external']['candidate']['observation_identity']['receiver_upper_qpc_ns']-1,after=None,before=None); r['external']['action_registry']['actions']=[a]
    yield 'missing_config_does_not_hide_action_before_observation',r,'REJECT',None
    r=c31_fixture(); a=action_for(r,after=6,before=7); r['external']['action_registry']['actions']=[a]; r['external']['candidate']=None
    yield 'missing_candidate_does_not_hide_reversed_action_revisions',r,'REJECT',None
    r=c31_fixture(); a=action_for(r); a['state']='proposed'; r['external']['action_registry']['actions']=[a]; r['external']['candidate']=None
    yield 'missing_candidate_does_not_turn_proposal_into_executed',r,'REJECT',None
    r=c31_fixture(); r['book']['PRIVATE_SENTINEL_KEY']='PRIVATE_SENTINEL_VALUE'; selected(r)['PRIVATE_SENTINEL_NESTED']={'PRIVATE_SENTINEL_INNER':'PRIVATE_SENTINEL_SECRET'}
    yield 'private_drop_names_and_values',r,'COMPLETE',None
    r=c31_fixture(); r['external']['PRIVATE_SENTINEL_KEY']='PRIVATE_SENTINEL_SECRET'; yield 'private_external_error_no_leak',r,'REJECT',None
    r=c31_fixture(); r['binding']=None; r['book']['discarded']={'samples':[None]*33}; yield 'same_named_private_samples_still_32',r,'REJECT','array budget'
    r=c31_fixture(); r['binding']=None; r['book']['discarded']={'canonical_source_hex':'a'*193}; yield 'same_named_private_hex_still_192',r,'REJECT','string budget'
    r=c31_fixture((10000,)); r['book']=None; r['book_current']=None; r['binding']=None
    yield 'exact_admission_path_1001_missing_book',r,'UNAVAILABLE',None
    r=c31_fixture((10000,)); now=r['external']['now_qpc_ns']; r['book']['samples']=[dict(tick_ms=10*i,source_count=i+1,nominal_qpc_ns=ANCHOR+10*i*NS,source_sha256=sha('independent-minimal-book-'+str(i)),status='complete',pose_reads={},adc=None,numerical_pose_span=None) for i in range(1001)]
    r['external'].update(candidate=None,history=[],captures=None,config=None,source_admissions=None,action_registry=None,current_pose=None); r['binding']=None; r['book_current']=None
    yield 'exact_book_samples_1001_missing_proofs',r,'UNAVAILABLE',None
    r=copy.deepcopy(r); r['book']['samples'].append(copy.deepcopy(r['book']['samples'][-1])); yield 'exact_book_samples_1002_rejected',r,'REJECT','array budget'
    r=c31_fixture(); a=action_for(r); r['external'].update(candidate=None,captures=[None]*32); r['external']['action_registry']['actions']=[a]
    yield 'missing_candidate_receipts32_plus_action_rejected',r,'REJECT','combined'
    r=copy.deepcopy(r); r['external']['captures'].pop(); r['external']['action_registry']['actions'][0]['from_pose_revision']=None; r['external']['action_registry']['actions'][0]['to_pose_revision']=None
    yield 'missing_candidate_receipts31_plus_action32_unavailable',r,'UNAVAILABLE',None
    r=c31_fixture(); raw=encoded(r); yield 'strict_duplicate_top_key',raw[:-1]+b',"enabled":true}', 'REJECT','duplicate'
    r=c31_fixture(); r['external']['source_admissions'][0]['received_qpc_ns']=ANCHOR+100000001
    # Preserve monotonic receipt order without altering later selected records.
    for a in r['external']['source_admissions'][1:11]: a['received_qpc_ns']=ANCHOR+100000001
    yield 'complete_legal_stale_preserves_C30_rejection',r,'REJECT','source admission original age'
    r=copy.deepcopy(r); r['binding']=None; yield 'incomplete_legal_stale_no_C30_call',r,'UNAVAILABLE',None
    r=c31_fixture(tuple(range(9050,10001,50))); r['enabled']=False
    wanted={x['adc_book_source_sha256'] for x in r['external']['captures']}
    r['book']['samples']=[s for s in r['book']['samples'] if s['source_sha256'] in wanted]
    for i,s in enumerate(r['book']['samples']):s['source_count']=i+1
    hash_changes={}
    for rec in r['external']['captures']:
        previous=rec['capture_sha256']; rec['capture_raw']+=' '*8000; rec['capture_sha256']=sha(rec['capture_raw']); hash_changes[previous]=rec['capture_sha256']
    for c in r['external']['history']+[r['external']['candidate']]:c['observation_identity']['capture_sha256']=hash_changes[c['observation_identity']['capture_sha256']]
    for rec in r['external']['captures']:rec['em_origin_capture_sha256']=hash_changes[rec['em_origin_capture_sha256']]
    assert len(encoded(r))<1048576, 'aggregate fixture input must fit'
    yield 'aggregate_output_wrapper_budget',r,'REJECT','output budget'

def main():
    public=pathlib.Path(sys.argv[1]); expected=sys.argv[2]; out=pathlib.Path(sys.argv[3]); out.mkdir(parents=True,exist_ok=True)
    source=public/'root_book_projection_v1.py'; data=source.read_bytes(); assert hashlib.sha256(data).hexdigest()==expected
    module=types.ModuleType('independent_frozen_c31'); module.__file__=str(source.resolve()); exec(compile(data,str(source),'exec'),module.__dict__)
    original_globals=dict(module._C30._ORIGINAL.__globals__); original_code=module._C30._ORIGINAL.__code__
    rows=[]; failed=0
    for index,(name,request,want,reason) in enumerate(cases(),1):
        raw=request if type(request) is bytes else encoded(request); folder=out/name; folder.mkdir(exist_ok=True); (folder/'input.json').write_bytes(raw)
        calls={'core':0,'c30_json':0}; actual=None; value=None
        def profile(frame,event,arg):
            if event=='call':
                if frame.f_code is original_code:calls['core']+=1
                if frame.f_code is module._C30.recommend_json.__code__:calls['c30_json']+=1
        sys.setprofile(profile)
        try:
            value=json.loads(module.project_json(raw)); actual=value['input_status']; output=encoded(value)
        except Exception as exc:
            actual='REJECT' if isinstance(exc,module.Rejected) else type(exc).__name__; output=encoded({'exception':type(exc).__name__,'message':str(exc)})
        finally:sys.setprofile(None)
        (folder/'output.json').write_bytes(output)
        ok=True; details=[]
        if want=='REJECT':ok=actual=='REJECT' and (reason is None or reason in output.decode())
        elif want=='UNAVAILABLE':ok=actual=='INPUT_UNAVAILABLE' and value['projection'] is None and value['c30_result'] is None and not value['core_ran'] and not value['c30_called'] and calls=={'core':0,'c30_json':0}
        elif want=='DISABLED':ok=actual=='DISABLED' and calls=={'core':0,'c30_json':1} and value['projection']['enabled'] is False
        else:
            ok=actual=='COMPLETE_DIAGNOSTIC' and value['core_ran'] and calls=={'core':1,'c30_json':1}
            if want=='POOR':ok=ok and value['status']=='STOP'
            if ok:
                projection=value['projection']; ext=request['external']
                ok=projection['candidate']==ext['candidate'] and projection['history']==ext['history'] and projection['now_qpc_ns']==ext['now_qpc_ns'] and projection['root_receipt']['source_admissions']==ext['source_admissions']
                ok=ok and value['claim']==CLAIM and value['native_interval_atomic'] is False and value['authorization']=='none'
                for supplied,projected in zip(ext['captures'],projection['root_receipt']['captures']):
                    for field in ('request_raw','capture_raw','capture_sha256','source_record_sha256','em_origin_capture_sha256','cause_action_id'):ok=ok and supplied[field]==projected[field]
                    for kind in ('adc','em'):
                        if projected[kind+'_pose'] is not None:
                            book_sample=next(s for s in request['book']['samples'] if s['source_sha256']==supplied[kind+'_book_source_sha256'])
                            p=projected[kind+'_pose']; read=book_sample['pose_reads'][kind]
                            ok=ok and p['nominal_source_qpc_ns']==book_sample['nominal_qpc_ns'] and p['pose']==read['pose'] and p['pose_read']=={k:read[k] for k in ('begin_qpc_ns','end_qpc_ns')}
        if type(request) is dict and encoded(request)!=raw:ok=False;details.append('fixture mutated')
        if 'PRIVATE_SENTINEL' in output.decode():ok=False;details.append('private key/value leaked')
        if any(module._C30._ORIGINAL.__globals__.get(k) is not v for k,v in original_globals.items()) or set(module._C30._ORIGINAL.__globals__)!=set(original_globals):ok=False;details.append('original globals mutated')
        row=dict(index=index,name=name,expected=want,actual=actual,passed=bool(ok),calls=calls,input_bytes=len(raw),input_sha256=hashlib.sha256(raw).hexdigest(),output_bytes=len(output),output_sha256=hashlib.sha256(output).hexdigest(),details=details)
        if actual=='REJECT' or value is None:row['exception']=json.loads(output)
        if value is not None:row['missing_codes']=value['missing_codes']
        rows.append(row); failed+=not ok
        if index==1 and not ok:
            row['fixture_gate_failed']=True;break
    summary=dict(runtime_sha256=expected,total=len(rows),passed=len(rows)-failed,failed=failed,cases=rows)
    print(json.dumps(summary,indent=2)); return 1 if failed else 0

if __name__=='__main__':raise SystemExit(main())

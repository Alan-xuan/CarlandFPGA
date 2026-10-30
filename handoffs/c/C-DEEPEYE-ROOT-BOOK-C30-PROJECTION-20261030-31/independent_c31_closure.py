"""Narrow independent C31-R1 closure; no old cases, suites or author imports.

CLI: python independent_c31_closure.py PUBLIC_DIR EXPECTED_SHA replay|new OUTPUT_DIR
Read/verify all original gzip-bundled bytes before any candidate import/call.
Requires sibling independent_c31_fixture.py and original-red-inputs.json.gz.
The invoked C31 keeps its original fixed C30/C28 sibling runtime dependencies.
"""
import copy,gzip,hashlib,json,pathlib,sys,types
from independent_c31_fixture import c31_fixture,action_for,pose,ANCHOR

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')

def original_inputs():
    path=pathlib.Path(__file__).with_name('original-red-inputs.json.gz')
    compressed=path.read_bytes()
    assert compressed[:2]==b'\x1f\x8b' and int.from_bytes(compressed[4:8],'little')==0
    bundle=json.loads(gzip.decompress(compressed))
    assert bundle['schema_version']==1 and len(bundle['cases'])==8
    rows=[];names=set()
    for case in bundle['cases']:
        raw=case['input_utf8'].encode('utf-8')
        assert len(raw)==case['input_bytes'] and hashlib.sha256(raw).hexdigest()==case['input_sha256']
        assert case['name'] not in names;names.add(case['name'])
        rows.append((case['name'],raw,'REJECT'))
    assert sum(len(row[1]) for row in rows)==485228
    return rows,hashlib.sha256(compressed).hexdigest()

def selected(request):
    digest=request['external']['captures'][-1]['adc_book_source_sha256']
    return next(s for s in request['book']['samples'] if s['source_sha256']==digest)

def actions_only(actions):
    request=c31_fixture()
    request['book']=None;request['book_current']=None;request['binding']=None
    request['external'].update(candidate=None,history=[],captures=None,config=None,source_admissions=None,current_pose=None)
    request['external']['action_registry']['actions']=actions
    return request

def new_inputs():
    request=c31_fixture();selected(request)['adc']['end_qpc_ns']=None
    yield 'real_missing_end_valid_supplied_begin',encoded(request),'UNAVAILABLE'
    request=c31_fixture();sample=selected(request);sample['adc']['end_qpc_ns']=None;sample['adc']['begin_qpc_ns']=sample['pose_reads']['adc']['end_qpc_ns']
    yield 'missing_end_begin_equals_known_read_end',encoded(request),'UNAVAILABLE'
    request=c31_fixture();request['external']['current_pose']['receipt_id']=None
    yield 'real_missing_current_receipt_without_contradiction',encoded(request),'UNAVAILABLE'
    request=c31_fixture();request['external']['candidate']=None
    yield 'real_missing_candidate_retains_actual_raw',encoded(request),'UNAVAILABLE'
    request=c31_fixture();action=action_for(request,after=None,before=7);request['external']['action_registry']['actions']=[action]
    # Historical prepared name/input retained. M2 clarified the current7 versus
    # executed before7 lower-bound contradiction before this case ever ran.
    yield 'real_missing_action_to_revision_with_valid_known_order',encoded(request),'REJECT'
    seed=c31_fixture();first=action_for(seed,after=None,before=None)
    request=actions_only([first,copy.deepcopy(first)])
    yield 'candidate_absent_duplicate_supplied_action_ids',encoded(request),'REJECT'
    second=copy.deepcopy(first);second['action_id']='second-independent-action';second['at_qpc_ns']-=1
    request=actions_only([copy.deepcopy(first),second])
    yield 'candidate_absent_action_time_reversal',encoded(request),'REJECT'
    first=action_for(seed,at=seed['external']['now_qpc_ns']-1,after=3,before=2)
    second=action_for(seed,after=4,before=2);second['action_id']='second-independent-action';second['to_pose']=pose(0.02)
    request=actions_only([first,second])
    yield 'candidate_absent_action_revision_chain_reversal',encoded(request),'REJECT'
    first=action_for(seed,after=None,before=None);first['state']='acknowledged'
    request=actions_only([first])
    yield 'candidate_absent_ACK_is_not_executed',encoded(request),'REJECT'
    request=c31_fixture();request['binding']=None;request['book_current']=None;request['external']['current_pose']=None
    for kind in ('adc','em'):request['external']['captures'][0][kind+'_pose']['receipt_id']=None
    selected(request)['pose_reads']['adc']['pose']=pose(0.2)
    yield 'partial_sample_receipts_do_not_hide_same_revision_read_conflict',encoded(request),'REJECT'
    # Missing execution/observation proof; nevertheless known numeric spans must
    # begin at or after the incoming committed revision's actual commit point.
    request=c31_fixture();request['book_current']=None;request['external']['current_pose']=None
    for kind in ('adc','em'):request['external']['captures'][0][kind+'_pose']['receipt_id']=None
    incoming=action_for(request,at=ANCHOR+1,after=7,before=6)
    incoming.update(receipt_id=None,observation_capture_sha256='e'*64,from_pose=pose(-0.01),to_pose=pose())
    request['external']['action_registry']['actions']=[incoming]
    yield 'partial_receipts_known_span_starts_1ns_before_commit',encoded(request),'REJECT'
    request=copy.deepcopy(request);request['external']['action_registry']['actions'][0]['at_qpc_ns']=ANCHOR
    yield 'missing_proof_with_span_start_equal_commit_is_not_contradiction',encoded(request),'UNAVAILABLE'
    request=c31_fixture((350,))
    yield 'complete_new_tick350_native_enabled_exact_core',encoded(request),'COMPLETE'
    request=c31_fixture((350,380));del request['enabled']
    yield 'complete_new_tick350_to380_held_default_disabled',encoded(request),'DISABLED'
    seed=c31_fixture();now=seed['external']['now_qpc_ns']
    first=action_for(seed,at=now-1,after=None,before=7)
    second=action_for(seed,at=now,after=None,before=6);second['action_id']='m2-second-action'
    request=actions_only([first,second])
    yield 'M2_missing_to_cannot_erase_prior_before_lower_bound',encoded(request),'REJECT'
    first=action_for(seed,at=now-1,after=None,before=7)
    second=action_for(seed,at=now,after=None,before=8);second.update(action_id='m2-second-action',from_pose=pose(0.01),to_pose=pose(0.02))
    request=actions_only([first,second])
    yield 'M2_before7_then_before8_missing_to_remains_feasible',encoded(request),'UNAVAILABLE'
    request=actions_only([action_for(seed,after=None,before=(1<<63)-1)])
    yield 'M2_max_uint63_before_has_no_representable_after',encoded(request),'REJECT'
    action=action_for(seed,at=now-1000,after=None,before=7)
    request=actions_only([action]);request['external']['current_pose']=copy.deepcopy(seed['external']['current_pose'])
    request['book_current']={'pose':pose(0.01),'pose_revision':8,'at_qpc_ns':now,'pose_read':{'begin_qpc_ns':now-200,'end_qpc_ns':now},'valid_span':{'from_qpc_ns':now-1000,'through_qpc_ns':now,'root_revision':11,'pose_revision':8},'claim':'numerical_immutable_committed_root_only','native_interval_atomic':False}
    yield 'M2_current8_after_before7_missing_to_remains_feasible',encoded(request),'UNAVAILABLE'

def complete_projection_matches(result,raw):
    """Compare supplied original data, not reconstructed identity/provenance."""
    request=json.loads(raw);ext=request['external'];projection=result['projection']
    if projection is None:return False
    root=projection['root_receipt']
    ok=projection['candidate']==ext['candidate'] and projection['history']==ext['history'] and projection['now_qpc_ns']==ext['now_qpc_ns']
    ok=ok and projection['enabled']==request.get('enabled',False)
    for field in ('config','source_admissions','action_registry'):ok=ok and root[field]==ext[field]
    ok=ok and len(root['captures'])==len(ext['captures'])
    for original,projected in zip(ext['captures'],root['captures']):
        for field in ('capture_sha256','source_record_sha256','request_raw','capture_raw','em_origin_capture_sha256','cause_action_id'):ok=ok and projected[field]==original[field]
        for kind in ('adc','em'):
            meta=original[kind+'_pose'];receipt=projected[kind+'_pose']
            if meta is None:
                ok=ok and receipt is None;continue
            sample=next(s for s in request['book']['samples'] if s['source_sha256']==original[kind+'_book_source_sha256'])
            read=sample['pose_reads'][kind];span=sample['numerical_pose_span']
            expected={'receipt_id':meta['receipt_id'],'source_admission_index':meta['source_admission_index'],'nominal_source_qpc_ns':sample['nominal_qpc_ns'],'pose':read['pose'],'pose_revision':read['pose_revision'],'pose_read':{k:read[k] for k in ('begin_qpc_ns','end_qpc_ns')},'valid_span':{'receipt_id':meta['valid_span_receipt_id'],'from_qpc_ns':span['from_qpc_ns'],'through_qpc_ns':span['through_qpc_ns']}}
            ok=ok and receipt==expected
        adc_sample=next(s for s in request['book']['samples'] if s['source_sha256']==original['adc_book_source_sha256'])
        ok=ok and projected['adc_call']=={k:adc_sample['adc'][k] for k in ('begin_qpc_ns','end_qpc_ns')}
    current=request['book_current'];meta=ext['current_pose']
    expected={'receipt_id':meta['receipt_id'],'context':meta['context'],'generation':meta['generation'],'at_qpc_ns':current['at_qpc_ns'],'pose':current['pose'],'pose_revision':current['pose_revision'],'pose_read':current['pose_read'],'valid_span':{'receipt_id':meta['valid_span_receipt_id'],'from_qpc_ns':current['valid_span']['from_qpc_ns'],'through_qpc_ns':current['valid_span']['through_qpc_ns']}}
    ok=ok and root['current_pose']==expected
    ok=ok and result['c30_result']['candidate']==ext['candidate'] and result['c30_result']['root_receipt']==root
    ok=ok and result['claim']=='numerical_immutable_committed_root_only' and result['native_interval_atomic'] is False and result['authorization']=='none'
    if len(root['captures'])==2:
        ok=ok and root['captures'][1]['em_pose']==root['captures'][0]['em_pose'] and root['captures'][1]['em_origin_capture_sha256']==root['captures'][0]['capture_sha256']
    return ok

def main():
    public=pathlib.Path(sys.argv[1]);expected=sys.argv[2];mode=sys.argv[3];out=pathlib.Path(sys.argv[4]);out.mkdir(parents=True,exist_ok=True)
    assert mode in ('replay','new')
    originals,bundle_sha=original_inputs()  # exact byte restoration precedes import
    source=public/'root_book_projection_v1.py';data=source.read_bytes();assert hashlib.sha256(data).hexdigest()==expected
    module=types.ModuleType('independent_frozen_c31_closure');module.__file__=str(source.resolve());exec(compile(data,str(source),'exec'),module.__dict__)
    before_globals=dict(module._C30._ORIGINAL.__globals__)
    rows=[]
    for name,raw,want in (originals if mode=='replay' else new_inputs()):
        folder=out/name;folder.mkdir(exist_ok=True);(folder/'input.json').write_bytes(raw)
        calls={'c30_json':0,'core':0};result=None
        def profile(frame,event,arg):
            if event=='call':
                if frame.f_code is module._C30.recommend_json.__code__:calls['c30_json']+=1
                if frame.f_code is module._C30._ORIGINAL.__code__:calls['core']+=1
        sys.setprofile(profile)
        try:
            output=module.project_json(raw);result=json.loads(output);actual=result['input_status'];message=None
        except Exception as exc:
            actual='REJECT' if isinstance(exc,module.Rejected) else type(exc).__name__;message=str(exc)
            output=encoded({'exception':type(exc).__name__,'message':message})
        finally:sys.setprofile(None)
        (folder/'output.json').write_bytes(output)
        if want=='REJECT':
            ok=actual=='REJECT' and calls=={'c30_json':0,'core':0}
        elif want=='UNAVAILABLE':
            ok=actual=='INPUT_UNAVAILABLE' and result['projection'] is None and result['c30_result'] is None and not result['c30_called'] and not result['core_ran'] and result['status']=='STOP' and calls=={'c30_json':0,'core':0}
        else:
            wanted_status='COMPLETE_DIAGNOSTIC' if want=='COMPLETE' else 'DISABLED'
            expected_core=want=='COMPLETE'
            ok=actual==wanted_status and result['c30_called'] and result['core_ran'] is expected_core and calls=={'c30_json':1,'core':int(expected_core)}
            ok=ok and complete_projection_matches(result,raw)
            if want=='DISABLED':ok=ok and result['status']=='STOP'
        ok=ok and set(module._C30._ORIGINAL.__globals__)==set(before_globals) and all(module._C30._ORIGINAL.__globals__[k] is v for k,v in before_globals.items())
        row={'name':name,'expected':want,'actual':actual,'passed':bool(ok),'calls':calls,'input_bytes':len(raw),'input_sha256':hashlib.sha256(raw).hexdigest(),'output_bytes':len(output),'output_sha256':hashlib.sha256(output).hexdigest()}
        if message is not None:row['message']=message
        if result is not None:row['missing_codes']=result['missing_codes']
        rows.append(row)
    summary={'mode':mode,'runtime_sha256':expected,'original_bundle_sha256':bundle_sha,'original_eight_verified_before_candidate_import':True,'total':len(rows),'passed':sum(r['passed'] for r in rows),'failed':sum(not r['passed'] for r in rows),'cases':rows}
    print(json.dumps(summary,indent=2));return 1 if summary['failed'] else 0

if __name__=='__main__':raise SystemExit(main())

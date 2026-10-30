"""Prepared independent C30 controls; execute ONLY after source freeze.

CLI: python -B independent_c30_checks.py PUBLIC_DIR
All fixtures are synthetic. No author tests/fixtures or old suite are imported.
Stdout contains compact original results and deterministic input hashes; recipes
are fully specified in this script. The CLI never modifies candidate source.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ANCHOR=2**56+987654321
NS=1000000
GEN=0x12345678
TAG=0xfedcba98
PROFILE='deepeye_forward_profile_candidate_v1'
ENCODING='candidate_four_channel_quality_v1'
PRODUCER='6a5f70a6acdaa6de52fc72d678d452956861370e1d143b70219ced107c5a04c9'
CORE='70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'
SCOPE='synthetic_diagnostic_fixture'


def raw(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n'


def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def pose(x=0):return {'position_m':[x,0,0],'orientation_xyzw':[0,0,0,1]}
def bracket(begin,end):return {'begin_qpc_ns':begin,'end_qpc_ns':end}
def span(begin,end,label):return {'receipt_id':label,'from_qpc_ns':begin,'through_qpc_ns':end}


def fixture(ticks=(100,),schedule=None):
    """New raw4/source/time fixture built without invoking any candidate helper."""
    context={'operation_id':'C30-independent-synthetic-only','request_hash':'1'*64,
             'tested_commit':'2'*40,'build_manifest_sha256':'3'*64,
             'boot_id':'original-Linux-kernel-instance-only','session_id':'S'*192,
             'tag':TAG,'clock_domain_id':'4'*32}
    config={'receipt_id':'synthetic-config','context':copy.deepcopy(context),'generation':GEN,
            'profile_id':PROFILE,'producer_sha256':PRODUCER,'source_policy':'candidate_causal_source_v1',
            'quality_encoding':ENCODING,'source_mode':'twin_fixture','transport_source':'software_fixture',
            'source_start_tick_ms':0,'source_start_monotonic_ns':ANCHOR,'goal_m':[0,0,3],
            'baseline_counters':[100,200,300],'initial_trigger_id':500,
            'pose_book_id':'synthetic-original-book','owner_binding_id':'synthetic-original-owner'}
    schedule=list(range(0,ticks[-1]+1,10)) if schedule is None else list(schedule)
    admissions=[];index_of={};last=None;consecutive=0;last_native=None
    for index,tick in enumerate(schedule):
        consecutive=min(10,consecutive+1) if last is not None and tick-last==10 else 1
        if tick%50==0:last_native=tick
        em=last_native
        q=(8 if consecutive==10 else 0)|(0x1000 if em is None else 7|(0x700 if em<tick else 0))
        counts=([None,None,None] if em is None else [1739,2048,2048])+[0 if consecutive==10 else None]
        admissions.append({'index':index,'adc_tick_ms':tick,'em_tick_ms':em,'channel_counts':counts,
                           'quality':q,'source_record_sha256':sha('synthetic-original-source-'+str(index)+'-'+str(tick)),
                           'received_qpc_ns':ANCHOR+tick*NS+12000,'new_em_sample':em is not None and em==tick})
        index_of[tick]=index;last=tick
    candidates=[];captures=[];native={}
    for seq,tick in enumerate(ticks,1):
        admission=admissions[index_of[tick]];q=admission['quality'];em_tick=admission['em_tick_ms']
        nominal=ANCHOR+tick*NS;em_ns=None if em_tick is None else ANCHOR+em_tick*NS
        injections=[nominal+13000+i for i in range(4)];receiver=nominal+15000
        values=[0 if v is None else v for v in admission['channel_counts']]
        qualities=[((q>>ch)&1)|(((q>>(ch+4))&1)<<1)|(((q>>(ch+8))&1)<<2)|(((q>>12)&1)<<3) for ch in range(4)]
        request={'schema':1,'kind':'diagnostic_scan','context':copy.deepcopy(context),'request_seq':seq,
                 'source_id':4,'source':'software_fixture','values':values,'qualities':qualities,'original_host_qpc_ns':injections}
        request_raw=raw(request)
        lanes=[{'channel':ch,'raw_words':[values[ch],ch|(qualities[ch]<<8),injections[ch]&0xffffffff,injections[ch]>>32,
                  4*(seq-1),4*seq-1,TAG,500+seq,GEN,0],
                'pipeline_counters':[100+4*seq,200+seq,300+4*(seq-1)+ch+1],'ack_returned':True} for ch in range(4)]
        capture={'schema':1,'kind':'diagnostic_capture','context':copy.deepcopy(context),'request_seq':seq,
                 'request_sha256':sha(request_raw),'generation':GEN,'trigger_id':500+seq,
                 'captures':lanes,'final_counters':[100+4*seq,200+seq,300+4*seq]}
        capture_raw=raw(capture);capture_hash=sha(capture_raw)
        ident={'context':copy.deepcopy(context),'request_seq':seq,'request_sha256':sha(request_raw),
               'capture_sha256':capture_hash,'generation':GEN,'trigger_id':500+seq,
               'source_admission_index':index_of[tick],'original_host_injection_qpc_ns':injections,'receiver_upper_qpc_ns':receiver}
        flags={'source_fresh_at_capture':em_ns is not None and receiver-em_ns<=100*NS,
               'all_channels_valid':q&15==15,'injection_to_receiver_upper_ns':receiver-injections[0],
               'target100ms_met':True,'target100ms_scope':'conservative_receiver_upper_bound',
               'formal_100ms_acceptance':'not_run','formal_H12':'not_run','transport_authenticated':False,
               'BOOT_authenticated':False,'physical_sample_authenticated':False,'compression_verified':False,
               'CPU_completion_created':False,'movement_authorized':False}
        candidate={'schema':1,'kind':'candidate_four_channel_input','profile_id':PROFILE,'profile_status':'candidate_only',
                   'profile_note':'not_calibrated;not_em_surrogate_v2;not_formally_frozen','source_mode':'twin_fixture',
                   'quality_encoding':ENCODING,'source_id':4,'transport_source':'software_fixture',
                   'channel_names':['log10_rho_apparent','yaw_log10_rho_difference','pitch_log10_rho_difference','near_bit_vibration_rms_g'],
                   'channel_counts':copy.deepcopy(admission['channel_counts']),'quality':q,
                   'source_time':{'adc_tick_ms':tick,'em_tick_ms':em_tick,'source_start_tick_ms':0,
                                  'source_start_monotonic_ns':ANCHOR,'admission_received_monotonic_ns':admission['received_qpc_ns'],
                                  'adc_source_age_ns':receiver-nominal,'em_source_age_ns':None if em_ns is None else receiver-em_ns,
                                  'time_basis':'trusted_root_source_schedule_not_physical_sample_authentication'},
                   'observation_identity':ident,'diagnostic_flags':flags}
        adc_pose={'receipt_id':'synthetic-adc-read-'+str(tick),'source_admission_index':index_of[tick],
                  'nominal_source_qpc_ns':nominal,'pose_revision':7,'pose':pose(),
                  'pose_read':bracket(nominal+6000,nominal+7000),
                  'valid_span':span(ANCHOR,nominal+10000,'synthetic-adc-valid-'+str(tick))}
        em_pose=None;origin=None
        if em_tick==tick:
            em_pose={'receipt_id':'synthetic-native-em-read-'+str(tick),'source_admission_index':index_of[tick],
                     'nominal_source_qpc_ns':nominal,'pose_revision':7,'pose':pose(),
                     'pose_read':bracket(nominal+1000,nominal+2000),
                     'valid_span':span(ANCHOR,nominal+10000,'synthetic-native-em-valid-'+str(tick))}
            native[em_tick]=(copy.deepcopy(em_pose),capture_hash);origin=capture_hash
        elif em_tick is not None:
            em_pose,origin=copy.deepcopy(native[em_tick])
        captures.append({'capture_sha256':capture_hash,'source_record_sha256':admission['source_record_sha256'],
                         'request_raw':request_raw,'capture_raw':capture_raw,'adc_pose':adc_pose,'em_pose':em_pose,
                         'em_origin_capture_sha256':origin,'cause_action_id':None,
                         'adc_call':bracket(nominal+8000,nominal+10000)})
        candidates.append(candidate)
    now=candidates[-1]['observation_identity']['receiver_upper_qpc_ns']+1000
    root={'kind':'c30_root_time_association_v1','evidence_scope':SCOPE,'config':config,
          'source_admissions':admissions,'captures':captures,
          'current_pose':{'receipt_id':'synthetic-current','context':copy.deepcopy(context),'generation':GEN,
                          'at_qpc_ns':now,'pose':pose(),'pose_revision':7,'pose_read':bracket(now-200,now-100),
                          'valid_span':span(ANCHOR,now,'synthetic-current-valid')},
          'action_registry':{'receipt_id':'synthetic-executed-registry','context':copy.deepcopy(context),
                             'generation':GEN,'as_of_qpc_ns':now,'actions':[]}}
    return {'schema_version':1,'abi_id':'private_raw4_time_association_v1','diagnostic_only':True,'evidence_scope':SCOPE,
            'enabled':True,'now_qpc_ns':now,'candidate':candidates[-1],'history':candidates[:-1],'root_receipt':root}


def now_at(request,now):
    request['now_qpc_ns']=now
    current=request['root_receipt']['current_pose']
    current['at_qpc_ns']=now;current['pose_read']=bracket(now-200,now-100)
    current['valid_span']['through_qpc_ns']=now
    request['root_receipt']['action_registry']['as_of_qpc_ns']=now


def action_fixture(stale_current=False):
    r=fixture();now_at(r,ANCHOR+110*NS+16000)
    action={'receipt_id':'synthetic-execution','action_id':'executed-A','state':'executed',
            'observation_capture_sha256':r['candidate']['observation_identity']['capture_sha256'],
            'at_qpc_ns':ANCHOR+105*NS,'from_pose':pose(),'to_pose':pose(.05),
            'from_pose_revision':7,'to_pose_revision':8}
    r['root_receipt']['action_registry']['actions']=[action]
    if not stale_current:
        current=r['root_receipt']['current_pose'];current['pose_revision']=8;current['pose']=pose(.05)
        current['valid_span']['from_qpc_ns']=ANCHOR+105*NS
    return r


def cases():
    planned=[]
    def add(name,r,expect):planned.append((name,r,expect))
    add('native_nominal_not_actual_full_coverage',fixture(),'ADVISE')
    add('held_original_em_span_not_required_to_cover_later_call',fixture((100,110)),'ADVISE')
    for field in ('pose_book_id','owner_binding_id'):
        r=fixture();r['root_receipt']['config'][field]=None;add('missing_'+field,r,'UNAVAILABLE')
    for which,field in (('adc_pose','pose_read'),('adc_pose','valid_span'),('em_pose','pose_read'),('em_pose','valid_span')):
        r=fixture();r['root_receipt']['captures'][0][which][field]=None;add('missing_'+which+'_'+field,r,'UNAVAILABLE')
    r=fixture();r['root_receipt']['captures'][0]['adc_call']=None;add('missing_adc_call',r,'UNAVAILABLE')
    r=fixture();r['root_receipt']['current_pose']['pose_read']=None;add('missing_current_read',r,'UNAVAILABLE')
    r=fixture();r['root_receipt']['action_registry']=None;add('missing_actual_action_registry',r,'UNAVAILABLE')
    for which in ('adc_pose','em_pose'):
        r=fixture();r['root_receipt']['captures'][0][which]['valid_span']['from_qpc_ns']=ANCHOR+100*NS+1
        add('nominal_outside_later_'+which+'_span',r,'UNAVAILABLE')
        r=fixture();r['root_receipt']['captures'][0][which]['valid_span']['through_qpc_ns']=ANCHOR+100*NS+9999
        add('native_call_end_outside_'+which+'_span_by_1ns',r,'UNAVAILABLE')
        r=fixture();r['root_receipt']['captures'][0][which]['pose_read']['begin_qpc_ns']=ANCHOR+100*NS+11000
        add('reversed_'+which+'_read',r,'REJECTED')
    r=fixture();r['root_receipt']['captures'][0]['adc_call']['end_qpc_ns']=ANCHOR+100*NS+7999
    add('reversed_adc_call',r,'REJECTED')
    r=fixture();r['root_receipt']['captures'][0]['adc_pose']['pose_read']['end_qpc_ns']=ANCHOR+100*NS+9000
    add('adc_pose_read_after_call_begin',r,'REJECTED')
    r=fixture();r['root_receipt']['current_pose']['valid_span']['through_qpc_ns']-=1
    add('current_span_missing_now_by_1ns',r,'UNAVAILABLE')
    r=fixture();r['root_receipt']['current_pose']['valid_span']['through_qpc_ns']+=1
    add('future_span_claim',r,'REJECTED')
    r=fixture();r['root_receipt']['current_pose']['pose']=pose(.1)
    add('same_revision_conflicting_pose',r,'REJECTED')
    r=fixture();r['root_receipt']['current_pose']['pose_revision']=8
    add('different_revision_overlapping_equal_pose_spans',r,'REJECTED')
    r=fixture();r['root_receipt']['current_pose']['pose_revision']=6
    r['root_receipt']['current_pose']['valid_span']['from_qpc_ns']=ANCHOR+100*NS+12000
    add('disjoint_spans_revision_goes_backwards',r,'REJECTED')
    r=fixture();r['root_receipt']['captures'][0]['em_pose']['pose_revision']=8
    add('native_adc_em_revision_disagree',r,'REJECTED')
    r=fixture((100,110));r['root_receipt']['captures'][-1]['em_pose']['pose_read']['end_qpc_ns']+=1
    add('held_original_read_receipt_changed',r,'REJECTED')
    r=fixture((100,110));r['history']=[];r['root_receipt']['captures']=r['root_receipt']['captures'][1:]
    add('held_board_origin_evicted',r,'UNAVAILABLE')
    for age in (100*NS,100*NS+1):
        r=fixture();now_at(r,ANCHOR+100*NS+age)
        add('exact_nominal_age_'+str(age),r,'ADVISE' if age==100*NS else 'UNAVAILABLE')
    r=fixture();r['now_qpc_ns']=2**63;add('uint63_now_overflow',r,'REJECTED')
    r=fixture();r['candidate']['source_time']['source_start_monotonic_ns']=2**63-1
    add('derived_source_qpc_overflow',r,'REJECTED')
    r=fixture();r['candidate']['source_time']['adc_source_age_ns']-=1
    add('one_ns_original_age_not_rounded',r,'REJECTED')
    add('complete_original_prefix_1001',fixture((10000,)),'ADVISE')
    r=fixture((10000,));r['root_receipt']['source_admissions'].append(copy.deepcopy(r['root_receipt']['source_admissions'][-1]))
    add('prefix_1002_refused',r,'REJECTED')
    for retained in (None,0,10):
        r=fixture();r['root_receipt']['source_admissions']=None if retained is None else r['root_receipt']['source_admissions'][:retained]
        add('missing_prefix_'+str(retained),r,'UNAVAILABLE')
    r=fixture();del r['root_receipt']['source_admissions'][0];add('no_nonzero_sliding_prefix',r,'REJECTED')
    r=fixture();r['history']=[copy.deepcopy(r['candidate']) for _ in range(33)];add('history_path_still_32',r,'REJECTED')
    r=fixture();r['root_receipt']['captures']=[copy.deepcopy(r['root_receipt']['captures'][0]) for _ in range(33)]
    add('capture_path_still_32',r,'REJECTED')
    r=fixture();r['root_receipt']['current_pose']['source_admissions']=[0]*1001
    add('same_name_wrong_path_no_1001_exception',r,'REJECTED')
    r=fixture();rec=r['root_receipt']['captures'][0];obj=json.loads(rec['capture_raw']);obj['source_admissions']=[0]*1001;rec['capture_raw']=raw(obj)
    add('raw_embedded_same_name_no_1001_exception',r,'REJECTED')
    schedule=[t for t in range(0,111,10) if t!=70]
    add('real_source_gap_invalid_c3_remains_quality_stop',fixture((100,110),schedule),'QUALITY_STOP')
    add('actual_executed_revision_current_matches',action_fixture(),'ADVISE')
    add('current_revision_behind_actual_executed_to',action_fixture(True),'REJECTED')
    r=fixture((100,110));action=action_fixture()['root_receipt']['action_registry']['actions'][0]
    action['observation_capture_sha256']=r['history'][0]['observation_identity']['capture_sha256']
    action['at_qpc_ns']=ANCHOR+110*NS+500;action['from_pose_revision']=6;action['to_pose_revision']=7
    action['to_pose']=pose();r['root_receipt']['action_registry']['actions']=[action]
    r['root_receipt']['captures'][-1]['cause_action_id']='executed-A'
    add('action_after_nominal_before_actual_read_not_cause',r,'REJECTED')
    r=fixture();r.pop('enabled');add('default_disabled_actual_context',r,'DISABLED')
    r=fixture();r['enabled']=False;r['root_receipt']['captures'][0]['adc_call']=None
    add('disabled_missing_call_no_core',r,'DISABLED')
    r=fixture();r['enabled']=False;r['root_receipt']['captures'][0]['adc_pose']['pose_read']['begin_qpc_ns']=2**63
    add('disabled_malformed_bracket_still_rejected',r,'REJECTED')
    r=fixture();r['root_receipt']['config']['owner_binding_id']='x'*193;add('identity_budget_193',r,'REJECTED')
    r=fixture();r['root_receipt']['captures'][0]['capture_raw']=' '*16385;add('raw_line_budget_16385',r,'REJECTED')
    r=fixture();value=0
    for _ in range(18):value={'x':value}
    r['root_receipt']['config']['pose_book_id']=value;add('tree_depth_budget',r,'REJECTED')
    r=fixture();r['root_receipt']['config']['pose_book_id']=[[[[0]*32 for _ in range(32)] for _ in range(32)] for _ in range(2)]
    add('tree_node_budget_65536',r,'REJECTED')
    r=fixture();rec=r['root_receipt']['captures'][0]
    for field in ('request_raw','capture_raw'):
        original=rec[field].rstrip('\n');rec[field]=original+' '*(16383-len(original.encode()))+'\n'
    r['root_receipt']['captures']=[copy.deepcopy(rec) for _ in range(32)]
    r['history']=[copy.deepcopy(r['candidate']) for _ in range(31)]
    add('encoded_input_budget_1MiB',r,'REJECTED')
    r=action_fixture()
    for which in ('adc_pose','em_pose'):
        r['root_receipt']['captures'][0][which]['valid_span']['through_qpc_ns']=ANCHOR+108*NS
    r['root_receipt']['current_pose']['valid_span']['from_qpc_ns']=ANCHOR+109*NS
    add('old_revision_span_after_completed_action_despite_disjoint_spans',r,'REJECTED')
    r=action_fixture();r['root_receipt']['current_pose']['valid_span']['from_qpc_ns']=ANCHOR+105*NS-1
    add('new_revision_span_starts_1ns_before_completed_action',r,'REJECTED')
    r=action_fixture()
    for which in ('adc_pose','em_pose'):
        r['root_receipt']['captures'][0][which]['valid_span']['through_qpc_ns']=ANCHOR+105*NS-1
    add('closed_action_boundary_old_through_Tminus1_new_from_T',r,'ADVISE')
    return planned


def main():
    start=time.monotonic();public=Path(sys.argv[1]).resolve()
    subject=public/'private_raw4_time_association_v1.py'
    spec=importlib.util.spec_from_file_location('c30_independent_frozen_subject',subject)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=module._ORIGINAL;original_globals=dict(original.__globals__)
    core_path=public.parent/'C-DEEPEYE-CAUSAL-FOUR-CHANNEL-PLANNER-20261029-28'/'candidate_four_channel_planner_v1.py'
    assert hashlib.sha256(core_path.read_bytes()).hexdigest()==CORE
    results=[]
    for name,request,expected in cases():
        before=copy.deepcopy(request)
        record={'name':name,'expected':expected,'input_sha256':sha(raw(request)),
                'input_bytes':len(raw(request).encode()),'core_calls':0,'isolated_globals':True}
        def profile(frame,event,arg):
            if event=='call' and frame.f_code is original.__code__:
                record['core_calls']+=1
                record['isolated_globals'] &= frame.f_globals is not original.__globals__ and all(
                    frame.f_globals.get(k) is v for k,v in original_globals.items() if k!='_validate')
        previous=sys.getprofile()
        try:
            sys.setprofile(profile);answer=module.recommend(request)
            record['output']={k:answer[k] for k in ('input_status','status','core_ran','reason','independent_em_count')}
            if expected=='REJECTED':raise AssertionError('expected Rejected')
            wanted={'ADVISE':('COMPLETE_DIAGNOSTIC','ADVISE',True),'QUALITY_STOP':('COMPLETE_DIAGNOSTIC','STOP',True),
                    'UNAVAILABLE':('INPUT_UNAVAILABLE','STOP',False),'DISABLED':('DISABLED','STOP',False)}[expected]
            assert (answer['input_status'],answer['status'],answer['core_ran'])==wanted
            assert answer['authorization']=='none' and record['core_calls']==int(answer['core_ran'])
            assert record['isolated_globals'] and answer['candidate']==request['candidate']
            assert answer['root_receipt']==request['root_receipt']
            assert json.loads(json.dumps(answer,allow_nan=False))==answer
            if expected=='ADVISE':assert answer['independent_em_count']==1
            record['passed']=True
        except Exception as exc:
            record['exception']={'type':type(exc).__name__,'message':str(exc)[:500]}
            record['passed']=expected=='REJECTED' and isinstance(exc,module.Rejected) and record['core_calls']==0
        finally:sys.setprofile(previous)
        record['input_unchanged']=request==before
        record['globals_unchanged']=all(original.__globals__.get(k) is v for k,v in original_globals.items())
        record['passed'] &= record['input_unchanged'] and record['globals_unchanged']
        results.append(record)
    report={'scope':'SYNTHETIC_C30_NEW_FOCUSED_ONLY','source_sha256':hashlib.sha256(subject.read_bytes()).hexdigest(),
            'action_completion_point_semantics_selected':True,
            'total_checks':len(results),'elapsed_seconds':time.monotonic()-start,'cases':results,
            'formal_acceptance':False,'actual_Root_run':False,'old_suites_run':False}
    report['passed']=all(r['passed'] for r in results) and report['elapsed_seconds']<=30
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())

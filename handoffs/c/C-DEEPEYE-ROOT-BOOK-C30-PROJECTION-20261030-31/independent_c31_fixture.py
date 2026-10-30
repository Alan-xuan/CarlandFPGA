"""Independent receipt builder copied as source, not imported from old suites.
No cases/main/old tests. New constants/identities and C31 NEW structural inputs.
"""
import copy,json,hashlib
ANCHOR=(1<<63)-20000000007
NS=1000000
GEN=0xf1234567
TAG=0xe1234567
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
    context={'operation_id':'C31-independent-new-synthetic','request_hash':'1'*64,
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
    return {'schema_version':1,'abi_id':'private_raw4_time_association_v2','diagnostic_only':True,'evidence_scope':SCOPE,
            'enabled':True,'now_qpc_ns':now,'candidate':candidates[-1],'history':candidates[:-1],'root_receipt':root}


CLAIM='numerical_immutable_committed_root_only'
BOOK_COMMIT='54e1fd6c5795cc2f1247866dd8783331f615ef66'

def numerical_span(begin,end):
    return dict(from_qpc_ns=begin,through_qpc_ns=end,root_revision=11,pose_revision=7)

def c31_fixture(ticks=(250,)):
    old=fixture(ticks); root=old['root_receipt']; now=old['now_qpc_ns']; cfg=root['config']
    samples=[]; hashes={}
    for admission in root['source_admissions']:
        tick=admission['adc_tick_ms']; n=ANCHOR+tick*NS
        counts=admission['channel_counts']
        values=[None if c is None else (float(c)/1000 if i==0 else (float(c)-2048)/409.6 if i in (1,2) else float(c)/409.5) for i,c in enumerate(counts)]
        payload=dict(profile_id=PROFILE,profile_status='candidate_only',profile_note='not_calibrated;not_em_surrogate_v2;not_formally_frozen',source_mode='twin_fixture',adc_tick_ms=tick,em_tick_ms=admission['em_tick_ms'],channel_values=values,channel_counts=copy.deepcopy(counts),quality=admission['quality'])
        canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        digest=hashlib.sha256(canonical).hexdigest(); hashes[tick]=digest
        reads={}
        for kind,b,e in [('adc',6000,7000)]+([('em',1000,2000)] if admission['new_em_sample'] else []):
            reads[kind]=dict(begin_qpc_ns=n+b,end_qpc_ns=n+e,pose=pose(),root_revision=11,pose_revision=7,revoke_generation=0,postcheck_complete=True)
        samples.append(dict(tick_ms=tick,source_count=len(samples)+1,nominal_qpc_ns=n,source_sha256=digest,
            canonical_source_hex=canonical.hex(),payload=payload,status='complete',pose_reads=reads,
            adc=dict(begin_qpc_ns=n+8000,end_qpc_ns=n+10000,previous_adc_tick_ms=None if tick==0 else tick-10,profile_tick_observed=True,postcheck_complete=True),
            numerical_pose_span=numerical_span(ANCHOR,n+10000)))
    for c,rec in zip(old['history']+[old['candidate']],root['captures']):
        time=c['source_time'];rec['adc_book_source_sha256']=hashes[time['adc_tick_ms']]
        rec['em_book_source_sha256']=None if time['em_tick_ms'] is None else hashes[time['em_tick_ms']]
        rec.pop('adc_call')
        for kind in ('adc','em'):
            p=rec[kind+'_pose']
            if p is not None:rec[kind+'_pose']=dict(receipt_id=p['receipt_id'],source_admission_index=p['source_admission_index'],valid_span_receipt_id=p['valid_span']['receipt_id'])
    current=root['current_pose']
    meta=dict(receipt_id=current['receipt_id'],context=copy.deepcopy(current['context']),generation=GEN,valid_span_receipt_id=current['valid_span']['receipt_id'])
    book_current=dict(pose=pose(),pose_revision=7,at_qpc_ns=now,pose_read=bracket(now-200,now),valid_span=numerical_span(ANCHOR,now),claim=CLAIM,native_interval_atomic=False)
    book=dict(schema=1,state='RUNNING',source_state='RUNNING',failure_reason=None,partial_samples=[],active_sample=None,source_origin_qpc_ns=ANCHOR,samples=samples,fixed_root_interval={**numerical_span(ANCHOR,now),'claim':CLAIM},native_interval_atomic=False)
    binding=dict(context=copy.deepcopy(cfg['context']),generation=GEN,pose_book_id=cfg['pose_book_id'],owner_binding_id=cfg['owner_binding_id'],committed_pose=pose(),pose_revision=7,root_revision=11,claim=CLAIM,native_interval_atomic=False)
    ext=dict(evidence_scope=SCOPE,now_qpc_ns=now,candidate=old['candidate'],history=old['history'],config=cfg,source_admissions=root['source_admissions'],captures=root['captures'],current_pose=meta,action_registry=root['action_registry'])
    return dict(schema_version=1,adapter_id='root_book_c30_projection_v1',diagnostic_only=True,enabled=True,book_source_commit=BOOK_COMMIT,book=book,book_current=book_current,binding=binding,external=ext)

def action_for(req,at=None,after=8,before=7):
    ext=req['external']; c=ext['candidate'] or ext['history'][-1]
    return dict(receipt_id='independent-actual-execution',action_id='independent-action',state='executed',observation_capture_sha256=c['observation_identity']['capture_sha256'],at_qpc_ns=ext['now_qpc_ns'] if at is None else at,from_pose=pose(),to_pose=pose(0.01),from_pose_revision=before,to_pose_revision=after)

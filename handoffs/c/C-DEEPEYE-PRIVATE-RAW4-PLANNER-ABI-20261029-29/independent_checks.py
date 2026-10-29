"""Independent C29 synthetic controls. CLI: python -B independent_checks.py PUBLIC_DIR.

No author fixtures/suite are imported. Candidate is imported once from PUBLIC_DIR;
its fixed sibling C28 dependency is required. No source file is written. Results
include exact failing inputs and outputs, and source SHA256, on stdout as JSON.
"""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

NS = 1000000
ANCHOR = 2**56 + 123457
GEN = 0x12345678
TAG = 0xfedcba98
PROFILE = 'deepeye_forward_profile_candidate_v1'
ENCODING = 'candidate_four_channel_quality_v1'
PRODUCER = '6a5f70a6acdaa6de52fc72d678d452956861370e1d143b70219ced107c5a04c9'
CORE = '70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'
SCOPE = 'synthetic_diagnostic_fixture'


def wire(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def pose(position=None, q=None):
    return {'position_m': position or [0, 0, 0], 'orientation_xyzw': q or [0, 0, 0, 1]}


def fixture(ticks=(100,), fault=False, counts=None, extra_quality=0, source_delay=3000):
    """Build original index0 schedule and independent synthetic four-lane bytes."""
    context = {'operation_id': 'independent-local-C29-control', 'request_hash': '1'*64,
               'tested_commit': '2'*40, 'build_manifest_sha256': '3'*64,
               'boot_id': 'linux-kernel-instance-only', 'session_id': 'full-session-' + 'S'*179,
               'tag': TAG, 'clock_domain_id': '4'*32}
    config = {'receipt_id': 'synthetic-config', 'context': context, 'generation': GEN,
              'profile_id': PROFILE, 'producer_sha256': PRODUCER,
              'source_policy': 'candidate_causal_source_v1', 'quality_encoding': ENCODING,
              'source_mode': 'twin_fixture', 'transport_source': 'software_fixture',
              'source_start_tick_ms': 0, 'source_start_monotonic_ns': ANCHOR,
              'goal_m': [0, 0, 3], 'baseline_counters': [100, 200, 300], 'initial_trigger_id': 500}
    admissions = []
    for i in range(ticks[-1]//10 + 1):
        t = 10*i
        em = None if fault and t == ticks[-1] else (t//50)*50
        cs = list(counts or [1739, 2048, 2048, 0])
        if t < 90:
            cs[3] = None
        q = (8 if t >= 90 else 0) | (0x1000 if em is None else 7 | (0x700 if em < t else 0))
        if em is None:
            cs[:3] = [None]*3
        elif t >= 100:
            q |= extra_quality
        admissions.append({'index': i, 'adc_tick_ms': t, 'em_tick_ms': em,
                           'channel_counts': cs, 'quality': q,
                           'source_record_sha256': digest('synthetic-original-source-' + str(i)),
                           'received_qpc_ns': ANCHOR+t*NS+source_delay,
                           'new_em_sample': em is not None and em == t})
    candidates, records, origins = [], [], {}
    for seq, tick in enumerate(ticks, 1):
        adm = admissions[tick//10]
        adc = ANCHOR+tick*NS
        em = None if adm['em_tick_ms'] is None else ANCHOR+adm['em_tick_ms']*NS
        injections = [adc+source_delay+1000+i for i in range(4)]
        receiver = injections[-1]+1000
        quality = adm['quality']
        qualities = [((quality>>ch)&1) | (((quality>>(ch+4))&1)<<1) |
                     (((quality>>(ch+8))&1)<<2) | (((quality>>12)&1)<<3) for ch in range(4)]
        values = [0 if x is None else x for x in adm['channel_counts']]
        request = {'schema': 1, 'kind': 'diagnostic_scan', 'context': copy.deepcopy(context),
                   'request_seq': seq, 'source_id': 4, 'source': 'software_fixture',
                   'values': values, 'qualities': qualities, 'original_host_qpc_ns': injections}
        request_raw = wire(request)
        lanes = []
        for ch, original_ns in enumerate(injections):
            lanes.append({'channel': ch, 'raw_words': [values[ch], ch|(qualities[ch]<<8),
                          original_ns&0xffffffff, original_ns>>32, 4*(seq-1), 4*seq-1,
                          TAG, 500+seq, GEN, 0],
                          'pipeline_counters': [100+4*seq, 200+seq, 300+4*(seq-1)+ch+1],
                          'ack_returned': True})
        capture = {'schema': 1, 'kind': 'diagnostic_capture', 'context': copy.deepcopy(context),
                   'request_seq': seq, 'request_sha256': digest(request_raw), 'generation': GEN,
                   'trigger_id': 500+seq, 'captures': lanes,
                   'final_counters': [100+4*seq, 200+seq, 300+4*seq]}
        capture_raw = wire(capture)
        h = digest(capture_raw)
        if em == adc:
            origins[em] = h
        ident = {'context': copy.deepcopy(context), 'request_seq': seq,
                 'request_sha256': digest(request_raw), 'capture_sha256': h,
                 'generation': GEN, 'trigger_id': 500+seq, 'source_admission_index': tick//10,
                 'original_host_injection_qpc_ns': injections, 'receiver_upper_qpc_ns': receiver}
        flags = {'source_fresh_at_capture': em is not None and receiver-em <= 100*NS,
                 'all_channels_valid': quality&15 == 15,
                 'injection_to_receiver_upper_ns': receiver-injections[0], 'target100ms_met': True,
                 'target100ms_scope': 'conservative_receiver_upper_bound',
                 'formal_100ms_acceptance': 'not_run', 'formal_H12': 'not_run',
                 'transport_authenticated': False, 'BOOT_authenticated': False,
                 'physical_sample_authenticated': False, 'compression_verified': False,
                 'CPU_completion_created': False, 'movement_authorized': False}
        candidate = {'schema': 1, 'kind': 'candidate_four_channel_input', 'profile_id': PROFILE,
                     'profile_status': 'candidate_only',
                     'profile_note': 'not_calibrated;not_em_surrogate_v2;not_formally_frozen',
                     'source_mode': 'twin_fixture', 'quality_encoding': ENCODING, 'source_id': 4,
                     'transport_source': 'software_fixture',
                     'channel_names': ['log10_rho_apparent', 'yaw_log10_rho_difference',
                                       'pitch_log10_rho_difference', 'near_bit_vibration_rms_g'],
                     'channel_counts': list(adm['channel_counts']), 'quality': quality,
                     'source_time': {'adc_tick_ms': tick, 'em_tick_ms': adm['em_tick_ms'],
                                     'source_start_tick_ms': 0, 'source_start_monotonic_ns': ANCHOR,
                                     'admission_received_monotonic_ns': adm['received_qpc_ns'],
                                     'adc_source_age_ns': receiver-adc,
                                     'em_source_age_ns': None if em is None else receiver-em,
                                     'time_basis': 'trusted_root_source_schedule_not_physical_sample_authentication'},
                     'observation_identity': ident, 'diagnostic_flags': flags}
        def receipt(index, ns):
            return {'receipt_id': 'synthetic-pose-'+str(index), 'source_admission_index': index,
                    'acquisition_qpc_ns': ns, 'pose': pose()}
        records.append({'capture_sha256': h, 'source_record_sha256': adm['source_record_sha256'],
                        'request_raw': request_raw, 'capture_raw': capture_raw,
                        'adc_pose': receipt(tick//10, adc),
                        'em_pose': None if em is None else receipt(adm['em_tick_ms']//10, em),
                        'em_origin_capture_sha256': None if em is None else origins.get(em, '0'*64),
                        'cause_action_id': None})
        candidates.append(candidate)
    now = candidates[-1]['observation_identity']['receiver_upper_qpc_ns']+1000
    root = {'kind': 'c29_root_association_v1', 'evidence_scope': SCOPE, 'config': config,
            'source_admissions': admissions, 'captures': records,
            'current_pose': {'receipt_id': 'synthetic-current', 'context': copy.deepcopy(context),
                             'generation': GEN, 'at_qpc_ns': now, 'pose': pose()},
            'action_registry': {'receipt_id': 'synthetic-registry', 'context': copy.deepcopy(context),
                                'generation': GEN, 'as_of_qpc_ns': now, 'actions': []}}
    return {'schema_version': 1, 'abi_id': 'private_raw4_planner_abi_v1', 'diagnostic_only': True,
            'evidence_scope': SCOPE, 'enabled': True, 'now_qpc_ns': now,
            'candidate': candidates[-1], 'history': candidates[:-1], 'root_receipt': root}


def set_now(r, ns):
    r['now_qpc_ns'] = ns
    r['root_receipt']['current_pose']['at_qpc_ns'] = ns
    r['root_receipt']['action_registry']['as_of_qpc_ns'] = ns


def rehash_capture(r, fn, which=-1):
    c = (r['history']+[r['candidate']])[which]
    rec = r['root_receipt']['captures'][which]
    raw = json.loads(rec['capture_raw'])
    fn(raw)
    old = rec['capture_sha256']
    rec['capture_raw'] = wire(raw)
    new = digest(rec['capture_raw'])
    c['observation_identity']['capture_sha256'] = rec['capture_sha256'] = new
    for x in r['root_receipt']['captures']:
        if x['em_origin_capture_sha256'] == old:
            x['em_origin_capture_sha256'] = new


def main():
    start = time.monotonic()
    public = Path(sys.argv[1]).resolve()
    module_path = public/'private_raw4_planner_abi_v1.py'
    spec = importlib.util.spec_from_file_location('c29_independent_subject', module_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    original_globals = dict(m._ORIGINAL.__globals__)
    report = {'fixture_scope': SCOPE, 'formal_acceptance': False, 'cases': [], 'source_pins': {}}
    for p in sorted(public.iterdir()):
        if p.is_file():
            report['source_pins'][p.name] = {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    core_path = public.parent/'C-DEEPEYE-CAUSAL-FOUR-CHANNEL-PLANNER-20261029-28'/'candidate_four_channel_planner_v1.py'
    assert hashlib.sha256(core_path.read_bytes()).hexdigest() == CORE
    def case(name, request, expect):
        before = copy.deepcopy(request)
        record = {'name': name, 'input': before}
        try:
            result = m.recommend(request)
            record['output'] = result
            expect(result)
            assert request == before, 'input mutated'
            assert json.loads(json.dumps(result, allow_nan=False)) == result
            record['pass'] = True
        except Exception as exc:
            record['exception'] = type(exc).__name__+': '+str(exc)
            if expect == reject and isinstance(exc, m.Rejected):
                assert request == before
                record['pass'] = True
            else:
                record['pass'] = False
                record['traceback'] = traceback.format_exc()
        report['cases'].append(record)
    def reject(_):
        raise AssertionError('expected Rejected')
    def advise(o):
        assert o['core_ran'] is True and o['status'] == 'ADVISE', o
        assert o['authorization'] == 'none' and o['independent_em_count'] == 1
        assert o['candidate']['observation_identity']['context']['session_id'] == 'full-session-'+'S'*179
        assert o['map_cells'][0]['original_em_qpc_ns'] == ANCHOR+100*NS
        assert type(o['map_cells'][0]['original_em_qpc_ns']) is int
        assert 'em_tick_ms' not in o['map_cells'][0]
    def unavailable(o):
        assert o['core_ran'] is False and o['status'] == 'STOP' and o['input_status'] == 'INPUT_UNAVAILABLE', o
    def quality_stop(o):
        assert o['core_ran'] is True and o['status'] == 'STOP' and o['reason'] == 'invalid_faulted_or_saturated', o
    def pose_stop(o):
        assert o['core_ran'] is True and o['status'] == 'STOP' and o['reason'] == 'original_observation_pose_inapplicable', o

    case('native_exact_large_qpc_identity_and_map', fixture(), advise)
    r = fixture(); r.pop('enabled')
    case('omitted_enabled_real_private_context', r, lambda o: check(o['input_status']=='DISABLED' and not o['core_ran']))
    for missing in ('root_receipt', 'config', 'source_admissions', 'captures', 'current_pose', 'action_registry'):
        r = fixture()
        if missing == 'root_receipt': r[missing] = None
        else: r['root_receipt'][missing] = None
        case('missing_'+missing, r, unavailable)
    for missing in ('request_raw', 'capture_raw', 'adc_pose', 'em_pose', 'em_origin_capture_sha256'):
        r = fixture(); r['root_receipt']['captures'][0][missing] = None
        case('missing_'+missing, r, unavailable)
    for age in (100*NS, 100*NS+1):
        r = fixture(); set_now(r, ANCHOR+100*NS+age)
        case('exact_now_age_'+str(age), r, advise if age == 100*NS else unavailable)
    r = fixture(); r['candidate']['source_time']['adc_source_age_ns'] -= 1
    case('one_ns_source_age_tamper', r, reject)
    r = fixture(); r['candidate']['source_time']['source_start_monotonic_ns'] += 1
    case('anchor_one_ns_not_rebased', r, reject)
    r = fixture(); r['candidate']['source_time']['adc_source_age_ns'] = r['candidate']['diagnostic_flags']['injection_to_receiver_upper_ns']
    case('injection_latency_is_not_source_age', r, reject)
    case('held_original_native_map_once', fixture((100,110)), advise)
    r = fixture((100,110)); r['history']=[]; r['root_receipt']['captures']=r['root_receipt']['captures'][1:]
    case('held_evicted_native_capture', r, unavailable)
    r = fixture((100,110)); r['root_receipt']['captures'][-1]['em_pose']['pose']=pose([0.01,0,0])
    case('held_own_pose_not_replaced', r, reject)
    r = fixture((100,110)); r['root_receipt']['captures'][-1]['em_pose']['source_admission_index']=11
    case('held_native_pose_index', r, reject)
    r = fixture((100,110)); r['root_receipt']['source_admissions'][11]['new_em_sample']=True
    case('held_not_new_native', r, reject)
    r = fixture((100,120)); r['root_receipt']['source_admissions'][11].update(
        em_tick_ms=None, channel_counts=[None,None,None,0], quality=0x1008, new_em_sample=False)
    case('held_after_source_fault_cannot_revive', r, reject)
    r = fixture(); r['root_receipt']['captures'][0]['adc_pose']['acquisition_qpc_ns'] += 1
    case('own_pose_one_ns_mismatch', r, reject)
    r = fixture(); r['root_receipt']['source_admissions'][0]['index']=1
    case('origin_zero_not_sliding_window', r, reject)
    r = fixture(); r['root_receipt']['source_admissions'][8]['adc_tick_ms']=70
    case('c3_contiguity_from_original_source', r, reject)
    case('startup_null_c3_legal_quality_stop', fixture((0,20)), quality_stop)
    case('em_fault_null_legal_quality_stop', fixture(fault=True), quality_stop)
    case('legal_nonfullscale_c3_saturation_stop', fixture(counts=[1739,2048,2048,1300], extra_quality=0x80), quality_stop)
    for key in ('session_id', 'tag', 'boot_id', 'clock_domain_id'):
        r=fixture(); ctx=r['root_receipt']['current_pose']['context']
        ctx[key] = TAG-1 if key=='tag' else ('5'*32 if key=='clock_domain_id' else ctx[key][:-1]+'X')
        case('full_context_mismatch_'+key,r,reject)
    r=fixture(); r['root_receipt']['config']['generation'] &= 255
    case('generation_no_lowbyte_alias',r,reject)
    r=fixture(); r['root_receipt']['captures'][0]['source_record_sha256']='9'*64
    case('source_record_hash_association',r,reject)
    r=fixture(); rehash_capture(r,lambda cap: cap['captures'][2]['raw_words'].__setitem__(0,2049))
    case('rehash_cannot_fix_returned_count_mismatch',r,reject)
    r=fixture(); rehash_capture(r,lambda cap: cap['captures'][1]['raw_words'].__setitem__(2,0))
    case('raw_qpc_low_word_exact',r,reject)
    r=fixture(); rehash_capture(r,lambda cap: cap['captures'][0]['raw_words'].__setitem__(6,TAG&255))
    case('raw_tag_no_lowbyte_alias',r,reject)
    for angle in (90,180):
        r=fixture((100,110)); a=math.radians(angle)/2
        r['root_receipt']['current_pose']['pose']=pose(q=[0,math.sin(a),0,math.cos(a)])
        case('world_turn_'+str(angle),r,pose_stop)
    r=fixture(); r['root_receipt']['current_pose']['pose']=pose([10,0,0])
    case('large_translation_stop',r,pose_stop)
    r=fixture(); r['root_receipt']['current_pose']['pose']=pose([0.01,0,0],[0,0,1,0])
    case('roll_and_small_translation_supported',r,advise)
    for angle in (15,15.00001):
        r=fixture(); a=math.radians(angle)/2
        r['root_receipt']['current_pose']['pose']=pose(q=[0,math.sin(a),0,math.cos(a)])
        case('pose_angle_boundary_'+str(angle),r,advise if angle==15 else pose_stop)
    for x in (0.25,0.25000001):
        r=fixture(); r['root_receipt']['current_pose']['pose']=pose([x,0,0])
        case('pose_translation_boundary_'+str(x),r,advise if x==0.25 else pose_stop)
    for axis in (0,1):
        for signal in (700,3400):
            cs=[2500,2048,2048,0]; cs[axis+1]=signal
            def sign_check(o,axis=axis,signal=signal):
                advise(o)
                assert o['direction_world'][axis]*(1 if signal==700 else -1)>0
            case('count_signal_direction_'+str(axis)+'_'+str(signal),fixture(counts=cs),sign_check)
    r=fixture((100,110)); h=r['history'][0]['observation_identity']['capture_sha256']
    action={'receipt_id':'synthetic-execution','action_id':'occurred-A','state':'executed',
            'observation_capture_sha256':h,'at_qpc_ns':ANCHOR+105*NS,
            'from_pose':pose(),'to_pose':pose([0.01,0,0])}
    r['root_receipt']['action_registry']['actions']=[action]
    r['root_receipt']['captures'][-1]['cause_action_id']='occurred-A'
    case('actual_action_receipt_causal_order',r,advise)
    for field,val in (('receipt_id',None),('state','planned'),('at_qpc_ns',ANCHOR+110*NS),('observation_capture_sha256','9'*64)):
        s=copy.deepcopy(r); s['root_receipt']['action_registry']['actions'][0][field]=val
        case('action_bad_'+field,s,unavailable if field in ('receipt_id','observation_capture_sha256') else reject)
    for disabled in (False,True):
        r=fixture(); r['enabled']=not disabled; r['root_receipt']['config']=None
        r['root_receipt']['captures'][0]['hidden_truth']=42
        case('hidden_nested_field_earlyreturn_'+str(disabled),r,reject)
    for mutation in ('boolqpc','floatqpc','unknown','nan','depth','history33'):
        r=fixture()
        if mutation=='boolqpc': r['now_qpc_ns']=True
        if mutation=='floatqpc': r['now_qpc_ns']=float(r['now_qpc_ns'])
        if mutation=='unknown': r['protocol_BOOT']='fake'
        if mutation=='nan': r['root_receipt']['config']['goal_m'][0]=float('nan')
        if mutation=='depth':
            val={}
            for _ in range(18): val={'x':val}
            r['root_receipt']['config']=val
        if mutation=='history33': r['history']=[copy.deepcopy(r['candidate']) for _ in range(33)]
        case('strict_json_'+mutation,r,reject)

    extras = []
    def extra(name, fn):
        try:
            detail=fn(); extras.append({'name':name,'pass':True,'detail':detail})
        except Exception:
            extras.append({'name':name,'pass':False,'traceback':traceback.format_exc()})
    def seam():
        r=fixture(); view=m._association(r,r['history']+[r['candidate']]); bound=m._bind_core(view)
        assert bound.__code__ is m._ORIGINAL.__code__
        assert bound.__globals__ is not m._ORIGINAL.__globals__
        assert set(bound.__globals__)==set(original_globals)
        assert all(bound.__globals__[k] is v for k,v in original_globals.items() if k!='_validate')
        assert view['now_tick_ms']==Fraction(r['now_qpc_ns'],NS)
        bad=copy.deepcopy(view); bad['now_tick_ms'] += Fraction(1,NS)
        try: bound(bad)
        except m.Rejected: pass
        else: raise AssertionError('modified internal projection accepted')
        assert all(m._ORIGINAL.__globals__[k] is v for k,v in original_globals.items())
        return 'same code object; only isolated validator differs; changed projection rejected'
    extra('exact_codeobject_isolation_and_fixed_projection',seam)
    def json_checks():
        r=fixture(); raw=wire(r).encode(); result=json.loads(m.recommend_json(raw))
        assert result==m.recommend(r)
        for malformed in (b'{"x":1,"x":2}',b'{"x":NaN}',b'\xff', b' '*262145):
            try: m.recommend_json(malformed)
            except m.Rejected: pass
            else: raise AssertionError('malformed byte input accepted')
        result['candidate']['channel_counts'][0]=0
        assert r['candidate']['channel_counts'][0]==1739
        return 'strict UTF8/duplicate/nonfinite/bytebound and detached output'
    extra('strict_bytes_and_detachment',json_checks)
    report['extra_checks']=extras
    report['elapsed_seconds']=time.monotonic()-start
    report['passed']=all(x['pass'] for x in report['cases']+extras) and report['elapsed_seconds']<=30
    report['total_checks']=len(report['cases'])+len(extras)
    # Nonfinite negative input is represented as a readable string in the raw log.
    print(json.dumps(report,indent=2,allow_nan=True))
    return 0 if report['passed'] else 1


def check(test):
    assert test


if __name__=='__main__':
    sys.exit(main())

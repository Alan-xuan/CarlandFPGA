"""C41 strict consistency-only C40 pair adapter. No I/O, source imports or core.

Mechanical C40 parsing/input checks below preserve the pinned grammar; they do
not authenticate source facts or perform inference. Result checks follow them.
"""
import hashlib
import json
import math
import re
from dataclasses import dataclass
from types import MappingProxyType

ABI = 'c37-owned-cpu-package/v2'


CORE_SHA256 = '70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'


UINT63 = (1 << 63) - 1


MAX_WIRE = 16384


MAX_PAYLOAD = 16380


MAX_CHUNK = 8192


MAX_OUTPUT = 18440


_PUBLIC = {'schema_version', 'projection_id', 'enabled', 'now_qpc_ns', 'pose',
           'goal_m', 'observation', 'history', 'executed_actions'}


_OBS = {'sample_id', 'counts', 'quality', 'adc_qpc_ns', 'em_qpc_ns', 'adc_pose', 'em_pose'}


_IDS = {'operation_id', 'run_id', 'actor_instance_id', 'invocation_id',
        'tested_commit', 'package_manifest_sha256'}


class Rejected(ValueError):
    """Only fixed public reason codes are emitted to the pipe."""


def need(condition, code='INVALID_PROJECTION'):
    if not condition:
        raise Rejected(code)


def exact(value, keys):
    need(type(value) is dict and set(value) == keys, 'INVALID_SHAPE')


def integer(value, low=0, high=UINT63):
    need(type(value) is int and low <= value <= high, 'INTEGER_BOUND')
    return value


def tree(value, depth=0, count=None):
    if count is None:
        count = [0]
    count[0] += 1
    need(depth <= 24 and count[0] <= 4096, 'TREE_BUDGET')
    kind = type(value)
    need(kind in (dict, list, str, int, float, bool, type(None)), 'JSON_TYPE')
    if kind is dict:
        need(len(value) <= 32 and all(type(k) is str and len(k) <= 96 for k in value), 'TREE_BUDGET')
        for item in value.values():
            tree(item, depth + 1, count)
    elif kind is list:
        need(len(value) <= 32, 'TREE_BUDGET')
        for item in value:
            tree(item, depth + 1, count)
    elif kind is str:
        need(len(value) <= 192, 'TREE_BUDGET')
    elif kind is int:
        need(abs(value) <= UINT63, 'INTEGER_BOUND')
    elif kind is float:
        need(math.isfinite(value), 'NONFINITE')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'DUPLICATE_KEY')
        result[key] = value
    return result


def _constant(_):
    raise Rejected('NONFINITE')


def _parse(raw):
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, Rejected):
            raise
        raise Rejected('INVALID_JSON') from None
    tree(result)
    return result


def _dump(value):
    tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def frame(payload, limit=16384):
    need(type(payload) is bytes and 1 <= len(payload) <= limit, 'FRAME_BUDGET')
    return len(payload).to_bytes(4, 'little') + payload


def fixed_request(payload):
    """Canonical outer JSON followed by ASCII spaces; hash the whole wire."""
    need(type(payload) is bytes and 1 <= len(payload) <= MAX_PAYLOAD, 'FRAME_BUDGET')
    return frame(payload + b' ' * (MAX_PAYLOAD - len(payload)), MAX_PAYLOAD)


def decode_request(wire):
    need(type(wire) is bytes and len(wire) == MAX_WIRE, 'FRAME_BUDGET')
    need(int.from_bytes(wire[:4], 'little') == MAX_PAYLOAD, 'FRAME_LENGTH')
    payload = wire[4:]
    value = _parse(payload)
    canonical = _dump(value)
    need(payload.startswith(canonical), 'NONCANONICAL_JSON')
    need(all(c in b' \t\r\n' for c in payload[len(canonical):]), 'PADDING')
    return value


def _number(value, bound):
    need(type(value) in (int, float), 'NUMBER_TYPE')
    need(math.isfinite(value) and abs(value) <= bound, 'NUMBER_BOUND')


def vector(value, size, bound):
    need(type(value) is list and len(value) == size, 'VECTOR_SHAPE')
    for item in value:
        _number(item, bound)


def pose(value):
    exact(value, {'position_m', 'orientation_xyzw'})
    vector(value['position_m'], 3, 1000)
    vector(value['orientation_xyzw'], 4, 1)
    need(abs(sum(x*x for x in value['orientation_xyzw']) - 1) <= 1e-12, 'POSE_NORM')


def _hex(value, width):
    need(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % width, value) is not None, 'DIGEST_FORMAT')


def validate_public(view):
    """Compact consistency only; original full-proof validation is host C36."""
    tree(view)
    exact(view, _PUBLIC)
    integer(view['schema_version'], 1, 1)
    need(view['projection_id'] == 'c36_c28_public_view_v1', 'PROJECTION_VERSION')
    need(type(view['enabled']) is bool, 'ENABLED_TYPE')
    now = integer(view['now_qpc_ns'])
    pose(view['pose']); vector(view['goal_m'], 3, 1000)
    history, actions = view['history'], view['executed_actions']
    need(type(history) is list and type(actions) is list, 'ARRAY_TYPE')
    need(len(history) <= 31 and len(actions) <= 31 and len(history) + 1 + len(actions) <= 32,
         'COMBINED_BUDGET')
    observations = history + [view['observation']]
    seen, native, previous = set(), {}, None
    for obs in observations:
        exact(obs, _OBS)
        _hex(obs['sample_id'], 64)
        need(obs['sample_id'] not in seen, 'DUPLICATE_SAMPLE')
        seen.add(obs['sample_id'])
        adc = integer(obs['adc_qpc_ns'])
        need(adc <= now, 'FUTURE_SOURCE')
        if previous is not None:
            need(adc > previous['adc_qpc_ns'], 'SOURCE_ORDER')
        pose(obs['adc_pose'])
        q = integer(obs['quality'], 0, 8191)
        counts = obs['counts']
        need(type(counts) is list and len(counts) == 4, 'COUNTS_SHAPE')
        em_valid = q & 7
        need(em_valid in (0, 7) and bool(q & 0x1000) == (em_valid == 0), 'EM_FAULT')
        need(not q & 0x800, 'C3_HELD')
        for i, count in enumerate(counts):
            valid, saturated, held = bool(q & (1 << i)), bool(q & (16 << i)), bool(q & (256 << i))
            need((count is not None) == valid, 'COUNTS_VALIDITY')
            if count is not None:
                integer(count, 0, 4095)
            need(valid or not (saturated or held), 'INVALID_FLAGS')
            if i < 3 and saturated:
                need(count in (0, 4095), 'EM_SATURATION')
        if q & 0x80:
            need(2*counts[3]/4095 + 1/4095 >= math.sqrt(0.4), 'C3_SATURATION')
        # Source model startup ticks/admissions are deliberately host-only facts;
        # an absolute QPC value cannot substitute for a model tick >=90ms.
        if em_valid:
            em = integer(obs['em_qpc_ns'])
            age = adc - em
            need(0 <= age <= 100_000_000, 'EM_SOURCE_AGE')
            need(q & 0x700 == (0x700 if age else 0), 'HELD_FLAGS')
            pose(obs['em_pose'])
            if not age:
                need(obs['em_pose'] == obs['adc_pose'], 'NATIVE_POSE')
                native[em] = obs
            else:
                origin = native.get(em)
                need(origin is not None and previous is not None and previous['em_qpc_ns'] == em,
                     'HELD_ORIGIN')
                need(origin['counts'][:3] == counts[:3] and origin['quality'] & 0x70 == q & 0x70
                     and origin['em_pose'] == obs['em_pose'], 'HELD_MUTATION')
        else:
            need(obs['em_qpc_ns'] is None and obs['em_pose'] is None, 'FAULT_ORIGIN')
        previous = obs
    ids = set()
    for action in actions:
        exact(action, {'action_id', 'from_pose', 'to_pose'})
        label = action['action_id']
        need(type(label) is str and re.fullmatch(r'[ -~]{1,192}', label) is not None, 'ACTION_ID')
        need(label not in ids, 'DUPLICATE_ACTION')
        ids.add(label)
        pose(action['from_pose']); pose(action['to_pose'])
    return observations


def _ids(value):
    exact(value, _IDS)
    for key in ('operation_id', 'run_id', 'actor_instance_id'):
        need(type(value[key]) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}', value[key])
             is not None, 'LABEL_FORMAT')
    integer(value['invocation_id'], 1)
    _hex(value['tested_commit'], 40); _hex(value['package_manifest_sha256'], 64)

# C41 output verification. No planner/host/native module is loaded.
PACKAGE_MANIFEST_SHA256 = 'cb971d321bcdd3dcb6a7b85fdd9e08171c995feb62fab3f995bc7f50fdf97a8a'
_READY = {'abi','kind','echo_ids','request_wire_sha256','core_sha256','authority'}
_RESULT = {'abi','kind','echo_ids','request_wire_sha256','status','core_ran',
           'authority','completion_grant','result','reason'}
_ADVICE = {'schema_version','planner_id','candidate_only','authorization','status','reason',
           'risk','uncertainty','direction_world','speed_limit_m_s','observation',
           'map_cells','independent_em_count'}
_STOP = {'invalid_faulted_or_saturated','original_sample_expired',
         'original_observation_pose_inapplicable','goal_near_requires_authority_completion',
         'contact_vibration_risk','no_forward_goal_progress','candidate_risk_limit'}


# Literal C40 Rejected codes reachable through the post-entry validator/output
# call surface. They remain failure diagnostics, never proof of failed computation.
_POSTCORE_REJECTED = frozenset(['ACTION_ID', 'ARRAY_TYPE', 'C3_HELD', 'C3_SATURATION', 'COMBINED_BUDGET', 'COUNTS_SHAPE', 'COUNTS_VALIDITY', 'DIGEST_FORMAT', 'DUPLICATE_ACTION', 'DUPLICATE_SAMPLE', 'EM_FAULT', 'EM_SATURATION', 'EM_SOURCE_AGE', 'ENABLED_TYPE', 'FAULT_ORIGIN', 'FUTURE_SOURCE', 'HELD_FLAGS', 'HELD_MUTATION', 'HELD_ORIGIN', 'INTEGER_BOUND', 'INTERNAL_TIME_LOSS', 'INTERNAL_TIME_TYPE', 'INVALID_FLAGS', 'INVALID_SHAPE', 'JSON_TYPE', 'NATIVE_POSE', 'NONFINITE', 'NUMBER_BOUND', 'NUMBER_TYPE', 'OUTPUT_TIME_MISMATCH', 'POSE_NORM', 'PROJECTION_VERSION', 'SOURCE_ORDER', 'TREE_BUDGET', 'VECTOR_SHAPE'])

def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key:_freeze(item) for key,item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class PairConsistency:
    """Detached immutable consistency data. No authentication or completion grant."""
    ready: object
    result: object
    request_wire_sha256: str
    response_wire_sha256: str


@dataclass(frozen=True, slots=True)
class HostObservedInterval:
    """Caller-supplied dispatch-to-full-result observation, not exact CPU finish."""
    lower_ns: int
    upper_ns: int


def validate_observed_interval(*, dispatch_lower_ns, all_result_observed_upper_ns, now_ns):
    """Check uint63/order only; cannot prove actual clock, IO, custody or freshness.

    No conversion to completed_monotonic_ns and no new deadline is provided.
    Original source/dispatch deadlines must independently bound admission.
    """
    lower=integer(dispatch_lower_ns);upper=integer(all_result_observed_upper_ns)
    now=integer(now_ns)
    need(lower <= upper <= now, 'OBSERVED_INTERVAL_ORDER')
    return HostObservedInterval(lower,upper)


def _two_frames(wire):
    need(type(wire) is bytes and 10 <= len(wire) <= MAX_OUTPUT, 'PAIR_BUDGET')
    values=[];offset=0
    for limit in (2048,16384):
        need(offset+4 <= len(wire), 'MISSING_FRAME')
        size=int.from_bytes(wire[offset:offset+4],'little');offset+=4
        need(1 <= size <= limit and offset+size <= len(wire), 'RESPONSE_FRAME_LENGTH')
        values.append(_parse(wire[offset:offset+size]));offset+=size
    need(offset == len(wire), 'EXTRA_FRAME_OR_BYTES')
    return values


def _public_error(request):
    # Same C40 ordering after correlated outer shape/ABI/IDs. A malformed public
    # request can still have a valid correlated REJECTED pair; it is not advice.
    try:
        enabled=request.get('enabled',False)
        need(type(enabled) is bool, 'ENABLED_TYPE')
        validate_public(request['input'])
        need(enabled == request['input']['enabled'], 'ENABLED_CONFLICT')
    except Rejected as error:
        return str(error)
    return None


def _unit_interval(value):
    _number(value,1)
    need(value >= 0, 'OUTPUT_NUMBER_BOUND')


def _advice(value,public):
    exact(value,_ADVICE)
    integer(value['schema_version'],1,1)
    need(value['planner_id']=='candidate_four_channel_planner_v1', 'PLANNER_ID')
    need(value['candidate_only'] is True and value['authorization']=='none', 'ADVICE_AUTHORITY')
    need(value['status'] in ('STOP','ADVISE'), 'ADVICE_STATUS')
    need(type(value['reason']) is str, 'ADVICE_REASON')
    _unit_interval(value['risk']);_unit_interval(value['uncertainty'])
    vector(value['direction_world'],3,1);_number(value['speed_limit_m_s'],0.25)
    need(value['speed_limit_m_s'] >= 0, 'SPEED_BOUND')
    # JSON tree + exact grammar checks prevent bool/int equality disguises.
    exact(value['observation'],_OBS)
    need(_dump(value['observation'])==_dump(public['observation']), 'OBSERVATION_MISMATCH')
    reason=value['reason']
    if value['status']=='STOP':
        need(reason in _STOP, 'STOP_REASON')
        need(value['direction_world']==[0,0,0] and value['speed_limit_m_s']==0, 'STOP_ACTION')
    else:
        need(reason=='bounded_observation_goal_search', 'ADVISE_REASON')
        need(abs(sum(x*x for x in value['direction_world'])-1) <= 1e-10, 'DIRECTION_NORM')
        need(value['risk'] < 0.8 and 0 < value['speed_limit_m_s'] <= 0.25, 'ADVISE_BOUND')
        # Global speed cap from the supplied risk/uncertainty, not a second search.
        need(value['speed_limit_m_s'] <= 0.25*(1-value['risk'])*(1-value['uncertainty'])+1e-15,
             'ADVISE_SPEED_RISK_BOUND')
    obs=public['observation'];quality=obs['quality']
    bad_quality=quality & 15 != 15 or bool(quality & 0x10F0)
    expired=(not bad_quality and (public['now_qpc_ns']-obs['em_qpc_ns'] > 100_000_000
                                 or public['now_qpc_ns']-obs['adc_qpc_ns'] > 100_000_000))
    if bad_quality:
        need(reason=='invalid_faulted_or_saturated','EARLY_QUALITY_REASON')
    elif expired:
        need(reason=='original_sample_expired','EARLY_AGE_REASON')
    else:
        need(reason not in ('invalid_faulted_or_saturated','original_sample_expired'),'EARLY_REASON_CONFLICT')
    cells=value['map_cells'];need(type(cells) is list and len(cells)<=32,'MAP_BUDGET')
    integer(value['independent_em_count'],0,32)
    need(value['independent_em_count']==len(cells),'MAP_COUNT')
    origins=[] if bad_quality or expired else [o for o in public['history']+[obs]
              if o['quality']==15 and o['adc_qpc_ns']==o['em_qpc_ns']]
    need(len(cells)==len(origins),'MAP_ORIGINS')
    for cell,origin in zip(cells,origins):
        exact(cell,{'sample_id','em_qpc_ns','pose','risk'})
        _hex(cell['sample_id'],64);integer(cell['em_qpc_ns']);pose(cell['pose']);_unit_interval(cell['risk'])
        need(cell['sample_id']==origin['sample_id'] and cell['em_qpc_ns']==origin['em_qpc_ns']
             and _dump(cell['pose'])==_dump(origin['em_pose']),'MAP_ORIGIN_MISMATCH')
    if bad_quality or expired:
        need(value['risk']==1 and value['uncertainty']==1,'EARLY_STOP_BOUNDS')
    elif reason=='original_observation_pose_inapplicable':
        need(value['risk']==1 and value['uncertainty']==1,'POSE_STOP_BOUNDS')
    elif reason in ('goal_near_requires_authority_completion','contact_vibration_risk','no_forward_goal_progress'):
        need(value['risk']==1,'STOP_RISK')
    elif reason=='candidate_risk_limit':
        need(value['risk']>=0.8,'RISK_STOP_BOUND')


def verify_pair(request_wire, response_wire, *, expected_ids):
    """Verify original bytes against caller expected correlation, no provenance.

    expected_ids must contain exactly the six C40 fields. Manifest/core pins are
    fixed here, never accepted merely because a child echoes caller labels.
    Uncorrelated/null-ID diagnostics are refused, not adopted into this result.
    No inference, source import, clock sample, filesystem or native operation.
    """
    tree(expected_ids);_ids(expected_ids)
    need(expected_ids['package_manifest_sha256']==PACKAGE_MANIFEST_SHA256,'PACKAGE_PIN')
    request=decode_request(request_wire)
    keys={'abi','kind','echo_ids','input'}
    need(type(request) is dict and set(request) in (keys,keys|{'enabled'}),'REQUEST_SHAPE')
    need(request['abi']==ABI and request['kind']=='recommend','REQUEST_ABI')
    _ids(request['echo_ids'])
    need(request['echo_ids']==expected_ids,'REQUEST_CORRELATION')
    ready,result=_two_frames(response_wire)
    exact(ready,_READY);exact(result,_RESULT)
    digest=hashlib.sha256(request_wire).hexdigest()
    for item,kind in ((ready,'READY'),(result,'RESULT')):
        need(item['abi']==ABI and item['kind']==kind,'PAIR_ORDER_OR_ABI')
        _ids(item['echo_ids'])
        need(item['echo_ids']==expected_ids,'RESPONSE_CORRELATION')
        _hex(item['request_wire_sha256'],64)
        need(item['request_wire_sha256']==digest,'REQUEST_WIRE_HASH')
        need(item['authority']=='none','RESPONSE_AUTHORITY')
    need(ready['core_sha256']==CORE_SHA256,'CORE_PIN')
    need(result['completion_grant'] is False,'COMPLETION_GRANT')
    need(type(result['core_ran']) is bool,'CORE_RAN_TYPE')
    status,reason=result['status'],result['reason']
    need(type(status) is str and type(reason) is str,'STATUS_REASON_TYPE')
    need(status in ('DISABLED','REJECTED','RESULT'),'RESULT_STATUS')
    error=_public_error(request)
    if error is not None:
        need(status=='REJECTED' and reason==error and result['core_ran'] is False
             and result['result'] is None,'PRECORE_REJECTION_SEMANTICS')
    elif not request.get('enabled',False):
        # This bounded disabled response cannot legitimately reach output overflow.
        need(status=='DISABLED' and reason=='disabled' and result['core_ran'] is False
             and result['result'] is None,'DISABLED_SEMANTICS')
    elif status=='REJECTED':
        need(result['result'] is None,'REJECTED_RESULT')
        # _to_internal precedes core entry; INTERNAL_ERROR can preserve either flag.
        # OUTPUT_TOO_LARGE after this bounded valid enabled request preserves true.
        need(reason=='INTERNAL_ERROR' or (result['core_ran'] is True and
             (reason=='OUTPUT_TOO_LARGE' or reason in _POSTCORE_REJECTED)),
             'POSTVALIDATION_REJECTION_SEMANTICS')
    else:
        need(status=='RESULT' and result['core_ran'] is True,'RESULT_CORE_SEMANTICS')
        _advice(result['result'],request['input'])
        need(reason==result['result']['reason'],'RESULT_REASON_MISMATCH')
    return PairConsistency(_freeze(ready),_freeze(result),digest,hashlib.sha256(response_wire).hexdigest())

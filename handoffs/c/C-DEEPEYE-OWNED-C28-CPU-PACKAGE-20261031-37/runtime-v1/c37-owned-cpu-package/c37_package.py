"""Finite public-input computation. No source/BOOT authentication or authority.

Only load-time reads of the fixed pinned core; process_wire performs no I/O.
Full proofs and original provider association remain outside this child.
"""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import types

ABI = 'c37-owned-cpu-package/v1'
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


def decode_request(wire):
    need(type(wire) is bytes and 5 <= len(wire) <= MAX_WIRE, 'FRAME_BUDGET')
    size = int.from_bytes(wire[:4], 'little')
    need(1 <= size <= MAX_PAYLOAD and size == len(wire) - 4, 'FRAME_LENGTH')
    return _parse(wire[4:])


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


def _to_internal(public):
    result = copy.deepcopy(public)
    result['now_tick_ms'] = Fraction(result.pop('now_qpc_ns'), 1_000_000)
    for obs in result['history'] + [result['observation']]:
        for old, new in (('adc_qpc_ns', 'adc_tick_ms'), ('em_qpc_ns', 'em_tick_ms')):
            ns = obs.pop(old)
            obs[new] = None if ns is None else Fraction(ns, 1_000_000)
    return result


def _ns(value):
    need(type(value) is Fraction, 'INTERNAL_TIME_TYPE')
    ns = value * 1_000_000
    need(ns.denominator == 1, 'INTERNAL_TIME_LOSS')
    return integer(ns.numerator)


def _from_internal(value):
    result = copy.deepcopy(value)
    result['now_qpc_ns'] = _ns(result.pop('now_tick_ms'))
    for obs in result['history'] + [result['observation']]:
        for old, new in (('adc_tick_ms', 'adc_qpc_ns'), ('em_tick_ms', 'em_qpc_ns')):
            ms = obs.pop(old)
            obs[new] = None if ms is None else _ns(ms)
    return result


def _validate_internal(request):
    validate_public(_from_internal(request))
    return request['history'] + [request['observation']]


# One fixed startup dependency, verified before executing its original bytes.
_core_path = Path(__file__).with_name('frozen_c28.py')
_raw_core = _core_path.read_bytes()
need(hashlib.sha256(_raw_core).hexdigest() == CORE_SHA256, 'CORE_HASH_MISMATCH')
_FROZEN = types.ModuleType('_c37_frozen_c28')
exec(compile(_raw_core, str(_core_path), 'exec'), _FROZEN.__dict__)
_globals = _FROZEN.recommend.__globals__.copy()
_globals['_validate'] = _validate_internal
_CORE = types.FunctionType(_FROZEN.recommend.__code__, _globals,
                           _FROZEN.recommend.__name__, _FROZEN.recommend.__defaults__,
                           _FROZEN.recommend.__closure__)
del _raw_core


def _infer(public, execution):
    internal = _to_internal(public)
    execution['core_ran'] = True
    result = _CORE(internal)
    # The output shape is a NEW ABI. Original numerical decisions remain intact.
    result['observation'] = copy.deepcopy(public['observation'])
    by_id = {obs['sample_id']: obs for obs in public['history'] + [public['observation']]}
    for cell in result['map_cells']:
        ns = _ns(cell.pop('em_tick_ms'))
        need(ns == by_id[cell['sample_id']]['em_qpc_ns'], 'OUTPUT_TIME_MISMATCH')
        cell['em_qpc_ns'] = ns
    tree(result)
    return result


def _ids(value):
    exact(value, _IDS)
    for key in ('operation_id', 'run_id', 'actor_instance_id'):
        need(type(value[key]) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}', value[key])
             is not None, 'LABEL_FORMAT')
    integer(value['invocation_id'], 1)
    _hex(value['tested_commit'], 40); _hex(value['package_manifest_sha256'], 64)


def process_wire(wire):
    """One bounded request -> correlated READY+RESULT; never grants completion."""
    need(type(wire) is bytes and len(wire) <= MAX_WIRE, 'FRAME_BUDGET')
    wire_hash = hashlib.sha256(wire).hexdigest()
    ids = None
    execution = {'core_ran': False}
    result = None
    status, reason = 'REJECTED', 'INVALID_REQUEST'
    try:
        request = decode_request(wire)
        need(type(request) is dict, 'INVALID_SHAPE')
        keys = {'abi', 'kind', 'echo_ids', 'input'}
        need(set(request) in (keys, keys | {'enabled'}), 'INVALID_SHAPE')
        need(request['abi'] == ABI and request['kind'] == 'recommend', 'ABI_VERSION')
        _ids(request['echo_ids'])
        ids = copy.deepcopy(request['echo_ids'])
        enabled = request.get('enabled', False)
        need(type(enabled) is bool, 'ENABLED_TYPE')
        public = request['input']
        validate_public(public)
        need(enabled == public['enabled'], 'ENABLED_CONFLICT')
        if not enabled:
            status, reason = 'DISABLED', 'disabled'
        else:
            result = _infer(public, execution)
            status, reason = 'RESULT', result['reason']
    except Rejected as error:
        status, reason, result = 'REJECTED', str(error), None
    except Exception:
        # Runtime errors are terminal diagnostics, not private traceback output.
        status, reason, result = 'REJECTED', 'INTERNAL_ERROR', None
    ready = dict(abi=ABI, kind='READY', echo_ids=ids, request_wire_sha256=wire_hash,
                 core_sha256=CORE_SHA256, authority='none')
    response = dict(abi=ABI, kind='RESULT', echo_ids=ids, request_wire_sha256=wire_hash,
                    status=status, core_ran=execution['core_ran'], authority='none',
                    completion_grant=False, result=result, reason=reason)
    try:
        payload = _dump(response)
        need(len(payload) <= 16384, 'OUTPUT_TOO_LARGE')
    except (Rejected, ValueError, OverflowError):
        response.update(status='REJECTED', result=None, reason='OUTPUT_TOO_LARGE')
        payload = _dump(response)
    output = frame(_dump(ready), 2048) + frame(payload)
    need(len(output) <= MAX_OUTPUT, 'OUTPUT_TOO_LARGE')
    return output


def make_request(echo_ids, public, *, enabled=False):
    """Serialization only. The caller must be the original host provider.

    This helper does not accept proof booleans and performs no dispatch. A must
    retain original full-proof/owner association before calling its transport.
    """
    value = dict(abi=ABI, kind='recommend', echo_ids=echo_ids, enabled=enabled, input=public)
    _ids(echo_ids); validate_public(public)
    need(type(enabled) is bool and enabled == public['enabled'], 'ENABLED_CONFLICT')
    return frame(_dump(value), MAX_PAYLOAD)

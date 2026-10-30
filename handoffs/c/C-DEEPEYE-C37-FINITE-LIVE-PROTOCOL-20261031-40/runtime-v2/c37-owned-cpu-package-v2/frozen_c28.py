"""Disabled-by-default, pure candidate advice; no transport or control authority.

The proposal input is supplied by A's trusted adapter. Structural validation
does not authenticate board bytes, physical sampling, timing or executed actions.
Only standard-library math/JSON/copy are used; no source/world/model imports.
"""
import copy
import json
import math
import re

MAX_JSON_BYTES = 262144
MAX_HISTORY = 32
MAX_CELLS = 32
MAX_REUSE_DISPLACEMENT_M = 0.25  # Candidate reuse gate, never measured sensor range.
MAX_REUSE_FORWARD_ANGLE_DEG = 15.0
MAX_NATIVE_DIRECTION_ANGLE_DEG = 30.0
_ANGLE_DOT_TOLERANCE = 1e-12  # Floating arithmetic only, not physical uncertainty.
PRODUCER_SHA256 = '6a5f70a6acdaa6de52fc72d678d452956861370e1d143b70219ced107c5a04c9'
PROFILE = 'deepeye_forward_profile_candidate_v1'
_LIMIT = (1 << 31) - 1
_REQUEST = {'schema_version', 'enabled', 'binding', 'now_tick_ms', 'pose',
            'goal_m', 'observation', 'history', 'executed_actions'}
_BINDING = {'run_id', 'build_sha256', 'boot_sha256', 'session', 'config_epoch',
            'clock_domain', 'source_id', 'source_mode', 'profile_id',
            'producer_sha256', 'topology_id'}
_OBS = {'binding', 'sample_id', 'trigger_id', 'sequence', 'board_frame_sha256',
        'source_record_sha256', 'adc_tick_ms', 'em_tick_ms', 'em_origin_sample_id',
        'counts', 'quality', 'adc_pose', 'em_pose', 'cause_action_id'}
_ACTION = {'binding', 'action_id', 'observation_sample_id', 'at_tick_ms',
           'from_pose', 'to_pose'}


class Rejected(ValueError):
    """Malformed, contradictory or unbounded proposal input."""


def _need(condition, reason):
    if not condition:
        raise Rejected(reason)


def _object(value, keys, name):
    _need(type(value) is dict and set(value) == keys, name + ': exact keys required')


def _integer(value, low, high, name):
    _need(type(value) is int and low <= value <= high, name + ': integer bound')
    return value


def _number(value, low, high, name):
    _need(type(value) in (int, float), name + ': finite number required')
    try:
        good = math.isfinite(value) and low <= value <= high
    except OverflowError:
        good = False
    _need(good, name + ': finite bound')
    return float(value)


def _label(value, name):
    _need(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}', value)
          is not None, name + ': label')


def _hash(value):
    _need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'hash format')


def _vector(value, size, bound, name):
    _need(type(value) is list and len(value) == size, name + ': array length')
    return [_number(v, -bound, bound, name) for v in value]


def _pose(value):
    _object(value, {'position_m', 'orientation_xyzw'}, 'pose')
    _vector(value['position_m'], 3, 1000, 'position_m')
    q = _vector(value['orientation_xyzw'], 4, 1, 'orientation_xyzw')
    _need(abs(sum(x*x for x in q) - 1) <= 1e-12, 'quaternion must be normalized')


def _binding(value):
    _object(value, _BINDING, 'binding')
    for key in ('run_id', 'clock_domain'):
        _label(value[key], key)
    for key in ('build_sha256', 'boot_sha256', 'producer_sha256'):
        _hash(value[key])
    _integer(value['session'], 0, (1 << 32)-1, 'session')
    _integer(value['config_epoch'], 0, 255, 'epoch')
    _integer(value['source_id'], 4, 4, 'source4')
    _integer(value['topology_id'], 1, 2, 'required H12 topology')
    _need(value['source_mode'] == 'twin_fixture' and value['profile_id'] == PROFILE
          and value['producer_sha256'] == PRODUCER_SHA256, 'candidate source/profile pin')


def _tick(value, period, name):
    _integer(value, 0, _LIMIT, name)
    _need(value % period == 0, name + ': grid')


def decode_counts(counts):
    """Four quantized centre estimates; null stays null, never FORCE features."""
    _need(type(counts) is list and len(counts) == 4, 'four counts required')
    lows = (math.log10(0.2), -2.0, -2.0, 0.0)
    spans = (4.0, 4.0, 4.0, 2.0)
    result = []
    for q, low, span in zip(counts, lows, spans):
        if q is None:
            result.append(None)
        else:
            _integer(q, 0, 4095, 'count')
            result.append(low + span*q/4095)
    return result


def _observation(obs, binding, now):
    _object(obs, _OBS, 'observation')
    _binding(obs['binding'])
    _need(obs['binding'] == binding, 'observation context/build changed')
    for key in ('sample_id', 'trigger_id'):
        _label(obs[key], key)
    for key in ('board_frame_sha256', 'source_record_sha256'):
        _hash(obs[key])
    _integer(obs['sequence'], 0, (1 << 32)-1, 'sequence')
    _tick(obs['adc_tick_ms'], 10, 'ADC tick')
    _need(obs['adc_tick_ms'] <= now, 'future ADC observation')
    _pose(obs['adc_pose'])
    q = _integer(obs['quality'], 0, 0x1FFF, 'producer quality')
    vals = decode_counts(obs['counts'])
    em_valid = q & 7
    _need(em_valid in (0, 7) and bool(q & 0x1000) == (em_valid == 0), 'EM validity/fault')
    _need(not q & 0x800, 'C3 cannot be held')
    for i, value in enumerate(vals):
        valid, sat, held = bool(q & (1 << i)), bool(q & (16 << i)), bool(q & (256 << i))
        _need((value is not None) == valid, 'count/null validity mismatch')
        _need(valid or not (sat or held), 'invalid saturation/hold')
        if i < 3 and sat:
            _need(obs['counts'][i] in (0, 4095), 'saturated EM endpoint')
    if q & 8:
        _need(obs['adc_tick_ms'] >= 90, 'C3 startup')
        if q & 0x80:
            _need(vals[3] + 1/4095 >= math.sqrt(0.4), 'C3 saturation window')
    if em_valid:
        _tick(obs['em_tick_ms'], 50, 'EM tick')
        age = obs['adc_tick_ms'] - obs['em_tick_ms']
        _need(0 <= age <= 100, 'EM source age')
        _need(q & 0x700 == (0x700 if age else 0), 'held/original EM time')
        _label(obs['em_origin_sample_id'], 'EM origin')
        _pose(obs['em_pose'])
        if age == 0:
            _need(obs['em_origin_sample_id'] == obs['sample_id'] and
                  obs['em_pose'] == obs['adc_pose'], 'fresh EM origin/pose')
    else:
        _need(obs['em_tick_ms'] is None and obs['em_origin_sample_id'] is None
              and obs['em_pose'] is None, 'invalid EM origin must be null')
    if obs['cause_action_id'] is not None:
        _label(obs['cause_action_id'], 'cause action')


def _bounded_tree(value, depth=0, count=None):
    """Bound direct mapping calls before copying/serializing; reject foreign objects."""
    if count is None:
        count = [0]
    count[0] += 1
    _need(depth <= 10 and count[0] <= 16000, 'JSON tree budget')
    _need(type(value) in (dict, list, str, int, float, bool, type(None)), 'JSON type')
    if type(value) is dict:
        _need(len(value) <= 32 and all(type(k) is str and len(k) <= 96 for k in value), 'object bound')
        for item in value.values():
            _bounded_tree(item, depth+1, count)
    elif type(value) is list:
        _need(len(value) <= MAX_HISTORY, 'array bound')
        for item in value:
            _bounded_tree(item, depth+1, count)
    elif type(value) is str:
        _need(len(value) <= 192, 'string bound')
    elif type(value) is int:
        _need(abs(value) <= (1 << 64), 'integer budget')
    elif type(value) is float:
        _need(math.isfinite(value), 'nonfinite JSON')


def _validate(request):
    _bounded_tree(request)
    _object(request, _REQUEST, 'request')
    _integer(request['schema_version'], 1, 1, 'schema_version')
    _need(type(request['enabled']) is bool, 'enabled bool')
    _binding(request['binding'])
    now = _integer(request['now_tick_ms'], 0, _LIMIT, 'same-domain now')
    _pose(request['pose'])
    _vector(request['goal_m'], 3, 1000, 'legal goal_m')
    history, actions = request['history'], request['executed_actions']
    _need(type(history) is list and type(actions) is list, 'history/action arrays')
    _need(len(history) + len(actions) + 1 <= MAX_HISTORY, 'combined history budget')
    observations = history + [request['observation']]
    seen, previous = {}, None
    for obs in observations:
        _observation(obs, request['binding'], now)
        _need(obs['sample_id'] not in seen, 'duplicate sample identity')
        if previous is not None:
            _need(obs['sequence'] > previous['sequence'] and
                  obs['adc_tick_ms'] > previous['adc_tick_ms'], 'duplicate/reversed observation')
        if obs['quality'] & 0x700:
            original = seen.get(obs['em_origin_sample_id'])
            _need(original is not None and original['adc_tick_ms'] == obs['em_tick_ms']
                  and original['em_tick_ms'] == obs['em_tick_ms'], 'held origin absent')
            _need(previous is not None and previous['em_tick_ms'] == obs['em_tick_ms'], 'held revival')
            _need(original['counts'][:3] == obs['counts'][:3] and
                  original['quality'] & 0x70 == obs['quality'] & 0x70 and
                  original['em_pose'] == obs['em_pose'], 'held value/saturation/pose changed')
        seen[obs['sample_id']] = obs
        previous = obs
    action_ids, last_tick = {}, -1
    for action in actions:
        _object(action, _ACTION, 'executed action')
        _binding(action['binding'])
        _need(action['binding'] == request['binding'], 'action context/build changed')
        for key in ('action_id', 'observation_sample_id'):
            _label(action[key], key)
        _need(action['action_id'] not in action_ids, 'duplicate action')
        tick = _integer(action['at_tick_ms'], 0, now, 'executed time')
        _need(tick >= last_tick, 'action time reversed')
        causal = seen.get(action['observation_sample_id'])
        _need(causal is not None and causal['adc_tick_ms'] <= tick, 'action observation cause')
        _pose(action['from_pose']); _pose(action['to_pose'])
        action_ids[action['action_id']] = action
        last_tick = tick
    for obs in observations:
        if obs['cause_action_id'] is not None:
            action = action_ids.get(obs['cause_action_id'])
            _need(action is not None and action['at_tick_ms'] < obs['adc_tick_ms'], 'observation action cause')
    return observations


def _rotate(q, v):
    x, y, z, w = q
    return [(1-2*(y*y+z*z))*v[0]+2*(x*y-z*w)*v[1]+2*(x*z+y*w)*v[2],
            2*(x*y+z*w)*v[0]+(1-2*(x*x+z*z))*v[1]+2*(y*z-x*w)*v[2],
            2*(x*z-y*w)*v[0]+2*(y*z+x*w)*v[1]+(1-2*(x*x+y*y))*v[2]]


def _norm(v):
    return math.sqrt(sum(x*x for x in v))


def _clip(value):
    return max(0.0, min(1.0, value))


def _direction_supported(a, b, angle_degrees):
    # Normalize the comparison because accepted quaternions have finite norm
    # tolerance. Roll does not change a pose's forward axis.
    cosine = sum(x*y for x, y in zip(a, b)) / (_norm(a)*_norm(b))
    return cosine >= math.cos(math.radians(angle_degrees)) - _ANGLE_DOT_TOLERANCE


def _poses_applicable(native, adc, current):
    """All three own poses stay in one small, explicit candidate reuse envelope.

    Pairwise checks prevent opposing offsets from each being close to native
    while current and ADC are far apart. This is not physical source validity.
    """
    for a, b in ((native, adc), (native, current), (adc, current)):
        distance = _norm([x-y for x, y in zip(a['position_m'], b['position_m'])])
        if distance > MAX_REUSE_DISPLACEMENT_M:
            return False
        if not _direction_supported(_rotate(a['orientation_xyzw'], [0, 0, 1]),
                                    _rotate(b['orientation_xyzw'], [0, 0, 1]),
                                    MAX_REUSE_FORWARD_ANGLE_DEG):
            return False
    return True


def _risk(values):
    return _clip(abs(values[0]-1.0)/2.0 + values[3]/2.0)


def recommend(request):
    """Return detached bounded advice. Raises Rejected on invalid proposal input.

    Default mode is disabled: callers must explicitly supply enabled=true.
    No raw bytes/provider boolean can turn this function into authentication.
    """
    observations = _validate(request)
    obs = request['observation']
    result = {'schema_version': 1, 'planner_id': 'candidate_four_channel_planner_v1',
              'candidate_only': True, 'authorization': 'none', 'status': 'STOP',
              'reason': 'disabled', 'risk': 1.0, 'uncertainty': 1.0,
              'direction_world': [0.0, 0.0, 0.0], 'speed_limit_m_s': 0.0,
              'observation': copy.deepcopy(obs), 'map_cells': [], 'independent_em_count': 0}
    if not request['enabled']:
        return result
    quality = obs['quality']
    if quality & 0xF != 0xF or quality & 0x10F0:
        result['reason'] = 'invalid_faulted_or_saturated'
        return result
    age = request['now_tick_ms'] - obs['em_tick_ms']
    if age > 100 or request['now_tick_ms'] - obs['adc_tick_ms'] > 100:
        result['reason'] = 'original_sample_expired'
        return result
    values = decode_counts(obs['counts'])
    # Only independent, clean native EM contributes map evidence. Held ADCs
    # never add cells or lower uncertainty, and map positions are original poses.
    for old in observations:
        if old['quality'] & 0x1FFF == 15 and old['adc_tick_ms'] == old['em_tick_ms']:
            result['map_cells'].append({'sample_id': old['sample_id'],
                'em_tick_ms': old['em_tick_ms'], 'pose': copy.deepcopy(old['em_pose']),
                'risk': _risk(decode_counts(old['counts']))})
    result['independent_em_count'] = len(result['map_cells'])
    result['uncertainty'] = _clip(0.5 + 0.4*age/100 + 2/4095)
    # Old forward measurements are not evidence for arbitrary new positions or
    # orientations. Keep their original map cells, but refuse to reuse them for
    # current advice outside this candidate applicability envelope.
    if not _poses_applicable(obs['em_pose'], obs['adc_pose'], request['pose']):
        result.update(reason='original_observation_pose_inapplicable', uncertainty=1.0)
        return result
    delta = [g-p for g, p in zip(request['goal_m'], request['pose']['position_m'])]
    distance = _norm(delta)
    if distance <= 0.02:
        result['reason'] = 'goal_near_requires_authority_completion'
        return result
    if values[3] >= 0.8:
        result['reason'] = 'contact_vibration_risk'
        return result
    goal = [v/distance for v in delta]
    q = request['pose']['orientation_xyzw']
    # The directional signal belongs to its original native acquisition frame,
    # not the current drill frame. Compare each candidate in that original frame.
    native_q = obs['em_pose']['orientation_xyzw']
    inverse_native = [-native_q[0], -native_q[1], -native_q[2], native_q[3]]
    candidates = []
    for x in (-0.35, 0.0, 0.35):
        for y in (-0.35, 0.0, 0.35):
            scale = math.sqrt(1+x*x+y*y)
            direction = _rotate(q, [x/scale, y/scale, 1/scale])
            progress = sum(a*b for a, b in zip(direction, goal))
            if progress <= 0:
                continue
            native = _rotate(inverse_native, direction)
            if not _direction_supported(native, [0, 0, 1], MAX_NATIVE_DIRECTION_ANGLE_DEG):
                continue
            # Empirical lobe interpolation, explicitly not an inversion/map oracle.
            predicted = values[0] + 0.5*(values[1]*native[0]/0.35 + values[2]*native[1]/0.35)
            risk = _clip(abs(predicted-1.0)/2 + values[3]/2)
            endpoint = [p+0.25*d for p, d in zip(request['pose']['position_m'], direction)]
            map_cost = 0.0
            for cell in result['map_cells']:
                square = sum((a-b)**2 for a, b in zip(endpoint, cell['pose']['position_m']))
                map_cost = max(map_cost, cell['risk']/(1+square))
            # Discourage undoing the last actual displacement, never an imagined action.
            undo = 0.0
            if request['executed_actions']:
                action = request['executed_actions'][-1]
                displacement = [b-a for a, b in zip(action['from_pose']['position_m'], action['to_pose']['position_m'])]
                length = _norm(displacement)
                if length:
                    undo = max(0.0, -sum(d*v/length for d, v in zip(direction, displacement)))
            cost = 1-progress + 2*risk + 0.2*map_cost + 0.1*undo
            candidates.append((cost, abs(x)+abs(y), x, y, risk, direction))
    if not candidates:
        result['reason'] = 'no_forward_goal_progress'
        return result
    chosen = min(candidates)
    result['risk'] = chosen[4]
    if chosen[4] >= 0.8:
        result['reason'] = 'candidate_risk_limit'
        return result
    result.update(status='ADVISE', reason='bounded_observation_goal_search',
                  direction_world=chosen[5],
                  speed_limit_m_s=0.25*(1-chosen[4])*(1-result['uncertainty'])*min(1.0, distance/0.5))
    return result


def recommend_json(raw):
    """Strict UTF-8 JSON -> canonical JSON bytes. No file/stream access."""
    _need(type(raw) is bytes and len(raw) <= MAX_JSON_BYTES, 'JSON byte budget/type')
    def pairs(items):
        obj = {}
        for key, value in items:
            _need(key not in obj, 'duplicate JSON field')
            obj[key] = value
        return obj
    def constant(_):
        raise Rejected('nonfinite JSON constant')
    try:
        request = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError, ValueError) as exc:
        raise Rejected('invalid strict JSON') from exc
    result = recommend(request)
    return json.dumps(result, allow_nan=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

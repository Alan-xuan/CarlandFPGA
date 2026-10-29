"""Bounded diagnostic ABI over one frozen C28 planner; no control authority.

Only module initialization reads the fixed, hash-pinned C28 dependency. Public
calls are pure. JSON correlations are not authentication: real adoption requires
A's original trusted Root to supply the actual registries described in README.
"""
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
from types import FunctionType, ModuleType

ABI = 'private_raw4_planner_abi_v1'
CORE_SHA256 = '70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'
PRODUCER_SHA256 = '6a5f70a6acdaa6de52fc72d678d452956861370e1d143b70219ced107c5a04c9'
PROFILE = 'deepeye_forward_profile_candidate_v1'
NOTE = 'not_calibrated;not_em_surrogate_v2;not_formally_frozen'
ENCODING = 'candidate_four_channel_quality_v1'
TIME_BASIS = 'trusted_root_source_schedule_not_physical_sample_authentication'
CHANNELS = ['log10_rho_apparent', 'yaw_log10_rho_difference',
            'pitch_log10_rho_difference', 'near_bit_vibration_rms_g']
MAX_BYTES = 262144
MAX_HISTORY = 32
AGE_NS = 100000000
NS_PER_MS = 1000000
_CTX = set('operation_id request_hash tested_commit build_manifest_sha256 boot_id session_id tag clock_domain_id'.split())
_IDENTITY = set('context request_seq request_sha256 capture_sha256 generation trigger_id source_admission_index original_host_injection_qpc_ns receiver_upper_qpc_ns'.split())
_TIME = set('adc_tick_ms em_tick_ms source_start_tick_ms source_start_monotonic_ns admission_received_monotonic_ns adc_source_age_ns em_source_age_ns time_basis'.split())
_CANDIDATE = set('schema kind profile_id profile_status profile_note source_mode quality_encoding source_id transport_source channel_names channel_counts quality source_time observation_identity diagnostic_flags'.split())
_FLAGS = set('source_fresh_at_capture all_channels_valid injection_to_receiver_upper_ns target100ms_met target100ms_scope formal_100ms_acceptance formal_H12 transport_authenticated BOOT_authenticated physical_sample_authenticated compression_verified CPU_completion_created movement_authorized'.split())
_SCOPES = {'unassociated_diagnostic', 'synthetic_diagnostic_fixture', 'root_supplied_diagnostic'}


class Rejected(ValueError):
    """Malformed, inconsistent or out-of-budget JSON; not an authority STOP."""


class _Unavailable(Exception):
    pass


def _need(test, reason):
    if not test:
        raise Rejected(reason)


def _present(value, reason):
    if value is None:
        raise _Unavailable(reason)
    return value


def _obj(value, fields, name):
    _need(type(value) is dict and set(value) == fields, name + ': exact fields')


def _uint(value, bits=63, name='integer'):
    _need(type(value) is int and 0 <= value < 1 << bits, name + ': strict unsigned integer')
    return value


def _text(value, name='identity'):
    _need(type(value) is str and 0 < len(value) <= 192 and
          all(32 <= ord(c) < 127 for c in value), name + ': bounded printable ASCII')


def _hash(value, size=64):
    _need(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % size, value) is not None, 'digest format')


def _context(value):
    _obj(value, _CTX, 'private context')
    for name in _CTX - {'tag'}:
        _text(value[name], name)
    for name, size in (('request_hash', 64), ('tested_commit', 40),
                       ('build_manifest_sha256', 64), ('clock_domain_id', 32)):
        _hash(value[name], size)
    _need(_uint(value['tag'], 32) > 0, 'nonzero tag')


def _tree(value, depth=0, nodes=None, key=None):
    if nodes is None:
        nodes = [0]
    nodes[0] += 1
    _need(depth <= 16 and nodes[0] <= 16000, 'JSON depth/node budget')
    _need(type(value) in (dict, list, str, int, float, bool, type(None)), 'strict JSON types')
    if type(value) is dict:
        _need(len(value) <= 32 and all(type(k) is str and len(k) <= 96 for k in value), 'object budget')
        for k, v in value.items():
            _tree(v, depth+1, nodes, k)
    elif type(value) is list:
        _need(len(value) <= MAX_HISTORY, 'array budget')
        for v in value:
            _tree(v, depth+1, nodes)
    elif type(value) is str:
        _need(len(value) <= (16384 if key in ('request_raw', 'capture_raw') else 192), 'string budget')
    elif type(value) is int:
        _need(abs(value) <= (1 << 64), 'integer budget')
    elif type(value) is float:
        _need(math.isfinite(value), 'nonfinite number')


def _json_bytes(value, newline=False):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + ('\n' if newline else '')).encode('utf-8')


def _parse(raw, max_bytes=MAX_BYTES):
    _need(type(raw) is bytes and 0 < len(raw) <= max_bytes, 'JSON bytes budget/type')
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise Rejected('nonfinite JSON constant')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Rejected('invalid strict JSON: ' + str(exc)) from exc
    _tree(result)
    return result


def _number(v, bound):
    _need(type(v) in (int, float), 'finite scalar type')
    _need(-bound <= v <= bound and math.isfinite(v), 'finite scalar bound')


def _vector(v, n, bound):
    _need(type(v) is list and len(v) == n, 'vector size')
    for x in v:
        _number(x, bound)


def _pose(p):
    _obj(p, {'position_m', 'orientation_xyzw'}, 'own pose')
    _vector(p['position_m'], 3, 1000)
    _vector(p['orientation_xyzw'], 4, 1)
    _need(abs(sum(x*x for x in p['orientation_xyzw'])-1) <= 1e-12, 'unit quaternion')


def _tick(v, period):
    _uint(v, 31, 'original model tick')
    _need(v % period == 0, 'original model tick grid')


def _source_ns(t, tick):
    if tick is None:
        return None
    _need(tick >= t['source_start_tick_ms'], 'source predates original anchor')
    return _uint(t['source_start_monotonic_ns'] +
                 (tick-t['source_start_tick_ms'])*NS_PER_MS, name='derived original source QPC')


def _quality(counts, quality, adc, em):
    _uint(quality, 13, 'producer quality')
    _need(type(counts) is list and len(counts) == 4, 'four returned counts')
    _tick(adc, 10)
    valid_em = quality & 7
    _need(valid_em in (0, 7) and bool(quality & 0x1000) == (valid_em == 0), 'EM validity/fault')
    _need(not quality & 0x800, 'C3 is never held')
    for ch, count in enumerate(counts):
        valid, sat, held = quality & (1 << ch), quality & (16 << ch), quality & (256 << ch)
        _need((count is not None) == bool(valid), 'returned null/validity mismatch')
        if not valid:
            _need(not (sat or held), 'invalid saturation/held')
        else:
            _need(_uint(count, 12, 'returned count') <= 4095, 'count range')
            if ch < 3 and sat:
                _need(count in (0, 4095), 'saturated EM endpoint')
    if quality & 8:
        _need(adc >= 90, 'C3 startup uses producer model tick')
        if quality & 0x80:
            _need(2*counts[3]/4095 + 1/4095 >= math.sqrt(0.4), 'C3 saturation window')
    if valid_em:
        _tick(em, 50)
        _need(0 <= adc-em <= 100, 'original EM/model age')
        _need(quality & 0x700 == (0x700 if em < adc else 0), 'held/original time')
    else:
        _need(em is None, 'faulted EM time must be null')


def _candidate(c):
    _obj(c, _CANDIDATE, 'actual candidate')
    _need(type(c['schema']) is int and c['schema'] == 1 and c['kind'] == 'candidate_four_channel_input', 'candidate schema')
    _need(c['profile_id'] == PROFILE and c['profile_status'] == 'candidate_only' and c['profile_note'] == NOTE,
          'candidate profile')
    _need(c['quality_encoding'] == ENCODING and c['source_mode'] == 'twin_fixture' and
          c['transport_source'] == 'software_fixture' and type(c['source_id']) is int and c['source_id'] == 4,
          'diagnostic source namespace')
    _need(c['channel_names'] == CHANNELS, 'channel order')
    t, ident, flags = c['source_time'], c['observation_identity'], c['diagnostic_flags']
    _obj(t, _TIME, 'source time'); _obj(ident, _IDENTITY, 'observation identity'); _obj(flags, _FLAGS, 'diagnostic flags')
    _context(ident['context'])
    for name in ('request_seq', 'generation', 'trigger_id', 'source_admission_index'):
        _uint(ident[name], 32, name)
    _need(ident['request_seq'] > 0 and ident['generation'] > 0, 'positive request/generation')
    _hash(ident['request_sha256']); _hash(ident['capture_sha256'])
    times = ident['original_host_injection_qpc_ns']
    _need(type(times) is list and len(times) == 4, 'four injection times')
    for v in times:
        _uint(v)
    now = _uint(ident['receiver_upper_qpc_ns'])
    _need(0 < times[0] <= times[1] <= times[2] <= times[3] <= now, 'injection/receiver order')
    _tick(t['source_start_tick_ms'], 10); _uint(t['source_start_monotonic_ns'])
    received = _uint(t['admission_received_monotonic_ns'])
    _need(t['time_basis'] == TIME_BASIS, 'source time namespace')
    _quality(c['channel_counts'], c['quality'], t['adc_tick_ms'], t['em_tick_ms'])
    adc, em = _source_ns(t, t['adc_tick_ms']), _source_ns(t, t['em_tick_ms'])
    _need(adc <= received <= times[0], 'admission before original injection')
    for name, sample in (('adc_source_age_ns', adc), ('em_source_age_ns', em)):
        if sample is None:
            _need(t[name] is None, 'null EM age')
        else:
            _uint(t[name]); _need(t[name] == now-sample, 'original source age mismatch')
    for name in _FLAGS - {'injection_to_receiver_upper_ns', 'target100ms_scope', 'formal_100ms_acceptance', 'formal_H12'}:
        _need(type(flags[name]) is bool, 'diagnostic boolean type')
    _uint(flags['injection_to_receiver_upper_ns'])
    _need(flags['injection_to_receiver_upper_ns'] == now-times[0], 'injection latency mismatch')
    fresh = now-adc <= AGE_NS and em is not None and now-em <= AGE_NS and not c['quality'] & 0x1000
    _need(flags['source_fresh_at_capture'] == bool(fresh) and
          flags['all_channels_valid'] == (c['quality'] & 15 == 15), 'source flags mismatch')
    _need(flags['target100ms_scope'] in ('conservative_receiver_upper_bound', 'private_HostOwner_request_to_receive'), 'timing scope')
    if flags['target100ms_scope'] == 'conservative_receiver_upper_bound':
        _need(flags['target100ms_met'] == (now-times[0] <= AGE_NS), 'timing flag mismatch')
    _need(flags['formal_100ms_acceptance'] == flags['formal_H12'] == 'not_run', 'no formal acceptance')
    for name in ('transport_authenticated', 'BOOT_authenticated', 'physical_sample_authenticated',
                 'compression_verified', 'CPU_completion_created', 'movement_authorized'):
        _need(flags[name] is False, 'no authority claims')
    return adc, em


def _raw(text):
    _need(type(text) is str, 'original raw line required')
    try:
        raw = text.encode('utf-8')
    except UnicodeError as exc:
        raise Rejected('invalid UTF8 original line') from exc
    _need(raw.endswith(b'\n') and raw.count(b'\n') == 1 and b'\r' not in raw, 'original single line')
    return raw, _parse(raw, 16384)


def _counter(values):
    _need(type(values) is list and len(values) == 3, 'three counters')
    for v in values:
        _uint(v, 32)


def _returned(c, record, config):
    request_raw, request = _raw(_present(record['request_raw'], 'missing_original_request'))
    capture_raw, capture = _raw(_present(record['capture_raw'], 'missing_original_capture'))
    ident = c['observation_identity']; seq = ident['request_seq']; ctx = ident['context']
    _obj(request, set('schema kind context request_seq source_id source values qualities original_host_qpc_ns'.split()), 'raw request')
    _obj(capture, set('schema kind context request_seq request_sha256 generation trigger_id captures final_counters'.split()), 'raw capture')
    _need(type(request['schema']) is int and request['schema'] == 1 and request['kind'] == 'diagnostic_scan', 'raw request schema')
    _need(type(capture['schema']) is int and capture['schema'] == 1 and capture['kind'] == 'diagnostic_capture', 'raw capture schema')
    _context(request['context']); _context(capture['context'])
    _need(request['context'] == capture['context'] == ctx, 'raw context mismatch')
    _need(type(request['source_id']) is int and request['source_id'] == 4 and request['source'] == 'software_fixture', 'raw source4')
    for name in ('request_seq', 'generation', 'trigger_id'):
        _uint(capture[name], 32)
        _need(capture[name] == ident[name], 'capture identity mismatch')
    _need(_uint(request['request_seq'], 32) == seq, 'request sequence mismatch')
    _need(_json_bytes(request, True) == request_raw, 'canonical original request bytes')
    _need(hashlib.sha256(request_raw).hexdigest() == capture['request_sha256'] == ident['request_sha256'], 'request hash mismatch')
    _need(hashlib.sha256(capture_raw).hexdigest() == ident['capture_sha256'], 'capture hash mismatch')
    q = c['quality']
    qualities = [((q >> ch) & 1) | (((q >> (4+ch)) & 1) << 1) |
                 (((q >> (8+ch)) & 1) << 2) | (((q >> 12) & 1) << 3) for ch in range(4)]
    values = [0 if v is None else v for v in c['channel_counts']]
    for name, expected, bits in (('values', values, 16), ('qualities', qualities, 8),
                                 ('original_host_qpc_ns', ident['original_host_injection_qpc_ns'], 63)):
        _need(type(request[name]) is list and len(request[name]) == 4, 'raw four lanes')
        for v in request[name]:
            _uint(v, bits)
        _need(request[name] == expected, 'raw/request/candidate lane mismatch')
    _need(ident['generation'] == config['generation'] and
          ident['trigger_id'] == config['initial_trigger_id'] + seq, 'original generation/trigger progression')
    lanes = capture['captures']; baseline = config['baseline_counters']
    _need(type(lanes) is list and len(lanes) == 4, 'raw capture lane count')
    for ch, lane in enumerate(lanes):
        _obj(lane, {'channel', 'raw_words', 'pipeline_counters', 'ack_returned'}, 'raw lane')
        _need(type(lane['channel']) is int and lane['channel'] == ch and lane['ack_returned'] is True, 'lane channel/ack')
        words = lane['raw_words']; ticks = request['original_host_qpc_ns'][ch]
        _need(type(words) is list and len(words) == 10, 'ten raw words')
        for v in words:
            _uint(v, 32)
        expected = [values[ch], ch | qualities[ch] << 8, ticks & 0xffffffff, ticks >> 32,
                    4*(seq-1), 4*seq-1, ctx['tag'], ident['trigger_id'], ident['generation']]
        _need(words[:9] == expected, 'returned raw words mismatch')
        _counter(lane['pipeline_counters'])
        _need(lane['pipeline_counters'] == [baseline[0]+4*seq, baseline[1]+seq, baseline[2]+4*(seq-1)+ch+1], 'lane counters')
    _counter(capture['final_counters'])
    _need(capture['final_counters'] == [baseline[0]+4*seq, baseline[1]+seq, baseline[2]+4*seq], 'final counters')


def _admissions(items, config):
    _present(items, 'missing_source_admissions')
    _need(type(items) is list and len(items) <= MAX_HISTORY, 'bounded original admissions from origin')
    if not items:
        raise _Unavailable('missing_source_admissions')
    previous = None; last_native = None; consecutive = 0; native = {}
    for index, item in enumerate(items):
        _obj(item, set('index adc_tick_ms em_tick_ms channel_counts quality source_record_sha256 received_qpc_ns new_em_sample'.split()), 'Root source admission')
        _need(_uint(item['index'], 32) == index, 'original admissions must begin at zero with no omission')
        _hash(item['source_record_sha256'])
        _quality(item['channel_counts'], item['quality'], item['adc_tick_ms'], item['em_tick_ms'])
        adc, em = item['adc_tick_ms'], item['em_tick_ms']
        adc_ns, em_ns = _source_ns(config, adc), _source_ns(config, em)
        received = _uint(item['received_qpc_ns'])
        _need(0 <= received-adc_ns <= AGE_NS and (em_ns is None or 0 <= received-em_ns <= AGE_NS), 'source admission original age')
        if previous is None:
            _need(adc == config['source_start_tick_ms'], 'missing original source start')
            consecutive = 1
        else:
            _need(adc > previous['adc_tick_ms'] and received >= previous['received_qpc_ns'], 'source order')
            consecutive = min(10, consecutive+1) if adc-previous['adc_tick_ms'] == 10 else 1
        _need(bool(item['quality'] & 8) == (consecutive == 10), 'C3 original contiguous window')
        new = em is not None and em != last_native
        _need(type(item['new_em_sample']) is bool and item['new_em_sample'] == new, 'native admission flag')
        if new:
            _need(em == adc and (last_native is None or em > last_native), 'native admission/time equality')
            native[em] = index; last_native = em
        elif em is not None:
            _need(previous is not None and previous['em_tick_ms'] == em, 'held fault revival')
            _need(item['channel_counts'][:3] == previous['channel_counts'][:3] and
                  item['quality'] & 0x70 == previous['quality'] & 0x70, 'held source changed')
        previous = item
    return native


def _pose_receipt(value, index, qpc, missing):
    _present(value, missing)
    _obj(value, {'receipt_id', 'source_admission_index', 'acquisition_qpc_ns', 'pose'}, 'acquisition pose receipt')
    _text(value['receipt_id']); _uint(value['source_admission_index'], 32); _uint(value['acquisition_qpc_ns'])
    _need(value['source_admission_index'] == index and value['acquisition_qpc_ns'] == qpc, 'own pose/source association')
    _pose(value['pose'])
    return value['pose']


def _association(request, candidates):
    root = _present(request['root_receipt'], 'missing_root_receipt')
    _obj(root, {'kind', 'evidence_scope', 'config', 'source_admissions', 'captures', 'current_pose', 'action_registry'}, 'Root association')
    _need(root['kind'] == 'c29_root_association_v1' and root['evidence_scope'] == request['evidence_scope'] and
          root['evidence_scope'] != 'unassociated_diagnostic', 'association evidence namespace')
    config = _present(root['config'], 'missing_root_config')
    _obj(config, set('receipt_id context generation profile_id producer_sha256 source_policy quality_encoding source_mode transport_source source_start_tick_ms source_start_monotonic_ns goal_m baseline_counters initial_trigger_id'.split()), 'Root config')
    _text(config['receipt_id']); _context(config['context'])
    _need(_uint(config['generation'], 32) > 0, 'Root generation')
    _uint(config['initial_trigger_id'], 32); _counter(config['baseline_counters'])
    _tick(config['source_start_tick_ms'], 10); _uint(config['source_start_monotonic_ns'])
    _vector(config['goal_m'], 3, 1000)
    _need(config['profile_id'] == PROFILE and config['producer_sha256'] == PRODUCER_SHA256 and
          config['source_policy'] == 'candidate_causal_source_v1' and config['quality_encoding'] == ENCODING and
          config['source_mode'] == 'twin_fixture' and config['transport_source'] == 'software_fixture', 'Root source configuration')
    native = _admissions(root['source_admissions'], config)
    records = _present(root['captures'], 'missing_capture_associations')
    _need(type(records) is list and len(records) == len(candidates), 'one Root association per retained capture')
    current = _present(root['current_pose'], 'missing_current_pose')
    _obj(current, {'receipt_id', 'context', 'generation', 'at_qpc_ns', 'pose'}, 'current own pose')
    _text(current['receipt_id']); _context(current['context']); _uint(current['generation'], 32); _uint(current['at_qpc_ns'])
    _need(current['context'] == config['context'] and current['generation'] == config['generation'] and
          current['at_qpc_ns'] == request['now_qpc_ns'], 'current pose context/time')
    _pose(current['pose'])
    observations = []; by_capture = {}; previous = None
    for c, rec in zip(candidates, records):
        _present(rec, 'missing_capture_association')
        _obj(rec, set('capture_sha256 source_record_sha256 request_raw capture_raw adc_pose em_pose em_origin_capture_sha256 cause_action_id'.split()), 'capture association')
        ident, t = c['observation_identity'], c['source_time']; index = ident['source_admission_index']
        if index >= len(root['source_admissions']):
            raise _Unavailable('missing_source_admission_index')
        adm = root['source_admissions'][index]
        _need(ident['context'] == config['context'] and ident['generation'] == config['generation'], 'capture/config identity')
        _need(t['source_start_tick_ms'] == config['source_start_tick_ms'] and
              t['source_start_monotonic_ns'] == config['source_start_monotonic_ns'], 'original anchor mismatch')
        _hash(rec['capture_sha256']); _hash(rec['source_record_sha256'])
        _need(rec['capture_sha256'] == ident['capture_sha256'] and rec['capture_sha256'] not in by_capture, 'unique capture identity')
        _need(rec['source_record_sha256'] == adm['source_record_sha256'] and
              c['quality'] == adm['quality'] and c['channel_counts'] == adm['channel_counts'] and
              t['adc_tick_ms'] == adm['adc_tick_ms'] and t['em_tick_ms'] == adm['em_tick_ms'] and
              t['admission_received_monotonic_ns'] == adm['received_qpc_ns'], 'capture/source association mismatch')
        if previous is not None:
            _need(ident['request_seq'] > previous['request_seq'] and index > previous['source_admission_index'] and
                  ident['original_host_injection_qpc_ns'][0] > previous['original_host_injection_qpc_ns'][-1] and
                  ident['receiver_upper_qpc_ns'] >= previous['receiver_upper_qpc_ns'], 'retained capture order')
        _returned(c, rec, config)
        adc_ns, em_ns = _source_ns(t, t['adc_tick_ms']), _source_ns(t, t['em_tick_ms'])
        adc_pose = _pose_receipt(rec['adc_pose'], index, adc_ns, 'missing_adc_pose')
        em_pose = None; origin = None
        if em_ns is not None:
            _need(t['em_tick_ms'] in native, 'missing native admission')
            ni = native[t['em_tick_ms']]
            em_pose = _pose_receipt(rec['em_pose'], ni, em_ns, 'missing_em_pose')
            origin = _present(rec['em_origin_capture_sha256'], 'missing_held_board_origin')
            _hash(origin)
            if adm['new_em_sample']:
                _need(ni == index and adc_ns == em_ns and origin == ident['capture_sha256'] and em_pose == adc_pose, 'native original identity/pose')
            else:
                original = _present(by_capture.get(origin), 'missing_retained_native_board_origin')
                _need(original['em_tick_ms'] == original['adc_tick_ms'] == Fraction(em_ns, NS_PER_MS) and
                      original['counts'][:3] == c['channel_counts'][:3] and
                      original['quality'] & 0x70 == c['quality'] & 0x70 and original['em_pose'] == em_pose,
                      'held native board evidence mismatch')
        else:
            _need(rec['em_pose'] is None and rec['em_origin_capture_sha256'] is None, 'faulted EM association must be null')
        if rec['cause_action_id'] is not None:
            _text(rec['cause_action_id'])
        obs = {'sample_id': ident['capture_sha256'], 'counts': copy.deepcopy(c['channel_counts']),
               'quality': c['quality'], 'adc_tick_ms': Fraction(adc_ns, NS_PER_MS),
               'em_tick_ms': None if em_ns is None else Fraction(em_ns, NS_PER_MS),
               'adc_pose': copy.deepcopy(adc_pose), 'em_pose': copy.deepcopy(em_pose)}
        observations.append(obs); by_capture[ident['capture_sha256']] = obs; previous = ident
    registry = _present(root['action_registry'], 'missing_action_registry')
    _obj(registry, {'receipt_id', 'context', 'generation', 'as_of_qpc_ns', 'actions'}, 'occurred action registry')
    _text(registry['receipt_id']); _context(registry['context']); _uint(registry['generation'], 32); _uint(registry['as_of_qpc_ns'])
    _need(registry['context'] == config['context'] and registry['generation'] == config['generation'] and
          registry['as_of_qpc_ns'] == request['now_qpc_ns'], 'action registry context/time')
    actions = _present(registry['actions'], 'missing_occurred_actions')
    _need(type(actions) is list and len(actions)+len(candidates) <= MAX_HISTORY, 'combined history/action bound')
    ids = {}; previous_time = -1
    for action in actions:
        _obj(action, {'receipt_id', 'action_id', 'state', 'observation_capture_sha256', 'at_qpc_ns', 'from_pose', 'to_pose'}, 'occurred action')
        _text(_present(action['receipt_id'], 'missing_action_execution_receipt')); _text(action['action_id'])
        _need(action['state'] == 'executed', 'only actually executed actions')
        _need(action['action_id'] not in ids, 'duplicate action identity')
        _hash(action['observation_capture_sha256'])
        observed = _present(by_capture.get(action['observation_capture_sha256']), 'missing_action_observation')
        at = _uint(action['at_qpc_ns'])
        _need(previous_time <= at <= request['now_qpc_ns'], 'action time order')
        ci = next(c['observation_identity'] for c in candidates if c['observation_identity']['capture_sha256'] == action['observation_capture_sha256'])
        _need(at >= ci['receiver_upper_qpc_ns'], 'action must follow received observation')
        _pose(action['from_pose']); _pose(action['to_pose'])
        ids[action['action_id']] = action; previous_time = at
    for c, rec in zip(candidates, records):
        cause = rec['cause_action_id']
        if cause is not None:
            action = _present(ids.get(cause), 'missing_observation_action_cause')
            _need(action['at_qpc_ns'] < _source_ns(c['source_time'], c['source_time']['adc_tick_ms']), 'future/cyclic action cause')
    return {'enabled': True, 'now_tick_ms': Fraction(request['now_qpc_ns'], NS_PER_MS),
            'pose': copy.deepcopy(current['pose']), 'goal_m': copy.deepcopy(config['goal_m']),
            'observation': observations[-1], 'history': observations[:-1],
            'executed_actions': copy.deepcopy(actions)}


# Known local dependency only: no caller-selected module path, no plugin lookup.
_CORE_PATH = Path(__file__).resolve().parent.parent / 'C-DEEPEYE-CAUSAL-FOUR-CHANNEL-PLANNER-20261029-28' / 'candidate_four_channel_planner_v1.py'
_CORE_BYTES = _CORE_PATH.read_bytes()
if hashlib.sha256(_CORE_BYTES).hexdigest() != CORE_SHA256:
    raise ImportError('frozen C28 source hash mismatch')
_CORE_MODULE = ModuleType('_frozen_c28_for_private_raw4')
exec(compile(_CORE_BYTES, str(_CORE_PATH), 'exec'), _CORE_MODULE.__dict__)
_ORIGINAL = _CORE_MODULE.recommend


def _validate_view(view, expected):
    # Fixed internal seam: full JSON/source/receipt checks ran before projection.
    # Recheck the exact per-call projection, including rational absolute units.
    _need(type(view) is dict and view == expected, 'internal view differs from validated association')
    _need(type(view['now_tick_ms']) is Fraction, 'exact absolute QPC view')
    for obs in view['history'] + [view['observation']]:
        _need(type(obs['adc_tick_ms']) is Fraction and
              (obs['em_tick_ms'] is None or type(obs['em_tick_ms']) is Fraction), 'exact original acquisition view')
        _need(obs['adc_tick_ms'] <= view['now_tick_ms'], 'future internal observation')
    return view['history'] + [view['observation']]


def _bind_core(expected):
    frozen = copy.deepcopy(expected)
    def validator(view):
        return _validate_view(view, frozen)
    local_globals = dict(_ORIGINAL.__globals__)
    local_globals['_validate'] = validator
    return FunctionType(_ORIGINAL.__code__, local_globals, _ORIGINAL.__name__, _ORIGINAL.__defaults__)


def _receipt_shape(root):
    """Reject hidden/foreign fields even on disabled or missing-evidence paths."""
    if root is None:
        return
    _obj(root, {'kind', 'evidence_scope', 'config', 'source_admissions', 'captures', 'current_pose', 'action_registry'}, 'Root association')
    _need(root['kind'] == 'c29_root_association_v1' and type(root['evidence_scope']) is str and
          root['evidence_scope'] in _SCOPES, 'Root association namespace')
    if root['config'] is not None:
        c = root['config']
        _obj(c, set('receipt_id context generation profile_id producer_sha256 source_policy quality_encoding source_mode transport_source source_start_tick_ms source_start_monotonic_ns goal_m baseline_counters initial_trigger_id'.split()), 'Root config')
        _context(c['context']); _vector(c['goal_m'], 3, 1000); _counter(c['baseline_counters'])
        for key in ('receipt_id', 'profile_id', 'source_policy', 'quality_encoding', 'source_mode', 'transport_source'):
            _text(c[key])
        _hash(c['producer_sha256']); _uint(c['generation'], 32); _uint(c['initial_trigger_id'], 32)
        _tick(c['source_start_tick_ms'], 10); _uint(c['source_start_monotonic_ns'])
    if root['source_admissions'] is not None:
        _need(type(root['source_admissions']) is list, 'admissions array')
        for a in root['source_admissions']:
            _obj(a, set('index adc_tick_ms em_tick_ms channel_counts quality source_record_sha256 received_qpc_ns new_em_sample'.split()), 'Root source admission')
            _quality(a['channel_counts'], a['quality'], a['adc_tick_ms'], a['em_tick_ms'])
            _uint(a['index'], 32); _uint(a['received_qpc_ns']); _hash(a['source_record_sha256'])
            _need(type(a['new_em_sample']) is bool, 'native flag boolean')
    if root['captures'] is not None:
        _need(type(root['captures']) is list, 'capture associations array')
        for r in root['captures']:
            if r is None:
                continue
            _obj(r, set('capture_sha256 source_record_sha256 request_raw capture_raw adc_pose em_pose em_origin_capture_sha256 cause_action_id'.split()), 'capture association')
            _hash(r['capture_sha256']); _hash(r['source_record_sha256'])
            if r['em_origin_capture_sha256'] is not None:
                _hash(r['em_origin_capture_sha256'])
            if r['cause_action_id'] is not None:
                _text(r['cause_action_id'])
            for name in ('adc_pose', 'em_pose'):
                if r[name] is not None:
                    _obj(r[name], {'receipt_id', 'source_admission_index', 'acquisition_qpc_ns', 'pose'}, 'acquisition pose receipt')
                    _pose(r[name]['pose'])
                    _text(r[name]['receipt_id']); _uint(r[name]['source_admission_index'], 32); _uint(r[name]['acquisition_qpc_ns'])
            if r['request_raw'] is not None:
                _, raw = _raw(r['request_raw'])
                _obj(raw, set('schema kind context request_seq source_id source values qualities original_host_qpc_ns'.split()), 'raw request')
                _context(raw['context'])
                _need(type(raw['schema']) is int and raw['schema'] == 1 and raw['kind'] == 'diagnostic_scan' and
                      type(raw['source_id']) is int and raw['source_id'] == 4 and raw['source'] == 'software_fixture', 'raw request schema/source')
                _uint(raw['request_seq'], 32)
                for name, bits in (('values', 16), ('qualities', 8), ('original_host_qpc_ns', 63)):
                    _need(type(raw[name]) is list and len(raw[name]) == 4, 'raw four lanes')
                    for v in raw[name]:
                        _uint(v, bits)
            if r['capture_raw'] is not None:
                _, raw = _raw(r['capture_raw'])
                _obj(raw, set('schema kind context request_seq request_sha256 generation trigger_id captures final_counters'.split()), 'raw capture')
                _context(raw['context']); _counter(raw['final_counters'])
                _need(type(raw['schema']) is int and raw['schema'] == 1 and raw['kind'] == 'diagnostic_capture', 'raw capture schema')
                _hash(raw['request_sha256'])
                for key in ('request_seq', 'generation', 'trigger_id'):
                    _uint(raw[key], 32)
                _need(type(raw['captures']) is list and len(raw['captures']) == 4, 'four raw capture lanes')
                for lane in raw['captures']:
                    _obj(lane, {'channel', 'raw_words', 'pipeline_counters', 'ack_returned'}, 'raw lane')
                    _counter(lane['pipeline_counters'])
                    _uint(lane['channel'], 32); _need(lane['ack_returned'] is True, 'raw lane ack')
                    _need(type(lane['raw_words']) is list and len(lane['raw_words']) == 10, 'ten raw words')
                    for word in lane['raw_words']:
                        _uint(word, 32)
    for name, time in (('current_pose', 'at_qpc_ns'), ('action_registry', 'as_of_qpc_ns')):
        value = root[name]
        if value is None:
            continue
        _obj(value, {'receipt_id', 'context', 'generation', time, 'pose' if name == 'current_pose' else 'actions'}, name)
        _context(value['context'])
        _text(value['receipt_id']); _uint(value['generation'], 32); _uint(value[time])
        if name == 'current_pose':
            _pose(value['pose'])
        elif value['actions'] is not None:
            _need(type(value['actions']) is list, 'occurred actions array')
            for action in value['actions']:
                _obj(action, {'receipt_id', 'action_id', 'state', 'observation_capture_sha256', 'at_qpc_ns', 'from_pose', 'to_pose'}, 'occurred action')
                _pose(action['from_pose']); _pose(action['to_pose'])
                if action['receipt_id'] is not None:
                    _text(action['receipt_id'])
                _text(action['action_id']); _text(action['state'])
                _hash(action['observation_capture_sha256']); _uint(action['at_qpc_ns'])


def _finish(result):
    _tree(result)
    _need(len(_json_bytes(result)) <= MAX_BYTES, 'output budget')
    return result


def recommend(request):
    """Strict diagnostic JSON mapping -> detached advice; no I/O in this call.

    Missing `enabled` means false. Missing evidence is explicit null, never an
    inferred empty registry. Structural receipts grant no physical authority.
    """
    _tree(request)
    fields = {'schema_version', 'abi_id', 'diagnostic_only', 'evidence_scope', 'enabled',
              'now_qpc_ns', 'candidate', 'history', 'root_receipt'}
    _need(type(request) is dict and set(request) in (fields, fields-{'enabled'}), 'exact C29 envelope')
    _need(type(request['schema_version']) is int and request['schema_version'] == 1 and request['abi_id'] == ABI,
          'C29 schema/namespace')
    _need(request['diagnostic_only'] is True and type(request['evidence_scope']) is str and
          request['evidence_scope'] in _SCOPES, 'diagnostic evidence scope')
    enabled = request.get('enabled', False)
    _need(type(enabled) is bool, 'enabled boolean')
    _uint(request['now_qpc_ns'])
    _need(type(request['history']) is list and len(request['history'])+1 <= MAX_HISTORY, 'capture history bound')
    _need(len(_json_bytes(request)) <= MAX_BYTES, 'encoded request budget')
    request = copy.deepcopy(request)
    candidates = request['history'] + [request['candidate']]
    for c in candidates:
        _candidate(c)
        _need(c['observation_identity']['receiver_upper_qpc_ns'] <= request['now_qpc_ns'], 'future capture')
    _receipt_shape(request['root_receipt'])
    if request['root_receipt'] is not None:
        _need(request['root_receipt']['evidence_scope'] == request['evidence_scope'], 'Root evidence scope mismatch')
    result = {'schema_version': 1, 'abi_id': ABI, 'diagnostic_only': True,
              'evidence_scope': request['evidence_scope'], 'authorization': 'none',
              'core_sha256': CORE_SHA256, 'core_ran': False, 'input_status': 'DISABLED',
              'status': 'STOP', 'reason': 'disabled', 'risk': 1.0, 'uncertainty': 1.0,
              'direction_world': [0.0, 0.0, 0.0], 'speed_limit_m_s': 0.0,
              'now_qpc_ns': request['now_qpc_ns'],
              'kernel_boot_id': request['candidate']['observation_identity']['context']['boot_id'],
              'candidate': copy.deepcopy(request['candidate']),
              'root_receipt': copy.deepcopy(request['root_receipt']),
              'map_cells': [], 'independent_em_count': 0}
    if not enabled:
        if request['root_receipt'] is not None:
            try:
                _association(request, candidates)
            except _Unavailable:
                pass
        return _finish(result)
    try:
        view = _association(request, candidates)
        # Exact original integers gate entry; never compare truncated or float ms.
        for c in candidates:
            t = c['source_time']
            if t['adc_source_age_ns'] > AGE_NS or (t['em_source_age_ns'] is not None and t['em_source_age_ns'] > AGE_NS):
                raise _Unavailable('original_source_expired_at_capture')
        t = request['candidate']['source_time']
        for name in ('adc_tick_ms', 'em_tick_ms'):
            ns = _source_ns(t, t[name])
            if ns is not None and request['now_qpc_ns']-ns > AGE_NS:
                raise _Unavailable('original_source_expired_now')
    except _Unavailable as exc:
        result.update(input_status='INPUT_UNAVAILABLE', reason=str(exc))
        return _finish(result)
    computed = _bind_core(view)(view)
    result.update(core_ran=True, input_status='COMPLETE_DIAGNOSTIC')
    for name in ('status', 'reason', 'risk', 'uncertainty', 'direction_world', 'speed_limit_m_s', 'independent_em_count'):
        result[name] = computed[name]
    origins = {c['observation_identity']['capture_sha256']: c for c in candidates}
    records = {r['capture_sha256']: r for r in request['root_receipt']['captures']}
    for cell in computed['map_cells']:
        c = origins[cell['sample_id']]
        ns = cell['em_tick_ms']*NS_PER_MS
        _need(type(ns) is Fraction and ns.denominator == 1, 'lossless output original QPC')
        result['map_cells'].append({'observation_identity': copy.deepcopy(c['observation_identity']),
            'source_record_sha256': records[cell['sample_id']]['source_record_sha256'],
            'original_em_qpc_ns': ns.numerator, 'original_em_tick_ms': c['source_time']['em_tick_ms'],
            'pose': copy.deepcopy(cell['pose']), 'risk': cell['risk']})
    return _finish(result)


def recommend_json(raw):
    """Strict UTF8 JSON bytes entry; exact Python integers through uint63 QPC."""
    return _json_bytes(recommend(_parse(raw)))


__all__ = ['recommend', 'recommend_json', 'Rejected', 'ABI', 'CORE_SHA256']

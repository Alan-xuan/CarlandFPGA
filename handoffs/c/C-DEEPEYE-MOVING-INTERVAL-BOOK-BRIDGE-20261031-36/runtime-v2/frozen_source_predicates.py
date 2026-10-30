"""Exact C32 pure predicate excerpts only; no C28 loading/calls. Source SHA39fe63a3...; extraction inventory retained."""

import hashlib, json, math, re

ABI = 'private_raw4_time_association_v2'

CORE_SHA256 = '70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'

PRODUCER_SHA256 = '6a5f70a6acdaa6de52fc72d678d452956861370e1d143b70219ced107c5a04c9'

PROFILE = 'deepeye_forward_profile_candidate_v1'

NOTE = 'not_calibrated;not_em_surrogate_v2;not_formally_frozen'

ENCODING = 'candidate_four_channel_quality_v1'

TIME_BASIS = 'trusted_root_source_schedule_not_physical_sample_authentication'

CHANNELS = ['log10_rho_apparent', 'yaw_log10_rho_difference',
            'pitch_log10_rho_difference', 'near_bit_vibration_rms_g']

MAX_BYTES = 1048576

MAX_SOURCE_ADMISSIONS = 1001

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

def _need(test, reason):
    if not test:
        raise Rejected(reason)

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

def _tree(value, depth=0, nodes=None, path=(), source_prefix=True):
    if nodes is None:
        nodes = [0]
    nodes[0] += 1
    _need(depth <= 16 and nodes[0] <= 65536, 'JSON depth/node budget')
    _need(type(value) in (dict, list, str, int, float, bool, type(None)), 'strict JSON types')
    if type(value) is dict:
        _need(len(value) <= 32 and all(type(k) is str and len(k) <= 96 for k in value), 'object budget')
        for k, v in value.items():
            _tree(v, depth+1, nodes, path+(k,), source_prefix)
    elif type(value) is list:
        cap = MAX_SOURCE_ADMISSIONS if source_prefix and path == ('root_receipt', 'source_admissions') else MAX_HISTORY
        _need(len(value) <= cap, 'array budget')
        for i, v in enumerate(value):
            _tree(v, depth+1, nodes, path+(i,), source_prefix)
    elif type(value) is str:
        raw_line = (len(path) == 4 and path[:2] == ('root_receipt', 'captures') and
                    type(path[2]) is int and path[3] in ('request_raw', 'capture_raw'))
        _need(len(value) <= (16384 if raw_line else 192), 'string budget')
    elif type(value) is int:
        _need(abs(value) <= (1 << 64), 'integer budget')
    elif type(value) is float:
        _need(math.isfinite(value), 'nonfinite number')

def _json_bytes(value, newline=False):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + ('\n' if newline else '')).encode('utf-8')

def _parse(raw, max_bytes=MAX_BYTES, source_prefix=True):
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
    _tree(result, source_prefix=source_prefix)
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
    return raw, _parse(raw, 16384, source_prefix=False)

def _counter(values):
    _need(type(values) is list and len(values) == 3, 'three counters')
    for v in values:
        _uint(v, 32)

def _returned(c, record, config, missing):
    # Each supplied raw line is checked independently; no substitute raw/config.
    ident = c['observation_identity']; seq = ident['request_seq']; ctx = ident['context']
    q = c['quality']
    qualities = [((q >> ch) & 1) | (((q >> (4+ch)) & 1) << 1) |
                 (((q >> (8+ch)) & 1) << 2) | (((q >> 12) & 1) << 3) for ch in range(4)]
    values = [0 if v is None else v for v in c['channel_counts']]
    if record['request_raw'] is None:
        missing.append('missing_original_request')
    else:
        request_raw, request = _raw(record['request_raw'])
        _need(request['context'] == ctx and request['request_seq'] == seq, 'raw request context/sequence mismatch')
        _need(_json_bytes(request, True) == request_raw, 'canonical original request bytes')
        _need(hashlib.sha256(request_raw).hexdigest() == ident['request_sha256'], 'request hash mismatch')
        for name, expected in (('values', values), ('qualities', qualities),
                               ('original_host_qpc_ns', ident['original_host_injection_qpc_ns'])):
            _need(request[name] == expected, 'raw/request/candidate lane mismatch')
    if record['capture_raw'] is None:
        missing.append('missing_original_capture')
        return
    capture_raw, capture = _raw(record['capture_raw'])
    _need(capture['context'] == ctx, 'raw capture context mismatch')
    for name in ('request_seq', 'generation', 'trigger_id'):
        _need(capture[name] == ident[name], 'capture identity mismatch')
    _need(capture['request_sha256'] == ident['request_sha256'], 'capture request hash mismatch')
    _need(hashlib.sha256(capture_raw).hexdigest() == ident['capture_sha256'], 'capture hash mismatch')
    lanes = capture['captures']
    first = lanes[0]['pipeline_counters']
    # Feasibility only: these actual values do not supply an authenticated config.
    _need(first[0] >= 4*seq and first[1] >= seq and first[2] >= 4*(seq-1)+1,
          'returned counters cannot have a nonnegative baseline')
    for ch, lane in enumerate(lanes):
        _need(lane['pipeline_counters'] == [first[0], first[1], first[2]+ch],
              'returned lane counters inconsistent')
        _need(type(lane['channel']) is int and lane['channel'] == ch and lane['ack_returned'] is True, 'lane channel/ack')
        words = lane['raw_words']; ticks = ident['original_host_injection_qpc_ns'][ch]
        expected = [values[ch], ch | qualities[ch] << 8, ticks & 0xffffffff, ticks >> 32,
                    4*(seq-1), 4*seq-1, ctx['tag'], ident['trigger_id'], ident['generation']]
        _need(words[:9] == expected, 'returned raw words mismatch')
        if config is not None:
            baseline = config['baseline_counters']
            _need(lane['pipeline_counters'] == [baseline[0]+4*seq, baseline[1]+seq, baseline[2]+4*(seq-1)+ch+1], 'lane counters')
    _need(capture['final_counters'] == lanes[-1]['pipeline_counters'], 'returned final counters inconsistent')
    if config is not None:
        baseline = config['baseline_counters']
        _need(capture['final_counters'] == [baseline[0]+4*seq, baseline[1]+seq, baseline[2]+4*seq], 'final counters')
    return seq, first

def _admissions(items, anchor):
    _need(type(items) is list and len(items) <= MAX_SOURCE_ADMISSIONS, 'bounded original admissions from origin')
    previous = None; last_native = None; consecutive = 0; native = {}; stale = False
    for index, item in enumerate(items):
        _obj(item, set('index adc_tick_ms em_tick_ms channel_counts quality source_record_sha256 received_qpc_ns new_em_sample'.split()), 'Root source admission')
        _need(_uint(item['index'], 32) == index, 'original admissions must begin at zero with no omission')
        _hash(item['source_record_sha256'])
        _quality(item['channel_counts'], item['quality'], item['adc_tick_ms'], item['em_tick_ms'])
        adc, em = item['adc_tick_ms'], item['em_tick_ms']
        _need(0 <= adc-anchor['source_start_tick_ms'] <= 10000, 'original ten-second source schedule')
        adc_ns, em_ns = _source_ns(anchor, adc), _source_ns(anchor, em)
        received = _uint(item['received_qpc_ns'])
        _need(received >= adc_ns and (em_ns is None or received >= em_ns), 'negative source admission original age')
        stale |= received-adc_ns > AGE_NS or (em_ns is not None and received-em_ns > AGE_NS)
        if previous is None:
            _need(adc == anchor['source_start_tick_ms'], 'missing original source start')
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
    return native, stale

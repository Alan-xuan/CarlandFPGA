"""Explicit numerical Root-book composition with frozen C32 and its sole C28.

Only fixed hash-pinned dependency reads happen on import. No clocks, producers,
Root/native objects, transport or control authority are created by this module.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
from types import ModuleType

ADAPTER_ID = 'root_book_stale_composition_v1'
BOOK_SOURCE_COMMIT = '54e1fd6c5795cc2f1247866dd8783331f615ef66'
C30_REFERENCE_SHA256 = 'abaa06d10ab68f0bee721bf1a6d9278fc000446112ac559362079ad63afc686d'
C31_REFERENCE_SHA256 = '506219cf445001c46f2f4e1ffd411829ea9d184d4260d18af9e45aa3787993ee'
C32_SHA256 = '39fe63a3d71308fae9482e3203b4f5120c34d796ccd2b755b99a9de902005a87'
CORE_SHA256 = '70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'
CLAIM = 'numerical_immutable_committed_root_only'
MAX_BYTES = 1048576

_PATH = Path(__file__).resolve().parent.parent / 'C-DEEPEYE-C30-STALE-ADMISSION-SEMANTICS-20261030-32' / 'private_raw4_time_association_v2.py'
_BYTES = _PATH.read_bytes()
if hashlib.sha256(_BYTES).hexdigest() != C32_SHA256:
    raise ImportError('frozen C32 dependency hash mismatch')
_C32 = ModuleType('_fixed_c32_for_c34')
_C32.__file__ = str(_PATH)
exec(compile(_BYTES, str(_PATH), 'exec'), _C32.__dict__)
Rejected = _C32.Rejected


def _need(test, reason):
    if not test:
        raise Rejected(reason)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf8')


def _tree(value, depth=0, nodes=None, path=()):
    if nodes is None:
        nodes = [0]
    nodes[0] += 1
    _need(depth <= 16 and nodes[0] <= 65536, 'C34 depth/node budget')
    _need(type(value) in (dict, list, str, int, float, bool, type(None)), 'C34 strict JSON type')
    if type(value) is dict:
        _need(len(value) <= 32 and all(type(k) is str and len(k) <= 96 for k in value), 'C34 object budget')
        for k, v in value.items():
            _tree(v, depth+1, nodes, path+(k,))
    elif type(value) is list:
        cap = 1001 if path in (('book', 'samples'), ('external', 'source_admissions'),
            ('projection', 'root_receipt', 'source_admissions'),
            ('c32_result', 'root_receipt', 'source_admissions')) else 32
        _need(len(value) <= cap, 'C34 array budget')
        for i, v in enumerate(value):
            _tree(v, depth+1, nodes, path+(i,))
    elif type(value) is str:
        raw = (len(path) == 4 and path[:2] == ('external', 'captures') and
               type(path[2]) is int and path[3] in ('request_raw', 'capture_raw'))
        raw = raw or (len(path) == 5 and path[0] in ('projection', 'c32_result') and
               path[1:3] == ('root_receipt', 'captures') and type(path[3]) is int and
               path[4] in ('request_raw', 'capture_raw'))
        hex_line = (len(path) == 4 and path[:2] == ('book', 'samples') and
                    type(path[2]) is int and path[3] == 'canonical_source_hex')
        _need(len(value) <= (16384 if raw else 8192 if hex_line else 192), 'C34 string budget')
    elif type(value) is int:
        _need(abs(value) <= 1 << 64, 'C34 integer budget')
    elif type(value) is float:
        _need(math.isfinite(value), 'C34 finite scalar')


def _parse(raw):
    _need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'C34 JSON bytes budget/type')
    def pairs(items):
        result = {}
        for k, v in items:
            _need(k not in result, 'C34 duplicate JSON key')
            result[k] = v
        return result
    def constant(_):
        raise Rejected('C34 nonfinite constant')
    try:
        result = json.loads(raw.decode('utf8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Rejected('C34 invalid JSON: '+str(exc)) from exc
    _tree(result)
    return result


def _keys(value, names, label):
    _need(type(value) is dict and set(value) == set(names.split()), label+': exact fields')


def _nullable(value, check):
    if value is not None:
        check(value)


def _metadata(value, current=False):
    if value is None:
        return
    names = 'receipt_id context generation valid_span_receipt_id' if current else 'receipt_id source_admission_index valid_span_receipt_id'
    _keys(value, names, 'C34 external pose metadata')
    for k in ('receipt_id', 'valid_span_receipt_id'):
        _nullable(value[k], _C32._text)
    if current:
        _C32._context(value['context']); _C32._uint(value['generation'], 32)
    else:
        _nullable(value['source_admission_index'], lambda x: _C32._uint(x, 32))


def _span(value, now, claimed=False):
    names = 'from_qpc_ns through_qpc_ns root_revision pose_revision'
    _keys(value, names+' claim' if claimed else names, 'C34 numerical interval')
    for key in names.split():
        _C32._uint(value[key])
    _need(value['from_qpc_ns'] <= value['through_qpc_ns'] <= now, 'C34 reversed/future numerical interval')
    if claimed:
        _need(value['claim'] == CLAIM, 'C34 numerical claim only')


def _read(value, now):
    _keys(value, 'begin_qpc_ns end_qpc_ns pose root_revision pose_revision revoke_generation postcheck_complete', 'C34 actual pose read')
    _C32._bracket({k: value[k] for k in ('begin_qpc_ns', 'end_qpc_ns')}, now)
    _C32._pose(value['pose'])
    for key in ('root_revision', 'pose_revision', 'revoke_generation'):
        _C32._uint(value[key])
    _need(type(value['postcheck_complete']) is bool, 'C34 read postcheck boolean')


def _binding(value):
    if value is None:
        return
    _keys(value, 'context generation pose_book_id owner_binding_id committed_pose pose_revision root_revision claim native_interval_atomic', 'C34 explicit Root numerical binding')
    _C32._context(value['context']); _C32._uint(value['generation'], 32)
    for k in ('pose_book_id', 'owner_binding_id'):
        _nullable(value[k], _C32._text)
    _nullable(value['committed_pose'], _C32._pose)
    for k in ('pose_revision', 'root_revision'):
        _nullable(value[k], _C32._uint)
    _need(value['claim'] == CLAIM and value['native_interval_atomic'] is False,
          'C34 binding must limit proof to numerical committed Root')


def _book_shape(book, current, now, missing):
    """Validate every supplied used field, even when an unrelated proof is absent."""
    samples = {}; discarded = 0
    if book is None:
        missing.add('missing_book')
    else:
        _need(type(book) is dict and type(book.get('schema')) is int and book['schema'] == 1, 'C34 exact book schema')
        _need(book.get('native_interval_atomic') is False, 'C34 book is not atomic native interval proof')
        for name in ('state', 'source_state'):
            _need(book.get(name) in ('NEW', 'RUNNING', 'RETIRED', 'FAILED', 'STOPPED'), 'C34 book/source state')
        if book['state'] not in ('RUNNING', 'RETIRED') or book['source_state'] not in ('RUNNING', 'STOPPED'):
            missing.add('book_not_complete_healthy')
        if book.get('failure_reason') is not None or book.get('partial_samples') or book.get('active_sample') is not None:
            missing.add('book_partial_or_failed')
        if book.get('source_origin_qpc_ns') is None:
            missing.add('missing_book_origin')
        else:
            _C32._uint(book['source_origin_qpc_ns'])
            _need(book['source_origin_qpc_ns'] <= now, 'C34 future book origin')
        interval = book.get('fixed_root_interval')
        if interval is None:
            missing.add('missing_fixed_root_interval')
        else:
            _span(interval, now, claimed=True)
        values = book.get('samples')
        if values is None:
            missing.add('missing_book_samples'); values = []
        _need(type(values) is list, 'C34 book sample list')
        last_tick = -1
        for position, sample in enumerate(values):
            _need(type(sample) is dict, 'C34 sample object')
            tick = sample.get('tick_ms'); count = sample.get('source_count')
            _C32._tick(tick, 10); _C32._uint(count)
            _need(count == position+1 and tick > last_tick and tick <= 10000,
                  'C34 original complete book count/tick order')
            last_tick = tick
            nominal = sample.get('nominal_qpc_ns'); _C32._uint(nominal)
            _need(nominal <= now, 'C34 future nominal')
            if book.get('source_origin_qpc_ns') is not None:
                _need(nominal == book['source_origin_qpc_ns']+tick*1000000,
                      'C34 original book nominal equation')
            digest = sample.get('source_sha256')
            if digest is not None:
                _C32._hash(digest)
                _need(digest not in samples, 'C34 duplicate book source hash')
                samples[digest] = sample
            else:
                missing.add('missing_book_source_hash')
            canonical_hex = sample.get('canonical_source_hex')
            if canonical_hex is not None:
                _need(type(canonical_hex) is str and len(canonical_hex) % 2 == 0 and
                      all(ch in '0123456789abcdef' for ch in canonical_hex), 'C34 original canonical hex')
                canonical = bytes.fromhex(canonical_hex)
                _need(0 < len(canonical) <= 4096, 'C34 canonical source bytes budget')
                document = _parse(canonical)
                _need(json.dumps(document, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf8') == canonical,
                      'C34 canonical source encoding mismatch')
                if digest is not None:
                    _need(hashlib.sha256(canonical).hexdigest() == digest, 'C34 original book source hash mismatch')
                if sample.get('payload') is not None:
                    _need(json.dumps(sample['payload'], sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf8') == canonical,
                          'C34 detached private payload/canonical mismatch')
            if sample.get('status') != 'complete':
                missing.add('book_sample_incomplete')
            reads = sample.get('pose_reads')
            if reads is None:
                missing.add('missing_book_pose_reads'); reads = {}
            _need(type(reads) is dict and set(reads) <= {'em', 'adc'}, 'C34 book read whitelist')
            for read in reads.values():
                _read(read, now)
                _need(nominal <= read['begin_qpc_ns'], 'C34 actual read before nominal')
                if not read['postcheck_complete']:
                    missing.add('missing_read_postcheck')
            call = sample.get('adc')
            if call is not None:
                allowed = set('begin_qpc_ns end_qpc_ns previous_adc_tick_ms profile_tick_observed postcheck_complete end_attempt_qpc_ns'.split())
                _need(type(call) is dict and set(call) <= allowed and
                      {'begin_qpc_ns','end_qpc_ns','profile_tick_observed','postcheck_complete'} <= set(call), 'C34 ADC call fields')
                _C32._uint(call['begin_qpc_ns'])
                _need(nominal <= call['begin_qpc_ns'] <= now, 'C34 supplied ADC begin outside nominal/now')
                for read in reads.values():
                    _need(read['end_qpc_ns'] <= call['begin_qpc_ns'], 'C34 read after ADC call begin')
                if call['end_qpc_ns'] is None:
                    missing.add('missing_adc_call_end')
                else:
                    _C32._bracket({k: call[k] for k in ('begin_qpc_ns', 'end_qpc_ns')}, now)
                _need(type(call['profile_tick_observed']) is bool and type(call['postcheck_complete']) is bool, 'C34 ADC proof boolean')
                if not call['profile_tick_observed'] or not call['postcheck_complete']:
                    missing.add('missing_adc_call_postcheck')
            else:
                missing.add('missing_adc_call')
            span = sample.get('numerical_pose_span')
            if span is not None:
                _span(span, now)
                for read in reads.values():
                    _need(read['root_revision'] == span['root_revision'] and read['pose_revision'] == span['pose_revision'],
                          'C34 sample read/span revision mismatch')
                if interval is not None:
                    _need(span['root_revision'] == interval['root_revision'] and
                          span['pose_revision'] == interval['pose_revision'] and
                          interval['from_qpc_ns'] == span['from_qpc_ns'] and
                          span['through_qpc_ns'] <= interval['through_qpc_ns'], 'C34 sample/fixed interval mismatch')
                points = [nominal]
                for read in reads.values():
                    points.extend((read['begin_qpc_ns'], read['end_qpc_ns']))
                if call is not None:
                    points.append(call['begin_qpc_ns'])
                    if call['end_qpc_ns'] is not None:
                        points.append(call['end_qpc_ns'])
                if not all(span['from_qpc_ns'] <= p <= span['through_qpc_ns'] for p in points):
                    missing.add('numerical_span_does_not_cover')
            else:
                missing.add('missing_numerical_span')
            used = {'tick_ms','source_count','nominal_qpc_ns','source_sha256','status','pose_reads','adc','numerical_pose_span'}
            discarded += len(set(sample)-used)
        used = {'schema','state','source_state','failure_reason','partial_samples','active_sample',
                'source_origin_qpc_ns','samples','fixed_root_interval','native_interval_atomic'}
        discarded += len(set(book)-used)
    if current is None:
        missing.add('missing_book_current')
    else:
        _keys(current, 'pose pose_revision at_qpc_ns pose_read valid_span claim native_interval_atomic', 'C34 current numerical view')
        _need(current['claim'] == CLAIM and current['native_interval_atomic'] is False, 'C34 current numerical claim only')
        _C32._pose(current['pose']); _C32._uint(current['pose_revision'])
        _C32._uint(current['at_qpc_ns'])
        _need(current['at_qpc_ns'] == now, 'C34 original current at must equal requested now')
        if current['pose_read'] is None:
            missing.add('missing_current_read')
        else:
            _C32._bracket(current['pose_read'], now)
            _need(current['pose_read']['end_qpc_ns'] == current['at_qpc_ns'], 'C34 actual current end/at mismatch')
        if current['valid_span'] is None:
            missing.add('missing_current_span')
        else:
            _span(current['valid_span'], now)
            _need(current['valid_span']['pose_revision'] == current['pose_revision'], 'C34 current span revision mismatch')
            points = [now]
            if current['pose_read'] is not None:
                points.extend(current['pose_read'].values())
            if not all(current['valid_span']['from_qpc_ns'] <= p <= current['valid_span']['through_qpc_ns'] for p in points):
                missing.add('current_span_does_not_cover')
    return samples, discarded


def _metadata_ready(meta):
    return meta is not None and all(v is not None for v in meta.values())


def _pose_projection(meta, sample, kind, missing):
    if not _metadata_ready(meta):
        missing.add('missing_'+kind+'_receipt_metadata')
    if sample is None:
        missing.add('missing_'+kind+'_book_link')
        return None
    read = (sample.get('pose_reads') or {}).get(kind)
    span = sample.get('numerical_pose_span')
    if read is None:
        missing.add('missing_'+kind+'_original_read')
    if not _metadata_ready(meta) or read is None or span is None:
        return None
    return dict(receipt_id=meta['receipt_id'], source_admission_index=meta['source_admission_index'],
        nominal_source_qpc_ns=sample['nominal_qpc_ns'], pose=copy.deepcopy(read['pose']),
        pose_revision=read['pose_revision'], pose_read={k:read[k] for k in ('begin_qpc_ns','end_qpc_ns')},
        valid_span=dict(receipt_id=meta['valid_span_receipt_id'],from_qpc_ns=span['from_qpc_ns'],through_qpc_ns=span['through_qpc_ns']))


def _supplied_admissions(items, anchor):
    """Decidable structure only; C30's complete freshness policy stays frozen."""
    if items is None:
        return
    previous = None; consecutive = 0; last_native = None
    for index, item in enumerate(items):
        _need(item['index'] == index, 'C34 source prefix starts zero without omissions')
        adc = item['adc_tick_ms']; em = item['em_tick_ms']; received = item['received_qpc_ns']
        if anchor is not None:
            _need(0 <= adc-anchor['source_start_tick_ms'] <= 10000, 'C34 original source window')
            nominal = _C32._source_ns(anchor, adc)
            _need(nominal <= received, 'C34 admission before source nominal')
            if em is not None:
                _need(_C32._source_ns(anchor, em) <= received, 'C34 future EM admission')
        if previous is None:
            if anchor is not None:
                _need(adc == anchor['source_start_tick_ms'], 'C34 missing original source start')
            consecutive = 1
        else:
            _need(adc > previous['adc_tick_ms'] and received >= previous['received_qpc_ns'], 'C34 source order')
            consecutive = min(10, consecutive+1) if adc-previous['adc_tick_ms'] == 10 else 1
        _need(bool(item['quality'] & 8) == (consecutive == 10), 'C34 source C3 continuity')
        new = em is not None and em != last_native
        _need(item['new_em_sample'] == new, 'C34 native source flag')
        if new:
            _need(em == adc, 'C34 native source time equality'); last_native = em
        elif em is not None:
            _need(previous is not None and previous['em_tick_ms'] == em and
                  item['channel_counts'][:3] == previous['channel_counts'][:3] and
                  item['quality'] & 0x70 == previous['quality'] & 0x70, 'C34 changed held source')
        previous = item


def _supplied_raw(candidate, record, config):
    """Check each original line against actual candidate fields independently.

    No absent config/counter baseline or other raw line is fabricated. This
    checker adds no C32 freshness semantics and creates no admission evidence.
    """
    ident = candidate['observation_identity']; seq = ident['request_seq']; q = candidate['quality']; capture = None
    values = [0 if x is None else x for x in candidate['channel_counts']]
    qualities = [((q >> ch)&1) | (((q >> (4+ch))&1)<<1) |
                 (((q >> (8+ch))&1)<<2) | (((q >> 12)&1)<<3) for ch in range(4)]
    if record['request_raw'] is not None:
        raw, request = _C32._raw(record['request_raw'])
        _need(hashlib.sha256(raw).hexdigest() == ident['request_sha256'], 'C34 supplied request/candidate hash mismatch')
        _need(_C32._json_bytes(request,True) == raw, 'C34 supplied original request canonical bytes')
        _need(request['context'] == ident['context'] and request['request_seq'] == seq,
              'C34 supplied request identity mismatch')
        _need(request['values'] == values and request['qualities'] == qualities and
              request['original_host_qpc_ns'] == ident['original_host_injection_qpc_ns'],
              'C34 supplied request/candidate lanes mismatch')
    if record['capture_raw'] is not None:
        raw, capture = _C32._raw(record['capture_raw'])
        _need(hashlib.sha256(raw).hexdigest() == ident['capture_sha256'] == record['capture_sha256'],
              'C34 supplied capture/candidate hash mismatch')
        _need(capture['request_sha256'] == ident['request_sha256'] and capture['context'] == ident['context'],
              'C34 supplied capture request/context mismatch')
        for name in ('request_seq','generation','trigger_id'):
            _need(capture[name] == ident[name], 'C34 supplied capture identity mismatch')
        _need(all(value >= increment for value,increment in zip(capture['final_counters'],(4*seq,seq,4*seq))),
              'C34 supplied counters require negative original baseline')
        for ch,lane in enumerate(capture['captures']):
            ticks = ident['original_host_injection_qpc_ns'][ch]
            expected = [values[ch], ch | qualities[ch]<<8, ticks & 0xffffffff, ticks>>32,
                4*(seq-1),4*seq-1,ident['context']['tag'],ident['trigger_id'],ident['generation']]
            _need(lane['channel'] == ch and lane['raw_words'][:9] == expected,
                  'C34 supplied raw words/candidate mismatch')
            _need(lane['pipeline_counters'][:2] == capture['final_counters'][:2] and
                  lane['pipeline_counters'][2]+3-ch == capture['final_counters'][2],
                  'C34 supplied raw lane/final counters mismatch')
        if config is not None:
            baseline = config['baseline_counters']
            _need(capture['final_counters'] == [baseline[0]+4*seq,baseline[1]+seq,baseline[2]+4*seq],
                  'C34 supplied capture/original counter baseline mismatch')
    if config is not None:
        _need(ident['generation'] == config['generation'] and ident['trigger_id'] == config['initial_trigger_id']+seq,
              'C34 supplied original generation/trigger mismatch')
    return capture


def _raw_intrinsics(record, config, namespace, now):
    """Relations between supplied raw objects do not need a missing candidate."""
    request = capture = None
    request_digest = None
    if record['request_raw'] is not None:
        raw,request = _C32._raw(record['request_raw']); request_digest = hashlib.sha256(raw).hexdigest()
        _need(_C32._json_bytes(request,True) == raw, 'C34 intrinsic request canonical bytes')
        _need(request['request_seq'] > 0, 'C34 intrinsic positive request sequence')
        ticks = request['original_host_qpc_ns']
        _need(0 < ticks[0] <= ticks[1] <= ticks[2] <= ticks[3] <= now, 'C34 intrinsic original request times')
        if namespace is not None:
            _need(request['context'] == namespace[0], 'C34 intrinsic request supplied namespace mismatch')
    if record['capture_raw'] is not None:
        raw,capture = _C32._raw(record['capture_raw'])
        _need(hashlib.sha256(raw).hexdigest() == record['capture_sha256'], 'C34 intrinsic capture hash mismatch')
        if namespace is not None:
            _need(capture['context'] == namespace[0] and capture['generation'] == namespace[1],
                  'C34 intrinsic capture supplied namespace mismatch')
        seq = capture['request_seq']; final = capture['final_counters']
        _need(capture['generation'] > 0, 'C34 intrinsic positive capture generation')
        captured_ticks = []
        for ch, lane in enumerate(capture['captures']):
            words = lane['raw_words']
            _need(words[4:9] == [4*(seq-1),4*seq-1,capture['context']['tag'],capture['trigger_id'],capture['generation']] and
                  words[1] & 255 == ch, 'C34 intrinsic capture identity words')
            captured_ticks.append(words[2] | words[3] << 32)
        _need(0 < captured_ticks[0] <= captured_ticks[1] <= captured_ticks[2] <= captured_ticks[3] <= now,
              'C34 intrinsic original capture times')
        _need(seq > 0 and all(v >= inc for v,inc in zip(final,(4*seq,seq,4*seq))), 'C34 intrinsic negative counter baseline')
        for ch,lane in enumerate(capture['captures']):
            _need(lane['channel'] == ch and lane['pipeline_counters'][:2] == final[:2] and
                  lane['pipeline_counters'][2]+3-ch == final[2], 'C34 intrinsic lane/final counters')
        if config is not None:
            base = config['baseline_counters']
            _need(final == [base[0]+4*seq,base[1]+seq,base[2]+4*seq] and
                  capture['trigger_id'] == config['initial_trigger_id']+seq,
                  'C34 intrinsic original config/counter/trigger mismatch')
    if request is not None and capture is not None:
        _need(capture['request_sha256'] == request_digest and capture['context'] == request['context'] and
              capture['request_seq'] == request['request_seq'], 'C34 supplied raw pair mismatch')
        seq = capture['request_seq']
        for ch,lane in enumerate(capture['captures']):
            ticks = request['original_host_qpc_ns'][ch]
            expected = [request['values'][ch],ch | request['qualities'][ch]<<8,ticks & 0xffffffff,ticks>>32,
                4*(seq-1),4*seq-1,capture['context']['tag'],capture['trigger_id'],capture['generation']]
            _need(lane['raw_words'][:9] == expected, 'C34 supplied raw pair words mismatch')


def _record_counter_consistency(records):
    """Necessary shared-baseline feasibility only; never manufacture a baseline.

    Runs after each actual line passed shape and intrinsic checks. A separate
    namespace/generation is not silently merged into a different capture group.
    """
    previous = {}
    for record in records.values():
        if record['capture_raw'] is None:
            continue
        _, capture = _C32._raw(record['capture_raw'])
        key = (_json(capture['context']), capture['generation'])
        if key in previous:
            prior = previous[key]
            delta = capture['request_seq'] - prior['request_seq']
            _need([b-a for a,b in zip(prior['final_counters'],capture['final_counters'])] ==
                  [4*delta,delta,4*delta], 'C34 supplied records cross-capture counter mismatch')
        previous[key] = capture


def _crosschecks(request,candidates,records,samples,missing):
    ext = request['external']; binding = request['binding']; book = request['book']
    config = ext['config']; current = request['book_current']; admissions = ext['source_admissions']
    namespaces = [(c['observation_identity']['context'],c['observation_identity']['generation']) for c in candidates]
    for supplied in (binding,config,ext['current_pose'],ext['action_registry']):
        if supplied is not None:
            namespaces.append((supplied['context'],supplied['generation']))
    # Compare every actual operand, even without an outer receipt. Request
    # lines supply context only; a comparison anchor is not a binding receipt.
    contexts = [item[0] for item in namespaces]
    generations = [item[1] for item in namespaces]
    for record in records.values():
        for name in ('request_raw', 'capture_raw'):
            if record[name] is not None:
                _, raw = _C32._raw(record[name])
                contexts.append(raw['context'])
                if name == 'capture_raw':
                    generations.append(raw['generation'])
    _need(not contexts or all(item == contexts[0] for item in contexts),
          'C34 supplied context conflict despite missing receipt')
    _need(not generations or all(item == generations[0] for item in generations),
          'C34 supplied generation conflict despite missing receipt')
    namespace = (contexts[0], generations[0] if generations else None) if contexts else None
    if config is not None:
        _need(config['generation'] > 0, 'C34 positive supplied config generation')
        _need(config['profile_id'] == _C32.PROFILE and config['producer_sha256'] == _C32.PRODUCER_SHA256 and
              config['source_policy'] == 'candidate_causal_source_v1' and config['quality_encoding'] == _C32.ENCODING and
              config['source_mode'] == 'twin_fixture' and config['transport_source'] == 'software_fixture',
              'C34 fixed C30 source configuration')
        for key in ('pose_book_id','owner_binding_id'):
            if config[key] is None:
                missing.add('missing_config_book_or_owner')
    registry = ext['action_registry']
    if registry is not None and registry['actions'] is not None:
        for action in registry['actions']:
            if any(action[key] is None for key in ('receipt_id','from_pose_revision','to_pose_revision')):
                missing.add('missing_actual_action_execution_receipt')
    if binding is not None:
        for candidate in candidates:
            ident = candidate['observation_identity']
            _need(ident['context'] == binding['context'] and ident['generation'] == binding['generation'],
                  'C34 candidate/explicit binding namespace mismatch')
        if config is not None:
            for key in ('context','generation','pose_book_id','owner_binding_id'):
                if config[key] is not None and binding[key] is not None:
                    _need(config[key] == binding[key], 'C34 config/binding mismatch')
        for meta in (ext['current_pose'],ext['action_registry']):
            if meta is not None:
                _need(meta['context'] == binding['context'] and meta['generation'] == binding['generation'],
                      'C34 external current/action binding mismatch')
        def bound(pose,revision,root_revision):
            if binding['committed_pose'] is not None:
                _need(pose == binding['committed_pose'], 'C34 supplied pose differs from explicit committed numerical pose')
            if binding['pose_revision'] is not None:
                _need(revision == binding['pose_revision'], 'C34 explicit committed pose revision mismatch')
            if binding['root_revision'] is not None:
                _need(root_revision == binding['root_revision'], 'C34 explicit committed Root revision mismatch')
        for sample in samples.values():
            for read in (sample.get('pose_reads') or {}).values():
                bound(read['pose'],read['pose_revision'],read['root_revision'])
            span = sample.get('numerical_pose_span')
            if span is not None:
                if binding['root_revision'] is not None:
                    _need(span['root_revision'] == binding['root_revision'], 'C34 span/explicit Root mismatch')
                if binding['pose_revision'] is not None:
                    _need(span['pose_revision'] == binding['pose_revision'], 'C34 span/explicit pose revision mismatch')
        if current is not None:
            root_revision = current['valid_span']['root_revision'] if current['valid_span'] is not None else binding['root_revision']
            bound(current['pose'],current['pose_revision'],root_revision)
    if config is not None and book is not None and book.get('source_origin_qpc_ns') is not None:
        _need(config['source_start_tick_ms'] == 0 and config['source_start_monotonic_ns'] == book['source_origin_qpc_ns'],
              'C34 original book/config origin cannot be rebased')
    if book is not None and current is not None and book.get('fixed_root_interval') is not None and current['valid_span'] is not None:
        fixed = book['fixed_root_interval']; span = current['valid_span']
        _need(span['from_qpc_ns'] == fixed['from_qpc_ns'] and span['through_qpc_ns'] <= fixed['through_qpc_ns'] and
              span['root_revision'] == fixed['root_revision'] and span['pose_revision'] == fixed['pose_revision'],
              'C34 current/fixed original interval mismatch')
    candidate_map = {c['observation_identity']['capture_sha256']:c for c in candidates}
    _need(len(candidate_map) == len(candidates), 'C34 duplicate candidate capture')
    for capture_sha,record in records.items():
        if ext['candidate'] is not None:
            _need(capture_sha in candidate_map, 'C34 extra association outside complete supplied candidates')
        _raw_intrinsics(record,config,namespace,ext['now_qpc_ns'])
        for kind in ('adc','em'):
            meta = record[kind+'_pose']; sample = samples.get(record[kind+'_book_source_sha256'])
            if meta is None or meta['source_admission_index'] is None or sample is None:
                continue
            index = meta['source_admission_index']
            if admissions is None or index >= len(admissions):
                missing.add('missing_actual_source_admission'); continue
            adm = admissions[index]
            _need(sample['tick_ms'] == adm['adc_tick_ms'], 'C34 supplied book/receipt/admission tick mismatch')
            if kind == 'adc':
                _need(record['source_record_sha256'] == adm['source_record_sha256'], 'C34 supplied receipt/admission wire hash mismatch')
                call = sample.get('adc')
                if call is not None and call['end_qpc_ns'] is not None:
                    _need(call['end_qpc_ns'] <= adm['received_qpc_ns'], 'C34 supplied book ADC call after admission')
            else:
                _need(adm['new_em_sample'] and adm['em_tick_ms'] == adm['adc_tick_ms'],
                      'C34 supplied original EM receipt is not native admission')
    _record_counter_consistency(records)
    previous = None; previous_returned = None
    for candidate in candidates:
        ident = candidate['observation_identity']; time = candidate['source_time']
        first_time = candidates[0]['source_time']
        _need(time['source_start_tick_ms'] == first_time['source_start_tick_ms'] and
              time['source_start_monotonic_ns'] == first_time['source_start_monotonic_ns'], 'C34 retained original anchor mismatch')
        if previous is not None:
            _need(ident['request_seq'] > previous['request_seq'] and
                  ident['source_admission_index'] > previous['source_admission_index'] and
                  ident['original_host_injection_qpc_ns'][0] > previous['original_host_injection_qpc_ns'][-1] and
                  ident['receiver_upper_qpc_ns'] >= previous['receiver_upper_qpc_ns'], 'C34 retained capture order')
        previous = ident
        if config is not None:
            _need(time['source_start_tick_ms'] == config['source_start_tick_ms'] and
                  time['source_start_monotonic_ns'] == config['source_start_monotonic_ns'], 'C34 candidate/config original anchor mismatch')
        record = records.get(ident['capture_sha256'])
        index = ident['source_admission_index']
        if admissions is None or index >= len(admissions):
            missing.add('missing_actual_source_admission')
        else:
            adm = admissions[index]
            _need(adm['adc_tick_ms'] == time['adc_tick_ms'] and adm['em_tick_ms'] == time['em_tick_ms'] and
                  adm['received_qpc_ns'] == time['admission_received_monotonic_ns'] and
                  adm['channel_counts'] == candidate['channel_counts'] and adm['quality'] == candidate['quality'],
                  'C34 original admission/capture/candidate mismatch')
            if record is not None:
                _need(adm['source_record_sha256'] == record['source_record_sha256'], 'C34 original wire/admission source hash mismatch')
        if record is None:
            missing.add('missing_candidate_capture_association'); continue
        returned = _supplied_raw(candidate,record,config)
        if returned is not None:
            if previous_returned is not None:
                delta = returned['request_seq']-previous_returned['request_seq']
                _need([b-a for a,b in zip(previous_returned['final_counters'],returned['final_counters'])] ==
                      [4*delta,delta,4*delta], 'C34 supplied cross-capture counter progression mismatch')
            previous_returned = returned
        if record['request_raw'] is not None and record['capture_raw'] is not None and config is not None:
            returned_missing = []
            _C32._returned(candidate,record,config,returned_missing)
            missing.update(returned_missing)
        else:
            missing.add('missing_raw_request_or_capture')
        adc_sample = samples.get(record['adc_book_source_sha256'])
        if adc_sample is not None:
            _need(adc_sample['tick_ms'] == time['adc_tick_ms'] and
                  adc_sample['nominal_qpc_ns'] == _C32._source_ns(time,time['adc_tick_ms']), 'C34 explicit ADC book link time mismatch')
            call = adc_sample.get('adc')
            if call is not None and call['end_qpc_ns'] is not None:
                _need(call['end_qpc_ns'] <= time['admission_received_monotonic_ns'], 'C34 actual ADC call after original admission')
        meta = record['adc_pose']
        if meta is not None and meta['source_admission_index'] is not None:
            _need(meta['source_admission_index'] == index, 'C34 explicit ADC admission index mismatch')
        em_tick = time['em_tick_ms']
        if em_tick is None:
            _need(record['em_pose'] is None and record['em_book_source_sha256'] is None and
                  record['em_origin_capture_sha256'] is None, 'C34 faulted EM association must be null')
            continue
        em_sample = samples.get(record['em_book_source_sha256'])
        if record['em_book_source_sha256'] is None or em_sample is None:
            missing.add('missing_explicit_native_em_book_link')
        if record['em_pose'] is None:
            missing.add('missing_em_receipt_metadata')
        if em_sample is not None:
            _need(em_sample['tick_ms'] == em_tick and em_sample['nominal_qpc_ns'] == _C32._source_ns(time,em_tick),
                  'C34 explicit native EM book link time mismatch')
        origin = record['em_origin_capture_sha256']
        if origin is None:
            missing.add('missing_original_native_capture')
        elif em_tick == time['adc_tick_ms']:
            _need(origin == ident['capture_sha256'], 'C34 native capture origin mismatch')
            if record['adc_book_source_sha256'] is not None and record['em_book_source_sha256'] is not None:
                _need(record['adc_book_source_sha256'] == record['em_book_source_sha256'], 'C34 conflicting native ADC/EM book links')
            if record['em_pose'] is not None and record['em_pose']['source_admission_index'] is not None:
                _need(record['em_pose']['source_admission_index'] == index, 'C34 explicit native EM admission mismatch')
        else:
            original = records.get(origin); native_candidate = candidate_map.get(origin)
            if original is None or native_candidate is None:
                missing.add('missing_retained_native_capture')
            else:
                _need(native_candidate['source_time']['adc_tick_ms'] == native_candidate['source_time']['em_tick_ms'] == em_tick,
                      'C34 held origin is not original native capture')
                _need(record['em_book_source_sha256'] == original['em_book_source_sha256'] and
                      record['em_pose'] == original['em_pose'], 'C34 held native receipt/book origin changed')


def _actual_temporal(request, candidates, records, samples, missing):
    """Check supplied numerical facts without constructing missing C30 receipts.

    Revision/pose consistency is only a necessary consistency condition. It
    authenticates neither a Root binding nor historical native getter values.
    """
    ext = request['external']; book = request['book']; current = request['book_current']
    poses = {}; spans = {}
    def pose(revision, value):
        if revision is not None and value is not None:
            _need(revision not in poses or poses[revision] == value, 'C34 actual same revision has conflicting pose')
            poses[revision] = value
    def span(value):
        if value is not None:
            rev = value['pose_revision']; begin = value['from_qpc_ns']; end = value['through_qpc_ns']
            # Extrema are used only for contradiction checks, not to assert
            # coverage of any gap between separately supplied closed spans.
            old = spans.get(rev)
            spans[rev] = (begin, end) if old is None else (min(begin, old[0]), max(end, old[1]))
    if book is not None:
        span(book.get('fixed_root_interval'))
        for sample in book.get('samples') or []:
            span(sample.get('numerical_pose_span'))
            for read in (sample.get('pose_reads') or {}).values():
                pose(read['pose_revision'], read['pose'])
    if current is not None:
        pose(current['pose_revision'], current['pose']); span(current['valid_span'])
    binding = request['binding']
    if binding is not None:
        pose(binding['pose_revision'], binding['committed_pose'])
    ordered = sorted(spans.items())
    for (_, earlier), (_, later) in zip(ordered, ordered[1:]):
        _need(earlier[1] < later[0], 'C34 actual revision spans overlap or reverse')
    by_candidate = {c['observation_identity']['capture_sha256']: c for c in candidates}
    registry = ext['action_registry']; ids = {}; previous_time = -1; completed_floor = 0
    for action in ([] if registry is None else registry['actions'] or []):
        _need(action['state'] == 'executed', 'C34 actual action must be executed')
        _need(action['action_id'] not in ids, 'C34 duplicate actual action identity')
        at = action['at_qpc_ns']
        _need(at >= previous_time, 'C34 actual action time reversal')
        previous_time = at; ids[action['action_id']] = action
        before, after = action['from_pose_revision'], action['to_pose_revision']
        if before is not None:
            _need(before >= completed_floor, 'C34 actual action revision reversal')
        # Necessary integer feasibility only: each actual execution strictly
        # increases revision. This lower bound never fills an unknown revision
        # or becomes a receipt, committed pose, span or returned proof.
        minimum_after = max(completed_floor, 0 if before is None else before)+1
        _need(minimum_after < 1 << 63, 'C34 actual action revision has no uint63 successor')
        if after is not None:
            _need(after >= minimum_after, 'C34 actual action revision reversal')
        completed_floor = minimum_after if after is None else after
        pose(before, action['from_pose']); pose(after, action['to_pose'])
        if after is not None:
            for rev, (begin, end) in spans.items():
                _need(end < at if rev < after else begin >= at, 'C34 actual span contradicts executed revision commit')
        else:
            for rev, (_, end) in spans.items():
                if rev < completed_floor:
                    _need(end < at, 'C34 actual span contradicts executed revision lower bound')
        observed = by_candidate.get(action['observation_capture_sha256'])
        if observed is None:
            missing.add('missing_action_observation')
        else:
            _need(at >= observed['observation_identity']['receiver_upper_qpc_ns'], 'C34 action before supplied observation receipt')
    if current is not None:
        _need(current['pose_revision'] >= completed_floor, 'C34 actual current predates executed revision')
    for capture_sha, record in records.items():
        cause = record['cause_action_id']
        if cause is None:
            continue
        action = ids.get(cause)
        if action is None:
            missing.add('missing_observation_action_cause'); continue
        # Both links are explicit. Neither list position nor an absent candidate
        # supplies an identity, nominal time or admission index here.
        candidate = by_candidate.get(capture_sha)
        if candidate is not None:
            time = candidate['source_time']
            _need(action['at_qpc_ns'] < _C32._source_ns(time, time['adc_tick_ms']), 'C34 supplied action cause is future/cyclic')
        sample = samples.get(record['adc_book_source_sha256'])
        if sample is not None:
            _need(action['at_qpc_ns'] < sample['nominal_qpc_ns'], 'C34 supplied action cause is future/cyclic for linked book')
        if candidate is None and sample is None:
            missing.add('missing_action_cause_nominal')


def project_json(raw):
    """Strict UTF8 JSON entry; maps detached data, never authorizes execution."""
    return _json(project(_parse(raw)))


def project(request):
    """Return detached diagnostic projection/advice, or explicit missing evidence.

    Every supplied decidable relation is checked before missing/default returns.
    A real current candidate permits one exact C32 JSON validation call; missing
    mapping forces that call disabled. Only complete enabled fresh input may
    reach the original C28 code object through C32.
    """
    _tree(request)
    fields = set('schema_version adapter_id diagnostic_only enabled book_source_commit book book_current binding external'.split())
    _need(type(request) is dict and set(request) in (fields, fields-{'enabled'}), 'C34 envelope fields')
    _need(type(request['schema_version']) is int and request['schema_version'] == 1 and
          request['adapter_id'] == ADAPTER_ID and request['diagnostic_only'] is True and
          request['book_source_commit'] == BOOK_SOURCE_COMMIT, 'C34 version/pinned source/diagnostic namespace')
    enabled = request.get('enabled', False)
    _need(type(enabled) is bool, 'C34 enabled boolean')
    _need(len(_json(request)) <= MAX_BYTES, 'C34 encoded input budget')
    request = copy.deepcopy(request)
    missing = set(); ext = request['external']; binding = request['binding']
    _keys(ext, 'evidence_scope now_qpc_ns candidate history config source_admissions captures current_pose action_registry', 'C34 external whitelist')
    _need(ext['evidence_scope'] in ('synthetic_diagnostic_fixture','root_supplied_diagnostic'), 'C34 diagnostic scope')
    now = _C32._uint(ext['now_qpc_ns'])
    _need(type(ext['history']) is list, 'C34 retained candidate history')
    candidates = ext['history'] + ([] if ext['candidate'] is None else [ext['candidate']])
    if ext['candidate'] is None:
        missing.add('missing_candidate')
    for candidate in candidates:
        _C32._candidate(candidate)
        _need(candidate['observation_identity']['receiver_upper_qpc_ns'] <= now, 'C34 future retained capture')
    _binding(binding)
    if binding is None or any(v is None for v in binding.values()):
        missing.add('missing_explicit_numerical_binding')
    samples, discarded = _book_shape(request['book'], request['book_current'], now, missing)
    records = ext['captures']; config = ext['config']; registry = ext['action_registry']
    if records is None:
        missing.add('missing_capture_associations'); records = []
    _need(type(records) is list, 'C34 capture list')
    if config is None:
        missing.add('missing_config')
    if ext['source_admissions'] is None or ext['source_admissions'] == []:
        missing.add('missing_source_admissions')
    if registry is None or (type(registry) is dict and registry.get('actions') is None):
        missing.add('missing_explicit_action_registry')
    _need(registry is None or type(registry) is dict, 'C34 registry object')
    actions = [] if registry is None or registry.get('actions') is None else registry['actions']
    _need(type(actions) is list, 'C34 actions array')
    _need(max(len(candidates),len(records))+len(actions) <= 32, 'C34 combined supplied capture/action bound')
    _metadata(ext['current_pose'], current=True)
    projected_records = []
    by_capture = {}
    for record in records:
        if record is None:
            missing.add('missing_capture_association'); projected_records.append(None); continue
        _keys(record, 'capture_sha256 source_record_sha256 request_raw capture_raw adc_pose em_pose em_origin_capture_sha256 cause_action_id adc_book_source_sha256 em_book_source_sha256', 'C34 capture metadata')
        for key in ('capture_sha256','source_record_sha256'):
            _C32._hash(record[key])
        _need(record['capture_sha256'] not in by_capture, 'C34 duplicate capture hash')
        by_capture[record['capture_sha256']] = record
        for key in ('adc_book_source_sha256','em_book_source_sha256','em_origin_capture_sha256'):
            _nullable(record[key], _C32._hash)
        _metadata(record['adc_pose']); _metadata(record['em_pose'])
        adc_sample = samples.get(record['adc_book_source_sha256'])
        em_sample = samples.get(record['em_book_source_sha256'])
        adc_pose = _pose_projection(record['adc_pose'],adc_sample,'adc',missing)
        if record['em_pose'] is None and record['em_book_source_sha256'] is None:
            em_pose = None
        else:
            em_pose = _pose_projection(record['em_pose'],em_sample,'em',missing)
        call = None if adc_sample is None else adc_sample.get('adc')
        projected_records.append(dict(capture_sha256=record['capture_sha256'],source_record_sha256=record['source_record_sha256'],
            request_raw=record['request_raw'],capture_raw=record['capture_raw'],adc_pose=adc_pose,em_pose=em_pose,
            em_origin_capture_sha256=record['em_origin_capture_sha256'],cause_action_id=record['cause_action_id'],
            adc_call=None if call is None or call['end_qpc_ns'] is None else {k:call[k] for k in ('begin_qpc_ns','end_qpc_ns')}))
    current = request['book_current']; cur_meta = ext['current_pose']; cur = None
    if not _metadata_ready(cur_meta):
        missing.add('missing_current_receipt_metadata')
    if _metadata_ready(cur_meta) and current is not None and current['pose_read'] is not None and current['valid_span'] is not None:
        cur = dict(receipt_id=cur_meta['receipt_id'],context=cur_meta['context'],generation=cur_meta['generation'],
            at_qpc_ns=current['at_qpc_ns'],pose=current['pose'],pose_revision=current['pose_revision'],pose_read=current['pose_read'],
            valid_span=dict(receipt_id=cur_meta['valid_span_receipt_id'],from_qpc_ns=current['valid_span']['from_qpc_ns'],through_qpc_ns=current['valid_span']['through_qpc_ns']))
    partial_root = dict(kind='c30_root_time_association_v1',evidence_scope=ext['evidence_scope'],config=config,
        source_admissions=ext['source_admissions'],captures=None if ext['captures'] is None else projected_records,
        current_pose=cur,action_registry=registry)
    # Validation helpers inspect only actual supplied C30 data. No recommendation
    # entry or fabricated identity is needed to reject a malformed partial input.
    _C32._receipt_shape(partial_root,now)
    _actual_temporal(request,candidates,by_capture,samples,missing)
    if candidates:
        _C32._time_metadata(partial_root,candidates)
    _supplied_admissions(ext['source_admissions'],config if config is not None else
                        candidates[0]['source_time'] if candidates else None)
    _crosschecks(request,candidates,by_capture,samples,missing)
    # When no current candidate exists, complete C32's anchor-dependent
    # admission traversal only with an actual config/history anchor.
    anchor = config if config is not None else candidates[0]['source_time'] if candidates else None
    if ext['source_admissions'] is not None and anchor is not None:
        _C32._admissions(ext['source_admissions'],anchor)
    result = dict(schema_version=1,adapter_id=ADAPTER_ID,diagnostic_only=True,authorization='none',
        claim=CLAIM,native_interval_atomic=False,C31_reference_sha256=C31_REFERENCE_SHA256,
        C30_reference_sha256=C30_REFERENCE_SHA256,C32_sha256=C32_SHA256,core_sha256=CORE_SHA256,
        c32_called=False,core_ran=False,input_status='INPUT_UNAVAILABLE',status='STOP',
        missing_codes=sorted(missing),discarded_book_field_count=discarded,projection=None,c32_result=None)
    if ext['candidate'] is not None:
        projection = dict(schema_version=1,abi_id=_C32.ABI,diagnostic_only=True,enabled=enabled if not missing else False,
            evidence_scope=ext['evidence_scope'],now_qpc_ns=now,candidate=ext['candidate'],history=ext['history'],root_receipt=partial_root)
        c32_result = json.loads(_C32.recommend_json(_json(projection)))
        result['c32_called'] = True
        if not missing:
            result.update(core_ran=c32_result['core_ran'],input_status=c32_result['input_status'],
                          status=c32_result['status'],projection=projection,c32_result=c32_result)
    _tree(result)
    _need(len(_json(result)) <= MAX_BYTES, 'C34 encoded output budget')
    return result



RETIRED_SOURCE70_SHA256 = '63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c'


def inspect_retired_source70(raw_bytes):
    """Single immutable archive diagnostic, never a general composition input.

    Exact bytes gate; no reconstructed clock, identity, receipt or planner call.
    This does not change the archived source or certify physical/native state.
    """
    _need(type(raw_bytes) is bytes and len(raw_bytes) == 82496 and
          hashlib.sha256(raw_bytes).hexdigest() == RETIRED_SOURCE70_SHA256,
          'C34 retired source70 exact bytes required')
    return dict(schema_version=1,adapter_id=ADAPTER_ID,diagnostic_only=True,authorization='none',
        input_status='INPUT_UNAVAILABLE',status='STOP',c32_called=False,core_ran=False,
        claim=CLAIM,native_interval_atomic=False,projection=None,c32_result=None,
        source_sha256=RETIRED_SOURCE70_SHA256,source_bytes=82496,book_schema_version=1,
        book_source_commit=BOOK_SOURCE_COMMIT,
        original_runtime_commit='4dc91fd24531b3df53fc916e8b7f509ad524592c',
        original_export_commit='d0185d335747acb26439f40a8ce945f7f4eaa9af',
        missing_codes=['missing_original_owner_and_current_proof','missing_original_admission_and_capture_proof',
                       'missing_original_native_em_association','missing_original_executed_action_registry'])


__all__ = ['project','project_json','inspect_retired_source70','Rejected','ADAPTER_ID',
           'C31_REFERENCE_SHA256','C30_REFERENCE_SHA256','C32_SHA256','CORE_SHA256']

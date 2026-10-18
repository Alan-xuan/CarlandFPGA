"""Offline independent fixture replay; only stdlib + this experiment's decoder.

The source oracle computes sizes and reconstruction directly from original
synthetic point values. It neither encodes bytes nor calls the decoder's code
selection. Raw fixtures are data, not an executable oracle.
"""
import copy
import json
from pathlib import Path

from candidate_decode import CandidateReceiver, Reject, crc16, decode_frame, decode_payload

HERE = Path(__file__).resolve().parent
RESULTS = []
EXPECTED = {}
FIELDS = ('index', 'tick_ms', 'valid', 'saturated', 'held', 'source_fault', 'source_tick_ms')


def equal(got, expected, label):
    if got != expected:
        raise AssertionError(f'{label}: got {got!r}; expected {expected!r}')


def rejects(action, label):
    try:
        action()
    except Reject as error:
        return str(error)
    raise AssertionError(label + ': accepted invalid candidate')


def source_math(points, e):
    """Independent source arithmetic; selects by bit cost without encoding."""
    n = len(points)
    if not points[0]['valid']:
        return dict(mode='raw', k=0, significant=0, values=[None] * n)
    values = [points[0]['value']]
    z_values = []
    step = 2 * e + 1
    for point in points[1:]:
        delta = point['value'] - values[-1]
        q = (delta + e) // step
        z_values.append(q * 2 if q >= 0 else (-q * 2) - 1)
        values.append(max(0, min(65535, values[-1] + q * step)))
    costs = {}
    for k in range(16):
        if all(z // (2 ** k) <= 31 for z in z_values):
            costs[k] = 16 + sum(z // (2 ** k) + 1 + k for z in z_values)
    chosen = min(costs, key=lambda k: (costs[k], k)) if costs else None
    if chosen is None or (costs[chosen] + 7) // 8 >= n * 2:
        return dict(mode='raw', k=0, significant=n * 16, values=[p['value'] for p in points])
    return dict(mode='rice', k=chosen, significant=costs[chosen], values=values)


def source_block(points, e):
    """Pure sizing/representability oracle; returns no wire bytes."""
    if not 1 <= len(points) <= 128:
        return None
    first = points[0]
    masks = ('valid', 'saturated', 'held', 'source_fault')
    if any(any(p[f] != first[f] for f in masks) for p in points):
        return None
    if first['held'] and any(p['source_tick_ms'] != first['source_tick_ms'] for p in points):
        return None
    metadata = 21
    if len(points) > 1:
        di = points[1]['index'] - first['index']
        dt = points[1]['tick_ms'] - first['tick_ms']
        if not 1 <= di <= 65535 or not 1 <= dt <= 65535:
            return None
        if any(p['index'] != first['index'] + j * di or p['tick_ms'] != first['tick_ms'] + j * dt
               for j, p in enumerate(points)):
            return None
        metadata += 4
    if first['held']:
        age = first['tick_ms'] - first['source_tick_ms']
        if age < 1:
            return None
        metadata += 2 if age <= 65535 else 8
    math = source_math(points, e)
    stored = (math['significant'] + 7) // 8
    if metadata + stored > 32:
        return None
    return dict(math, metadata=metadata, stored=stored, payload=metadata + stored)


def greedy_counts(points, e):
    position, counts = 0, []
    while position < len(points):
        legal = [n for n in range(1, min(128, len(points) - position) + 1)
                 if source_block(points[position:position + n], e) is not None]
        if not legal:
            raise AssertionError('source singleton not representable')
        counts.append(max(legal))
        position += max(legal)
    return counts


def totals(ledgers):
    out = dict(frame_count=len(ledgers))
    for key in ('payload_bytes', 'frame_bytes', 'line_bits_8n1', 'value_count', 'selected_raw_bytes',
                'significant_bits', 'stored_code_bytes', 'padding_bits', 'metadata_bytes'):
        out[key + '_total'] = sum(row[key] for row in ledgers)
    return out


def check_source_frames(name, source, frames, binding, channel, start_sequence):
    expected_counts = greedy_counts(source, binding['e'])
    equal(len(frames), len(expected_counts), name + ' independently sized frame count')
    restored, ledgers, expected_records = [], [], []
    offset = 0
    receiver = CandidateReceiver(binding)
    max_error = 0
    for j, (wire, expected_count) in enumerate(zip(frames, expected_counts)):
        block = source[offset:offset + expected_count]
        expected = source_block(block, binding['e'])
        actual = decode_frame(wire, binding)
        accepted = receiver.accept(wire)
        equal(accepted['points'], actual['points'], name + ' stateless/receiver')
        equal(actual['channel'], channel, name + ' channel')
        equal(actual['sequence'], start_sequence + j, name + ' sequence')
        equal(actual['count'], expected_count, name + ' longest legal prefix')
        equal((actual['mode'], actual['k'], actual['significant_bits']),
              (expected['mode'], expected['k'], expected['significant']), name + ' independent mode/k/bits')
        predicted = []
        for original, value, got in zip(block, expected['values'], actual['points']):
            point = dict(original, value=value)
            predicted.append(point)
            equal({f: got[f] for f in FIELDS}, {f: original[f] for f in FIELDS}, name + ' exact metadata/masks/source')
            equal(got['value'], value, name + ' independent reconstructed value')
            if original['valid']:
                error = abs(got['value'] - original['value'])
                if error > binding['e']:
                    raise AssertionError(name + ' E bound exceeded')
                max_error = max(max_error, error)
        equal(actual['points'][0]['value'], block[0]['value'], name + ' exact block anchor')
        expected_ledger = dict(count=expected_count, value_count=expected_count if block[0]['valid'] else 0,
                               selected_raw_bytes=expected_count * 2 if block[0]['valid'] else 0,
                               significant_bits=expected['significant'], stored_code_bytes=expected['stored'],
                               padding_bits=expected['stored'] * 8 - expected['significant'],
                               metadata_bytes=expected['metadata'], payload_bytes=expected['payload'],
                               outer_overhead_bytes=14, frame_bytes=expected['payload'] + 14,
                               line_bits_8n1=10 * (expected['payload'] + 14))
        equal(actual['byte_ledger'], expected_ledger, name + ' independently computed ledger')
        equal(len(wire), expected_ledger['frame_bytes'], name + ' actual frame bytes')
        restored.extend(actual['points'])
        ledgers.append(actual['byte_ledger'])
        expected_records.append(dict(points=predicted, ledger=expected_ledger,
                                     mode=expected['mode'], k=expected['k'], sequence=start_sequence + j))
        offset += expected_count
    equal(offset, len(source), name + ' every point exactly once')
    EXPECTED[name] = dict(derivation='source-only integer closed loop + exhaustive legal-prefix sizing; no encoded-byte oracle',
                          blocks=expected_records, max_abs_error=max_error, aggregate=totals(ledgers))
    return restored, ledgers, max_error


def fixture_packet(payload, binding, sequence, tick=None):
    """Test envelope only. No sample compressor/packer or production encoder."""
    if tick is None:
        tick = int.from_bytes(payload[13:21], 'little') & 0xFFFFFFFF
    body = (bytes((3, 7, len(payload), binding['config_epoch'])) + sequence.to_bytes(2, 'little')
            + tick.to_bytes(4, 'little') + payload)
    return b'\xa5\x5a' + body + crc16(body).to_bytes(2, 'little')


def singleton(binding, sequence, index, tick, channel=0, value=1234):
    payload = (bytes((1, 8 + (0, 1, 2, 4, 8).index(binding['e']), 4 + channel, 1, 16))
               + binding['session'].to_bytes(4, 'little') + index.to_bytes(4, 'little')
               + tick.to_bytes(8, 'little') + value.to_bytes(2, 'little'))
    return fixture_packet(payload, binding, sequence)


def positives(vectors, manual):
    equal(len(manual['vectors']), 8, 'manual inventory')
    enriched = vectors['manual_vectors']['vectors']
    for row in manual['vectors']:
        companion = next(r for r in enriched if r['name'] == row['name'])
        for key, val in row.items():
            equal(companion[key], val, 'verbatim manual provenance ' + row['name'] + '/' + key)
        wire = bytes.fromhex(row['frame_hex'])
        equal(wire[12:-2], bytes.fromhex(row['payload_hex']), 'manual payload identity')
        restored, ledgers, error = check_source_frames('manual/' + row['name'], row['points'], [wire],
                                                       row['binding'], row['channel'], row['sequence'])
        equal(restored, row['expected_points'], row['name'] + ' hand-derived expected points')
        for key, expected_key in (('payload_bytes', 'payload_bytes'), ('metadata_bytes', 'metadata_bytes'),
                                  ('stored_code_bytes', 'code_bytes'), ('significant_bits', 'significant_bits'),
                                  ('padding_bits', 'padding_bits'), ('frame_bytes', 'frame_bytes'),
                                  ('line_bits_8n1', 'line_bits_8N1')):
            equal(ledgers[0][key], row[expected_key], row['name'] + ' manual cost')
        RESULTS.append(dict(case='manual/' + row['name'], status='passed', frames=1, points=len(restored),
                            max_abs_error=error, ledger=totals(ledgers)))
    equal(len(vectors['synthetic_vectors']), 32, 'synthetic inventory')
    for row in vectors['synthetic_vectors']:
        frames = [bytes.fromhex(wire) for wire in row['frames_hex']]
        restored, ledgers, error = check_source_frames('synthetic/' + row['id'], row['source_points'], frames,
                                                       row['binding'], row['channel'], row['start_sequence'])
        equal(restored, row['restored_points'], row['id'] + ' pinned restored points')
        equal(ledgers, row['ledger_per_frame'], row['id'] + ' pinned ledgers')
        equal(totals(ledgers), row['aggregate_ledger'], row['id'] + ' aggregate')
        # The pinned fixture uses null for some mixed/invalid streams. The
        # independent bound above still checks every valid point explicitly.
        if row['max_abs_error'] is not None:
            equal(error, row['max_abs_error'], row['id'] + ' max error')
        RESULTS.append(dict(case='synthetic/' + row['id'], status='passed', frames=len(frames),
                            points=len(restored), max_abs_error=error, ledger=totals(ledgers)))


def negatives(vectors):
    equal(len(vectors['malformed_payloads']), 23, 'payload negative inventory')
    equal(len(vectors['malformed_frames']), 11, 'frame negative inventory')
    for kind in ('malformed_payloads', 'malformed_frames'):
        for row in vectors[kind]:
            data = bytes.fromhex(row['payload_hex' if kind == 'malformed_payloads' else 'frame_hex'])
            binding = row['binding']
            fn = decode_payload if kind == 'malformed_payloads' else decode_frame
            reason = rejects(lambda: fn(data, binding), row['id'])
            receiver = CandidateReceiver(binding)
            receiver.accept(singleton(binding, 0, 0, 0))
            before = receiver.state_snapshot()
            # An oversized payload may produce an oversized frame, still invalid.
            packet = fixture_packet(data, binding, 1) if kind == 'malformed_payloads' else data
            receiver_reason = rejects(lambda: receiver.accept(packet), row['id'] + ' receiver')
            equal(receiver.state_snapshot(), before, row['id'] + ' atomic failure')
            recovered = receiver.accept(singleton(binding, 100, 1, 1))
            equal((recovered['status'], len(recovered['points'])), ('accepted', 1), row['id'] + ' recovery')
            RESULTS.append(dict(case=kind + '/' + row['id'], status='passed', independent_rejection=reason,
                                fixture_claimed_defect=row['expect_error_contains'], receiver_rejection=receiver_reason,
                                no_state_commit=True, next_frame_recovery=True))


def receiver_checks():
    binding = dict(session=0x01020304, config_epoch=2, e=0)
    equal(crc16(b'123456789'), 0x29B1, 'known CRC check value')
    r = CandidateReceiver(binding)
    binding['session'] = 99
    binding = dict(session=0x01020304, config_epoch=2, e=0)
    first = singleton(binding, 0, 0, 0)
    output = r.accept(first)
    output['points'][0]['index'] = 999
    snapshot = r.state_snapshot()
    snapshot['highwaters'][0] = (999, 999)
    snapshot['binding']['session'] = 0
    snapshot['cache'].clear()
    equal(r.state_snapshot()['highwaters'][0], (0, 0), 'detached output/snapshot')
    for sequence in range(1, 17):
        r.accept(singleton(binding, sequence, sequence, sequence))
    equal(len(r.state_snapshot()['cache']), 16, 'exact bounded cache')
    state = r.state_snapshot()
    equal(r.accept(singleton(binding, 1, 1, 1)), dict(status='duplicate', sequence=1, points=[]), 'cached duplicate')
    equal(r.state_snapshot(), state, 'duplicate does not renew cache')
    rejects(lambda: r.accept(first), 'evicted stale packet')
    rejects(lambda: r.accept(singleton(binding, 1, 1, 1, value=7)), 'same sequence conflict')
    equal(r.state_snapshot(), state, 'conflict/stale atomic')
    # Channel 1 can use the same acquisition coordinates already seen on channel 0.
    r.accept(singleton(binding, 30, 0, 0, channel=1))
    r.accept(singleton(binding, 40, 0, 0, channel=2))
    r.accept(singleton(binding, 50, 0, 0, channel=3))
    state = r.state_snapshot()
    rejects(lambda: r.accept(singleton(binding, 60, 17, 16)), 'tick must exceed high water')
    rejects(lambda: r.accept(singleton(binding, 60, 16, 17)), 'index must exceed high water')
    equal(r.state_snapshot(), state, 'independent index/tick atomic')
    accepted = r.accept(singleton(binding, 100, 17, 17))
    equal(len(accepted['points']), 1, 'sequence gap adds no points')
    equal(r.state_snapshot()['highwaters'], [(17, 17), (0, 0), (0, 0), (0, 0)], 'four independent waters')
    r.accept(singleton(binding, 65535, 18, 18))
    state = r.state_snapshot()
    rejects(lambda: r.accept(singleton(binding, 0, 19, 19)), 'sequence never wraps')
    equal(r.state_snapshot(), state, 'wrap rejection atomic')
    new_binding = dict(binding, session=binding['session'] + 1, config_epoch=3)
    rejects(lambda: r.accept(singleton(new_binding, 0, 0, 0)), 'binding retirement')
    r.close()
    r.close()
    rejects(lambda: r.accept(singleton(binding, 65535, 18, 18)), 'terminal close including duplicate')
    successor = CandidateReceiver(new_binding)
    equal(successor.accept(singleton(new_binding, 0, 0, 0))['status'], 'accepted', 'explicit new receiver')
    RESULTS.append(dict(case='receiver/state_machine', status='passed', cache_limit=16, channels=4,
                        coverage=['CRC known answer', 'binding copied', 'outputs detached', 'snapshots detached',
                                  'cached duplicate zero points/no renewal', 'eviction', 'conflict', 'stale',
                                  'future gap', 'independent index/tick highwaters', 'four channels', '65535 no wrap',
                                  'session/epoch mismatch', 'terminal idempotent close', 'explicit successor']))


def input_strictness():
    class IntTrap(int):
        def __eq__(self, other):
            raise AssertionError('int subclass user equality executed')
    class KeyTrap(str):
        def __hash__(self):
            return str.__hash__(self)
        def __eq__(self, other):
            raise AssertionError('str subclass user equality executed')
    class BytesTrap(bytes):
        pass
    class DictTrap(dict):
        pass
    binding = dict(session=1, config_epoch=2, e=0)
    packet = singleton(binding, 0, 0, 0)
    tests = [lambda: decode_frame(BytesTrap(packet), binding), lambda: decode_frame(bytearray(packet), binding),
             lambda: decode_frame(packet, DictTrap(binding)),
             lambda: decode_frame(packet, dict(binding, session=True)),
             lambda: decode_frame(packet, dict(binding, e=IntTrap(0))),
             lambda: decode_frame(packet, {KeyTrap('session'): 1, 'config_epoch': 2, 'e': 0}),
             lambda: decode_frame(packet, dict(binding, extra=1)),
             lambda: decode_frame(packet, dict(binding, session=-1)),
             lambda: decode_frame(packet, dict(binding, config_epoch=256)),
             lambda: decode_frame(packet, dict(binding, e=3)),
             lambda: decode_payload(BytesTrap(packet[12:-2]), binding)]
    for j, case in enumerate(tests):
        rejects(case, 'strict ingress ' + str(j))
    RESULTS.append(dict(case='strict_ingress', status='passed', checks=len(tests), user_operators_executed=False))


def independent_handchecks():
    binding = dict(session=0x01020304, config_epoch=2, e=0)
    cases = [([10000, 10001, 10002, 10004], 'rice', 1, 26),
             ([0, 8, 16], 'rice', 3, 28), ([0, 64], 'raw', 0, 32),
             ([0, 2048, 4096], 'raw', 0, 48), ([100, 100, 100], 'rice', 0, 18),
             ([100] * 41, 'rice', 0, 56)]
    for values, mode, k, bits in cases:
        points = [dict(index=j, tick_ms=j * 10, value=value, valid=True, saturated=False,
                       held=False, source_fault=False, source_tick_ms=j * 10) for j, value in enumerate(values)]
        result = source_block(points, 0)
        equal((result['mode'], result['k'], result['significant']), (mode, k, bits), 'hand-derived arithmetic')
    RESULTS.append(dict(case='independent/hand_arithmetic', status='passed', checks=len(cases),
                        literal_expectations=[dict(values=v, mode=m, k=k, significant_bits=b) for v,m,k,b in cases]))


def additional_payload_checks(manual):
    binding = dict(session=0x01020304, config_epoch=2, e=0)
    single = bytes.fromhex(manual['vectors'][0]['payload_hex'])
    malformed = []

    def changed(name, offset, value, original=single):
        data = bytearray(original)
        data[offset] = value
        malformed.append((name, bytes(data), binding))

    changed('unknown revision', 0, 2)
    for ecode in (5, 6, 7):
        changed('undefined E code ' + str(ecode), 1, 8 | ecode)
    changed('long origin without held', 2, single[2] | 64)
    changed('valid missing anchor', 4, 0)
    changed('count128 singleton metadata absent', 3, 128)
    invalid = single[:2] + bytes((0, 1, 0)) + single[5:21]
    changed('invalid saturated', 2, 8, invalid)
    changed('invalid held', 2, 16, invalid)
    malformed.append(('invalid fabricated anchor', invalid + b'\x00\x00', binding))
    # Literal Rice body 01 means ZigZag1 => q=-1; from anchor0 at E1
    # reconstruction clamps to0, whose canonical residual is q0, so impossible.
    # Literal body 001 means ZigZag2 => q1; from65535 at E1 it clamps.
    for name, anchor, significant, body in [('impossible negative clamp', 0, 18, b'\x40'),
                                              ('impossible positive clamp', 65535, 19, b'\x20')]:
        e1 = dict(binding, e=1)
        prefix = bytes((1, 1, 4, 2, significant)) + single[5:21]
        data = prefix + b'\x01\x00\x0a\x00' + anchor.to_bytes(2, 'little') + body
        malformed.append((name, data, e1))
    reasons = []
    for name, data, bound in malformed:
        reasons.append(dict(name=name, payload_hex=data.hex(), binding=bound,
                            reason=rejects(lambda: decode_payload(data, bound), name)))
    # Every truncation and extension of a valid singleton frame is rejected.
    packet = bytes.fromhex(manual['vectors'][0]['frame_hex'])
    truncations = 0
    for length in range(len(packet)):
        rejects(lambda: decode_frame(packet[:length], binding), 'truncated frame ' + str(length))
        truncations += 1
    rejects(lambda: decode_frame(packet + b'\x00', binding), 'one trailing frame byte')
    RESULTS.append(dict(case='independent/additional_malformed', status='passed', payload_cases=reasons,
                        all_frame_prefix_truncations=truncations, trailing_frame_byte=True))


def bit_corruption_checks(manual):
    packet = bytes.fromhex(manual['vectors'][0]['frame_hex'])
    binding = manual['vectors'][0]['binding']
    rejected = 0
    for position in range(len(packet) * 8):
        altered = bytearray(packet)
        altered[position // 8] ^= 1 << (position % 8)
        rejects(lambda: decode_frame(bytes(altered), binding), 'single bit corruption ' + str(position))
        rejected += 1
    RESULTS.append(dict(case='independent/every_single_bit_corruption', status='passed',
                        frame_bits=rejected, crc_recomputed=False))


def packer_data_checks(vectors):
    for row in vectors['packer_verification']:
        counts = greedy_counts(row['source_points'], row['binding']['e'])
        if 'frames_hex' in row:
            actual = [decode_frame(bytes.fromhex(w), row['binding'])['count'] for w in row['frames_hex']]
            equal(actual, counts, 'independent exhaustive packer sizing')
            equal(len(counts), row['frame_count'], 'pinned packer count')
        else:
            equal(len(counts), row['frame_count_at_zero'], 'independent required frame count')
            equal((len(counts), 65536 - row['start_sequence']), (30, 6), 'literal no-wrap capacity')
        RESULTS.append(dict(case='packer_data/' + row['id'], status='passed', independently_sized_counts=counts,
                            note='Sizing of opaque fixture source only; no encoder API or partial-output claim'))


def main():
    vectors = json.loads((HERE/'inputs/trace_candidate_vectors.json').read_bytes())
    manual = json.loads((HERE/'inputs/main_manual_vectors.json').read_bytes())
    positives(vectors, manual)
    negatives(vectors)
    receiver_checks()
    input_strictness()
    independent_handchecks()
    additional_payload_checks(manual)
    bit_corruption_checks(manual)
    packer_data_checks(vectors)
    summary = dict(status='passed', manual_vectors=8, synthetic_streams=32, malformed_payloads=23,
                   malformed_frames=11, total_checks=len(RESULTS), results=RESULTS,
                   runtime_acceptance='not_run', production_type7='not_enabled', physical_board='not_run')
    (HERE/'independent_expected.json').write_text(json.dumps(EXPECTED, indent=2) + '\n', encoding='utf-8', newline='\n')
    (HERE/'replay_results.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')
    for result in RESULTS:
        print('PASS', result['case'], json.dumps({k:v for k,v in result.items() if k not in ('case','status')}, sort_keys=True))
    print(json.dumps({k:v for k,v in summary.items() if k != 'results'}, sort_keys=True))


if __name__ == '__main__':
    main()

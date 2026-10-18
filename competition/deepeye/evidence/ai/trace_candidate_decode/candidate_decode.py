"""Independent, offline candidate revision 1 decoder; no production integration.

Written from the copied normative prose/layout, never from B implementation.
No encoder, transport, scanner, authentication, clock, units or motion API.
"""

from collections import OrderedDict
from copy import deepcopy


class Reject(ValueError):
    """An offline candidate packet is structurally or canonically invalid."""


ERRORS = (0, 1, 2, 4, 8)


def require(condition, reason):
    if not condition:
        raise Reject(reason)


def exact_uint(value, width, name):
    require(type(value) is int, name + ': exact int required')
    require(0 <= value < 1 << width, name + ': unsigned bound')
    return value


def binding_copy(binding):
    require(type(binding) is dict, 'binding: exact dict required')
    require(all(type(k) is str for k in binding), 'binding: exact str keys required')
    require(set(binding) == {'session', 'config_epoch', 'e'}, 'binding: exact keys')
    exact_uint(binding['session'], 32, 'session')
    exact_uint(binding['config_epoch'], 8, 'config_epoch')
    exact_uint(binding['e'], 4, 'e')
    require(binding['e'] in ERRORS, 'unsupported E')
    return dict(binding)


def crc16(data):
    """Bit-serial CRC-16/CCITT-FALSE; no third-party or project codec use."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc


def little(data, start, size):
    require(start + size <= len(data), 'truncated metadata')
    return int.from_bytes(data[start:start + size], 'little')


def _canonical_code(values, e):
    """Canonicality predicate's local arithmetic, not a source roundtrip oracle.

    Given reconstructed values, enumerate all legal Rice k by significant bits,
    then apply the RAW byte tie rule. This is independent of the bit reader.
    """
    residuals = []
    previous = values[0]
    for value in values[1:]:
        q = (value - previous + e) // (2 * e + 1)
        previous = min(65535, max(0, previous + q * (2 * e + 1)))
        residuals.append(2 * q if q >= 0 else -2 * q - 1)
    choices = []
    for k in range(16):
        quotients = [z >> k for z in residuals]
        if all(q <= 31 for q in quotients):
            choices.append((16 + sum(q + 1 + k for q in quotients), k))
    raw = b''.join(value.to_bytes(2, 'little') for value in values)
    if not choices:
        return 'raw', 0, 16 * len(values), raw
    significant, k = min(choices)
    if (significant + 7) // 8 >= len(raw):
        return 'raw', 0, 16 * len(values), raw
    digits = []
    for z in residuals:
        digits.extend([0] * (z >> k))
        digits.append(1)
        digits.extend((z >> shift) & 1 for shift in range(k - 1, -1, -1))
    packed = bytearray(values[0].to_bytes(2, 'little'))
    for start in range(0, len(digits), 8):
        group = digits[start:start + 8]
        packed.append(sum(bit << (7 - j) for j, bit in enumerate(group)))
    return 'rice', k, significant, bytes(packed)


def decode_payload(payload, binding):
    bound = binding_copy(binding)
    require(type(payload) is bytes, 'payload: exact bytes required')
    require(21 <= len(payload) <= 32, 'payload length outside 21..32')
    revision, settings, quality, count, significant = payload[:5]
    require(revision == 1, 'candidate revision')
    require(not quality & 0x80, 'reserved quality bit')
    e_code, raw, k = settings & 7, bool(settings & 8), settings >> 4
    require(e_code < len(ERRORS), 'invalid E code')
    e = ERRORS[e_code]
    require(e == bound['e'], 'E binding mismatch')
    require(not raw or k == 0, 'RAW requires k0')
    require(little(payload, 5, 4) == bound['session'], 'session binding mismatch')
    require(1 <= count <= 128, 'point count outside 1..128')
    channel = quality & 3
    valid, saturated, held, source_fault, long_tick = [bool(quality & (1 << i)) for i in range(2, 7)]
    require(not long_tick or held, 'long source without held')
    require(valid or not (saturated or held or long_tick), 'invalid flags')
    first_index = little(payload, 9, 4)
    first_tick = little(payload, 13, 8)
    cursor = 21
    index_stride = tick_stride = None
    if count > 1:
        index_stride = little(payload, cursor, 2)
        tick_stride = little(payload, cursor + 2, 2)
        require(index_stride > 0 and tick_stride > 0, 'zero stride')
        cursor += 4
        require(first_index + (count - 1) * index_stride < 1 << 32, 'index progression overflow')
        require(first_tick + (count - 1) * tick_stride < 1 << 64, 'tick progression overflow')
    origin = None
    if held:
        if long_tick:
            origin = little(payload, cursor, 8)
            cursor += 8
            require(origin < first_tick and first_tick - origin > 65535, 'noncanonical long source origin')
        else:
            age = little(payload, cursor, 2)
            cursor += 2
            require(1 <= age <= 65535 and age <= first_tick, 'short source age bound')
            origin = first_tick - age
    code = payload[cursor:]
    require(len(code) == (significant + 7) // 8, 'code length mismatch or trailing bytes')
    values = []
    if not valid:
        require(raw and k == 0 and significant == 0 and not code, 'invalid quality-only shape')
    else:
        require(significant >= 16 and len(code) >= 2, 'missing valid anchor')
        padding = len(code) * 8 - significant
        require(not padding or not code[-1] & ((1 << padding) - 1), 'nonzero low padding')
        if raw:
            require(significant == count * 16, 'RAW count/significant mismatch')
            values = [little(code, j * 2, 2) for j in range(count)]
        else:
            values = [little(code, 0, 2)]
            position = 16

            def bit():
                nonlocal position
                require(position < significant, 'truncated Rice code')
                answer = (code[position // 8] >> (7 - position % 8)) & 1
                position += 1
                return answer

            for _ in range(count - 1):
                quotient = 0
                while bit() == 0:
                    quotient += 1
                    require(quotient <= 31, 'overlong Rice unary')
                remainder = 0
                for _ in range(k):
                    remainder = remainder * 2 + bit()
                zigzag = (quotient << k) | remainder
                q = zigzag // 2 if not zigzag & 1 else -(zigzag // 2) - 1
                value = min(65535, max(0, values[-1] + q * (2 * e + 1)))
                values.append(value)
            require(position == significant, 'unused significant Rice bits')
        declared = ('raw' if raw else 'rice', k, significant, code)
        require(declared == _canonical_code(values, e), 'noncanonical mode/k/bits/code')
    points = []
    for j in range(count):
        index = first_index + j * (index_stride or 0)
        tick = first_tick + j * (tick_stride or 0)
        points.append(dict(index=index, tick_ms=tick, value=values[j] if valid else None,
                           valid=valid, saturated=saturated, held=held, source_fault=source_fault,
                           source_tick_ms=(origin if held else tick) if valid else None))
    ledger = dict(count=count, value_count=count if valid else 0,
                  selected_raw_bytes=2 * count if valid else 0, significant_bits=significant,
                  stored_code_bytes=len(code), padding_bits=len(code) * 8 - significant,
                  metadata_bytes=cursor, payload_bytes=len(payload), outer_overhead_bytes=14,
                  frame_bytes=len(payload) + 14, line_bits_8n1=(len(payload) + 14) * 10)
    return dict(channel=channel, e=e, mode='raw' if raw else 'rice', k=k,
                count=count, significant_bits=significant, first_index=first_index,
                first_tick_ms=first_tick, index_stride=index_stride, tick_stride_ms=tick_stride,
                held_origin=origin, points=points, byte_ledger=ledger)


def decode_frame(packet, binding):
    bound = binding_copy(binding)
    require(type(packet) is bytes, 'packet: exact bytes required')
    require(35 <= len(packet) <= 46, 'frame length outside 35..46')
    require(packet[:2] == b'\xa5\x5a', 'frame magic')
    require(packet[2] == 3 and packet[3] == 7, 'frame version/type')
    require(21 <= packet[4] <= 32 and len(packet) == packet[4] + 14, 'declared frame length')
    require(packet[5] == bound['config_epoch'], 'epoch binding mismatch')
    require(crc16(packet[2:-2]) == little(packet, len(packet) - 2, 2), 'CRC mismatch')
    decoded = decode_payload(packet[12:-2], bound)
    require(little(packet, 8, 4) == decoded['first_tick_ms'] & 0xFFFFFFFF, 'header tick-low mismatch')
    decoded.update(sequence=little(packet, 6, 2), config_epoch=packet[5])
    return decoded


class CandidateReceiver:
    """Pure offline receiver with atomic state and one terminal binding."""

    def __init__(self, binding):
        self._binding = binding_copy(binding)
        self._cache = OrderedDict()
        self._highwaters = [None] * 4
        self._last_sequence = None
        self._closed = False

    def close(self):
        self._closed = True

    def state_snapshot(self):
        return deepcopy(dict(binding=self._binding, last_sequence=self._last_sequence,
                             cache=list(self._cache.items()), highwaters=self._highwaters,
                             closed=self._closed))

    def accept(self, packet):
        require(not self._closed, 'receiver closed')
        decoded = decode_frame(packet, self._binding)
        sequence = decoded['sequence']
        if sequence in self._cache:
            require(self._cache[sequence] == packet, 'sequence conflict')
            return dict(status='duplicate', sequence=sequence, points=[])
        require(self._last_sequence is None or sequence > self._last_sequence, 'stale sequence/no wrap')
        water = self._highwaters[decoded['channel']]
        first, last = decoded['points'][0], decoded['points'][-1]
        require(water is None or (first['index'] > water[0] and first['tick_ms'] > water[1]),
                'per-channel high water')
        self._cache[sequence] = packet
        if len(self._cache) > 16:
            self._cache.popitem(last=False)
        self._last_sequence = sequence
        self._highwaters[decoded['channel']] = (last['index'], last['tick_ms'])
        decoded['status'] = 'accepted'
        return decoded

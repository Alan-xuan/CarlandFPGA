"""Strict host-envelope record validator; bounded, stateless and non-authorizing.

Validates one JSON envelope against the local sealed whitelist
``docs/host_contract.json`` (JSON Schema Draft 2020-12, every ``$ref`` local)
plus the static cross-field rules frozen in ``docs/host_timing_contract.md``,
``docs/enums.json`` and ``docs/interface.json`` (wire layout revision 1).

Deliberate limits - a successful return is NOT motion authorization:
- No authentication or ACL: the caller asserts the authenticated ``producer``
  and the active negotiated ``context``; process/pipe isolation is a separate
  runtime gate (host_contract.json x-cross-field-invariants).
- No history or ledger: observation freshness, duplicate-command retention,
  mailbox consumption, codec rollback and monotonic deadline renewal are
  stateful checks owned by the caller. Nothing here reads a live ledger.
- No measured time: anchors, USB/clock/holdover bounds and sample-window
  arithmetic come from ``host_timing_contract.md`` with independently verified
  measurement records; nullable hash fields here are references, never
  authentication, and a null timing/capture reference authorizes nothing.
- No BOOT handshake completion, physical capture validation, register/reset
  semantics, collision or route legality, sensor calibration or board state.
- No routing: ``board_response`` is hardware-bridge-to-authority only; the
  optional ``consumer`` argument refuses to mark it safe for any other role.
- No network, board, model, service or live-ledger access: parsing and
  checking only. Every rejection (including bad input types) raises ValueError.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

from jsonschema import Draft202012Validator, exceptions
from jsonschema.validators import extend


MAX_MESSAGE_BYTES = 16384
MAX_NESTING_DEPTH = 16
QUATERNION_NORM_TOLERANCE = 1e-3
FACE_CLEARANCE_TOLERANCE_M = 1e-9

PROFILE_NAMES = {1: 'fast_9600', 2: 'stress_300'}
SAMPLE_COUNTS = {1: 50, 2: 800}
DURATION_LIMIT_MS = {'fast_9600': 3000, 'stress_300': 12000}
TOPOLOGY_BINDING = {1: ('board_capture', True),
                    2: ('pc_direct_host', False),
                    3: ('fpga_local_capture', True)}
FRAME_TYPE_TELEM = 1
FRAME_TYPE_EVENT = 2
KNOWN_REQUEST_TYPES = frozenset({5, 10, 12, 14})
RESPONSE_REQUEST_TYPE = {9: 5, 11: 10, 15: 14}
PHASES = frozenset({0, 1, 2, 3, 4})
CAPTURE_QUALITY_RESERVED_MASK = 0xF0
GATE_HALF_EXTENT_M = 15.0
_FACE_AXIS = {'+X': (0, 1.0), '-X': (0, -1.0), '+Y': (1, 1.0),
              '-Y': (1, -1.0), '+Z': (2, 1.0), '-Z': (2, -1.0)}
_DENIED_KEY_PARTS = ('obstacle', 'truth', 'seed', 'hidden', 'screenshot',
                     'editor', 'collision_query', 'precomputed')

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'docs' / 'host_contract.json'

_SCHEMA = None
_MESSAGE_VALIDATOR = None
_CONTEXT_VALIDATOR = None


@dataclass(frozen=True)
class ValidatedMessage:
    """Informational record of one accepted envelope; never an authorization."""
    kind: str
    producer: str
    consumer: str | None
    authority_only: bool
    document: dict


def _load_sibling(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_wire = _load_sibling('deepeye_wire', 'wire.py')
_motion = _load_sibling('deepeye_motion', 'motion.py')


def _strict_enum(validator, enums, instance, schema):
    if any(type(candidate) is type(instance) and candidate == instance for candidate in enums):
        return
    yield exceptions.ValidationError(
        '{!r} is not one of {!r} under strict type identity'.format(instance, enums))


def _strict_const(validator, const, instance, schema):
    if type(instance) is type(const) and instance == const:
        return
    yield exceptions.ValidationError('{!r} is not strictly {!r}'.format(instance, const))


StrictDraft202012Validator = extend(
    Draft202012Validator,
    {'enum': _strict_enum, 'const': _strict_const},
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        'integer', lambda checker, instance: type(instance) is int))


def _iter_refs(node):
    if isinstance(node, dict):
        if '$ref' in node:
            yield node['$ref']
        for value in node.values():
            yield from _iter_refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_refs(value)


def _sealed_schema():
    global _SCHEMA
    if _SCHEMA is None:
        schema = json.loads(SCHEMA_PATH.read_bytes().decode('utf-8'))
        for reference in _iter_refs(schema):
            if not reference.startswith('#/$defs/'):
                raise ValueError(
                    'host_contract.json carries non-local $ref {!r}; refusing to resolve'.format(reference))
        _SCHEMA = schema
    return _SCHEMA


def _validators():
    global _MESSAGE_VALIDATOR, _CONTEXT_VALIDATOR
    if _MESSAGE_VALIDATOR is None:
        schema = _sealed_schema()
        _MESSAGE_VALIDATOR = StrictDraft202012Validator(schema)
        _CONTEXT_VALIDATOR = StrictDraft202012Validator(schema['$defs']['context'])
    return _MESSAGE_VALIDATOR, _CONTEXT_VALIDATOR

def _subtree(error):
    collected = [error]
    stack = list(error.context or [])
    while stack:
        current = stack.pop()
        collected.append(current)
        stack.extend(current.context or [])
    return collected


def _closest_error(error):
    if not error.context:
        return error
    branches = [_subtree(branch) for branch in error.context]
    branch = min(branches, key=lambda nodes: (len(nodes), -max(len(node.absolute_path) for node in nodes)))
    return max(branch, key=lambda node: len(node.absolute_path))


def _describe(error):
    error = _closest_error(error)
    path = '/'.join(str(part) for part in error.absolute_path)
    message = error.message
    if len(message) > 160:
        message = message[:160] + '...'
    return '{}: {}'.format(path or '<root>', message)


def _reject_constant(token):
    raise ValueError('non-finite JSON constant {!r} is not allowed'.format(token))


def _parse_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('non-finite JSON number {!r} is not allowed'.format(text))
    return value


def _strict_object(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError('duplicate JSON object key {!r}'.format(key))
        document[key] = value
    return document


def _check_nesting(raw):
    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:
                escaped = True
            elif byte == 0x22:
                in_string = False
        elif byte == 0x22:
            in_string = True
        elif byte in (0x7B, 0x5B):
            depth += 1
            if depth > MAX_NESTING_DEPTH:
                raise ValueError('message nesting exceeds {} levels'.format(MAX_NESTING_DEPTH))
        elif byte in (0x7D, 0x5D):
            depth -= 1


def _reject_nonfinite(node):
    if isinstance(node, float) and not math.isfinite(node):
        raise ValueError('non-finite number is not allowed')
    if isinstance(node, dict):
        for value in node.values():
            _reject_nonfinite(value)
    elif isinstance(node, list):
        for value in node:
            _reject_nonfinite(value)


def _reject_denied_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = key.lower()
            for part in _DENIED_KEY_PARTS:
                if part in lowered:
                    raise ValueError(
                        'controller input may not carry hidden-truth field {!r}'.format(key))
            _reject_denied_keys(value)
    elif isinstance(node, list):
        for value in node:
            _reject_denied_keys(value)


def _parse_message(raw_bytes):
    if not isinstance(raw_bytes, (bytes, bytearray)):
        raise ValueError('raw_bytes must be bytes')
    raw = bytes(raw_bytes)
    if not 0 < len(raw) <= MAX_MESSAGE_BYTES:
        raise ValueError('message must be between 1 and {} bytes'.format(MAX_MESSAGE_BYTES))
    _check_nesting(raw)
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError('message is not valid UTF-8: {}'.format(error)) from error
    try:
        document = json.loads(text, object_pairs_hook=_strict_object,
                              parse_constant=_reject_constant, parse_float=_parse_float)
    except RecursionError as error:
        raise ValueError('message nesting exceeds the parser bound') from error
    except json.JSONDecodeError as error:
        raise ValueError('message is not exactly one JSON value: {}'.format(error)) from error
    _reject_nonfinite(document)
    _reject_denied_keys(document)
    return document


def _check_producer_argument(producer, schema):
    if not isinstance(producer, str) or producer not in schema['x-producers']:
        raise ValueError('unknown producer role {!r}'.format(producer))


def _check_consumer_argument(consumer, authority_only, schema):
    if consumer is None:
        return
    if not isinstance(consumer, str) or consumer not in schema['x-producers']:
        raise ValueError('unknown consumer role {!r}'.format(consumer))
    if authority_only and consumer != 'world_authority':
        raise ValueError(
            'board_response is authority-facing only; refusing consumer {!r}'.format(consumer))


def _check_now_argument(now_ns):
    if type(now_ns) is not int or now_ns < 0:
        raise ValueError('now_ns must be a nonnegative integer monotonic nanosecond value')


def _check_context_argument(context, validator):
    if not isinstance(context, dict):
        raise ValueError('context must be the negotiated context object')
    error = next(validator.iter_errors(context), None)
    if error is not None:
        raise ValueError('context reject: {}'.format(_describe(error)))


def _check_message_context(document, context):
    if document['context'] != context:
        raise ValueError('message context does not equal the active negotiated context')


def _check_nested_contexts(document, context):
    observation = document.get('observation')
    if isinstance(observation, dict) and observation.get('context') != context:
        raise ValueError('observation context does not equal the active negotiated context')

_INTERVAL_FIELDS = {
    'telem_observation': (('receipt_interval_ns',),
                          ('adc_last_interval_ns', 'adc_first_interval_ns', 'native_em_interval_ns')),
    'event_observation': (('receipt_interval_ns',), ('trigger_sample_interval_ns',)),
    'odometry': ((), ('at_interval_ns',)),
    'board_response': (('receipt_interval_ns',), ()),
}


def _check_intervals(document, kind, now_ns):
    receipt_fields, mapped_fields = _INTERVAL_FIELDS.get(kind, ((), ()))
    for field in receipt_fields + mapped_fields:
        interval = document[field]
        if interval is not None and interval['lower_ns'] > interval['upper_ns']:
            raise ValueError('{} has lower_ns after upper_ns'.format(field))
    for field in receipt_fields:
        interval = document[field]
        if interval is not None and interval['upper_ns'] > now_ns:
            raise ValueError('{} ends after the current host time'.format(field))
    for field in mapped_fields:
        interval = document[field]
        if interval is not None and interval['lower_ns'] > now_ns:
            raise ValueError('{} starts after the current host time'.format(field))


def _check_pose(pose_document, label):
    values = (list(pose_document['position_m']) + list(pose_document['orientation_xyzw'])
              + [pose_document['position_error_bound_m'],
                 pose_document['orientation_error_bound_rad']])
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('{} contains a non-finite or non-numeric value'.format(label))
    norm = math.sqrt(sum(component * component for component in pose_document['orientation_xyzw']))
    if abs(norm - 1.0) > QUATERNION_NORM_TOLERANCE:
        raise ValueError('{} quaternion is not unit within {}'.format(label, QUATERNION_NORM_TOLERANCE))


def _check_gate(gate, label):
    face = gate['face']
    axis, sign = _FACE_AXIS[face]
    center = gate['center_m']
    radius = gate['radius_m']
    for value in center:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('{} center contains a non-finite or non-numeric value'.format(label))
    if center[axis] != sign * GATE_HALF_EXTENT_M:
        raise ValueError('{} center is not on the selected {} face'.format(label, face))
    in_plane = math.hypot(*(value for index, value in enumerate(center) if index != axis))
    if in_plane + radius > GATE_HALF_EXTENT_M + FACE_CLEARANCE_TOLERANCE_M:
        raise ValueError('{} circle does not fully clear the cube face'.format(label))


def _profile_name(context):
    return PROFILE_NAMES[context['transport_profile_id']]


def _check_target(target_document, profile_name):
    action = target_document['action']
    if action == 0:
        if any(target_document[field] != 0
               for field in ('yaw_q', 'pitch_q', 'speed_code', 'duration_ms')):
            raise ValueError('STOP target must keep yaw_q, pitch_q, speed_code and duration_ms at zero')
    else:
        duration = target_document['duration_ms']
        if duration <= 0:
            raise ValueError('SET_TARGET requires a positive duration_ms')
        limit = DURATION_LIMIT_MS[profile_name]
        if duration > limit:
            raise ValueError('SET_TARGET duration_ms {} exceeds the {} ms {} limit'.format(
                duration, limit, profile_name))
    try:
        _motion.validate(profile_name, target_document['speed_code'],
                         target_document['yaw_q'], target_document['pitch_q'])
    except ValueError as error:
        raise ValueError('motion target rejected: {}'.format(error)) from error


def _require_observation(document):
    if document['target']['action'] == 1 and document['observation'] is None:
        raise ValueError('SET_TARGET requires a nonnull same-context observation')


def _decode_frame(wire_frame_hex, context):
    try:
        packet = bytes.fromhex(wire_frame_hex)
    except ValueError as error:
        raise ValueError('wire_frame_hex is not hex: {}'.format(error)) from error
    try:
        frame = _wire.decode(packet)
    except ValueError as error:
        raise ValueError('wire frame rejected: {}'.format(error)) from error
    if frame.config_epoch != context['config_epoch']:
        raise ValueError('wire header config_epoch does not match the active context')
    return frame


def _check_telem(document, context, now_ns):
    frame = _decode_frame(document['wire_frame_hex'], context)
    if frame.type_id != FRAME_TYPE_TELEM:
        raise ValueError('telem_observation wire frame must be TELEM (type 1)')
    if frame.sequence != document['observed_seq']:
        raise ValueError('wire header sequence does not equal observed_seq')
    if frame.tick_ms != document['tick_ms_raw']:
        raise ValueError('wire header tick does not equal tick_ms_raw')
    mean = struct.unpack('<4H', frame.payload[:8])
    spans = struct.unpack('<4H', frame.payload[8:16])
    quality, = struct.unpack('<H', frame.payload[16:18])
    if list(mean) != document['mean_counts']:
        raise ValueError('wire mean counts do not equal the envelope')
    if list(spans) != document['range_counts']:
        raise ValueError('wire range counts do not equal the envelope')
    if quality != document['quality_flags']:
        raise ValueError('wire quality flags do not equal the envelope')
    expected = SAMPLE_COUNTS[context['transport_profile_id']]
    if document['sample_count'] != expected:
        raise ValueError('sample_count {} does not match transport profile count {}'.format(
            document['sample_count'], expected))


def _check_event(document, context, now_ns):
    frame = _decode_frame(document['wire_frame_hex'], context)
    if frame.type_id != FRAME_TYPE_EVENT:
        raise ValueError('event_observation wire frame must be EVENT (type 2)')
    if frame.sequence != document['observed_seq']:
        raise ValueError('wire header sequence does not equal observed_seq')
    if frame.tick_ms != document['tick_ms_raw']:
        raise ValueError('wire header tick does not equal tick_ms_raw')
    decoded = struct.unpack('<HBBH', frame.payload)
    if decoded != (document['bitmap'], document['channel'], document['severity'],
                   document['peak_counts']):
        raise ValueError('wire event payload does not equal the envelope')


def _check_candidate(document, context, now_ns):
    if document['completed_monotonic_ns'] > now_ns:
        raise ValueError('candidate completed after the current host time')
    _check_target(document['target'], _profile_name(context))
    _require_observation(document)


def _check_request(document, context, now_ns):
    if document['host_issue_monotonic_ns'] > now_ns:
        raise ValueError('request issue time is after the current host time')
    _check_target(document['target'], _profile_name(context))
    _require_observation(document)


def _check_grant(document, context, now_ns):
    _check_target(document['target'], _profile_name(context))
    _require_observation(document)
    expected_source, capture_required = TOPOLOGY_BINDING[context['topology_id']]
    if document['action_source'] != expected_source:
        raise ValueError('action_source {!r} does not match topology {}'.format(
            document['action_source'], context['topology_id']))
    capture_seq = document['capture_seq']
    if capture_required and capture_seq is None:
        raise ValueError('topology {} requires a nonnull capture_seq'.format(context['topology_id']))
    if not capture_required and capture_seq is not None:
        raise ValueError('topology {} requires capture_seq to stay null'.format(context['topology_id']))
    if document['target']['action'] == 1 and document['deadline_monotonic_ns'] <= now_ns:
        raise ValueError('a positive grant requires deadline_monotonic_ns after the current host time')


def _check_odometry(document, context, now_ns):
    _check_pose(document['pose'], 'odometry pose')


def _check_geometry(document, context, now_ns):
    _check_gate(document['entry_blue'], 'entry_blue')
    _check_gate(document['exit_red'], 'exit_red')
    if document['entry_blue']['radius_m'] != document['exit_red']['radius_m']:
        raise ValueError('entry and exit gate radii must be equal')
    _check_pose(document['initial_odometry'], 'initial odometry')

_KIND_VALIDATOR_CACHE = {}


def _kind_validator(kind):
    validator = _KIND_VALIDATOR_CACHE.get(kind)
    if validator is None:
        schema = _sealed_schema()
        validator = StrictDraft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/' + kind})
        _KIND_VALIDATOR_CACHE[kind] = validator
    return validator


def _check_request_type(request_type, expected):
    if request_type not in KNOWN_REQUEST_TYPES:
        raise ValueError('unknown request_type {}'.format(request_type))
    if request_type != expected:
        raise ValueError('request_type {} does not match the expected request {}'.format(
            request_type, expected))


def _check_config_ack(frame, context):
    fields = struct.unpack('<IHBBBBBHBBBH', frame.payload)
    _check_request_type(fields[2], RESPONSE_REQUEST_TYPE[9])
    if fields[3] not in PHASES:
        raise ValueError('CONFIG_ACK carries unknown phase {}'.format(fields[3]))
    if fields[10] != context['config_epoch']:
        raise ValueError('CONFIG_ACK applied_epoch does not match the active context')


def _check_gain_ack(frame, context):
    fields = struct.unpack('<IHBBBHHHHB', frame.payload)
    _check_request_type(fields[2], RESPONSE_REQUEST_TYPE[11])
    if fields[3] not in PHASES:
        raise ValueError('GAIN_ACK carries unknown phase {}'.format(fields[3]))


def _check_boot_ack(frame, context):
    mode, = struct.unpack_from('<B', frame.payload, 4)
    expected = (context['transport_profile_id'] | (context['source_id'] << 2)
                | (context['topology_id'] << 5))
    if mode != expected:
        raise ValueError('BOOT_ACK mode {} does not echo the proposed context encoding {}'.format(
            mode, expected))


def _check_ack3d(frame, context):
    fields = struct.unpack('<IHBBhhBHBHBB', frame.payload)
    _check_request_type(fields[2], RESPONSE_REQUEST_TYPE[15])
    if fields[3] not in PHASES:
        raise ValueError('ACK3D carries unknown phase {}'.format(fields[3]))
    if fields[10] != context['config_epoch']:
        raise ValueError('ACK3D control_epoch does not match the active context')
    if fields[11] & CAPTURE_QUALITY_RESERVED_MASK:
        raise ValueError('ACK3D capture_quality uses reserved bits')


def _check_state(frame, context):
    """Frozen 18-byte physical GAIN/PC_DIRECT diagnostic heartbeat.

    Its tick can anchor a separately measured clock. Its capture-looking
    fields never establish three-axis motion or a PC_DIRECT command lease.
    """
    fields = struct.unpack('<IHhBBHHHBB', frame.payload)
    if fields[4] not in PHASES:
        raise ValueError('STATE carries unknown phase {}'.format(fields[4]))
    if fields[6] > 0xFF:
        raise ValueError('STATE fault_flags must zero the high byte')
    if fields[8] != context['config_epoch']:
        raise ValueError('STATE control_epoch does not match the active context')
    if fields[9] & CAPTURE_QUALITY_RESERVED_MASK:
        raise ValueError('STATE capture_quality uses reserved bits')


def _check_state3d(frame, context):
    fields = struct.unpack('<IHhhBBHHHBB', frame.payload)
    if fields[5] not in PHASES:
        raise ValueError('STATE3D carries unknown phase {}'.format(fields[5]))
    if fields[7] > 0xFF:
        raise ValueError('STATE3D fault_flags must zero the high byte')
    if fields[9] != context['config_epoch']:
        raise ValueError('STATE3D control_epoch does not match the active context')
    if fields[10] & CAPTURE_QUALITY_RESERVED_MASK:
        raise ValueError('STATE3D capture_quality uses reserved bits')


_BOARD_RESPONSE_TYPES = {8: _check_state, 9: _check_config_ack, 11: _check_gain_ack, 13: _check_boot_ack,
                         15: _check_ack3d, 16: _check_state3d}


def _check_board_response(document, context, now_ns):
    frame = _decode_frame(document['wire_frame_hex'], context)
    handler = _BOARD_RESPONSE_TYPES.get(frame.type_id)
    if handler is None:
        raise ValueError(
            'board_response may carry only STATE(8), CONFIG_ACK(9), GAIN_ACK(11), BOOT_ACK(13), '
            'ACK3D(15) or STATE3D(16)')
    session, = struct.unpack_from('<I', frame.payload, 0)
    if session != context['session']:
        raise ValueError('board_response session does not match the active context')
    handler(frame, context)
    if frame.type_id == 8 and context['topology_id'] == 2:
        if document['physical_capture_record_sha256'] is not None:
            raise ValueError('PC_DIRECT STATE heartbeat cannot claim physical motion capture')


_KIND_CHECKS = {
    'telem_observation': _check_telem,
    'event_observation': _check_event,
    'model_candidate': _check_candidate,
    'motion_request': _check_request,
    'motion_grant': _check_grant,
    'odometry': _check_odometry,
    'public_task_geometry': _check_geometry,
    'board_response': _check_board_response,
}


def validate_message(raw_bytes, *, producer, context, now_ns, consumer=None):
    """Validate one bounded envelope; raise ValueError on any rejection.

    ``producer`` and ``context`` are caller-asserted (authenticated upstream);
    ``now_ns`` is the caller's monotonic host nanosecond reading. The returned
    record is a static-consistency verdict only: it is never ACL proof, never
    measured-time provenance, never observation-history freshness and never
    motion authorization. World authority still verifies session/epoch,
    capture, request and observation history and deadlines before any grant,
    and stale grants stay the caller's responsibility to reject.
    """
    schema = _sealed_schema()
    message_validator, context_validator = _validators()
    _check_producer_argument(producer, schema)
    _check_now_argument(now_ns)
    _check_context_argument(context, context_validator)
    document = _parse_message(raw_bytes)
    error = next(message_validator.iter_errors(document), None)
    if error is not None:
        kind_hint = document.get('kind') if isinstance(document, dict) else None
        if isinstance(kind_hint, str) and kind_hint in _KIND_CHECKS:
            error = next(_kind_validator(kind_hint).iter_errors(document), error)
        raise ValueError('host_contract.json reject: {}'.format(_describe(error)))
    kind = document['kind']
    if kind not in schema['x-producers'][producer]:
        raise ValueError('producer {!r} may not carry {!r}'.format(producer, kind))
    _check_message_context(document, context)
    _check_nested_contexts(document, context)
    _check_intervals(document, kind, now_ns)
    _KIND_CHECKS[kind](document, context, now_ns)
    authority_only = kind in schema.get('x-authority-only-kinds', [])
    _check_consumer_argument(consumer, authority_only, schema)
    return ValidatedMessage(kind=kind, producer=producer, consumer=consumer,
                            authority_only=authority_only, document=document)


__all__ = ['MAX_MESSAGE_BYTES', 'MAX_NESTING_DEPTH', 'QUATERNION_NORM_TOLERANCE',
           'ValidatedMessage', 'validate_message']

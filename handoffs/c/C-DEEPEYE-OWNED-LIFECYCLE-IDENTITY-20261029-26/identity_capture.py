"""C26 SOURCE ONLY: current release cannot authorize any identity probe.

No native library, identity collection or candidate execution occurs on import.
Only reviewed original Create/Popen HANDLEs and current self pseudo HANDLE are
in scope. Never use a PID list or a self report to establish ownership.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

SOURCE_ONLY = True
ROOT_CAP = 8192
LINE_CAP = 3072  # Includes LF; original actor stream still has its 4096B cap.
ACTOR_CAP = 4096
OUTER_STDOUT_CAP = 8192
IMAGE_CHARS = 2048
SCHEMA = 'C26.identity.v1'
PREFIX = b'C26_IDENTITY '
FIXED = {'primary': b'C25_PRIMARY\n', 'owned-residual': b'C25_OWNED_RESIDUAL\n'}
FLAG_NAMES = ('debug', 'inspect', 'interactive', 'optimize', 'dont_write_bytecode',
              'no_user_site', 'no_site', 'ignore_environment', 'verbose',
              'bytes_warning', 'quiet', 'hash_randomization', 'isolated',
              'dev_mode', 'utf8_mode', 'warn_default_encoding', 'safe_path',
              'int_max_str_digits')


class IdentityError(ValueError):
    pass


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise IdentityError('duplicate_key')
        value[key] = item
    return value


def _reject_constant(_value):
    raise IdentityError('nonfinite_JSON')


def _read(path, cap):
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    if len(raw) > cap:
        raise IdentityError('file_bound')
    return raw


def _decode(raw):
    try:
        return json.loads(raw.decode('ascii'), object_pairs_hook=_pairs,
                          parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise IdentityError('strict_JSON_failed') from exc


def require_root():
    """Permanent current-source gate, before Popen/Job/API/self probes.

    Editing false booleans is insufficient. A fresh operation, guard, reviewed
    authorization design and owner hard-limit closure require a new source
    revision. No execution authorization validator is claimed by this proposal.
    """
    root = _decode(_read(Path(__file__).with_name('ROOT.false.json'), ROOT_CAP))
    if type(root) is not dict or root.get('schema_version') != 1:
        raise IdentityError('root_schema')
    if SOURCE_ONLY or root.get('enabled') is not True or root.get('execution_authorized') is not True:
        raise IdentityError('C26_source_only_execution_forbidden')
    # Intentionally no reachable success branch in this delivery.
    raise IdentityError('fresh_authorization_and_owner_hard_limit_not_implemented')


def _text(value, cap):
    if type(value) is not str or len(value) > cap or any(c in value for c in ('\0', '\r', '\n')):
        raise IdentityError('runtime_text_bound')
    return value


def _version(value):
    # Preserve raw sys.version, including escaped line breaks inside JSON.
    if type(value) is not str or len(value) > 384 or '\0' in value:
        raise IdentityError('runtime_version_bound')
    return value


def _runtime():
    require_root()  # direct private metadata collector is closed too
    flags = {name: getattr(sys.flags, name, None) for name in FLAG_NAMES}
    if any(type(value) not in (int, bool, type(None)) for value in flags.values()):
        raise IdentityError('runtime_flags_type')
    optional_base = getattr(sys, '_base_executable', None)
    missing = {name: 'attribute_unavailable' for name, value in flags.items() if value is None}
    if optional_base is None:
        missing['base_executable'] = 'attribute_unavailable'
    return dict(executable=_text(sys.executable, 512),
                base_executable=None if optional_base is None else _text(optional_base, 512),
                prefix=_text(sys.prefix, 512), base_prefix=_text(sys.base_prefix, 512),
                version=_version(sys.version), flags=flags, missing=missing)


def capture_original_handle(handle, origin):
    """Future original HANDLE probe; no PID input/reopen/scanning API exists.

    Caller must retain the original HANDLE until the original Wait/Close. This
    function itself cannot establish its provenance; the four-source patch
    supplies it directly at original acquisition sites.
    """
    require_root()
    if origin not in ('original_CreateProcessW', 'original_Popen', 'current_self_pseudo'):
        raise IdentityError('handle_origin')
    if origin != 'current_self_pseudo' and (type(handle) is not int or not 0 < handle < 2**64):
        raise IdentityError('handle_type')
    import ctypes as c
    if os.name != 'nt' or c.sizeof(c.c_void_p) != 8:
        raise IdentityError('Windows_64_required')
    H, D, B = c.c_void_p, c.c_uint32, c.c_int32

    class FT(c.Structure):
        _fields_ = [('low', D), ('high', D)]

    kernel = c.WinDLL('kernel32', use_last_error=True)
    signatures = {'GetCurrentProcess': ([], H), 'GetProcessId': ([H], D),
                  'QueryFullProcessImageNameW': ([H, D, c.c_wchar_p, c.POINTER(D)], B),
                  'GetProcessTimes': ([H, c.POINTER(FT), c.POINTER(FT), c.POINTER(FT), c.POINTER(FT)], B)}
    for name, (args, result) in signatures.items():
        fn = getattr(kernel, name)
        fn.argtypes, fn.restype = args, result
    calls = []
    if origin == 'current_self_pseudo':
        c.set_last_error(0)
        handle = kernel.GetCurrentProcess()
        error = c.get_last_error()
        calls.append(dict(api='GetCurrentProcess', inputs={}, returned=handle, last_error=error))
        if not handle:
            raise IdentityError('self_pseudo_HANDLE_unknown')
    c.set_last_error(0)
    pid = kernel.GetProcessId(handle)
    error = c.get_last_error()
    calls.append(dict(api='GetProcessId', inputs={'handle': handle}, returned=pid, last_error=error))
    buffer = c.create_unicode_buffer(IMAGE_CHARS)
    size = D(IMAGE_CHARS)
    c.set_last_error(0)
    image_ok = kernel.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(size))
    error = c.get_last_error()
    image = buffer[:size.value] if image_ok and 0 < size.value < IMAGE_CHARS else None
    calls.append(dict(api='QueryFullProcessImageNameW',
                      inputs=dict(handle=handle, flags=0, capacity_characters=IMAGE_CHARS),
                      returned=image_ok, returned_size_characters=size.value,
                      image=image, last_error=error))
    creation, exit_time, kernel_time, user_time = FT(), FT(), FT(), FT()
    c.set_last_error(0)
    times_ok = kernel.GetProcessTimes(handle, c.byref(creation), c.byref(exit_time),
                                      c.byref(kernel_time), c.byref(user_time))
    error = c.get_last_error()

    def ft(value):
        return dict(low=value.low, high=value.high, uint64=(value.high << 32) | value.low)

    raw_times = dict(creation=ft(creation), exit=ft(exit_time), kernel=ft(kernel_time), user=ft(user_time))
    calls.append(dict(api='GetProcessTimes', inputs=dict(handle=handle, output_fields=list(raw_times)),
                      returned=times_ok, last_error=error, raw_FILETIME=raw_times,
                      exit_time_defined=False, exit_time_note='not evidence of exit; original Wait is separate'))
    reasons = []
    if not pid:
        reasons.append('GetProcessId_failed')
    if not image_ok or image is None:
        reasons.append('QueryFullProcessImageNameW_failed_or_bounded_capacity')
    if not times_ok:
        reasons.append('GetProcessTimes_failed')
    return dict(origin=origin, capturing_self_pid=os.getpid(), original_handle=handle, pid=pid, image=image,
                creation_FILETIME=ft(creation) if times_ok else None, creation_unit='100ns_UTC_since_1601',
                complete=not reasons, unknown_reasons=reasons, calls=calls)


def capture_current():
    require_root()
    pid = os.getpid()
    native = capture_original_handle(None, 'current_self_pseudo')
    if not native['complete'] or pid != native['pid']:
        raise IdentityError('self_native_mismatch')
    return dict(self_pid=pid, runtime=_runtime(), native=native)


def _wire_identity(identity):
    # Include raw self calls in the bounded original channel as well. Long paths
    # may exhaust the line cap: that is a failure, never truncation or omission.
    return dict(self_pid=identity['self_pid'], runtime=identity['runtime'],
                native=identity['native'])


def _validate_native_calls(native):
    """Validate self-reported raw data, never authenticate its physical writer."""
    def fields(value, expected):
        if type(value) is not dict or set(value) != expected:
            raise IdentityError('identity_raw_call_fields')

    def integer(value, low, high):
        if type(value) is not int or not low <= value < high:
            raise IdentityError('identity_raw_call_integer')

    def filetime(value):
        fields(value, {'low', 'high', 'uint64'})
        integer(value['low'], 0, 2**32)
        integer(value['high'], 0, 2**32)
        integer(value['uint64'], 0, 2**64)
        if value['uint64'] != (value['high'] << 32) | value['low']:
            raise IdentityError('identity_raw_FILETIME')

    handle, pid = native['original_handle'], native['pid']
    integer(handle, 1, 2**64)
    integer(pid, 1, 2**32)
    image = _text(native['image'], IMAGE_CHARS - 1)
    calls = native['calls']
    names = ['GetCurrentProcess', 'GetProcessId', 'QueryFullProcessImageNameW', 'GetProcessTimes']
    extras = [set(), set(), {'returned_size_characters', 'image'},
              {'raw_FILETIME', 'exit_time_defined', 'exit_time_note'}]
    if type(calls) is not list or len(calls) != 4:
        raise IdentityError('identity_raw_call_count')
    for row, name, extra in zip(calls, names, extras):
        fields(row, {'api', 'inputs', 'returned', 'last_error'} | extra)
        if row['api'] != name:
            raise IdentityError('identity_raw_call_order')
        # Keep the original signed/unsigned 32-bit integer representation.
        # LastError does not override a successful documented API return.
        integer(row['last_error'], -(2**31), 2**32)
    fields(calls[0]['inputs'], set())
    integer(calls[0]['returned'], 1, 2**64)
    if calls[0]['returned'] != handle:
        raise IdentityError('identity_raw_pseudo_HANDLE')
    for row in calls[1:]:
        required = ({'handle', 'flags', 'capacity_characters'} if row['api'] == names[2]
                    else {'handle', 'output_fields'} if row['api'] == names[3] else {'handle'})
        fields(row['inputs'], required)
        integer(row['inputs']['handle'], 1, 2**64)
        if row['inputs']['handle'] != handle:
            raise IdentityError('identity_raw_input_HANDLE')
    integer(calls[1]['returned'], 1, 2**32)
    if calls[1]['returned'] != pid:
        raise IdentityError('identity_raw_PID')
    for row in calls[2:]:
        integer(row['returned'], -(2**31), 2**31)
        if row['returned'] == 0:
            raise IdentityError('identity_raw_failed_BOOL')
    query = calls[2]
    integer(query['inputs']['flags'], 0, 1)
    integer(query['inputs']['capacity_characters'], IMAGE_CHARS, IMAGE_CHARS + 1)
    integer(query['returned_size_characters'], 1, IMAGE_CHARS)
    # Windows WCHAR counts UTF-16 code units, excluding the terminating NUL.
    if (type(query['image']) is not str or query['image'] != image
            or query['returned_size_characters'] != len(image.encode('utf-16-le', 'surrogatepass')) // 2):
        raise IdentityError('identity_raw_image_output')
    times = calls[3]
    if times['inputs']['output_fields'] != ['creation', 'exit', 'kernel', 'user']:
        raise IdentityError('identity_raw_time_outputs')
    fields(times['raw_FILETIME'], {'creation', 'exit', 'kernel', 'user'})
    for value in times['raw_FILETIME'].values():
        filetime(value)
    if (times['raw_FILETIME']['creation'] != native['creation_FILETIME']
            or times['exit_time_defined'] is not False
            or times['exit_time_note'] != 'not evidence of exit; original Wait is separate'):
        raise IdentityError('identity_raw_time_consistency')


def emit_current(*, role, case):
    root = require_root()
    if role not in ('observer', 'primary', 'owned-residual') or case not in ('batch', 'normal', 'owned-residual'):
        raise IdentityError('identity_role')
    nonce = root['nonce']
    if type(nonce) is not str or re.fullmatch('[0-9a-f]{32}', nonce) is None:
        raise IdentityError('nonce')
    identity = capture_current()
    row = dict(schema=SCHEMA, nonce=nonce, role=role, case=case, identity=_wire_identity(identity))
    raw = PREFIX + json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(',', ':'),
                              allow_nan=False).encode('ascii') + b'\n'
    if len(raw) > LINE_CAP:
        raise IdentityError('identity_line_bound')
    returned = sys.stdout.buffer.write(raw)
    if type(returned) is not int or returned != len(raw):
        raise IdentityError('identity_write_unknown')
    sys.stdout.buffer.flush()
    return dict(identity=identity, line_bytes=len(raw), line_sha256=hashlib.sha256(raw).hexdigest(),
                channel='original stdout; actor pipe or outer Popen file as configured')


def _match_line(line, original, *, role, case):
    root = require_root()
    if type(line) is not bytes or len(line) > LINE_CAP or not line.startswith(PREFIX) or not line.endswith(b'\n'):
        raise IdentityError('identity_line_shape')
    row = _decode(line[len(PREFIX):-1])
    if type(row) is not dict or set(row) != {'schema', 'nonce', 'role', 'case', 'identity'}:
        raise IdentityError('identity_schema')
    if row['schema'] != SCHEMA or row['nonce'] != root['nonce'] or row['role'] != role or row['case'] != case:
        raise IdentityError('identity_correlation')
    value = row['identity']
    if type(value) is not dict or set(value) != {'self_pid', 'runtime', 'native'}:
        raise IdentityError('identity_fields')
    native = value['native']
    if type(native) is not dict or set(native) != {'origin', 'capturing_self_pid', 'original_handle', 'pid', 'image',
                                                'creation_FILETIME', 'creation_unit', 'complete', 'unknown_reasons', 'calls'}:
        raise IdentityError('identity_native_fields')
    if (native['origin'] != 'current_self_pseudo' or native['creation_unit'] != '100ns_UTC_since_1601'
            or type(native['original_handle']) is not int or type(native['calls']) is not list
            or native['unknown_reasons'] != [] or type(native['capturing_self_pid']) is not int
            or native['capturing_self_pid'] != native['pid']
            or len(native['calls']) != 4
            or [call.get('api') for call in native['calls'] if type(call) is dict] !=
               ['GetCurrentProcess', 'GetProcessId', 'QueryFullProcessImageNameW', 'GetProcessTimes']):
        raise IdentityError('identity_native_raw_calls')
    creation = native['creation_FILETIME']
    if (type(creation) is not dict or set(creation) != {'low', 'high', 'uint64'}
            or any(type(creation[k]) is not int for k in creation)
            or not 0 <= creation['low'] < 2**32 or not 0 <= creation['high'] < 2**32
            or creation['uint64'] != (creation['high'] << 32) | creation['low']):
        raise IdentityError('identity_FILETIME')
    if (not original['complete'] or native['complete'] is not True
            or type(value['self_pid']) is not int or type(native['pid']) is not int
            or value['self_pid'] != original['pid'] or native['pid'] != original['pid']
            or native['image'] != original['image'] or creation != original['creation_FILETIME']):
        raise IdentityError('identity_original_HANDLE_mismatch')
    _validate_native_calls(native)
    runtime = value['runtime']
    if type(runtime) is not dict or set(runtime) != {'executable', 'base_executable', 'prefix', 'base_prefix', 'version', 'flags', 'missing'}:
        raise IdentityError('identity_runtime_fields')
    for key in ('executable', 'prefix', 'base_prefix'):
        _text(runtime[key], 512)
    if runtime['base_executable'] is not None:
        _text(runtime['base_executable'], 512)
    _version(runtime['version'])
    flags = runtime['flags']
    if type(flags) is not dict or set(flags) != set(FLAG_NAMES) or any(type(v) not in (int, bool, type(None)) for v in flags.values()):
        raise IdentityError('identity_flags')
    expected_missing = {name: 'attribute_unavailable' for name, value in flags.items() if value is None}
    if runtime['base_executable'] is None:
        expected_missing['base_executable'] = 'attribute_unavailable'
    if runtime['missing'] != expected_missing:
        raise IdentityError('identity_missing_reasons')
    return dict(matched=True, identity=row, line_bytes=len(line), line_sha256=hashlib.sha256(line).hexdigest(),
                ownership_created=False, byte_writer_or_ancestry_proven=False)


def actor_stream(raw, original, *, role, case):
    require_root()
    if type(raw) is not bytes or len(raw) > ACTOR_CAP or role not in FIXED:
        raise IdentityError('actor_stream_bound')
    split = raw.find(b'\n')
    if split < 0 or raw[split+1:] != FIXED[role]:
        raise IdentityError('actor_original_line_missing_or_extra')
    return _match_line(raw[:split+1], original, role=role, case=case)


def actor_ready(raw, original, *, role, case):
    try:
        actor_stream(raw, original, role=role, case=case)
        return True
    except IdentityError:
        return False


def observer_channel(path, original):
    """Original Popen stdout FILE, not a pipe and not writer provenance."""
    require_root()
    raw = _read(path, OUTER_STDOUT_CAP)
    lines = raw.splitlines(keepends=True)
    if len(lines) != 2 or len(lines[1]) > 4096 or not lines[1].endswith(b'\n'):
        raise IdentityError('outer_original_file_shape')
    matched = _match_line(lines[0], original, role='observer', case='batch')
    summary = _decode(lines[1])
    if type(summary) is not dict:
        raise IdentityError('outer_summary_type')
    return dict(**matched, channel='original Popen stdout file', original_stdout_bytes=len(raw),
                original_stdout_sha256=hashlib.sha256(raw).hexdigest(), driver_summary=summary)

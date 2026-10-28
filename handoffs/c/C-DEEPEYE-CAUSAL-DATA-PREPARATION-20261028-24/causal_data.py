"""C24 bounded offline CANDIDATE data preparation, Python stdlib only.

No package/model/physical conversion/provider/online interface is imported.
All declarations remain unapproved. See SCHEMA.md for exact native semantics.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

ALGORITHM = 'population_native_components_v1'
MAX_TIME = (1 << 63) - 1
MAX_SEQUENCE = (1 << 64) - 1
MAX_OUTPUT = 131072
_SEAL = object()
_PROFILES = {
    'hardware_raw_code_candidate_v1': ('hardware_raw_code', 'real', 'count'),
    'full_voltage_candidate_v1': ('full_induced_voltage', 'complex', 'V'),
    'born_derivative_candidate_v1': ('born_derivative', 'complex', None),
    'logrho_candidate_v1': ('candidate_logrho', 'real', None),
    'vibration_candidate_v1': ('candidate_vibration', 'real', None),
    'definition_real_v1': ('definition_scalar', 'real', 'definition_unit'),
    'definition_complex_v1': ('definition_complex', 'complex', 'definition_unit'),
}
_RECORD_FIELDS = {'schema_version', 'run_id', 'sequence', 'source_time_ns', 'clock_domain', 'profile_id', 'channels'}
_CHANNEL_FIELDS = {'channel_id', 'quantity_id', 'representation', 'unit', 'unit_reason', 'calibration_id',
                   'value', 'reason', 'valid', 'held', 'fault', 'saturated', 'native_sequence',
                   'native_time_ns', 'native_reason', 'native_ref'}
_PROVENANCE_FIELDS = {'schema_version', 'record_sha256', 'source_id', 'source_kind', 'native_profile_id',
                      'delivery_index', 'channel_bindings', 'clock_context'}
_CLOCK_FIELDS = {'boot_id', 'boot_reason', 'clock_mapping_id', 'clock_error_ns', 'clock_reason',
                 'own_odometry_history_ref', 'history_reason'}
_BINDING_FIELDS = {'channel_id', 'quantity_id', 'representation', 'unit', 'unit_reason', 'calibration'}


class DataError(ValueError):
    """Fixed bounded code only; never echoes records, paths or raw exceptions."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _fail(code='schema_invalid'):
    raise DataError(code)


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        _fail('bounds_invalid')
    return value


def _label(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}', value) is None:
        _fail('bounds_invalid')
    return value


def _reason(value):
    if type(value) is not str or not value:
        _fail()
    try:
        size = len(value.encode('utf-8'))
    except UnicodeError:
        _fail()
    if size > 192:
        _fail('bounds_invalid')
    return value


def _nullable_label(value, reason):
    if value is None:
        _reason(reason)
    else:
        _label(value)
        if reason is not None:
            _fail()


def _sha(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        _fail()
    return value


def _fields(value, expected):
    if type(value) is not dict or value.keys() != expected:
        _fail()
    return value


def _version(doc):
    if type(doc['schema_version']) is not int or doc['schema_version'] != 1:
        _fail()


def _boolean(value):
    if type(value) is not bool:
        _fail()


def _number(value):
    if type(value) not in (int, float):
        _fail()
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        _fail('bounds_invalid')
    if not math.isfinite(converted) or abs(converted) > 1e100:
        _fail('bounds_invalid')
    if type(value) is int and converted != value:
        _fail('bounds_invalid')
    return value  # retain original native semantic number; do not impute/coerce


def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                          separators=(',', ':')).encode('ascii')
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
        _fail()


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def _nonfinite(_value):
    _fail()


def _json(raw):
    if type(raw) is not bytes:
        _fail()
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_nonfinite)
    except DataError:
        raise
    except (UnicodeError, ValueError, TypeError, RecursionError, OverflowError):
        _fail()


def _report(status='candidate'):
    return dict(schema_version=1, format_valid=True, candidate_only=True,
                approved_training_data=False, status=status)


def _output(value):
    if len(_canonical(value)) + 1 > MAX_OUTPUT:
        _fail('bounds_invalid')
    return value


def _path(value):
    if type(value) not in (str, type(Path())):
        _fail('path_invalid')
    if type(value) is str and (not value or len(value) > 4096 or '\0' in value):
        _fail('path_invalid')
    try:
        return Path(os.path.abspath(value))
    except (ValueError, OSError):
        _fail('path_invalid')


def _safe_stat(path, *, directory=False):
    """Reject links/reparse points in every component before bounded reads."""
    try:
        for component in reversed((path,) + tuple(path.parents)):
            info = component.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
                _fail('path_invalid')
            if component != path and not stat.S_ISDIR(info.st_mode):
                _fail('path_invalid')
        if directory:
            if not stat.S_ISDIR(info.st_mode):
                _fail('path_invalid')
        elif not stat.S_ISREG(info.st_mode):
            _fail('path_invalid')
        return info
    except (OSError, ValueError):
        _fail('path_invalid')


def _read(path, expected, cap):
    _sha(expected)
    info = _safe_stat(path)
    if info.st_size > cap:
        _fail('bounds_invalid')
    try:
        with path.open('rb') as stream:
            raw = stream.read(cap + 1)
    except (OSError, ValueError):
        _fail('path_invalid')
    if len(raw) > cap:
        _fail('bounds_invalid')
    if _digest(raw) != expected:
        _fail('hash_mismatch')
    return raw


def _reference(root, reference, role):
    _fields(reference, {'path', 'sha256'})
    name = reference['path']
    if type(name) is not str or re.fullmatch(role + r'/[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.json', name) is None:
        _fail('path_invalid')
    _sha(reference['sha256'])
    path = root / name
    _safe_stat(path)
    try:
        if not path.resolve(strict=True).is_relative_to(root):
            _fail('path_invalid')
    except OSError:
        _fail('path_invalid')
    return path


def _clock(doc):
    _fields(doc, _CLOCK_FIELDS)
    _nullable_label(doc['boot_id'], doc['boot_reason'])
    _nullable_label(doc['own_odometry_history_ref'], doc['history_reason'])
    mapping, error = doc['clock_mapping_id'], doc['clock_error_ns']
    if mapping is None or error is None:
        if mapping is not None or error is not None:
            _fail()
        _reason(doc['clock_reason'])
    else:
        _label(mapping)
        _integer(error, 0, MAX_TIME)
        if doc['clock_reason'] is not None:
            _fail()


def _record(doc):
    _fields(doc, _RECORD_FIELDS)
    _version(doc)
    for name in ('run_id', 'clock_domain', 'profile_id'):
        _label(doc[name])
    if doc['profile_id'] not in _PROFILES:
        _fail()
    _integer(doc['sequence'], 0, MAX_SEQUENCE)
    _integer(doc['source_time_ns'], 0, MAX_TIME)
    channels = doc['channels']
    if type(channels) is not list or not 1 <= len(channels) <= 16:
        _fail('bounds_invalid')
    names = set()
    for channel in channels:
        _fields(channel, _CHANNEL_FIELDS)
        name = _label(channel['channel_id'])
        if name in names:
            _fail()
        names.add(name)
        _label(channel['quantity_id'])
        _nullable_label(channel['unit'], channel['unit_reason'])
        if channel['calibration_id'] is not None:
            _label(channel['calibration_id'])
        quantity, representation, unit = _PROFILES[doc['profile_id']]
        if (channel['quantity_id'] != quantity or channel['representation'] != representation
                or (channel['unit'] is not None and channel['unit'] != unit)):
            _fail('binding_mismatch')
        value = channel['value']
        if value is None:
            _reason(channel['reason'])
        else:
            if channel['reason'] is not None:
                _fail()
            if representation == 'complex':
                _fields(value, {'real', 'imag'})
                _number(value['real'])
                _number(value['imag'])
            else:
                _number(value)
        for flag in ('valid', 'held', 'saturated'):
            _boolean(channel[flag])
        if channel['fault'] is not None:
            _reason(channel['fault'])
        sequence, time = channel['native_sequence'], channel['native_time_ns']
        if sequence is not None:
            _integer(sequence, 0, MAX_SEQUENCE)
        if time is not None:
            _integer(time, 0, MAX_TIME)
            if time > doc['source_time_ns']:
                _fail('future_sample')
        if sequence is None or time is None:
            _reason(channel['native_reason'])
        elif channel['native_reason'] is not None:
            _fail()
        reference = channel['native_ref']
        if channel['held']:
            if reference is None or sequence is None or time is None:
                _fail('held_mismatch')
            _fields(reference, {'record_sha256', 'channel_id'})
            _sha(reference['record_sha256'])
            _label(reference['channel_id'])
        elif reference is not None:
            _fail('held_mismatch')


def _provenance(doc, record, record_sha):
    _fields(doc, _PROVENANCE_FIELDS)
    _version(doc)
    _sha(doc['record_sha256'])
    if doc['record_sha256'] != record_sha:
        _fail('hash_mismatch')
    _label(doc['source_id'])
    if doc['source_kind'] not in ('synthetic_definition', 'twin_fixture', 'hardware_unqualified', 'offline_unqualified'):
        _fail()
    if doc['native_profile_id'] != record['profile_id']:
        _fail('binding_mismatch')
    _integer(doc['delivery_index'], 1, (1 << 31) - 1)
    _clock(doc['clock_context'])
    bindings = doc['channel_bindings']
    if type(bindings) is not list or len(bindings) != len(record['channels']):
        _fail()
    synthetic = record['profile_id'] in ('definition_real_v1', 'definition_complex_v1')
    for binding, channel in zip(bindings, record['channels']):
        _fields(binding, _BINDING_FIELDS)
        for name in ('channel_id', 'quantity_id', 'representation', 'unit', 'unit_reason'):
            if type(binding[name]) is not type(channel[name]) or binding[name] != channel[name]:
                _fail('binding_mismatch')
        calibration = _fields(binding['calibration'], {'state', 'id', 'reason'})
        if calibration['state'] not in ('unknown', 'declared', 'synthetic_definition'):
            _fail()
        _nullable_label(calibration['id'], calibration['reason'])
        if (calibration['state'] == 'unknown') != (calibration['id'] is None):
            _fail()
        if channel['calibration_id'] != calibration['id']:
            _fail('binding_mismatch')
        if synthetic:
            if doc['source_kind'] != 'synthetic_definition' or calibration['state'] != 'synthetic_definition':
                _fail('binding_mismatch')
        elif calibration['state'] == 'synthetic_definition':
            _fail('binding_mismatch')


def _group(doc, record_sha):
    _fields(doc, {'schema_version', 'record_sha256', 'scene_id', 'event_id', 'target'})
    _version(doc)
    _sha(doc['record_sha256'])
    if doc['record_sha256'] != record_sha:
        _fail('hash_mismatch')
    _label(doc['scene_id'])
    _label(doc['event_id'])
    target = _fields(doc['target'], {'definition_id', 'label', 'reason'})
    _label(target['definition_id'])
    if target['label'] is None:
        _reason(target['reason'])
    else:
        if target['reason'] is not None:
            _fail()
        if type(target['label']) is str:
            _label(target['label'])
        else:
            _number(target['label'])


class Catalog:
    """Immutable verified byte snapshot, not caller-asserted approval."""
    __slots__ = ('_snapshot', '_catalog_sha256')

    def __init__(self, seal, rows, sha):
        if seal is not _SEAL:
            _fail()
        object.__setattr__(self, '_snapshot', tuple(_canonical(row) for row in rows))
        object.__setattr__(self, '_catalog_sha256', sha)

    def __setattr__(self, _name, _value):
        raise AttributeError('immutable candidate catalog')

    @property
    def catalog_sha256(self):
        return self._catalog_sha256

    @property
    def entry_count(self):
        return len(self._snapshot)


def _rows(catalog):
    if type(catalog) is not Catalog:
        _fail()
    return [_json(raw) for raw in catalog._snapshot]


def load_catalog(root, expected_catalog_sha256):
    root = _path(root)
    _safe_stat(root, directory=True)
    try:
        root = root.resolve(strict=True)
    except OSError:
        _fail('path_invalid')
    raw = _read(root / 'catalog.json', expected_catalog_sha256, 65536)
    doc = _fields(_json(raw), {'schema_version', 'entries'})
    _version(doc)
    entries = doc['entries']
    if type(entries) is not list or not 1 <= len(entries) <= 128:
        _fail('bounds_invalid')
    total, cache, rows, ids = len(raw), {}, [], set()
    for entry in entries:
        _fields(entry, {'sample_id', 'split', 'record', 'provenance', 'group'})
        sample_id = _label(entry['sample_id'])
        if sample_id in ids:
            _fail()
        ids.add(sample_id)
        if entry['split'] not in ('train', 'validation', 'test'):
            _fail()
        row = dict(sample_id=sample_id, split=entry['split'])
        for name, role in (('record', 'records'), ('provenance', 'provenance'), ('group', 'groups')):
            reference = entry[name]
            path = _reference(root, reference, role)
            if reference['path'] not in cache:
                data = _read(path, reference['sha256'], 16384)
                total += len(data)
                if total > 8388608:
                    _fail('bounds_invalid')
                cache[reference['path']] = data
            data = cache[reference['path']]
            if _digest(data) != reference['sha256']:
                _fail('hash_mismatch')
            row[name], row[name + '_sha256'] = _json(data), reference['sha256']
        _record(row['record'])
        _provenance(row['provenance'], row['record'], row['record_sha256'])
        _group(row['group'], row['record_sha256'])
        rows.append(row)
    _analyze(rows)
    return Catalog(_SEAL, rows, _digest(raw))


def _stream(row):
    record, provenance = row['record'], row['provenance']
    return provenance['source_id'], record['run_id'], record['clock_domain']


def _binding(row, index):
    provenance, record = row['provenance'], row['record']
    native = provenance['channel_bindings'][index]
    return dict(source_id=provenance['source_id'], source_kind=provenance['source_kind'],
                profile_id=record['profile_id'], channel_id=native['channel_id'],
                quantity_id=native['quantity_id'], representation=native['representation'],
                unit=native['unit'], unit_reason=native['unit_reason'], calibration=native['calibration'])


def _native(row, index):
    channel = row['record']['channels'][index]
    if channel['native_sequence'] is None:
        return None
    return _stream(row) + (channel['channel_id'], channel['native_sequence'])


def _key_document(key):
    if key is None:
        return None
    return dict(zip(('source_id', 'run_id', 'clock_domain', 'channel_id', 'native_sequence'), key))


def _native_signature(row, index):
    channel = row['record']['channels'][index]
    return _canonical(dict(binding=_binding(row, index), native_time_ns=channel['native_time_ns'],
                           native_reason=channel['native_reason'], value=channel['value'],
                           valid=channel['valid'], fault=channel['fault'], saturated=channel['saturated']))


def _analyze(rows):
    """Finite native/link/order validation and transitive split connectivity."""
    ordered = sorted(range(len(rows)), key=lambda i: (_stream(rows[i]), rows[i]['provenance']['delivery_index']))
    streams, native_signatures, owners, native_latest = {}, {}, {}, {}
    by_hash = {}
    for i, row in enumerate(rows):
        by_hash.setdefault(row['record_sha256'], []).append(i)
    # First validate held against the original *hash-linked* record, not a
    # timestamp supplied twice in a newly rehashed held wrapper.
    for i in ordered:
        row, record, provenance = rows[i], rows[i]['record'], rows[i]['provenance']
        stream = _stream(row)
        binding = _canonical([_binding(row, j) for j in range(len(record['channels']))])
        previous = streams.get(stream)
        if previous is not None:
            old = rows[previous]
            if binding != _canonical([_binding(old, j) for j in range(len(old['record']['channels']))]):
                _fail('binding_mismatch')
            if (provenance['delivery_index'] <= old['provenance']['delivery_index']
                    or record['source_time_ns'] < old['record']['source_time_ns']
                    or record['sequence'] < old['record']['sequence']):
                _fail('sequence_regression')
            if record['sequence'] == old['record']['sequence'] and row['record_sha256'] != old['record_sha256']:
                _fail('sequence_regression')
        streams[stream] = i
        for j, channel in enumerate(record['channels']):
            key = _native(row, j)
            signature = _native_signature(row, j)
            if channel['held']:
                reference = channel['native_ref']
                originals = []
                for original_i in by_hash.get(reference['record_sha256'], ()):
                    original = rows[original_i]
                    if (_stream(original) != stream
                            or original['provenance']['delivery_index'] >= provenance['delivery_index']
                            or original['record']['source_time_ns'] > record['source_time_ns']):
                        continue
                    for original_j, original_channel in enumerate(original['record']['channels']):
                        if (original_channel['channel_id'] == reference['channel_id']
                                and original_channel['channel_id'] == channel['channel_id']
                                and not original_channel['held']
                                and original_channel['native_time_ns'] is not None
                                and _native(original, original_j) == key
                                and _native_signature(original, original_j) == signature):
                            originals.append(original_i)
                if not originals:
                    _fail('held_mismatch')
            if key is not None:
                if key in native_signatures and native_signatures[key] != signature:
                    _fail('native_conflict')
                native_signatures[key] = signature
                owners.setdefault(key, (i, j))  # sorted minimum delivery_index
                if not channel['held']:
                    channel_key = key[:-1]
                    if channel_key in native_latest and key[-1] < native_latest[channel_key]:
                        _fail('sequence_regression')
                    native_latest[channel_key] = key[-1]

    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i, j):
        parent[find(i)] = find(j)
    first = {}
    for i, row in enumerate(rows):
        identities = [('scene', row['group']['scene_id']), ('event', row['group']['event_id']),
                      ('original_record', row['record_sha256'])]
        identities.extend(('native', _native(row, j)) for j in range(len(row['record']['channels']))
                          if _native(row, j) is not None)
        for identity in identities:
            if identity in first:
                union(i, first[identity])
            else:
                first[identity] = i
    splits = {}
    for i, row in enumerate(rows):
        component = find(i)
        if component in splits and splits[component] != row['split']:
            _fail('split_leakage')
        splits[component] = row['split']
    return owners, len(splits)


def check_splits(catalog):
    rows = _rows(catalog)
    _owners, components = _analyze(rows)
    result = _report()
    result.update(entry_count=len(rows), component_count=components,
                  split_counts={split: sum(row['split'] == split for row in rows)
                                for split in ('train', 'validation', 'test')},
                  full_catalog_sha256=catalog.catalog_sha256)
    return _output(result)


def _reasons(row, index, owners, row_index, *, cutoff=None, max_age=None):
    channel = row['record']['channels'][index]
    binding = _binding(row, index)
    key = _native(row, index)
    reasons = []
    if channel['value'] is None:
        reasons.append('missing_value')
    if not channel['valid']:
        reasons.append('invalid')
    if channel['held']:
        reasons.append('held')
    if channel['fault'] is not None:
        reasons.append('fault')
    if channel['saturated']:
        reasons.append('saturated')
    if key is None or channel['native_time_ns'] is None:
        reasons.append('native_unknown')
    if binding['unit'] is None:
        reasons.append('unit_unknown')
    if binding['calibration']['state'] == 'unknown':
        reasons.append('calibration_unknown')
    if key is not None and owners[key] != (row_index, index):
        reasons.append('duplicate_native')
    if cutoff is not None and channel['native_time_ns'] is not None and cutoff - channel['native_time_ns'] > max_age:
        reasons.append('stale')
    return reasons


def fit_scaler(catalog):
    rows = _rows(catalog)
    owners, _components = _analyze(rows)
    training = sorted((i for i, row in enumerate(rows) if row['split'] == 'train'),
                      key=lambda i: rows[i]['sample_id'])
    manifest_entries, bindings, values, contributors = [], {}, {}, []
    for i in training:
        row = rows[i]
        row_bindings = [_binding(row, j) for j in range(len(row['record']['channels']))]
        manifest_entries.append(dict(sample_id=row['sample_id'], record_sha256=row['record_sha256'],
                                     provenance_sha256=row['provenance_sha256'], group_sha256=row['group_sha256'],
                                     bindings=row_bindings))
        for j, binding in enumerate(row_bindings):
            digest = _digest(_canonical(binding))
            bindings[digest] = binding
            components = ('real', 'imag') if binding['representation'] == 'complex' else ('value',)
            for component in components:
                values.setdefault((digest, component), [])
            if _reasons(row, j, owners, i):
                continue
            channel = row['record']['channels'][j]
            raw = channel['value']
            native_values = dict(real=raw['real'], imag=raw['imag']) if binding['representation'] == 'complex' else dict(value=raw)
            contributors.append(dict(native_key=_key_document(_native(row, j)), binding_sha256=digest,
                                     record_sha256=row['record_sha256'], provenance_sha256=row['provenance_sha256'],
                                     group_sha256=row['group_sha256'], components=native_values))
    # Numeric order depends only on immutable training contribution identity.
    contributors.sort(key=_canonical)
    for contribution in contributors:
        for component, value in contribution['components'].items():
            values[(contribution['binding_sha256'], component)].append(value)
    manifest = dict(schema_version=1, algorithm=ALGORITHM, entries=manifest_entries)
    statistics = []
    for (digest, component), samples in sorted(values.items()):
        binding = bindings[digest]
        reason, mean, scale = None, None, None
        if binding['unit'] is None:
            reason = 'unit_unknown'
        elif binding['calibration']['state'] == 'unknown':
            reason = 'calibration_unknown'
        elif len(samples) < 2:
            reason = 'insufficient_samples'
        else:
            try:
                candidate_mean = math.fsum(samples) / len(samples)
                variance = math.fsum((value - candidate_mean) ** 2 for value in samples) / len(samples)
                candidate_scale = math.sqrt(variance)
            except (ValueError, OverflowError):
                _fail('bounds_invalid')
            if not all(math.isfinite(number) for number in (candidate_mean, variance, candidate_scale)):
                _fail('bounds_invalid')
            if candidate_scale == 0:
                reason = 'constant_values'
            else:
                mean, scale = candidate_mean, candidate_scale
        statistics.append(dict(binding_sha256=digest, binding=binding, component=component,
                               count=len(samples), mean=mean, scale=scale, reason=reason))
    result = _report('blocked' if not statistics or any(item['reason'] is not None for item in statistics) else 'candidate')
    result.update(algorithm=ALGORITHM, full_catalog_sha256=catalog.catalog_sha256,
                  training_manifest=manifest, training_manifest_sha256=_digest(_canonical(manifest)),
                  contributors=contributors, statistics=statistics)
    return _output(result)


def _plain(value, depth=0, counter=None):
    """Reject callback/subclass/NaN/alias-shaped external scaler structures."""
    if counter is None:
        counter = [0]
    counter[0] += 1
    if depth > 20 or counter[0] > 32768:
        _fail('scaler_mismatch')
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        # A contribution can contain a large exactly representable native
        # integer; uint64 identity fields need not be float-representable.
        if value.bit_length() > 334 or abs(value) > 10 ** 100:
            _fail('scaler_mismatch')
    elif type(value) is float:
        if not math.isfinite(value) or abs(value) > 1e100:
            _fail('scaler_mismatch')
    elif type(value) is str:
        if len(value) > 4096:
            _fail('scaler_mismatch')
    elif type(value) is list:
        if len(value) > 4096:
            _fail('scaler_mismatch')
        for item in value:
            _plain(item, depth + 1, counter)
    elif type(value) is dict:
        if len(value) > 4096 or any(type(key) is not str for key in value):
            _fail('scaler_mismatch')
        for key, item in value.items():
            if len(key) > 192:
                _fail('scaler_mismatch')
            _plain(item, depth + 1, counter)
    else:
        _fail('scaler_mismatch')


def validate_scaler(catalog, scaler):
    expected = fit_scaler(catalog)
    _plain(scaler)
    if type(scaler) is not dict or len(_canonical(scaler)) > 131072 or _canonical(scaler) != _canonical(expected):
        _fail('scaler_mismatch')
    result = _report(expected['status'])
    result.update(scaler_valid=True, training_manifest_sha256=expected['training_manifest_sha256'],
                  full_catalog_sha256=catalog.catalog_sha256)
    return _output(result)


def make_window(catalog, sample_ids, *, cutoff_ns, max_age_ns):
    _integer(cutoff_ns, 0, MAX_TIME)
    _integer(max_age_ns, 0, MAX_TIME)
    if type(sample_ids) not in (list, tuple) or not 1 <= len(sample_ids) <= 128:
        _fail('bounds_invalid')
    for sample_id in sample_ids:
        _label(sample_id)
    if len(set(sample_ids)) != len(sample_ids):
        _fail('sequence_regression')
    rows = _rows(catalog)
    owners, _components = _analyze(rows)
    by_id = {row['sample_id']: i for i, row in enumerate(rows)}
    if any(sample_id not in by_id for sample_id in sample_ids):
        _fail()
    selected = [by_id[sample_id] for sample_id in sample_ids]
    stream, previous_index, features, metadata = None, 0, [], []
    for i in selected:
        row, record, provenance = rows[i], rows[i]['record'], rows[i]['provenance']
        if stream is not None and _stream(row) != stream:
            _fail('binding_mismatch')
        stream = _stream(row)
        if provenance['delivery_index'] <= previous_index:
            _fail('sequence_regression')
        previous_index = provenance['delivery_index']
        if record['source_time_ns'] > cutoff_ns:
            _fail('future_sample')
        feature_row, channel_meta = [], []
        for j, channel in enumerate(record['channels']):
            native_time = channel['native_time_ns']
            if native_time is not None and native_time > cutoff_ns:
                _fail('future_sample')
            reasons = _reasons(row, j, owners, i, cutoff=cutoff_ns, max_age=max_age_ns)
            feature_row.append(dict(raw_value=channel['value'], effective_mask=0 if reasons else 1,
                                    status_reasons=reasons))
            channel_meta.append(dict(binding=_binding(row, j), native_key=_key_document(_native(row, j)),
                                     native_time_ns=native_time, native_ref=channel['native_ref'],
                                     age_ns=None if native_time is None else cutoff_ns-native_time,
                                     valid=channel['valid'], held=channel['held'], fault=channel['fault'],
                                     saturated=channel['saturated']))
        features.append(feature_row)
        metadata.append(dict(run_id=record['run_id'], sequence=record['sequence'],
                             source_time_ns=record['source_time_ns'], clock_domain=record['clock_domain'],
                             delivery_index=provenance['delivery_index'], profile_id=record['profile_id'],
                             clock_context=provenance['clock_context'], record_sha256=row['record_sha256'],
                             provenance_sha256=row['provenance_sha256'], channels=channel_meta))
    result = _report('blocked' if any(channel['effective_mask'] == 0 for row in features for channel in row) else 'candidate')
    result.update(features=features, causal_metadata=metadata, cutoff_ns=cutoff_ns, max_age_ns=max_age_ns)
    return _output(result)


def _extra_input(root, name, sha, cap):
    root = _path(root)
    _safe_stat(root, directory=True)
    root = root.resolve(strict=True)
    candidate = Path(name)
    path = _path(candidate if candidate.is_absolute() else root / candidate)
    # Explicit extra CLI inputs are contained root children, not model paths.
    if path.parent != root or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.json', path.name) is None:
        _fail('path_invalid')
    return _json(_read(path, sha, cap))


def main(argv=None):
    try:
        args = sys.argv[1:] if argv is None else argv
        if type(args) is not list or any(type(arg) is not str or len(arg) > 4096 for arg in args):
            _fail()
        if len(args) not in (3, 5):
            _fail()
        command, root, sha = args[:3]
        catalog = load_catalog(root, sha)
        if command == 'validate' and len(args) == 3:
            result = check_splits(catalog)
        elif command == 'fit' and len(args) == 3:
            result = fit_scaler(catalog)
        elif command == 'check-scaler' and len(args) == 5:
            result = validate_scaler(catalog, _extra_input(root, args[3], args[4], 131072))
        elif command == 'window' and len(args) == 5:
            selection = _fields(_extra_input(root, args[3], args[4], 16384), {'sample_ids', 'cutoff_ns', 'max_age_ns'})
            result = make_window(catalog, selection['sample_ids'], cutoff_ns=selection['cutoff_ns'], max_age_ns=selection['max_age_ns'])
        else:
            _fail()
        code = 0  # candidate/blocked are format-valid reports, never admission
    except DataError as error:
        result = dict(schema_version=1, format_valid=False, candidate_only=True,
                      approved_training_data=False, status='invalid', error=error.code)
        code = 2
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        result = dict(schema_version=1, format_valid=False, candidate_only=True,
                      approved_training_data=False, status='invalid', error='schema_invalid')
        code = 2
    # Exactly one small JSON report; no outputs, datasets or caches are written.
    sys.stdout.write(_canonical(_output(result)).decode('ascii') + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())

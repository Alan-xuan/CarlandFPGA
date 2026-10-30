"""Diagnostic for one exact retired source70 artifact, not a general adapter.

No I/O, clock, actor, frozen runtime or planner is used. A byte pin selects the
reviewed historical input; it authenticates neither an owner nor an action.
"""
import hashlib
import json

INPUT_BYTES = 82496
INPUT_SHA256 = '63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c'
SOURCE_COMMIT = '4dc91fd24531b3df53fc916e8b7f509ad524592c'
EXPORT_COMMIT = 'd0185d335747acb26439f40a8ce945f7f4eaa9af'
MAX_OUTPUT_BYTES = 65536
REJECTION = 'C33_RETIRED_INPUT_NOT_PINNED'
MISSING_CODES = (
    'retired_not_current',
    'original_book_owner_identity_missing',
    'original_em_scope_receipt_missing',
    'live_current_pose_capture_missing',
    'original_admission_capture_times_missing',
    'executed_action_receipts_missing',
    'actual_commit_point_missing',
    'verified_board_boot_missing',
)


class Rejected(ValueError):
    """The supplied bytes are not the single reviewed historical artifact."""


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf8')


def diagnose_retired(raw):
    """Return bounded historical facts and unavailable reasons for pinned bytes.

    All other inputs fail the type/length/SHA gate BEFORE parsing. No generic
    JSON/schema/temporal validator is exposed or claimed by this entry point.
    """
    if type(raw) is not bytes or len(raw) != INPUT_BYTES:
        raise Rejected(REJECTION)
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise Rejected(REJECTION)
    saved = json.loads(raw)
    book = saved['original_source_book']
    origin = saved['source_origin_qpc_ns']
    rows = []
    # These three parallel arrays are the exact pinned export's documented
    # association. Their position NEVER supplies an admission/capture identity.
    for record, sample, end in zip(saved['records'], book['samples'],
                                   saved['actual_record_end_qpc_ns']):
        rows.append(dict(
            source_count=sample['source_count'],
            adc_tick_ms=record['adc_tick_ms'],
            em_tick_ms=record['em_tick_ms'],
            nominal_qpc_ns=sample['nominal_qpc_ns'],
            actual_record_end_qpc_ns=end,
            source_sha256=sample['source_sha256'],
            channel_counts=record['channel_counts'],
            channel_values=record['channel_values'],
            quality=record['quality'],
            em_timestamp_mode=('fresh_source_timestamp' if record['em_tick_ms'] == record['adc_tick_ms']
                               else 'held_source_timestamp'),
            original_em_scope_association='unavailable',
            nominal_em_age_at_record_completion_ns=end-(origin+record['em_tick_ms']*1000000),
        ))
    result = dict(
        schema_version=1,
        diagnostic_kind='single_pinned_retired_source70_v2',
        input_sha256=INPUT_SHA256, input_bytes=len(raw),
        source_commit=saved['source_commit'], export_commit=EXPORT_COMMIT,
        original_operation_id=saved['original_operation_id'], book_schema=book['schema'],
        historical_only=True, compatibility='CURRENT_NOT_DIRECTLY_COMPATIBLE',
        input_status='INPUT_UNAVAILABLE', status='STOP', authorization='none',
        claim='numerical_immutable_committed_root_only', native_interval_atomic=False,
        projection=None, c30_called=False, c31_called=False, core_ran=False,
        missing_codes=list(MISSING_CODES), historical_rows=rows,
        historical_summary=dict(
            record_count=len(rows), source_origin_qpc_ns=origin,
            first_record_end_qpc_ns=rows[0]['actual_record_end_qpc_ns'],
            last_record_end_qpc_ns=rows[-1]['actual_record_end_qpc_ns'],
            fresh_source_timestamp_count=sum(r['em_timestamp_mode'] == 'fresh_source_timestamp' for r in rows),
            held_source_timestamp_count=sum(r['em_timestamp_mode'] == 'held_source_timestamp' for r in rows),
            null_c3_count=sum(r['channel_counts'][3] is None for r in rows),
            valid_zero_c3_count=sum(r['channel_counts'][3] == 0 and bool(r['quality'] & 8) for r in rows),
            missing_original_em_scope_count=len(rows),
            max_nominal_em_age_at_record_completion_ns=max(r['nominal_em_age_at_record_completion_ns'] for r in rows),
        ),
    )
    if len(_encoded(result)) > MAX_OUTPUT_BYTES:
        raise Rejected('C33_INTERNAL_OUTPUT_BUDGET')
    return result


def diagnose_json(raw):
    """Same single-input diagnostic, serialized to deterministic UTF8 JSON."""
    return _encoded(diagnose_retired(raw))


__all__ = ['diagnose_retired', 'diagnose_json', 'Rejected']

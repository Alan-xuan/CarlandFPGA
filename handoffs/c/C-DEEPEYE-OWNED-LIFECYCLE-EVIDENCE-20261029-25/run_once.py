"""Fixed C25 source/configuration guard and driver; this is not a service."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

OPERATION = 'C-DEEPEYE-OWNED-LIFECYCLE-EVIDENCE-20261029-25'
CASES = ['normal_primary_to_Job0', 'owned_residual_rejected_and_cleaned']
SOURCES = {'owned_lifecycle.py', 'case_actor.py', 'README.md', 'run_once.py'}
LIMITS = {'aggregate_wall_seconds': 30, 'observer_budget_seconds': 24,
          'process_commit_bytes': 536870912, 'job_commit_bytes': 1073741824,
          'total_output_bytes': 1048576, 'max_cases': 2, 'attempts_per_case': 1}
REPORT_CAP = 65536


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bounded(path: Path, cap: int) -> bytes:
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    if len(raw) > cap:
        raise ValueError(f'Bound exceeded: {path.name}')
    return raw


def write_json(path: Path, value: dict, cap: int = REPORT_CAP) -> None:
    raw = (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if len(raw) > cap:
        raise ValueError('Bounded evidence serialization exceeded its cap')
    with path.open('xb') as stream:
        stream.write(raw)


def source_identity(here: Path, expected: dict) -> dict:
    if set(expected) != SOURCES:
        raise ValueError('Exactly four new C25 source pins are required')
    observed = {}
    for name in sorted(SOURCES):
        raw = read_bounded(here/name, 98304)
        observed[name] = {'bytes': len(raw), 'sha256': digest(raw)}
    if observed != expected:
        raise ValueError('Frozen source bytes do not match')
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', type=Path, required=True)
    parser.add_argument('--configuration-sha256', required=True)
    args = parser.parse_args()
    started = time.monotonic()
    guard = None
    output = None
    report = None
    try:
        raw = read_bounded(args.configuration, 16384)
        if digest(raw) != args.configuration_sha256:
            raise ValueError('Original configuration hash mismatch')
        config = json.loads(raw)
        if set(config) != {'operation_id', 'task_id', 'task_version', 'base_python', 'base_sha256',
                           'source_pins', 'cases', 'limits', 'guard', 'output'}:
            raise ValueError('Unexpected configuration fields')
        if (config['operation_id'] != OPERATION or config['task_id'] != 'DEEPEYE-IMPLEMENTATION-20261014'
                or type(config['task_version']) is not int or config['task_version'] != 1
                or config['cases'] != CASES or config['limits'] != LIMITS):
            raise ValueError('Configuration changes the fixed operation or limits')
        here = Path(__file__).resolve().parent
        source_identity(here, config['source_pins'])
        base = Path(config['base_python']).resolve(strict=True)
        if (base != Path(sys.executable).resolve(strict=True)
                or digest(read_bounded(base, 1048576)) != config['base_sha256']):
            raise ValueError('Use the exact existing direct CPU base PE')
        output = Path(config['output']).resolve()
        guard = Path(config['guard']).resolve()
        if (output == here or here in output.parents or guard == here or here in guard.parents):
            raise ValueError('Raw outputs and fixed intent guard must be outside product source')
        output.mkdir(parents=True, exist_ok=False)
        guard.parent.mkdir(parents=True, exist_ok=True)
        write_json(guard, {'operation_id': OPERATION, 'configuration_sha256': args.configuration_sha256,
                          'state': 'consumed; no automatic retry or alternate guard for these cases',
                          'created_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
        write_json(output/'driver-intent.json', {'operation_id': OPERATION, 'configuration': config,
                                              'configuration_sha256': args.configuration_sha256,
                                              'original_argv': sys.argv, 'cases_started': 0})
        spec = importlib.util.spec_from_file_location('c25_owned_lifecycle', here/'owned_lifecycle.py')
        if spec is None or spec.loader is None:
            raise RuntimeError('Cannot load the pinned new observer source')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        observer_output = output/'observer-raw'
        observer_output.mkdir(exist_ok=False)
        report = module.run_batch(base_python=base, expected_base_sha256=config['base_sha256'],
                                  output=observer_output, expected_source_pins=config['source_pins'])
        write_json(output/'observer-result.json', report)
        source_identity(here, config['source_pins'])
        files = [p for p in output.rglob('*') if p.is_file()]
        existing_bytes = sum(p.stat().st_size for p in files)
        elapsed = time.monotonic()-started
        summary = {'operation_id': OPERATION, 'all_cases_passed': report['all_cases_passed'],
                   'observer_result_sha256': digest(read_bounded(output/'observer-result.json', REPORT_CAP)),
                   'source_bytes_unchanged': True, 'configuration_sha256': args.configuration_sha256,
                   'elapsed_through_driver_checkpoint_seconds': elapsed,
                   'elapsed_scope': 'driver entry through observer result/hash check; external original Popen measures complete command',
                   'raw_output_bytes_through_driver_checkpoint': existing_bytes,
                   'output_scope': 'raw directory through this checkpoint; supervisor later measures all final raw outputs',
                   'original_C24_unchanged_and_unaccepted': True, 'formal_acceptance': False}
        good = (report['all_cases_passed'] is True and elapsed <= 26 and existing_bytes <= 950000)
        summary['status'] = 'controls_passed' if good else 'failed'
        write_json(output/'driver-result.json', summary)
        print(json.dumps(summary, ensure_ascii=True, allow_nan=False))
        return 0 if good else 1
    except BaseException as exc:
        consumed = guard is not None and guard.exists()
        failure = {'operation_id': OPERATION, 'status': 'execution_or_evidence_unknown' if consumed else 'not_started',
                   'guard_consumed': consumed, 'may_have_run': consumed, 'definite_no_case': not consumed,
                   'error': {'type': type(exc).__name__, 'message': str(exc)[:500]}, 'no_retry': True,
                   'observer_result_available': report is not None}
        if output is not None and output.is_dir():
            try:
                write_json(output/'driver-failure.json', failure)
            except BaseException:
                pass
        print(json.dumps(failure, ensure_ascii=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

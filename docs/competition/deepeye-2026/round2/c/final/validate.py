"""Validate the C planning package; this does not simulate RTL or operate hardware."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check() -> dict:
    prior = json.loads((ROOT.parent / 'freeze_v2.json').read_text('utf-8'))
    for name, expected in prior['files'].items():
        assert sha(ROOT.parent / name) == expected, f'changed frozen input: {name}'
    tasks = json.loads((ROOT / 'tasks.json').read_text('utf-8'))
    cards = tasks['cards']
    by_id = {c['id']: c for c in cards}
    assert len(by_id) == len(cards) == 10
    done: set[str] = set()
    for c in cards:
        assert c['status'] == 'not_run'
        assert set(c['depends_on']) <= done, f'missing/cyclic/out-of-order dependency: {c}'
        assert all(by_id[d]['due'] <= c['due'] for d in c['depends_on'])
        assert c['acceptance_ref'] == 'TASKBOOK.md'
        done.add(c['id'])
    assert tasks['implementation_authorized_by_this_package'] is False
    assert tasks['board_operator'] == 'A'
    # Independently recompute line budget, rather than trusting a copied result.
    baud, bits, window, guard = 300, 10, 4, 0.2
    frame_overhead = sum([2, 1, 1, 1, 2, 2, 4, 1, 2])
    assert frame_overhead == 16
    summary, command, status, event = 32, 24, 24, 16
    normal = summary + command + status
    burst = normal + event
    usable_bytes = (window - guard) * baud / bits
    spare = usable_bytes - burst
    assert normal == 80 and burst == 96 and spare == 18
    assert event <= spare < command
    assert abs((burst * bits / baud + guard) / window - 0.85) < 1e-12
    # Reference CRC arithmetic only, not a test of any protocol implementation.
    crc = 0xFFFF
    for value in b'123456789':
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    assert crc == 0x29B1
    return {
        'result': 'passed_planning_checks_only',
        'prior_frozen_hashes_verified': len(prior['files']),
        'task_cards': len(cards),
        'dag_valid': True,
        'budget': {'baud': baud, 'bits_per_byte': bits, 'window_s': window,
                   'guard_s': guard, 'header_and_crc_bytes': frame_overhead,
                   'normal_bytes': normal, 'event_window_bytes': burst,
                   'normal_utilization': (normal * bits / baud + guard) / window,
                   'event_utilization': (burst * bits / baud + guard) / window,
                   'spare_bytes': spare, 'command_retry_fits': False,
                   'max_nonpreemptive_frame_s': summary * bits / baud},
        'crc_reference_check': 'CRC16_CCITT_FALSE_123456789_29B1',
        'rtl_simulation': 'not_run', 'synthesis': 'not_run',
        'implementation': 'not_run', 'board': 'not_run', 'npu': 'not_run',
    }


def local_links() -> int:
    count = 0
    for p in ROOT.glob('*.md'):
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', p.read_text('utf-8')):
            if '://' in link or link.startswith('#'):
                continue
            assert (p.parent / link.split('#')[0]).is_file(), f'broken link {p.name}: {link}'
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', action='store_true', help='write planning result and byte manifest')
    args = parser.parse_args()
    result = check()
    if args.seal:
        (ROOT / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        manifest = {
            'schema': 1, 'owner': 'C/Astra-C',
            'task_id': 'task-1a2875a7abef3ef5bcc824eb', 'task_version': 1791910536639,
            'work_id': 'C-independent-final-v1',
            'prior_freeze_sha256': sha(ROOT.parent / 'freeze_v2.json'),
            'scope': 'planning_only',
            'files': {p.name: sha(p) for p in sorted(ROOT.iterdir()) if p.is_file() and p.name != 'manifest.json'},
        }
        (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert json.loads((ROOT / 'validation.json').read_text('utf-8')) == result
    manifest = json.loads((ROOT / 'manifest.json').read_text('utf-8'))
    actual = {p.name for p in ROOT.iterdir() if p.is_file() and p.name != 'manifest.json'}
    assert set(manifest['files']) == actual
    for name, expected in manifest['files'].items():
        assert sha(ROOT / name) == expected, f'final hash mismatch: {name}'
    assert manifest['prior_freeze_sha256'] == sha(ROOT.parent / 'freeze_v2.json')
    result['local_links_checked'] = local_links()
    result['manifest_files_checked'] = len(manifest['files'])
    result['python'] = sys.version.split()[0]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

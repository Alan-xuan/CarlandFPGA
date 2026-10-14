"""Recompute research arithmetic and validate the review package, not product tests."""
import hashlib
import json
import math
from pathlib import Path

root = Path(__file__).resolve().parent
cards = json.loads((root / 'acceptance.json').read_text(encoding='utf-8'))
assert cards['task_version'] == 5
assert cards['all_product_checks_status'] == 'not_run'
assert [c['id'] for c in cards['cards']] == [f'C5-{i:02d}' for i in range(1, 11)]
for card in cards['cards']:
    assert all(card[k] for k in ('owner', 'dependencies', 'pass', 'evidence', 'failure_action'))
sources = json.loads((root / 'sources.json').read_text(encoding='utf-8'))
assert len(sources['sources']) == 11
assert all(s['kind'] == 'primary' and s['boundary'] for s in sources['sources'])

radius = 2.0
speed = 0.002
omega_deg_s = math.degrees(speed / radius)
old_lsb = 0.1
proposed_lsb = 0.001
assert omega_deg_s < old_lsb
legal_counts = [math.floor(math.degrees(code * 0.0001 / radius) / proposed_lsb)
                for code in range(1, 21)]
assert min(legal_counts) >= 1
assert 15 / proposed_lsb <= 32767

drill_r = 0.24 / 2
ring_r = 0.30 / 2
clearance = ring_r - drill_r
assert math.isclose(clearance, 0.03)
# Example ONLY: origin at the center and all geometry enclosed by this cylinder.
# Actual implementation must derive Rb from the complete model and true origin.
rb_centered = math.hypot(0.8 / 2, drill_r)
dt = 0.01
v = 0.25
omega = v / radius
motion_envelope_without_numeric_error = (v + rb_centered * omega) * dt
telem_end_ms = 35 + 32 * 10 / 9600 * 1000
compute_gap_ms = 210 - telem_end_ms
assert compute_gap_ms < 150

result = {
    'status': 'research_arithmetic_and_document_structure_pass',
    'not_product_validation': True,
    'reviewed_commit': '74c854d74baf817beafcbd1d4d52a8dd4450bbca',
    'stress_max_angular_deg_s': omega_deg_s,
    'old_lsb_deg_s': old_lsb,
    'old_nonzero_stress_turn_possible': False,
    'proposed_lsb_deg_s': proposed_lsb,
    'proposed_max_single_axis_legal_code_by_stress_speed_code_1_to_20': legal_counts,
    'proposed_abs_fullscale_code': round(15 / proposed_lsb),
    'ring_radial_clearance_m': clearance,
    'local_grid_to_radial_clearance_ratio': 0.25 / clearance,
    'example_centered_body_rb_m': rb_centered,
    'example_10ms_sweep_bound_m_excluding_numeric_error': motion_envelope_without_numeric_error,
    'fast_telem_end_ms': telem_end_ms,
    'fast_compute_gap_ms_before_usb_dispatch_packaging': compute_gap_ms,
    'card_count': len(cards['cards']),
    'primary_source_count': len(sources['sources']),
    'all_product_gates': 'not_run'
}
if (root / 'freeze_manifest.json').exists():
    manifest = json.loads((root / 'freeze_manifest.json').read_text(encoding='utf-8'))
    for filename, info in manifest['files'].items():
        data = (root / filename).read_bytes()
        assert len(data) == info['bytes'], filename
        assert hashlib.sha256(data).hexdigest() == info['sha256'], filename
    result['frozen_files_hashes_verified'] = True
print(json.dumps(result, ensure_ascii=False, indent=2))

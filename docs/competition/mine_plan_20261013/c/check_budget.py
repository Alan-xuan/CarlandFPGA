"""Verify design arithmetic only; this is not hardware measurement."""
import json
from pathlib import Path

def budget():
    baud = 300
    uart_bits = 10
    window_s = 8
    wire_bytes = baud / uart_bits * window_s
    acquisition_bps = 4 * 100 * 16
    summary_raw_bytes = 4 * 2 * 2 * window_s
    telemetry_payload = 90
    frame_overhead = 16
    max_payload = 48
    telemetry_frames = (telemetry_payload + max_payload - 1) // max_payload
    telemetry_wire = telemetry_payload + telemetry_frames * frame_overhead
    reserved_wire = 24 + 20 + 20
    turnaround_s = 0.2
    line_seconds = (telemetry_wire + reserved_wire) * uart_bits / baud + turnaround_s
    return {
        'status': 'design_arithmetic_verified',
        'assumptions': {'baud': baud, 'format': '8N1', 'half_duplex': True, 'window_seconds': window_s, 'turnaround_total_seconds': turnaround_s},
        'wire_bytes_per_window_without_guard': wire_bytes,
        'acquisition_bps': acquisition_bps,
        'all_raw_minimum_ratio_before_headers': acquisition_bps / (baud * 8 / uart_bits),
        'summary_raw_bytes_per_window': summary_raw_bytes,
        'telemetry_payload_budget_bytes': telemetry_payload,
        'required_payload_ratio_for_2hz_summary': summary_raw_bytes / telemetry_payload,
        'nominal_airtime_seconds_with_guard': line_seconds,
        'nominal_occupancy': line_seconds / window_s,
        'max_frame_airtime_seconds': 64 * uart_bits / baud,
        'nominal_alarm_worst_serialization_seconds': (64 + 20) * uart_bits / baud + turnaround_s,
        'buffer_seconds_if_1mib_raw_4ch_100hz': 2**20 / (acquisition_bps / 8),
        'assertions': ['all transmission, retransmission and turnaround must enter measurement', 'adaptive 1Hz fallback is mandatory for incompressible summaries', 'no microsecond end-to-end claims at 300baud'],
    }

if __name__ == '__main__':
    data = budget()
    assert abs(data['nominal_occupancy'] - .8) < 1e-9
    assert data['summary_raw_bytes_per_window'] == 128
    assert abs(data['nominal_alarm_worst_serialization_seconds'] - 3) < 1e-9
    Path(__file__).with_name('budget_result.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(data, ensure_ascii=False))

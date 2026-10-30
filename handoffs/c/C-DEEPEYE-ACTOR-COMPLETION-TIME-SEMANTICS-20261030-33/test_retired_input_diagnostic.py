"""NEW single-artifact controls, no old suite or actual source/model replay."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('c33_retired_diagnostic', HERE/'retired_input_diagnostic.py')
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)
RAW = (HERE/'retired-source70.json').read_bytes()


class RetiredSource70(unittest.TestCase):
    def test_01_exact_historical_facts_and_no_projection(self):
        self.assertEqual(len(RAW), 82496)
        self.assertEqual(hashlib.sha256(RAW).hexdigest(), '63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c')
        result = diagnostic.diagnose_retired(RAW)
        self.assertEqual(result['input_status'], 'INPUT_UNAVAILABLE')
        self.assertEqual(result['status'], 'STOP')
        self.assertEqual(result['compatibility'], 'CURRENT_NOT_DIRECTLY_COMPATIBLE')
        self.assertIsNone(result['projection'])
        self.assertEqual([result[k] for k in ('c30_called','c31_called','core_ran','native_interval_atomic')], [False]*4)
        self.assertEqual(result['authorization'], 'none')
        self.assertEqual(result['source_commit'], '4dc91fd24531b3df53fc916e8b7f509ad524592c')
        self.assertEqual(result['book_schema'], 1)
        self.assertEqual(result['historical_summary'], dict(
            record_count=20, source_origin_qpc_ns=27001348289300,
            first_record_end_qpc_ns=27001355219600, last_record_end_qpc_ns=27001540674400,
            fresh_source_timestamp_count=4, held_source_timestamp_count=16,
            null_c3_count=9, valid_zero_c3_count=11, missing_original_em_scope_count=20,
            max_nominal_em_age_at_record_completion_ns=43130900))

    def test_02_each_original_value_timestamp_and_quality_preserved(self):
        saved = json.loads(RAW); result = diagnostic.diagnose_retired(RAW)
        self.assertEqual(len(result['historical_rows']), 20)
        for row, source, sample, end in zip(result['historical_rows'], saved['records'],
                saved['original_source_book']['samples'], saved['actual_record_end_qpc_ns']):
            for key in ('adc_tick_ms','em_tick_ms','channel_counts','channel_values','quality'):
                self.assertEqual(row[key], source[key])
            for key in ('source_count','nominal_qpc_ns','source_sha256'):
                self.assertEqual(row[key], sample[key])
            self.assertEqual(row['actual_record_end_qpc_ns'], end)
            self.assertEqual(row['nominal_em_age_at_record_completion_ns'],
                end-(27001348289300+source['em_tick_ms']*1000000))
            self.assertEqual(row['original_em_scope_association'], 'unavailable')
        self.assertTrue(all(r['channel_values'][3] is None for r in result['historical_rows'][:9]))
        self.assertEqual(len(set(r['channel_values'][3] for r in result['historical_rows'][9:])), 11)
        self.assertTrue(all(r['channel_values'][3] > 0 for r in result['historical_rows'][9:]))

    def test_03_nonmatching_type_size_hash_reject_before_parse(self):
        changed = RAW.replace(b'"schema": 1', b'"schema": 2', 1)
        variants = [None, RAW.decode(), bytearray(RAW), memoryview(RAW), b'', RAW[:-1], RAW+b' ', changed]
        # Same-length private marker changes test only the byte pin gate. They
        # do not claim a generic schema/authority/duplicate-key branch test.
        self.assertEqual(len(changed), len(RAW)); self.assertNotEqual(changed, RAW)
        with patch.object(diagnostic.json, 'loads', side_effect=AssertionError('parse reached')) as parse:
            for value in variants:
                with self.subTest(kind=type(value).__name__):
                    with self.assertRaises(diagnostic.Rejected) as caught:
                        diagnostic.diagnose_retired(value)
                    self.assertEqual(str(caught.exception), 'C33_RETIRED_INPUT_NOT_PINNED')
            parse.assert_not_called()

    def test_04_bounded_whitelist_and_original_input_unchanged(self):
        before = hashlib.sha256(RAW).hexdigest(); out = diagnostic.diagnose_json(RAW)
        self.assertLessEqual(len(out), 65536)
        result = json.loads(out)
        self.assertEqual(set(result), set('schema_version diagnostic_kind input_sha256 input_bytes source_commit export_commit original_operation_id book_schema historical_only compatibility input_status status authorization claim native_interval_atomic projection c30_called c31_called core_ran missing_codes historical_rows historical_summary'.split()))
        row_keys = set('source_count adc_tick_ms em_tick_ms nominal_qpc_ns actual_record_end_qpc_ns source_sha256 channel_counts channel_values quality em_timestamp_mode original_em_scope_association nominal_em_age_at_record_completion_ns'.split())
        for row in result['historical_rows']: self.assertEqual(set(row), row_keys)
        for private_key in (b'canonical_source_hex',b'position_m',b'orientation_xyzw',b'owner_binding_id',b'payload'):
            self.assertNotIn(private_key, out)
        self.assertEqual(before, hashlib.sha256(RAW).hexdigest())
        self.assertEqual(out, diagnostic.diagnose_json(RAW))
        result['historical_rows'][0]['channel_counts'][0] = -1
        self.assertEqual(diagnostic.diagnose_retired(RAW)['historical_rows'][0]['channel_counts'][0],3011)

    def test_05_no_frozen_runtime_or_io_imports(self):
        tree = ast.parse((HERE/'retired_input_diagnostic.py').read_text(encoding='utf8'))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.extend(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom): imports.append(node.module)
        self.assertEqual(sorted(imports), ['hashlib','json'])
        self.assertFalse(any(isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
            and node.func.id in {'open','eval','exec','__import__'} for node in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main(verbosity=2)

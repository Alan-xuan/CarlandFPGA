import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRODUCT = ROOT / '.local/deepeye-implementation-c/competition/deepeye'
EVIDENCE = PRODUCT / 'evidence/ai/force_cpu_training_20261024'
ARTIFACT = PRODUCT / 'ai_pc/cpu_model/force_v1'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = read(ARTIFACT / 'model_manifest.json')
result = read(HERE / 'train-01.result.json')
assert result['exit_code'] == 0
for channel in ('stdout', 'stderr'):
    name = 'train-01.' + channel + '.txt'
    assert (HERE / name).read_bytes() == (EVIDENCE / 'run' / name).read_bytes()
    assert sha(HERE / name) == result[channel]['sha256']
assert sha(ARTIFACT / 'model_manifest.json') == '0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959'
for key in ('graph', 'weights'):
    assert sha(ARTIFACT / manifest[key]['path']) == manifest[key]['sha256']
assert sha(ARTIFACT / 'weights.json') == sha(HERE.parent / 'training-cache/epoch-05-weights.json')
assert sha(ARTIFACT / 'public_input.jsonl') == 'd81b29a6200d83133eda22149c70d2a0f6b3db06f9885ae669ddaffc75e99b37'
for name, expected in manifest['training']['sources'].items():
    assert sha(PRODUCT / name) == expected, name
assert sha(PRODUCT / 'data/preprocessing.json') == manifest['preprocessing']['sha256']
assert sha(PRODUCT / 'data/label_schema.json') == manifest['label_schema']['sha256']
before = read(EVIDENCE / 'pre-test-open-journal.json')
after = read(EVIDENCE / 'source-open-journal.json')
assert len(before['members']) == 99 and {item['split'] for item in before['members']} == {'train', 'validation'}
assert len(after['members']) == len({item['member'] for item in after['members']}) == 118
assert [item for item in after['members'] if item['split'] != 'test'] == before['members']
assert len([item for item in after['members'] if item['split'] == 'test']) == 19
events = [json.loads(line) for line in (HERE / 'train-01.stdout.txt').read_text().splitlines()]
frozen_at = next(i for i, item in enumerate(events) if item['event'] == 'model_frozen_before_test')
test_at = next(i for i, item in enumerate(events) if item.get('split') == 'test')
assert frozen_at < test_at
assert [item['epoch'] for item in events if item['event'] == 'epoch_complete'] == [1, 2, 3, 4, 5]
graph_freeze = read(EVIDENCE / 'graph-freeze-before-optimizer.json')
assert graph_freeze['optimizer_steps'] == 0 and graph_freeze['graph_sha256'] == manifest['graph']['sha256']
checks = read(EVIDENCE / 'causal-window-equivalence.json')
assert len(checks) == 3 and sum(len(item['sequences']) for item in checks) == 18 and all(item['float32_exact_equal'] for item in checks)
metrics = read(EVIDENCE / 'heldout_metrics.json')
assert metrics['fixed12_macro_f1_target'] == 0.60 and metrics['fixed12_macro_f1_target_met'] is False
assert metrics['test_model']['samples'] == 244176
assert sum(item['samples'] for item in metrics['test_model']['confidence_strata'].values()) == 244176
assert metrics['test_model']['macro_f1_fixed12'] < metrics['test_current_vector_centroid']['macro_f1_fixed12']
assert [item['source_code'] for item in metrics['test_model']['per_class'] if item['support'] == 0] == [70032, 88000, 93000]
assert metrics['test_model']['per_class'][4]['true_positive'] == 0
main_decision = HERE.parent / 'main-train-launch-decision.json'
(EVIDENCE / 'main-train-launch-decision.json').write_bytes(main_decision.read_bytes())
report = {
    'task_id': 'DEEPEYE-IMPLEMENTATION-20261014', 'task_version': 1,
    'work_id': 'C-FORCE-CPU-CNN-20261024-v1', 'actual_agent_id': '/root/force_cpu_model',
    'main_thread_id': '01a14025-4dfd-7ec3-aebb-57be48daba59',
    'contract': {'id': 'DEEPEYE-HUMAN-LOCK-20261014/revision1', 'source': 'f5989cd5defce561f9ba98e6b18fc2682945f0a2', 'requirements_sha256': 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804', 'design': '1011259415a0916054eb580687612580bc1e5f09'},
    'model_manifest_sha256': sha(ARTIFACT / 'model_manifest.json'),
    'public_input_sha256': sha(ARTIFACT / 'public_input.jsonl'),
    'graph_sha256': manifest['graph']['sha256'], 'weights_sha256': manifest['weights']['sha256'],
    'source_hashes': manifest['training']['sources'],
    'actual_runs': {'new_training_runs': 1, 'train_01_exit': 0, 'new_behavior_tests_01_exit': read(HERE / 'new-model-tests-01.result.json')['exit_code'], 'new_behavior_tests_02_exit': read(HERE / 'new-model-tests-02.result.json')['exit_code'], 'pip_install_exit': 0, 'env_check_exit': 0},
    'evidence_checks': {'all_source_and_frozen_artifact_bytes_unchanged': True, 'selected_weights_equal_epoch05_json': True, 'graph_frozen_before_optimizer': True, 'raw_log_proves_model_freeze_before_first_test_open': True, 'source_journal_99_before_118_after': True, 'complete_test_wells': 19, 'real_window_builder_exact_comparisons': 18},
    'quality': {'frozen_book_fixed12_macro_f1_target': 0.60, 'test_cnn': metrics['test_model']['macro_f1_fixed12'], 'test_centroid': metrics['test_current_vector_centroid']['macro_f1_fixed12'], 'test_majority': metrics['test_majority']['macro_f1_fixed12'], 'target_met': False, 'cnn_worse_than_centroid': True, 'unsupported_test_classes': [70032, 88000, 93000], 'dolomite_true_positives': 0, 'no_useful_core_AI_or_formal_C01_C02_C03_acceptance': True},
    'limits': ['Offline FORCE only; no sim_em_v2/water/obstacle/core online perception/map/planning model', 'No compressed-vs-raw quality comparison, R03/runtime, ROCm/AMD/NPU, physical sensor or board/system acceptance', 'No peer messages, commits, controller/SQL/credentials/physical board actions by this worker', 'Model and source frozen after test; no test-based tuning or repeat training'],
    'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
(EVIDENCE / 'model-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
(HERE / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
selected = [PRODUCT / name for name in ('ai_pc/model/force_cnn.py', 'ai_pc/train_force_cpu.py', 'ai_pc/force_training_data.py', 'tests/ai/cpu/test_force_model.py')]
selected += sorted(path for path in ARTIFACT.rglob('*') if path.is_file())
selected += sorted(path for path in EVIDENCE.rglob('*') if path.is_file())
records = [{'path': path.relative_to(PRODUCT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)} for path in selected]
delivery = {'task_id': report['task_id'], 'task_version': 1, 'work_id': report['work_id'], 'actual_agent_id': report['actual_agent_id'], 'files': records, 'artifact_count': len(records), 'report_sha256': sha(HERE / 'report.json'), 'no_commits_or_external_side_effects': True}
(HERE / 'delivery-manifest.json').write_text(json.dumps(delivery, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'actual_model_train_delivery_complete_quality_failed', 'files': len(records), 'report_sha256': sha(HERE / 'report.json'), 'delivery_manifest_sha256': sha(HERE / 'delivery-manifest.json')}), flush=True)

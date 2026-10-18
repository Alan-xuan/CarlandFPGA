"""Verify exact permitted inputs, source pins, lock identity and import boundary."""
import ast
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WATCH = '.local/main-20261015-01a14025/watch-20261018'
SOURCE = WATCH + '/b-candidate-review/sources/competition/deepeye'
PINS = {
    'trace_candidate_layout.json': '0de9a9a303ed691c645beba2ba9d39c7eb2261a8df336ea321f5055a07436e9c',
    'trace_candidate_vectors.json': 'e9fb59aa20324ebdeffb25ac89f43e42a085b3d49cec3ee9104ff551d9409bf2',
    'main_manual_vectors.json': '36b8e3fdb53e3c8fc911cc44b4f4151d62863d2e05b189f68c42fefe869b2d24',
    'main_candidate_spec.md': '7bc33ebc28c9f08e200c539a1a59c07b42b36211cb49b08ac449875bf75f9a73',
}
ORIGINALS = {
    'TRACE_CANDIDATE.md': WATCH + '/github/snapshot-20261018T143222Z/new-reference-bytes/pr30--competition__deepeye__golden__codec__TRACE_CANDIDATE.md',
    'trace_candidate_layout.json': SOURCE + '/golden/codec/trace_candidate_layout.json',
    'trace_candidate_vectors.json': SOURCE + '/golden/codec/trace_candidate_vectors.json',
    'main_manual_vectors.json': SOURCE + '/evidence/codec/trace-candidate-20261017-05/main/main_manual_vectors.json',
    'main_candidate_spec.md': SOURCE + '/evidence/codec/trace-candidate-20261017-05/main/main_candidate_spec.md',
    'immutable_scope.json': '.local/deepeye-implementation-c/docs/competition/deepeye-2026/immutable_scope.json',
    'immutable_scope.md': '.local/deepeye-implementation-c/docs/competition/deepeye-2026/immutable_scope.md',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, help='Optional author deployment root for original-copy equality; absent on peers')
    parser.add_argument('--check-only', action='store_true', help='Verify without rewriting evidence')
    args = parser.parse_args()
    records = []
    for name, relative_source in ORIGINALS.items():
        data = (HERE/'inputs'/name).read_bytes()
        if args.source_root is not None and data != (args.source_root/relative_source).read_bytes():
            raise AssertionError('copy differs from assigned source: ' + name)
        digest = hashlib.sha256(data).hexdigest()
        if name in PINS and digest != PINS[name]:
            raise AssertionError('documented SHA pin mismatch: ' + name)
        records.append(dict(path='inputs/' + name, source_relative_to_root=relative_source,
                            bytes=len(data), sha256=digest,
                            source_bytes_equal=True if args.source_root is not None else 'not_checked_portable_mode',
                            documented_sha256=PINS.get(name),
                            git_blob_sha1=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()))
    lock = json.loads((HERE/'inputs/immutable_scope.json').read_bytes())
    canonical = json.dumps(lock['requirements'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    expected = 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
    assert hashlib.sha256(canonical).hexdigest() == expected
    assert [r['id'] for r in lock['requirements']] == ['H' + str(i).zfill(2) for i in range(1, 16)]
    # The offline executable dependency closure has only this decoder and stdlib.
    imports = {}
    for name in ('candidate_decode.py', 'replay.py'):
        tree = ast.parse((HERE/name).read_text(encoding='utf-8'))
        modules = sorted({node.module if isinstance(node, ast.ImportFrom) else alias.name
                          for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                          for alias in (node.names if isinstance(node, ast.Import) else [None])})
        imports[name] = modules
        assert not any('trace_candidate' in module or 'codec_reference' in module for module in modules)
        assert set(modules) <= {'collections', 'copy', 'json', 'pathlib', 'candidate_decode'}
    manifest = dict(schema=1, task_id='DEEPEYE-IMPLEMENTATION-20261014', task_version=1,
                    work_id='C-independent-trace-candidate-decoder-20261018-v1', agent_id='/root/trace_decoder',
                    input_head='781be78d9da77a75ea711cf690eeea6523733d3a',
                    operation='B-DEEPEYE-TRACE-CANDIDATE-20261017-05',
                    request_hash='abe52729c5bb46944ec8c55dd92481af9362b4d5a92b0bdefd13d1061038de4a',
                    contract='DEEPEYE-HUMAN-LOCK-20261014/revision1',
                    contract_source_commit='f5989cd5defce561f9ba98e6b18fc2682945f0a2',
                    requirements_sha256=expected, design_commit='1011259415a0916054eb580687612580bc1e5f09',
                    source_imports=imports, input_files=records,
                    independence='No B encoder/decoder implementation or review script opened/imported. Source math uses original fixture values; raw expected bytes are pinned data.')
    if not args.check_only:
        (HERE/'input_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(status='passed', copied_inputs=len(records), original_byte_equality=args.source_root is not None,
                          documented_sha_pins=len(PINS),
                          requirements=15, requirements_sha256=expected, imports=imports), sort_keys=True))


if __name__ == '__main__':
    main()

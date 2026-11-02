"""Read-only byte verification; does not execute the historical fixture or product."""
import argparse
import hashlib
import json
from pathlib import Path

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path,
                        help='Optional exact A e470 checkout root for source byte checks')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    index = json.loads((root / 'artifact-index.json').read_bytes())
    for entry in index['files']:
        path = (root / entry['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('artifact outside package')
        data = path.read_bytes()
        if len(data) != entry['bytes'] or digest(data) != entry['sha256']:
            raise ValueError('artifact mismatch: ' + entry['path'])
    layout = json.loads((root / 'geometry/layout-software-fixture.json').read_bytes())
    parameters = json.loads((root / 'geometry/parameters.json').read_bytes())
    if not parameters['software_fixture'] or not parameters['not_mouse_authored']:
        raise ValueError('fixture provenance changed')
    checked_source = 0
    if args.source_root:
        pins = json.loads((root / 'geometry/source-pins.json').read_bytes())
        for entry in pins['files']:
            path = (args.source_root / entry['path']).resolve()
            if not path.is_relative_to(args.source_root.resolve()):
                raise ValueError('source outside root')
            data = path.read_bytes()
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if (len(data), digest(data), blob) != (entry['bytes'], entry['sha256'], entry['git_blob']):
                raise ValueError('A source mismatch: ' + entry['path'])
            checked_source += 1
    print(json.dumps(dict(status='BYTES_VERIFIED', artifacts=len(index['files']),
                         source_files_checked=checked_source,
                         layout_hash=layout['layout_hash'],
                         source_commit=index['A_source_commit'],
                         software_fixture=True, not_mouse_authored=True,
                         historical_tests_rerun=False, product_executed=False,
                         formal_acceptance=False), sort_keys=True))

if __name__ == '__main__':
    main()

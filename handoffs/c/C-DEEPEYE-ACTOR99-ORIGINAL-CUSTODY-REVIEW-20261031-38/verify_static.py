"""Offline byte/AST packaging verification; never imports or executes A source."""
import argparse
import ast
import base64
import difflib
import gzip
import hashlib
import json
from pathlib import Path


def definitions(tree):
    out = {}
    def walk(body, prefix=''):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                key = prefix + node.name
                out[key] = node
                walk(node.body, key + '.')
    walk(tree.body)
    return out


def dump(node):
    return ast.dump(node, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', nargs='?', default=str(Path(__file__).parent))
    directory = Path(parser.parse_args().package)
    pins = json.loads((directory / 'source-pins.json').read_bytes())
    archive = json.loads(gzip.decompress(base64.b64decode(
        (directory / 'source-bytes.json.gz.b64').read_bytes(), validate=True)))
    assert len(pins) == len(archive) == 21
    data = {}
    for pin, member in zip(pins, archive):
        assert (pin['ref'], pin['path']) == (member['ref'], member['path'])
        raw = base64.b64decode(member['base64'], validate=True)
        assert len(raw) == pin['bytes']
        assert hashlib.sha256(raw).hexdigest() == pin['sha256']
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == pin['git_blob']
        key = (pin['ref'], Path(pin['path']).name)
        assert key not in data
        data[key] = raw
        if pin['path'].endswith('.py'):
            ast.parse(raw)
    old = 'd9716760b15cd84c6b60442a9d9368fdcd0e46fa'
    new = 'e794de598a40c11cefb372813aa950f58f03007a'
    changes = {}
    for ref, name in data:
        if ref != old:
            continue
        a, b = data[old, name], data[new, name]
        left, right = definitions(ast.parse(a)), definitions(ast.parse(b))
        changes[name] = {
            'changed': [n for n in left if n in right and dump(left[n]) != dump(right[n])],
            'added': sorted(right.keys() - left.keys()),
            'removed': sorted(left.keys() - right.keys()),
        }
        delta = ''.join(difflib.unified_diff(
            a.decode().splitlines(True), b.decode().splitlines(True),
            fromfile=old + '/' + name, tofile=new + '/' + name))
        assert delta.replace('\r\n', '\n') == (directory / (name + '.parent.diff')).read_text(encoding='utf8')
        if name == 'motion_executor.py':
            def suffix(node):
                for i, statement in enumerate(node.body):
                    if isinstance(statement, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id == 'fence' for t in statement.targets
                    ):
                        return ast.Module(body=node.body[i:], type_ignores=[])
                raise AssertionError('missing final fence')
            key = 'OwnedMotionExecutor._commit_numeric'
            assert dump(suffix(left[key])) == dump(suffix(right[key]))
            changes[name]['final_callback_through_return_AST_identical'] = True
    assert len(changes) == 5
    assert changes == json.loads((directory / 'AST-parent-delta.json').read_bytes())
    findings = json.loads((directory / 'FINDINGS.json').read_bytes())
    assert findings['source_approved'] is False
    assert [x['id'] for x in findings['open_findings']] == ['C38-R1']
    print(json.dumps({'verification': 'PACKAGING_BYTES_AND_STATIC_AST_ONLY',
        'source_bytes': sum(x['bytes'] for x in pins), 'sources_verified': 21,
        'parent_diffs_verified': 5, 'final_callback_AST_identical': True,
        'candidate_imports': 0, 'candidate_tests_run': 0,
        'local_function': {'status': 'NOT_RUN', 'exit_code': None},
        'runtime': {'status': 'NOT_RUN', 'exit_code': None},
        'source_approved': False, 'open_findings': ['C38-R1']}))


if __name__ == '__main__':
    main()

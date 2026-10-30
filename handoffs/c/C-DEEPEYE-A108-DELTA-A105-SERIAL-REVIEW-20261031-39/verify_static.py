"""Standalone offline byte/GET/git-blob/AST/diff verifier; imports no source.

Run with Python3.12+ from any cwd. No extraction, network, source execution or
upstream tests. A successful result is static evidence integrity only.
"""
import ast
import base64
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT=Path(__file__).resolve().parent
NEW='51c48e106c76f3e4d18000da61be17dd8a4b6623'
OLD='2a5e57ff7dc78763bc98352e6cb02e2510d370ea'
BASE='e794de598a40c11cefb372813aa950f58f03007a'
REQ='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def read_json(name): return json.loads((ROOT/name).read_bytes())


def functions(raw):
    result={}
    def visit(node,prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                name=prefix+child.name
                if not isinstance(child,ast.ClassDef):
                    result[name]=ast.dump(child,include_attributes=False)
                visit(child,name+'.')
    visit(ast.parse(raw))
    return result


def main():
    ordinary=[p for p in ROOT.iterdir() if p.is_file() and p.name != "manifest.json"]
    assert len(ordinary)<=23 and sum(p.stat().st_size for p in ordinary)<2097152
    index=read_json('archive-index.json')
    for item in index['copied_files']:
        raw=(ROOT/item['file']).read_bytes()
        assert len(raw)==item['bytes'] and sha(raw)==item['sha256']
    archives={}
    for filename,entry in index['archives'].items():
        raw=(ROOT/filename).read_bytes()
        assert len(raw)==entry['bytes'] and sha(raw)==entry['sha256']
        members={}
        with zipfile.ZipFile(ROOT/filename) as archive:
            infos=archive.infolist()
            assert len(infos)==len(entry['members']) and len({i.filename for i in infos})==len(infos)
            assert sum(i.file_size for i in infos)<=2097152
            expected={r['name']:r for r in entry['members']}
            for info in infos:
                path=PurePosixPath(info.filename)
                assert not path.is_absolute() and '..' not in path.parts and '\\' not in info.filename
                data=archive.read(info)
                pin=expected[info.filename]
                assert len(data)==pin['bytes'] and sha(data)==pin['sha256']
                members[info.filename]=data
        archives[filename]=members
    sources=archives['sources.zip']; api=archives['original-api-evidence.zip']
    pins=read_json('source-pins.json')
    assert len(pins)==len(sources)==20
    parsed=0
    for pin in pins:
        name=pin['local'].replace('\\','/')
        raw=sources[name]
        assert len(raw)==pin['bytes'] and sha(raw)==pin['sha256']
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==pin['git_blob']
        if pin['path'].endswith('.py'):
            ast.parse(raw);parsed+=1
    commands=read_json('api-read-command-summary.json')
    assert len(commands)==20
    contents=0
    for row in commands:
        name=row['record'].replace('\\','/')
        original=json.loads(api[name])
        assert original['argv']==row['argv'] and original['exit_code']==row['exit_code']==0
        assert original['argv'][:2]==['gh','api']
        response_name=name.removesuffix('.command.json')
        response=json.loads(api[response_name])
        assert api[response_name+'.stderr']==b''
        if '/contents/' in original['argv'][2]:
            raw=base64.b64decode(response['content'])
            source_name=response_name.removesuffix('.api.json')
            pin=next(p for p in pins if p['local'].replace('\\','/')==source_name)
            assert sources[source_name]==raw and response['path']==pin['path']
            assert response['size']==pin['bytes'] and response['sha']==pin['git_blob']
            assert original['argv'][2].endswith('?ref='+pin['ref'])
            contents+=1
    assert contents==18  # Other two GETs are commit metadata; two source contexts were reused.
    commits={key:json.loads(api[key+'-commit.api.json']) for key in ('A105','A108')}
    assert commits['A108']['sha']==NEW and commits['A108']['parents'][0]['sha']==OLD
    assert commits['A105']['sha']==OLD and commits['A105']['parents'][0]['sha']==BASE
    supplied=json.loads(api['requested-source-pins.json'])
    assert len(supplied)==11
    for item in supplied:
        pin=next(p for p in pins if (p['ref'],p['path'])==(item['ref'],item['path']))
        assert all(pin[k]==item[k] for k in ('bytes','sha256','git_blob'))
    for label,ref,count in [('A108',NEW,6),('A105',OLD,5)]:
        paths={f['filename'] for f in commits[label]['files']}
        assert len(paths)==count and paths=={p['path'] for p in supplied if p['ref']==ref}
    assert not {f['filename'] for f in commits['A105']['files']} & {f['filename'] for f in commits['A108']['files']}
    for pin in pins:
        if 'sealed C38' in pin['provenance']:
            assert all(pin['path'] not in {f['filename'] for f in c['files']} for c in commits.values())
    deltas=read_json('ast-delta.json')
    assert len(deltas)==5
    for row in deltas:
        before=sources['inputs/'+row['before']+'/'+row['file']].decode('utf-8').replace('\r\n','\n')
        after=sources['inputs/'+row['after']+'/'+row['file']].decode('utf-8').replace('\r\n','\n')
        diff=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
             fromfile=row['before']+'/'+row['file'],tofile=row['after']+'/'+row['file']))
        assert diff==(ROOT/row['diff']).read_text(encoding='utf-8')
        a,b=functions(before),functions(after)
        assert row['changed']==[k for k in sorted(a.keys()&b.keys()) if a[k]!=b[k]]
        assert row['added']==sorted(b.keys()-a.keys()) and row['removed']==sorted(a.keys()-b.keys())
    findings=read_json('FINDINGS.json'); summary=read_json('static-verification.json')
    assert findings['source_approved'] is True and findings['open_source_findings']==[]
    assert findings['runtime_status']==findings['local_function_tests_status']=='NOT_RUN'
    assert findings['runtime_exit_code'] is None and findings['local_function_tests_exit_code'] is None
    assert summary['requirements_sha256']==REQ and summary['source_imports']==0
    manifest=ROOT/'proposed-manifest.json'
    checked=False
    if manifest.exists():
        for item in json.loads(manifest.read_bytes())['files']:
            raw=(ROOT/item['file']).read_bytes()
            assert len(raw)==item['bytes'] and sha(raw)==item['sha256']
        checked=True
    print(json.dumps(dict(kind='OFFLINE_STATIC_PACKET_VERIFICATION',source_files=20,parsed_python=parsed,
                         original_GET_commands=20,source_GET_responses=18,supplied_pins=11,diffs=5,
                         packet_manifest_checked=checked,source_imports=0,
                         runtime_status='NOT_RUN',runtime_exit_code=None,
                         local_function_tests_status='NOT_RUN',local_function_tests_exit_code=None,
                         integration_compatibility_approved=False,multicycle_approved=False),sort_keys=True))


if __name__=='__main__': main()

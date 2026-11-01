from pathlib import Path, PurePosixPath
import hashlib, io, json, zipfile
root=Path(__file__).resolve().parent
def check(b,rec):
    assert len(b)==rec['bytes'] and hashlib.sha256(b).hexdigest()==rec['sha256'], rec['path']
def archive(b):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        names=z.namelist()
        assert len(names)==len(set(names))
        assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names)
        m=json.loads(z.read('evidence-manifest.json'))
        assert set(names)=={r['path'] for r in m['files']}|{'evidence-manifest.json'}
        for r in m['files']:
            data=z.read(r['path']); check(data,r)
            if r['path'].endswith('.zip'): archive(data)
        return len(names)
m=json.loads((root/'draft-manifest.json').read_text())
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
assert actual=={r['path'] for r in m['files']}|{'draft-manifest.json'}
for r in m['files']: check((root/r['path']).read_bytes(),r)
count=archive((root/'evidence.zip').read_bytes())
print(json.dumps({'status':'BYTE_VERIFIED','public_files':len(actual),'archive_members':count,'candidate_imports':0,'test_execution':False}))

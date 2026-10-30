"""Verify delivered exact-byte evidence without importing or executing tests.
Usage: python -B verify_evidence_archive.py PUBLIC_DIR [NEW_EXTRACTION_DIR]
Extraction is optional and refuses to replace an existing directory.
"""
import base64,gzip,hashlib,json,pathlib,sys
def sha(b):return hashlib.sha256(b).hexdigest()
P=pathlib.Path(sys.argv[1]).resolve()
manifest=json.loads((P/'manifest.json').read_bytes())
root=P.parents[2]
assert isinstance(manifest['files'],dict), 'canonical handoff manifest required'
for name,e in manifest['files'].items():
 rel=pathlib.PurePosixPath(name);assert not rel.is_absolute() and '..' not in rel.parts
 b=(root/rel).read_bytes();assert len(b)==e['size'] and sha(b)==e['sha256'],name
public_files=[p for p in P.iterdir() if p.is_file()]
assert {p.relative_to(root).as_posix() for p in public_files if p.name!='manifest.json'}=={n for n in manifest['files'] if pathlib.PurePosixPath(n).parent.name==P.name}
assert len(public_files)<=18 and sum(p.stat().st_size for p in public_files)<=2097152
index=json.loads((P/'evidence-index.json').read_bytes())
raw=base64.b64decode((P/'evidence-archive.json.gz.b64').read_bytes(),validate=True)
assert sha(raw)==index['gzip_sha256']
archive=json.loads(gzip.decompress(raw))
assert archive['entries']==index['entries']
blobs={k:base64.b64decode(v,validate=True) for k,v in archive['blobs'].items()}
assert all(sha(b)==s for s,b in blobs.items())
seen=set();extracted=0
out=pathlib.Path(sys.argv[2]).resolve() if len(sys.argv)>2 else None
if out:out.mkdir(parents=True,exist_ok=False)
for e in archive['entries']:
 rel=pathlib.PurePosixPath(e['path']);assert not rel.is_absolute() and '..' not in rel.parts and ':' not in e['path'] and '\\' not in e['path']
 assert e['path'] not in seen;seen.add(e['path'])
 b=blobs[e['sha256']];assert len(b)==e['bytes'];extracted+=len(b)
 if out:
  target=out.joinpath(*rel.parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
print(json.dumps({'verified_files':len(public_files),'public_bytes':sum(p.stat().st_size for p in public_files),'archive_entries':len(seen),'exact_restored_bytes':extracted,'tests_executed':0,'candidate_imports':0}))

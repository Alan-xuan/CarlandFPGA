from pathlib import Path,PurePosixPath
import gzip,hashlib,io,json,re,zipfile
D=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def walk(name,b,depth=0):
 assert depth<8
 if name.endswith('.gz'):walk(name[:-3],gzip.decompress(b),depth+1);return
 if zipfile.is_zipfile(io.BytesIO(b)):
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   names=z.namelist();assert len(names)==len(set(names)) and z.testzip() is None
   assert len(names)<2048 and sum(i.file_size for i in z.infolist())<64*1024*1024
   for n in names:
    p=PurePosixPath(n);assert not p.is_absolute() and '..' not in p.parts and ':' not in n and chr(92) not in n
    walk(n,z.read(n),depth+1)
  return
 text=b.decode('utf8','replace')
 for pattern in [r'[A-Za-z]:[\\/]+Users[\\/]+',r'\.codex[\\/]+sessions',r'01a[0-9a-f]{5}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}','xilinx'+'@','fe80'+'::[0-9a-f:%]+']:
  assert not re.search(pattern,text,re.I),'private pattern: '+name
rows=json.loads((D/'delivery-files.json').read_bytes())
assert {p.relative_to(D).as_posix() for p in D.rglob('*') if p.is_file()}=={r['path'] for r in rows}|{'delivery-files.json'}
for r in rows:
 b=(D/r['path']).read_bytes();assert len(b)==r['bytes'] and sha(b)==r['sha256'];walk(r['path'],b)
with zipfile.ZipFile(D/'independent-review-evidence.zip') as z:
 m=json.loads(z.read('MANIFEST.json'))['files'];assert set(z.namelist())=={r['path'] for r in m}|{'MANIFEST.json'}
 for r in m:
  b=z.read(r['path']);assert len(b)==r['bytes'] and sha(b)==r['sha256']
approval=json.loads((D/'source-approval.json').read_bytes())
with zipfile.ZipFile(D/'c51-repaired-source.zip') as z:
 for r in approval['shipping_sources']:
  b=z.read(r['archive_path']);assert len(b)==r['bytes'] and sha(b)==r['sha256']
print(json.dumps(dict(status='C51_BYTES_ARCHIVES_PASS',files=len(rows)+1,product_tests_executed=False,source_approval='bounded only',production_activation=False)))

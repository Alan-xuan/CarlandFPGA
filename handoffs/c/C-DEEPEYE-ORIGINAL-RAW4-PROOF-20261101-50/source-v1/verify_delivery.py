from pathlib import Path, PurePosixPath
import gzip,hashlib,io,json,re,subprocess,sys,zipfile
D=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def walk(name,b,depth=0):
 assert depth<8
 if name.endswith('.gz'):walk(name[:-3],gzip.decompress(b),depth+1);return
 if zipfile.is_zipfile(io.BytesIO(b)):
  with zipfile.ZipFile(io.BytesIO(b))as z:
   assert len(z.namelist())==len(set(z.namelist())) and z.testzip()is None
   assert len(z.namelist())<1024 and sum(i.file_size for i in z.infolist())<32*1024*1024
   for n in z.namelist():
    p=PurePosixPath(n);assert not p.is_absolute()and '..'not in p.parts and ':'not in n and chr(92)not in n
    walk(n,z.read(n),depth+1)
  return
 text=b.decode('utf8','replace')
 for p in [r'[A-Za-z]:[\\/]Users[\\/]',r'\.codex[\\/]sessions',r'01a[0-9a-f]{5}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}','xilinx'+'@','fe80'+'::[0-9a-f:%]+']:
  assert not re.search(p,text,re.I),'private pattern: '+name
rows=json.loads((D/'delivery-files.json').read_bytes())
assert {p.relative_to(D).as_posix()for p in D.rglob('*')if p.is_file()}=={r['path']for r in rows}|{'delivery-files.json'}
for r in rows:
 b=(D/r['path']).read_bytes();assert len(b)==r['bytes']and sha(b)==r['sha256'];walk(r['path'],b)
with zipfile.ZipFile(D/'independent-review-evidence.zip')as z:
 m=json.loads(z.read('MANIFEST.json'));assert set(z.namelist())=={x['path']for x in m['files']}|{'MANIFEST.json'}
 for r in m['files']:
  b=z.read(r['path']);assert len(b)==r['bytes']and sha(b)==r['sha256']
for args in [[str(D/'raw4/verify_package.py')],[str(D/'mailbox/verify_package.py'),str(D/'mailbox/c50-mailbox-public-draft-v1.zip')]]:
 r=subprocess.run([sys.executable,'-I','-S','-B',*args],capture_output=True);assert r.returncode==0,r.stderr.decode('utf8','replace');print(r.stdout.decode(),end='')
print(json.dumps(dict(status='C50_BYTES_ARCHIVES_PASS',files=len(rows)+1,product_tests_executed=False,source_approval='bounded partial only',production_activation=False)))

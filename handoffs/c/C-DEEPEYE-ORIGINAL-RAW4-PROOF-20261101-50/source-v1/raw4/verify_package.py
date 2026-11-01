from pathlib import Path
import hashlib,io,json,zipfile
D=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def recurse(name,b):
 if name.endswith('.zip'):
  with zipfile.ZipFile(io.BytesIO(b))as z:
   assert z.testzip()is None and len(z.namelist())==len(set(z.namelist()))
   for n in z.namelist():
    assert not n.startswith(('/',chr(92))) and '..'not in Path(n).parts
    recurse(n,z.read(n))
with zipfile.ZipFile(D/'raw4-repaired-draft.zip')as z:
 m=json.loads((D/'draft-manifest.json').read_bytes());assert set(z.namelist())=={f['path']for f in m['files']}
 for f in m['files']:
  b=z.read(f['path']);assert len(b)==f['bytes']and sha(b)==f['sha256'];recurse(f['path'],b)
 with zipfile.ZipFile(io.BytesIO(z.read('history/original-unapproved-draft.zip')))as old:
  om=json.loads(z.read('history/original-manifest.json'))
  assert set(old.namelist())=={f['path']for f in om['files']}
  for f in om['files']:
   b=old.read(f['path']);assert len(b)==f['bytes']and sha(b)==f['sha256']
 for f in json.loads(z.read('final-source-pins.json'))['files']:
  b=z.read(f['path']);assert len(b)==f['bytes']and sha(b)==f['sha256']
 p='repair/runs/run01/';c=json.loads(z.read(p+'command.DERIVED.json'));r=json.loads(z.read(p+'result.json'))
 assert r['exit_code']==0 and r['pins']['command.json']==c['original']['sha256']
 for n in ('source-version.zip','stdout.bin','stderr.bin'):assert sha(z.read(p+n))==r['pins'][n]
 with zipfile.ZipFile(io.BytesIO(z.read(p+'source-version.zip')))as version:
  for f in c['source_pins']:
   b=version.read(f['path']);assert len(b)==f['bytes']and sha(b)==f['sha256']
 assert len(json.loads(z.read('repair/cases.json')))==10
 r=json.loads(z.read('independent-original/exit.json'));c=json.loads(z.read('independent-original/command.DERIVED.json'))
 assert r['exit_code']==1 and r['pins']['command.json']==c['original']['sha256']
 for n in ('stdout.bin','stderr.bin'):assert sha(z.read('independent-original/'+n))==r['pins'][n]
 print(json.dumps(dict(status='PASS_BYTES_ONLY',members=len(m['files']),historical_author_runs=7,independent_reds=4,repair_cases=10,product_tests_executed=0)))

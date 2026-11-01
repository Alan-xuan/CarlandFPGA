from pathlib import Path
import hashlib,io,json,zipfile
P=Path(__file__).resolve().parent
def check(z,rows):
 assert len(z.namelist())==len(rows) and set(z.namelist())=={r['path'] for r in rows}
 for r in rows:
  b=z.read(r['path']);assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
for r in json.loads((P/'pins.json').read_bytes()):
 b=(P/r['path']).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
rows=json.loads((P/'evidence-index.json').read_bytes())['files']
with zipfile.ZipFile(P/'evidence.zip') as z:
 check(z,rows)
 with zipfile.ZipFile(io.BytesIO(z.read('predecessor-public/evidence.zip'))) as old:
  check(old,json.loads(z.read('predecessor-public/evidence-index.json'))['files'])
print(json.dumps({'outer_members':len(rows),'nested_predecessor_verified':True,'source_execution':False,'approval':'BOUNDED_SOURCE_APPROVED'}))

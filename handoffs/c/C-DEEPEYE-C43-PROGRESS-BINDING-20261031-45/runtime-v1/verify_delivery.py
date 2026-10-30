from pathlib import Path
import json,hashlib,zipfile
P=Path(__file__).resolve().parent
pins=json.loads((P/'pins.json').read_bytes())
for r in pins:
 b=(P/r['path']).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
index=json.loads((P/'evidence-index.json').read_bytes())['files']
with zipfile.ZipFile(P/'evidence.zip') as z:
 assert len(z.namelist())==len(index) and set(z.namelist())=={r['path'] for r in index}
 for r in index:
  b=z.read(r['path']);assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
print(json.dumps({'public_pins':len(pins),'archive_members':len(index),'source_execution':False,'native_run':False,'formal_acceptance':False}))

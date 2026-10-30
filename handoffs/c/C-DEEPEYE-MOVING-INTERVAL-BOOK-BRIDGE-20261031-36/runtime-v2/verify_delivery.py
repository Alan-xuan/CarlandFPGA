"""Check source/evidence bytes only; never import host, planner or actor."""
from pathlib import Path
import hashlib,json,zipfile
P=Path(__file__).resolve().parent
pins=json.loads((P/'pins.json').read_bytes())
for row in pins['files']:
 p=P/row['path'];assert p.resolve().is_relative_to(P)
 b=p.read_bytes();assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
index=json.loads((P/'evidence-index.json').read_bytes())
with zipfile.ZipFile(P/'evidence.zip') as z:
 assert z.testzip() is None and set(z.namelist())=={r['path'] for r in index['members']}
 for row in index['members']:
  b=z.read(row['path']);assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
assert hashlib.sha256((P/'host_projection.py').read_bytes()).hexdigest()=='7defaee9318f9a33a0586628661d054c028b5952584030ebc3b771a479a8982e'
assert hashlib.sha256((P/'request.schema.json').read_bytes()).hexdigest()=='ab1b432e9f337523fd75057fec4647f5eda2569de308e7c777507e05907bdd70'
assert hashlib.sha256((P/'public-view.schema.json').read_bytes()).hexdigest()=='046b863c6bc07bbaa5396c5b7dfc55fb1febf7bbd0bda29ef79cbd5119f981ed'
print(json.dumps({'artifact_pins_verified':len(pins['files']),'archive_members_verified':len(index['members']),'planner_calls':0,'native_actor_runs':0,'formal_acceptance':False}))

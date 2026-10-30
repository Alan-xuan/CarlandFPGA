"""Verify delivered bytes and recorded evidence only; never run planner or actor."""
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
assert hashlib.sha256((P/'c37-owned-cpu-package/frozen_c28.py').read_bytes()).hexdigest()=='70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'
inv=json.loads((P/'runtime-inventory.json').read_bytes());assert len(inv['files'])==633
for row in inv['package_files']:
 b=(P/'c37-owned-cpu-package'/row['path']).read_bytes()
 assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
print(json.dumps({'artifact_pins_verified':len(pins['files']),'archive_members_verified':len(index['members']),'planner_calls':0,'native_actor_runs':0,'formal_acceptance':False}))

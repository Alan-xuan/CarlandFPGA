from pathlib import Path
import json,hashlib
D=Path(__file__).resolve().parent
x=json.loads((D/'artifact-index.json').read_bytes())
for r in x['files']:
 p=D/r['path'];assert p.resolve().is_relative_to(D.resolve());b=p.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
assert json.loads((D/'readiness-checks.json').read_bytes())['product_execution'] is False
assert json.loads((D/'display-candidate.json').read_bytes())['product_execution']=='NOT_RUN'
print(json.dumps(dict(status='PASS_BYTES_ONLY',files=len(x['files']),product_execution=False,formal_acceptance=False)))

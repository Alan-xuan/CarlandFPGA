from pathlib import Path
import json,hashlib,zipfile
D=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
idx=json.loads((D/'artifact-index.json').read_bytes())
for row in idx['files']:
 p=D/row['path'];assert p.resolve().is_relative_to(D.resolve())
 b=p.read_bytes();assert len(b)==row['bytes'] and sha(b)==row['sha256'],row['path']
m=json.loads((D/'candidate-manifest-v2.json').read_bytes())
with zipfile.ZipFile(D/'candidate-source.zip') as z:
 assert len(z.namelist())==43 and set(z.namelist())=={r['path'] for r in m['files']}
 for r in m['files']:assert sha(z.read(r['path']))==r['sha256']
assert json.loads((D/'main/validate-fullscreen.command.json').read_bytes())['exit_code']==2
for label in ['validate-fullscreen-v2','import-new-copy-v2','probe-v2']:
 assert json.loads((D/'main'/f'{label}.command.json').read_bytes())['exit_code']==0
assert json.loads((D/'main/viewer-exit-v2.json').read_bytes())['exit_code']==0
assert b'DEEPEYE_VIEWER_CHILD_EXIT=0' in (D/'main/viewer-v2.stdout').read_bytes()
assert (D/'main/viewer-v2.stderr').read_bytes()==b''
print(json.dumps(dict(status='PASS_BYTES_ONLY',files=len(idx['files']),source_files=43,product_execution=False,formal_acceptance=False)))

from pathlib import Path
import json,hashlib,zipfile
R=Path(__file__).resolve().parent
def h(b):return hashlib.sha256(b).hexdigest()
index=json.loads((R/'artifact-index.json').read_bytes())
for row in index['files']:
 p=R/row['path'];assert p.is_relative_to(R) and p.is_file()
 b=p.read_bytes();assert len(b)==row['bytes'] and h(b)==row['sha256'],row['path']
manifest=json.loads((R/'candidate-manifest-v2.json').read_bytes())
with zipfile.ZipFile(R/'candidate-source.zip') as z:
 assert set(z.namelist())=={r['path'] for r in manifest['files']}
 for row in manifest['files']:
  b=z.read(row['path']);assert len(b)==row['bytes'] and h(b)==row['sha256'],row['path']
 changed=[r['path'] for r in manifest['files'] if r['sha256']!=r['baseline_sha256']]
 assert set(changed)=={'competition/deepeye/simulator/editor/layout_commit_bridge.gd','competition/deepeye/simulator/native/layout_runtime.json','competition/deepeye/simulator/native/run_viewer.py'}
assert h((R/'ui/mouse-layout.json').read_bytes())=='6b6caf18d6dfb61df23db1f29fda3a33f6f7f47395803090185f103a0488dbbe'
assert json.loads((R/'main/viewer-exit-v1.json').read_bytes())['exit_code']==0
assert 'DEEPEYE_VIEWER_CHILD_EXIT=0' in (R/'main/viewer.stdout').read_text()
print(json.dumps({'indexed_files':len(index['files']),'source_files':len(manifest['files']),'allowed_changed_files':len(changed),'byte_verification':'PASS','product_execution':False,'raw_ACK_capture':False,'formal_acceptance':False}))

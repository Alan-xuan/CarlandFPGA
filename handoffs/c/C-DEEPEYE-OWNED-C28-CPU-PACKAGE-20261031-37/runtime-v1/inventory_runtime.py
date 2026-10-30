"""Read/hash the existing CPython distribution; no binaries copied/downloaded."""
import datetime
import hashlib
import json
from pathlib import Path
import sys

out = Path(__file__).resolve().parent
package = out / 'c37-owned-cpu-package'
names = ('c37_entry.py', 'c37_package.py', 'frozen_c28.py')
files = {name: hashlib.sha256((package/name).read_bytes()).hexdigest() for name in names}
assert files['frozen_c28.py'] == '70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4'
(package/'package-manifest.json').write_text(json.dumps({'schema_version':1,'files':files},indent=2)+'\n',encoding='utf-8')
base = Path(sys.base_prefix).resolve()
excluded = {'site-packages', '__pycache__', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', 'venv'}
paths = [base/name for name in ('python.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt')]
for folder in ('Lib', 'DLLs'):
    paths.extend(p for p in (base/folder).rglob('*') if p.is_file()
                 and not set(p.relative_to(base).parts) & excluded
                 and not p.name.startswith('_test') and p.suffix != '.pyc')
records = []
for path in sorted(set(paths)):
    assert not path.is_symlink()
    raw = path.read_bytes()
    records.append({'path':'runtime/'+path.relative_to(base).as_posix(), 'bytes':len(raw),
                    'sha256':hashlib.sha256(raw).hexdigest()})
runtime_bytes = sum(x['bytes'] for x in records)
assert runtime_bytes < 268435456
document = {'schema_version':1,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'runtime_original_root':str(base),'version':sys.version,'files':records,
            'runtime_bytes':runtime_bytes,'actor_stage_max_bytes':268435456,
            'license_file':'runtime/LICENSE.txt','binary_publication':False,
            'system_dependencies':'Windows system DLLs / API sets from trusted OS; not copied as package artifacts',
            'status':'EXACT_EXISTING_FILES_INVENTORIED_NOT_RELOCATED_OR_ORIGINAL_ACTOR_QUALIFIED',
            'excluded_directories':sorted(excluded),
            'package_files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                             for p in sorted(package.iterdir()) if p.is_file()]}
(out/'runtime-inventory.json').write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'runtime_files':len(records),'runtime_bytes':runtime_bytes,
                  'package_manifest_sha256':hashlib.sha256((package/'package-manifest.json').read_bytes()).hexdigest(),
                  'status':document['status'],'binaries_copied':0}))

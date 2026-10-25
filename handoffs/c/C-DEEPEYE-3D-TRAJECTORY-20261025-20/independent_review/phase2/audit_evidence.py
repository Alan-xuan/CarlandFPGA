"""Metadata-only audit of saved author execution evidence and final textual diff."""
import hashlib
import json
from pathlib import Path
import platform
import sys

node=Path(sys.argv[1])
root=node/'.local/deepeye-implementation-c'
folder=root/'competition/deepeye/evidence/ai/trajectory_candidate_20261025'
pins={
 'competition/deepeye/ai_pc/planning/trajectory_candidates.py':'ede34dfa38f093c7ba0858ca211b824e08268447846a0859b9a69cb4cb7a0c15',
 'competition/deepeye/ai_pc/planning/swept_capsule.py':'765b83405a4773c2e4da4806d9d42bd39bc66bda6e78f0a4acf9e3d86eba5b4a',
 'competition/deepeye/ai_pc/planning/TRAJECTORY_CANDIDATE.md':'87daba843f69425a7d8db78fc2ba382586770fb581586003601c79e4cf3294b9',
}
assert hashlib.sha256((folder/'delivery-manifest.json').read_bytes()).hexdigest()=='f1f128b867acb623f2aea49cab00e9c453312e93cb5e8ac786f46e7a01e43ad1'
raw_checks=[]
for name in ('tests-01','tests-final','examples'):
    command=json.loads((folder/name/'command.json').read_text(encoding='utf-8-sig'))
    result=json.loads((folder/name/'result.json').read_text(encoding='utf-8-sig'))
    assert result['exit_code']==0
    hashes={}
    for stream in ('stdout','stderr'):
        actual=hashlib.sha256((folder/name/(stream+'.txt')).read_bytes()).hexdigest()
        assert actual==result[stream+'_sha256']
        hashes[stream]=actual
    snapshot_checks={}
    for path in pins:
        if path not in command['sources_before']: continue
        snap=folder/name/'source-before'/path
        actual=hashlib.sha256(snap.read_bytes()).hexdigest()
        assert actual==command['sources_before'][path]
        if name!='tests-01': assert actual==pins[path]
        snapshot_checks[path]=actual
    raw_checks.append({'name':name,'exit_code':result['exit_code'],'argv':command['argv'],'stream_hashes':hashes,'source_snapshots':snapshot_checks})
sections={}
current=None
for line in (folder/'source-review.diff').read_text(encoding='utf-8-sig').splitlines(keepends=True):
    if line.startswith('+++ b/'):
        current=line[len('+++ b/'):].strip()
        sections[current]=[]
    elif line.startswith('--- '):
        current=None
    elif current and line.startswith('+') and not line.startswith('+++'):
        sections[current].append(line[1:])
for path,pin in pins.items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==pin
    assert ''.join(sections[path])==(root/path).read_text(encoding='utf-8-sig')
phase1=Path(__file__).resolve().parent.parent
old_manifest=json.loads((phase1/'phase1-manifest.json').read_text(encoding='utf-8-sig'))
for record in old_manifest['files']:
    assert hashlib.sha256((phase1/record['path']).read_bytes()).hexdigest()==record['sha256']
print(json.dumps({'source_pins':pins,'raw_author_evidence':raw_checks,'actual_diff_final_primary_text_equal':True,'phase1_files_unchanged':len(old_manifest['files']),'reviewer_runtime':{'python':platform.python_version(),'executable':sys.executable},'author_suite_executed_by_reviewer':False},indent=2))


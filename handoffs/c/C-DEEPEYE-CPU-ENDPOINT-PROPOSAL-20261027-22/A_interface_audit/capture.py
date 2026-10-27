"""Narrow endpoint source GET recorder; no project imports or endpoint execution."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
MAIN = ROOT / '.local/main-20261015-01a14025'
WT = ROOT / '.local/deepeye-implementation-c'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def get(label, endpoint):
    args = ['gh', 'api', endpoint]
    p = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=60)
    d = OUT / 'GET'
    d.mkdir(exist_ok=True)
    (d / (label + '.stdout.json')).write_bytes(p.stdout)
    (d / (label + '.stderr.txt')).write_bytes(p.stderr)
    write_json(d / (label + '.command.json'), {
        'args': args, 'exit_code': p.returncode,
        'utc': datetime.now(timezone.utc).isoformat(),
        'stdout_sha256': sha(p.stdout), 'stderr_sha256': sha(p.stderr),
        'activity': 'read-only source API GET',
    })
    if p.returncode:
        raise RuntimeError('Read-only API GET failed: ' + label)
    return json.loads(p.stdout)

assignment = json.loads((OUT.parent / 'assignment.json').read_bytes())
mine = [x for x in assignment['assignments']
        if x['actual_agent_id'] == '/root/sim_em_contract_audit'][0]
if mine['work_id'] != 'C-ENDPOINT-A-INTERFACE-AUDIT-20261027-v1':
    raise RuntimeError('Assignment binding mismatch')
scope = json.loads((WT / 'docs/competition/deepeye-2026/immutable_scope.json').read_bytes())
req = json.dumps(scope['requirements'], ensure_ascii=False,
                 sort_keys=True, separators=(',', ':')).encode()
if sha(req) != assignment['requirements_sha256']:
    raise RuntimeError('H01-H15 requirement identity mismatch')
write_json(OUT / 'identity.json', {
    'task_id': assignment['task_id'], 'task_version': assignment['task_version'],
    'work_id': mine['work_id'], 'actual_canonical_agent_id': mine['actual_agent_id'],
    'actual_main_thread_id': assignment['actual_main_thread_id'],
    'contract_id': assignment['contract_id'], 'contract_source': assignment['contract_source'],
    'requirements_sha256': sha(req),
    'requirements': [x['id'] for x in scope['requirements']],
    'frozen_design_commit': assignment['frozen_design_commit'],
    'exclusive_files': mine['ownership'], 'product_write_ownership': False,
    'board_operator': 'A', 'utc': datetime.now(timezone.utc).isoformat(),
})
pr = get('A-pr24-current', 'repos/carolwjade/CarlandFPGA/pulls/24')
comment = get('A-original-C21-request-6416227814',
              'repos/carolwjade/CarlandFPGA/issues/comments/6416227814')
head = pr['head']['sha']
old = MAIN / 'cpu-package-20261024/cpu_host_interface/tree.stdout.json'
if head == '5c192f34bad064b14e238747c2c569347257a62c':
    tree_raw = old.read_bytes()
    tree = json.loads(tree_raw)
    tree_origin = 'same exact A head; prior raw nontruncated tree reused'
    if tree['sha'] != head or tree.get('truncated'):
        raise RuntimeError('Old A tree mismatch')
else:
    tree = get('A-current-tree', 'repos/' + pr['head']['repo']['full_name']
               + '/git/trees/' + head + '?recursive=1')
    tree_origin = 'new current A head; actual source tree GET'
if tree.get('truncated'):
    raise RuntimeError('Current A tree is truncated; cannot infer selected file set')
selected = [x for x in tree['tree'] if x['type'] == 'blob'
            and x['path'].startswith(('competition/deepeye/integration/',
                                      'competition/deepeye/docs/',
                                      'competition/deepeye/simulation/authority/',
                                      'competition/deepeye/simulation/isolation/'))
            and any(s in x['path'].lower() for s in
                    ['invocation', 'endpoint', 'actor_composition', 'factory',
                     'actor_ipc', 'ipc_framing', 'runtime_factory'])]
write_json(OUT / 'A-current-selected-tree.json', {
    'head_commit': head, 'head_repo': pr['head']['repo']['full_name'],
    'head_ref': pr['head']['ref'], 'tree_origin': tree_origin,
    'tree_sha': tree['sha'], 'files': selected,
})
print(json.dumps({'A_head': head, 'head_repo': pr['head']['repo']['full_name'],
                  'selected_paths': [x['path'] for x in selected],
                  'A_comment_body': comment['body']}, ensure_ascii=False))

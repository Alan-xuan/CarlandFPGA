"""Record completed local evidence and actual worker release as the final write."""
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    replay = json.loads((HERE/'replay_results.json').read_bytes())
    assert replay['status'] == 'passed' and replay['total_checks'] == 81
    commands = sorted((HERE/'captures').glob('*.command.json'))
    exits = {p.stem.replace('.command', ''):json.loads(p.read_bytes())['exit_code'] for p in commands}
    assert exits['replay-final'] == 0 and exits['provenance-02'] == 0 and exits['scope-01'] == 0
    release = dict(schema=1, task_id='DEEPEYE-IMPLEMENTATION-20261014', task_version=1,
                   work_id='C-independent-trace-candidate-decoder-20261018-v1',
                   actual_agent_id='/root/trace_decoder', state='released',
                   released_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   ownership=['competition/deepeye/evidence/ai/trace_candidate_decode/**'],
                   released_to='parent /root; current C main 01a14025-4dfd-7ec3-aebb-57be48daba59',
                   reason='Assigned offline implementation and evidence complete; final handoff follows with no more writes.',
                   commands_all_finished=True, background_jobs_started=False, child_agents_started=False,
                   no_further_product_or_evidence_writes=True, command_exit_codes=exits,
                   runtime_acceptance='not_run', physical_board='not_run', production_type7='remains_rejected')
    (HERE/'release.json').write_text(json.dumps(release, indent=2)+'\n', encoding='utf-8', newline='\n')
    files = []
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.name != 'artifact_manifest.json':
            data = path.read_bytes()
            files.append(dict(path=path.relative_to(HERE).as_posix(), bytes=len(data),
                              sha256=hashlib.sha256(data).hexdigest(),
                              git_blob_sha1=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()))
    manifest = dict(schema=1, agent_id='/root/trace_decoder', file_count=len(files),
                    manifest_excludes_itself=True, files=files)
    destination = HERE/'artifact_manifest.json'
    destination.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(status='released', files=len(files),
                          artifact_manifest_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                          release_sha256=hashlib.sha256((HERE/'release.json').read_bytes()).hexdigest()), sort_keys=True))


if __name__ == '__main__':
    main()

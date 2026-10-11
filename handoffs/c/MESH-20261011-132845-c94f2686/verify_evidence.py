"""Validate immutable node C receipts; makes no network or model calls."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def read(n): return json.loads((ROOT/(n+'.json')).read_text(encoding='utf-8'))
def check(test, label):
    if not test: raise AssertionError(label)
    print('PASS '+label)

child=read('child-result')[0]
check(child['status']=='completed' and child['result']['model']=='deepseek-flash'
      and child['result']['provider']=='deepseek' and child['result']['reasoning_effort']=='max','real Flash/max completed metadata')
check(child['result']['text']==read('child-golden')['expected']=='C_FLASH_SUM=34849','independent arithmetic oracle')
for n in ('child-duplicate','cross-entrance-duplicate'):
    d=read(n);check(d['duplicate'] and d['job_id']==child['job_id'],n)
check(read('ownership-conflict')['guard_rejected'],'active ownership overlap rejected')
for n in ('text-readback','human-group-readback'):
    check(all(x['sent_at'] and x['platform_message_id'] and x['readback_matches'] for x in read(n)),n)
human=read('human-main-result')
check(human['status']=='completed' and human['result']['text']=='ACK_c94f2686_C','real human C ingress completed')
route2=read('main-result-2-terminal');v2=read('main-result-recovery-v2')
check(route2['status']==v2['status']=='completed','both final route probes completed')
check(route2['result']['thread_id']==v2['result']['thread_id'],'same task main thread reused')
check((route2['result']['model'],route2['result']['reasoning_effort'])==('gpt-6-astra','ultra')
      and (v2['result']['model'],v2['result']['reasoning_effort'])==('gpt-5.6-luna','low'),'actual completed model and effort switch')
check(read('main-result-1')['status']=='interrupted' and not read('main-duplicate-1')['queued'],'interrupted request not replayed')
f=read('astra-file-roundtrip')
check(f['matches'] and f['sha256']==f['source_sha256']==hashlib.sha256((ROOT/'C-file-transfer.txt').read_bytes()).hexdigest(),'Astra file bytes roundtrip')
check(read('astra-receive')['matches_announced'],'A package downloaded by C matches published hash')
check(read('report')['overall']=='BLOCKED','no false three-node success claim')
manifest=ROOT/'manifest.json'
if manifest.exists():
    for entry in json.loads(manifest.read_text(encoding='utf-8'))['files']:
        p=ROOT/entry['path'];check(p.stat().st_size==entry['size'] and hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],'hash '+entry['path'])

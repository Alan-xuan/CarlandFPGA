"""Check the human-pinned requirements; does not establish runtime acceptance."""
from pathlib import Path
import argparse,hashlib,json,sys

def verify(base,expected_sha,book=None,plan=None):
    data=json.loads((base/'immutable_scope.json').read_text(encoding='utf-8'))
    req=data['requirements']
    actual=hashlib.sha256(json.dumps(req,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if actual!=expected_sha or data['requirements_sha256']!=expected_sha:
        raise ValueError('HUMAN_LOCK_HASH_MISMATCH: stop; only new explicit human instruction can amend')
    if [x['id'] for x in req]!=[f'H{i:02}' for i in range(1,16)]:
        raise ValueError('HUMAN_LOCK_REQUIREMENT_SET_MISMATCH')
    md=(base/'immutable_scope.md').read_text(encoding='utf-8')
    for x in req:
        if x['must'] not in md:raise ValueError('HUMAN_LOCK_MD_MISMATCH:'+x['id'])
    human=md.split('## 原始人类指令\n\n',1)[1].strip()
    if hashlib.sha256(human.encode()).hexdigest()!=data['human_instruction_sha256']:
        raise ValueError('HUMAN_AUTHORITY_TEXT_MISMATCH')
    if book:
        text=book.read_text(encoding='utf-8')
        for x in req:
            if x['id'] not in text:raise ValueError('BOOK_COVERAGE_MISSING:'+x['id'])
    if plan:
        p=json.loads(plan.read_text(encoding='utf-8'))
        if p.get('immutable_scope_sha256')!=expected_sha:raise ValueError('PLAN_LOCK_MISMATCH')
        for x in req:
            for card in x['acceptance_cards']:
                if card not in p['tasks']:raise ValueError('PLAN_CARD_MISSING:'+card)
    return {'status':'passed','scope':'human requirement identity and trace coverage only','contract':data['contract_id'],'requirements':len(req),'requirements_sha256':actual,'runtime_acceptance':'not_run'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-sha',required=True);p.add_argument('--base',type=Path,default=Path(__file__).parent);p.add_argument('--book',type=Path);p.add_argument('--plan',type=Path);a=p.parse_args()
    try:print(json.dumps(verify(a.base,a.expected_sha,a.book,a.plan),ensure_ascii=False))
    except (ValueError,KeyError,FileNotFoundError) as e:
        print(json.dumps({'status':'failed','error':str(e)},ensure_ascii=False));sys.exit(1)

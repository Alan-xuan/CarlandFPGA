"""Corrected NEW aggregate-output control only; run01 malformed padding retained.
CLI: python independent_aggregate_check.py PUBLIC_DIR EXPECTED_SHA OUTPUT_DIR
"""
import hashlib,json,pathlib,sys,types
from independent_c31_fixture import c31_fixture,sha

def encode(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

def main():
    source=pathlib.Path(sys.argv[1])/'root_book_projection_v1.py'; expected=sys.argv[2]; out=pathlib.Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    data=source.read_bytes();assert hashlib.sha256(data).hexdigest()==expected
    r=c31_fixture(tuple(range(9050,10001,50)));r['enabled']=False
    wanted={x['adc_book_source_sha256'] for x in r['external']['captures']}
    r['book']['samples']=[s for s in r['book']['samples'] if s['source_sha256'] in wanted]
    for i,s in enumerate(r['book']['samples']):s['source_count']=i+1
    changes={}
    for rec in r['external']['captures']:
        old=rec['capture_sha256'];rec['capture_raw']=rec['capture_raw'][:-1]+' '*9000+'\n';rec['capture_sha256']=sha(rec['capture_raw']);changes[old]=rec['capture_sha256']
        assert rec['capture_raw'].count('\n')==1 and rec['capture_raw'].endswith('\n') and len(rec['capture_raw'])<=16384
    for c in r['external']['history']+[r['external']['candidate']]:c['observation_identity']['capture_sha256']=changes[c['observation_identity']['capture_sha256']]
    for rec in r['external']['captures']:rec['em_origin_capture_sha256']=changes[rec['em_origin_capture_sha256']]
    raw=encode(r);assert len(raw)<1048576;(out/'input.json').write_bytes(raw)
    m=types.ModuleType('independent_c31_aggregate');m.__file__=str(source.resolve());exec(compile(data,str(source),'exec'),m.__dict__)
    calls={'c30_json':0,'core':0}
    def profile(frame,event,arg):
        if event=='call':
            if frame.f_code is m._C30.recommend_json.__code__:calls['c30_json']+=1
            if frame.f_code is m._C30._ORIGINAL.__code__:calls['core']+=1
    sys.setprofile(profile)
    try:
        output=m.project_json(raw);actual='RETURN';message=''
    except Exception as exc:
        actual='REJECT' if isinstance(exc,m.Rejected) else type(exc).__name__;message=str(exc);output=encode({'exception':type(exc).__name__,'message':message})
    finally:sys.setprofile(None)
    (out/'output.json').write_bytes(output)
    ok=actual=='REJECT' and message=='C31 encoded output budget' and calls=={'c30_json':1,'core':0}
    print(json.dumps(dict(name='corrected_aggregate_output_wrapper_budget',passed=ok,actual=actual,message=message,calls=calls,input_bytes=len(raw),input_sha256=hashlib.sha256(raw).hexdigest(),output_bytes=len(output),output_sha256=hashlib.sha256(output).hexdigest()),indent=2));return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())

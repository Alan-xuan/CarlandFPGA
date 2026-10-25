"""Independent small real-model stream check; never invokes old batch runner."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
from unittest.mock import patch

def digest(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return json.dumps(value,allow_nan=False,separators=(',',':')).encode()+b'\n'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--oracle',type=Path,required=True)
    parser.add_argument('--expected-stream-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=args.root/'competition/deepeye/ai_pc/cpu_package/stream_core.py'
    assert digest(source.read_bytes())==args.expected_stream_sha256
    raw_oracle=args.oracle.read_bytes()
    assert digest(raw_oracle)=='d51715b564fd09803c69e9995de8b834fdbab0962fe0a6f8135a863fe59e2a44'
    oracle=json.loads(raw_oracle)
    sys.path.insert(0,str(args.root/'competition/deepeye'))
    from ai_pc.cpu_package.stream_core import FrozenForceStream,StreamError
    core=FrozenForceStream()
    records=[s.encode() for s in oracle['raw_records']]
    binding=json.loads(records[0])
    token=core.start_session(generation=1,epoch=0,run_id=binding['run_id'])
    prefix=b''
    results=[]
    checks=[]
    maximum_difference=0.0
    for index,raw in enumerate(records):
        if index==0:
            result=core.observe(token,raw)
        else:
            with patch('builtins.open',side_effect=AssertionError('observation attempted file read')), patch.object(Path,'open',side_effect=AssertionError('observation attempted Path.open')):
                result=core.observe(token,raw)
        prefix+=raw
        expected=oracle['expected_predictions'][index]
        assert result.feature_tensor_sha256==expected['feature_tensor_sha256']
        assert result.input_prefix_sha256==expected['input_prefix_sha256']==digest(prefix)
        assert result.sequence==expected['window']['latest_sequence']==json.loads(raw)['sequence']
        assert result.binding._asdict()==expected['binding']
        assert result.predicted_class_index==expected['predicted_class_index']
        assert list(result.class_order)==oracle['class_order']
        difference=max(abs(a-b) for a,b in zip(result.probabilities,expected['probabilities']))
        assert difference<=oracle['absolute_probability_tolerance']
        maximum_difference=max(maximum_difference,difference)
        assert len(result.probabilities)==12 and len(result.encoded)<=8192
        payload=json.loads(result.encoded)
        assert payload['movement_authorized'] is False and payload['motion_bytes'] is None
        forbidden={'observed_seq','BOOT','boot_id','sampling_age','model_candidate','motion_request'}
        assert not forbidden.intersection(payload)
        assert core.latest_result(token) is result
        results.append(result)
    checks.append('3 real selected-prefix parity; later2 observations fenced against file reads')
    previous=results[-1]
    old_outputs=[r.encoded for r in results]
    before=core.state()

    def reject(call,expected_code=None):
        try: call()
        except StreamError as exc:
            assert len(str(exc))<=256
            if expected_code is not None: assert exc.code==expected_code,(exc.code,expected_code)
        else: raise AssertionError('expected bounded rejection')
        assert core.state()==before
        assert core.latest_result(token) is previous

    reject(lambda:core.observe(token,b'{bad future suffix'))
    wrong=json.loads(records[-1]); wrong['label']=30000
    reject(lambda:core.observe(token,encoded(wrong)))
    wrong=json.loads(records[-1]); wrong['sequence']+=1; wrong['value_0']=1e45; wrong['valid_0']=True
    reject(lambda:core.observe(token,encoded(wrong)),'feature_invalid')
    reject(lambda:core.observe(token,bytearray(records[-1])),'record_limit')
    reject(lambda:core.observe(token,memoryview(records[-1])),'record_limit')
    class LyingBytes(bytes):
        def __len__(self):return 1
    reject(lambda:core.observe(token,LyingBytes(b'x'*16385)),'record_limit')
    copied=token._replace(epoch=token.epoch)
    assert copied==token and copied is not token
    reject(lambda:core.observe(copied,records[-1]),'stale_session')
    reject(lambda:core.end_session(copied),'stale_session')
    checks.append('8 bounded nonmutating future/overflow/type/stale rejections')

    duplicate=(json.dumps(json.loads(records[-1]),sort_keys=True,indent=1)+'\r\n').encode()
    repeated=core.observe(token,duplicate)
    prefix+=duplicate
    assert repeated.input_prefix_sha256==digest(prefix)
    assert repeated.feature_tensor_sha256==previous.feature_tensor_sha256
    assert repeated.probabilities==previous.probabilities
    assert repeated.metadata.accepted_observations==previous.metadata.accepted_observations
    assert repeated.metadata.idempotent_repeats==previous.metadata.idempotent_repeats+1
    assert repeated.delivery_index==previous.delivery_index+1
    assert [r.encoded for r in results]==old_outputs
    checks.append('reencoded semantic duplicate advances exact raw prefix without new acquisition')

    good=json.loads(records[-1]); good['sequence']+=1
    good_raw=encoded(good)
    continued=core.observe(token,good_raw)
    prefix+=good_raw
    assert continued.sequence==good['sequence'] and continued.input_prefix_sha256==digest(prefix)
    assert continued.metadata.accepted_observations==4
    checks.append('valid continuation at previously rejected overflow sequence succeeds')
    end=core.end_session(token)
    assert end.input_prefix_sha256==digest(prefix) and end.movement_authorized is False
    second=core.start_session(generation=2,epoch=1,run_id=binding['run_id'])
    before_new=core.state()
    try:core.observe(token,records[0])
    except StreamError as exc:assert exc.code=='stale_session'
    else:raise AssertionError('ended token accepted')
    assert core.state()==before_new
    first_again=core.observe(second,records[0])
    assert first_again.feature_tensor_sha256==results[0].feature_tensor_sha256
    assert first_again.input_prefix_sha256==digest(records[0])
    assert first_again.metadata.accepted_observations==1 and first_again.metadata.missing_slots==127
    assert core.state().lifetime_deliveries==6
    core.end_session(second)
    checks.append('explicit same-label cold restart with new local IDs; ended token cannot overwrite')
    assert [r.encoded for r in results]==old_outputs
    torch=sys.modules['torch']
    report={'passed':True,'stream_source_sha256':args.expected_stream_sha256,
        'oracle_sha256':digest(raw_oracle),'actual_model_forwards':5,
        'accepted_deliveries':6,'selected_parity_records':3,
        'maximum_selected_probability_abs_difference':maximum_difference,
        'runtime':{'python':platform.python_version(),'torch':torch.__version__,
            'CPU_threads':torch.get_num_threads(),'device':'cpu'},
        'checks':checks,'real_outputs':[json.loads(r.encoded) for r in results],
        'old_runner_execute_training_heldout_benchmark':False,
        'runtime_or_formal_acceptance':False,'movement_authorized':False}
    with args.output.open('xb') as f:f.write(json.dumps(report,ensure_ascii=False,indent=2).encode()+b'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='real_outputs'},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())

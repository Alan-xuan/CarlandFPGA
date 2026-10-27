"""Independent C22 pure-byte controls. No endpoint process or learned model."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import struct
import sys
from unittest.mock import patch


def main():
    args=argparse.ArgumentParser()
    args.add_argument('--root',type=Path,required=True)
    args.add_argument('--record',type=Path,required=True)
    args.add_argument('--reply',type=Path,required=True)
    args.add_argument('--output',type=Path,required=True)
    a=args.parse_args()
    sys.path.insert(0,str(a.root/'competition/deepeye'))
    from ai_pc.cpu_package import process_endpoint as endpoint
    from ai_pc.cpu_package import endpoint_protocol as protocol
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    record=a.record.read_bytes(); recorded=a.reply.read_bytes()
    assert len(record)==354 and sha(record)=='9c9200453ca7feab036ee9e41b9b78f9b61df5d672792961379d5daa920d1eb8'
    assert len(recorded)==2007 and recorded[-1:]==b'\n' and sha(recorded)=='3cbffc7619558619bde6f1b25e53f3cb7225855b79aea45417e2fcf33cd4034b'
    expected_run=json.loads(record)['run_id']
    identity=dict(operation_id='ROOT-SYNTHETIC',request_hash='1'*64,tested_commit='2'*40,
                  package_manifest_sha256='3'*64,run_id='ROOT-SYNTH-A-RUN',
                  invocation_id=31,actor_instance_id='ROOT-SYNTH-ACTOR')
    H=struct.Struct('>4sBBHII')

    def frame(payload,index=1,kind=1,variant=True):
        value=dict(identity=dict(identity,invocation_id=30+index),frame_index=index,payload_sha256=sha(payload))
        meta=json.dumps(value,ensure_ascii=True,sort_keys=False,indent=1).encode() if variant else json.dumps(value,sort_keys=True,separators=(',',':')).encode()
        return H.pack(b'C22E',1,kind,0,len(meta),len(payload))+meta+payload

    def decode_reply(raw,request,payload,kind):
        magic,version,k,flags,m,p=H.unpack(raw[:16])
        assert (magic,version,k,flags)==(b'C22E',1,kind,0)
        assert len(raw)==16+m+p and m<=2048 and p<=4096
        meta=json.loads(raw[16:16+m]); exact=raw[16+m:]
        assert set(meta)=={'identity','frame_index','request_frame_sha256','request_payload_sha256','payload_sha256'}
        request_meta=json.loads(request[16:16+H.unpack(request[:16])[4]])
        assert meta['identity']==request_meta['identity'] and meta['frame_index']==request_meta['frame_index']
        assert meta['request_frame_sha256']==sha(request)
        assert meta['request_payload_sha256']==request_meta['payload_sha256']
        assert meta['payload_sha256']==sha(payload) and exact==payload
        assert meta['identity']['request_hash'] not in (sha(request),request_meta['payload_sha256'])
        return len(raw)

    class PrivateCore:
        def __init__(self,payload=recorded,expected=record):
            self.token=object(); self.starts=[]; self.observations=[]; self.ends=0
            self.payload,self.expected=payload,expected
        def start_session(self,**kw):
            assert kw==dict(generation=1,epoch=0,run_id=expected_run)
            self.starts.append(kw); return self.token
        def observe(self,token,raw):
            assert token is self.token and type(raw) is bytes and raw==self.expected
            self.observations.append(raw); return SimpleNamespace(encoded=self.payload)
        def end_session(self,token):
            assert token is self.token; self.ends+=1
            assert self.ends==1
            return SimpleNamespace(encoded=b'{"kind":"ROOT-PRIVATE-FAKE-END"}\n')

    class PrivateIO:
        def __init__(self,raw,mode='exact'):
            self.raw,self.pos,self.mode=raw,0,mode; self.events=[]; self.writes=[]
        def read(self,size):
            self.events.append(('read',self.pos,size))
            n=min(size,7,len(self.raw)-self.pos)
            out=self.raw[self.pos:self.pos+n]; self.pos+=n; return out
        def write(self,raw):
            self.events.append(('write',self.pos,len(raw))); self.writes.append(raw)
            if self.mode=='none':return None
            if self.mode=='short':return 7
            if self.mode=='zero':return 0
            if self.mode=='exception':raise OSError('private unknown write completion')
            return len(raw)

    def run(raw,payload=recorded,mode='exact'):
        io=PrivateIO(raw,mode); core=PrivateCore(payload)
        with patch.object(endpoint,'_new_core',return_value=core) as ctor:
            driver=endpoint.EndpointDriver(io.read,io.write); result=driver.run()
        assert ctor.call_count==1
        assert len(core.starts)==1 and len(core.observations)==1 and core.ends==1
        before=(io.pos,len(io.events),len(io.writes)); again=driver.run()
        assert again.exit_code!=0 and (io.pos,len(io.events),len(io.writes))==before
        return io,core,result

    checks=[]; first=frame(record); end=frame(b'',2,2)
    io,core,result=run(first+end+b'POISON-UNREAD-TAIL')
    assert result.exit_code==0 and result.responses_emitted==2 and io.pos==len(first+end)
    assert identity['run_id']!=expected_run
    response_bytes=decode_reply(io.writes[0],first,recorded,129)
    decode_reply(io.writes[1],end,b'{"kind":"ROOT-PRIVATE-FAKE-END"}\n',130)
    writes=[e for e in io.events if e[0]=='write']
    assert writes[0][1]==len(first) and writes[1][1]==len(first+end)
    checks.append('original_record_binding_vs_A_identity_exact2007LF_and_noncanonical_frame_hash')

    poison=H.pack(b'BAD!',1,1,0,10,1)
    io,core,result=run(first+poison)
    assert result.exit_code!=0 and len(io.writes)==1 and result.responses_emitted==1
    assert next(e for e in io.events if e[0]=='write')[1]==len(first)
    decode_reply(io.writes[0],first,recorded,129)
    checks.append('valid_reply_written_before_poison_header_and_not_rewritten')

    for mode in ('none','short','zero','exception'):
        io,core,result=run(first+end,mode=mode)
        assert result.exit_code!=0 and result.responses_emitted==0
        assert io.pos==len(first) and len(io.writes)==1
        assert io.events[-1][0]=='write'
        checks.append('single_write_no_retry_or_future_read_'+mode)

    full4096=b'R'*4095+b'\n'
    io,core,result=run(first+end,payload=full4096)
    assert result.exit_code==0
    size4096=decode_reply(io.writes[0],first,full4096,129)
    assert size4096>4096 and size4096<=6160
    checks.append('reply4096_includes_LF_and_hash_with_independent_envelope_overhead')
    io,core,result=run(first+end,payload=b'R'*4096+b'\n')
    assert result.exit_code!=0 and not io.writes and io.pos==len(first)
    checks.append('reply4097_retires_before_any_write')

    compact=frame(record,variant=False); metadata_size=H.unpack(compact[:16])[4]
    raw_size=16384-16-metadata_size
    padded=record+b' '*(raw_size-len(record)); boundary=frame(padded,variant=False)
    assert len(boundary)==16384
    request=protocol.decode_request(boundary)
    assert request.payload==padded and request.frame_sha256==sha(boundary)
    for invalid in (frame(padded+b' ',variant=False),frame(b'R'*16384,variant=False)):
        try:protocol.decode_request(invalid)
        except protocol.ProtocolError:pass
        else:raise AssertionError('whole-frame cap not applied')
    checks.append('whole_request16384_includes_metadata_header_and_rejects_payload16384_plus_header')

    assert not any(n=='torch' or n.startswith('torch.') for n in sys.modules)
    assert 'ai_pc.cpu_package.stream_core' not in sys.modules
    result={'passed':True,'scope':'independent pure bytes and private fake core; no OS endpoint/model transport',
        'checks':checks,'check_groups':len(checks),'actual_A_recorded_reply_bytes':len(recorded),
        'actual_A_recorded_reply_sha256':sha(recorded),'recorded2007_response_total_bytes':response_bytes,
        'synthetic4096_response_total_bytes':size4096,'max_request_for_this_identity_payload_bytes':raw_size,
        'Torch_imported':False,'real_model_constructors':0,'learned_forwards':0,'endpoint_process_launches':0,
        'active_jobs':[],'formal_acceptance':'not_run'}
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))


if __name__=='__main__':main()

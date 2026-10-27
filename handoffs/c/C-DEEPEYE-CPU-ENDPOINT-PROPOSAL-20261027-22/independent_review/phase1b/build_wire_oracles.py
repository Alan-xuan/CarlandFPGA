"""Independent C22 wire-oracle preparation, not endpoint implementation tests.
No evolving endpoint import, model/scaler construction/forward, or process launch.
"""
import hashlib, json, os, struct, sys
from pathlib import Path
from datetime import datetime, timezone
NODE=Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c")
WT=NODE/".local/deepeye-implementation-c"
BASE=Path(__file__).resolve().parent
OUT=BASE/"r2"
OUT.mkdir()
REVIEW=BASE.parent
DESIGN=NODE/".local/main-20261015-01a14025/endpoint-20261027/main/design-v2.md"
DESIGN_SHA="437aedcf1f09f11109632f4f101a6851c07a2ba2a6f65939fe35cbf92540d07f"
h=lambda b:hashlib.sha256(b).hexdigest()
assert h(DESIGN.read_bytes())==DESIGN_SHA
HEADER=struct.Struct(">4sBBHII")
assert HEADER.size==16
RAW=(REVIEW/"original-first-record.raw").read_bytes()
REPLY=(REVIEW/"A-recorded-reply.exact.bin").read_bytes()
assert len(RAW)==354 and h(RAW)=="9c9200453ca7feab036ee9e41b9b78f9b61df5d672792961379d5daa920d1eb8"
assert len(REPLY)==2007 and h(REPLY)=="3cbffc7619558619bde6f1b25e53f3cb7225855b79aea45417e2fcf33cd4034b"
def cj(obj):
    return json.dumps(obj,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")
def put(name,b):
    with (OUT/name).open("xb") as f:f.write(b);f.flush();os.fsync(f.fileno())
def emit(name,obj):
    put(name,(json.dumps(obj,ensure_ascii=True,indent=2,allow_nan=False)+"\n").encode())
def header(kind,m,p,flags=0,version=1,magic=b"C22E"):
    a=HEADER.pack(magic,version,kind,flags,m,p)
    b=magic+bytes([version,kind])+flags.to_bytes(2,"big")+m.to_bytes(4,"big")+p.to_bytes(4,"big")
    assert a==b and len(a)==16
    return a
IDENTITY={"operation_id":"SYNTH-C22-BYTE-ONLY","request_hash":"1"*64,"tested_commit":"2"*40,
          "package_manifest_sha256":"3"*64,"run_id":"SYNTH-A-RUN","invocation_id":1,
          "actor_instance_id":"SYNTH-ACTOR"}
def identity(invocation):
    return {**IDENTITY,"invocation_id":invocation}
def request(kind,index,invocation,payload,*,metadata_raw=None):
    md={"identity":identity(invocation),"frame_index":index,"payload_sha256":h(payload)}
    metadata=cj(md) if metadata_raw is None else metadata_raw
    assert json.loads(metadata)==md
    frame=header(kind,len(metadata),len(payload))+metadata+payload
    return frame,md,metadata
def response(kind,request_frame,request_md,payload,*,metadata_raw=None):
    md={"identity":request_md["identity"],"frame_index":request_md["frame_index"],
        "request_frame_sha256":h(request_frame),"request_payload_sha256":request_md["payload_sha256"],
        "payload_sha256":h(payload)}
    metadata=cj(md) if metadata_raw is None else metadata_raw
    assert json.loads(metadata)==md
    return header(kind,len(metadata),len(payload))+metadata+payload,md,metadata

fixtures=[]
def fixture(name,b,kind,expectation):
    put(name,b)
    fixtures.append({"path":name,"bytes":len(b),"sha256":h(b),"kind":kind,"expectation":expectation})
obs,obs_md,obs_meta=request(1,1,1,RAW)
res,res_md,res_meta=response(129,obs,obs_md,REPLY)
end,end_md,end_meta=request(2,2,2,b"")
# No original raw A end receipt supplied; this is explicitly synthetic.
end_payload=b'{"synthetic":"END-RECEIPT-BYTES-ONLY"}\n'
ended,ended_md,_=response(130,end,end_md,end_payload)
fixture("observe-1.frame",obs,"synthetic envelope around original354B record","accept first OBSERVE")
fixture("result-1.frame",res,"synthetic correlation metadata + unchanged actual2007B A payload","one write must equal these bytes exactly")
fixture("end-2.frame",end,"synthetic END identity/index with empty payload","accept after OBSERVE; return without tail read")
fixture("ended-2.frame",ended,"synthetic END receipt and synthetic envelope","byte/framing oracle only, not actual A receipt")

# Same parsed first request but different original JSON serialization.
noncanonical=json.dumps(obs_md,ensure_ascii=True,sort_keys=False,separators=(", ",": ")).encode("ascii")
variant,variant_md,_=request(1,1,1,RAW,metadata_raw=noncanonical)
variant_response,_,_=response(129,variant,variant_md,REPLY)
assert h(variant)!=h(obs)
assert json.loads(noncanonical)==obs_md
assert h(RAW)==res_md["request_payload_sha256"] and res_md["payload_sha256"]==h(REPLY)
assert len({IDENTITY["request_hash"],h(obs),h(RAW),h(REPLY)})==4
fixture("observe-meta-variant.frame",variant,"noncanonical equivalent request metadata","accept; full raw frame hash differs")
fixture("result-meta-variant.frame",variant_response,"same payload/identity but different request_frame_sha256","must not substitute canonical-request digest")

# Full input cap binds header+metadata+payload, not only original payload.
capacity=16384-16-len(obs_meta)
assert 354<capacity<16384
raw_at_capacity=RAW+b" "*(capacity-len(RAW))
at_limit,_,at_limit_meta=request(1,1,1,raw_at_capacity)
assert len(at_limit)==16384 and len(at_limit_meta)==len(obs_meta)
too_large,_,_=request(1,1,1,raw_at_capacity+b" ")
assert len(too_large)==16385
payload_max_but_total_bad,_,_=request(1,1,1,(REVIEW/"synthetic-record-16384.raw").read_bytes())
fixture("input-total-16384.frame",at_limit,"synthetic whitespace-padded13field record","accept framing/total-bound")
fixture("input-total-16385.frame",too_large,"synthetic total exceeds cap though payload below16384","reject before core")
fixture("raw16384-total-bad.frame",payload_max_but_total_bad,"synthetic raw payload16384 plus metadata/header","reject total cap before core")

# Metadata parser order is unconstrained; whitespace counts toward its size.
meta2048=obs_meta+b" "*(2048-len(obs_meta))
meta2049=meta2048+b" "
in2048,_,_=request(1,1,1,RAW,metadata_raw=meta2048)
in2049,_,_=request(1,1,1,RAW,metadata_raw=meta2049)
fixture("input-meta-2048.frame",in2048,"synthetic valid noncanonical metadata2048","accept framing/meta bound")
fixture("input-meta-2049.frame",in2049,"synthetic valid metadata2049","reject before core")

for n in (4095,4096,4097):
    payload=(REVIEW/("synthetic-reply-%d.bin"%n)).read_bytes()
    frame,_,_=response(129,obs,obs_md,payload)
    fixture("reply-%d.frame"%n,frame,"synthetic padded reply; never learned output",
            "accept payload bound" if n<=4096 else "reject before write")
max_payload=(REVIEW/"synthetic-reply-4096.bin").read_bytes()
_,_,max_canonical_meta=response(129,obs,obs_md,max_payload)
max_md=max_canonical_meta+b" "*(2048-len(max_canonical_meta))
max_frame,_,_=response(129,obs,obs_md,max_payload,metadata_raw=max_md)
assert len(max_frame)==6160
fixture("response-6160.geometry",max_frame,"synthetic padded metadata+payload geometry, not actual canonical encoder emission",
        "total geometry bound16+2048+4096; no transport/adoption claim")

# Endpoint syntax-negative frames are intentionally not repaired/rehashed.
bad_payload=bytearray(obs);bad_payload[-1]^=1
fixture("bad-payload-hash.frame",bytes(bad_payload),"synthetic tamper","reject payload hash before core")
for name,args in [
    ("bad-magic",{"magic":b"D22E"}),("bad-version",{"version":2}),
    ("bad-flags",{"flags":1}),("bad-kind",{}),
]:
    kind=3 if name=="bad-kind" else 1
    b=header(kind,len(obs_meta),len(RAW),**args)+obs_meta+RAW
    fixture(name+".frame",b,"synthetic invalid header","reject before core")
for name,md in [
    ("bad-first-index",{**obs_md,"frame_index":0}),
    ("bad-bool-index",{**obs_md,"frame_index":True}),
    ("bad-bool-invocation",{**obs_md,"identity":{**IDENTITY,"invocation_id":True}}),
    ("bad-extra-key",{**obs_md,"BOOT":"forbidden"}),
]:
    b=cj(md)
    fixture(name+".frame",header(1,len(b),len(RAW))+b+RAW,"synthetic invalid metadata","reject before core")

# First binding uses actual pinned parsing, but fake constructor only.
parser_pins=[
    ("competition/deepeye/ai_pc/cpu_package/runner.py","92114790259b7e35e8bf7b1a0519f0e3f68da52729d08b5b9862c992deae70af"),
    ("competition/deepeye/ai_pc/model/curve_input.py","c017729a2d5717ff2bbf5a6c591320519c415ac10068b4cee19b3136913d848c"),
]
for rel,digest in parser_pins:
    with (WT/rel).open("rb") as f:b=f.read(2097153)
    assert len(b)<=2097152 and h(b)==digest
sys.path.insert(0,str(WT/"competition/deepeye"))
from ai_pc.cpu_package.runner import strict_json
from ai_pc.model.curve_input import CurveObservation
FIXED_PREPROC="cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef"
def parse_original_binding(raw_bytes):
    observation=CurveObservation.from_mapping(strict_json(raw_bytes))
    binding=observation.binding
    assert binding.source_domain=="geo_replay"
    assert binding.profile_id=="force_curve_v1"
    assert binding.preprocessing_sha256==FIXED_PREPROC
    assert type(binding.run_id) is str and 1<=len(binding.run_id.encode("utf8"))<=128
    return binding
binding=parse_original_binding(RAW)
assert binding.run_id=="C-FORCE-CPU-20261024-v1"
assert binding.run_id!=IDENTITY["run_id"] # distinct original record and A envelope labels

events=[]
class PrivateFakeCore:
    """Oracle fixture only. No model/scaler instance or forward."""
    def __init__(self):
        events.append({"event":"private_fake_construct"})
    def start_session(self,*,generation,epoch,run_id):
        assert generation==1 and epoch==0 and run_id==binding.run_id
        events.append({"event":"private_fake_start","generation":generation,"epoch":epoch,"run_id":run_id})
        return object()
    def observe(self,token,original):
        assert original is RAW
        events.append({"event":"private_fake_observe","raw_sha256":h(original),"raw_bytes":len(original)})
        return REPLY
    def end_session(self,token):
        events.append({"event":"private_fake_end"})
core=PrivateFakeCore()
token=core.start_session(generation=1,epoch=0,run_id=binding.run_id)
assert core.observe(token,RAW) is REPLY
core.end_session(token)
assert "torch" not in sys.modules
parse_negatives=[]
first=json.loads(RAW)
for label,change in [
    ("wrong-domain",{"source_domain":"software_fixture"}),
    ("wrong-profile",{"profile_id":"sim_em_v2"}),
    ("wrong-scaler",{"preprocessing_sha256":"0"*64}),
    ("oversize-original-run",{"run_id":"界"*43}),
    ("extra-field",{"BOOT":1}),
]:
    candidate=cj({**first,**change})
    try:parse_original_binding(candidate)
    except (ValueError,AssertionError,UnicodeError):
        parse_negatives.append(label)
    else:raise AssertionError("invalid first binding accepted: "+label)
assert len(events)==4

retirement=[
 {"scenario":"valid OBSERVE then valid END","construct":1,"start":1,"observe":1,"end_attempt":1,"write_attempts":2,"tail_reads":0,"exit":0},
 {"scenario":"malformed first frame","construct":0,"start":0,"observe":0,"end_attempt":0,"write_attempts":0,"exit":"nonzero"},
 {"scenario":"boundary EOF after OBSERVE","construct":1,"start":1,"observe":1,"end_attempt":1,"write_attempts":1,"exit":"nonzero"},
 {"scenario":"malformed later/read error after OBSERVE","construct":1,"start":1,"observe":1,"end_attempt":1,"write_attempts":1,"exit":"nonzero"},
 {"scenario":"constructor raises","construct":1,"start":0,"observe":0,"end_attempt":0,"write_attempts":0,"exit":"nonzero"},
 {"scenario":"start raises before success","construct":1,"start":1,"observe":0,"end_attempt":0,"write_attempts":0,"exit":"nonzero"},
 {"scenario":"first observe raises","construct":1,"start":1,"observe":1,"end_attempt":1,"write_attempts":0,"exit":"nonzero"},
 {"scenario":"first RESULT short/None/zero/invalid/exception write","construct":1,"start":1,"observe":1,"end_attempt":1,"write_attempts":1,"future_reads":0,"exit":"nonzero"},
 {"scenario":"END end_session raises","construct":1,"start":1,"observe":1,"end_attempt":1,"write_attempts":1,"cleanup_end_retry":0,"exit":"nonzero"},
 {"scenario":"ENDED write fails","construct":1,"start":1,"observe":1,"end_attempt":1,"write_attempts":2,"tail_reads":0,"cleanup_end_retry":0,"exit":"nonzero"},
]
oracle={"work_id":"C-ENDPOINT-INDEPENDENT-REVIEW-20261027-v1","phase":"1b","created_utc":datetime.now(timezone.utc).isoformat(),
        "design_sha256":DESIGN_SHA,"header_format":">4sBBHII","header_bytes":16,
        "observe_header_hex":obs[:16].hex(),"observe_metadata_bytes":len(obs_meta),
        "observe_frame_bytes":len(obs),"result_frame_bytes":len(res),
        "raw_capacity_at_this_identity":capacity,"max_response_geometry_bytes":6160,
        "synthetic_identity":IDENTITY,"identity_claim":"test-only labels, no A authentication/provenance/authority",
        "hash_semantics":{"operation_request_hash":IDENTITY["request_hash"],"request_frame_sha256":h(obs),
                          "request_payload_sha256":h(RAW),"unchanged_reply_payload_sha256":h(REPLY)},
        "alternate_metadata_request_sha256":h(variant),"response_metadata":res_md,"end_request_metadata":end_md,
        "fixtures":fixtures,"actual_parser_pins":[{"path":r,"sha256":d} for r,d in parser_pins],
        "binding_control":{"record_run_id":binding.run_id,"A_envelope_run_id":IDENTITY["run_id"],
                           "must_stay_distinct":True,"private_fake_events":events,
                           "preconstructor_binding_negatives":parse_negatives,"torch_imported":False},
        "retirement_expectations":retirement,
        "truncation_positions":[0,1,3,4,7,8,15,16,16+len(obs_meta)-1,16+len(obs_meta),len(obs)-1],
        "partial_read_pattern_examples":[[1],[3],[15,1],[16,17,31]],"no_partial_write_completion":True,
        "model_loads":0,"learned_forwards":0,"endpoint_process_launches":0,
        "status":"independent reference fixtures/control expectations only; no evolving endpoint execution"}
emit("wire-oracles.json",oracle)
print(json.dumps({"status":"PASS","design_sha256":DESIGN_SHA,"header_hex":obs[:16].hex(),
                  "observe_frame_bytes":len(obs),"result_frame_bytes":len(res),"raw_capacity":capacity,
                  "fixture_count":len(fixtures),"actual_stdlib_first_binding_parsed":binding.run_id,
                  "separate_A_envelope_run_id":IDENTITY["run_id"],"fake_lifecycle_events":len(events),
                  "first_binding_negatives":len(parse_negatives),"model_loads":0,"learned_forwards":0,
                  "endpoint_process_launches":0},sort_keys=True))


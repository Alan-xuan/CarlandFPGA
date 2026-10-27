"""Phase1 exact-byte/source proof only: no endpoint import, model load or forward."""
import hashlib, json, os, sys
from pathlib import Path
from datetime import datetime, timezone
NODE=Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c")
WT=NODE/".local/deepeye-implementation-c"
SOURCE=NODE/".local/channel-followup-01a15a24/endpoint-next-20261027"
OUT=Path(__file__).resolve().parent
EXPECTED="3cbffc7619558619bde6f1b25e53f3cb7225855b79aea45417e2fcf33cd4034b"
h=lambda b:hashlib.sha256(b).hexdigest()
def put(name, data):
    with (OUT/name).open("xb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
def emit(name, data):
    put(name,(json.dumps(data,indent=2,ensure_ascii=True,allow_nan=False)+"\n").encode())
request_raw=(SOURCE/"A-endpoint-request.json").read_bytes()
comment=json.loads(request_raw)
assert comment["id"]==6416227814
assert comment["user"]["login"]=="carolwjade"
assert comment["html_url"]=="https://github.com/carolwjade/CarlandFPGA/pull/25#issuecomment-6416227814"
body=comment["body"]
fence=chr(96)*3
opening=fence+"json\n"
assert body.count(opening)==1 and body.count(fence)==2
assert body.count("\ufffd")==0
start=body.index(opening)+len(opening)
end=body.index(fence,start)
# Exact fenced UTF8 bytes: no json.dumps, float conversion, strip or newline rewrite.
fenced=body[start:end].encode("utf8")
fixture=(SOURCE/"A-C21-first-result.exact.json").read_bytes()
assert len(fenced)==len(fixture)==2007
assert h(fenced)==h(fixture)==EXPECTED
assert fenced==fixture
assert fixture[-1:]==b"\n" and fixture[-2:-1]!=b"\n"
assert fixture.count(b"\n")==1 and b"\r" not in fixture
assert len(fixture[:-1])==2006
doc=json.loads(fixture) # inspection only; never used to reconstruct reply
assert doc["movement_authorized"] is False and doc["motion_bytes"] is None
assert doc["formal_acceptance"]=="incomplete"
assert doc["generation"]==1 and doc["epoch"]==0 and doc["sequence"]==7327
assert doc["delivery_index"]==0 and doc["window"]["missing_slots"]==127
assert doc["binding"]["source_domain"]=="geo_replay" and doc["binding"]["profile_id"]=="force_curve_v1"
assert len(doc["probabilities"])==12
assert doc["artifact_pins"]["model_manifest_sha256"]=="0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959"
put("A-recorded-reply.exact.bin",fixture)
# Read only first public raw record, not the model or future suffix.
input_path=WT/"competition/deepeye/ai_pc/cpu_model/force_v1/public_input.jsonl"
with input_path.open("rb") as f:
    first=f.readline(16385)
assert len(first)==354
assert h(first)==doc["input_prefix_sha256"]
observation=json.loads(first)
fields={"run_id","source_domain","profile_id","preprocessing_sha256","sequence"}|{"value_"+str(i) for i in range(4)}|{"valid_"+str(i) for i in range(4)}
assert set(observation)==fields and len(observation)==13
assert observation["sequence"]==doc["sequence"]
assert all(observation[k]==doc["binding"][k] for k in doc["binding"])
assert len(first)==doc["session_bytes"]
put("original-first-record.raw",first)
contract_path=WT/"docs/competition/deepeye-2026/immutable_scope.json"
contract_raw=contract_path.read_bytes()
contract=json.loads(contract_raw)
req=contract["requirements"]
reqsha=h(json.dumps(req,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
assert reqsha=="c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
assert [x["id"] for x in req]==["H%02d"%i for i in range(1,16)]
# Pure boundary fixtures, explicitly synthetic. No numerical lexeme is rewritten.
fixtures=[{"path":"A-recorded-reply.exact.bin","kind":"actual recorded A result; byte proof only","bytes":len(fixture),"sha256":h(fixture)},
          {"path":"original-first-record.raw","kind":"first original13field record; not executed","bytes":len(first),"sha256":h(first)}]
for maximum in (4095,4096,4097):
    b=fixture[:-1]+b" "*(maximum-len(fixture))+b"\n"
    assert len(b)==maximum
    assert json.loads(b)["sequence"]==7327
    name="synthetic-reply-%d.bin"%maximum
    put(name,b)
    fixtures.append({"path":name,"kind":"synthetic private fake-core byte-limit fixture, not learned output","bytes":len(b),"sha256":h(b)})
for maximum in (16383,16384,16385):
    b=first+b" "*(maximum-len(first))
    assert len(b)==maximum and set(json.loads(b))==fields
    name="synthetic-record-%d.raw"%maximum
    put(name,b)
    fixtures.append({"path":name,"kind":"synthetic whitespace-padded13field byte-limit record; not executed","bytes":len(b),"sha256":h(b)})
source_pins=[]
for p in [SOURCE/"A-endpoint-request.json",SOURCE/"A-C21-first-result.exact.json",SOURCE/"fixture-readback.json",SOURCE/"metadata-readback.json",contract_path]:
    b=p.read_bytes();source_pins.append({"path":str(p),"bytes":len(b),"sha256":h(b)})
oracle={"work_id":"C-ENDPOINT-INDEPENDENT-REVIEW-20261027-v1","phase":1,
        "created_utc":datetime.now(timezone.utc).isoformat(),"source_comment":{"id":comment["id"],"url":comment["html_url"],
        "author":comment["user"]["login"],"created_at":comment["created_at"],"updated_at":comment["updated_at"],"body_utf8_sha256":h(body.encode("utf8"))},
        "proof":"cached original GitHub public-comment body fence UTF8 bytes exactly equal supplied fixture; no live refresh or JSON reply reserialization",
        "source_pins":source_pins,"fixtures":fixtures,"real_reply_bytes":2007,"real_reply_json_bytes_without_LF":2006,
        "real_reply_sha256":EXPECTED,"first_record_bytes":354,"first_record_sha256":h(first),"reply_cap":4096,"record_cap":16384,
        "native_128B_gap":{"actual_reply_exceeds128":2007>128,"actual_reply_minus128":2007-128,
                           "status":"128B native fixture alone cannot demonstrate2007B/4096B transport correctness"},
        "contract_requirements_sha256":reqsha,"H01_H15_verified_identity_only":True,"learned_model_loads":0,
        "learned_forwards":0,"endpoint_process_launches":0,"wire_specific_controls":"pending main concrete framing design",
        "formal_acceptance":"incomplete; no new authority"}
emit("phase1-byte-oracles.json",oracle)
print(json.dumps({"status":"PASS","exact_fenced_reply_bytes":2007,"reply_sha256":EXPECTED,
                  "first_record_bytes":354,"first_record_sha256":h(first),"synthetic_boundary_fixtures":6,
                  "contract_requirements_sha256":reqsha,"learned_model_loads":0,"learned_forwards":0,
                  "endpoint_process_launches":0},sort_keys=True))


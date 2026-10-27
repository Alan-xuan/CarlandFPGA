"""Independent C22 source review controls. No author/old suite, model or CLI run."""
import ast, dataclasses, hashlib, importlib, json, struct, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
OUT=Path(__file__).resolve().parent
REVIEW=OUT.parent
WT=Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c\.local\deepeye-implementation-c")
FIX=REVIEW/"phase1b/r2"
ORACLE=json.loads((FIX/"wire-oracles.json").read_bytes())
RAW=(REVIEW/"original-first-record.raw").read_bytes()
REPLY=(REVIEW/"A-recorded-reply.exact.bin").read_bytes()
END_REPLY=b'{"synthetic":"END-RECEIPT-BYTES-ONLY"}\n'
H=struct.Struct(">4sBBHII")
ID=ORACLE["synthetic_identity"]
USED=set()
FACTS={"scope":"frozen-source pure-byte controls with private fake core only",
       "model_loads":0,"learned_forwards":0,"endpoint_process_launches":0,
       "private_factory_calls":0,"groups":{},"blocked_model_import_attempts":[]}
class NoModel:
    def find_spec(self,fullname,*_):
        if fullname=="torch" or fullname.startswith("torch.") or fullname=="ai_pc.model.force_cnn":
            FACTS["blocked_model_import_attempts"].append(fullname)
            raise AssertionError("forbidden learned module import: "+fullname)
sys.meta_path.insert(0,NoModel())
sys.path.insert(0,str(WT/"competition/deepeye"))
from ai_pc.cpu_package import endpoint_protocol as p
from ai_pc.cpu_package import process_endpoint as d

def sha(b):return hashlib.sha256(b).hexdigest()
def cj(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def fixture(name):
    USED.add(name);return (FIX/name).read_bytes()
def req(kind=1,index=1,inv=1,payload=RAW,changes=None,metadata=None):
    ident={**ID,"invocation_id":inv}
    if changes:ident.update(changes)
    md={"identity":ident,"frame_index":index,"payload_sha256":sha(payload)}
    meta=cj(md) if metadata is None else metadata
    return H.pack(b"C22E",1,kind,0,len(meta),len(payload))+meta+payload
def payload_of(frame):
    magic,version,kind,flags,ml,pl=H.unpack(frame[:16])
    assert magic==b"C22E" and version==1 and flags==0
    assert len(frame)==16+ml+pl
    return kind,json.loads(frame[16:16+ml]),frame[16+ml:]
def note(group,**values):
    FACTS["groups"][group]=values
    print(json.dumps({"group":group,**values},sort_keys=True),flush=True)

class Reader:
    def __init__(self,data,chunks=(100000,),fault=None):
        self.data,self.pos,self.chunks,self.calls,self.fault=data,0,chunks,[],fault
    def read(self,n):
        assert type(n) is int and 0<n<=16384
        self.calls.append((self.pos,n))
        if self.fault:
            answer=self.fault(self,n)
            if answer is not NotImplemented:return answer
        maximum=self.chunks[(len(self.calls)-1)%len(self.chunks)]
        part=self.data[self.pos:self.pos+min(n,maximum)]
        self.pos+=len(part);return part

class Writer:
    def __init__(self,reader,ack=None):
        self.reader,self.ack,self.attempts,self.positions=reader,ack,[],[]
    def write(self,b):
        assert type(b) is bytes
        self.attempts.append(b);self.positions.append(self.reader.pos)
        return len(b) if self.ack is None else self.ack(b)

class FakeCore:
    """Private fixture only; captured call/encoded bytes are not model evidence."""
    def __init__(self,reply=REPLY,fail=None):
        self.reply,self.fail,self.starts,self.observed,self.ends=reply,fail,[],[],0
        self.token=object()
    def start_session(self,**kw):
        self.starts.append(kw)
        if self.fail=="start":raise RuntimeError("private-start-SECRET"+"x"*600)
        assert kw=={"generation":1,"epoch":0,"run_id":"C-FORCE-CPU-20261024-v1"}
        return self.token
    def observe(self,token,original):
        assert token is self.token and type(original) is bytes
        self.observed.append(original)
        # Real pinned stdlib parse ensures fake bytes cannot conceal binding.
        from ai_pc.cpu_package.runner import strict_json
        from ai_pc.model.curve_input import CurveObservation
        ob=CurveObservation.from_mapping(strict_json(original))
        assert ob.binding.run_id==self.starts[0]["run_id"]
        if self.fail=="observe":raise RuntimeError("private-observe-SECRET"+"x"*600)
        return SimpleNamespace(encoded=self.reply)
    def end_session(self,token):
        assert token is self.token
        self.ends+=1
        if self.fail=="end":raise RuntimeError("private-end-SECRET"+"x"*600)
        return SimpleNamespace(encoded=END_REPLY)

def drive(data,*,reply=REPLY,fail=None,chunks=(100000,),ack=None,fault=None,limits=None):
    reader=Reader(data,chunks,fault);writer=Writer(reader,ack);core=FakeCore(reply,fail);calls=[]
    def factory():
        calls.append(1);FACTS["private_factory_calls"]+=1
        if fail=="construct":raise RuntimeError("private-construct-SECRET"+"x"*600)
        return core
    driver=d.EndpointDriver(reader.read,writer.write,limits=limits)
    with patch.object(d,"_new_core",factory):
        outcome=driver.run()
        before=(len(reader.calls),len(writer.attempts),len(calls),len(core.starts),len(core.observed),core.ends)
        retired=driver.run()
        assert retired.exit_code!=0 and retired.diagnostic=="driver_retired"
        assert before==(len(reader.calls),len(writer.attempts),len(calls),len(core.starts),len(core.observed),core.ends)
    assert outcome.diagnostic.isascii() and len(outcome.diagnostic)<=64
    return SimpleNamespace(reader=reader,writer=writer,core=core,calls=calls,outcome=outcome,driver=driver)

class IndependentEndpoint(unittest.TestCase):
    def test_E01_exact_frozen_frames_and_full_reply(self):
        observe=fixture("observe-1.frame");end=fixture("end-2.frame")
        request=p.decode_request(observe)
        self.assertEqual(request.raw,observe);self.assertEqual(request.payload,RAW)
        identity=p.InvocationIdentity(**ID)
        self.assertEqual(p.encode_request(identity,1,RAW),observe)
        self.assertEqual(p.encode_response(request,REPLY),fixture("result-1.frame"))
        end_request=p.decode_request(end)
        self.assertEqual(p.encode_response(end_request,END_REPLY),fixture("ended-2.frame"))
        case=drive(observe+end+b"TAIL-MUST-STAY")
        self.assertEqual(case.outcome.exit_code,0)
        self.assertEqual(case.writer.attempts,[fixture("result-1.frame"),fixture("ended-2.frame")])
        self.assertEqual(case.reader.pos,len(observe)+len(end))
        self.assertEqual(sha(payload_of(case.writer.attempts[0])[2]),ORACLE["hash_semantics"]["unchanged_reply_payload_sha256"])
        note("E01",exact_A_reply_bytes=2007,full_result_frame=2665,byte_match=True,tail_unread=True)

    def test_E02_total_meta_reply_caps(self):
        for name in ("input-total-16384.frame","input-meta-2048.frame"):
            self.assertIsInstance(p.decode_request(fixture(name)),p.Request)
        for name in ("input-total-16385.frame","raw16384-total-bad.frame","input-meta-2049.frame"):
            data=fixture(name);case=drive(data)
            self.assertNotEqual(case.outcome.exit_code,0)
            self.assertEqual(case.calls,[]);self.assertEqual(case.reader.pos,16)
            self.assertEqual(case.writer.attempts,[])
        request=p.decode_request(fixture("observe-1.frame"))
        for n in (4095,4096):
            expected=fixture("reply-%d.frame"%n)
            padded=(REVIEW/("synthetic-reply-%d.bin"%n)).read_bytes()
            self.assertEqual(p.encode_response(request,padded),expected)
            case=drive(fixture("observe-1.frame")+fixture("end-2.frame"),reply=padded)
            self.assertEqual(case.outcome.exit_code,0);self.assertEqual(case.writer.attempts[0],expected)
        excessive=(REVIEW/"synthetic-reply-4097.bin").read_bytes();fixture("reply-4097.frame")
        case=drive(fixture("observe-1.frame")+fixture("end-2.frame"),reply=excessive)
        self.assertEqual(case.writer.attempts,[]);self.assertEqual(case.core.ends,1)
        self.assertEqual(case.reader.pos,len(fixture("observe-1.frame")))
        geometry=fixture("response-6160.geometry")
        self.assertEqual(len(geometry),p.MAX_RESPONSE)
        note("E02",input_total_edge=16384,dynamic_raw_edge=15908,reply_4096_accepted=True,
             reply_4097_no_write=True,geometry6160="synthetic only")

    def test_E03_fixed_invalid_frames_and_truncation(self):
        bad=["bad-payload-hash.frame","bad-magic.frame","bad-version.frame","bad-flags.frame",
             "bad-kind.frame","bad-first-index.frame","bad-bool-index.frame","bad-bool-invocation.frame","bad-extra-key.frame"]
        for name in bad:
            case=drive(fixture(name))
            self.assertEqual(case.calls,[],name);self.assertEqual(case.writer.attempts,[],name)
            self.assertNotEqual(case.outcome.exit_code,0)
        first=fixture("observe-1.frame")
        for position in ORACLE["truncation_positions"]:
            case=drive(first[:position])
            self.assertEqual(case.calls,[]);self.assertEqual(case.writer.attempts,[])
            self.assertNotEqual(case.outcome.exit_code,0)
        for ml,pl in [(0,1),(2049,1),(1,0xffffffff),(1,16384)]:
            case=drive(H.pack(b"C22E",1,1,0,ml,pl))
            self.assertEqual(case.calls,[]);self.assertEqual(case.reader.pos,16)
        note("E03",negative_frozen_frames=len(bad),truncation_positions=len(ORACLE["truncation_positions"]),
             overlimit_body_not_read=True)

    def test_E04_partial_reads_and_invalid_completions(self):
        stream=fixture("observe-1.frame")+fixture("end-2.frame")
        for pattern in [(1,),(3,),(15,1),(16,17,31)]:
            case=drive(stream+b"TAIL",chunks=pattern)
            self.assertEqual(case.outcome.exit_code,0);self.assertEqual(case.reader.pos,len(stream))
            self.assertEqual(case.writer.attempts[0],fixture("result-1.frame"))
        def raises(_r,_n):raise OSError("private-read-SECRET")
        faults=[lambda _r,_n:None,lambda _r,_n:b"",lambda _r,_n:bytearray(b"x"),
                lambda _r,_n:"x",lambda _r,n:b"x"*(n+1),raises]
        for fault in faults:
            case=drive(stream,fault=fault)
            self.assertEqual(len(case.reader.calls),1);self.assertEqual(case.calls,[])
            self.assertEqual(case.writer.attempts,[])
        note("E04",positive_fragment_patterns=4,invalid_read_completions=6,no_retry=True)

    def test_E05_single_write_short_unknown_and_error(self):
        first=fixture("observe-1.frame");stream=first+fixture("end-2.frame")
        def raises(_b):raise OSError("private-write-SECRET")
        acks=[lambda _b:0,lambda _b:None,lambda _b:True,lambda _b:-1,
              lambda b:len(b)-1,lambda b:len(b)+1,lambda _b:"1",raises]
        for ack in acks:
            case=drive(stream,ack=ack)
            self.assertEqual(len(case.writer.attempts),1)
            self.assertEqual(case.writer.positions,[len(first)])
            self.assertEqual(case.reader.pos,len(first));self.assertEqual(case.core.ends,1)
            self.assertEqual(case.outcome.responses_emitted,0);self.assertEqual(case.outcome.output_bytes,0)
            self.assertNotEqual(case.outcome.exit_code,0)
        note("E05",unknown_write_cases=len(acks),single_attempt=True,no_remainder_errorframe_or_future_read=True)

    def test_E06_retirement_counts_end_eof_failures(self):
        obs=fixture("observe-1.frame");end=fixture("end-2.frame")
        normal=drive(obs+end);self.assertEqual((len(normal.calls),len(normal.core.starts),len(normal.core.observed),normal.core.ends,len(normal.writer.attempts)),(1,1,1,1,2))
        eof=drive(obs);self.assertEqual((eof.outcome.exit_code,len(eof.writer.attempts),eof.core.ends),(1,1,1))
        for failure,counts in [("construct",(1,0,0,0,0)),("start",(1,1,0,0,0)),("observe",(1,1,1,1,0)),("end",(1,1,1,1,1))]:
            case=drive(obs+end,fail=failure)
            actual=(len(case.calls),len(case.core.starts),len(case.core.observed),case.core.ends,len(case.writer.attempts))
            self.assertEqual(actual,counts,failure);self.assertNotEqual(case.outcome.exit_code,0)
        cleanup=drive(obs,fail="end")
        self.assertEqual(cleanup.core.ends,1);self.assertTrue(cleanup.outcome.cleanup_failed)
        first_end=drive(req(2,1,1,b""))
        self.assertEqual(first_end.calls,[]);self.assertNotEqual(first_end.outcome.exit_code,0)
        note("E06",normal_counts=[1,1,1,1,2],boundary_eof_abnormal=True,
             failed_explicit_end_not_retried=True,cleanup_failure_no_extra_write=True)

    def test_E07_actual_lazy_fixed_constructor_seam_no_model(self):
        core_module=importlib.import_module("ai_pc.cpu_package.stream_core") # definitions only, stdlib
        captures=[];pins=[]
        original_pin=d._source_pin
        def pin(path,expected):
            pins.append((str(path),expected));return original_pin(path,expected)
        def fake_construct(*args,**kwargs):
            captures.append((args,kwargs))
            self.assertEqual(kwargs["limits"].max_output_bytes,4096)
            return "PRIVATE-FAKE-ONLY"
        with patch.object(d,"_source_pin",pin),patch.object(core_module,"FrozenForceStream",fake_construct):
            made=d._new_core()
        self.assertEqual(made,"PRIVATE-FAKE-ONLY");self.assertEqual(len(captures),1)
        self.assertEqual(pins[0][1],d.STREAM_CORE_SHA256)
        with patch.object(d,"_source_pin",side_effect=p.ProtocolError("source_pin_failed")), \
             patch.object(d,"_import_at",side_effect=AssertionError("import before source verification")):
            with self.assertRaises(p.ProtocolError):d._new_core()
        case=drive(fixture("observe-1.frame")+fixture("end-2.frame"))
        self.assertEqual(case.core.starts,[{"generation":1,"epoch":0,"run_id":"C-FORCE-CPU-20261024-v1"}])
        self.assertNotEqual(case.core.starts[0]["run_id"],ID["run_id"])
        self.assertNotIn("torch",sys.modules)
        note("E07",actual_fixed_new_core_source_pin=True,actual_StreamLimits_output4096=True,
             constructor_privately_replaced=True,original_record_run_id_preserved=True)

    def test_E08_real_first_parser_negatives_and_binding_freeze(self):
        original=json.loads(RAW)
        cases=[]
        for change in [{"source_domain":"software_fixture"},{"profile_id":"sim_em_v2"},
                       {"preprocessing_sha256":"0"*64},{"run_id":""},{"run_id":"界"*43},
                       {"run_id":"\ud800"},{"BOOT":1},{"valid_0":1},{"value_0":True}]:
            cases.append(cj({**original,**change}))
        missing=dict(original);missing.pop("valid_3");cases.append(cj(missing))
        cases.extend([b"{",b"\xff",RAW+RAW])
        for candidate in cases:
            case=drive(req(payload=candidate))
            self.assertEqual(case.calls,[]);self.assertEqual(case.writer.attempts,[])
        changed=cj({**original,"run_id":"DIFFERENT-RECORD-RUN"})
        case=drive(fixture("observe-1.frame")+req(index=2,inv=2,payload=changed))
        self.assertEqual(len(case.core.observed),1);self.assertEqual(len(case.writer.attempts),1)
        self.assertEqual(case.core.ends,1)
        note("E08",real_original_parser_unpatched=True,first_binding_negatives=len(cases),
             changed_later_record_before_fake_observe=True)

    def test_E09_identity_index_highwaters_and_immutable_shape(self):
        observe=fixture("observe-1.frame")
        changes=[{"operation_id":"OTHER"},{"request_hash":"4"*64},{"tested_commit":"4"*40},
                 {"package_manifest_sha256":"4"*64},{"run_id":"OTHER"},{"actor_instance_id":"OTHER"}]
        for change in changes:
            case=drive(observe+req(index=2,inv=2,changes=change))
            self.assertEqual(len(case.core.observed),1);self.assertEqual(len(case.writer.attempts),1)
        for index,inv in [(1,2),(3,2),(2,1),(2,0)]:
            case=drive(observe+req(index=index,inv=inv))
            self.assertEqual(len(case.core.observed),1);self.assertNotEqual(case.outcome.exit_code,0)
        jump=drive(observe+req(index=2,inv=7)+req(2,3,8,b""))
        self.assertEqual(jump.outcome.exit_code,0);self.assertEqual(len(jump.core.observed),2)
        parsed=p.decode_request(observe)
        with self.assertRaises(dataclasses.FrozenInstanceError):parsed.identity.run_id="MUTATED"
        with self.assertRaises(dataclasses.FrozenInstanceError):parsed.frame_index=0
        for kw in [{"invocation_id":True},{"invocation_id":2**63},{"operation_id":"x"*193},{"run_id":"é"},{"request_hash":"A"*64},{"tested_commit":"0"*41}]:
            with self.assertRaises(p.ProtocolError):p.InvocationIdentity(**{**ID,**kw})
        note("E09",six_frozen_fields=True,index_exact_next=True,invocation_strict_increase_allows_jump=True,
             no_identity_authentication_claim=True)

    def test_E10_retired_object_and_end_tail_isolation(self):
        # drive always reruns retired driver and proves no I/O/core activity.
        obs=fixture("observe-1.frame");end=fixture("end-2.frame")
        case=drive(obs+end+obs)
        self.assertEqual(case.reader.pos,len(obs)+len(end))
        self.assertEqual(len(case.core.starts),1);self.assertEqual(case.core.ends,1)
        self.assertEqual(case.outcome.responses_emitted,2)
        # Initial syntactically valid correlation can differ; it is not auth.
        other=drive(req(changes={"run_id":"SYNTH-OTHER-A-RUN"})+req(2,2,2,b"",changes={"run_id":"SYNTH-OTHER-A-RUN"}))
        self.assertEqual(other.outcome.exit_code,0)
        note("E10",used_driver_no_reactivation=True,no_end_tail_read=True,
             distinct_initial_A_labels_diagnostic_only=True)

    def test_E11_future_poison_preserves_first_reply(self):
        obs=fixture("observe-1.frame")
        bad=fixture("bad-magic.frame")
        case=drive(obs+bad+fixture("end-2.frame"))
        self.assertNotEqual(case.outcome.exit_code,0)
        self.assertEqual(case.writer.attempts,[fixture("result-1.frame")])
        self.assertEqual(case.writer.positions,[len(obs)])
        self.assertEqual(case.reader.pos,len(obs)+16)
        self.assertEqual(case.core.ends,1)
        note("E11",first_success_before_future_read=True,earlier_reply_unchanged=True,future_error_no_resync=True)

    def test_E12_original_metadata_and_distinct_hash_semantics(self):
        variant=fixture("observe-meta-variant.frame")
        case=drive(variant+fixture("end-2.frame"))
        self.assertEqual(case.writer.attempts[0],fixture("result-meta-variant.frame"))
        kind,md,payload=payload_of(case.writer.attempts[0])
        self.assertEqual(kind,129);self.assertEqual(payload,REPLY)
        self.assertEqual(md["request_frame_sha256"],sha(variant))
        self.assertEqual(md["request_payload_sha256"],sha(RAW))
        self.assertEqual(md["payload_sha256"],sha(REPLY))
        self.assertEqual(md["identity"]["request_hash"],ID["request_hash"])
        self.assertEqual(len(set([md["request_frame_sha256"],md["request_payload_sha256"],md["payload_sha256"],ID["request_hash"]])),4)
        note("E12",noncanonical_metadata_raw_hash=True,operation_frame_record_reply_hashes_distinct=True,LF_preserved=True)

    def test_E13_lifetime_budgets_before_core_or_write(self):
        obs=fixture("observe-1.frame");end=fixture("end-2.frame")
        result=fixture("result-1.frame");ended=fixture("ended-2.frame")
        low=drive(obs+end,limits=d.EndpointLimits(max_input_bytes=len(obs)-1))
        self.assertEqual(low.calls,[]);self.assertEqual(low.reader.pos,16)
        exact=drive(obs+end,limits=d.EndpointLimits(max_input_bytes=len(obs)+len(end),max_output_bytes=len(result)+len(ended),max_frames=2,max_observations=1))
        self.assertEqual(exact.outcome.exit_code,0)
        out=drive(obs+end,limits=d.EndpointLimits(max_output_bytes=len(result)-1))
        self.assertEqual(out.writer.attempts,[]);self.assertEqual(len(out.core.observed),1);self.assertEqual(out.core.ends,1)
        end_out=drive(obs+end,limits=d.EndpointLimits(max_output_bytes=len(result)+len(ended)-1))
        self.assertEqual(len(end_out.writer.attempts),1);self.assertEqual(end_out.core.ends,1)
        no_slot=drive(obs,limits=d.EndpointLimits(max_frames=1))
        self.assertEqual(no_slot.calls,[])
        two=drive(obs+req(index=2,inv=2),limits=d.EndpointLimits(max_frames=2))
        self.assertEqual(len(two.core.observed),1)
        for field,maximum in [("max_frames",65536),("max_observations",65535),("max_input_bytes",67108864),("max_output_bytes",67108864)]:
            for bad in (0,True,maximum+1):
                with self.assertRaises(p.ProtocolError):d.EndpointLimits(**{field:bad})
        limits=d.EndpointLimits();driver=d.EndpointDriver(lambda _n:b"",lambda b:len(b),limits=limits)
        object.__setattr__(limits,"max_frames",1)
        self.assertEqual(driver._limits.max_frames,65536)
        note("E13",exact_whole_wire_budget=True,input_before_factory=True,output_before_write=True,
             final_END_slot_reserved=True,limits_detached_only_lower=True)

    def test_E14_strict_json_diagnostics_no_private_echo(self):
        base=json.loads(req()[16:16+ORACLE["observe_metadata_bytes"]])
        candidates=[]
        canonical=cj(base)
        candidates.append(canonical[:-1]+b',"frame_index":1}')
        candidates.append(canonical.replace(b'"frame_index":1',b'"frame_index":NaN'))
        candidates.append(canonical.replace(b'"frame_index":1',b'"frame_index":1e999'))
        candidates.extend([b"\xff",b"[]",b"null",b"{"*1000+b"}"*1000])
        for md in candidates:
            frame=H.pack(b"C22E",1,1,0,len(md),len(RAW))+md+RAW
            case=drive(frame)
            self.assertEqual(case.calls,[]);self.assertEqual(case.writer.attempts,[])
            self.assertNotIn("SECRET",case.outcome.diagnostic)
        failing=drive(fixture("observe-1.frame"),fail="observe")
        self.assertEqual(failing.outcome.diagnostic,"endpoint_failed")
        self.assertEqual(failing.writer.attempts,[])
        note("E14",json_negatives=len(candidates),bounded_ascii_diagnostic=True,no_error_banner_or_raw_exception=True)

    def test_E15_static_cli_and_no_runtime_authority_imports(self):
        source=Path(d.__file__).read_text()
        tree=ast.parse(source)
        imported=[n.module or "" for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        imported.extend(a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names)
        self.assertFalse(any(x.startswith(("integration","simulation","torch","subprocess","threading","socket")) for x in imported))
        self.assertNotIn("sys.stdin",source);self.assertNotIn("sys.stdout",source)
        self.assertIn("os.read(0, size)",source);self.assertIn("os.write(1, raw)",source)
        self.assertIn("msvcrt.setmode(0, os.O_BINARY)",source);self.assertIn("msvcrt.setmode(1, os.O_BINARY)",source)
        self.assertIn("if len(sys.argv) != 1:",source)
        self.assertEqual(set(__import__("inspect").signature(d.EndpointDriver).parameters),{"read","write","limits"})
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="print" for n in ast.walk(tree)))
        note("E15",static_raw_stdio_binary_mode=True,no_CLI_execution=True,no_A_authority_model_or_process_import=True)

    def test_E16_fixture_coverage_and_no_model_imports(self):
        # All24 preimplementation reference frames were read in earlier groups.
        self.assertEqual(USED,{x["path"] for x in ORACLE["fixtures"]})
        self.assertFalse(FACTS["blocked_model_import_attempts"])
        self.assertNotIn("torch",sys.modules)
        self.assertNotIn("ai_pc.model.force_cnn",sys.modules)
        note("E16",all_reference_frames_used=24,Torch_imported=False,model_loads=0,learned_forwards=0,endpoint_process_launches=0)

    def test_E17_fixed_scope_and_source_sha(self):
        self.assertEqual(sha(Path(p.__file__).read_bytes()),"1654f857a6cb17af734aa66e8f96f028551b15f4a7767f196e511104783de998")
        self.assertEqual(sha(Path(d.__file__).read_bytes()),"46b792911fecdc211d3895f8747ee745498eadf10c1fac3b53477e058a08a2e4")
        parsed=json.loads(REPLY)
        self.assertIs(parsed["movement_authorized"],False);self.assertIsNone(parsed["motion_bytes"])
        self.assertEqual(parsed["formal_acceptance"],"incomplete")
        self.assertEqual(parsed["binding"]["source_domain"],"geo_replay")
        self.assertFalse(FACTS["blocked_model_import_attempts"])
        note("E17",fixed_source_pins=True,FORCE_nonmotion_only=True,production_adoption=False,
             model_quality_runtime_and_formal_acceptance="unchanged incomplete")

if __name__=="__main__":
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    FACTS["unittest"]={"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
                       "skips":len(result.skipped),"success":result.wasSuccessful()}
    FACTS["reference_frames_used"]=sorted(USED)
    FACTS["Torch_imported"]="torch" in sys.modules
    (OUT/"control-facts.json").write_text(json.dumps(FACTS,indent=2,allow_nan=False)+"\n",encoding="utf8",newline="\n")
    print(json.dumps({"summary":FACTS["unittest"],"private_factories":FACTS["private_factory_calls"],
                      "model_import_attempts":FACTS["blocked_model_import_attempts"],"Torch_imported":FACTS["Torch_imported"]},sort_keys=True))
    sys.exit(0 if result.wasSuccessful() else 1)


"""Independent final-source controls. Only P01 runs real model forwards (three).
Other successful-prediction controls use clearly labelled private _predict stubs.
Private fixture clones reuse the one immutable loaded model/scaler, never a public backend API.
"""
import base64, builtins, copy, dataclasses, hashlib, inspect, json, math, struct, sys, threading, unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

OUT = Path(__file__).resolve().parent
REVIEW = OUT.parent
WT = Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c\.local\deepeye-implementation-c")
sys.path.insert(0, str(WT / "competition/deepeye"))
from ai_pc.cpu_package import stream_core as m
ORACLE = json.loads((REVIEW / "phase1-oracles.json").read_bytes())
RAWS = [base64.b64decode(x["raw_bytes_base64"]) for x in ORACLE["selected_records"]]
ROWS = [json.loads(x) for x in RAWS]
STATS = json.loads((WT / "competition/deepeye/data/preprocessing.json").read_bytes())["channels"]
FACTS = {"scope": "independent phase1 controls on repaired source; no old/author suites",
         "source_sha256": hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),
         "real_model_forwards": 0, "private_stub_predictions": 0, "groups": {},
         "private_fixture": "clones share actual fixed loaded model/scaler but create private fresh state/lock/limits; not a public injection API"}
assert FACTS["source_sha256"] == "0a8c07f34080784f36180951b28873b43de5e3f80ad201325254b274bd01217b"

def sha(b):
    return hashlib.sha256(b).hexdigest()

def raw(row, **kwargs):
    return (json.dumps(row, allow_nan=False, **kwargs) + "\n").encode()

def changed(base=None, **changes):
    r = dict(ROWS[0] if base is None else base)
    r.update(changes)
    return r

def field(obj, name):
    return getattr(obj, "_FrozenForceStream" + name)

def frozen_fingerprint(core):
    state = core.state()
    active = field(core, "__committed").active
    if active is None:
        return (state, None)
    b = active.builder
    vals = tuple((k, tuple(v) if k == "_slots" else v) for k, v in sorted(vars(b).items()))
    return (state, id(active.token), id(active.latest), active.latest.encoded if active.latest else None,
            active.prefix.hexdigest(), vals)

def scalar_feature(rows):
    """Independent sequence placement and scalar normalization, no builder call."""
    last = rows[-1]["sequence"]
    retained = {r["sequence"]: r for r in rows if last - r["sequence"] < 128}
    channels = [[0.0] * 128 for _ in range(8)]
    for sequence, row in retained.items():
        k = 127 - (last - sequence)
        for c in range(4):
            v = row["value_" + str(c)]
            usable = row["valid_" + str(c)] and v is not None and (c != 3 or v > 0)
            if usable:
                transformed = math.log10(v) if c == 3 else v
                channels[c][k] = (transformed - STATS[c]["mean"]) / STATS[c]["effective_scale"]
                channels[c + 4][k] = 1.0
    return sha(struct.pack("<1024f", *(v for ch in channels for v in ch)))

def stub_predict(*_args, **_kwargs):
    FACTS["private_stub_predictions"] += 1
    return [1.0 / 12.0] * 12

def note(group, **facts):
    FACTS["groups"][group] = facts
    print(json.dumps({"group": group, **facts}, sort_keys=True), flush=True)

class StopBeforeModel(BaseException):
    pass

class AConstructorBound(unittest.TestCase):
    def test_R1_original_read_trap_and_all_nine_limits(self):
        # Original RED seam: first asset must call read(cap+1), not read().
        original_open = Path.open
        source_path = Path(m._runner.__file__).resolve()
        actual_reads = []
        owner = self
        class Trap:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, size=-1):
                actual_reads.append(size)
                owner.assertEqual(size, 2 * 1024 * 1024 + 1)
                raise StopBeforeModel()
        def intercepted_open(path, *a, **kw):
            return Trap() if Path(path).resolve() == source_path else original_open(path, *a, **kw)
        with patch.object(Path, "open", intercepted_open), self.assertRaises(StopBeforeModel):
            m.FrozenForceStream()
        self.assertEqual(actual_reads, [2097153])

        calls = []
        original_pinned = m._runner.read_pinned
        def finite_pinned(path, expected, **kw):
            calls.append({"path": str(path), "limit": kw.get("limit")})
            self.assertEqual(type(kw.get("limit")), int)
            self.assertEqual(kw["limit"], 2097152)
            return original_pinned(path, expected, **kw)
        with patch.object(m._runner, "read_pinned", finite_pinned), \
             patch.object(m.CurveScaler, "from_document_bytes", side_effect=StopBeforeModel), \
             self.assertRaises(StopBeforeModel):
            m.FrozenForceStream()
        self.assertEqual(len(calls), 9)
        note("R1", first_actual_read_size=actual_reads[0], preflight_reads=calls,
             no_constructor_model_load=True, status="GREEN")

class BIndependentGroups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ai_pc.model import force_cnn
        import torch
        cls.initial_limits = m.StreamLimits()
        with patch.object(force_cnn, "load_frozen_model", wraps=force_cnn.load_frozen_model) as load, \
             patch.object(m.CurveScaler, "from_document_bytes", wraps=m.CurveScaler.from_document_bytes) as scale:
            cls.prototype = m.FrozenForceStream(limits=cls.initial_limits)
            cls.model_loads = load.call_count
            cls.scaler_loads = scale.call_count
        assert cls.model_loads == cls.scaler_loads == 1
        FACTS["runtime"] = {"python": sys.version, "torch": torch.__version__, "device": "cpu",
                            "threads": torch.get_num_threads(), "deterministic": torch.are_deterministic_algorithms_enabled()}
        FACTS["actual_constructor_model_loads"] = cls.model_loads
        FACTS["actual_constructor_scaler_loads"] = cls.scaler_loads
        cls.actual = []

    def clone(self, limits=None):
        # Explicit private fixture: no additional loader/model construction.
        core = object.__new__(m.FrozenForceStream)
        for slot in m.FrozenForceStream.__slots__:
            setattr(core, "_FrozenForceStream" + slot, field(self.prototype, slot))
        setattr(core, "_FrozenForceStream__lock", threading.Lock())
        setattr(core, "_FrozenForceStream__limits", dataclasses.replace(limits or m.StreamLimits()))
        setattr(core, "_FrozenForceStream__committed", m._Committed())
        return core

    def start(self, core, *, generation=1, epoch=0, run_id=None):
        return core.start_session(generation=generation, epoch=epoch, run_id=run_id or ROWS[0]["run_id"])

    def reject(self, core, function, code=None):
        before = frozen_fingerprint(core)
        with self.assertRaises(m.StreamError) as caught:
            function()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertLessEqual(len(str(caught.exception)), 256)
        self.assertEqual(frozen_fingerprint(core), before)
        return caught.exception.code

    def test_P01_three_real_prefixes_loadonce_and_postinit_no_file_reads(self):
        core = self.prototype
        model_id, scaler_id = id(field(core, "__model")), id(field(core, "__scaler"))
        # Caller can forcibly mutate its own frozen dataclass, but constructor detached it.
        object.__setattr__(self.initial_limits, "max_deliveries", 1)
        self.assertEqual(field(core, "__limits").max_deliveries, 65536)
        original_predict = m._runner._predict
        def count_real(*args, **kwargs):
            FACTS["real_model_forwards"] += 1
            return original_predict(*args, **kwargs)
        results = []
        no_file = AssertionError("post-construction file read attempted")
        with ExitStack() as stack:
            stack.enter_context(patch.object(builtins, "open", side_effect=no_file))
            stack.enter_context(patch.object(Path, "open", side_effect=no_file))
            stack.enter_context(patch.object(Path, "read_bytes", side_effect=no_file))
            stack.enter_context(patch.object(m._runner, "read_pinned", side_effect=no_file))
            stack.enter_context(patch.object(m._runner, "_predict", count_real))
            token = self.start(core)
            for i, raw_record in enumerate(RAWS):
                result = core.observe(token, raw_record)
                saved = ORACLE["selected_records"][i]["saved_prediction"]
                self.assertEqual(result.sequence, saved["window"]["latest_sequence"])
                self.assertEqual(result.input_prefix_sha256, saved["input_prefix_sha256"])
                self.assertEqual(result.feature_tensor_sha256, saved["feature_tensor_sha256"])
                self.assertEqual(result.predicted_class_index, saved["predicted_class_index"])
                self.assertEqual(result.binding._asdict(), saved["binding"])
                self.assertEqual(result.metadata.filled_slots, i + 1)
                error = max(abs(a-b) for a,b in zip(result.probabilities, saved["probabilities"]))
                self.assertLessEqual(error, 2e-7)
                self.assertEqual(len(result.probabilities), 12)
                self.assertTrue(all(math.isfinite(v) and 0 <= v <= 1 for v in result.probabilities))
                self.assertLessEqual(abs(sum(result.probabilities)-1), 1e-5)
                self.assertIs(core.latest_result(token), result)
                self.assertLessEqual(len(result.encoded), 8192)
                results.append(result)
                self.actual.append({"index": i, "max_probability_abs_error": error,
                                    "feature_sha256": result.feature_tensor_sha256,
                                    "prefix_sha256": result.input_prefix_sha256,
                                    "class": result.predicted_class_index, "encoded_bytes": len(result.encoded)})
                if i == 0:
                    self.reject(core, lambda: core.observe(token, b'{"future":'), "schema_invalid")
                    self.assertIs(core.latest_result(token), result)
            receipt = core.end_session(token)
            token2 = self.start(core, generation=2, epoch=1)
            self.assertIsNone(core.latest_result(token2))
            self.assertEqual(core.state().lifetime_deliveries, 3)
            self.assertEqual(core.state().session_deliveries, 0)
            self.assertEqual((id(field(core, "__model")), id(field(core, "__scaler"))), (model_id, scaler_id))
            self.reject(core, lambda: core.observe(token, RAWS[0]), "stale_session")
            core.end_session(token2)
        self.assertEqual(FACTS["real_model_forwards"], 3)
        self.assertEqual(results[0].encoded, self.actual_result_encoded(results[0]))
        self.__class__.real_results = tuple(results)
        note("P01", real_model_forwards=3, parity=self.actual, no_postinit_file_reads=True,
             model_loads=self.model_loads, scaler_loads=self.scaler_loads, cold_restart=True)

    def actual_result_encoded(self, result):
        return m._runner.canonical_json(m._result_payload(result)) + b"\n"

    def test_P02_future_rejection_and_valid_continuation(self):
        a, b = self.clone(), self.clone()
        ta, tb = self.start(a), self.start(b)
        with patch.object(m._runner, "_predict", stub_predict):
            first = a.observe(ta, RAWS[0])
            b.observe(tb, RAWS[0])
            before = first.encoded
            self.reject(a, lambda: a.observe(ta, b'{"unread_future":'), "schema_invalid")
            accepted = a.observe(ta, RAWS[1])
            twin = b.observe(tb, RAWS[1])
        self.assertEqual(accepted, twin)
        self.assertEqual(first.encoded, before)
        note("P02", mode="private stub predictions", earlier_result_preserved=True, continuation_matches_twin=True)

    def test_P03_exact_raw_bytes_not_canonical_prefix(self):
        canonical = (json.dumps(ROWS[0], sort_keys=True, separators=(",", ":")) + "\n").encode()
        a,b = self.clone(),self.clone()
        ta,tb=self.start(a),self.start(b)
        with patch.object(m._runner,"_predict",stub_predict):
            a.observe(ta,RAWS[0]); ar=a.observe(ta,canonical)
            b.observe(tb,RAWS[0]); br=b.observe(tb,RAWS[0])
            self.assertEqual(ar.input_prefix_sha256, ORACLE["duplicate_prefix_controls"]["original_then_reencoded_semantic_duplicate"])
            self.assertEqual(br.input_prefix_sha256, ORACLE["duplicate_prefix_controls"]["original_then_exact_duplicate"])
            self.assertNotEqual(ar.input_prefix_sha256,br.input_prefix_sha256)
            crlf=canonical[:-1]+b"\r\n"; cr=a.observe(ta,crlf)
            self.assertEqual(cr.input_prefix_sha256,sha(RAWS[0]+canonical+crlf))
            self.assertEqual(cr.feature_tensor_sha256,ar.feature_tensor_sha256)
        note("P03", mode="private stub predictions", distinct_byte_digests=True, crlf_preserved=True)

    def test_P04_duplicate_delivery_not_acquisition(self):
        core=self.clone();token=self.start(core)
        first_raw=raw(changed(value_0=1))
        equivalent=raw(changed(value_0=1.0),sort_keys=True)
        with patch.object(m._runner,"_predict",side_effect=stub_predict) as predict:
            first=core.observe(token,first_raw)
            second=core.observe(token,equivalent)
            third=core.observe(token,equivalent)
            self.assertEqual(predict.call_count,1)
        self.assertEqual([first.delivery_index,second.delivery_index,third.delivery_index],[0,1,2])
        self.assertEqual(third.metadata.accepted_observations,1)
        self.assertEqual(third.metadata.idempotent_repeats,2)
        self.assertIs(first.probabilities,third.probabilities)
        self.assertEqual(third.input_prefix_sha256,sha(first_raw+equivalent+equivalent))
        self.assertNotEqual(first.encoded,third.encoded)
        note("P04", mode="private stub predictions", accepted_deliveries=3, acquisitions=1,
             idempotent_repeats=2, predict_calls=1)

    def test_P05_conflicting_masked_duplicate_regression_and_zero(self):
        core=self.clone();token=self.start(core)
        row=changed(valid_0=False)
        with patch.object(m._runner,"_predict",stub_predict):
            core.observe(token,raw(row))
            self.reject(core,lambda:core.observe(token,raw(changed(row,value_0=row["value_0"]+1))),"schema_invalid")
            self.reject(core,lambda:core.observe(token,raw(changed(row,sequence=row["sequence"]-1))),"schema_invalid")
            z=self.clone();tz=self.start(z)
            z.observe(tz,raw(changed(value_0=0)))
            rz=z.observe(tz,raw(changed(value_0=-0.0)))
            self.assertEqual(rz.metadata.idempotent_repeats,1)
        note("P05", mode="private stub predictions", masked_conflict_rejected=True, regression_rejected=True, signed_zero_idempotent=True)

    def test_P06_malformed_types_schema_binding_and_bounds(self):
        core=self.clone();token=self.start(core)
        class BytesSubclass(bytes): pass
        class NeverIterate:
            def __iter__(self): raise AssertionError("future iterator consumed")
        cases=[
            b"", b"{", b"\xff", b"[]",b"null",b'"not-object"', RAWS[0]+RAWS[1],
            RAWS[0].rstrip()[:-1]+b',"sequence":7327}', b" "*16385,
            BytesSubclass(RAWS[0]),bytearray(RAWS[0]),memoryview(RAWS[0]),ROWS[0],NeverIterate(),
        ]
        for changes in [
            {"sequence":True},{"sequence":1.0},{"sequence":-1},{"sequence":2**64},
            {"value_0":True},{"value_0":2**53+1},{"valid_0":1},{"valid_3":0},
            {"run_id":"wrong"},{"run_id":"\ud800"},{"run_id":"x"*129},
            {"source_domain":"software_fixture"},{"profile_id":"sim_em_v2"},
            {"preprocessing_sha256":"0"*64},
            {"label":65000},{"truth":True},{"future":0},{"timestamp":1},
        ]:
            cases.append(raw(changed(**changes)))
        missing=dict(ROWS[0]);missing.pop("valid_3");cases.append(raw(missing))
        for number in [b"NaN",b"Infinity",b"-Infinity",b"1e999"]:
            marker=raw(changed(value_0="MARKER"))
            cases.append(marker.replace(b'"MARKER"',number))
        codes=[]
        with patch.object(m._runner,"_predict",side_effect=AssertionError("invalid record reached inference")):
            for candidate in cases:
                codes.append(self.reject(core,lambda candidate=candidate:core.observe(token,candidate)))
        self.assertEqual(core.state().lifetime_deliveries,0)
        note("P06", negative_cases=len(cases), exception_codes=sorted(set(codes)), all_nonmutating=True)

    def test_P07_postbuilder_float32_overflow_atomic_retry(self):
        core,twin=self.clone(),self.clone()
        token,tt=self.start(core),self.start(twin)
        with patch.object(m._runner,"_predict",side_effect=stub_predict) as predict:
            core.observe(token,RAWS[0]);twin.observe(tt,RAWS[0])
            calls=predict.call_count
            overflow=raw(changed(ROWS[1],value_0=1e45))
            code=self.reject(core,lambda:core.observe(token,overflow))
            self.assertEqual(predict.call_count,calls) # actual _tensor rejected before predict
            self.assertEqual(core.observe(token,RAWS[1]),twin.observe(tt,RAWS[1]))
        note("P07", mode="actual tensor conversion / private prediction stub", normalized_double=ORACLE["overflow_control"]["normalized_double"],
             overflow_code=code, no_prediction_on_overflow=True, retry_matches_twin=True)

    def test_P08_inference_serialization_and_end_failure_atomicity(self):
        core=self.clone();token=self.start(core)
        with patch.object(m._runner,"_predict",side_effect=RuntimeError("fault-"+"x"*500)):
            self.reject(core,lambda:core.observe(token,RAWS[0]),"transaction_failed")
        with patch.object(m._runner,"_predict",stub_predict), \
             patch.object(m._runner,"canonical_json",side_effect=ValueError("private-serialization-fault")):
            self.reject(core,lambda:core.observe(token,RAWS[0]),"transaction_failed")
        with patch.object(m._runner,"_predict",stub_predict):
            result=core.observe(token,RAWS[0])
        with patch.object(m._runner,"canonical_json",side_effect=ValueError("end-private-fault")):
            self.reject(core,lambda:core.end_session(token),"transaction_failed")
        self.assertIs(core.latest_result(token),result)
        receipt=core.end_session(token)
        self.assertEqual(receipt.session_deliveries,1)
        note("P08", mode="private failure injections/stub success", inference_rollback=True, serialization_rollback=True, end_rollback=True, retry_end_transitions=2)

    def test_P09_duplicate_output_overlimit_atomic(self):
        core=self.clone();token=self.start(core)
        canonical=m._runner.canonical_json
        with patch.object(m._runner,"_predict",side_effect=stub_predict) as predict:
            first=core.observe(token,RAWS[0])
            with patch.object(m._runner,"canonical_json",side_effect=lambda payload:canonical(payload)+b" "*8192):
                self.reject(core,lambda:core.observe(token,RAWS[0]),"output_limit")
            self.assertEqual(predict.call_count,1)
            second=core.observe(token,RAWS[0])
            self.assertEqual(predict.call_count,1)
        self.assertEqual(second.metadata.idempotent_repeats,1)
        self.assertEqual(second.input_prefix_sha256,sha(RAWS[0]*2))
        self.assertIsNot(first,second)
        small=self.clone(m.StreamLimits(max_output_bytes=512));ts=self.start(small)
        with patch.object(m._runner,"_predict",stub_predict):
            self.reject(small,lambda:small.observe(ts,RAWS[0]),"output_limit")
        note("P09", mode="private valid-JSON whitespace oversize injection/stub success",
             duplicate_size_guard=True, failed_duplicate_rollback=True, lower_output_cap=512)

    def test_P10_identity_stale_foreign_ended_tokens_and_bindings(self):
        core,foreign=self.clone(),self.clone()
        token,foreign_token=self.start(core),self.start(foreign)
        self.assertEqual(token,foreign_token);self.assertIsNot(token,foreign_token)
        copies=[m.SessionToken(*token),copy.copy(token),token._replace(),foreign_token]
        for other in copies:
            self.assertIsNot(other,token)
            self.reject(core,lambda other=other:core.observe(other,RAWS[0]),"stale_session")
            self.reject(core,lambda other=other:core.end_session(other),"stale_session")
        self.reject(core,lambda:self.start(core,generation=2,epoch=1),"active_session")
        core.end_session(token)
        self.reject(core,lambda:core.observe(token,RAWS[0]),"inactive_session")
        token2=self.start(core,generation=2,epoch=1)
        for method in [lambda:core.observe(token,RAWS[0]),lambda:core.end_session(token),lambda:core.latest_result(token)]:
            self.reject(core,method,"stale_session")
        self.assertIsNone(core.latest_result(token2))
        note("P10", strict_identity=True, copied_foreign_stale_ended_rejected=True, active_reset_rejected=True)

    def test_P11_lifecycle_integer_utf8_highwaters_and_start_failure(self):
        core=self.clone()
        class IntSubclass(int): pass
        invalid=[
            {"generation":0},{"generation":-1},{"generation":True},{"generation":2**32},{"generation":IntSubclass(1)},
            {"epoch":-1},{"epoch":True},{"epoch":2**32},{"run_id":""},{"run_id":b"bytes"},
            {"run_id":"\ud800"},{"run_id":"界"*43},
        ]
        for change in invalid:
            args={"generation":1,"epoch":0,"run_id":ROWS[0]["run_id"]};args.update(change)
            self.reject(core,lambda args=args:core.start_session(**args))
        before=frozen_fingerprint(core)
        with patch.object(m,"CurveWindowBuilder",side_effect=RuntimeError("private-start-builder-fault")):
            with self.assertRaises(RuntimeError):
                self.start(core)
        self.assertEqual(frozen_fingerprint(core),before)
        token=self.start(core,run_id="界"*42)
        self.assertEqual(len(token.binding.run_id.encode()),126)
        core.end_session(token)
        self.reject(core,lambda:self.start(core,generation=1,epoch=1),"stale_session")
        self.reject(core,lambda:self.start(core,generation=2,epoch=0),"stale_session")
        next_token=self.start(core,generation=2,epoch=1,run_id="x"*128)
        self.assertEqual(core.state().sessions_started,2)
        core.end_session(next_token)
        maximum=self.clone();mt=self.start(maximum,generation=2**32-1,epoch=2**32-1)
        maximum.end_session(mt)
        self.reject(maximum,lambda:self.start(maximum,generation=2**32,epoch=2**32),"bounds_invalid")
        self.reject(maximum,lambda:self.start(maximum,generation=1,epoch=0),"stale_session")
        note("P11", negative_transition_cases=len(invalid), start_failure_nonmutating=True,
             generation_epoch_monotonic=True, uint32_max_no_wrap=True, utf8_limits=[126,128])

    def test_P12_uint64_huge_gap_and_independent_scalar_features(self):
        core=self.clone();token=self.start(core)
        first=changed(sequence=0);last=changed(sequence=2**64-1,value_0=17.0)
        with patch.object(m._runner,"_predict",stub_predict):
            core.observe(token,raw(first));result=core.observe(token,raw(last))
            self.assertEqual(result.sequence,2**64-1)
            self.assertEqual((result.metadata.filled_slots,result.metadata.missing_slots,result.metadata.dropped_oldest),(1,127,1))
            self.assertEqual(result.feature_tensor_sha256,scalar_feature([last]))
            self.assertEqual(len(field(core,"__committed").active.builder._slots),128)
            duplicate=core.observe(token,raw(last))
            self.assertEqual(duplicate.metadata.idempotent_repeats,1)
            self.reject(core,lambda:core.observe(token,raw(changed(last,sequence=2**64))))
            self.reject(core,lambda:core.observe(token,raw(first)))
            normal=self.clone();nt=self.start(normal)
            later=changed(first,sequence=3)
            normal.observe(nt,raw(first));nr=normal.observe(nt,raw(later))
            self.assertEqual((nr.metadata.filled_slots,nr.metadata.missing_slots),(2,126))
            self.assertEqual(nr.feature_tensor_sha256,scalar_feature([first,later]))
        note("P12", mode="actual tensor/private prediction stub", uint64_preserved=2**64-1,
             huge_gap_filled=1, normal_gap_filled=2, scalar_hashes_match=True)

    def test_P13_missing_masks_rdep_policy_negative_values(self):
        core=self.clone();token=self.start(core)
        a=changed(value_0=-2.0,value_1=123.0,valid_1=False,value_2=0.0,value_3=0.0)
        b=changed(a,sequence=a["sequence"]+1,value_3=-2.0)
        c=changed(b,sequence=b["sequence"]+1,valid_0=False,valid_1=False,valid_2=False,valid_3=False)
        with patch.object(m._runner,"_predict",stub_predict):
            results=[core.observe(token,raw(r)) for r in [a,b,c]]
        self.assertEqual(results[0].latest_valid_masks,(1.0,0.0,1.0,0.0))
        self.assertEqual(results[1].latest_valid_masks,(1.0,0.0,1.0,0.0))
        self.assertEqual(results[2].latest_valid_masks,(0.0,)*4)
        for i,r in enumerate(results):
            self.assertEqual(r.feature_tensor_sha256,scalar_feature([a,b,c][:i+1]))
        note("P13", mode="actual tensor/private prediction stub", rdep_nonpositive_missing=True,
             negative_identity_channel_preserved=True, masks_and_scalar_hashes_match=True)

    def test_P14_limits_lifetime_memory_and_only_reductions(self):
        limits={"max_record_bytes":16384,"max_output_bytes":8192,"max_binding_bytes":128,
                "max_deliveries":65536,"max_total_bytes":64*1024*1024,"max_sessions":1024}
        for name,maximum in limits.items():
            with self.assertRaises(m.StreamError):
                m.StreamLimits(**{name:maximum+1})
            with self.assertRaises(m.StreamError):
                m.StreamLimits(**{name:True})
        with patch.object(m._runner,"_predict",stub_predict):
            d=self.clone(m.StreamLimits(max_deliveries=1));dt=self.start(d)
            d.observe(dt,RAWS[0]);self.reject(d,lambda:d.observe(dt,RAWS[1]),"stream_limit")
            d.end_session(dt);dt2=self.start(d,generation=2,epoch=1)
            self.reject(d,lambda:d.observe(dt2,RAWS[0]),"stream_limit")
            b=self.clone(m.StreamLimits(max_total_bytes=len(RAWS[0])));bt=self.start(b)
            b.observe(bt,RAWS[0]);self.reject(b,lambda:b.observe(bt,RAWS[0]),"stream_limit")
            b.end_session(bt);bt2=self.start(b,generation=2,epoch=1)
            self.reject(b,lambda:b.observe(bt2,RAWS[0]),"stream_limit")
            small=self.clone(m.StreamLimits(max_record_bytes=1));st=self.start(small)
            self.reject(small,lambda:small.observe(st,RAWS[0]),"record_limit")
            slots=self.clone();slt=self.start(slots)
            for i in range(12):
                slots.observe(slt,raw(changed(sequence=i*1000)))
            active=field(slots,"__committed").active
            self.assertEqual(active.builder._slots.maxlen,128)
            self.assertEqual(len(active.builder._slots),128)
            self.assertIs(core_latest:=slots.latest_result(slt),active.latest)
            self.assertIsInstance(active.prefix, type(hashlib.sha256()))
            self.assertFalse(hasattr(slots,"__dict__"))
            self.assertEqual(set(vars(active)),{"token","builder","prefix","deliveries","total_bytes","latest"})
        s=self.clone(m.StreamLimits(max_sessions=1));t=self.start(s);s.end_session(t)
        self.assertEqual(s.state().lifecycle_transitions,2)
        self.reject(s,lambda:self.start(s,generation=2,epoch=1),"lifecycle_limit")
        narrow=self.clone(m.StreamLimits(max_binding_bytes=5))
        self.reject(narrow,lambda:self.start(narrow,run_id="123456"),"binding_invalid")
        note("P14", mode="private fixture/stub success", only_lower_limits=True, lifetime_caps_survive_restart=True,
             sample_deliveries=12, bounded_slots=128, only_latest_retained=True, transitions_bound=2)

    def test_P15_deep_immutable_detached_outputs_and_no_stale_setter(self):
        core=self.clone();token=self.start(core)
        with patch.object(m._runner,"_predict",stub_predict):
            first=core.observe(token,RAWS[0]);before=first.encoded
            def immutable(value):
                if value is None or type(value) in (int,float,str,bool,bytes):return True
                return isinstance(value,tuple) and all(immutable(v) for v in value)
            self.assertTrue(immutable(first));self.assertTrue(immutable(token))
            for target,name,value in [(first,"sequence",0),(token,"epoch",99),(first.binding,"run_id","other")]:
                with self.assertRaises((AttributeError,TypeError)):
                    object.__setattr__(target,name,value)
            decoded=json.loads(first.encoded);decoded["probabilities"][0]=99;decoded["binding"]["run_id"]="mutated"
            caller_copy=first._replace(sequence=0)
            self.assertEqual(caller_copy.sequence,0);self.assertIs(core.latest_result(token),first)
            with self.assertRaises(AttributeError):
                core.latest_result=caller_copy
            core.end_session(token);newtoken=self.start(core,generation=2,epoch=1)
            second=core.observe(newtoken,RAWS[1])
        self.assertEqual(first.encoded,before)
        self.assertNotEqual(first.generation,second.generation)
        self.assertEqual(second.metadata.filled_slots,1)
        note("P15", mode="private stub success", deep_immutable=True, caller_json_copy_detached=True,
             stale_caller_copy_cannot_install=True, old_result_survives_end_restart=True)

    def test_P16_reentry_busy_and_no_core_threads(self):
        core=self.clone();token=self.start(core)
        rejected=[]
        def reentry(*args):
            operations=[lambda:core.state(),lambda:core.latest_result(token),
                        lambda:core.observe(token,RAWS[0]),lambda:core.end_session(token),
                        lambda:self.start(core,generation=2,epoch=1)]
            for operation in operations:
                with self.assertRaises(m.StreamError) as caught:operation()
                rejected.append(caught.exception.code)
            return stub_predict(*args)
        with patch.object(m._runner,"_predict",reentry), \
             patch.object(threading,"Thread",side_effect=AssertionError("core created thread")):
            result=core.observe(token,RAWS[0])
            self.assertIs(core.latest_result(token),result)
            core.end_session(token)
        self.assertEqual(rejected,["busy"]*5)
        self.assertEqual(core.state().lifetime_deliveries,1)
        note("P16", mode="private reentry callback/stub success", busy_rejections=5, single_outer_commit=True, core_thread_constructions=0)

    def test_P17_explicit_profile_fixed_model_zero_authority(self):
        with patch.object(m._runner,"read_pinned",side_effect=AssertionError("invalid configuration read asset")):
            for kwargs,code in [({"profile":"sim_em_v2"},"sim_em_model_missing"),
                                ({"profile":"other"},"profile_invalid"),({"device":"hip"},"device_invalid"),
                                ({"expected_manifest_sha256":"0"*64},"hash_mismatch"),({"limits":{}},"bounds_invalid")]:
                with self.assertRaises(m.StreamError) as caught:m.FrozenForceStream(**kwargs)
                self.assertEqual(caught.exception.code,code)
                if code=="sim_em_model_missing":self.assertTrue(caught.exception.blocked)
        params=set(inspect.signature(m.FrozenForceStream).parameters)
        self.assertFalse(params & {"model","callback","backend","result","clock","output_path","observations","iterator"})
        for result in self.real_results:
            doc=json.loads(result.encoded)
            self.assertIs(doc["movement_authorized"],False)
            self.assertIsNone(doc["motion_bytes"])
            self.assertEqual(doc["formal_acceptance"],"incomplete")
            self.assertIs(result.movement_authorized,False)
            self.assertEqual(result.class_order,tuple(ORACLE["selected_records"][0]["saved_prediction"].get("class_order", [30000,65030,65000,80000,74000,70000,70032,88000,86000,99000,90000,93000])))
            self.assertEqual(dict(result.artifact_pins)["model_manifest_sha256"],m.FIXED_MANIFEST_SHA256)
            self.assertFalse(set(doc)&{"BOOT","boot_id","observed_seq","capture_time","sample_age","action","grant"})
        # Tie behavior is a synthetic stub control, not a statement about real logits.
        tie=self.clone();tt=self.start(tie)
        with patch.object(m._runner,"_predict",stub_predict):
            result=tie.observe(tt,RAWS[0])
        self.assertEqual(result.predicted_class_index,0)
        note("P17", fixed_model_and_profile=True, sim_em_blocked=True, no_authority=True,
             firstmax_tie="private synthetic uniform prediction only")

if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    FACTS["unittest"]={"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skips":len(result.skipped),"success":result.wasSuccessful()}
    FACTS["quality"]="unchanged FAIL; no heldout/train/oldbaseline/benchmark"
    (OUT/"control-facts.json").write_text(json.dumps(FACTS,indent=2,allow_nan=False)+"\n",encoding="utf8",newline="\n")
    print(json.dumps({"summary":FACTS["unittest"],"real_model_forwards":FACTS["real_model_forwards"],
                      "private_stub_predictions":FACTS["private_stub_predictions"]},sort_keys=True),flush=True)
    sys.exit(0 if result.wasSuccessful() else 1)


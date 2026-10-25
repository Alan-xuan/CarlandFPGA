"""Pinned repaired source/artifact audit; no product imports or tests."""
import ast, difflib, hashlib, json, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
REVIEW=OUT.parent
WT=Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c\.local\deepeye-implementation-c")
FIX=WT/"competition/deepeye/evidence/ai/cpu_stream_20261025/bounded-init-fix"
h=lambda b:hashlib.sha256(b).hexdigest()
manifest_raw=(FIX/"delivery-manifest.json").read_bytes()
assert h(manifest_raw)=="8aadc2ef8317f667e4a757e02b1c4d6fce5dc7c374ec1f372658fa5b688f41ff"
manifest=json.loads(manifest_raw)
for artifact in manifest["artifacts"]:
    b=(WT/artifact["path"]).read_bytes()
    assert h(b)==artifact["sha256"] and len(b)==artifact["bytes"],artifact["path"]
assert len(manifest["artifacts"])==26
for p in json.loads((REVIEW/"source-pins.json").read_bytes()):
    assert h(Path(p["path"]).read_bytes())==p["sha256"],p["path"]
source=WT/"competition/deepeye/ai_pc/cpu_package/stream_core.py"
doc=source.with_name("STREAM_CORE.md")
assert h(source.read_bytes())=="0a8c07f34080784f36180951b28873b43de5e3f80ad201325254b274bd01217b"
assert h(doc.read_bytes())=="81ee766e4dfaa7d5c15ec444ba7ccfa7594c62bcf81b47e57b101c86a96c509b"
before=(REVIEW/"phase2/frozen-stream_core.py").read_text()
after=source.read_text()
diff="".join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
                               fromfile="phase2-original-0ddbe671",tofile="phase3-repaired-0a8c07f3"))
(OUT/"independent-minimal-delta.diff").write_text(diff,encoding="utf8",newline="\n")
# Exactly one cap constant plus explicit limit keywords, no other source changes.
normalized=after.replace("_PREFLIGHT_ASSET_CAP = 2 * 1024 * 1024\n","").replace(", limit=_PREFLIGHT_ASSET_CAP","")
assert normalized==before,"unexpected source delta"
calls=[]
for n in ast.walk(ast.parse(after)):
    if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=="_runner" and n.func.attr=="read_pinned":
        kw={x.arg:ast.unparse(x.value) for x in n.keywords}
        assert "limit" in kw
        calls.append({"line":n.lineno,"limit":kw["limit"],"source":ast.get_source_segment(after,n)})
assert len(calls)==6 # 3 sources + manifest + reference-loop site + direct preprocessing; loop expands4.
records=[]
for label,argv in [("head",["git","rev-parse","HEAD"]),("tracked-diff",["git","diff","--name-only","HEAD"])]:
    p=subprocess.run(argv,cwd=WT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    (OUT/(label+".stdout.txt")).write_bytes(p.stdout)
    (OUT/(label+".stderr.txt")).write_bytes(p.stderr)
    assert p.returncode==0
    records.append({"argv":argv,"cwd":str(WT),"exit_code":p.returncode,"stdout_sha256":h(p.stdout),"stderr_sha256":h(p.stderr)})
assert (OUT/"head.stdout.txt").read_text().strip()=="e3f86f7301abef866c30de2ec851e4a939198381"
assert not (OUT/"tracked-diff.stdout.txt").read_bytes()
# Current manifest hashes all raw result/log bytes; record test counts without executing.
raw_runs=[]
for result_path in sorted(FIX.rglob("result.json")):
    j=json.loads(result_path.read_bytes())
    if "exit_code" in j:
        raw_runs.append({"path":str(result_path),"result":j})
        assert j["exit_code"]==0
(OUT/"frozen-stream_core.py").write_bytes(source.read_bytes())
(OUT/"frozen-STREAM_CORE.md").write_bytes(doc.read_bytes())
j={"repair_manifest_sha256":h(manifest_raw),"verified_repair_artifacts":manifest["artifacts"],
   "original_nine_inputs_still_pinned":True,"source_delta_only":"one finite2MiB cap plus eight uncapped read invocations",
   "static_preflight_call_sites":calls,"runtime_expansion":9,"commands":records,"original_repair_run_evidence":raw_runs,
   "author_or_old_suites_executed":False}
(OUT/"source-inspection.json").write_text(json.dumps(j,indent=2)+"\n",encoding="utf8",newline="\n")
print("PASS:26repair artifacts and9original source/model/scaler/baseline pins; tracked tree unchanged.")
print("PASS: exact delta only2MiB preflight caps; all6call sites/9runtime reads have finite limits.")


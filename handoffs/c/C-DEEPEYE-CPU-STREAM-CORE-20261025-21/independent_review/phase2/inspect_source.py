"""Read-only source/diff/artifact audit; no product import and no suite execution."""
import hashlib,json,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
WT=Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c\.local\deepeye-implementation-c")
SOURCE=WT/"competition/deepeye/ai_pc/cpu_package/stream_core.py"
DOC=SOURCE.with_name("STREAM_CORE.md")
AUTHOR=WT/"competition/deepeye/evidence/ai/cpu_stream_20261025/author"
h=lambda b:hashlib.sha256(b).hexdigest()
pins={str(SOURCE.relative_to(WT)):"0ddbe6710be81df3e428f63809257dea69c35fee1aabd24cd9bb58eb71b41976",
      str(DOC.relative_to(WT)):"3950ef879b879d928ba8a3392b9de803f3354d036afa9ed5525d96df36924c1d",
      str((AUTHOR/"delivery-manifest.json").relative_to(WT)):"220f3c1bdcfc6722da937be45d9e41da587a09563733e0045894f66471315511"}
for rel,digest in pins.items():
    assert h((WT/rel).read_bytes())==digest,(rel,"changed")
delivery=json.loads((AUTHOR/"delivery-manifest.json").read_bytes())
checked=[]
for a in delivery["artifacts"]:
    raw=(WT/a["path"]).read_bytes()
    assert len(raw)==a["bytes"] and h(raw)==a["sha256"],a["path"]
    checked.append(a)
assert len(checked)==22
commands=[]
for label,argv,expected_exit in [
    ("head",["git","rev-parse","HEAD"],0),
    ("tracked-diff",["git","diff","--name-only","HEAD"],0),
    ("new-source-diff",["git","diff","--no-index","--","/dev/null",str(SOURCE)],1),
]:
    r=subprocess.run(argv,cwd=WT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    (OUT/(label+".stdout.txt")).write_bytes(r.stdout)
    (OUT/(label+".stderr.txt")).write_bytes(r.stderr)
    assert r.returncode==expected_exit,(label,r.returncode)
    commands.append({"label":label,"argv":argv,"cwd":str(WT),"exit_code":r.returncode,
                     "stdout_sha256":h(r.stdout),"stderr_sha256":h(r.stderr)})
assert (OUT/"head.stdout.txt").read_text().strip()=="e3f86f7301abef866c30de2ec851e4a939198381"
assert not (OUT/"tracked-diff.stdout.txt").read_bytes(),"prior tracked files changed"
raw_evidence=[]
for part,methods in [("tests-01",16),("end-boundary-final",1)]:
    data=json.loads((AUTHOR/part/"result.json").read_bytes())
    stdout=(AUTHOR/part/"stdout.txt").read_bytes()
    stderr=(AUTHOR/part/"stderr.txt").read_bytes()
    assert data["exit_code"]==0
    assert data["stdout_sha256"]==h(stdout) and data["stderr_sha256"]==h(stderr)
    assert ("Ran "+str(methods)+" test") in stderr.decode("utf8"),part
    raw_evidence.append({"path":str(AUTHOR/part),"exit_code":0,"methods":methods,
                         "source_sha256":next(a["sha256"] for a in checked if a["path"].endswith(part+"/source-before/competition/deepeye/ai_pc/cpu_package/stream_core.py")),
                         "claim":"original recorded run only; not rerun"})
(OUT/"frozen-stream_core.py").write_bytes(SOURCE.read_bytes())
(OUT/"frozen-STREAM_CORE.md").write_bytes(DOC.read_bytes())
source_lines=SOURCE.read_text().splitlines()
runner=WT/"competition/deepeye/ai_pc/cpu_package/runner.py"
report={"input_pins":pins,"verified_artifacts":checked,"commands":commands,"author_raw_exit_evidence":raw_evidence,
        "finding":"constructor read_pinned limit omitted; runner reads unbounded before hash",
        "source_line_evidence":[{"line":i+1,"text":l} for i,l in enumerate(source_lines) if "_runner.read_pinned(" in l],
        "runner_line_evidence":[{"line":i+1,"text":l} for i,l in enumerate(runner.read_text().splitlines()) if 82<=i<=95],
        "not_executed":["author/old suites","Torch/model forward","17-group targeted controls pending repair","train/heldout/benchmark"],
        "product_writes":0}
(OUT/"source-inspection.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8",newline="\n")
print("PASS: source/doc/manifest pins,22artifacts, unchanged tracked tree, original16+1rawexits verified.")
print("CONFIRMED: unbounded constructor preflight before pinned-loader finite size checks.")


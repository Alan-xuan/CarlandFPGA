"""Read-only exact frozen-source/delivery/diff audit, no endpoint import."""
import hashlib,json,subprocess
from pathlib import Path
NODE=Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c")
WT=NODE/".local/deepeye-implementation-c"
MAIN=NODE/".local/main-20261015-01a14025/endpoint-20261027"
OUT=Path(__file__).resolve().parent
h=lambda b:hashlib.sha256(b).hexdigest()
freeze=json.loads((MAIN/"main/source-freeze-r1.json").read_bytes())
author=WT/"competition/deepeye/evidence/ai/cpu_endpoint_20261027/author/manifest.json"
mb=author.read_bytes()
assert h(mb)==freeze["manifest_sha256"]=="250f7a2662ecd41baf359701d404d74c58590081440e25337598850485908996"
manifest=json.loads(mb)
all_artifacts=manifest["sources"]+manifest["artifacts"]
for artifact in all_artifacts:
    b=(WT/artifact["path"]).read_bytes()
    assert h(b)==artifact["sha256"] and len(b)==artifact["bytes"],artifact["path"]
assert len(all_artifacts)==31
snapshot_pins=[]
for rel,digest in freeze["source_hashes"].items():
    b=(WT/rel).read_bytes()
    assert h(b)==digest
    snapshots=list((MAIN/"main/frozen-source-r1").rglob(Path(rel).name))
    assert len(snapshots)==1 and snapshots[0].read_bytes()==b,rel
    snapshot_pins.append({"path":rel,"bytes":len(b),"sha256":digest,"main_snapshot":str(snapshots[0])})
    if rel.endswith((".md","endpoint_protocol.py","process_endpoint.py")):
        (OUT/("frozen-"+Path(rel).name)).write_bytes(b)
# Prior nine C19 assets/source are read only for byte pins, never model loading.
original=json.loads((NODE/".local/main-20261015-01a14025/stream-core-20261025/review/source-pins.json").read_bytes())
for item in original:
    assert h(Path(item["path"]).read_bytes())==item["sha256"]
commands=[]
outputs={}
for stem,argv,code in [
    ("head",["git","rev-parse","HEAD"],0),
    ("tree",["git","ls-tree","-r","--name-only","HEAD"],0),
    ("changed",["git","diff","--name-only","HEAD"],0),
    ("protocol-diff",["git","diff","--no-index","--","/dev/null",str(WT/"competition/deepeye/ai_pc/cpu_package/endpoint_protocol.py")],1),
    ("driver-diff",["git","diff","--no-index","--","/dev/null",str(WT/"competition/deepeye/ai_pc/cpu_package/process_endpoint.py")],1),
]:
    p=subprocess.run(argv,cwd=WT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    (OUT/(stem+".stdout.txt")).write_bytes(p.stdout)
    (OUT/(stem+".stderr.txt")).write_bytes(p.stderr)
    assert p.returncode==code,(stem,p.returncode)
    outputs[stem]=p.stdout.decode("utf8")
    commands.append({"argv":argv,"cwd":str(WT),"exit_code":p.returncode,"expected":"new-file diff exists" if code==1 else "success",
                     "stdout_sha256":h(p.stdout),"stderr_sha256":h(p.stderr)})
assert outputs["head"].strip()=="b898e90c7248dec5a6dd0ee850c8a07e097e83aa"
old=set(outputs["tree"].splitlines());changed=set(outputs["changed"].splitlines())
assert not old&changed,sorted(old&changed)
raw_runs=[]
for artifact in manifest["artifacts"]:
    if artifact["path"].endswith("/result.json"):
        path=WT/artifact["path"];j=json.loads(path.read_bytes())
        if "exit_code" in j:
            assert j["exit_code"]==0
            for stream in ("stdout","stderr"):
                if stream+"_sha256" in j:
                    assert h(path.with_name(stream+".txt").read_bytes())==j[stream+"_sha256"]
            raw_runs.append({"path":str(path),"data":j,"scope":"original author recorded run only; not executed here"})
data={"freeze":freeze,"verified_artifacts":all_artifacts,"five_source_snapshot_pins":snapshot_pins,
      "original_nine_pins_unchanged":True,"prior_tree_entries":len(old),"prior_tree_tracked_changes":[],
      "commands":commands,"author_raw_runs":raw_runs,
      "author_test_contents_read_for_controls":False,"author_or_old_suite_executed":False}
(OUT/"source-inspection.json").write_text(json.dumps(data,indent=2)+"\n",encoding="utf8",newline="\n")
print("PASS:31artifacts/fiveexactfrozen snapshots,9originalpins, unchanged prior tracked tree, original raw author exits.")
print("New-source diff exits1 expected; no product writes or endpoint/model/CLI execution.")


"""Independent actual CLI corruption/missing/alias checks; raw ZIP bytes only."""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--product-root",type=Path,required=True);p.add_argument("--archive",type=Path,required=True);p.add_argument("--out",type=Path,required=True);args=p.parse_args();root=args.product_root.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
paths=["data/"+n for n in ("source_inventory.json","force_wells.json","splits.json","split_policy.json","label_schema.json","preprocessing.json","force_inventory.py","force_preprocess.py","grouping.py")]+["data/provenance/force_2020_v1/"+n for n in ("force_inventory.py","force_preprocess.py")]+["tools/verify_data.py"]
results=[]
for scenario,expected in (("positive",0),("default_full_blocked",2),("missing_snapshot",2),("corrupt_snapshot",1),("corrupt_live_helper",1),("snapshot_hardlink_output",1)):
 with tempfile.TemporaryDirectory(prefix="independent_provenance_") as temp:
  copied=Path(temp)/"product"
  for relative in paths:
   target=copied/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/relative,target)
  snapshot=copied/"data/provenance/force_2020_v1/force_inventory.py"
  if scenario=="missing_snapshot":snapshot.unlink()
  if scenario=="corrupt_snapshot":snapshot.write_bytes(snapshot.read_bytes()+b"\n# independent corruption\n")
  if scenario=="corrupt_live_helper":
   target=copied/"data/force_inventory.py";target.write_bytes(target.read_bytes()+b"\n# independent corruption\n")
  command=[sys.executable,"-X","utf8","-B",str(copied/"tools/verify_data.py")]
  if scenario!="default_full_blocked":command.extend(["--scope","force-offline","--archive",str(args.archive.resolve())])
  if scenario=="snapshot_hardlink_output":
   alias=copied/"snapshot_alias.py";before=hashlib.sha256(snapshot.read_bytes()).hexdigest();os.link(snapshot,alias);command.extend(["--output",str(alias)])
  run=subprocess.run(command,capture_output=True,cwd=copied);(out/(scenario+".stdout.txt")).write_bytes(run.stdout);(out/(scenario+".stderr.txt")).write_bytes(run.stderr)
  report=json.loads(run.stdout);assert run.returncode==expected,(scenario,run.returncode,run.stderr.decode());assert report["product_card_C01"]=="not_run"
  if scenario=="positive":assert report["status"]=="passed_offline_identity_consistency_only" and report["production_provenance"] is True
  elif expected==1:assert report["status"]=="failed"
  else:assert report["status"]=="blocked"
  if scenario=="snapshot_hardlink_output":assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==before and os.path.samefile(snapshot,alias)
  result={"scenario":scenario,"command":command,"exit_code":run.returncode,"expected_exit_code":expected,"status":report["status"],"stdout_sha256":hashlib.sha256(run.stdout).hexdigest(),"stderr_sha256":hashlib.sha256(run.stderr).hexdigest()};results.append(result);print(scenario,run.returncode,report["status"],flush=True)
summary={"task_id":"DEEPEYE-IMPLEMENTATION-20261014","task_version":1,"reviewer":"/root current C main","software_only":True,"cases":results,"source_sha256":{x:hashlib.sha256((root/x).read_bytes()).hexdigest() for x in paths},"archive":"raw identity stream only; no ZIP members opened, LAS values parsed, refit, training or heldout evaluation","runtime_board_system_acceptance":"not_run"};(out/"result.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")

"""Validate planning artifacts and arithmetic, never certify unrun hardware."""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def run():
    c = ROOT / "c"
    manifest = json.loads((c / "freeze_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_count"] >= 5
    assert manifest["peer_communication_before_lock"] is False
    for name, expected in manifest["files"].items():
        actual = hashlib.sha256((c / name).read_bytes()).hexdigest()
        assert actual == expected, "frozen input changed: " + name
    text = (ROOT / "taskbook_candidate.md").read_text(encoding="utf-8")
    ids = re.findall(r"^(G[0-8]\.\d+)\s", text, flags=re.M)
    assert len(ids) == len(set(ids)), "duplicate step IDs"
    expected = ["G%d.%d" % (g, i) for g, n in enumerate([3,4,3,3,3,3,3,3,1]) for i in range(1,n+1)]
    assert set(ids) == set(expected), "missing acceptance steps"
    budget = json.loads((c / "budget_result.json").read_text(encoding="utf-8"))
    assert abs(budget["nominal_occupancy"] - .8) < 1e-9
    scores = [(4.5,4.5,4.5,3.8,4.2,4.6),(3.5,4.5,4,3.8,4.5,4.2),(4,3.8,4.3,4.5,4,4.5),(4.7,4.5,3.8,3.3,3.3,4.7),(2.5,4.5,3.2,4.2,4.6,3.1)]
    weighted = [round(sum(w*x/5 for w,x in zip([25,20,20,15,10,10],s)),1) for s in scores]
    assert weighted == [87.5,80.3,82.9,82.6,71.3]
    return {"validation":"passed","scope":"planning structure and byte hashes only","C_candidates":5,"acceptance_steps":len(ids),"steps":ids,"scores":weighted,"hardware":"not_run","NPU_model":"not_run","three_node_external_review":"pending"}
if __name__ == "__main__":
    try:
        out=run()
        (ROOT/"c"/"plan_validation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(out,ensure_ascii=False))
    except Exception as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)


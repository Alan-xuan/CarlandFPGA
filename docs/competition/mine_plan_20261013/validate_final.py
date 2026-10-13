"""Validate C final planning deliverables; never certify unrun implementation."""
import hashlib,json,re,zipfile,sys
from pathlib import Path
R=Path(__file__).resolve().parent
def check():
    with zipfile.ZipFile(R/"c/frozen_portfolio_raw.zip") as z:
        freeze=json.loads(z.read("freeze_manifest.json"))
        assert freeze["candidate_count"]>=5 and freeze["peer_communication_before_lock"] is False
        for name,sha in freeze["files"].items():assert hashlib.sha256(z.read(name)).hexdigest()==sha,name
    text=(R/"taskbook_final.md").read_text(encoding="utf-8")
    ids=re.findall(r"^(G[0-8]\.\d+)\s",text,re.M)
    assert len(ids)==26 and len(set(ids))==26
    d=json.loads((R/"acceptance_final.json").read_bytes())
    assert d["version"]==2 and [s["id"] for s in d["steps"]]==ids
    for s in d["steps"]:
        assert s["status"]=="planned"
        assert all(s[k] for k in ["id","owner","reviewer","input","procedure","pass_criteria","evidence"])
    for broken in ["接口和COM","DRC独立复核DC","A/C最佳及","不要求等待C或三机"]:assert broken not in text,broken
    b=json.loads((R/"round2_budget.json").read_bytes())
    assert b["total_bps"]==207.5 and b["margin_to_80pct_bps"]==32.5
    assert "ROCm≥7.14" in text and "Ryzen 7 8845H" in text
    return {"status":"passed","scope":"planning structure, raw archive bytes and budget arithmetic only","steps":26,"C_candidates":freeze["candidate_count"],"core_design_occupancy":b["occupancy"],"RTL_simulation":"not_run","synthesis":"not_run","implementation":"not_run","hardware":"not_run","GPU_model":"not_run","NPU_model":"not_run"}
if __name__=="__main__":
    try:print(json.dumps(check(),ensure_ascii=False))
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)


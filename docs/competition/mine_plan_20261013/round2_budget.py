"""Second-round proposed shared half-duplex budget, no measured claims."""
import json
from pathlib import Path
def run():
    profiles=[("summary",34,4),("event_reserve",20,4),("command",24,8),("feedback_ack",22,8)]
    wire_bps=sum(n*10/period for _,n,period in profiles)
    guard_bps=.2/4*300
    r={"scope":"round2 proposal arithmetic only","baud":300,"format":"8N1","duplex":"half","profiles":[{"type":t,"total_frame_bytes":n,"nominal_period_s":s,"wire_bps":n*10/s} for t,n,s in profiles],"frame_bps":wire_bps,"guard_equivalent_bps":guard_bps,"total_bps":wire_bps+guard_bps,"occupancy":(wire_bps+guard_bps)/300,"margin_to_80pct_bps":240-wire_bps-guard_bps,"unverified":["guard duration","event burst envelope","timely receive slots","real GPU and task metrics"],"stage_status":"not_run"}
    assert r["total_bps"]==207.5 and r["margin_to_80pct_bps"]==32.5
    return r
if __name__=="__main__":
    r=run();Path(__file__).with_name("round2_budget.json").write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps(r,ensure_ascii=False))


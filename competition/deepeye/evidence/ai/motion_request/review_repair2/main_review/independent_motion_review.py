import sys,json,hashlib,importlib.util,unittest,argparse
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument("--product-root",type=Path,default=Path(__file__).resolve().parents[5])
args, remaining=parser.parse_known_args()
ROOT=args.product_root.resolve()
sys.argv=[sys.argv[0],*remaining]
sys.path.insert(0,str(ROOT))
s=importlib.util.spec_from_file_location("fixtures",ROOT/"tests/ai/control_broker/test_motion_request.py"); f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
from ai_pc.control_broker.motion_request import MotionRequestAdapter
class Review(unittest.TestCase):
 def run_nested(self,count,raises=False):
  emitted=[]
  class V:
   def verify_motion(v,check):
    for i in range(count): emitted.append(a.safe_stop(now_ns=(21+i)*f.MS))
    if raises: raise RuntimeError("after STOP")
  a=MotionRequestAdapter(context=f.CONTEXT,verifier=V());a.register_observation(f.observation())
  outer=f.submit(a,f.candidate(10))
  self.assertIsNone(outer.request_bytes);self.assertEqual(outer.reason,"superseded_during_verification")
  self.assertEqual([(x.candidate_id,x.command_seq) for x in emitted],[(11+i,i) for i in range(count)])
  for x in emitted: self.assertEqual(json.loads(x.request_bytes)["target"]["action"],0)
  return a
 def test_public_stop_survives_callback_success_and_failure(self):
  for n in (1,2,8):
   for raises in (False,True):
    with self.subTest(n=n,raises=raises): self.run_nested(n,raises)
 def test_nested_move_remains_newest_and_seq_is_not_consumed_by_outer(self):
  emitted=[]
  class V:
   def verify_motion(v,check):
    if check.candidate_id==10: emitted.append(f.submit(a,f.candidate(20),issue=21*f.MS,now=21*f.MS))
  a=MotionRequestAdapter(context=f.CONTEXT,verifier=V());a.register_observation(f.observation())
  outer=f.submit(a,f.candidate(10));self.assertIsNone(outer.request_bytes)
  self.assertEqual((emitted[0].candidate_id,emitted[0].command_seq),(20,0))
  stop=a.safe_stop(now_ns=22*f.MS);self.assertEqual((stop.candidate_id,stop.command_seq),(21,1))
 def test_registering_new_observation_supersedes_old_request(self):
  class V:
   def verify_motion(v,check): a.register_observation(f.observation(sequence=8,ordinal=70001,tick=101,lower=f.MS))
  a=MotionRequestAdapter(context=f.CONTEXT,verifier=V());a.register_observation(f.observation())
  out=f.submit(a);self.assertIsNone(out.request_bytes);self.assertEqual(out.reason,"superseded_during_verification")
 def test_retained_callback_timing_and_context_never_rewrite_audit_or_wire(self):
  retained=[]
  class V:
   def verify_motion(v,check):
    retained.append(check);object.__setattr__(check.timing,"deadline_ns",0);object.__setattr__(check.context,"session",999)
  a=MotionRequestAdapter(context=f.CONTEXT,verifier=V());a.register_observation(f.observation())
  out=f.submit(a);self.assertIsNotNone(out.request_bytes);wire=out.request_bytes
  self.assertEqual(out.timing.deadline_ns,1020*f.MS);self.assertEqual(json.loads(wire)["context"]["session"],42)
  object.__setattr__(retained[0].timing,"deadline_ns",2**63-1);object.__setattr__(retained[0].observation.context,"session",888)
  self.assertEqual(out.timing.deadline_ns,1020*f.MS);self.assertEqual(a.context.session,42);self.assertEqual(out.request_bytes,wire)
if __name__=="__main__":
 print("source_sha256="+hashlib.sha256((ROOT/"ai_pc/control_broker/motion_request.py").read_bytes()).hexdigest(),flush=True)
 unittest.main(verbosity=2)

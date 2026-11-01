"""Two new isolated controls, no author test imports or actual Root execution.
CLI: PATCHED_TREE OUTPUT_DIRECTORY. Synthetic dependency boundary only.
"""
import ast,hashlib,json,sys,threading,types
from pathlib import Path
def main():
 root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
 modulepath=root/'competition/deepeye/simulation/authority/g05p_runtime_v1.py';actorpath=root/'competition/deepeye/simulation/authority/actor_composition.py'
 for name in ('isolated49','isolated49.simulation','isolated49.simulation.authority','isolated49.integration'):
  p=types.ModuleType(name);p.__path__=[];sys.modules[name]=p
 w=types.ModuleType('isolated49.integration.pc_direct_watchdog');w.PcDirectWatchdog=type('UnusedWatchdog',(),{});sys.modules[w.__name__]=w
 m=types.ModuleType('isolated49.simulation.authority.g05p_runtime_v1');sys.modules[m.__name__]=m;exec(compile(modulepath.read_bytes(),str(modulepath),'exec'),m.__dict__)
 # Actual factory bodies and actual new gate; no fake gate returning success.
 nodes=[n for n in ast.parse(actorpath.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name in ('_production_channels','_create_authority_for_original_world')]
 class ActivationUnavailable(ValueError):pass
 calls=dict(claim=0,actor=0,channel=0,clock=0)
 class Capability:
  def _claim(self,*args):calls['claim']+=1;raise AssertionError('unexpected capability claim')
 def actor(*args,**kwargs):calls['actor']+=1;raise AssertionError('unexpected actor allocation')
 def clockbinding(value):calls['clock']+=1;return value
 # production_channels is wrapped only to count accidental entrance, not alter it.
 original=m.production_channels
 def channel(*args,**kwargs):calls['channel']+=1;return original(*args,**kwargs)
 m.production_channels=channel
 g=dict(__name__='isolated49.simulation.authority.actor_composition',__package__='isolated49.simulation.authority',ActivationUnavailable=ActivationUnavailable,clocks=types.SimpleNamespace(_require_binding=clockbinding),ActorComposition=actor,_RETAINED=[])
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(actorpath),'exec'),g)
 refusals=[]
 for profile in (None,m.G05Profile(b'{}'),m.G05Profile(b'{}',True)):
  cfg=types.SimpleNamespace(g05p_profile=profile,owned_invocation_v1=None)
  try:g['_create_authority_for_original_world'](cfg,Capability(),host_clock=object())
  except ValueError as e:refusals.append(dict(profile='legacy' if profile is None else 'disabled' if not profile.enabled else 'enabled',type=type(e).__name__,message=str(e)))
  else:raise AssertionError('factory unexpectedly accepted')
 assert calls==dict(claim=0,actor=0,channel=0,clock=3)
 assert refusals[0]['type']=='ActivationUnavailable' and all('C49_PARTIAL' in r['message'] for r in refusals[1:])
 first=dict(case='factory-default-and-explicit-profiles-before-any-claim',passed=True,calls=calls,refusals=refusals)
 # Allocate no original credential: isolate checkpoint's irreversible clock latch.
 c=object.__new__(m.G05Channels);ticks=[100];checks=dict(operation=0,ssh=0,producer=0)
 def count(k):checks[k]+=1
 c._thread=threading.get_ident();c._clock=lambda:ticks[0];c._last_time=None;c._revoked=False;c._session_deadline_ns=200
 c._config=object();c._capability=object();c._refs=types.SimpleNamespace(session=types.SimpleNamespace(_unknown=False,_closed=False,_check=lambda:count('ssh')))
 c._producer=types.SimpleNamespace(_failed=False,_closed=False,_check=lambda:count('producer'));c._chain=types.SimpleNamespace(sequence=types.SimpleNamespace(closed=False))
 c._operation=types.SimpleNamespace(config=c._config,link=c._capability,clock=c._clock,_check=lambda:count('operation'))
 assert c.checkpoint()==100
 errors=[]
 for tick in (99,101):
  ticks[0]=tick
  try:c.checkpoint()
  except ValueError as e:errors.append(str(e))
  else:raise AssertionError('clock regression or retirement revived')
 assert c._revoked and checks==dict(operation=1,ssh=1,producer=1)
 assert 'regressed' in errors[0] and 'retired' in errors[1]
 second=dict(case='clock-regression-followed-by-forward-time-cannot-revive',passed=True,errors=errors,checks=checks,revoked=c._revoked)
 summary=dict(module_sha256=hashlib.sha256(modulepath.read_bytes()).hexdigest(),actor_sha256=hashlib.sha256(actorpath.read_bytes()).hexdigest(),controls=[first,second],passed=True,synthetic_boundary=True,actual_Root_execution=False,native_calls=0,old_suites_run=False)
 (out/'results.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));return 0
if __name__=='__main__':raise SystemExit(main())

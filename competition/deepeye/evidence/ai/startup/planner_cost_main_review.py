"""Main independent graph/cost review; takes explicit product and output paths."""
import argparse, hashlib, importlib.util, json, math, random, shutil, subprocess, sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--product',required=True);p.add_argument('--output',required=True);a=p.parse_args()
root=Path(a.product).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
owned=['ai_pc/planning/candidate_graph.py','tests/ai/planning/test_candidate_graph.py','evidence/ai/startup/planner_cost.json','evidence/ai/startup/planner_cost.log']
hashes={x:hashlib.sha256((root/x).read_bytes()).hexdigest() for x in owned}
snapshot=out/'planner-cost-before-main-review';snapshot.mkdir(exist_ok=False)
for name in owned:
    dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((root/name).read_bytes())
spec=importlib.util.spec_from_file_location('reviewed_candidate_graph',root/owned[0]);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
def formula(values):
    q=[Fraction(v) for v in values]
    return q[0]+q[1]/2+4*q[2]+q[3]/2+q[4]
def enumerate_paths(nodes,edges,start):
    # Enumerate all simple paths. No production weighted_total or search machinery.
    best={}
    def visit(node,seen,cost,ids,chain):
        key=(cost,len(ids),ids)
        if node not in best or key<best[node][0]:best[node]=(key,chain)
        for eid,src,dst,values in edges:
            if src==node and dst not in seen:
                visit(dst,seen|{dst},cost+formula(values),ids+(eid,),chain+(dst,))
    visit(start,{start},Fraction(0),(),(start,))
    return best
seed=60152026;rng=random.Random(seed);digest=hashlib.sha256();queries=budget_queries=permutation_queries=found=unreachable=0
for case in range(240):
    n=2+case%6;nodes=[f'n{i}' for i in range(n)];edges=[]
    for src in nodes:
        for dst in nodes:
            if rng.random()<.26:
                for par in range(1+int(rng.random()<.12)):
                    values=[Fraction(rng.randrange(5),rng.randrange(1,9)) for _ in range(5)]
                    if case%5==0:values=[0]*5
                    elif case%7==0:values[rng.randrange(5)]=rng.choice([.1,.3,math.nextafter(0.0,1.0),1e308])
                    edges.append((f'e{rng.randrange(1000000):06}_{len(edges)}',src,dst,values))
    digest.update(json.dumps({'case':case,'nodes':nodes,'edges':edges},default=str,sort_keys=True,separators=(',',':')).encode())
    graph=m.CandidateGraph(nodes,[m.Edge(e,s,t,m.NormalizedCost(*v)) for e,s,t,v in edges],source_domain='software_fixture')
    pn=nodes[:];pe=graph.edges[:];pe=list(pe);rng.shuffle(pn);rng.shuffle(pe)
    perm=m.CandidateGraph(pn,pe,source_domain='software_fixture')
    for start in nodes:
        ref=enumerate_paths(nodes,edges,start)
        order=sorted(ref,key=lambda node:(ref[node][0],node))
        for goal in nodes:
            want=ref.get(goal);queries+=1
            got=graph.search(start,goal,64)
            if want:
                found+=1;key,chain=want
                assert (got.status,got.cost,got.edge_ids,got.node_ids)==('found',key[0],key[2],chain),(case,start,goal)
                rank=order.index(goal);assert got.expansion_count==rank
            else:
                unreachable+=1;assert (got.status,got.cost,got.edge_ids,got.node_ids,got.expansion_count)==('unreachable',None,(),(),len(ref))
            for budget in range(n+2):
                b=graph.search(start,goal,budget);budget_queries+=1
                needed=order.index(goal) if want else len(ref)
                if budget>=needed:
                    assert b==got,(case,start,goal,budget)
                else:
                    assert (b.status,b.cost,b.edge_ids,b.node_ids,b.expansion_count)==('budget_exhausted',None,(),(),budget),(case,start,goal,budget)
                assert perm.search(start,goal,budget)==b;permutation_queries+=1
    # Graph ingress tuple copies survive mutable caller-list edits.
    pn[:]=['replaced'];pe.clear();assert perm.node_count==n and perm.edge_count==len(edges)

# Bounds with a 64-node chain and 512 edges, including zero-cost self loops.
nodes=[f'q{i:02}' for i in range(64)];zero=m.NormalizedCost(0,0,0,0,0)
edges=[m.Edge(f'a{i:02}',nodes[i],nodes[i+1],zero) for i in range(63)]
edges += [m.Edge(f'loop{i:03}',nodes[i%64],nodes[i%64],zero) for i in range(449)]
g=m.CandidateGraph(nodes,edges,source_domain='software_fixture')
for budget in range(65):
    b=g.search(nodes[0],nodes[-1],budget)
    assert b.status==('found' if budget>=63 else 'budget_exhausted')
    assert b.expansion_count==min(budget,63)
    assert b.edge_ids==(tuple(f'a{i:02}' for i in range(63)) if budget>=63 else ())
invalid=0
def rejects(fn):
    global invalid
    try:fn()
    except m.CandidateGraphError:invalid+=1
    else:raise AssertionError('malformed input accepted')
for bad in [True,False,float('nan'),float('inf'),-1,Fraction(-1,7),'1',None]:
    for i in range(5):
        vals=[0]*5;vals[i]=bad;rejects(lambda vals=vals:m.NormalizedCost(*vals))
rejects(lambda:m.CandidateGraph(nodes+['too_many'],[],source_domain='software_fixture'))
rejects(lambda:m.CandidateGraph(nodes,edges+[m.Edge('extra',nodes[0],nodes[1],zero)],source_domain='software_fixture'))
for domain in ['force_curve_v1','sim_em_v2','sensor_live','production',None,True]:
    rejects(lambda domain=domain:m.CandidateGraph(['a'],[],source_domain=domain))

commands=[]
def run(cmd,name):
    r=subprocess.run(cmd,capture_output=True,timeout=90)
    (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
    commands.append({'command':cmd,'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest(),'raw_prefix':name})
    assert r.returncode==0,r.stderr.decode(errors='replace')
    assert b'Ran 30 tests' in r.stderr and b'OK' in r.stderr
run([sys.executable,'-X','utf8','-B',str(root/owned[1])],'planner-cost-main-unit')
portable=out/'planner-cost-portable-checkout';portable.mkdir(exist_ok=False)
for name in owned[:2]:
    target=portable/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((root/name).read_bytes())
run([sys.executable,'-X','utf8','-B',str(portable/owned[1])],'planner-cost-main-portable')
assert hashes=={x:hashlib.sha256((root/x).read_bytes()).hexdigest() for x in owned}
result={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'contract_id':'DEEPEYE-HUMAN-LOCK-20261014/revision1','requirements_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804','design_commit':'1011259415a0916054eb580687612580bc1e5f09','job_id':'child-08030d9f6a3545c7975ff3201f5eeb70','at_utc':datetime.now(timezone.utc).isoformat(),'unit_tests':30,'portable_tests':30,'independent_graphs':240,'independent_seed':seed,'independent_input_sha256':digest.hexdigest(),'ordered_pairs':queries,'found':found,'unreachable':unreachable,'budget_queries':budget_queries,'permuted_budget_queries':permutation_queries,'max_size_budget_cases':65,'main_invalid_cases':invalid,'commands':commands,'python_version':sys.version,'source_sha256':hashes,'product_worktree_HEAD':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip(),'child_evidence_HEAD_note':'Child readback git_head ab527e20 is the controller/root checkout HEAD, not the product worktree/source commit. Product files were untracked during tests; exact reviewed file hashes above bind this review. New source commit is recorded by the subsequent handoff manifest.','reasoning':'Every nonnegative edge extension strictly increases (cost,hops,sequence); equal-prefix labels preserve ordering under a common suffix. Zero-cost cycles increase hops and cannot improve the optimum. Main oracle enumerates every simple path independently and derives expansion rank from complete per-node optimum labels, rather than reproducing heap code. Expansion count excludes goal because its outgoing edges are never relaxed.','acceptance':'passed_software_fixture_math_foundation_only','G04':'not_run','C04':'not_run','limits':['No production normalization or calibrated risk','No 3D pose primitives, full-volume collision, braking tail or motion authority','No runtime/perception/planning latency measurement','All product and hardware/system cards remain not_run'],'provider':'deepseek','model':'deepseek-flash','reasoning_effort':'max'}
(out/'planner-cost-main-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))

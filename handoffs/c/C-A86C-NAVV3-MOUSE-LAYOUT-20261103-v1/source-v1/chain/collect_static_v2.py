"""C55 evidence only: bytes, AST literals and hashes; never import product."""
import ast, hashlib, json
from pathlib import Path

D=Path(__file__).resolve().parent
W=D.parent
S=W/'main/A-e470-source'
P='competition/deepeye/'
def digest(b): return hashlib.sha256(b).hexdigest()
def save(name,obj):
    (D/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(src.read_bytes())
idx=json.loads((W/'main/A-e470-verified-inputs.json').read_bytes())
by={x['path']:x for x in idx['files']}
names='''simulation/authority/navigation_session_profile.py
simulation/authority/demo30h_ai_em3_profile_v2/__init__.py
simulation/authority/demo30h_ai_em3_profile_v2/verifier.py
simulation/authority/demo30h_ai_em3_profile_v2/projection.py
ai_pc/demo30h_owned_em3_package_v2/c37_entry.py
ai_pc/demo30h_owned_em3_package_v2/c37_package.py
ai_pc/demo30h_owned_em3_package_v2/em3_core.py
ai_pc/demo30h_owned_em3_package_v2/package-manifest.json
simulation/authority/g05_csr_projection_v1.py
simulation/authority/g05_csr_channels_v1.py
simulation/authority/owned_invocation_v1/adapter.py
simulation/authority/owned_invocation_v1/mechanics.py
integration/completion_interval.py
simulation/authority/actor_composition.py
simulation/authority/pc_direct_runtime.py
simulation/authority/motion_executor.py
simulation/authority/motion/demo_motion_profile.py
simulation/authority/source_projection_v1/source_poll.py
simulation/authority/source_projection_v1/provider.py
tools/diagnostic/causal_pl_exchange.py
tools/diagnostic/original_source_trace_scan_a.py
tools/run_causal_functional_chain.py
simulation/authority/root_source_book.py
simulation/authority/_actor_source_custody.py
simulation/authority/original_world_actor_link.py
simulation/authority/_world_loop.py
simulation/sensors/forward_profile.py
tests/integration/test_navigation_fresh_action_392.py
tests/integration/test_navigation_amendment_392.py
tests/integration/test_navigation_session_392.py'''.splitlines()
pins=[]
for n in names:
    path=P+n; raw=(S/path).read_bytes(); row=by[path]
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert (len(raw),digest(raw),blob)==(row['bytes'],row['sha256'],row['git_blob']),path
    copy(S/path,D/'source'/path)
    pins.append(dict(path=path,bytes=len(raw),sha256=digest(raw),git_blob=blob))
save('source-pins.json',dict(commit=idx['source_commit'],tree_sha=idx['tree_sha'],method='exact byte SHA256 and Git blob SHA1 against main verified immutable tree; no source execution',files=pins))
for n in ['nav-chain-assignment-v1.json','A86C.stdout.json','ui-availability-v1.json','owner-ack-receipt.json']:
    copy(W/'main'/n,D/'inputs'/n)
assert digest((D/'inputs/nav-chain-assignment-v1.json').read_bytes())=='96f80e0f45aab707de7dd75815db0da489dedc101a05ba5f709a48f8930d69f6'
req=json.loads((W/'main/prior-seal-contract-and-stops.json').read_bytes())['requirements']
reqraw=json.dumps(req,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
assert digest(reqraw)=='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
save('requirements.json',req)
save('contract-verification.json',dict(contract_id='DEEPEYE-HUMAN-LOCK-20261014',revision=1,source='f5989cd5defce561f9ba98e6b18fc2682945f0a2',fixed_design='1011259415a0916054eb580687612580bc1e5f09',requirements_sha256=digest(reqraw),count=len(req),status='identity_verified_only_no_acceptance'))
tree=ast.parse((S/(P+'simulation/authority/navigation_session_profile.py')).read_text(encoding='utf-8'))
vals={}
def lit(node):
    if isinstance(node,ast.Name): return vals[node.id]
    if isinstance(node,ast.Tuple): return tuple(lit(x) for x in node.elts)
    return ast.literal_eval(node)
for node in tree.body:
    if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('_SOURCE_PINS','_VALUES'):
        vals[node.targets[0].id]=lit(node.value)
pre=json.dumps(('DEEPEYE-TYPED-NAVIGATION-PROFILE-V3',*vals['_VALUES']),separators=(',',':')).encode('ascii')
navsha=digest(pre)
assert navsha=='5a3679f80be3668aaa1765ecdb157776f38c661ce1bb9d40d5dac8b447967d17'
for path,sha in vals['_SOURCE_PINS']:
    assert digest((S/(P+"simulation/authority/"+path+".py")).read_bytes())==sha,path
pkg=S/(P+'ai_pc/demo30h_owned_em3_package_v2')
manraw=(pkg/'package-manifest.json').read_bytes(); man=json.loads(manraw)
for n,sha in man['files'].items(): assert digest((pkg/n).read_bytes())==sha
save('logical-and-package-pins.json',dict(navigation_profile_sha256=navsha,navigation_preimage_utf8=pre.decode(),source_dependencies=vals['_SOURCE_PINS'],prospective_io=42+76*16+2*128+15*16,manifest_sha256=digest(manraw),package_files=man['files'],AI_logical_profile_id='DEEPEYE-EM3-NAV-FAST-V1',AI_logical_declared_sha256='11ff1d2895c46ab7135e18835e06afa5b4251665341f215eda1ede6e4969e861',AI_logical_hash_derivation='declaration repeated in four fixed modules; no canonical preimage definition found in these source modules; not confused with file or package digest',product_imported=False))
print(json.dumps(dict(status='STATIC_BYTES_AST_HASH_OK',source_files=len(pins),contract=digest(reqraw),nav=navsha,manifest=digest(manraw),product_ran=False)))

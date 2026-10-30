"""C42 A108 mechanical host-proof assembly. No C36/core/dispatch authority."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import threading

ADAPTER='c42_a108_proof_assembler_v1'
SOURCE='51c48e106c76f3e4d18000da61be17dd8a4b6623'
SCHEMA_SHA='ab1b432e9f337523fd75057fec4647f5eda2569de308e7c777507e05907bdd70'
_MAX=1048576
_MAX_SOURCE_BYTES=16*1048576
_KEY=object()
_PREFIX='competition.deepeye.simulation.authority.'
_PINS={'root_source_book':'f80a6dbb4c264253759ce910c69ef75ae8a774f8d3b8ae22dee9121839e4e2cb','_actor_source_custody':'0cb3438533a7fec25ac4dc7c0072de7c6de7e3acff5a84ecaf7d1636614ed671','original_world_actor_link':'38e731c392f41b0b9d3b1852bea49c081f8398501cab996544ae36adbac108fb','_world_loop':'1d6939f5019a12f7746d5a9872389da5d2c1bd693a9505043d33d68025adb306'}
_raw_schema=Path(__file__).with_name('request.schema.json').read_bytes()
if hashlib.sha256(_raw_schema).hexdigest()!=SCHEMA_SHA:raise ImportError('fixed schema mismatch')
_SCHEMA=json.loads(_raw_schema)
class Rejected(ValueError):pass
class Unavailable(RuntimeError):pass
def need(ok,reason):
 if not ok:raise Rejected(reason)
def raw(x):
 try:return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')
 except (TypeError,ValueError,OverflowError,RecursionError):raise Rejected('NON_JSON_DATA') from None
def clone(x,limit=_MAX):
 b=raw(x);need(len(b)<=limit,'BUDGET_EXCEEDED');return json.loads(b)
def same(a,b):
 if a is not None and b is not None:need(a==b,'SUPPLIED_CONTRADICTION')
def merge(actual,extra):
 out=copy.deepcopy(extra or {})
 for k,v in actual.items():
  if isinstance(v,dict)and isinstance(out.get(k),dict):out[k]=merge(v,out[k]);continue
  if k in out:same(v,out[k])
  out[k]=v
 return out
def definition(n):return _SCHEMA['$defs'][n]
def nullable(s):
 if '$ref' in s:return nullable(definition(s['$ref'].split('/')[-1]))
 return s.get('type')=='null' or any(nullable(v) for v in s.get('anyOf',s.get('oneOf',[])))
def project(value,spec,path,missing,dropped):
 if '$ref' in spec:return project(value,definition(spec['$ref'].split('/')[-1]),path,missing,dropped)
 choices=spec.get('anyOf',spec.get('oneOf'))
 if choices:
  if value is None and any(nullable(v) for v in choices):return None
  choices=[v for v in choices if v.get('type')!='null']
  if len(choices)==1:return project(value,choices[0],path,missing,dropped)
  selected=[]
  for choice in choices:
   s=definition(choice['$ref'].split('/')[-1]) if '$ref' in choice else choice
   if isinstance(value,dict) and all(k not in value or (value[k]==v['const'] if 'const' in v else value[k] in v['enum']) for k,v in s.get('properties',{}).items() if 'const' in v or 'enum' in v):selected.append(choice)
  need(len(selected)==1,'AMBIGUOUS_SOURCE_VARIANT');return project(value,selected[0],path,missing,dropped)
 if value is None and spec.get('type')!='null':missing.add(path);return None
 if 'const' in spec:need(type(value)is type(spec['const'])and value==spec['const'],'SOURCE_CONSTANT_MISMATCH')
 if 'enum' in spec:need(value in spec['enum'],'SOURCE_ENUM_MISMATCH')
 typ=spec.get('type')
 if typ is None:return value
 expected={'object':dict,'array':list,'integer':int,'string':str,'boolean':bool,'null':type(None)}
 if typ=='number':need((type(value)is int and abs(value)<=1.7976931348623157e308)or(type(value)is float and math.isfinite(value)),'NUMBER_RANGE')
 else:need(type(value)is expected[typ],'SOURCE_SHAPE')
 if typ=='object':
  out={};props=spec['properties']
  for key in value:
   if key not in props:dropped.add(path+'.'+key)
  for key,s in props.items():
   if key not in value:
    if key in spec.get('required',[]):missing.add(path+'.'+key);out[key]=None
   else:out[key]=project(value[key],s,path+'.'+key,missing,dropped)
  return out
 if typ=='array':
  need(spec.get('minItems',0)<=len(value)<=spec.get('maxItems',2048),'BUDGET_EXCEEDED')
  return [project(v,spec['items'],path+'['+str(i)+']',missing,dropped)for i,v in enumerate(value)]
 if typ in ('integer','number'):
  need(spec.get('minimum',-math.inf)<=value<=spec.get('maximum',math.inf),'NUMBER_RANGE')
  if 'exclusiveMinimum'in spec:need(value>spec['exclusiveMinimum'],'NUMBER_RANGE')
 if typ=='string':
  import re
  need(spec.get('minLength',0)<=len(value)<=spec.get('maxLength',_MAX),'BUDGET_EXCEEDED')
  if 'pattern'in spec:need(re.fullmatch(spec['pattern'],value)is not None,'SOURCE_STRING')
 return value

def _exact_json_number(value):
 from fractions import Fraction
 if type(value)is int:return value
 if type(value)is float:return value if math.isfinite(value)else None
 if type(value)is Fraction:
  if value.denominator==1:return value.numerator
  try:converted=float(value)
  except OverflowError:return None
  return converted if math.isfinite(converted)and Fraction.from_float(converted)==value else None
 return None
def _pose(p):return None if p is None else dict(position_m=list(p.position_m),orientation_xyzw=list(p.orientation_xyzw))
def _root(r):return None if r is None else dict(root_revision=r.revision,pose_revision=r.pose_revision,revoke_generation=r.revoke_generation,pose=_pose(r.pose))
def _key(t):return tuple(t[k]for k in ('kind','before_root_revision','from_pose_revision','lower_observed_qpc_ns'))
def _collect_original_reads(book):
 # Ordered actual getter, then original evidence. Not an atomic snapshot.
 current=book.current_pose_interval();evidence=book.evidence();return current,evidence

def _capture_availability(request,missing):
 """Presence/link availability only, not C36 equality, time or quality validation."""
 root=request['root_receipt'];samples=request['actor_book']['samples'];records=root['captures']or[]
 if not root['source_admissions']:missing.add('request.root_receipt.source_admissions')
 observations=[(request['candidate'],'request.candidate')]+[(c,'request.history['+str(i)+']')for i,c in enumerate(request['history'])]
 def required(obj,names,path):
  if obj is not None:
   for name in names:
    if obj.get(name)is None:missing.add(path+'.'+name)
 def lookup(items,key,value,path):
  found=[(i,item)for i,item in enumerate(items)if item is not None and value is not None and item.get(key)==value]
  if len(found)!=1:missing.add(path);return None,None
  return found[0]
 for observation,path in observations:
  if observation is not None:
   identity=observation.get('observation_identity')or{}
   lookup(records,'capture_sha256',identity.get('capture_sha256'),path+'.observation_identity.capture_sha256')
 for i,record in enumerate(records):
  if record is None:continue
  path='request.root_receipt.captures['+str(i)+']'
  required(record,('adc_call','adc_root_revision','adc_pose','adc_book_source_sha256'),path)
  required(record['adc_pose'],('receipt_id','pose','pose_revision','pose_read','valid_span'),path+'.adc_pose')
  si,sample=lookup(samples,'source_sha256',record['adc_book_source_sha256'],path+'.adc_book_source_sha256')
  if sample is not None:
   sp='request.actor_book.samples['+str(si)+']';required(sample,('adc','numerical_pose_span','pose_reads'),sp)
   required(sample['pose_reads'],('adc',),sp+'.pose_reads')
  selected=[c for c,_ in observations if c is not None and (c.get('observation_identity')or{}).get('capture_sha256')==record['capture_sha256']]
  if not selected:
   missing.add(path+'.capture_sha256');continue
  # Any supplied selected observation requiring EM needs its original attachments.
  # Conflicting observations remain C36's job; never choose one by array order.
  if not any((c.get('source_time')or{}).get('em_tick_ms')is not None for c in selected):continue
  required(record,('em_pose','em_root_revision','em_book_source_sha256','em_origin_capture_sha256','original_em_call','original_em_scope_closed_qpc_ns'),path)
  required(record['em_pose'],('receipt_id','pose','pose_revision','pose_read','valid_span'),path+'.em_pose')
  ei,em_sample=lookup(samples,'source_sha256',record['em_book_source_sha256'],path+'.em_book_source_sha256')
  lookup(records,'capture_sha256',record['em_origin_capture_sha256'],path+'.em_origin_capture_sha256')
  if em_sample is not None:required(em_sample['pose_reads'],('em',),'request.actor_book.samples['+str(ei)+'].pose_reads')
  if sample is not None:
   required(sample,('held_em_association',),sp)
   held=sample['held_em_association']
   required(held,('original_em',),sp+'.held_em_association')
   if held is not None:required(held['original_em'],('pose_read','call','numerical_pose_span'),sp+'.held_em_association.original_em')

def assemble_snapshot(evidence,current,attachments,*,candidate,history,enabled=False):
 """Untrusted diagnostic data path; cannot create a live Producer or provenance."""
 need(type(enabled)is bool,'STRICT_BOOL');need(type(history)is list,'HISTORY_REQUIRED')
 evidence=clone(evidence,_MAX_SOURCE_BYTES);snapshot_sha=hashlib.sha256(raw(evidence)).hexdigest();current=clone(current);a=clone(attachments)
 missing=set();dropped=set();need(type(evidence)is dict and type(a)is dict,'SOURCE_SHAPE')
 samples=evidence.get('samples');need(type(samples)is list and len(samples)<=1001,'BUDGET_EXCEEDED')
 need(len(history)<=32,'BUDGET_EXCEEDED')
 for sample in samples:
  if type(sample.get('held_em_association'))is str:
   need(sample['held_em_association'].startswith('unavailable;'),'SOURCE_SHAPE');sample['held_em_association']=None
  if sample.get('tick_ms')is not None and sample['tick_ms']%50 and isinstance(sample.get('pose_reads'),dict):sample['pose_reads'].setdefault('em',None)
 book=merge(dict(source_commit=SOURCE,snapshot_sha256=snapshot_sha,current_read=current,claim='numerical_immutable_committed_root_only',native_interval_atomic=False),evidence)
 now=None if current is None else current.get('at_qpc_ns')
 if current is None:missing.add('original.current_pose_interval')
 else:
  need(type(current)is dict,'SOURCE_SHAPE');read=current.get('pose_read');span=current.get('valid_span')
  if read is None or span is None:missing.add('original.current_pose_interval.read_and_span')
  else:
   same(now,read.get('end_qpc_ns'));same(now,span.get('through_qpc_ns'));same(current.get('pose_revision'),span.get('pose_revision'))
   if read.get('begin_qpc_ns')is not None and read.get('end_qpc_ns')is not None:need(read['begin_qpc_ns']<=read['end_qpc_ns'],'SUPPLIED_CONTRADICTION')
   envelope=evidence.get('current_pose_interval')
   if envelope is not None:
    for k in ('root_revision','pose_revision','from_qpc_ns'):same(span.get(k),envelope.get(k))
    if envelope.get('through_qpc_ns')is not None and now is not None:need(envelope['through_qpc_ns']>=now,'SUPPLIED_CONTRADICTION')
 cur=None
 if current is not None:
  span=current.get('valid_span');extra=a.get('current')or{}
  cur=merge({k:current.get(k)for k in ('pose','pose_revision','at_qpc_ns','pose_read')},extra)
  same(cur.get('root_revision'),None if span is None else span.get('root_revision'));cur['root_revision']=None if span is None else span.get('root_revision')
  actual=None if span is None else {k:span.get(k)for k in ('from_qpc_ns','through_qpc_ns')}
  cur['valid_span']=None if actual is None else merge(actual,extra.get('valid_span'))
 registry=a.get('actor_registry')
 if registry is not None:same(registry.get('as_of_qpc_ns'),now)
 if registry is not None and registry.get('associations')is not None and evidence.get('actor_pose_intervals')is not None:
  original=evidence['actor_pose_intervals']['transitions'];keys=[_key(x['transition_key'])for x in registry['associations']if x is not None]
  need(len(keys)==len(set(keys)),'DUPLICATE_ASSOCIATION')
  if set(keys)!={_key(t)for t in original}:missing.add('original.transition_attachments')
 root=dict(kind='c36_interval_root_association_v1',evidence_scope='root_supplied_diagnostic',config=a.get('config'),source_admissions=a.get('source_admissions'),captures=a.get('captures'),current_pose=cur,actor_registry=registry)
 request=dict(schema_version=2,abi_id='moving_interval_book_bridge_v2',diagnostic_only=True,evidence_scope='root_supplied_diagnostic',enabled=enabled,now_qpc_ns=now,candidate=candidate,history=history,root_receipt=root,actor_book=book)
 partial=project(request,definition('Request'),'request',missing,dropped)
 _capture_availability(partial,missing)
 # Nullable means representable, not proof that a missing actual record exists.
 # C36 _wire requires both original config bindings and both original wires.
 # Keep this field-specific: BOOT command absence and no-EM nulls are legal.
 projected_root=partial['root_receipt']
 config=projected_root['config']
 if config is not None:
  for name in ('pose_book_id','owner_binding_id'):
   if config.get(name)is None:missing.add('request.root_receipt.config.'+name)
 for i,record in enumerate(projected_root['captures']or[]):
  path='request.root_receipt.captures['+str(i)+']'
  if record is None:missing.add(path);continue
  for name in ('request_raw','capture_raw'):
   if record.get(name)is None:missing.add(path+'.'+name)
 for key in ('config','source_admissions','captures','actor_registry'):
  if a.get(key)is None:missing.add('attachments.'+key)
 if candidate is None:missing.add('attachments.candidate')
 if a.get('current')is None:missing.add('attachments.current')
 for path,value in [('current.receipt_id',None if cur is None else cur.get('receipt_id')),('current.valid_span.receipt_id',None if cur is None or cur.get('valid_span')is None else cur['valid_span'].get('receipt_id'))]:
  if value is None:missing.add('attachments.'+path)
 def receipt_missing(obj,path,kind=None):
  if isinstance(obj,dict):
   if 'transition_key'in obj:kind=obj['transition_key'].get('kind')
   for k,v in obj.items():
    if v is None and not(k=='command_receipt_id'and kind=='BOOT')and (k=='receipt_id' or k.endswith('_receipt_id') or k in ('effect_witness_id','old_pose_span','current_read','current_pose_interval','numerical_pose_span')):missing.add(path+'.'+k)
    receipt_missing(v,path+'.'+k,kind)
  elif isinstance(obj,list):
   for i,v in enumerate(obj):receipt_missing(v,path+'['+str(i)+']',kind)
 receipt_missing(partial,'request')
 need(len(raw(partial))<=_MAX,'BUDGET_EXCEEDED')
 return dict(adapter=ADAPTER,status='INPUT_UNAVAILABLE'if missing else'ASSEMBLED_UNVALIDATED',proof=None if missing else partial,partial=partial,missing_paths=sorted(missing),dropped_paths=sorted(dropped),source_authenticated=False,dispatch_authorized=False,core_ran=False)

class Producer:
 """Owner-thread attachment collector. Trusted-process identity checks, not an OS boundary."""
 def __init__(self,key,owner,link,book,modules):
  need(key is _KEY,'ORIGINAL_FACTORY_REQUIRED');self._owner=owner;self._link=link;self._book=book;self._modules=modules;self._thread=threading.get_ident();self._failed=False
  self._ids=[];self._config=None;self._registry=[];self._admissions=[];self._captures=[];self._actions=[];self._readings=[]
 def _check(self):
  if self._failed:raise Unavailable('PRODUCER_LATCHED')
  need(threading.get_ident()==self._thread,'OWNER_THREAD_REQUIRED')
  o,l,b=self._owner,self._link,self._book
  need(l.owner is o and l.book is b and b._owner is o and b._actor_custody.link is l and b._actor_custody.book is b and l.source._source_book is b,'ORIGINAL_BINDING_CHANGED')
  l._registered();b._actor_custody._context()
 def bind_id(self,original,opaque_id):
  self._check();need(original is not None and type(opaque_id)is str and 0<len(opaque_id)<=192 and opaque_id.isascii(),'OPAQUE_ID_REQUIRED')
  for ref,label in self._ids:
   if ref is original:need(label==opaque_id,'ID_REBIND');return label
   need(label!=opaque_id,'ID_COLLISION')
  need(len(self._ids)<8192,'BUDGET_EXCEEDED');self._ids.append((original,opaque_id));return opaque_id
 def _id(self,ref):return next((v for r,v in self._ids if r is ref),None)if ref is not None else None
 def attach_config(self,original,fields):
  self._check();need(original is not None and self._config is None,'CONFIG_REBIND');self._config=(original,clone(fields))
 def attach_registry(self,original,context,generation,*,as_of_qpc_ns):
  self._check();need(original is not None and not any(r[0]is original for r in self._registry),'REGISTRY_REBIND');need(len(self._registry)<32,'BUDGET_EXCEEDED');self._registry.append((original,clone(context),generation,as_of_qpc_ns))
 def attach_admission(self,original,fields):
  self._check();need(original is not None and not any(r is original for r,_ in self._admissions),'DUPLICATE_ATTACHMENT');need(len(self._admissions)<1001,'BUDGET_EXCEEDED');self._admissions.append((original,clone(fields)))
 def attach_capture(self,original,sample,*,candidate,fields):
  self._check();need(original is not None and any(sample is s for s in self._book._samples),'ORIGINAL_SAMPLE_REQUIRED');need(not any(r is original for r,*_ in self._captures),'DUPLICATE_ATTACHMENT');need(len(self._captures)<32,'BUDGET_EXCEEDED');self._captures.append((original,sample,clone(candidate),clone(fields)))
 def attach_transition(self,transition,*,successor_root,slot=None,fields):
  self._check();need(any(transition is t for t in self._book._actor_custody.transitions),'ORIGINAL_TRANSITION_REQUIRED');need(not any(t is transition for t,*_ in self._actions),'DUPLICATE_ATTACHMENT');need(len(self._actions)<32,'BUDGET_EXCEEDED')
  if successor_root is not None:need(transition.closed and successor_root is self._book._root and successor_root is self._link.executor._root,'RETAIN_SUCCESSOR_AT_ORIGINAL_COMPLETION')
  if slot is not None:need(any(slot is x for x in self._owner._commits)and slot.book_transition is transition and slot.original_witness.link is self._link,'ORIGINAL_SLOT_REQUIRED')
  self._actions.append((transition,successor_root,slot,clone(fields)))
 def _capture(self,entry):
  original,sample,candidate,fields=entry;actual={'adc_book_source_sha256':sample.get('source_sha256'),'adc_call':None,'adc_root_revision':None}
  adc=sample.get('adc');read=sample.get('pose_reads',{}).get('adc');span=sample.get('numerical_pose_span')
  if adc is not None:actual['adc_call']={k:adc.get(k)for k in ('begin_qpc_ns','end_qpc_ns')}
  if read is not None:actual['adc_root_revision']=read.get('root_revision')
  for key in ('request_raw','capture_raw'):
   if fields.get(key)is not None and type(fields[key])is not str:raise Rejected('ORIGINAL_UTF8_WIRE_REQUIRED')
  if fields.get('capture_raw')is not None:actual['capture_sha256']=hashlib.sha256(fields['capture_raw'].encode('utf8')).hexdigest()
  if read is not None:
   pose={k:read.get(k)for k in ('pose','pose_revision')};pose['pose_read']={k:read.get(k)for k in ('begin_qpc_ns','end_qpc_ns')};pose['nominal_source_qpc_ns']=sample.get('nominal_qpc_ns')
   pose['valid_span']=None if span is None else merge({k:span.get(k)for k in ('from_qpc_ns','through_qpc_ns')},(fields.get('adc_pose')or{}).get('valid_span'))
   actual['adc_pose']=merge(pose,fields.get('adc_pose'))
  held=sample.get('held_em_association');em=held.get('original_em')if isinstance(held,dict)else None
  if em is not None:
   actual['em_root_revision']=em.get('root_revision');actual['original_em_call']=em.get('call');actual['original_em_scope_closed_qpc_ns']=em.get('scope_closed_qpc_ns')
   er=em.get('pose_read');es=em.get('numerical_pose_span')
   if er is not None:
    ep={k:er.get(k)for k in ('pose','pose_revision')};ep['pose_read']={k:er.get(k)for k in ('begin_qpc_ns','end_qpc_ns')};ep['nominal_source_qpc_ns']=em.get('nominal_qpc_ns');ep['valid_span']=None if es is None else merge({k:es.get(k)for k in ('from_qpc_ns','through_qpc_ns')},(fields.get('em_pose')or{}).get('valid_span'));actual['em_pose']=merge(ep,fields.get('em_pose'))
  return merge(actual,fields)
 def _action(self,entry):
  transition,after,slot,fields=entry;t=transition.record;l=self._link
  if after is None and slot is not None:after=getattr(slot,'post_root',None)
  actual=dict(receipt_id=self._id(transition),transition_key={k:t[k]for k in ('kind','before_root_revision','from_pose_revision','lower_observed_qpc_ns')},from_root=_root(transition.before),to_root=_root(after))
  custody=fields.get('custody')
  if custody is not None:actual['custody']=merge(dict(pose_book_id=self._id(self._book),owner_binding_id=self._id(l.binding),actor_composition_id=self._id(l.composition),original_world_actor_link_id=self._id(l),before_root_revision=transition.before.revision,after_root_revision=None if after is None else after.revision,revoke_generation_before=transition.before.revoke_generation,revoke_generation_after=None if after is None else after.revoke_generation),custody)
  if slot is not None:
   witness=slot.original_witness;receipt=slot.receipt;actual['candidate_root']=_root(witness.candidate_root);actual['nonspatial_receipt']=None;actual['action_id']=self._id(slot)
   if receipt is None:actual['step_receipt']=merge(dict(returned_receipt_observed=False,returned_receipt_id=None,effect_observation=slot.effect_observation),fields.get('step_receipt'))
   if receipt is not None:actual['step_receipt']=merge(dict(receipt_id=self._id(slot),candidate_receipt_id=self._id(witness.allocated_receipt),returned_receipt_id=self._id(receipt),effect_witness_id=self._id(witness),effect_observation=slot.effect_observation,returned_receipt_observed=True,model_start_qpc_ns=receipt.start_ns,model_executed_until_qpc_ns=receipt.end_ns,command_seq=receipt.command_seq,command_sha256=hashlib.sha256(slot.command_raw).hexdigest(),pose_revision=receipt.pose_revision),fields.get('step_receipt'))
   pub=slot.publication
   if pub is None:actual['publication']=None
   if pub is not None:
    self._modules['original_world_actor_link']._require_admitted_readback(pub,slot)
    policy=getattr(getattr(getattr(l,'binding',None),'world_values',None),'budget_derivation',None);bounds=getattr(slot,'endpoint_bounds',(None,None))
    actual['publication']=merge(dict(receipt_id=self._id(pub),operation_id=pub.operation_id,kind=pub.kind,state=pub.state,numerical_receipt_digest=slot.receipt_digest,freeze_id=l.epoch.identity['freeze_id'],pose_revision=pub.revision,getter_readback_qpc_ns=pub.admitted_readback_ns,getter_receipt_id=self._id(pub.admitted_readback),getter_policy_receipt_id=self._id(policy),local_error_bound_m=_exact_json_number(bounds[0]),global_error_bound_m=_exact_json_number(bounds[1]),frozen_getter_cap_m=_exact_json_number(getattr(policy,'getter_endpoint_cap_m',None))),fields.get('publication'))
  if t['kind']!='STEP':actual.update(action_id=None,observation_capture_sha256=None,candidate_root=None,step_receipt=None,publication=None)
  if t['kind']!='STEP' and after is not None:
   command=after.command
   actual['nonspatial_receipt']=merge(dict(receipt_id=self._id(transition),boot_receipt_id=self._id(after.boot),command_receipt_id=self._id(command),command_seq=None if command is None else command.sequence,command_sha256=None if command is None else hashlib.sha256(command.raw).hexdigest(),duplicate_command=after is transition.before),fields.get('nonspatial_receipt'))
  return merge(actual,fields)
 def read_current(self):
  self._check();need(len(self._readings)<32,'BUDGET_EXCEEDED')
  try:
   current,evidence=_collect_original_reads(self._book);self._check();self._readings.append((current,evidence,raw(current),raw(evidence),current.get('valid_span')));return current
  except Exception:self._failed=True;raise
 def export(self,*,current_read,registry_ref,candidate_ref,history_refs,enabled=False):
  self._check();need(type(enabled)is bool and type(history_refs)is tuple,'EXPLICIT_SELECTION_REQUIRED');need(len(history_refs)<=32,'BUDGET_EXCEEDED')
  selected=[]
  for ref in history_refs+(candidate_ref,):
   matches=[x for x in self._captures if x[0]is ref];need(len(matches)<=1,'DUPLICATE_ATTACHMENT');selected.append(matches[0]if matches else None)
  try:
   readings=[x for x in self._readings if x[0]is current_read];need(len(readings)==1,'ORIGINAL_CURRENT_READ_REQUIRED');current,evidence,saved_current,saved_evidence,saved_span=readings[0];need(raw(current)==saved_current and raw(evidence)==saved_evidence and current.get('valid_span')is saved_span,'ORIGINAL_CURRENT_READ_REPLACED')
   registries=[r for r in self._registry if r[0]is registry_ref];need(len(registries)<=1,'DUPLICATE_ATTACHMENT');registry=registries[0]if registries else None
   config=None if self._config is None else merge(dict(receipt_id=self._id(self._config[0]),pose_book_id=self._id(self._book),owner_binding_id=self._id(self._link.binding)),self._config[1])
   reg=None if registry is None else dict(receipt_id=self._id(registry[0]),context=registry[1],generation=registry[2],as_of_qpc_ns=registry[3],associations=[self._action(x)for x in self._actions])
   cur=None if registry is None else dict(receipt_id=self._id(current),context=registry[1],generation=registry[2],valid_span=dict(receipt_id=self._id(current.get('valid_span'))))
   attachments=dict(config=config,source_admissions=[x[1]for x in self._admissions]if self._admissions else None,captures=[self._capture(x)for x in self._captures]if self._captures else None,actor_registry=reg,current=cur)
   candidate=None if selected[-1]is None else selected[-1][2];history=[None if x is None else x[2]for x in selected[:-1]]
   result=assemble_snapshot(evidence,current,attachments,candidate=candidate,history=history,enabled=enabled)
   result['live_owner_binding_checked']=True;result['ordered_nonatomic_getter_then_evidence']=True;return result
  except Exception:
   self._failed=True;raise

def attach_original(owner,link,book):
 """Call only inside A's original already-loaded owner process; never starts it."""
 modules={}
 for name,pin in _PINS.items():
  module=sys.modules.get(_PREFIX+name)
  if module is None:raise Unavailable('ORIGINAL_MODULE_NOT_LOADED')
  need(hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()==pin,'ORIGINAL_SOURCE_PIN_MISMATCH');modules[name]=module
 need(type(owner)is modules['_world_loop']._RootWorldOwner and type(link)is modules['original_world_actor_link']._OriginalWorldActorLink and type(book)is modules['root_source_book'].RootSourceBook,'EXACT_ORIGINAL_TYPES_REQUIRED')
 need(owner._test is False and type(book._actor_custody)is modules['_actor_source_custody']._ActorSourceCustody,'PRODUCTION_OWNER_REQUIRED')
 producer=Producer(_KEY,owner,link,book,modules);producer._check();return producer

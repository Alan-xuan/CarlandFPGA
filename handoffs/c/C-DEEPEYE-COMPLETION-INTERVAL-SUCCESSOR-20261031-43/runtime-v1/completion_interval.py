"""Explicit opt-in host model-candidate interval successor; no grant or I/O.

Default forwards the exact v1 call. Opt-in reuses original schema/types and all
original producer/context/observation/target/consumer gates without a scalar.
The legacy object and supplied bounds are process-call contracts, not proof.
"""
import copy
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType

BASIS='host_dispatch_to_complete_result_observed_v1'
UINT63=(1<<63)-1
MAX_CANDIDATE_AGE_NS=100_000_000
BASE_SCHEMA_CANONICAL_SHA256='28a0d7721da1287c41665f8757346c4e3b81a15dbb651d3ab4bcf52d3b5e9b2f'

class Rejected(ValueError):pass
class Unavailable(ValueError):pass

def _need(condition,reason):
    if not condition:raise Rejected(reason)

def _uint(value,label):
    _need(type(value) is int and 0<=value<=UINT63,label+': uint63 required')
    return value

def _freeze(value):
    if type(value) is dict:return MappingProxyType({k:_freeze(v) for k,v in value.items()})
    if type(value) is list:return tuple(_freeze(v) for v in value)
    return value

def _schema(legacy):
    original=legacy._sealed_schema()
    raw=json.dumps(original,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    _need(hashlib.sha256(raw).hexdigest()==BASE_SCHEMA_CANONICAL_SHA256,'original schema pin mismatch')
    schema=copy.deepcopy(original)
    schema['$id']='urn:carlandfpga:deepeye:host-model-candidate-completion-interval:v2'
    schema['title']='Explicit opt-in model candidate completion interval revision 2'
    schema['oneOf']=[{'$ref':'#/$defs/model_candidate_interval'}]
    candidate=copy.deepcopy(schema['$defs']['model_candidate'])
    candidate['properties']['schema_version']={'const':2}
    del candidate['properties']['completed_monotonic_ns']
    candidate['required'].remove('completed_monotonic_ns')
    candidate['properties']['completion_observed_interval_ns']={'$ref':'#/$defs/interval_ns'}
    candidate['properties']['basis']={'const':BASIS}
    candidate['required']+=['completion_observed_interval_ns','basis']
    schema['$defs']['model_candidate_interval']=candidate
    return schema

@dataclass(frozen=True,slots=True)
class IntervalCandidate:
    kind: str
    producer: str
    consumer: object
    authority_only: bool
    document: object
    valid_until_ns: int
    validated_at_ns: int
    bounds: object

@dataclass(frozen=True,slots=True)
class FiniteActionCandidate:
    """Exact existing target/observation plus a conservative deadline; no command."""
    candidate: IntervalCandidate
    host_issue_ns: int
    deadline_ns: object
    authority: str='none'


def _validity(bounds,lower,now):
    _need(type(bounds) is dict and set(bounds)=={'max_age_ns','source_deadline_ns','dispatch_deadline_ns','previous_deadline_ns'},'exact four explicit bounds required')
    # No unspecified previous sentinel: first candidate must explicitly pass None.
    age=_uint(bounds['max_age_ns'],'max_age_ns')
    _need(0<age<=MAX_CANDIDATE_AGE_NS,'max_age_ns must be 1..100000000')
    source=bounds['source_deadline_ns'];dispatch=bounds['dispatch_deadline_ns'];previous=bounds['previous_deadline_ns']
    if source is not None:_uint(source,'source_deadline_ns')
    if dispatch is not None:_uint(dispatch,'dispatch_deadline_ns')
    if previous is not None:_uint(previous,'previous_deadline_ns')
    _need(lower<=UINT63-age,'lower plus max_age_ns overflows uint63')
    if source is None or dispatch is None:raise Unavailable('original source and dispatch bounds required')
    caps=[lower+age,source,dispatch]
    if previous is not None:caps.append(previous)
    deadline=min(caps)
    if deadline<=now:raise Unavailable('candidate original lower/source/dispatch/previous deadline expired')
    return deadline


def validate_message(raw_bytes,*,legacy,producer,context,now_ns,consumer=None,
                     enable_interval=False,bounds=None):
    """v1 default; explicit v2 interval and original finite bounds required.

    No call fabricates completed_monotonic_ns. Returns original v1 result when
    disabled, IntervalCandidate when enabled. No registration or new authority.
    """
    _need(type(enable_interval) is bool,'enable_interval must be bool')
    if not enable_interval:
        _need(bounds is None,'bounds require explicit interval opt-in')
        return legacy.validate_message(raw_bytes,producer=producer,context=context,now_ns=now_ns,consumer=consumer)
    schema=_schema(legacy)
    legacy._check_producer_argument(producer,schema)
    _uint(now_ns,'now_ns')
    _,context_validator=legacy._validators()
    legacy._check_context_argument(context,context_validator)
    document=legacy._parse_message(raw_bytes)
    error=next(legacy.StrictDraft202012Validator(schema).iter_errors(document),None)
    if error is not None:raise Rejected('interval schema reject: '+legacy._describe(error))
    kind=document['kind']
    _need(kind in schema['x-producers'][producer],'producer may not carry model_candidate')
    legacy._check_message_context(document,context)
    legacy._check_nested_contexts(document,context)
    legacy._check_intervals(document,kind,now_ns)
    # These are the original candidate's other two gates, without its scalar.
    legacy._check_target(document['target'],legacy._profile_name(context))
    legacy._require_observation(document)
    legacy._check_consumer_argument(consumer,False,schema)
    span=document['completion_observed_interval_ns']
    lower=_uint(span['lower_ns'],'lower_ns');upper=_uint(span['upper_ns'],'upper_ns')
    _need(lower<=upper<=now_ns,'ordered interval must end by now')
    if bounds is None:raise Unavailable('original completion bounds missing')
    deadline=_validity(bounds,lower,now_ns)
    return IntervalCandidate(kind,producer,consumer,False,_freeze(document),deadline,now_ns,_freeze(bounds))


def adapt_action_candidate(candidate,*,host_issue_ns,now_ns,previous_deadline_ns):
    """Produce a finite downstream candidate, never motion_request or grant.

    SET_TARGET duration must fit fully within retained caps; no shortening or
    renewal is implicit. STOP retains zero target and gets no positive lease.
    Original authority/PC_DIRECT still checks its live state and all source gates.
    """
    _need(isinstance(candidate,IntervalCandidate),'interval candidate required')
    issue=_uint(host_issue_ns,'host_issue_ns');now=_uint(now_ns,'now_ns')
    _need(candidate.validated_at_ns<=issue<=now,'issue must follow validation and not be future')
    if previous_deadline_ns is not None:_uint(previous_deadline_ns,'previous_deadline_ns')
    target=candidate.document['target']
    if target['action']==0:return FiniteActionCandidate(candidate,issue,None)
    duration=target['duration_ms']*1_000_000
    _need(issue<=UINT63-duration,'issue plus target duration overflows uint63')
    requested_end=issue+duration
    deadline=min(candidate.valid_until_ns,previous_deadline_ns) if previous_deadline_ns is not None else candidate.valid_until_ns
    if deadline<=now or requested_end<=now:raise Unavailable('finite action candidate expired')
    if requested_end>deadline:raise Unavailable('full requested target duration exceeds original validity')
    return FiniteActionCandidate(candidate,issue,requested_end)

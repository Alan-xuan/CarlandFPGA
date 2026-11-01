"""Private, single-owner numerical motion transaction; no source authenticators.

The trusted integration supplies admitted original commands and the runtime's
one final fence. This module is not registered as a provider or a Run path.
Scene, asset containment and budgets are explicit authority assertions, never
facts established by frozen dataclasses. See docs/motion_executor.md.
"""
from dataclasses import dataclass, replace
from fractions import Fraction as F
from functools import wraps
import hashlib
import threading

from ...integration import host_envelope as envelope
from ...integration import pc_direct_watchdog as watchdog
from .pc_direct_runtime import BootBinding, StepFence, CommitReceipt, _is_binding
from .motion import certified_path as cp
from .motion import passage_phase as p
from .motion import workspace_boundaries as w
from .motion import solid_clearance as s
from .motion.kinematics import MAX_DT_NS
from . import _offboard_motion_component as off


@dataclass(frozen=True)
class GeometryBudget:
    numeric: F
    asset: F
    obstacle: F
    source: str

    def __post_init__(self):
        s._label(self.source)
        for name in ('numeric','asset','obstacle'):
            value=s._scalar(getattr(self,name))
            if value<0:raise ValueError('explicit nonnegative upper budgets required')
            object.__setattr__(self,name,value)


@dataclass(frozen=True)
class RendererView:
    pose: object
    pose_revision: int


@dataclass(frozen=True)
class ControllerView:
    stopped: bool
    trial_failed: bool


@dataclass(frozen=True)
class _Command:
    boot: BootBinding
    raw: bytes
    sequence: int
    issue_ns: int
    deadline_ns: int
    profile: str
    speed_code: int
    yaw_q: int
    pitch_q: int


@dataclass(frozen=True)
class _CommitFrame:
    relative: p.RelativeTransition
    proof_binding: str
    sweeps: tuple
    solids: tuple
    previous: object
    fence: StepFence | None


@dataclass(frozen=True)
class _Root:
    revision: int
    revoke_generation: int
    pose: object
    pose_revision: int
    phase: p.PassageState
    frame: _CommitFrame | None
    boot: BootBinding | None
    command: _Command | None
    stopped: bool
    trial_failed: bool
    world_invalid: bool
    executed_until_ns: int


@dataclass(frozen=True,init=False)
class _Prepared:
    """Only identity in this owner's private pending registry is accepted."""
    root: _Root
    path: cp.CanonicalPath
    relative: p.RelativeTransition
    sweeps: tuple
    solids: tuple
    proof_binding: str


class PreparationRejected(ValueError):
    """Authority-internal coarse result; do not export a collision oracle."""
    def __init__(self,status,checked_slices=0):
        super().__init__('motion preparation rejected')
        self.status=status
        self.checked_slices=checked_slices


def _entry(method):
    @wraps(method)
    def call(self, /, *args, **kwargs):
        self._owner_check()
        if self._busy:
            self.revoke('reentrant owner transaction')
            raise ValueError('reentrant motion transaction')
        self._busy=True
        try:return method(self,*args,**kwargs)
        except Exception:
            self.revoke('motion transaction rejected')
            raise
        finally:self._busy=False
    return call


def _revoking_entry(method):
    """STOP/world invalidation stays callable while busy, including bad shapes."""
    @wraps(method)
    def call(self, /, *args, **kwargs):
        self._owner_check()
        try:return method(self,*args,**kwargs)
        except Exception as error:
            self._revoke('invalid revoking entry')
            raise ValueError('invalid revoking entry; owner stopped') from error
    return call


def _offboard_entry(method):
    # Reject Root custody before _entry can revoke or alter its executor.
    transaction = _entry(method)
    @wraps(method)
    def call(self, /, *args, **kwargs):
        off._require_unbound(self)
        return transaction(self, *args, **kwargs)
    return call


def _integer(value,minimum=0):
    if type(value) is not int or value<minimum:raise ValueError('strict nonnegative integer required')
    return value


class OwnedMotionExecutor:
    """Trusted owner's store; methods are not exposed to controllers/renderers.

    One thread serializes the runtime, this object and its world registry.
    It must invoke revoke on every STOP/config/source/AI loss independently of
    runtime.stop. Runtime's final callback also rechecks all current evidence.
    """
    def __init__(self,*,initial_state,scene,model,budget,limits=s.Limits(),max_slices=16):
        if not p._valid(initial_state):raise ValueError('valid owned initial/history state required')
        if (type(scene) is not s.Scene or type(model) is not s.CapsuleModel
                or type(budget) is not GeometryBudget or type(limits) is not s.Limits):
            raise TypeError('complete scene, contained body and explicit budgets required')
        _integer(max_slices)
        body=initial_state.context.envelope
        if (model.half_segment,model.radius,model.pivot_radius)!=tuple(map(F,(body.half_segment_m,body.radius_m,body.pivot_radius_m))):
            raise ValueError('workspace and solid body bounds must agree exactly')
        if F(initial_state.errors.additional_margin_m)<budget.numeric+budget.asset+budget.obstacle:
            raise ValueError('workspace margin omits explicit engine/asset/obstacle budgets')
        self._scene,self._model,self._budget,self._limits=scene,model,budget,limits
        self._max_slices=max_slices
        self._owner=threading.get_ident();self._busy=False;self._pending={}
        self._generation=0;self._used_sessions=set()
        self._offboard_owner=None
        self._world_binding=w.digest((initial_state.context,scene.digest,model,budget))
        self._root=_Root(0,0,initial_state.pose,initial_state.pose_revision,initial_state,None,
            None,None,True,False,False,initial_state.monotonic_ns)

    def _owner_check(self):
        if threading.get_ident()!=self._owner:raise ValueError('owner-thread serialization required')

    def authority_snapshot(self):
        self._owner_check();return self._root

    def renderer_view(self):
        self._owner_check();root=self._root
        return RendererView(root.pose,root.pose_revision)

    def controller_view(self):
        self._owner_check();root=self._root
        return ControllerView(root.stopped,root.trial_failed)

    @property
    def admitted_raw(self):
        self._owner_check()
        if type(self._root.command) is not _Command:raise ValueError('no admitted production command')
        return self._root.command.raw

    def passage_state(self):
        self._owner_check();root=self._root
        if root.frame is None:return root.phase
        frame=root.frame;fence=frame.fence
        # Hashing and event materialization deliberately occur outside commit.
        try:
            return p.materialize_committed_transition(frame.relative,start_ns=fence.checked_ns,
                end_ns=fence.step_end_ns,binding=frame.proof_binding)
        except BaseException:
            # This read can occur outside _entry or inside its final callback.
            # Keep the committed frame/pose, but revoke all future movement
            # before propagating an unknown history failure or cancellation.
            # Unknown is not a proved collision and does not set trial_failed.
            self._revoke('passage materialization failed')
            raise

    def prepared_audit(self,handle):
        self._owner_check()
        if self._pending.get(id(handle)) is not handle:raise ValueError('unknown owner handle')
        return handle

    def _revoke(self,reason,*,trial_failed=False):
        self._owner_check()
        # This entry remains usable synchronously during the final callback.
        if type(reason) is not str or not reason or type(trial_failed) is not bool:
            reason='invalid revoke';trial_failed=False
        root=self._root
        self._root=replace(root,revision=root.revision+1,revoke_generation=root.revoke_generation+1,
            command=None,stopped=True,trial_failed=root.trial_failed or trial_failed)
        self._pending.clear()

    @_revoking_entry
    def revoke(self,reason,*,trial_failed=False):
        return self._revoke(reason,trial_failed=trial_failed)

    @_revoking_entry
    def invalidate_world(self,reason):
        """Any scene/asset/epoch/layout edit retires this entire static store.

        A new run must initialize a new executor/history; a new BOOT alone may
        not reinterpret old geometric proofs against new world bytes.
        """
        self.revoke(reason)
        self._root=replace(self._root,world_invalid=True)

    @_entry
    def activate_boot(self,boot):
        root=self._root
        if (self._offboard_owner is not None or not _is_binding(boot, executor=self) or type(boot.run_id) is not str
                or boot.run_id!=root.phase.context.run_id or type(boot.context_json) is not bytes
                or type(boot.ai_instance) is not str or not boot.ai_instance):
            raise ValueError('independently verified exact BOOT required')
        _integer(boot.generation,1)
        context=watchdog._context_copy(envelope._parse_message(boot.context_json))
        if boot.generation<=self._generation or context['session'] in self._used_sessions:
            raise ValueError('retired BOOT generation/session')
        self._generation=boot.generation;self._used_sessions.add(context['session'])
        if root.world_invalid:raise ValueError('world edit requires new run/store/history')
        self._pending.clear()
        self._root=replace(root,revision=root.revision+1,revoke_generation=root.revoke_generation+1,
            boot=boot,command=None,stopped=root.trial_failed)

    @_entry
    def admit_command(self,boot,command_raw):
        """Called only after trusted runtime admission, never as authentication.

        The runtime still checks original observation, source, STATE8 and AI at
        the final fence. Structural parsing here cannot establish those facts.
        """
        root=self._root
        if root.stopped or root.world_invalid or root.trial_failed or not _is_binding(boot, executor=self) or boot is not root.boot:
            raise ValueError('inactive owner BOOT')
        if type(command_raw) is not bytes:raise ValueError('immutable original command bytes required')
        doc=envelope._parse_message(command_raw)
        issue=_integer(doc.get('host_issue_monotonic_ns'))
        context=watchdog._context_copy(envelope._parse_message(boot.context_json))
        parsed=envelope.validate_message(command_raw,producer='control_broker',consumer='world_authority',context=context,now_ns=issue)
        if parsed.kind!='motion_request' or parsed.document['target']['action']!=1:
            raise ValueError('only admitted non-STOP motion_request accepted')
        doc=parsed.document;target=doc['target'];sequence=doc['command_seq']
        if root.command is not None:
            if command_raw==root.command.raw:return
            if sequence<=root.command.sequence:raise ValueError('changed/replayed command')
        profile={1:'fast_9600',2:'stress_300'}[context['transport_profile_id']]
        command=_Command(boot,command_raw,sequence,issue,issue+target['duration_ms']*1_000_000,
            profile,target['speed_code'],target['yaw_q'],target['pitch_q'])
        self._pending.clear();self._root=replace(root,revision=root.revision+1,command=command)

    def _sweep(self,record):
        # CP errors already cover inherited/accumulated numerical position,
        # orientation and speed drift. additional_margin includes all fixed
        # budgets, partitioned exactly (no float subtraction or dropped term).
        budget=self._budget
        extra=F(record.errors.additional_margin_m)
        errors=s.ErrorBounds(record.errors.position_error_m,record.errors.angle_error_rad,
            extra-budget.asset-budget.obstacle,budget.asset,budget.obstacle,budget.source)
        bound=record.gate_bounds
        return s.Sweep(self._model,record.start.state.position_m,record.end.state.position_m,
            record.start.state.orientation_xyzw,bound.arc_length_upper_m,
            bound.curvature_upper_per_m,bound.rotation_upper_rad,errors)

    @_entry
    def prepare_step(self,boot,command_raw,expected_pose_revision,dt_ns):
        root=self._root;_integer(expected_pose_revision);_integer(dt_ns,1)
        if dt_ns>MAX_DT_NS:raise ValueError('canonical duration exceeds 10ms')
        if (root.stopped or root.trial_failed or root.world_invalid or type(root.command) is not _Command
                or not _is_binding(boot, executor=self) or boot is not root.boot or type(command_raw) is not bytes
                or command_raw!=root.command.raw or expected_pose_revision!=root.pose_revision):
            raise ValueError('owner/admitted original command/current revision mismatch')
        return self._prepare_geometry(root,root.command,False,dt_ns)

    def _prepare_geometry(self,root,command,fixture,dt_ns=None):
        # Private fixed body; callers have already checked their exact authority.
        if fixture:
            off._require_unbound(self)
        if dt_ns is None:
            raise ValueError('duration required')
        phase=self.passage_state()
        path=cp.CanonicalPath(root.pose,command.profile,command.speed_code,command.yaw_q,command.pitch_q,dt_ns,
            inherited_errors=p.required_inherited_errors(phase,dt_ns),error_budget_reference=phase.error_budget_reference)
        relative=p.prepare_relative_transition(phase,path,phase.context,max_slices=self._max_slices)
        preview=relative.preview
        if preview.status!='SAFE':
            if preview.failure_candidate:self.revoke('proved workspace violation',trial_failed=True)
            raise PreparationRejected(preview.status)
        plan=path.plan(start_monotonic_ns=relative.anchor_ns,
            deadline_monotonic_ns=relative.anchor_ns+dt_ns+1,hard_stop=False)
        if plan.covered_ns!=dt_ns or not plan.slices:raise PreparationRejected('UNKNOWN')
        sweeps=[];solids=[];elapsed=0
        for index,record in enumerate(plan.slices):
            if record.start.elapsed_ns!=elapsed:raise PreparationRejected('UNKNOWN',index)
            sweep=self._sweep(record);result=s.certify_scene(sweep,self._scene,limits=self._limits)
            sweeps.append(sweep);solids.append(result)
            if result.status!='CLEAR':raise PreparationRejected(result.status,index+1)
            elapsed=record.end.elapsed_ns
        if elapsed!=dt_ns or self._root is not root:raise PreparationRejected('UNKNOWN')
        if fixture:
            binding=w.digest(('offboard-numeric-v1',self._world_binding,root.revision,root.revoke_generation,
                command.sequence,command.issue_ns,command.deadline_ns,command.profile,command.speed_code,
                command.yaw_q,command.pitch_q,relative,tuple(sweeps),tuple(solids)))
        else:
            binding=w.digest((self._world_binding,root.revision,root.revoke_generation,
                hashlib.sha256(command.raw).hexdigest(),command.boot.generation,
                hashlib.sha256(command.boot.context_json).hexdigest(),relative,tuple(sweeps),tuple(solids)))
        handle=w._create(off.Prepared if fixture else _Prepared,root=root,path=path,relative=relative,sweeps=tuple(sweeps),solids=tuple(solids),proof_binding=binding)
        # Runtime has one synchronous step in flight. A later preparation
        # retires the previous handle, bounding retained pending proof memory.
        self._pending={id(handle):handle}
        return handle

    @_entry
    def commit_step(self,prepared,before_commit):
        if type(self._root.command) is not _Command or not _is_binding(self._root.boot, executor=self):
            raise ValueError('production command and boot required')
        return self._commit_numeric(prepared,before_commit,False,None)

    def _commit_numeric(self,prepared,before_commit,fixture,owner):
        if fixture:
            off._require_unbound(self)
        # Consume identity first, including stale-root or failed-fence attempts.
        known=self._pending.pop(id(prepared),None)
        root=self._root
        if known is not prepared or type(prepared) is not (off.Prepared if fixture else _Prepared) or prepared.root is not root:
            raise ValueError('consumed/foreign/stale prepared handle')
        if root.stopped or root.trial_failed or root.world_invalid or (not fixture and not callable(before_commit)):
            raise ValueError('motion owner stopped or missing final fence')
        command=root.command;relative=prepared.relative;candidate=relative.preview.candidate
        # Allocate constant-size publication containers before calling the fence.
        # They remain unreachable outside this stack until the one root swap.
        receipt=(off.Receipt(owner,command.sequence,root.pose_revision+1,0,0) if fixture else
                 CommitReceipt(command.boot,command.sequence,root.pose_revision+1,0,0))
        frame=_CommitFrame(relative,prepared.proof_binding,prepared.sweeps,prepared.solids,root.frame,None)
        new_root=replace(root,revision=root.revision+1,pose=candidate.pose,pose_revision=root.pose_revision+1,
            phase=relative.previous,frame=frame,executed_until_ns=0)
        if not fixture and getattr(self,'_original_world_witness',None) is not None:
            from .original_world_actor_link import _stage_original_commit_witness
            _stage_original_commit_witness(self,prepared,root,new_root,frame,receipt)
        fence=before_commit if fixture else before_commit()  # production callback exactly once
        # From here to publication: bounded strict field tests and bindings only.
        # No geometry, hash, clock, I/O, provider or user callbacks.
        if self._root is not root or type(fence) is not (off.Fence if fixture else StepFence):
            raise ValueError('owner root revoked or invalid final fence')
        if ((fence.owner is not owner if fixture else fence.boot is not command.boot)
                or type(fence.command_seq) is not int or fence.command_seq!=command.sequence
                or type(fence.checked_ns) is not int or type(fence.step_end_ns) is not int
                or type(fence.deadline_ns) is not int
                or (fixture and (fence.checked_ns > (1<<63)-1 or fence.step_end_ns > (1<<63)-1 or fence.deadline_ns > (1<<63)-1))
                or fence.checked_ns<root.executed_until_ns or fence.checked_ns<command.issue_ns
                or fence.step_end_ns-fence.checked_ns!=relative.duration_ns
                or fence.step_end_ns>=fence.deadline_ns or fence.deadline_ns>command.deadline_ns):
            raise ValueError('final fence interval/identity/original deadline mismatch')
        object.__setattr__(frame,'fence',fence)
        object.__setattr__(new_root,'executed_until_ns',fence.step_end_ns)
        object.__setattr__(receipt,'start_ns',fence.checked_ns)
        object.__setattr__(receipt,'end_ns',fence.step_end_ns)
        self._root=new_root  # the single owner-root CAS/publication point
        return receipt

    @_offboard_entry
    def _offboard_activate(self,owner):
        root=self._root
        if (type(owner) is not off.Component or owner._executor is not self or self._offboard_owner is not None
                or root.boot is not None or root.command is not None or not root.stopped
                or root.world_invalid or root.trial_failed or self._generation != 0):
            raise ValueError('fresh exclusively owned numeric fixture required')
        self._offboard_owner=owner
        self._root=replace(root,revision=root.revision+1,revoke_generation=root.revoke_generation+1,stopped=False)

    @_offboard_entry
    def _offboard_command(self,owner,command):
        from .motion.kinematics import validate
        root=self._root
        if (owner is not self._offboard_owner or type(owner) is not off.Component
                or type(command) is not off.Command or command.owner is not owner
                or root.boot is not None or root.stopped or root.world_invalid or root.trial_failed):
            raise ValueError('active exclusive fixture required')
        for x in (command.sequence,command.issue_ns,command.deadline_ns): _integer(x)
        if (command.sequence>(1<<63)-1 or command.deadline_ns>(1<<63)-1
                or command.deadline_ns<=command.issue_ns or (root.command is not None and command.sequence<=root.command.sequence)):
            raise ValueError('fixture deadline/sequence invalid')
        validate(command.profile,command.speed_code,command.yaw_q,command.pitch_q)
        self._pending.clear()
        self._root=replace(root,revision=root.revision+1,command=command)

    @_offboard_entry
    def _offboard_prepare(self,owner,expected_pose_revision,dt_ns):
        root=self._root;_integer(expected_pose_revision);_integer(dt_ns,1)
        if (dt_ns>MAX_DT_NS or owner is not self._offboard_owner or type(owner) is not off.Component
                or root.boot is not None or type(root.command) is not off.Command or root.command.owner is not owner
                or root.stopped or root.world_invalid or root.trial_failed or expected_pose_revision!=root.pose_revision):
            raise ValueError('current offboard command required')
        return self._prepare_geometry(root,root.command,True,dt_ns)

    @_offboard_entry
    def _offboard_commit(self,owner,prepared,fence):
        root=self._root
        if (owner is not self._offboard_owner or type(owner) is not off.Component or root.boot is not None
                or type(root.command) is not off.Command or root.command.owner is not owner):
            raise ValueError('current offboard authority required')
        return self._commit_numeric(prepared,fence,True,owner)


__all__=['OwnedMotionExecutor','GeometryBudget','RendererView','ControllerView','PreparationRejected']

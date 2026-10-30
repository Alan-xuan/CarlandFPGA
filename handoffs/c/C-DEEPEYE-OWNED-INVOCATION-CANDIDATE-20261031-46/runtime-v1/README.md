# C46 original owned invocation adapter v1

This is a default-off PC_DIRECT integration candidate, not a deployed provider,
motion grant, enabled native result, or H12 completion. All writes are private.
Apply the frozen C43 interval successor, then C45 default-off interval patch,
then `c46-owned-invocation.patch`. Install `package/owned_invocation_v1/` under
`competition/deepeye/simulation/authority/owned_invocation_v1/`. The two complete
patched source files are supplied for byte review. Original A baseline is
`aa314dcb953e1aac799b43c5f8a080fa18edf09f`; exact GET argv, raw source, stderr,
exit, SHA256 and Git blob are retained under `source/`.

The original `_production_channels` remains byte-identical to C45 and raises
ActivationUnavailable. No default provider is installed. A must integrate the
original admission mapping described below. Python private names and object
identity are trusted-process conventions, not a security boundary. Neither a
JSON field, callback, hash, PID, child core_ran claim nor constructing a Python
record establishes physical/owner provenance.

## Concrete API and admission chain

`AuthorityConfig.owned_invocation_v1` defaults to None. Opt-in requires exact
`OwnedInvocationPolicy(operation_id, request_hash, tested_commit,
max_invocations, max_reads, max_polls, duration_ms)` plus the existing C45 opt-in,
fixed C44 staged four-file identities and exact entry arguments. K is 2..16:
C44 protocol supports K1 but the original serial owner requires K>=2. The fixed
prospective action duration is 1..100ms, chosen before any invocation, never
shortened after completion. Reads/polls are finite and the original deadlines
remain controlling. The only new start branch calls original
`registry.launch_overlapped`; it cannot adopt or upgrade an already launched
actor. Original registry, process, thread, lifetime and cleanup fences remain.

At the original trusted `channels.verify_observation(event, boot)` admission
callsite, A must already hold the cross-format source allocation. Before returning
its exact VerifiedObservation, it calls private `_retain_original_association`.
The original `_Dependencies.verify_observation` then puts that same result in the
active `_InputTransaction`, and the original runtime must admit it before C46
begins. The hook requires:

* Exact composition/event/active transaction/VerifiedObservation/BOOT/source/clock.
* Original C42 ProjectionSession, producer, capture reference, sample reference,
  current read, registry reference and full ordered history references.
* Original cross-format mapping receipt, source-bound receipt and dispatch-policy
  receipt; exact source and dispatch deadlines; explicit previous-action object
  and bound, or both None when genuinely absent.

The mapping receipt is retained by identity, not interpreted as a truth assertion.
Its authenticity and raw4-to-TELEM/EVENT association must already be established
by A's original producer/ingress allocation. Current original runtime admits
TELEM aggregate means or EVENT peaks; raw4 counts cannot be compared as if they
were those means. This code does not synthesize that relation from sequence or
context and does not install a constructor accessible to child/controller input.
Missing original association fails before journal preparation or write.

The implemented chain is: original producer attachment -> active transaction ->
runtime-admitted observation -> exact retained capture/sample/raw SHA -> complete
C42 assembly -> fixed C36 host projection (core0) -> immutable padded C44 request
-> original serial preparation/write/read/poll -> original pair seal -> fixed
C44 verifier -> finite quantization -> real C43 interval candidate -> original
C45 `_CompletedInference` and candidate owner. C36/C44 consistency alone confers
no authority. The original source admission/proof/history is retained host-side;
only compact public input crosses the 16384-byte request boundary. No planner,
original C28 code or native actor is executed by C46 on C.

`accept_observation` returns PENDING after one reserved dispatch. Each
`poll_owned_invocation()` advances only original finite IO. Partial frames and
pending OS operations remain PENDING. No complete event exists until both exact
frames, all original OS operations and original journal/pair seal succeed. Any
uncertainty, malformed/trailing bytes, timeout/budget violation or foreign event
fails closed; it never resends. Transaction exit clears the active transaction;
the immutable association retains its original object but never reactivates it.

The returned completion event is an opaque empty-slots token. It exposes no
proof/record/finite data. Adapter-private storage independently retains original
record, immutable request, proof bytes, finite candidate, caps and Root guard.
`inspect_owned_candidate(event)` returns the immutable C43 FiniteActionCandidate
without consuming the event. `accept_completion(event)` consumes the exact token
once and routes only that independently retained proof into C45. With opt-in,
foreign/scalar completion inputs cannot fall back to the old channel.

Inspect returns the original `host_issue_ns`, complete target duration and
deadline. A's original broker must use that fixed issue or revalidate the whole
duration against the same original bounds at a genuinely later issue. It cannot
renew from arrival, silently shorten duration, or extend using the observation
upper bound. C46 creates no motion_request, registers no authority and sends no
board command. Original command admission, mailbox, heartbeat, final fences and
typed original executor remain required.

## Root, time and finite action semantics

Pending work retains the exact original link/book/executor/Root and serialized
root_revision, pose_revision, revoke_generation and pose. Before further IO,
after seal, before proof creation and on inspect/consume, any object replacement
or field change rejects, including a new numerically identical Root. This is a
conservative continuity policy, not a fabricated validity span.

The completion interval is `[dispatch.raw_call_bracket_ns[0],
original_series_ticket.observed_qpc_ns]`. The first retained read lower is kept
separately. All remain original uint63 host QPC in the same domain. Asynchronous
read-call upper is **not** whole-RESULT observation: original `account` does not
rewrite that bracket. Require dispatch lower <= read lower <= seal observation
<= now. No CPU-finish timestamp is invented. C43 uses lower+max_age and original
source/dispatch/previous caps. Inspect/consume additionally require now before
candidate.valid_until_ns and, for positive actions, finite.deadline_ns. STOP has
no positive lease but still expires at candidate validity. Each consume/inspect
also calls original ActorOwner._invocation_check for actual retained lifetime.

Quantization is new candidate behavior. Original kinematics uses body +Z forward,
+Y up, +X right, xyzw body-to-world quaternion, body angular axis (-pitch,yaw,0).
World direction is rotated back to that body; nonforward direction rejects.
Positive yaw steers +X and positive pitch +Y. Angular code is desired degrees
times 1e6 / prospective duration_ms, then conservatively clipped to the original
combined curvature ROM and truncated toward zero. Exact integer ROM is rechecked
by original motion.validate. Speed is floored using Fraction against original
Decimal SPEED_STEP and capped at 20; zero becomes STOP. Speed never exceeds the
advisory limit. Truncation contributes less than one angular code per axis after
clipping; saturation can leave substantial heading error. This is not a proof of
trajectory accuracy, clearance, 1% accuracy or 100ms end-to-end performance.

## Second H12 path: explicit remaining gap

Exact existing input is `ActorComposition.accept_board` -> original
`_Dependencies.verify_board` -> exact `VerifiedEnvelope(boot, raw)` ->
`PcDirectRuntime.board` -> `board_response`, hardware_bridge to world_authority.
Source lines 311..333 only update STATE8 heartbeat/fault state; other healthy
responses explicitly do not create a capture. `ReceiptLedger.claim_board_response`
in pinned `live_board_receipts.py:224` is a one-use schema translation with null
physical_capture_record_sha256 and no manufactured sample interval. It explicitly
requires separate peer/BOOT authentication. `original_world_actor_link.py` retains
an original numerical CommitReceipt after already-authorized execution and calls
itself an identity association, not a source/channel/motion grant. Neither is a
typed board-capture-to-motion authority producer. The private offboard component
is a numerical fixture and is not used.

A still must supply a distinct original board-derived motion producer with exact
physical frame/capture, build/BOOT/source/sample/clock/command association and
typed original admission to the executor. Do not route this PC candidate through
that identity. This second chain is not implemented here; neither H12 chain is
claimed accepted from these C controls.

## Executed evidence and limits

Every NEW process is bounded to 25 seconds. No native handles, C28, model, PDE,
old test suite, service or board was executed. `test_c46_new.py` removes relative
imports from the exact adapter AST and injects explicitly fake original owner/IO/
producer objects. It uses real pinned C44 verification, original motion numeric
code and actual C43 validation with the already frozen C43 vendor dependency.
The C36 projection and actual owner provenance are fake in these controls; the
product path uses fixed dependencies. This does not prove original provider
installation, asynchronous native custody, actual clocks or enabled execution.

| phase | exact execution | result |
|---|---|---|
| run01 | construct patch/copy fixed sources; no test | exit0 |
| run02 | initial 11 NEW methods | exit1: 9 passed, 01/05 fixture ADVISE_REASON errors |
| run03 | only corrected fixture 01/05; production unchanged | 2 passed exit0 |
| run04 | Root/opaque production change: affected05 and NEW12/13 | 3 passed exit0 |
| run05 | candidate/action expiry + lifetime: affected05 and NEW14 | 2 passed exit0 |
| run06 | changed fail-closed08 and NEW STOP-age15; production unchanged | 2 passed exit0 |
| run07 | syntax, 20 exact GET pins, C45 patch and default gate static audit | exit0; no imports |

Full versions/run02..run06 preserve executed source and test bytes, verified
against each actual phase hash. run02 original failure is not erased. Final
source matches run05/run06 production; earlier unaffected controls were not
rerun on final source. No aggregate final-suite pass is claimed. Initial setup
also had one existing-directory error, one GBK source-read UnicodeDecodeError
before any GET, and bounded read-only path/glob lookup failures; these are tool/
setup failures, not product test results. Original native session records remain
available to main. Final static audit checks source pins, syntax and exact
integration diff without importing source modules.

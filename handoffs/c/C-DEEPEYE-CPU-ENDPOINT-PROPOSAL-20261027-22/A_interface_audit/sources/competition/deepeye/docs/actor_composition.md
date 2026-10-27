# Original-actor composition library: production unavailable

Task DEEPEYE-IMPLEMENTATION-20261014/v1, A-actor-composition-implementation-20261019-v1.
Selected design SHA256 `6ab5929285a4a5ef1fa55ff2f47bd8230c8f318a93a08d31b437903fec3617dd`.
Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, H01-H15 canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` unchanged.

`simulation.authority.actor_composition.create_authority(AuthorityConfig(...))` is a trusted
library composition entry. Its fixed production channel/package gate currently raises
`ActivationUnavailable` **before ActorRegistry construction or launch**. No actual AI entry,
authenticated readiness/BOOT/channel or measured source/clock/capture provider is installed.
The library does not enable viewer Run, register a product provider, stage a model, launch a
process or implement the four product processes. Importing it does not load the native backend.

The explicit config is private trusted-main state: actor policy, initial world state, solid
scene/model/budget, heartbeat timeout, geometry slice bound, approved inference model SHA256
and fixed inference progress age cap. It is neither a credential nor
an untrusted controller message. The factory has no public provider, verifier, registry,
executor, actor, PID, HANDLE, alive boolean or AiLease injection argument. The only lifetime
adapter target is this factory's original actor.ai_lease; geometry targets its own executor.
The channel adapter cannot replace either. Python privacy and immutable dataclasses do not
protect against malicious code already inside the trusted authority process.

## Ownership and activation

The factory retains a holder in private `_RETAINED` before registry construction/acquisition.
It constructs the actual registry, owned executor and runtime on one thread. The registry keeps
every original owner, including a process acquired before launch raises. Recovery holders are
never evicted automatically, adopted from disk, reopened by PID or force-discarded. A future
trusted recovery manager must account for this deliberate retention and admission bounds.

After original authenticated readiness/BOOT evidence exists, one closed transaction must:

1. Derive one fresh exact BootBinding from the original owned actor/channel and verifier. No
   plain dataclass, READY text or matching caller string authenticates it.
2. Activate the runtime and executor with that same retained object, then bind the original
   actor to those exact authorities. Recheck transaction veto, verifier health and actor life
   before opening command admission. A failed proposal cannot be retried on this composition.
3. Route runtime command admission first, then admit only its original accepted non-STOP bytes
   to the executor. Broker STOP closes admission and never becomes movement.

The production verifier is deliberately absent. Tests patch a module-private channel factory;
their opaque object identities, synthetic progress status and valid JSON/CRC are **fixtures**,
not real endpoint authentication or inference. They provide no production fallback. A real
implementation needs separately reviewed bounded persistent IPC, original endpoint ownership,
one-use readiness association, approved model/package provenance and actual device/initialization
evidence. Model initialization still does not establish H11 usefulness. Current synchronous
write helpers provide no hard cancellation deadline; this library adds no IPC protocol or wire
fields. Original authenticated inference completion/source/timing evidence remains a missing
provider obligation. The progress gate below consumes private verifier results; synthetic
test records and fixture health checks do not fulfill that obligation.

## Command-bound inference progress

Progress work `A-ACTOR-PROGRESS-IMPLEMENTATION-20261019-v1` follows selected design SHA256
`cb91477153276369c6eaead242cbecb70423804f6939bbbef49a788a931451db`.
`progress_max_age_ns` is an explicit integer in 1..2**63-1; `ai_model_sha256` is an
explicit 64-character lowercase hex hash. Neither has a permissive default. Invalid policy
rejects before acquisition. These values are trusted-main policy, not measured AI performance.

Each activation captures one monotonic callable and starts an EMPTY gate with fixed deadline
activation time + age cap. EMPTY has no positive progress lease. The first completed inference
must arrive within that initial budget. Time, IDs and sums are bounded; booleans, integer
subclasses, overflow and clock regression reject. The gate retains one current immutable
command/completion and increasing command, candidate and invocation IDs, not an unbounded cache.

The private `_CompletedInference` record must come from the original channel verifier and bind
the exact BOOT object, channel object and clock domain. It includes the original candidate bytes,
invocation ID and conservative dispatch/completion time bounds. The existing host-envelope
validators check the candidate and broker request; model hash, candidate ID, full target and
causal observation must match. The ordered times are:

`activation <= dispatch_lower <= completion_lower <= candidate_completed <= completion_upper <= request_issue <= trusted_now`.

The deadline is **original completion_lower + fixed age cap**, never receipt time + age cap.
An exact duplicate preserves both bytes and original metadata/deadline; changed duplicates
reject. A newer command needs strictly increasing candidate/invocation IDs while the old gate
is still healthy. Unrelated inference, channel heartbeat, ACK, polling or process survival
cannot renew the current command. Expiry/revocation is irreversible within this activation;
late completion cannot resurrect it. STOP requires no completion or slot verifier and retires admission.
All callbacks are bracketed by the existing owner veto and trusted clock checks.

Every runtime lease request still calls the original `actor.ai_lease`. After that HANDLE sample,
the adapter rechecks the exact gate/generation, actor instance, BOOT and current admitted bytes,
then returns the minimum of the original actor lifetime deadline and the bound progress deadline.
The final lease seam adds no IPC, channel callback, envelope parsing or clock callback. Existing
runtime post-sample time checks and executor strict `step_end < deadline` apply to the full dt,
including expiry during geometry preparation, original HANDLE observation and actual commit.
Revocation sets the gate before cleanup callbacks; later callbacks cannot restore freshness.

Private object identity and valid JSON remain in-process correlation checks, **not authentication**.
There is still no real completion producer, bounded authenticated IPC or genuine AI model here.
The production gate remains unavailable. A responsive fixture is not evidence of H11 usefulness.

## Stateful original-completion owner

Work `A-R03-STATEFUL-OWNER-IMPLEMENTATION-20261020-v1` implements the selected
private PC_DIRECT composition design. `_CompletedInference` now lives in
`candidate_owner.py`, with its private import alias retained in the composition.
The progress gate's identity, interval, replay and deadline checks are unchanged.
Its record is still a container; constructing it, a mailbox Selection, a HIL
Association, a boolean or a C ordinal does not establish authentication.

Three additional **mandatory original providers remain absent**:

| Private channel method | Required original evidence |
|---|---|
| `mailbox_activation_for_boot(boot)` | Exact BOOT/source/clock identity, pre-established slot origin, measured conservative USB and packing upper bounds |
| `verify_completion(event, boot)` | Original retained actor completion/IPC event and invocation provenance, approved model/candidate, conservative dispatch/completion intervals in the owner clock |
| `verify_slot(event, boot)` | Original current decision-window event for that BOOT/source/clock |

Missing methods or unknown bounds refuse. No provider is created by the private
record types; `create_authority` still fails before any registry acquisition.
The adopted mailbox uses the frozen BOOT profile document and its full digest.
No command receipt, local time, C ordinal, caller proof or Selection reconstructs
missing evidence.

After actual runtime observation admission succeeds, the owner offers the same
single verified observation record's original bytes and sample lower bound to
the mailbox. It neither re-verifies nor taps an observation rejected by runtime.
`accept_completion(event)` verifies an original event before command selection.
The owner refreshes its actual monotonic clock after every external verifier
callback and rechecks the same veto epoch. The mailbox deadline is checked
`completion_lower_ns + progress_max_age_ns`; offering a completion never updates
the initial/current progress deadline.

For a new non-STOP `accept_command(event, slot_event=...)`, the existing broker
verifier runs first, then the original slot verifier. Default legacy selection consumes only
at the refreshed actual clock's exact legal slot instant. A verifier returning
one nanosecond late refuses. No scheduled timestamp, equality relaxation or
fictional jitter allowance is substituted. These rules do not establish that
any real scheduler can hit that instant.

Trusted-main config may explicitly opt into PC_DIRECT fixed-anchor consumption
window v2 with `pc_direct_window_v2=PcDirectWindowV2(10_000_000)`. This root-selected
10 ms policy is not a measured scheduling bound. The original grant k fixes
`S=origin+first+k*period`, `E=S+W`; original ready must be at or before S, and the
refreshed actual time must satisfy `S<=now<min(E,original_deadline)`. Strict bounded
integer arithmetic and `0<W<period` apply. HIL and default exact-slot behavior
remain unchanged; policy/entry mixing refuses. The original proof, irreversible
consume, ProgressGate and final fence/CAS remain in place. E limits consumption
only and does not renew motion or progress deadlines. Production activation is
still unconditionally unavailable. See [v2 contract](pc_direct_window_v2.md).

For a fresh run, trusted main may pass one exact fixed `QpcHostClock` through
`create_authority(config, host_clock=binding)`. The same callable/domain object
reaches ActorRegistry (including original HANDLE sampling), runtime, progress and
candidate ownership. Ledger/BOOT use that same run binding; None retains legacy
defaults. This is raw clock routing, not a provider or measured timing authority:
unknown timestamp uncertainty remains unknown and production still rejects before
registry acquisition. No v2 width, original deadline or final fence/CAS changes.
See [raw QPC clock contract](host_clock_qpc_v1.md).

The exact retained original completion object passes through selection to the
unchanged progress gate. The adapter keeps only one pending proof, one committed
command/proof association and one synchronous input transaction. The current
association is installed only after runtime and executor admission both succeed.
Failure retires the owner; a consumed proposal is never reinserted. Exact
current command bytes reuse the original committed proof without another slot,
consume or completion callback and cannot renew any deadline. Changed duplicates
and a newly numbered command using an already consumed candidate refuse.

STOP and failed transitions clear pending/current proof and the input transaction,
and stop the mailbox before cleanup/authority callbacks. Retirement has no reset
or mailbox reactivation path. New ownership requires a new composition and
independently fresh original BOOT. The actor lifetime target, runtime freshness,
geometry checks and executor's final callback/root CAS remain unchanged; no new
work is inserted between that final callback and CAS. A later veto preserves
an already observed positive CAS receipt.

The integration fixtures retain real mailbox/runtime/executor and synthetic
upstream/native/time only. Their initial clock is explicitly placed at 210 ms
with a pre-established origin 0 and zero synthetic transfer costs. This is a
deterministic legal test slot, not measured scheduling/transport evidence. The
old placeholder BOOT digest is replaced by the actual frozen profile digest.
Fixture completion events are emitted before broker command creation; the old
command-to-completion lookup is removed. Existing verifier-adversary tests now
target `verify_completion`. A legitimate unrelated completion may remain
pending, but the old command still expires at its original deadline.

Two tests that genuinely traverse the next 500 ms window explicitly use a
750 ms progress policy and intermediate STATE8 heartbeats. Their original
ordering/replay assertions remain. Separate controls preserve refusal when a
5 ms policy attempts that wait. The default 100 ms and all 5 ms full-dt boundary
tests remain as stated; no production policy or equality was tuned.

## Revocation and outcomes

Every event/step uses the same owner-thread guard. Malformed shapes and caught reentry veto the
outer operation. A foreign thread only sets a pending Event; the owner drains it before work,
and the fixed actor adapter checks it again after the original HANDLE observation. No foreign
thread closes handles or calls the executor. Polling cadence belongs to the future owner loop;
no watcher/service or guaranteed owner-hang supervision is added.

Failure first closes admission and advances the composition veto. Runtime STOP and executor
revoke independently check the exact original activation at each callback dispatch. The second
check happens after STOP returns, since it may activate an executor successor. R1 actor callback
fences remain in force during cleanup. Even before actor.bind_verified_boot has installed its
own callbacks, the composition can revoke each successfully activated original authority.
Callback exceptions cannot skip the other target or actor cleanup.

Cleanup occurs after the outer owner call has unwound, avoiding reentrant native teardown
during a sample. It visits the registry's retained owners and uses their existing one-attempt
cleanup; repeated close never retries native effects. The primary exception, callback/cleanup
errors and actual last runtime step stay private and strongly retained. Uncertain resources or
incomplete actor evidence remain QUARANTINED. CLOSED describes cleanup, not successful launch
or inference. Public errors are sanitized; status exposes only lifecycle state and step results
only committed/pose_revision. Do not serialize private objects, causes, raw source/geometry
errors or authority exceptions to a controller. Renderer/world transport remains separate work.

All noncommitted steps conservatively retire this composition, including healthy idle/normal
expiry. This deliberate availability cost avoids guessing idle semantics from exception text.
A new composition/actor and independently verified fresh run/session/generation are required
for recovery; no actor replacement occurs inside the old composition. Existing world-edit
invalidations still require a new world/store/history. Late old close/poll/errors cannot revoke
a successor activation.

Geometry preparation, full original dt, original TTL/observation/heartbeat bounds and the
executor's one final callback/strict end<deadline/root CAS remain unchanged. No IPC, log, hash
or added probe is inserted after that final callback. An original-HANDLE sample is a recent
nonsignaled observation, not survival through CAS or responsive/useful inference. A veto after
an observed successful CAS retires future admission while preserving the positive commit fact;
it cannot undo or relabel the numerical side effect. A negative outcome is absence of an
accepted commit receipt, not a universal independent proof against side effects from a broken
trusted executor/provider. Unknown outcomes must never be replayed automatically.

## Verification scope

Offline tests retain the real ActorRegistry/resource cleanup and numerical runtime/executor;
only native acquisition and original channel events are synthetic. They cover zero acquisition
at the absent production gate, detached static channel lease attempts, original death before
and during final checks, real pose publication, partial activation, identity-fenced callbacks,
STOP, malformed/reentrant/foreign calls, strong recovery and post-CAS veto semantics. Existing
actor/runtime/executor regressions use the accepted actor-repair/current-G06 dependency bytes.
The separately owned moving native harness/document are not imported or pinned dependencies.

Progress verification retained all 24 original test methods unchanged. Three preimplementation
counterexamples actually committed after progress expiry/at the full-step deadline; their RED
logs are preserved separately. Added tests exercise the actual executor fence, both deadline
minimum orders, end equality versus one nanosecond before, monotonic advancement/replay,
duplicate nonrenewal, absent/wrong completion, source/model/clock binding, integer/overflow
bounds, expiry during original Wait, irreversible revoke and heartbeat nonrenewal. These are
offline software tests with synthetic time and original-verifier fixtures, not native AI runs.

No native actor, genuine AI/readiness, real source/channel/BOOT/timing authentication, product
Run, both complete H12 chains, game rendering/interaction, hardware/board or all29 formal card
acceptance is established. PC_DIRECT remains a legal independent full path; HIL_PC_FPGA still
requires its own original board actuation/capture evidence. Neither becomes mandatory for the
other. Controller inputs remain causal FPGA observations, legal task geometry and odometry;
world truth, future sensors and collision rejection details never become an AI channel.

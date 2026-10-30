# C47 finite original actor bootstrap, partial implementation

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work
`C47-ORIGINAL-FINITE-ACTOR-BOOTSTRAP-IMPLEMENT-v1`.
Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
H01–H15 and both H12 chains remain required. Only A operates the board.

This adds an executable trusted-root configuration/lifecycle helper at
`competition/deepeye/tools/finite_actor_bootstrap_v1.py`. It does not install an
authenticated channel provider. Production activation at the pinned A commit
still fails before actor stage/acquisition. Production functionality, genuine
same-handshake attachment, and H12 acceptance remain incomplete.

## Installation and exact dependency order

1. A baseline `0a3cd027b234374519110b67894c94db4cfe9e74`, already containing
   C43/C45 and the canonical package import fix.
2. Apply the complete frozen C46 patch and package from source
   `0d18d5d649bcbf0dabcb1349369b97126b734c7e` / delivery head
   `1e5c9ea2c729ea574d547cf70726491f363ff3f7`. In particular, actor composition
   must be SHA `3765ba5e68942dc888b0235792c63963e6e29fb5be66a4f14226e0c0ba29203a`.
3. Apply `c47-finite-bootstrap.patch`, which only adds the new helper. No old
   source, C43 runtime/schema, C42 provider/assembler or C46 bytes are changed.

This is a Python package import, not a directly executed script. Import through
`competition.deepeye.tools.finite_actor_bootstrap_v1` in A's existing trusted
root. No CLI, controller JSON, generic channel callback, environment override,
second registry or substitute actor is introduced.

## Concrete trusted-root calls

The original root supplies its existing `FunctionalWorld`, `AuthorityConfig`,
and a C46 `OwnedInvocationPolicy`. Its `ActorPolicy` must include the actual
runtime manifest and existing absolute paths; no runtime hash is generated or
assumed by C47. The fixed C46 entry is `runtime/python.exe` with arguments
`('-I','-B','c37_entry.py','--actor-stdio-v2','--max-invocations',str(K),
'--request-bytes','16384')`, K from the original policy, within 2..16.

```python
from competition.deepeye.tools.finite_actor_bootstrap_v1 import (
    FiniteLimits, prepare_config, FiniteActorBootstrap)

# These are actual existing trusted-root allocations, not parsed credentials.
limits = FiniteLimits(max_polls=host_call_budget,
                      max_teardown_observations=observation_budget,
                      enabled=True)
config = prepare_config(original_authority_config, original_c46_policy,
                        clock=original_world.clock, limits=limits)
run = FiniteActorBootstrap(original_world, config, limits=limits)
with run:                       # exactly one original activate call
    run.accept_boot(original_opaque_boot_event)  # original verifier must accept
    # The trusted root retains its original board/observation/command methods.
    # run.poll() invokes original health/expiry; run.poll(owned_invocation=True)
    # additionally polls the original C46 pending invocation, never fabricates one.
    # Original sampling/event scheduling is supplied by A, not by a callback here.
    pass
states = run.observe_teardown()  # retained scalar fields only, finite count
```

The code above describes the eventual callsite: current A0a3 `with run` raises
`ActivationUnavailable` at the original production gate. No original BOOT event
is available from this package. Do not supply arbitrary dictionaries or dataclass
instances as a substitute. `enabled=True` selects code, not authority.

`prepare_config` preserves the entire original scene/model/budget/policy/caps
and all IDs by dataclass replacement; it only selects interval-v2 and the
provided C46 owned policy. It calls existing ActorPolicy and C46 validators.
It does not infer source/dispatch/previous-action deadlines. The additional
poll and diagnostic counts can only stop calls; they never renew deadlines.

The world is **already prepared** before this API. “Zero acquisition on missing
provider” means no new actor acquisition, not that preparation of the original
native world was free. On successful wrapper construction, its caller explicitly
hands it the one original world close responsibility. Configuration failure
before construction leaves lifecycle responsibility with the caller.

## BOOT, source and cleanup ordering

The exact original chain is FunctionalSource.activate_original_authority →
actor_composition._create_authority_for_original_world → original production
channels gate → link claim → retained composition → C46 original `_start` /
launch_overlapped. Original ActorOwner allocation/instance exists before
`accept_boot`. The original verifier then checks the opaque event against that
instance/run and performs the original runtime/executor/mailbox activations.
Only its successful `ACTIVE` state permits the helper to call source.start once.

Source.start itself requires the prepared source to remain NEW and starts its
original clocked lifecycle once. This ordering is locally compatible with the
two explicit A methods. Whether the future genuine handshake producer can
obtain BOOT independently of starting that sample stream is **not established**:
A must supply its actual callsite. There is no invented circularity workaround,
prefabricated BOOT or claim that the current provider can run this sequence.

Any activation, BOOT or poll failure retires this wrapper and calls original
FunctionalWorld.close once. Original source recovery retains a partially
created composition; the wrapper keeps the same world/source. Original body and
cleanup exceptions remain separately retained. Reentry/restart cannot launch a
second actor. Close uncertainty never triggers a retry. Read-only observations
read only original `_state` and `_cleanup_attempted` scalar fields. They do not
call diagnostics (its entry wrapper can clean up on error), poll_teardown,
close, terminate, reset or any other actor method/property. They do not advance
any pending native operation, and explicitly return resource_confirmation=false.
Wrapper RETIRED
does not mean native CLOSED. A's original owner remains responsible for any
retained unknown/quarantined native resource; C47 claims no cleanup success.

A private strong-reference relation reserves the original world and source at
wrapper construction, before any start. A second wrapper over either same
object is rejected without taking close responsibility. This relation survives
failure and close and has no release/reset/transfer API. It is only local
lifecycle ownership, not a receipt or authentication mechanism; no original
world/source flags are changed to claim it.

## Exact missing original producer facts and attachment callsites

There is **no consumable same-handshake receipt type** in the pinned sources.
Consequently C47 implements no authority-enabling attachment branch, new
receipt dataclass, opaque token verifier or public injection hook.

* `actor_composition._production_channels(config, host_clock=original_clock)`
  still raises. A must provide the fixed original channel construction path
  backed by actual transport/handshake allocations, not a caller factory.
* Original `channels.verify_boot(event, run_id=..., instance_id=...)` must
  independently verify the actual event and return the existing exact
  `pc_direct_runtime.BootBinding(run_id, generation, context_json, ai_instance)`.
  The record itself is a verifier result, not a credential. Its instance is the
  just-created ActorOwner instance, never a JSON PID/identity supplied by C47.
* The same original handshake must bind that BootBinding's **legacy**
  `context_json` to the separate C42 proof Context and actual configuration,
  source/board receipts, generation and original QPC domain. No cross-format
  equality/merge or invented IDs is justified. A must supply the actual receipt
  class, allocating function, retained references and verifying callsite.
* Current `FunctionalSource.read_current_with_registry()` performs the ordered
  getter/registry read, retains original `_RegistryView` and `_RegistryHold`,
  and keeps `context_attached=False`. Do not flip it or treat non-null view as
  that missing handshake receipt. Once A verifies an actual mapping, the
  existing `FunctionalSource.attach_registry` → `ProjectionSession.attach_registry`
  path receives its actual context/generation/observation ref. Preserve the
  observed bounds; a getter is not an atomic all-system snapshot.
* Inside the original `channels.verify_observation(event, boot)` call made
  during `ActorComposition.accept_observation`, A must call existing C46
  `_retain_original_association(owner,event,record, session=...,
  capture_ref=...,sample_ref=...,current_read=...,registry_ref=...,
  history_refs=...,mapping_receipt=...,source_bound_receipt=...,
  dispatch_bound_receipt=...,source_deadline_ns=...,dispatch_deadline_ns=...,
  previous_action=...,previous_deadline_ns=...)` before returning the exact
  original VerifiedObservation. All attachments are original retained objects;
  presence alone is not authentication. No missing cap is derived from age.
* Existing checkpoint, board/command verifier and mailbox activation/slot
  paths remain mandatory. `live_chain_channels.LiveFourChannelChannel` explicitly
  supplies diagnostic plumbing only, not authenticated production authority.

A reported B131 delivered/integrating; it is not listed as absent. Qualified
build/BOOT and authentic legacy STATE8 heartbeat are still original A facts.
TRACE and model/software completion cannot replace that heartbeat. A151 native
transport startup is A-reported prior evidence, not re-executed or requalified.

## NEW bounded evidence

Eleven distinct C47 software controls only, using isolated AST local-import
substitution with explicit fake lifecycle objects, not native/model/board code.
The exact A production refusal AST is executed. The canonical import control
executes the exact A host import branch and the real pure completion_interval
module/class, with its validation function temporarily replaced by a test
return to isolate module identity. It does not claim schema/semantic validation.

* run01: eight new controls, seven PASS and one real RED. The initial diagnostic
  helper called poll_teardown; the read-only control recorded two side effects.
* run02: only that affected control, PASS after removing those calls.
* run03: one new scope-error/cleanup-error control, real RED: close replaced the
  original body exception.
* run04: only that control, PASS after retaining both and propagating the original.
* run05: main review found diagnostics itself has an effectful entry wrapper;
  a new fault-injection control reproduced the error/cleanup-call risk.
* run06: only the new diagnostic fault and adjacent read-only/budget controls,
  PASS after eliminating all actor method/property calls from observation.
* run07: new duplicate world/source close-owner control, real RED: two wrappers
  could previously be constructed before either started.
* run08: only that control, PASS with the permanent private lifecycle relation;
  original owner still starts/closes once and source aliases cannot acquire it.

Raw exits `[1,0,1,0,1,0,1,0]`; each child has a 30 s timeout, source snapshots, exact
command and stdout/stderr. No broad rerun after the narrow fixes. No original
suite, core, native actor, model, PDE or board execution. Independent review and
main acceptance remain outstanding.

Read/fetch mistakes are preserved: first mkdir encountered an already-created
empty exclusive directory; first guessed tools URL returned 404 (later corrected
using the exact Git tree); a later source read misspelled deepeye and exited 1
after its GETs had succeeded. Original outputs are in the native session;
fetch01-partial-verified.json records the 404. No repeated GET or lost source.

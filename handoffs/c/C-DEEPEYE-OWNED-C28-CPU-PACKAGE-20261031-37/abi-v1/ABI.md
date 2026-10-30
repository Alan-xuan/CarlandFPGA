# C37 finite owned child ABI v1

Operation C-DEEPEYE-OWNED-C28-CPU-PACKAGE-20261031-37. Interface-only delivery; implementation and runtime closure are pending. A31 selected host core0 -> child same frozen core1. First invocation only; future serial support is not enabled.

## Selected boundary

1. C36 host entry project_interval_json(full_proof: bytes)->bytes is default off, validates all original moving-book/current/action/capture/admission/age/quality facts within its <=1MiB proof budget, and calls C28 zero times. It returns unavailable/STOP for missing evidence. Contradictory provided evidence remains rejection, even when another fact is missing or disabled.
2. Eligible host projection contains only exact public observations, own poses and goal/config required by C28. Original full evidence stays with A's original owner/recorder. A's provider retains the real association among full validated proof, exact serialized request, original process/package/pipe, one-use transcript, actual bytes, host times and final candidate. That association is not a caller boolean, echoed ID, hash-only JSON proof or imported private owner object.
3. C37 child checks its compact public input, constructs an exact internal computational view and invokes the same frozen C28 recommend code object once. No C36 composed recommendation call in host followed by another planner in child. Missing host proof never dispatches a planner request and never creates a completion grant. Child consistency checks do not authenticate the source, BOOT, model or authority.
4. Only A's original provider can construct _CompletedInference after its own actual checks. Child READY, STOP/ADVISE, timestamp, successful exit and digest are insufficient individually or together.

The old requirement to send all proofs inline to child is explicitly replaced by A's reviewed host projection boundary, not silently bypassed. No truth/layout/material/seed/private owner data crosses into child. Current A schema3 lacks required original external/capture/admission/BOOT proof; production remains unavailable. The separate C38 readback-identity finding and strict old-span-end < reserve.lower gap remain A/main blockers; no C37 workaround or fabricated exact commit.

## Concrete first-invocation protocol

Unchanged original host facts are pinned in sourcepins.json and DESIGN.md's exact-host section: original ActorOwner has one consumed invocation slot and one reserved WriteFile, raw request total <=16384, read chunk <=8192, reads only after actual recorded full write. Original native readiness event is appended with input/output handles. No flag reset, second slot or original native actor operation is proposed.

Staged command contract:

`runtime/python.exe -I -B c37_entry.py --actor-stdio-v1 --max-invocations 1 --request-bytes N READY_HANDLE INPUT_HANDLE OUTPUT_HANDLE`

N is fixed by trusted ActorPolicy to the exact framed request size 5..16384. Last three handles are appended by original actor. Child initialization validates fixed dependency hashes, prepares the core and signals the inherited native event. It emits no unsolicited stdout. It reads exactly N bytes, verifies the 4-byte LE length equals N-4, strict-decodes one JSON request, then emits one correlated READY frame and one correlated RESULT frame; READY means package protocol readiness only, not provenance. No waiting for stdin EOF, extra request, dispatch retry or remainder. Child exits after this one result. Initialization failure exits without a READY claim.

The JSON payload of the entire outer request is <=16380 bytes; no evidence or history truncation to fit. Generic codec payload1..16384/chunk<=8192 remains unchanged. Strict UTF8, duplicate-key refusal, no BOM/nonfinite/unknown keys, <=4096 nodes/depth24 are proposed package bounds. C36 projection has stricter field-specific bounds and combined history+candidate+actions<=32. Final agreement must use the lower applicable bound at every layer.

Envelope exact keys: abi='c37-owned-cpu-package/v1', kind='recommend', echo_ids, optional enabled (defaultfalse), input (object). echo_ids retains operation_id/run_id/actor_instance_id (1..192 original ASCII label grammar), invocation_id (1..uint63max), tested_commit (40hex), package_manifest_sha256 (64hex). They remain labels, not authority. C36 public-view.schema.json requires projected enabled explicitly; outer enabled defaults false but must agree with that required bool. Missing projected enabled is rejected, not inserted. Invalid booleans/conflicts reject. This replaces the earlier message-level suggestion of two optional enabled fields and is reported to main for common freeze. Full request hash is computed by host from original complete header+JSON wire, avoiding a self-referential field; child result echoes its calculation for comparison only.

Frozen compact input exact keys, aligned with sibling's latest proposal:

| Field | Exact public content |
|---|---|
| schema_version | 1 |
| projection_id | Literal c36_c28_public_view_v1; not an authority token |
| enabled | Required exact bool; host projection entry remains default off |
| now_qpc_ns | Original uint63 host clock-domain now, no offset reset |
| pose, goal_m | Original own pose and legal goal, unchanged bounds |
| observation, history | Candidate and ordered selected original observations; never trim to fit |
| executed_actions | Original ordered STEP displacement records only |

Each observation exact keys: sample_id, counts, quality, adc_qpc_ns, em_qpc_ns, adc_pose, em_pose. Preserve counts/null/quality/held source timing and original native pose. Each action exact keys: action_id, from_pose, to_pose. Do not add fake at, synthetic integer-ms ticks, invented binding/BOOT or manufactured native equality. Full interval/cause/admission identity proofs and original action sequence live in the host association. Child can recheck public numeric/time/order/quality/duplicate/pairwise consistency, but those checks are deliberately not a second full proof validator or planner. C36's final field/nullability table and projection literal are frozen by the accompanying C36 public schema.

The actual candidate schema was read at C36-20261031/abi-design-v1/public-view.schema.json: sample_id is64 lowercase hex; counts are four 0..4095 integers or null; quality0..8191; original EM QPC and pose are explicitly nullable. Preserve null through the internal view and enforce its quality/count consistency; never create a timestamp or pose to fill it. Source-invalid quality returns the original C28 conservative STOP before its valid-EM age arithmetic. All nine compact top-level fields are required. Quaternion normalization and combined count budget remain semantic checks in addition to structural JSON schema.

## Exact single-core seam; a new JSON ABI

This is NOT the original C28 JSON ABI. Its legacy validator requires binding and integer millisecond/action.at fields which this new interval input cannot honestly supply. Literal use of recommend_json would be incompatible. The chosen seam is explicit and subject to implementation review:

* Verify the immutable original C28 bytes SHA256 70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4 on package load. Verify fixed C36 projection schema/adapter and runtime dependency pins. No optional plugin/import path.
* Copy the frozen recommend function globals into a new private dict. Replace exactly the `_validate` binding with the C37 compact-view validator. Create a private function from original recommend.__code__, this dict and original defaults/closure. Never mutate the original module or replace its numerical helpers/constants/builtins. No caller-supplied injection surface.
* The original recommended body uses copy, math, decode_counts, _risk, _clip, _poses_applicable, _norm, _rotate, _direction_supported and MAX_NATIVE_DIRECTION_ANGLE_DEG, with their original transitive dependencies/constants. Keep all unchanged and pinned. The custom validator returns the validated history+candidate observations; it does not rewrite risk/direction/STOP logic.
* Gate uint63 integer source age/order before constructing an internal view. Convert original absolute ns to Fraction(ns,1000000) only for now_tick_ms/adc_tick_ms/em_tick_ms computational keys. No rounding, offset removal, origin reset, inferred native equality or loss of1ns boundaries. Internal actions need only original from_pose/to_pose; no exact action.at is fabricated. Host has already checked the full actual interval/cause chain.
* Translate only output time representation back to exact original QPC ns; verify each restored value against the corresponding retained public input. No Fraction, pseudo-ms or private object may escape JSON. Original C28 decision/status/reason/quality/risk/uncertainty/direction/speed/map values and poses retain their semantics. This adapter's new JSON shape is explicitly separate from legacy recommend_json.

RESULT exact keys: abi, kind='RESULT', echo_ids, request_wire_sha256, status, core_ran, authority='none', completion_grant=false, result, reason. Preserve the complete bounded C28 candidate/STOP result under the new time representation; null result on package rejection. core_ran is truthful even on a post-compute output-budget failure. READY exact keys: abi, kind='READY', echo_ids, request_wire_sha256, core_sha256, authority='none'. READY payload <=2048 (the full bounded labels fit); RESULT <=16384; total output <=18440 including two 4-byte headers. Proposed recorder max_output_bytes=18440, max_reads=64, read_size=8192. ActorPolicy.output_limit<=8192 is its separate cleanup diagnostic bound and is not relaxed. Reject oversize output with a small OUTPUT_TOO_LARGE result, no partial map or fabricated STOP-success. Host expects exactly the correlated pair and terminal process evidence, no third frame/no arbitrary stdout.

## Clock and freshness contract

Source QPC integers and clock domain come only from original host_clock conversion/binding, retained in host proof. Projected now is original host-observed time, not a child-generated estimate. Child must never use wall clock, guessed offset/scaling, rounded milliseconds or a new origin. If child samples a compute timestamp, it must use the exact pinned original host_clock implementation/domain; that source/runtime dependency is not among the four authorized host files and remains an explicit integration gap. No custom conversion is specified. The first protocol needs no child timestamp field: actual host dispatch/read/completion brackets independently bound delay, and the original provider must check age/eligibility again before accepting completion. Projection-time freshness alone cannot authorize a delayed result. No child marker creates a sample/completion interval.

## Finite serial extension specification, not enabled

Future package protocol may accept a fixed launch count K in 1..16, strictly serial. Current implementation phase and original ActorOwner support only K=1; values>1 must refuse until A explicitly supplies and reviews append-only next-invocation ownership/API. No resetting `_invocation_claimed`, write_reserved, EOF, budgets or unknown state.

For a future approved K>1 path: each invocation has its own complete <=16384 wire request, exact sequence/invocation ID, original full-proof host association, request hash, independently bounded output/read/age/deadline and one reserved write. Host may issue next request only after previous full result bytes, actual transport settlement and original provider disposition are recorded; no pipeline or unsolicited output. Child starts no next inference before previous result is fully written, accepts strictly next invocation ID, and processes at most K requests before terminal exit. The host proves no early dispatch from its actual original call records; child cannot infer arrival time from buffered stream bytes. Each subsequent header determines its finite payload length; exact complete frame bytes are verified/retained by host before its original dispatch. No dynamic configuration or proof reuse across invocations. Unknown/short write, malformed response, timeout, broken stream, mismatched IDs, failed freshness or exceeded budget is terminal teardown, never replay or resynchronization. EOF/cancel after a settled invocation terminates; final K completion closes child and triggers A's actual original cleanup checks.

## Remaining exact freeze dependencies and test plan

C36 projection literal/table and the C37 seam are frozen by this interface delivery; runtime/code pins follow implementation. A must accept the N argument/native event convention and actual runtime dependency manifest; original host_clock bytes/domain support must be pinned before any child sampling. Main owns e794 host delta and C38 issue resolution. No runtime executable/dependency closure or current production-eligible dispatch is claimed.

NEW focused controls after separate implementation assignment: full-wire16384/16385 boundaries and strict frame splits/trailing data; correlated READY/result only; missing host evidence results in zero dispatch and host core0; valid synthetic projection makes child core1; original code-object identity and sole validator replacement; uint63 high-QPC100ms and1ns excess/native-equality distinctions; counts/null/held/time/pose preservation; defaultoff/contradiction rejection; oversized result truthful core flag; first count1/no EOF wait; future K>1 rejected on current API; fake serial state machine rejects pipeline/replay/unknown continuation. Each <=30s, offline fake-only, no old suites/native actor/model/board. These are planned controls, not pass claims.

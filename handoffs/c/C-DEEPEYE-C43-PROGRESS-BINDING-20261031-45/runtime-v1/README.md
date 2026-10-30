# C45 original progress observed-interval branch

This is an incremental candidate patch against exact A commit 42f3de654aef3d52300ae1cfb16e3ac512ea2cea. The actual source calls this path `_ProgressGate._admit`, not `_InferenceProgress.bind`. The patch also joins the two earlier scalar-only gates in `_CandidateOwner.offer` and `LatestCompletedMailbox.complete`; it is not another standalone schema adapter.

## Required apply order

1. Begin with exact A42f input source hashes in source-pins.json.
2. Apply the already published, unchanged C43 `completion-interval-successor.patch`, SHA256 37f6b42d5d7a662a86d1e787b63896ae36ab0fee868fc0ef48c65ea6ba4fb22d. This installs C43's host-envelope opt-in plus completion_interval.py/schema. If already applied, verify its resulting hashes instead of applying twice.
3. Apply this C45 `c45-progress-binding.patch`. It modifies only actor_composition.py, candidate_owner.py and candidate_mailbox.py. This C45 patch does NOT include or replace C43 files. The complete three patched files are also supplied under patched/. No new package/type aliases or silent dependency replacement is involved.

C43 runtime remains 05da98393d47f3eaf4690d8979d2e37d2e4f1e0b00c801177a3fb6a3f84bbe96 and its patched host remains 20b2221491825964f91381f68053a13bf3867347d35896ce1dd132c4a8972c3b. C43 schema bytes remain unchanged, recorded in source-pins.json.

## Caller and source contract

The original trusted configuration adds `enable_completion_interval_v2=False`. Both original factories require a strict bool. accept_boot passes that explicit flag to the original progress gate and candidate owner, which passes it into mailbox activation. No message document selects the branch. Defaults retain the scalar/v1 calls, existing positional construction, and no C43 interval import through the new branch.

The original A `channels.verify_completion(event, boot)` must return its exact original `_CompletedInference` with a trailing `observed_interval_v2` value. The default is None. When explicitly enabled, that value is an exact frozen `candidate_mailbox.ObservedIntervalBoundsV2(max_age_ns, source_deadline_ns, dispatch_deadline_ns, previous_deadline_ns)` from the same package. This is a correlation record, not a credential or independent source authentication. A's original production factory/source verifier is still responsible for provenance and actual same-clock facts; no new provider factory or bypass is installed here.

- `max_age_ns` must equal original config.progress_max_age_ns and be 1..100000000.
- `source_deadline_ns` must be the original independently established source lifetime cap. At mailbox completion it must also not exceed the retained observation's original sample_lower_ns plus the existing profile _age_cap (fast_9600:1500ms, stress_300:12000ms). An unknown original sample lower rejects. This further upper bound does not create the missing source credential.
- `dispatch_deadline_ns` must be retained by the original dispatch/verifier. A42f's old _CompletedInference has no independent field supplying it. This new API requires the real value; it cannot be derived from initial_deadline, process survival, RESULT read end or dispatch+age and relabelled as an independent cap.
- `previous_deadline_ns` is explicitly None or a retained deadline applicable to this same inference/action. It is not implicitly taken from a different previous invocation's gate bound. Provider provenance remains A-owned.

The candidate's uint63 interval lower equals the exact original dispatch_lower_ns; upper equals the original completion_upper_ns after all RESULT bytes are observed. Original completion_lower_ns remains the real read/observation lower, and may be strictly greater than dispatch. It is never overwritten. The order is started<=dispatch<=completion_lower<=completion_upper<=issue<=now. Fixed basis is host_dispatch_to_complete_result_observed_v1. No completed_monotonic_ns is fabricated.

The exclusive expiry is min(dispatch+max_age, original source cap, original dispatch cap, explicit previous cap if present). C43 checks overflow and now<deadline. Mailbox requires its projected deadline to equal that exact result. The progress gate uses that result without adding to read lower. Source/clock/boot object identity, model hash, request/candidate/observation/target equality and original host issue ordering remain enforced. Missing caps reject rather than obtaining defaults.

The full immutable bounds record is included in mailbox duplicate fingerprint and final bound-progress equality, even when a changed cap would coincidentally yield the same minimum. Exact duplicate bytes/proof/bounds cannot renew or reinstall pending after consumption. Fresh seq/candidate/invocation still may advance its deadline under the original behavior; there is no activation-wide 100ms clamp added. Initial progress timeout, monotonic high-water, revocation, replay protection and all final lifetime fences remain.

## Evidence and limits

run01 uses exact original A pure blocks against a new interval candidate: it fails at the first owner host schema gate (schema_version2 rejected as v1), preserving the real reachable blocker. run02 passes eight new affected-branch tests, including the real pure method sequence offer -> mailbox.complete -> consume_pc_direct_v2/select -> progress.admit -> commit -> duplicate. It proves dispatch<readlower remains accepted, expiry comes from dispatch, default v1 keeps lower+age, original caps clip and missing caps reject, exact endpoints/basis are required, duplicate cap changes reject, and fresh invocation can advance. run03 adds only the necessary mailbox cap-fingerprint and unknown sample-lower edges; it passes without replaying run02. Nine distinct new methods have passing evidence. Each run is bounded at30seconds and retains stdout/stderr/exit and exact source versions.

Tests extract finite original/patched AST blocks into isolated synthetic namespaces, initialize explicit fake owner/activation/observation dependencies, and call the unchanged C43 host validator. They do not import or activate A's original actor/native factory, model/PDE/C28 or board. They do not prove provider/package authentication; runtime exact-type/source/clock checks still require the genuine original process. No old suite is replayed.

run04's static AST audit verifies exactly the allowed changed blocks: thirteen original blocks changed and two new definitions; all remaining original methods/functions are unchanged. In particular select, commit, duplicate_proof, progress.observe_time/admit/deadline_for, entry/retirement/lease/runtime/command/step fences and mailbox consume/window scheduling are not changed. The explicit flag wiring in accept_boot is the only ActorComposition method change.

A must still wire and independently validate the real completion provider, caps and RESULT observations. This delivery grants no movement, native readiness, production integration, physical-board measurement or formal acceptance. H01-H15 and fixed contract/design remain unchanged; A alone operates the physical board.

# C45 independent review

Decision: source approved for the default-off completion-interval binding candidate, with no open source finding. Incremental patch SHA256 `49cbf4c63e2c02c41525fc1e4557bf876d715c5cf2d184cc6629e7b4e6f59a31`; author FINAL `70138fd56f34eb83aef3a9ad2924d867b04632f37e5368906eff4de2bde73cbf`. Actual provider cap provenance, original factory integration and native operation remain unverified and A-owned.

## Exact source and reachable path

Read and verified authenticated A43 comment6533070672 and fixed main decisions. The exact A42f implementation is named `_ProgressGate._admit`, rather than the name used in the message. The patch connects `_CandidateOwner.offer` → `LatestCompletedMailbox.complete` → original selection/progress admission. It is not merely a disconnected validator helper. It requires frozen C43 patch37f6b42d first, then this three-file delta; C43 host/runtime/schema pins are unchanged.

Verified 79 artifact/source evidence entries before and after, including original and patched three-source hashes, dependency pins, versioned raw logs and original RED. Independently compared AST blocks: exactly thirteen existing blocks change and two definitions are added. Unchanged blocks include mailbox selection/consumption/window scheduling, candidate selection/commit/duplicate_proof, progress high-water/admit/revoke/deadline methods, original runtime/lease/step/command/final fences and production provider rejection. Only accept_boot changes among ActorComposition methods, to pass the explicit flag. Patch hunk reconstruction is checked against the supplied original/patched source texts; no Git application or deployment occurred.

## Binding and timing review

The trusted config, owner, mailbox activation and gate use a strict bool flag defaulting false. New fields are trailing default-None records and keyword-only controls, preserving prior positional construction. With the flag false, the original scalar calls/order/deadline computation remain; a nonnull new bounds attachment is explicitly rejected. The new branch calls the unchanged C43 opt-in validator and never invents a scalar CPU-finish timestamp.

`ObservedIntervalBoundsV2` must be the exact frozen record type in the same package. The progress age must equal the original configured age and lie within1..100000000. Missing/boolean/out-of-range source/dispatch/previous bounds are rejected rather than derived from gate initial_deadline, arrival, process lifetime or read upper. Actual source/boot/clock association and `_CompletedInference` exact type checks remain at the original owner and progress boundaries. Record construction and labels still are not authentication.

Candidate interval lower is compared exactly to retained dispatch_lower; upper exactly to retained complete-RESULT observation upper. The real read/observation lower remains independent and may be later than dispatch. The order started<=dispatch<=read_lower<=read_upper<=issue<=now remains. Deadline is the C43 minimum of dispatch+age, original source/dispatch and supplied previous caps, with integer overflow and exclusive expiry checks. Mailbox requires the record deadline to equal that exact result. Retained observation sample_lower must exist; its existing profile age bound can only constrain the original source cap. A cap above that bound is rejected, even when another cap would already produce an earlier minimum.

The full new bounds record participates in both mailbox fingerprint and bound-progress equality. Thus a changed nonbinding cap cannot masquerade as an identical duplicate. Exact duplicates do not renew; fresh strictly progressing sequence/candidate/invocation may advance the current deadline while the original gate is still live. Original high-water, irreversible expiry/revocation and replay checks prevent a new candidate from reviving an already retired activation. No unrelated previous gate deadline is imposed as an activation-wide permanent cap.

## Minimal independent checks

Three NEW controls passed in one25second-bounded process, actual0.500s, exit **0**, stderr empty. The portable script accepts C45 implementation, frozen C43 implementation and output directories. It defines new synthetic data and compiles only selected pure original/patched AST definitions in isolated namespaces with explicit fake dependencies; no original actor/factory imports or activation, old tests, author fixture import, model, C28/core, native handles or board occurred. C43 host validation and its pinned private vendor were used read-only.

- With source_cap exactly equal to sample_lower+1500ms, the original owner/mailbox/progress path accepts and retains read_lower strictly later than dispatch. With source_cap one nanosecond larger, mailbox refuses and halts even though the dispatch cap is earlier and would otherwise decide validity.
- A fresh distinct observation/candidate/invocation advances an unexpired gate from50ms to80ms. An exact duplicate leaves80ms unchanged. Changing only a nonbinding source cap on that duplicate is refused and revokes progress.
- A subclass lookalike of the new bounds record is refused by both owner and progress; no pending proof is installed and progress is revoked. This tests exact-type consistency, not authentication.

Executed script, exact generated candidate/cap parameters, observed results, hashes, command, stdout/stderr and exit are retained. Author's complete new branch suite was not rerun. Unchanged selection/commit behavior was assessed statically and from the author's actual source-pinned run, not claimed as independently re-executed here.

## Versioned evidence and remaining work

Author raw exits [1,0,0,0] remain intact. Baseline RED uses a newly constructed interval input against original A pure blocks: it reaches the original owner and fails because schema_version2 is not v1. Run02 passes eight new methods; run03 adds one mailbox-edge method; run04 is a static audit. Nine distinct methods have passing evidence across runs, not an independent/full-suite rerun. No failed result was relabeled.

A's original verify_completion and factory must still supply genuine retained source/dispatch/previous caps under original source/boot/clock identity and original RESULT observation. Existing production unavailability/authentication gates remain; this patch cannot supply missing facts or admit a provider by JSON. No auto-registration, BOOT/motion/completion grant, native readiness or formal acceptance follows. H01–H15/original29/bothH12/final100MHz/timing/1%/100ms and A-only physical-board authority remain unchanged.

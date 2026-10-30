# C34 independent implementation review — one blocking finding

**Source approval: false.** Frozen runtime `f913c3f0d9188dc9f8d04e6f360061c081cd34da2d0dea57a61170e845333bbd` has one P2 missing-path namespace defect, reproduced by three NEW inputs. The other 35 NEW controls passed. No public or frozen source was changed.

Reviewer `/root/c28_independent_review`, actual thread `01a18686-39ad-75d3-8bb4-90836d2ac026`; work `C34-INDEPENDENT-COMPOSITION-IMPLEMENTATION-REVIEW-v1`. Only this review directory was written. Main retains final disposition and publication.

## C34-R1 — contradictory original raw namespaces are hidden by missing outer evidence

In `root_book_stale_composition_v1.py`, `_crosschecks` lines **467–472** builds namespace evidence only from candidates, binding, config, current metadata and action registry. When those are absent, `namespace=None`. `_raw_intrinsics` lines **406–413** then does not compare supplied raw contexts/generation against a shared namespace. `_record_counter_consistency` line **455** groups separate context/generation values instead of rejecting their conflict. The request returns INPUT_UNAVAILABLE at lines **830–840** without entering C32.

Each of the following NEW inputs has no candidate/history/config/binding/book/current/registry. It contains two actual synthetic retained raw records, with individually valid shape/hash/sequence/time/counter relationships. No identity, config or current candidate was invented for the validation call.

| Exact input | Bytes | SHA256 | Required | Actual |
|---|---:|---|---|---|
| `new_request_only_conflicting_sessions.input.json` |2754|`31e1c49dc96da36586cf0717fcf7843019b5a589298068e737b02390a0f2d6a5`|Rejected|INPUT_UNAVAILABLE|
| `new_capture_only_conflicting_sessions.input.json` |3909|`4401b8de60b0aa8b4a8f19b320512601ddc9ddba1db51ad35de77d67701cc897`|Rejected|INPUT_UNAVAILABLE|
| `new_capture_only_conflicting_generations.input.json` |4075|`b0dcb9abf6bc8ec18efc980440b5703f36aefa7a2e9dde72df0fab4211323094`|Rejected|INPUT_UNAVAILABLE|

The first two use distinct original session strings; the third uses identical context but different actual capture generations, updating corresponding raw identity words so this is not a per-record identity-word error. All three return the same 971-byte unavailable output, SHA256 `2b6ceba2fa8b35a6f06bd1c521986c3d46707c0af087487d8fdce90d39c215b4`. Each records zero C32 JSON calls and zero core calls. That prevents execution, but does not satisfy the interface's requirement to reject known contradictions before unavailable.

The contradiction is already decidable: a future complete C32 request requires a single full context/generation for retained candidates (`_time_metadata`, C32 lines 619–623), and each supplied raw request/capture must agree with the candidate context and capture generation. No completion can reconcile two conflicting retained raw contexts or two capture generations in that one association namespace. The lack of an outer anchor does not erase these original operands.

**Minimal repair:** collect and compare the full actual `context` from every supplied request/capture raw line, and actual `generation` from each supplied capture, together with all existing outer sources. A request raw line has no generation; do not fill one. Compare independently available fields before missing/default/stale exits. Once equal, shared-baseline checking can retain the current arithmetic. Do not manufacture a config/candidate, discard a supplied record, choose the first foreign namespace as authority, or broaden this into a generic validator rewrite. Closure should replay only these three exact originals and a few adjacent same-namespace/mixed-raw/known-generation controls, not rerun this 38-case matrix.

## Static review and design gates

All five assigned public pins matched. Independently regenerated the published C31-to-C34 diff and verified exact equality. After mechanical `_C30`/C31/result-label renaming, only `_raw_intrinsics`, `_crosschecks` and `project` change; `_record_counter_consistency` and `inspect_retired_source70` are new. Seventeen inherited functions have identical ASTs after those mechanical substitutions, including actual temporal revision lower bounds, book/projection checks, tree/parser and supplied admissions/raw checks. Frozen C28/C30/C31/C32 hashes match before and after review.

The three design gates are visibly implemented: code-contract54e1 remains separate from runtime4dc91; raw-only shared counter feasibility is present and independently passes a valid pair/rejects incompatible counters; the separate exact archive entry creates no now/IDs/projection. These do not waive R1.

The final raw-only changes correctly enforce positive request sequence, ordered original request QPC through now, positive capture generation, capture word sequence/tag/trigger/generation/channel relations and original capture QPC through now. NEW independent sequence0/future+1/trigger-word cases reject. Actual author raw failures and their original versioned fixes were read, not rerun.

Candidate present causes exactly one C32 JSON call. Stage1 missing forces only this call disabled and preserves null projection/result. Actual null captures remain null, whereas a supplied empty association list conflicts with a real candidate. Missing-current path does not promote history or invent a candidate. Original-data temporal checks still reject a known current-pose conflict despite a missing receipt ID. Config generation positivity and actual history/config anchor disagreement are checked with no current candidate. All of these controls passed.

The loader creates one C32 module and one C28 module through fixed paths/hashes; no C30 or frozen C31 module executes. Fresh native/held calls reach exactly the original C28 code object once, through one C32 JSON call. Default-off/missing/stale/invalid inputs do not enter it. Original globals identities remain stable across calls. Held output retains the original native EM receipt exactly.

## Actual NEW execution

One subprocess invocation, 30-second timeout: **exit 1**, **5.282 seconds**, **38 cases / 35 PASS / 3 product RED**, stdout **14543 bytes**, stderr **0 bytes**. `run01.command.json`, `run01.stdout`, `run01.stderr`, `run01.exit.json` are original process evidence. No candidate rerun followed the finding.

Passing controls cover final-version complete native/held/default-off; real-candidate missing book/null versus empty captures; stale plus later malformed prefix despite missing book/config; partial current conflict; history/config anchor conflict; config generation0; raw-only counter validity/conflict; final raw sequence/time/identity repairs; exact above2^53 now/capture/admission ages100000000 ns versus100000001 ns; actual32 versus33 receipt arrays; initial1001 versus1002 prefix and original10-second window; duplicate JSON keys, wrong-path array exceptions, input byte cap; aggregate output cap; contract/runtime label separation; exact original archive and changed-byte rejection.

The aggregate positive fixture has 473767-byte input and 809687-byte output. Its padded counterpart has 941281-byte input (below1MiB) and is rejected specifically at `C34 encoded output budget` after one C32 call, with zero core calls. This checks aggregate output rather than only input or individual components. Other unchanged strict tree/node/depth predicates were reviewed statically; the new matrix does not claim exhaustive coverage of every cap combination.

The original archive was SHA-verified and passed unchanged; its result contains no now/candidate/config/registry/owner fields and makes zero C32/core calls. It remains schema1, numerical-only and unavailable. No source kernel/model/native/Root/board was imported or run.

## Preserved evidence and reproducibility

```text
python -B independent_c34_checks.py PUBLIC_DIR OUTPUT_DIR SOURCE70_JSON
```

The portable script uses sibling `independent_fixtures.py` and `independent-fixture-data.json`. The latter is retained synthetic JSON data, explicitly labeled and pinned; no author or old test/fixture module is imported. New inputs are independently constructed, including distinct goal/current-time values and new raw-only sequences/baselines. All 38 exact input/output UTF8 strings and hashes are retained losslessly in private `run01-input-output.jsonl.gz` (515892 bytes). Failed input bytes and observed JSON are also saved individually; `original-red-inputs.json` supplies a small flat exact-byte bundle for closure/public evidence. No failure was rewritten.

For publication budget, prefer the portable scripts/data, compact actual stdout/results, this report and the three original RED inputs/bundle. The full 515892-byte journal can remain private; do not describe a smaller derived result list as the full input/output journal. Source/diff/author evidence summaries are static read evidence, not new author execution.

Author run exits were independently read as `[0,1,0,1,0,1,0,0,1,0]` with their source/test snapshot hashes. Run02/run04 failures are recorded test expectation/fixture issues; run06/run09 contain actual missing-path product failures; their original versions remain intact. Earlier author PASS groups are not relabelled as final-version reruns. This independent matrix is new final-version evidence, not replacement for any old failure/pass.

No additional exploration or broad replay is needed before the narrow R1 repair. This review does not authorize action/native/physical acceptance. H01–H15, both H12, original29 and final1%/100ms remain unchanged. All work stops and ownership is released in FINAL; jobs/subprocesses are empty.

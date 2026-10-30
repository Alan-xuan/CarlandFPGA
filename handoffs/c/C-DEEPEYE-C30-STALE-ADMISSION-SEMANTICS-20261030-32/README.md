# C32 legal stale admission semantics

New ABI `private_raw4_time_association_v2` fixes the classification of a structurally legal source admission received more than 100 ms after its original nominal source time. After every supplied, decidable consistency check completes, it returns `INPUT_UNAVAILABLE`, `STOP`, `core_ran: false`. Disabled requests remain `DISABLED` after the same validation. Negative age, future events, identity conflicts, malformed data and budget violations remain `Rejected`.

This operation leaves frozen C30/C29/C28 and their earlier failures unchanged. C30 baseline SHA is `abaa06d10ab68f0bee721bf1a6d9278fc000446112ac559362079ad63afc686d`; `baseline-to-candidate.diff` is the exact unified runtime diff. C31's separately pinned dependency is not redirected. `abi-contract.json` contains the full retained field tables and the new validation order.

## Behavior and validation order

C30 combined negative age and freshness upper bound in `_admissions` as a single structural assertion. A legal late admission therefore raised `Rejected`, including disabled requests. Simply changing that assertion to an unavailable exception would hide malformed later prefix records, raw identities or actions. An earlier missing-config exception could also hide independently verifiable supplied facts.

C32 refactors the existing association pass once. `_admissions` traverses the whole original prefix, rejects negative age and inconsistent ordering/quality/provenance, and accumulates a stale flag for an upper-bound excess. `_association` records absent required evidence while continuing rules whose actual operands are present. It does not fill missing fields or manufacture a complete Root/config. `_returned` checks each supplied raw line independently against the original candidate, so missing one line cannot hide conflicts in the other. There is no second complete validator or second planner.

Only after the supplied facts have been checked does classification occur:

1. Disabled: bounded `DISABLED` / `STOP` / `core_ran: false`.
2. Missing original evidence or sufficient proven coverage: bounded `INPUT_UNAVAILABLE` / `STOP` / `core_ran: false`.
3. Otherwise legal stale: bounded `INPUT_UNAVAILABLE` / `STOP` / `core_ran: false` with an original-source-age reason.
4. Complete, fresh evidence: invoke the frozen C28 code object once.

No `Rejected` exception is caught and relabeled. Missing evidence takes precedence over stale in enabled output, so an incomplete association is not described as complete merely because its age can be measured.

## What missing evidence can and cannot defer

The original candidate always supplies source and transport identity. All retained candidates must agree on the original source-start tick/QPC pair; any supplied config must match it. That actual `source_time` supplies an explicit anchor for prefix validation even if config is absent. No substitute config, baseline counter or trigger identity is created.

Supplied raw request/capture context, hashes, values, qualities, original injection words, tag, sequence, generation and trigger are checked against the candidate independently. Absolute counter comparisons to the original baseline and initial trigger progression require actual config; their internal consistency does not. Within each supplied raw capture, first and second lane counters must agree, third counters increase exactly1 per lane, and final counters equal the last lane. For request sequence `s`, the first lane must satisfy `[c0,c1,c2] >= [4*s,s,4*(s-1)+1]` componentwise, so a nonnegative original baseline could exist. Between supplied raw captures separated by actual sequence difference `d`, the same-channel increments must be `[4*d,d,4*d]`; missing intermediate raw captures do not reset this check. These equations prove only consistency, never the missing baseline's provenance. No derived value becomes config, identity, output evidence or permission to run the core. Actual config checks remain mandatory when supplied. If config exists but capture receipts are missing, candidate/config trigger progression is still checked. Candidate/admission count, quality, tick and received-time equality is also checked independently of capture-receipt presence; a supplied receipt additionally binds the original source-record hash.

Missing read/span/revision, a legal absent admission tail, missing current pose or a missing execution receipt records an evidence gap. It cannot suppress supplied reversed intervals, raw/hash mismatches, duplicate action identities, known observation-to-action/cause timing, or other independently decidable conflicts. Absent values are not considered equal evidence; only supplied counterparts can be compared. Root absence itself leaves independent envelope/candidate checks, not a fabricated Root object.

Actual initial-counter or original-execution facts cannot be verified without their real receipts. Their absence still prevents the core. The implementation does not infer an empty action registry, original pose validity, ownership, completion, healthy C3 or missing native capture.

## Original time and core remain unchanged

Every QPC and revision remains a strict uint63 integer. Admission age is the original admission-received QPC minus that sample's original nominal QPC. It is not current time minus every old prefix sample. All supplied admissions are checked, including an older stale admission when the newest candidate is fresh. Capture-receiver and current-now source-age gates remain separate.

Exactly `100000000` ns is permitted; `100000001` ns is stale. No float conversion, millisecond truncation, reset origin or rewritten received time is used by the adapter. For an inclusive positive boundary fixture, admission, all four injections, receiver and now may legitimately coincide; adding transport delay can independently cross a later freshness gate.

The Root kind remains `c30_root_time_association_v1`. Its original closed pose-validity span, actual pose-read/ADC-call brackets, native/held original receipt and committed revision rules are unchanged. Held EM uses its original native call and pose, not a later held call or current pose. Executed action time still means the original Root completion/commit point; no movement duration is inferred. Missing nullable proof remains missing even if another receipt supplies a numerical counterpart.

The fixed sibling C28 source hash remains `70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4`. Initialization reads and verifies that exact known local dependency; mismatch fails closed. Public recommendation calls have no I/O. The same `recommend.__code__` executes with per-call private globals changing only the strict validation seam. Original module globals stay unchanged. Its absolute `Fraction(QPC,1000000)` view is private; outputs preserve exact integer QPC and original context. The original 0.25 m / 15° pairwise support, 30° native cone, roll support, quality behavior and goal-sensitive 3D algorithm are not revised.

Default enablement is false; `diagnostic_only` is true and authorization is `none`. Root receipt strings/JSON establish structural consistency, not actual source authentication or control authority.

## Resource and identity contract

Complete operation/request/tested commit/build manifest/kernel boot string/session/tag/generation/source/capture identities are retained. No protocol BOOT, epoch or topology is invented. Root/context fields remain closed whitelists.

Input and output each cap at 1048576 bytes, with 65536 nodes and depth16. Only the exact `root_receipt.source_admissions` path permits1001 records, preserving original indices0..1000 and the original ten-second model window. Other arrays cap32. The pre-return bound remains `max(retained candidate count, supplied Root capture count) + supplied actions <=32`, including missing and disabled paths; the later association bound also remains. Null contributes zero supplied items to budgeting only. Ordinary strings/object fields/raw-line limits and strict duplicate-key/nonfinite checks remain as in the contract. Every returned result passes the output budget check.

## New local evidence

Only new C32 controls were run; no old C28/C29/C30 suite or old suite entrypoint was invoked. Six fixture-construction functions were copied as source into the new test file; that does not import the old suite.

`run01-baseline-red` called frozen C30 exactly once. A synthetic native admission at100 ms +1 ns, with high original QPC `36028797018964091`, returned `Rejected: source admission original age`; child exit1 and original input/raw logs/source snapshot are preserved. Input SHA is `eb6c254e77a0ced596bf2996ebc3d7dee97477aa20074001d11c55d78d938f7c`.

`run02-new-controls` ran53 new focused cases in one bounded30s process, exit0 in0.883s. They include native ADC and held original-EM exact100ms/+1ns, enabled/disabled/missing combinations, stale-plus-known-malformed cases, earlier stale prefix followed by later faults, independent raw-line validation, source/candidate/trigger relationships, held original evidence, action timing/duplicates, source1001/1002 and selected resource limits. Runtime profiling observed the exact original C28 code object once for complete fresh outcomes and zero times for stale/missing/disabled/rejected outcomes; request and original globals stayed unchanged. Exact inputs/outputs, hashes and compact raw report are retained privately for main review.

The original RED input matches the passing candidate stale case after **only** the explicit ABI identifier change; the candidate returns unavailable/corefalse. This is synthetic diagnostic evidence, not A's real source request. A's observed473319100 ns remains an actual age fact with incomplete real integration evidence; it is not claimed as a complete request reproduced here. No actual Root, board, engine or full-chain execution occurred. Main independently reviews the frozen files before publication.

## C32-R1 counter repair v2 evidence

Independent review of initial C32 runtime `30466fc69099112010c72cdaec7c097ce38c0b43a1307a6f18ad4c58390e6f77` found four real RED cases: supplied lane/final counters could contradict each other while config was missing, yet the result was unavailable or disabled. That version was not approved. Its complete five-file bytes and all four original input/output/exception records remain preserved. The failure established the missing internal feasibility checks described above; it did not run the core or grant control authority.

The narrow repair changes only `_returned` and `_association` in the runtime. New `test_counter_consistency_v2.py` ran27 targeted synthetic cases, exit0 in0.518s under a30s timeout. Coverage includes second-lane equality, third-lane increments, final equality, each negative-baseline impossibility, zero/high-uint32 feasible boundaries, actual-config mismatch, sequence1→5 increments, each cross-capture counter component, missing middle raw capture and missing request line. Missing config stays unavailable after all equations pass; complete fresh positive controls still use the same C28 code object once. Original candidate/Root data and globals remain unchanged.

The author did not replay the original four independent RED inputs or rerun53/35/old suites; independent follow-up owns that exact replay. `test_stale_admission_v2.py` remains byte-identical to the initial C32 freeze. Prior53-case evidence applies to its earlier runtime version; it is not claimed as a repair-v2 rerun. Exact new raw logs, source pins and narrow v1→v2 diff accompany the private handoff; the public `baseline-to-candidate.diff` still compares the final runtime to immutable C30.

DEEPEYE-HUMAN-LOCK-20261014 revision1, source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, fixed design `1011259415a0916054eb580687612580bc1e5f09`: H01–H15, both H12 modes, source100ms and original final1%100ms requirements remain unchanged. Formal acceptance remains false.

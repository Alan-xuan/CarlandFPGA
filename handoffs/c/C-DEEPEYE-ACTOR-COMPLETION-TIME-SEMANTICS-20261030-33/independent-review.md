# C33 v2 narrow provenance correction review

**Passed; no open findings in this correction.** Reviewer `/root/c28_independent_review`, actual thread `01a18686-39ad-75d3-8bb4-90836d2ac026`, work `C33-INDEPENDENT-PROVENANCE-CORRECTION-REVIEW-v2`. Only `review/provenance-v2` was written. No public, author, frozen dependency or previous evidence was modified.

## Correction of the previous review

My v1 conclusion that source70 runtime4dc91 versus C31 contract54e1 alone establishes incompatibility was too strong; it is withdrawn. The actual book-code bytes are identical. Likewise, C31's fixed-binding restriction limits a future moving bridge; it is not itself missing evidence in this static revision0 sample. Removing these two reasons from `missing_codes` is justified. This is a source/provenance semantics correction, not an old product-test RED. All v1 code, reports and actual five-author/six-independent PASS records retain their original version and scope; they were not rerun or relabelled as v2 coverage.

## Independent retained-source verification

Read both original immutable GET command records and raw responses. Both recorded exit 0 with empty stderr. For each, independently decoded the base64 response and compared every byte to the retained `.py` file; checked the exact requested commit, repository path, response size and response blob; recomputed SHA256 and Git blob SHA1 using `blob <length>\0<bytes>`. Both sources are **25692 B**, SHA256 `624c84f8de949c7c078ca0b7afa84c295804d7bc881527e9b91c38ba645004ef`, Git blob `be584260af61fa6bd4800914e3dd37323e734bf8`, and byte-identical. No fresh GET, Git command or source execution was performed by this reviewer.

C31 runtime line 14 defines `BOOK_SOURCE_COMMIT=54e1...`; lines 698–702 validate the external envelope's `book_source_commit` against that pinned code contract. `_book_shape` lines 145–264 validates schema1 book facts separately. The original book's `evidence()` around line 490 emits schema1, spans/read samples and explicit numerical-only limits, without embedding a whole-runtime source commit. Source70's top-level `source_commit=4dc91...` records the actual run and remains unchanged. An independently verified statement that this run used the identical book-code contract can coexist with that runtime label. Sending 4dc91 as C31's contract field would still fail its literal guard, but this does not establish semantic incompatibility of the identical book implementation.

Equality of this one source file does not establish identity of the whole repositories, dependency closure, actual caller execution, owner authentication, missing receipts or a complete acceptable C31 request. No substitute C31 request, fake contract proof, new admission/opaque identity, or projection was constructed. Frozen C31 was read and hash-verified, never executed. The later scoped-EM schema2 work is separate and not enabled by this finding.

## Narrow change and execution

Verified all six assigned v2 pins. Comparing the full runtime bytes to retained v1 yields exactly three literal edits: remove `frozen_c31_source_version_incompatible`; remove `frozen_c31_fixed_binding_only`; change diagnostic kind from `single_pinned_retired_source70_v1` to `single_pinned_retired_source70_v2`. No input gate, parser, arithmetic, original rows, summary, projection or execution path changed. The document diff corrects the same distinction and adds the checked provenance record; the copied C30/C31 fields and completion/closed-span/held semantics remain unchanged.

One bounded NEW narrow run: **3/3 passed, exit 0, 0.188 seconds, stdout 923 B, stderr 0 B**, 30-second subprocess timeout. The script loads only current C33 code and retained v1 output as data, not v1 code or either old suite.

- Current output equals the retained actual v1 output after exactly the kind change and two code removals. Every other field, including all original rows, values, times, identities, quality and summary, is unchanged.
- The eight actual missing/retired reasons remain. Result is INPUT_UNAVAILABLE/STOP, authorization none, projection null, C30/C31/core false, and native interval atomic false.
- New provenance JSON and contract agree; code-contract54e1 and actual runtime4dc91 remain distinct. Completion-observed-to-C30 mapping is still null. Source70 remains original schema1 bytes.

Actual v2 output: **11282 B**, SHA256 `972fa8d75d6faef2c1746a94832bdd6c11668f25f750cd25a24f8c7d1a36daf5`. Retained actual v1 baseline: **11355 B**, SHA256 `7564f32602731a19d279b8eae841bf8173681d878f56ae239721673e1351a3e6`. Neither baseline nor original input was regenerated.

## Reproduction and limits

```text
python -B independent_c33_provenance_checks.py PUBLIC_DIR v1-actual-diagnostic.json OUTPUT_DIR
```

The standard-library script is portable, accepts the public directory, and verifies runtime/input/baseline hashes before the single current diagnostic call. Keep `v1-actual-diagnostic.json` as the exact baseline artifact alongside the script. `run01.command.json`, `run01.stdout`, `run01.stderr`, `run01.exit.json`, `actual-diagnostic-v2.json`, `narrow-results.json` preserve this run. `provenance-verification.json` and source pin inventories preserve the independent retained-GET comparison. Original read/verification tool responses are retained separately.

No original five/six tests, old planner suite, source kernel, model, live Root, service or physical board ran. This narrow review does not establish general validator coverage, runtime authority, current freshness, native/physical acquisition, complete C31 compatibility or formal acceptance. H01–H15/both H12/original29/final 1% and 100 ms remain unchanged. Parent owns publication. Ownership is released in FINAL with no jobs or subprocesses.

# C42-R1 independent follow-up

Decision: C42-R1 CLOSED for runtime `b49169ac2ab87073e31406d8448d69c7958d5e5775310f94990fe89eee8d3722`. Source approved within the assembly-completeness scope; no open finding in this repair review. This is not C36 semantic validation, source authentication, native/live integration approval, or a dispatch grant.

## Scope and source evidence

Reviewed exact implementation-v1 → repair-v1 → repair-v2 deltas, the field-specific documentation amendments, frozen C36 `_receipt`/`_captures` requirements (host_projection.py lines 440–515), and version-specific repair raw logs. Verified 34 repair artifact/FINAL pins before and after. C36 runtime/schema hashes remain `7defaee9318f9a33a0586628661d054c028b5952584030ebc3b771a479a8982e` / `ab1b432e9f337523fd75057fec4647f5eda2569de308e7c777507e05907bdd70`.

AST comparison: first repair changes only `assemble_snapshot` and `Producer._capture`; second adds `_capture_availability` (and its nested helpers) and invokes it from `assemble_snapshot`. Original-object registry binding, getter ordering, Fraction conversion, projection and clock handling are unchanged. Null original wires now remain representable for unavailable output; nonnull non-string wires still reject. Config book/owner IDs and original wire fields are explicitly required. ADC call/root/pose and sample associations are checked after projection. Conditional EM attachment requirements apply to every supplied candidate/history observation associated by capture digest; matching labels alone are not authentication. Missing or ambiguous targets cannot be chosen by array order. Empty admission prefix and missing selected captures are unavailable. Legitimate no-EM nulls remain possible; unchanged kind-aware receipt scanning still exempts BOOT's absent command receipt. BOOT was statically checked, not newly executed.

## Actual independent execution

`independent_followup_checks.py ADAPTER_DIR ORIGINAL_FIVE_BUNDLE OUTPUT_DIR` imports only the repaired C42 assembler. `original-five-inputs.json` retains exact original UTF-8 strings, lengths and hashes; the runner verifies them before parsing. One process, timeout 25 seconds, actual 0.188 seconds, exit **0**, stderr empty. Ten checks passed: five explicitly authorized affected regressions and five new adjacent checks. No author suite or unrelated old group was rerun.

The original complete input still yields ASSEMBLED_UNVALIDATED with a nonnull proof and no missing paths. The four original null book-ID / owner-ID / request-wire / capture-wire inputs now yield INPUT_UNAVAILABLE, proof=None and the precise missing path. Their input hashes are byte-identical to original review-v1 evidence; old RED outputs remain untouched.

New checks cover simultaneous independent ADC call/root/read nulls; empty admission prefix and capture array; a null original EM nested call; an EM-requiring history observation despite a candidate with null EM time; and a legitimate no-EM null attachment positive. Each checks input immutability, exact integer source-origin preservation above 2^53, false core/authentication/dispatch flags, status/proof/missing-path behavior. The history/candidate conflicting-EM fixture is intentionally an availability probe, not a valid C36 semantic input. Both synthetic positives demonstrate reachable mechanical assembly only. They are not genuine A evidence or downstream C36 acceptance.

Exact commands, exit, stdout/stderr and all ten input/output byte files are retained. No C36, C28, original A runtime, native process/handle, model, PDE, physical board, peer message, Git or publication operation was performed.

## Author evidence attribution

Author repair-v1 raw exits are [1, 0], with version-pinned source. Repair-v2 exits are [1, 1, 0]: the first run preserves 19 failing subcases; the separate empty-prefix run preserves its failure; final run03 on b49169ac passed eight methods and their subcases. Those are author evidence, read but not rerun by this reviewer. The first failing assertion in the earlier association method prevented its later branches, which are not claimed as separate baseline failures. Earlier original implementation tests are not relabeled as final-source passes.

## Remaining boundary

The new helper establishes finite presence and link availability. Time/pose/revision/quality/raw-wire equality, source-admission ordering and contents, transition semantics, authenticity, actual producer callsite integration and downstream dispatch remain outside this approval. `ASSEMBLED_UNVALIDATED` is deliberately not a valid or authenticated proof. No acceptance claim changes H01–H15, either H12, or A-only physical-board authority.

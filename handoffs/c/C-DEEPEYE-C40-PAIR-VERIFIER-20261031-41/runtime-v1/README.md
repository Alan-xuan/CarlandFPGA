# C41 C40 READY + RESULT consistency verifier

Entry: `verify_pair(request_wire: bytes, response_wire: bytes, *, expected_ids: dict) -> PairConsistency`. The standalone module `c40_pair_verifier_v1.py` uses only stdlib hashlib/json/math/re/dataclasses/types. It performs no I/O, source-module imports, native operation, planner inference, clock sampling or dispatch. Input bytes must be retained from the actual original exchange by A. Handcrafted test bytes are explicitly synthetic.

The return contains detached recursively immutable READY/RESULT mappings, tuples for arrays, and exact request/response wire hashes. Frozen data can be read but not used as _CompletedInference, BOOT, process authentication, model qualification or movement authority. The reported core_ran is validated child data, not measured execution. No boolean, label or hash authenticates a process or source.

## Exact admission scope and pins

Only requests with C40's complete legal outer shape, ABI `c37-owned-cpu-package/v2`, kind recommend and all six valid echo_ids are admitted. All IDs must equal the caller's separately retained expected values. The package manifest is fixed to `d63dc5d32c7b9d8bb32035edc1d78483a51c6d88e680b7fbd4ef9f304cf005f0`; core SHA256 is fixed to `70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4`. Wrong pins cannot be accepted by supplying matching wrong expected labels. The original package identity remains A's responsibility.

C40 entry.request_identity can recognize IDs before process_wire validates outer shape/ABI. Invalid outer shape/ABI may therefore produce a C40 REJECTED pair with echo_ids=null. Such an uncorrelated early diagnostic is explicitly outside C41 pair admission and is rejected here, not claimed impossible in C40. Within legal correlated outer scope, malformed compact input is supported as a precise pre-core REJECTED diagnostic.

Request: exactly 16384 wire bytes, LE4=16380, canonical JSON then only ASCII JSON whitespace. Hash includes header and every padding byte. Responses: exactly READY then RESULT, no missing/third frame or leftover bytes, payload1..2048 then1..16384, aggregate<=18440. Duplicate JSON keys, unknown/missing fields, nonfinite numbers, non-UTF8, excessive depth/nodes/arrays and bool masquerading as integer are refused. Request/public schema checks are mechanically copied from the exact C40 source, not imported; no inference code is copied. Absolute ns are exact uint63 integers throughout.

## Result semantics

| Admitted request condition | Required status | core_ran | result / reason |
|---|---|---|---|
| Compact schema/enabled validation fails | REJECTED | false | null / exact first C40 validation reason |
| Valid, disabled (outer defaults false, inner required) | DISABLED | false | null / disabled |
| Valid enabled, normal return | RESULT | true | complete bounded advice / same nested reason |
| Valid enabled, generic internal failure | REJECTED | false or true | null / INTERNAL_ERROR |
| Valid enabled, post-entry C40 Rejected surface | REJECTED | true | null / fixed literal reason in postcore-code-surface.json |
| Valid enabled, output serialization/size fallback | REJECTED | true | null / OUTPUT_TOO_LARGE |

The fixed post-entry set includes `_validate_internal`/`_from_internal`/`_ns`/public validators and output tree/time checks. Recognizing a reason does not prove a failure actually occurred. Unknown reasons and unsupported statuses (including INPUT_UNAVAILABLE, which this C40 producer does not emit) are rejected. A bounded disabled/pre-core rejection response cannot legitimately overflow; output overflow must not erase true core_ran after entry. Generic INTERNAL_ERROR may occur before core flag assignment in _to_internal. No rejected record exposes partial advice or is adopted as completed inference.

A RESULT may contain STOP or ADVISE. Exact nested keys, planner ID, candidate_only=true/authorization=none, finite risk/uncertainty[0,1], finite direction and speed[0,0.25] are checked. STOP requires zero direction/speed and a fixed STOP reason. ADVISE requires its fixed reason, unit direction, risk<0.8 and positive speed below the risk/uncertainty-derived global cap. Early quality/expired reasons match the original input with exact >100ms comparison; 100ms is included. Observation must exactly match the supplied compact observation. Map entries correspond in order to original clean native samples, including exact sample ID/ns/pose; held samples cannot introduce map evidence. Counts, independent count, map bounds, reason equality and authority fields are checked.

This verifier does not repeat directional search, numerical risk prediction or optimality checks. Validating shape/ranges and original-field consistency is not proof that the frozen core actually generated the data; A must bind the genuine package/process/transcript and preserve freshness. The same limitation applies to synthetically valid advice used in tests.

## Host observation interval: narrow proposal only

`validate_observed_interval(dispatch_lower_ns=..., all_result_observed_upper_ns=..., now_ns=...) -> HostObservedInterval` checks exact uint63 values and `lower <= upper <= now`. It samples nothing and asserts no provenance or freshness. A must supply the original host-domain observation taken before the first request write attempt and the original observation after every byte of the complete RESULT frame was received. With genuine request/result/custody association, that gives a conservative dispatch-to-all-result-observed interval containing computation completion; it does not measure an exact CPU-finish timestamp. READY reception is not the upper endpoint.

Historical original host_envelope at commit5c192f34bad064b14e238747c2c569347257a62c, path competition/deepeye/integration/host_envelope.py, SHA256025adf0eee851327f6492ac853b77bc6ebfbb26c17eb7960f01baf644de4b7fd, lines431–435 checks completed_monotonic_ns<=now and leaves measured provenance/freshness to its caller. That exact scalar cannot honestly encode this interval as an exact CPU finish. Current A source/semantics were not fetched or changed in this task.

Proposed narrow NEW host-envelope version: replace the exact-completion scalar with `completion_observed_interval_ns:{lower_ns,upper_ns}` and a fixed `completion_basis:'host_dispatch_to_complete_result_observed_v1'`; retain the original matching request/result/transcript/source references in A's provider. This proposal is not an accepted or implemented A schema. Never fill the old scalar with upper, max(source time), projection.now or a fabricated child clock. Existing version remains unchanged until A makes a pinned amendment.

The upper bound establishes only that the full result was observed by then. It must not restart or extend an inference lease. Original source/command/dispatch deadlines stay in force. If an original maximum inference age L must be checked without an exact finish, `now-lower <= L` is conservative, or reject when the original deadline has elapsed; using `now-upper` alone would falsely make delayed results fresh. This helper intentionally does not decide L, derive a deadline, admit a stale source or grant completion. A owns original QPC domain/custody, source freshness and final movement fence.

A39 reports a new raw response-pair extension implemented with software controls, pending separate A review/publication. That statement is not original native execution or semantic authentication. C41 neither runs nor qualifies it. The historical A105 one-frame mode remains a distinct contract.

## Actual evidence

run01: 12 NEW handcrafted verifier methods, exit0, 25s subprocess bound, source SHA2f776a477e85a06dc1d5cc49be0f497cf048f165355c46e9168574a56b5674a7. Following main source-order guidance, only the fixed post-core reason surface was expanded; old source/test bytes retained. run02: only affected test06 plus new test13, exit0, final source SHAfc00cd1441e0dc15a092e601bb2864419e19ca688ba508c0b5a52faee429dd9b. No broad rerun or claim of a final whole-suite execution. Thirteen distinct methods have passing evidence; the unchanged paths retain run01 evidence and changed rejection paths have run02 evidence.

Coverage includes exact frames/budgets, keys/types/duplicate/nonfinite JSON, expected IDs/pins/full-padding hash, immutable detached outputs, disabled and malformed input, post-core flags/overflow, STOP and exact high-QPC100ms+1ns, nested advice/map/action bounds, held native identity, and observed interval ordering without freshness grants. Raw stdout/stderr/argv/exit/source versions are retained.

One preparation assertion failed before source generation because A-original-body.txt uses CRLF while assignment SHA names the original LF comment body. Original A-comment.stdout.json ID6531554988/author328016885/body SHA0e39f017... was then verified; saved text differs only in newlines (raw SHA03cfa590...). Failed preparation script and raw tool output remain in the private phase snapshot. No candidate test failed.

H01–H15/DEEPEYE-HUMAN-LOCK-20261014 revision1 were reread and requirements SHA c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 verified. No frozen/public files, old suites, original core/native/model/PDE/board, Git/network/service/credentials were changed or run. Main independent review and original A integration remain required; formal acceptance is false.

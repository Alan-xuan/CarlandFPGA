# C34 explicit numerical book / stale-aware composition

This is a new diagnostic adapter, `root_book_stale_composition_v1`. It preserves the schema1 detached numerical-book mapping of frozen C31 while explicitly selecting frozen C32's stale/structural semantics and its sole frozen C28 code object. It is default-disabled and grants no execution, movement, native, transport, board, CPU-completion or formal acceptance authority. H01–H15, both H12 chains, and A-only board authority are unchanged.

## Exact dependencies and contract

| Role | SHA-256 |
|---|---|
| C31 source copied, never imported | `506219cf445001c46f2f4e1ffd411829ea9d184d4260d18af9e45aa3787993ee` |
| C30 historical reference only, never loaded | `abaa06d10ab68f0bee721bf1a6d9278fc000446112ac559362079ad63afc686d` |
| C32 sole imported association engine | `39fe63a3d71308fae9482e3203b4f5120c34d796ccd2b755b99a9de902005a87` |
| C28 sole original core loaded by C32 | `70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4` |

The fixed sibling path to C32 is checked by hash on import. C32 checks and loads C28 once; its per-request bound function uses `_ORIGINAL.__code__` with copied globals. There is no caller-selected engine, monkeypatch of frozen modules, C31 import, second C28 load or fallback to C30. The entire source delta is `frozen-C31-to-C34.diff`.

`book_source_commit` remains exactly `54e1fd6c5795cc2f1247866dd8783331f615ef66`, the book code contract. Actual runtime provenance `4dc91fd24531b3df53fc916e8b7f509ad524592c` remains distinct. Verified identical `root_source_book.py` bytes under those commits do not change the field's definition or supply missing historical evidence. Schema2 is rejected.

## General entry

`project_json(raw: bytes) -> bytes` uses strict UTF-8 JSON with duplicate keys and nonfinite numbers rejected. `project(mapping) -> mapping` has equivalent tree, field and encoded-size checks and copies its input. `Rejected` propagates every known contradiction; it is not converted to missing or stale.

The only envelope fields are:

```text
schema_version=1, adapter_id="root_book_stale_composition_v1",
diagnostic_only=true, enabled? (omitted=false), book_source_commit,
book, book_current, binding, external
```

The C31 supplied-field meanings and nullability are preserved. `external` has exactly:

The frozen field-map reference is `C-DEEPEYE-ROOT-BOOK-C30-PROJECTION-20261030-31/mapping-contract.json`, SHA-256 `e36f59929fb21bd1b3e288af7455ccca631619184f3827532a09db0fbca6cb0d`. It is a field-map reference, not another runtime import. The explicit C34 differences below supersede only dependency selection, missing-path validation and result dispatch; they do not authorize missing original fields.

```text
evidence_scope, now_qpc_ns, candidate, history, config,
source_admissions, captures, current_pose, action_registry
```

`history` contains only actual retained candidates; missing current `candidate` stays null and is never filled with the last history item. `now_qpc_ns` is a supplied uint63 QPC integer, never a wall-clock sample, export completion or last sample end. Book/current/binding/config/admission/capture/action fields retain the frozen C31 mapping contract. Binding fields remain `context generation pose_book_id owner_binding_id committed_pose pose_revision root_revision claim native_interval_atomic`. Current metadata remains `receipt_id context generation valid_span_receipt_id`. Capture metadata remains:

```text
capture_sha256 source_record_sha256 request_raw capture_raw
adc_pose em_pose em_origin_capture_sha256 cause_action_id
adc_book_source_sha256 em_book_source_sha256
```

Pose metadata fields are `receipt_id source_admission_index valid_span_receipt_id`. Explicit ADC/EM book hashes are distinct from original wire/admission hashes. A supplied canonical source hex/payload must still agree with its original canonical bytes/hash. Unknown book/sample fields are dropped and counted, subject to the input tree limits; no whole book or private payload enters C32/C28.

The binding still describes one committed numerical Root pose/revision. Every supplied read/span/current association must agree with that single binding. This adapter does not enable arbitrary moving multi-revision native books. Claims stay `numerical_immutable_committed_root_only`, `native_interval_atomic=false`; equal pose coordinates or endpoint reads do not prove historical native getter continuity. Native/held EM requires the original explicit book link, retained native capture, admission, read, revision and span; no array-position inference occurs.

## Validation and dispatch order

1. Validate every supplied field/type/budget, canonical book hash, actual read/call/span/current time, namespace/anchor, explicit candidate/admission/raw links, held EM, and action revision/pose/cause relation. Partial missing receipt IDs cannot erase known actual contradictions. The inherited unknown-after action lower bound is validation-only and never fills a revision or receipt.
2. Validate positive actual config generation even without a candidate. Compare every actual config/history anchor. Traverse the full admission prefix with an actual config/history anchor when present; otherwise validate its decidable prefix/order/C3/native/held properties without inventing an origin.
3. Check each actual raw request's positive sequence and `0 < lane0 <= lane1 <= lane2 <= lane3 <= supplied_now`, independently of a candidate/capture/config. Each actual capture requires positive generation, internal lane/final counters, feasible nonnegative baseline, actual raw word sequence range/context tag/trigger/generation/channel and ordered original QPC through supplied now. These are necessary consistency checks, not authenticated receipts.
4. Compare every supplied raw request/capture context with every other actual raw context and every existing candidate/history/binding/config/current/action-registry context before missing/default/stale exits. Compare each actual capture generation with every other supplied generation. A request line has no generation and contributes none. These internal equality operands are not authenticated binding evidence and never fill output fields. Once those actual operands agree, capture final-counter deltas must equal `[4*dseq, dseq, 4*dseq]`. No inferred baseline is returned as config; existing actual config baseline and candidate/raw checks remain.
5. `captures=null` stays null. An actual list retains order and null entries; an empty actual list with a real current candidate fails C32's association count. Combined count is `max(len(actual_history)+current_present, len(actual_captures))+len(actual_actions) <= 32`, including missing/default-off paths.
6. With a real current candidate, call exact C32 `recommend_json` exactly once. Stage1 missing forces only that validation call's `enabled=false`, so structural validation still runs but no core can run. Outer output remains unavailable with null projection/result. Complete Stage1 forwards original enabled (default false). No disabled-then-enabled double call occurs.
7. Without a current candidate, no C32 recommendation is called. Local and C32 pure helpers check only supplied operands; output remains unavailable. This does not claim that a complete C32 envelope was validated.

On complete Stage1, frozen C32 traverses all supplied associations before its disabled/missing/stale decision. Legal stale input with enabled true is `INPUT_UNAVAILABLE`; disabled input is `DISABLED`. Contradictory stale input is rejected. Fresh allowed input alone can invoke the sole original C28 code object once. A diagnostic recommendation is not a live action or physical acceptance.

## Result and limits

Results include schema/adapter/diagnostic markers, authorization=`none`, claim, native flag=false, four source/dependency hashes, `c32_called`, `core_ran`, `input_status`, `status`, sorted fixed `missing_codes`, discarded book field count, `projection`, and `c32_result`. Stage1 missing uses `INPUT_UNAVAILABLE/STOP`, `core_ran=false`, null projection/result; `c32_called` accurately reports the single validation call if a real candidate existed. Complete Stage1 returns the actual projected C32 request and C32 diagnostic result. Structural exceptions are preserved.

Original uint63 integer clocks, inclusive100ms and +1ns expiration, original 10-second source window and initial1001 admission prefix are unchanged. General JSON input/output each limit1MiB; depth16, nodes65536, object32 fields, keys96 characters, ordinary arrays32 and strings192. Exact book-samples/admissions paths admit1001. Only exact raw request/capture paths admit16384 characters; only exact book sample canonical-hex paths admit8192. Output exceptions name `c32_result`, not arbitrary matching keys. The whole combined result is checked after projection and nested C32 result are attached; passing the component limits does not bypass aggregate limits.

## Separate immutable archive diagnostic

`inspect_retired_source70(raw_bytes)` accepts only type bytes, length82496 and SHA-256 `63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c`. Any changed bytes/type get one fixed rejection. This exact archive gate does not implement or claim a generic JSON/schema validator.

It returns minimal fixed unavailable/STOP provenance: original runtime4dc91, export `d0185d335747acb26439f40a8ce945f7f4eaa9af`, original schema1, book code contract54e1, missing original owner/current/admission/capture/native-EM/action proof. No synthetic now, IDs, config, projection, C32 or C28 call is produced. It leaves all original timestamps, held/null/valid-zero data untouched in the input; it does not reproduce C33's statistics or certify general composition acceptance.

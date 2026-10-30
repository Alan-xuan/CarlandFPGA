# C36 A108 host validation and projection v2

This explicit host v2 implementation validates bounded moving source/action evidence and produces the unchanged compact C37 input, without calling C28. Missing original facts produce STOP/INPUT_UNAVAILABLE; supplied contradictions reject even when unrelated evidence is missing. Projection is structural/numerical only and grants no dispatch, provenance or completion authority.

Operation C-DEEPEYE-MOVING-INTERVAL-BOOK-BRIDGE-20261031-36; task DEEPEYE-IMPLEMENTATION-20261014/version1. Target A source51c48e106c76f3e4d18000da61be17dd8a4b6623. The previous public abi-v1 contract is preserved; this runtime-v2 package explicitly uses host schema_version2 and moving_interval_book_bridge_v2, with response moving_interval_book_projection_v2. Old e794 records are not silently upgraded. Child schema_version1/projection_id=c36_c28_public_view_v1 and schema bytes are unchanged.

## Entry and real field contract

```python
from host_projection import project_interval_json
response_bytes = project_interval_json(full_proof_bytes)
```

The host envelope is at most1MiB. JSON parsing and the complete finite schema reject duplicate keys, unknown/hidden fields, invalid types, nonfinite/out-of-bounds numbers and excessive structure. Source prefix, quality/count/null/saturation, exact clock/held original pose, Root/revoke/read/capture/admission/interval/action consistency are checked before considering enablement. C28 is not imported or invoked. Exact original source parameters and whole frozen dependency pins are retained;42 selected pure predicate segments are AST-equivalent to pinned C32/C34 source, with differing newline formatting rather than byte-identical fragment text.

Each A108 transition requires the actual nullable old_pose_span, independently correlated with its original closed span and predecessor Root/pose. Supplied through must be strictly less than the separately observed lower for BOOT, COMMAND and STEP. Ties and late contradictory endpoints reject; missing facts remain unavailable. The validator does not add/subtract time, crop a span, fabricate an action instant, infer an absent receipt or renew old captures. Current pose must include the actual selected book.current_pose_interval() pose/read/valid_span facts. The original evidence.current_pose_interval interval-only export cannot stand in for that call. ABI.md documents exact field mappings and separately required provider receipt associations.

The reviewed partial-consistency repairs remain: getter timestamps cannot precede their supplied transition observations; missing to_root cannot conceal supplied STEP successor/revoke contradictions; missing config/book cannot conceal conflicting custody IDs. These are internal consistency checks, not authentication by labels.

The enabled result contains public_input only after supplied structure and numerical associations validate. Before dispatch, A's original provider must independently establish actual full-proof/owner/receipt/getter/native-source/BOOT/capture provenance and bind that proof to exact serialized bytes, retained process/package/pipe, one-use invocation and host dispatch/read/completion freshness. C36 cannot reconstruct the private receipt digest/context preimage, validate an actual retained object from JSON, or prove that an exported getter was called. PROJECTED never replaces these obligations. Missing provider evidence prevents actual dispatch even if a synthetic input projects successfully.

## Versioned validation

- Initial host implementation:22 distinct new controls with11 recorded runs, exits `[1,1,0,1,0,1,0,1,0,1,0]`. Each version and failure remains preserved; this was not a final-source22-test run.
- Independent e794 review:7 new cases,2 pass/5 RED, exit1, yielding R1/R2/R3. Narrow consistency repair:the same7 affected cases and8 direct boundaries passed in two runs, exits0,0. Old22 were not repeated.
- A108 host adaptation:14 distinct new controls with exits1,0,1,0. The final host source ran only the last3 affected author controls; earlier13-control results retain their exact earlier source version.
- Final independent review: no new blocking source defect found in the scoped repairs/adaptation. One NEW synthetic cross-component run passed on the exact final host and already delivered C37: host core calls0, child original C28 calls1; request1508B; original high-QPC/EM pose preserved; ADVISE output. Missing actual current_read returned STOP/INPUT_UNAVAILABLE with local serialization/process calls0. This is a software boundary check, not A's real provider or native actor execution.

The archive retains original REDs, fixture/extraction/harness errors, source snapshots, commands, stdout/stderr and exit codes by version. REVIEW.md and FINDINGS.json contain the independent result and limits. `evidence-index.json` lists exact archive member hashes. Historical scripts retain their original paths; do not run them into old evidence directories or treat their synthetic IDs as production receipts.

`python -I -S -B verify_delivery.py` checks delivered bytes/archive integrity only and executes no source function, model or actor. Runtime SHA2567defaee9318f9a33a0586628661d054c028b5952584030ebc3b771a479a8982e; host schema SHA256ab1b432e9f337523fd75057fec4647f5eda2569de308e7c777507e05907bdd70; child schema SHA256046b863c6bc07bbaa5396c5b7dfc55fb1febf7bbd0bda29ef79cbd5119f981ed.

Actual native handles/process invocation, live source/startup/BOOT, production control, board/full-chain and formal acceptance remain NOT_RUN or unavailable. C37 still supports only one invocation; A105's exactly-one-frame raw seal cannot directly consume READY plus RESULT, and no serial-child enablement is granted. Original initial9C3null behavior, warmup and100ms freshness must remain real; do not burn/renew a lease during warmup or retime observations.

Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, source f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements SHA256c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804, fixed design1011259415a0916054eb580687612580bc1e5f09. H01–H15/original29/both H12/final100MHz/timing/1%/100ms remain unchanged and unaccepted. A alone operates the physical board.

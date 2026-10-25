# Independent stream review: phase1 control freeze

Work C-CPU-STREAM-INDEPENDENT-REVIEW-20261025-v1; task DEEPEYE-IMPLEMENTATION-20261014/version1. Main thread01a14025-4dfd-7ec3-aebb-57be48daba59, canonical reviewer /root/cpu_independent_review. This phase derives controls from unchanged C19 runner/builder/scaler/saved results and A comment6395841435. It has not read, imported or executed evolving stream source/tests. Product/index unchanged. Phase2 requires the parent's frozen-source trigger.

Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, source f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 and design1011259415a0916054eb580687612580bc1e5f09 remain fixed. H01-H15 and unmet formal gates remain incomplete; A alone operates the board.

Source pins are in source-pins.json. Original model manifest0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959 and saved result e84bdfe850efb8a231f72c98a5fb05cc20c7f6036014f4db77ef3f6cf44b418f match. A-source-comment.json preserves local source, snapshot hash, exact UTF8 body hash and zero replacement characters. No fresh GitHub/network request was made.

derive_controls.py ran once under Python3.13 stdlib-only (-I -S -B -X utf8), exit0. It pins nine unchanged inputs, reads only first3 raw public lines (sequence7327,7328,7329), independently computes frozen means/scales/log10 normalization and right-aligned masks, packs1024 float32 values in little endian channel order, and matches all3 original C19 tensor and raw-prefix hashes. Saved probabilities/classes are copied parity oracles; no probability was recomputed. Actual argv/stdout/stderr/exit are preserved separately.

Parent-approved new API decisions: FrozenForceStream(manifest_path,fixed manifest pin,only lower limits); immutable strict-identity token; uint32 monotonically increasing generation AND epoch; UTF8 run_id<=128bytes; explicit end before newer start; one raw byte record<=16384/call; immutable encoded JSON<=8192. Maxima65536 accepted deliveries/64MiB raw/1024sessions/2048transitions need explicit per-session/lifetime scope and cannot reset away lifetime limits. These limits/lifecycle tighten the old builder's unbounded counters/run_id. They are new acceptance requirements, not preexisting builder claims.

Planned small phase2 controls (adapt call spelling after freeze; no author suite or old baseline rerun):

| ID | Independent control and required result |
|---|---|
| P01 | One real fixed-model core, only first3 oracle records: original sequence/binding, exact prefix SHA and float32 tensor SHA, class equality and finite12probs; compare saved probs with explicit measured error/tolerance. Earlier output exists before next input. Retain old immutable outputs. No all128 replay. |
| P02 | First accepted record followed by malformed future bytes: reject second without rewriting first result/history/counters/prefix. Good continuation matches rejection-free twin. No future file/iterator API or file reads after construction. |
| P03 | Equal observation encoded with changed key order/whitespace/CRLF or numeric1 vs1.0 changes exact raw-prefix digest. Prefix equals SHA256(concatenated accepted rawbytes), never canonical JSON or decoded-text digest. |
| P04 | Same current sequence and equal value/valid tuple is accepted idempotent physical delivery: prefix/delivery index advance; idempotent increments, fresh count/history/features do not. Probs/tensor may be reused; entire old encoded result must not be reused. Exact/reencoded semantic duplicates follow builder equality. |
| P05 | Conflicting duplicate, including changed masked raw value, and regressing sequence reject atomically. +0/-0 or equal int/float values retain old equality semantics. No raw-byte-only duplicate policy or retrospective mutation. |
| P06 | Missing/extra/label/truth/future field, duplicate JSON key, invalid UTF8, multiple objects, nonfinite numbers (including1e999), bool sequence/value, integer validity, lossy integer value, oversized raw/UTF8 run_id, wrong input type: explicit nonmutating rejection. Exact13fields only; no truncation. |
| P07 | GR1e45 is finite before/after double normalization but exceeds float32 max. Post-builder tensor check rejects; trial builder/deque/digest/counters/last output cannot commit. Valid retry at that sequence matches rejection-free history. |
| P08 | Private labelled fault injection after trial build in inference/serialization, then retry: no partial commit. No public fake-model/result-injection API. Stubbed outputs cannot count as real model evidence. |
| P09 | Duplicate branch serialization/output limit: private serializer emits valid JSON whose bytes exceed configured cap, or equivalent frozen seam. Reject before changing prefix/idempotent/delivery/latest output, including reused features/probs. Check encoded size, not only early exception. |
| P10 | Explicit start/end only; active session cannot silently reset. Wrong-core, copied/equal-looking, ended/stale token, wrong binding, old-token end/observe against newer session reject and preserve current state. Old generations/epochs cannot reset newer sessions. |
| P11 | uint32 endpoints/exhaustion; generation AND epoch increase, bool/negative/overflow reject. UTF8 byte bound. End/start resets only documented run history and retains same loaded model/scaler. Rejected transitions cannot consume caps or reload. |
| P12 | Sequence0 to uint64MAX: at most127 missing slots, final filled1/missing127, uint64 preserved without float conversion/per-gap iteration. MAX+1, wrap/regression reject. Normal gaps/right-aligned masks match builder. |
| P13 | RDEP<=0 or invalid channel gives zero value/mask0; valid other negative values stay normalized. Cold start, gaps and allmissing channels bounded. No clipping/remapping/invented values. |
| P14 | Lower delivery/raw-byte/session/transition/output caps cause bounded nonmutating errors. Static plus few stubbed records verifies128history and constant digest state, not retained full prefix/output list; invalid-call telemetry bounded if present. Avoid65k real forwards. |
| P15 | Encoded bytes and nested public metadata/token immutable or detached. Caller mutation cannot change history/old outputs/latest. No stale external setter overwrites state. |
| P16 | Nonblocking lifecycle/observe lock rejects reentrant callback without deadlock/state mutation. No background writer/thread or implicit reset. |
| P17 | FORCE/geo_replay fixed pin only; sim_em blocked. Output current finite12probs, fixed class order/first maximum tie, tensor identity/prefix/original sequence/binding, movement_authorized=false. No acquisition clock/BOOT/observed_seq/action/verifier/IPC/runtime/motion authority. |

Raw duplicate oracle has three distinct digests: first original, original+exact duplicate, original+reencoded semantic duplicate. Overflow records normalized double and IEEE float32 max. Huge gap derives O(128) work independent of uint64 distance. These expectations do not claim new implementation passes.

Inspection limitations: initial scaler path ai_pc/data instead of data failed exit1; guessed manifest.json read failed while the following PowerShell read returned0. Raw diagnostics retained; corrected paths then pinned successfully. Initial A-body console encoding mismatch was corrected with UTF8 extraction; original body has zero replacement characters. Read failures had no product effects. Inspection tool results combine streams; oracle subprocess preserves rawstdout/stderr separately.

FORCE quality remains FAIL: CNN fixed12 macro-F1 .1827348057438266 below centroid .2047004573101128 and .60. No training, heldout, old suite, runtime/sim_em/board/formal acceptance run or asserted. Phase2 source/runtime review remains pending.


# C31: detached numerical Root book to frozen C30

Operation `C-DEEPEYE-ROOT-BOOK-C30-PROJECTION-20261030-31`, original task
`DEEPEYE-IMPLEMENTATION-20261014/version1`. This is a default-disabled, pure
structural adapter. It accepts detached JSON and projects a strict whitelist
into the existing C30 diagnostic JSON entry. It neither executes A's code nor
creates a planner, clock, producer, Root owner, native process, transport,
action, CPU completion or movement permission.

`project_json(raw: bytes) -> bytes` is the strict UTF8 entry;
`project(json_mapping) -> detached_mapping` is its in-process equivalent.
Missing `enabled` means false. Complete input calls the exact fixed C30
`recommend_json`; its diagnostic computation uses the same original C28
`recommend.__code__` with C30's isolated validation globals. Import reads only
the two known, hash-pinned local dependencies; calls perform no external I/O.

Dependencies are immutable:

| Dependency | Exact pin |
| --- | --- |
| A numerical book source | `54e1fd6c5795cc2f1247866dd8783331f615ef66` |
| A `root_source_book.py` SHA256 | `624c84f8de949c7c078ca0b7afa84c295804d7bc881527e9b91c38ba645004ef` |
| C30 runtime SHA256 | `abaa06d10ab68f0bee721bf1a6d9278fc000446112ac559362079ad63afc686d` |
| C28 core SHA256 | `70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4` |

C32 is not bound. No C28/C29/C30 file is modified by this operation.

## Numerical proof boundary

Every C31 result retains `claim=numerical_immutable_committed_root_only`,
`native_interval_atomic=false`, `diagnostic_only=true`, and `authorization=none`.
A's book span describes an immutable numerical committed Root under its
original trusted owner and writer rules. It is not a native getter atomic
interval, GPU result, physical trajectory or authentication boundary.

The external `binding` must explicitly associate the original book/owner IDs,
full context/generation and committed numerical pose/root/pose revisions.
Checking equal read coordinates is only a consistency check on that supplied
association; C31 never uses endpoint equality to create interval provenance.
Missing this binding is unavailable even if all poses happen to match.

This version requires the detached `evidence()` snapshot to include the current
view's checkpoint: obtain `current_pose_interval()` first, then detach the book
evidence without running another source operation. The supplied fixed interval
must contain the current span. An earlier detached book with a later current
checkpoint is not accepted by this conservative version.

“Native EM” below means the original EM **sample** and its original returned
capture, not native-engine interval atomicity. Held EM uses the original sample
read/span/revision/call and explicit original capture link. The later held ADC
call cannot replace the original EM call. A's book itself does not supply held
wire capture linkage or executed actions; those must come from separate actual
Root associations, or from explicitly synthetic test inputs.

## Required inputs and mapping

The exact machine-readable field lists and rules are in `mapping-contract.json`.
`interface-examples.json` contains three complete **synthetic** examples. Their
private payload is a synthetic marker, not evidence that a SourceRecord,
producer, Godot or A Root operation ran.

| Supplied data | Projected data / check |
| --- | --- |
| External candidate/history/full config | Exact original C30 fields; no identity, count, quality or clock changes |
| External original source admissions | Original complete prefix and indices; never derive an admission from a book array position, finish or poll |
| Explicit `adc_book_source_sha256` | Select the original detached ADC sample by its book hash |
| Explicit `em_book_source_sha256` plus `em_origin_capture_sha256` | Select the original EM sample and its retained original returned capture; reject contradictory dual origins |
| Actual sample nominal/read/call/span | Exact C30 nominal, pose read, ADC call and closed numerical span endpoints |
| External pose metadata | Original receipt IDs, source admission indices and span receipt IDs; no generated labels |
| Detached `book_current` plus external current metadata | Actual current read/pose/revision/span; `at == read.end == external.now` |
| External action registry | Actual original execution/commit records, or an explicitly supplied actual empty registry |

The book `source_sha256` hashes its original canonical SourceRecord bytes.
The wire/admission `source_record_sha256` is a separate namespace and may have
different encoding/newline history. C31 never equates or rewrites these hashes.
The original Root explicitly supplies their association. If canonical book
bytes are supplied, C31 verifies strict canonical UTF8, SHA256 and exact optional
payload bytes before discarding the private contents. This checks consistency,
not authenticity of a JSON sender.

Private book payload/canonical bytes and unused operation fields are discarded.
Unknown fields within the private book are also discarded and counted; their
names/values never enter the planner/result. Unknown external, binding, current
and used temporal structure fields are rejected. No scene, material, seed,
boundary, screen or collision oracle is forwarded.

## Missing evidence and malformed evidence

Before any missing/default return, C31 validates all supplied shapes, budgets and
decidable associations. This includes each supplied original raw line against
the candidate even if the other line or config is missing; source prefix/order/
native flags/C3 continuity even without config; and candidate/admission relations
even without a capture receipt. Supplied raw counters must satisfy per-lane and
final consistency, a nonnegative original baseline at the actual request seq,
and exact cross-capture counter increments. These checks do not invent a config.

Incomplete adapter proof returns `INPUT_UNAVAILABLE`, `STOP`, `core_ran=false`,
`c30_called=false`, `projection=null`, `c30_result=null`, and bounded fixed
missing codes. No placeholder identity/request is sent to C30. Null never means
an observed empty registry. Contradictions, wrong types, duplicate keys, hidden
external fields and cap violations raise `Rejected`; an unrelated missing field
does not turn them into unavailable evidence.

Complete inputs enter the frozen C30 JSON interface with the requested enable
flag. C30's own results and exceptions are preserved. In particular, a complete
pure-stale retained admission currently raises C30's `Rejected('source admission
original age')`, including disabled input. That known semantic gap belongs to
the separate C32 task; C31 does not swallow it or substitute another dependency.
New synthetic versions of the known tick0/470, 473319100ns age and null-C3 facts
with absent real associations remain unavailable/STOP, without repairing data.

## Bounds

Adapter input and output are each at most 1048576 UTF8 bytes, with 65536 nodes,
depth16, object32, key96, ordinary string192 and ordinary array32. Only exact
`book.samples` and `external.source_admissions` allow1001 entries. Original raw
capture/request lines allow16384 characters/bytes through C30; original book
canonical hex allows8192 characters for at most4096 bytes. The complete original
source window remains10000ms with unchanged anchor. Before **every** return:

`max(actual candidate+history count, supplied capture count) + supplied action count <= 32`.

The projected C30 input/output also retain all their original checks. No
truncation, prefix reset, clock rebase or byte-budget bypass is performed.
Unchanged C28 policy includes source100ms, pairwise0.25m/15deg, original native
EM cone30deg, quality/null/fault/counts and conservative STOP. This adapter grants
no actual Root, CPU qualification, H12, final1pct100ms or formal acceptance.

## Versioned NEW software evidence

Each invocation was bounded to30s, saved original stdout/stderr, source/test
snapshots, input/output hashes and actual exit code. No old C28/C29/C30 suite or
closed author/independent group was rerun.

| Run | Source phase | New methods / result |
| --- | --- | --- |
| 01 | v1 `b43739c3…` | 16 methods:15 pass, test09 expectation error; exit1. Correct contradictory dual-origin rejection had been expected to be unavailable. |
| 02 | Same v1 | Only repaired test09 plus new17–19; 4 pass, exit0. No runtime change. |
| 03 | Same v1 | NEW four gap methods /7 failing assertions, exit1: supplied canonical hash, partial raw correlation, prefix without config, candidate/admission without capture. |
| 04 | v2 `2be2fd24…` | Exact four failed methods pass, exit0 after local validation fixes. |
| 05 | Same v2 | Five NEW controls pass, exit0: Unicode canonical positive, hash-consistent raw contradictions, valid partial raw evidence, strict canonical/private payload, disabled missing receipt conflict. |
| 06 | Same v2 | Two NEW C31 counter failures, exit1: negative baseline feasibility and cross-capture increment without config. C32 evidence is not reused. |
| 07 | `ecf0cb43…` | Exact two failed methods pass, exit0 after local counter relation checks. |
| 08 | Same source | Two NEW positives pass, exit0: retained request seq gap without config; complete nonzero supplied baseline enters single C28 core. |
| 09 | Same source | One NEW failure, exit1: Python bool/int equality could hide a private payload/canonical JSON type mismatch. |
| 10 | `d003fdf0…` | Exact failed method passes, exit0; comparison uses exact canonical bytes. |
| 11 | Same source | Two NEW missing/identity defects, exit1: missing candidate with retained receipt incorrectly rejected; missing current receipt plus binding hid a supplied namespace contradiction. |
| 12 | Final `9b810d79…` | Exact two methods pass, exit0; actual supplied namespaces are checked independently, absent candidate is unavailable, and supplied raw/book/admission relations remain validated without it. |
| 13 | Same final source | Three NEW controls pass, exit0: candidate absent with contradictory raw pair, valid missing current metadata, changed legal goal through the exact C28 core. |

These are version-specific results, not a claim that a single38-method suite
passed on the final bytes. Original failed snapshots/logs remain available to
the main and independent reviewer. Final independent review/public evidence is
owned by the original C main. Reproduction commands name the explicit methods
in the saved execution records; do not indiscriminately rerun closed groups.

Human contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, fixed design
`1011259415a0916054eb580687612580bc1e5f09` remain unchanged. H01–H15, both H12,
all29 and final1pct100ms unfulfilled gates remain unfulfilled. A alone operates
the physical board. Actual A Root/native/Godot/producer/board/full-chain/formal
execution is **NOT_RUN** for this C31 delivery.

## Independent R1 repair: author-v2

The independent review of runtime `9b810d79...` found eight real partial-input
temporal defects. This version validates supplied ADC begin against nominal,
now and every actual read end even when call end is absent. It separately checks
actual book/current poses, revisions and supplied spans against actual action
commits, regardless of missing receipt metadata, binding, config or candidate.
Same revision must have the same numerical pose; known different revision spans
must be ordered without overlap. Span extrema are used only to detect
contradictions, never to fill gaps or create new coverage claims.

Actual actions must be executed, have unique IDs, preserve time and known
revision order, and follow any supplied referenced observation receiver.
An explicitly linked cause must precede the supplied candidate/book nominal.
Unknown observations/causes remain fixed missing codes and never become fake
receipts, namespaces or identity bindings. Equality is only a consistency
condition: the numerical committed Root claim and `native_interval_atomic=false`
remain unchanged. Complete requests still enter the exact frozen C30 JSON ABI;
no C32 dependency or alternative planner was introduced.

The standalone `test_partial_temporal_v2.py` reads saved synthetic examples as
data, never imports the old test suite. Four bounded invocations are preserved:

| V2 run | Exact result |
| --- | --- |
| 01 | Baseline `9b810d79...`: 14 NEW methods, 11 product RED and 3 unavailable positives pass; exit1. |
| 02 | Runtime `c6a38982...`: only the 11 failed methods replayed, all pass; exit0. |
| 03 | Same runtime: 4 NEW adjacent controls, 3 pass; complete-path test hook error because C30 clones function code and cannot accept the closure hook; exit1. |
| 04 | Same runtime: only corrected complete-path test hook replayed, passes with exactly one C30 JSON call and one real bound C28 core call; exit0. |

This is version-specific evidence, not an all18-on-final-source claim. The old
author38 and independent30 groups were not replayed. Original independent eight
input replays and closure remain the independent reviewer's responsibility.
All original failures and raw exits are retained in `author-v2/`; original
author-v1 records remain unchanged. No Git operation or formal acceptance was
performed by this worker.

## Main static M2 repair: author-v3

An absent action `to_pose_revision` must not erase its supplied before revision.
The adapter now tracks an internal necessary integer lower bound across actual
executions: before cannot precede that bound, each execution strictly advances,
and a uint63 successor must exist. A supplied current revision cannot precede
the final bound. With unknown after, only spans below the bound must end before
commit; spans at/above the bound are not forced to begin at commit. The bound is
never an actual revision, filled receipt, pose, span or returned proof. Original
null after values and unavailable output remain unchanged.

Three NEW bounded v3 invocations preserve snapshots and raw logs: run01 has four
real lower-bound REDs on `c6a38982...`, exit1; run02 replays only those four on
`506219cf...`, all pass, exit0; run03 has three NEW valid unknown-after controls,
all pass, exit0. They cover increasing before/current, the last representable
uint63 successor, and a span at the bound that can precede unknown actual after.
These are seven narrow controls, not a replay of old18/38/8/30 or a claim that
all historical tests ran on the final bytes. Original v1/v2 evidence is retained;
independent original-eight replay remains pending with the reviewer.

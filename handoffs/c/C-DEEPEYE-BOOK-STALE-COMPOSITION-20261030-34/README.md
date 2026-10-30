# C34 numerical-book composition handoff

C34 provides a new explicit default-disabled composition of the frozen C31 detached-book checks with exact C32 stale/structural semantics and the same original C28 code object. It does not modify or silently redirect any frozen C28/C30/C31/C32 artifact. Read `ABI.md` for exact input/output, missing-path rules and the separate immutable source70 diagnostic.

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work `C34-EXPLICIT-C31-C32-COMPOSITION-IMPLEMENTATION-v1`. Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA-256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, fixed design `1011259415a0916054eb580687612580bc1e5f09`. H01–H15 and both H12 chains remain; physical board operations belong only to A. Main retains independent review, publication and acceptance.

The five new files are the pure runtime, new focused controls, ABI, this README and complete C31-to-C34 source diff. The only imported engine is hash-pinned C32, whose fixed C28 import and `_ORIGINAL.__code__` are checked by call-frame instrumentation. Example JSON from frozen C31 is read as explicitly synthetic fixture data; old tests and runtimes are not imported or run.

New controls cover default-off versus one actual original-core call; complete native and held data; null/empty/list-entry preservation; missing book/config/raw/receipt/metadata contradictions; action unknown-after lower bounds; records-only counter consistency; absent-current config generation/history anchors; high QPC above2^53 with admission/capture/now at100ms and+1ns; stale plus late contradiction;1001 prefix/10-second limits; combined32/33; strict JSON; wrong-path caps; aggregate output exceeding1MiB despite input below1MiB; source contract/schema2; and immutable archive provenance without engine calls.

Every invocation is bounded by30seconds and records the exact argv/cwd, source snapshots, raw stdout/stderr and actual child exit in the private assignment evidence. No model, PDE, native producer, old suite, network, peer, Git or board execution occurred.

## Actual execution record

Evidence root is `.local/main-20261015-01a14025/C34-20261030/author-implementation-v1/` in the node C deployment. These are actual runs, not inferred successes:

| Run | Exit | Outcome |
|---|---:|---|
| run01-core |0|New fresh/default and held controls passed; one original C28 code object verified.|
| run02-partial |1|Four tests passed; null/empty test correctly rejected but expected the wrong error substring. Original failure retained.|
| run03-time |0|New admission/capture/now100ms and+1ns, disabled stale and late structural conflict passed.|
| run04-caps |1|Prefix positive/cap checks and two other tests passed; out-of-window fixture first contradicted held bits. Original failure retained.|
| run05-expectations |0|Only the two failed controls rerun after test-only fixes.|
| run06-raw-missing |1|Two genuine missing-candidate request-only gaps: sequence0 and future raw QPC accepted as unavailable. Original inputs/logs/source preserved.|
| run07-aggregate |0|Actual32 candidate/capture and1001 prefix input; small output passed, large combined output rejected.|
| run08-raw-fix |0|Local request sequence/time repair; negative/valid controls and original single-core/default chain passed.|
| run09-capture-only |1|Two genuine capture-only gaps: actual identity words and original QPC contradictions accepted as unavailable. Original inputs/logs/source preserved.|
| run10-capture-fix |0|Local capture words/time/generation repair; negative/valid controls, missing held book, records-only pair and single original core passed.|

Earlier successful groups are not claimed to have been rerun on later source versions. Each run has its exact runtime/test pin. Final changes after run07 are narrow raw-intrinsic predicates and are covered by run08/run10; frozen dependencies are rehashed at final freeze. No failed or ambiguous side effect was replayed: these are pure new diagnostic controls. The final evidence index lists raw files and pins. Independent exact-candidate review remains required; these checks are not native/board/formal acceptance.

## Important boundaries

The numerical book code contract remains54e1, with actual runtime4dc91 recorded separately in the immutable archive diagnostic. Equality of those book implementation bytes does not supply missing original evidence. A later observation bound cannot replace a true committed action point; this adapter does not create a live actor or barrier protocol. The single committed numerical Root binding and closed-span semantics remain as in C31. Unknown-after lower bounds are validation-only, never fabricated revisions or receipts. Original held EM needs its explicit native ancestry.

The historical source70 entry makes no general C32 composition call and creates no now, owner or action record. Original raw source is not modified. Completion of this handoff does not close the main task or mark its remaining acceptance items complete.


## C34-R1 narrow repair after independent review

The independently reviewed f913c3f0d9188dc9f8d04e6f360061c081cd34da2d0dea57a61170e845333bbd version accepted three contradictory raw-only namespaces as INPUT_UNAVAILABLE. Its complete five public files and original RED input/observed bytes are retained in `.local/main-20261015-01a14025/C34-20261030/repair-r1-v1/original-public` and `original-red`; the original review remains unchanged.

This repair changes only `_crosschecks`: full actual context from every request/capture and actual generation from every capture join the existing outer comparison operands. Contradictions reject before missing returns even without candidate/history/config/binding/current/registry. Request-only input supplies no generation. An internal comparison operand does not establish authenticated ownership or fill projection/config/output evidence. The single frozen C32/C28 chain, all clock/quality/pose/counter policies, default-off and output limits are unchanged. `test_composition_v1.py` is unchanged.

One new bounded run (30-second limit), `repair-r1-v1/run01`: exit0,8/8 controls passed,0.305seconds, stdout2864B, stderr0B. It replays only the exact three original RED bytes, then checks consistent request-only (no generation), capture-only and mixed raw input as unavailable, complete fresh input with exactly one original C28 code-object call, and omitted-enabled with no core call. Missing cases have no C32 call or projection; complete/default cases each have one C32 JSON call. Original core globals identities remain stable. The closed independent38-case matrix and old author10groups were not rerun; their earlier evidence remains historical. Repair verification is diagnostic software evidence, not Root/native/board or formal acceptance.

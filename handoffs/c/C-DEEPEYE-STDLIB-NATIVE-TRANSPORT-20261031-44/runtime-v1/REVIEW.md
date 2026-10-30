# C44 independent review

Decision: source approved for the explicit C44 transport variant and unchanged consistency-only verifier. No open source finding. Manifest `cb971d321bcdd3dcb6a7b85fdd9e08171c995feb62fab3f995bc7f50fdf97a8a`; entry `899b843111a1b9278e4c5ee16b11d4493c35c1cb0bca328a57f164c3f0c11c74`. Native qualification remains **NOT_RUN**, not approved by fake controls.

## Source and API evidence

Verified A42 comment 6532501500 author/body hash and author FINAL 8e3d159df3f0c6bacee6726cce6f2a437fad6e8a58bec7d0dd18ec8cdb0aa1ca. Independently verified 67 frozen/source pin entries before and after. Read the complete new entry, source/verifier diffs, documentation, official CPython source excerpts and author control sources/raw results. There was no new source GET, stage, dependency change or publication.

Official pinned CPython v3.12.14 `_winapi.c` implements synchronous ReadFile as `(bytes,error)`, permits ERROR_MORE_DATA as a nonzero tuple result, raises other synchronous read errors, implements WriteFile as `(written,error)`, and returns None on successful CloseHandle. `overlapped.c` SetEvent raises on failure and returns None on success. The new transport's exact tuple/int/bytes/None checks match these APIs. In particular bool is refused as an int result, nonzero read error is refused even with bytes, positive partial reads remain legal, and every short write is refused without a remainder retry.

Independent read-only module inspection confirmed local CPython 3.12.14 `_winapi` is built-in and has no SetEvent, while `_overlapped.SetEvent` exists with the expected signature. No handle API was called. An independent stdlib PE import-table reader rechecked the five selected local binaries against the recorded hashes and parsed imports/delay-imports; all matched. `_overlapped.pyd` has kernel/socket/python312/VCRUNTIME/CRT dependencies, not `_ctypes`/libffi. This is local static dependency evidence only, not AppContainer behavior or a diagnosis of A's earlier DLL failure.

## Minimal change and lifetime

`c37_package.py` and `frozen_c28.py` are byte-identical to frozen C40. `serve` and `load_package` are exact source-segment matches. Consequently this transport change does not modify core code-object contents, numerical/projection/QPC/status logic, K1..16, request16384, chunks8192, serial identity checks, READY/RESULT limits2048/16384 or total18440. No core was imported or invoked by this review.

The C41 verifier is an exact byte replacement of only the old manifest pin with the C44 pin. The staging helper is byte-identical to frozen C40 and was not run. All 633 inherited runtime inventory rows are unchanged; four package rows match new files. This is C633 provenance, not an A632/A636 equivalence or a restage. Only selected current local PE/runtime files were inspected; the 633 runtime binaries were not rehashed as a new closure qualification.

NativeTransport accepts three distinct bounded integer handles and sets one-use flags before readiness, wait and closure attempts. Event construction is prospective, before readiness. The event is never set by this code and wait has no timeout. While waiting or after close, further transport use is refused. Unchanged serve has no read, inference, timestamp sample or normal successful exit after K; owner retains fixed lifetime enforcement.

Once CloseHandle is available, initialization failure attempts all three slots; earlier close exceptions or non-None results do not suppress later attempts. Closing marks retired before calls and does not retry failed closes. Before close API availability, explicit closure is not claimed. Main distinguishes invalid args64, package70, setup with successful attempted closure71, missing close API74, setup-close failure75, serve failure72 and serve-close failure73. Numeric exits do not serialize arbitrary exception/handle text. OS process-exit cleanup, owner Job state and AppContainer access still require actual A evidence.

## New independent execution

Only two new combined-fault controls, one process with timeout25s, actual0.172s, exit **0**, stderr empty. The script imports only the new entry and injects independent fake API/Event/package objects; it never calls load_package or imports adapter/core. Case inputs, observed call traces, fixed exits, captured empty output streams, command and raw stdout/stderr are retained.

1. One complete synthetic request reaches one fake callback. First8192 output bytes succeed, the remaining809-byte write returns808. Closing then raises for slot0 and returns False for slot2. Main returns73, all three close slots were attempted once, no remainder retry/second request/second callback/wait occurs, and closed-object reuse produces no further fake API calls.
2. Prospective Event construction raises after close API acquisition. Slot0 close returns False, slot1 raises, slot2 succeeds. Main returns75, all three attempts and failure slots[0,1] are retained, and no readiness/read/write/callback occurs. Captured diagnostic streams remain empty.

These combinations supplement existing author single-fault boundaries; they are not native cleanup or pipeline qualification. The fake callback count is not a C28 count. No old group or author full suite was replayed.

## Raw failure attribution

Author phase exits are [0,0,1,0,0,0,0,0], with frozen raw streams retained. Run02 had eleven NEW methods: ten passed, test10 failed on its own dict-versus-bytes framing fixture before verifier admission. Run04 reran only corrected test10 with unchanged production source. Run06 added one method containing five fake fault subcases. Twelve distinct methods have passing evidence across those runs; no single final twelve-method run is claimed. Inventory metadata correction and its earlier draft remain versioned.

This review's first static preparation command exited1 because the review script treated the freeze files list as a dict. It failed before candidate import/test execution. Original `prepare.py` remains unchanged; `prepare02.py` changes only that parsing assumption and succeeds. The original tool traceback/exit is retained in the actual session (chunk f8404a); `preparation-error-reference.json` indexes that evidence. This is a reviewer tooling error, not a product RED or rerun of candidate controls.

## Boundaries

No original A actor, inherited native handle call, planner/model/PDE/board execution, real stage or weaker-isolation fallback occurred. A owns its explicitly selected A632 runtime adaptation, first actual C44 native run, original transcripts/identity, process exit/Job/handle cleanup, and all AppContainer/ACL/mitigation/source gates. C44 supplies no motion or completion grant and no CPU-finish timestamp. H01–H15/original29/bothH12/final100MHz/timing/1%/100ms remain unchanged and unaccepted; physical board authority remains A-only.

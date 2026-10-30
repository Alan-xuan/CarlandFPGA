# C44 explicit stdlib transport variant

This is a new private package for A's independent native qualification. It preserves C40 wire ABI `c37-owned-cpu-package/v2` and changes package identity to manifest SHA256 `cb971d321bcdd3dcb6a7b85fdd9e08171c995feb62fab3f995bc7f50fdf97a8a`. It does not qualify AppContainer startup, authenticate an owner, grant motion/completion, or establish a CPU completion timestamp.

`c44-owned-cpu-package/` contains four files. `c37_package.py` and `frozen_c28.py` are byte-identical to C40. Entry `load_package` and `serve` source segments are identical. The original one-core computation, numerical functions, compact projection, exact QPC conversion, status rules, serial identities, K=1..16, fixed padded request 16384 bytes, chunks <=8192, READY/RESULT limits 2048/16384 and aggregate 18440 remain unchanged. Entry still uses `--actor-stdio-v2 --max-invocations K --request-bytes 16384` followed by the three original inherited handle strings. No core was executed in this work.

New transport API:

| Operation | Actual CPython call | Accepted result |
|---|---|---|
| Readiness | `_overlapped.SetEvent(ready)` | exactly `None`, one attempt |
| Read | `_winapi.ReadFile(input, size, overlapped=False)` | exact tuple `(bytes, int 0)`, 1..size bytes |
| Write | `_winapi.WriteFile(output, raw, overlapped=False)` | exact tuple `(int len(raw), int 0)` |
| Close | `_winapi.CloseHandle(handle)` | exactly `None`; each original slot attempted once |
| Final wait | prospectively initialized `threading.Event().wait()` | must never return normally |

Positive partial reads accumulate in the unchanged `serve`; zero, over-budget, malformed tuple and any nonzero error (including ERROR_MORE_DATA=234) fail. Writes cannot be short and have no remainder retry. Boolean integers are refused in API tuples. Readiness cannot be repeated even after a failed first attempt. API exceptions become fixed main exit codes; exception text, handles and tracebacks are not emitted to either pipe.

The private Event is created before readiness and is never set. Its wait receives no arguments: no timeout, timer, periodic wake, new pipe read, clock sample or inference after K. Returning wait is an error. Closed or waiting objects cannot signal/read/write again. The original owner must enforce its previously bounded lifetime and teardown; this child does not extend it.

Initialization and cleanup:

| Exit | Meaning | Explicit close state |
|---|---|---|
| 64 | Invalid command arguments | ownership not accepted; process exit cleanup |
| 70 | Package loading/manifest validation failed | NativeTransport not constructed; no explicit attempts |
| 71 | Native setup failed after obtaining close API | all three slots attempted, all returned None |
| 74 | Native setup failed before close API was available | no explicit attempts; OS process exit is required |
| 75 | Native setup failed and some close failed | all three slots attempted once; failures retained |
| 72 | Serve/API/wait failure | unchanged serve finally attempts close of all slots |
| 73 | Serve finally encountered a close failure | all three attempted; at least one failed |

`close_attempted` and `close_failed` are local slot indices 0/1/2, not handle values. `NativeSetupFailure` retains the same tuples for constructor failure; successful cleanup does not imply initialization succeeded. Closing marks the object closed before attempting all three, so failed closes are not blindly retried. Main emits only a numeric exit status. On package/no-API failure there is deliberately no fallback loader or weakened isolation; explicit closure cannot be claimed, and A must confirm actual process exit/Job/handle cleanup. Tests use injected fakes and do not confirm OS cleanup.

Runtime and staging:

`runtime-inventory-c44.json` inherits exactly 633 C40 runtime rows (35,473,690 bytes), adds four C44 package rows (40,734 bytes), and lists 637 staged files / 35,514,424 bytes. It is an inventory, not a new stage or native run. Runtime rows were NOT all rehashed here. `local-api-pe.json` records this C machine's current CPython 3.12.14 API and selected PE bytes. `selected-runtime-current.json` additionally checks the base executable, threading source and LICENSE against inherited pins. The inherited runtime includes ctypes/libffi files; their presence is not evidence that this transport imports or depends on them. No ctypes fallback exists. Observed `_overlapped.pyd` PE imports are Windows socket/kernel, python312, VCRUNTIME140 and CRT system API sets, not `_ctypes` or libffi. PE closure does not establish AppContainer compatibility or identify A's original import failure cause.

`stage_package.py` is an exact copy of C40's lexical-path-checked helper. It was not run here. A owns its separately selected A632 adaptation and first native execution; neither A632 nor old A636 is represented as this C633 inventory. Public delivery should contain source, manifest and inventory only, not runtime binaries. The inventory identifies the Python license and system DLL boundary.

`c44_pair_verifier_v1.py` is exactly C41 with only `PACKAGE_MANIFEST_SHA256` changed to the new pin; `verifier.diff` proves the sole replacement. Its API and consistency-only semantics are unchanged. It does not authenticate a native origin or prove execution from status/hash.

Evidence and validation:

- `primary-source/`: original official CPython v3.12.14 source GET bytes, argv, API exits and hashes; `source-pins.json` pins old sources and A42 assignment/body record.
- `_winapi.c` lines 377–391: CloseHandle failure raises, success None; 1855–1903: synchronous ReadFile tuple and MORE_DATA behavior; 2141–2188: synchronous WriteFile tuple. `overlapped.c` lines 478–489: SetEvent failure raises, success None.
- run00: actual local API/PE inspection, exit0, no handle API call.
- run01: candidate construction, exit0.
- run02: 11 NEW controls, 10 passed, one fixture error before verifier admission: dict passed to original bytes-only framing API. Original test bytes and exit1 are retained. This was not a product failure.
- run03: corrected only that fixture's serialization and inventory metadata labeling/time; production package unchanged. The original inventory draft is preserved, including its placeholder timestamp; final inventory uses actual metadata creation time.
- run04: only corrected test10, exit0. Other passing methods were not repeated.
- run05: current base executable/threading/LICENSE pins and dependency source record, exit0.
- run06: one NEW main/API exception integration method (five synthetic fault subcases), exit0. Read/write/readiness/setup/close failures each attempt all available closes once with the expected exit code.

There are 12 unique NEW methods with successful final evidence across run02/run04/run06. No final all-suite rerun is claimed. Tests use fake APIs, fake Event and a fake package callback; callbacks are not C28 calls and their output is synthetic. The manifest/verifier control accepts a synthetic diagnostic rejection pair under the new pin, refuses the old pin and checks immutable output. Adapter and core are read/compiled for static syntax/hash comparison only, never imported or executed. No A actor/native handle API/model/PDE/board/service/credential/publication or old test suite ran.

H01–H15/original29/bothH12/final100MHz/timing/1%/100ms remain unchanged and unaccepted. Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804. Parent alone reviews and publishes; this directory is released at FINAL.

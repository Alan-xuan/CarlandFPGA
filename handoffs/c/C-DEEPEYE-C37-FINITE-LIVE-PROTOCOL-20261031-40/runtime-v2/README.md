# C40 finite live protocol candidate v2

Work C40-C37-A35-FINITE-LIVE-PROTOCOL-v1. Implements authenticated A35 comment6530717609 in a new private candidate; sealed C37 v1 and C39 remain unchanged. H01-H15 and DEEPEYE-HUMAN-LOCK-20261014/revision1 requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 remain unchanged and are not accepted by these software controls.

## Entry and lifetime

Proposed executable and arguments under an original approved stage:

```
runtime/python.exe -I -B c37_entry.py --actor-stdio-v2 --max-invocations K --request-bytes 16384 READY INPUT OUTPUT
```

The original owner appends its three distinct inherited handles. K is selected before launch, integer 1..16, and cannot be renewed by a request. The same initialized child signals the native model_ready_event once, then handles requests serially. It reads exactly 16384 bytes in chunks <=8192, computes at most once, writes the complete correlated READY+RESULT pair in chunks <=8192, and only then reads another request. The original provider must not pipeline; the child does not authenticate host scheduling or detect already buffered future bytes. Each complete valid-ID request, including disabled/rejected diagnostics, consumes one of K protocol slots.

First invocation_id may be any valid positive uint63; each subsequent ID must equal prior+1 and the other five echo_ids must stay identical. These are local consistency checks, not authentication. Oversized/truncated/noncanonical framing or invalid/replayed/cross-context identity is terminal before inference; malformed compact public data returns the unchanged REJECTED diagnostic with core_ran=false. Partial output is terminal with no retry or remainder replay.

After the Kth pair, no further pipe read, inference, output or clock sample occurs. NativeTransport calls kernel32.Sleep(INFINITE); it does not close handles or voluntarily exit after success. The original owner's existing bounded process lifetime and teardown remain mandatory. This is an owner-enforced bound, not a new child timer, lease, keepalive, process renewal or proof. Early EOF/IO/initialization failures remain terminal; owner termination reclaims the original process endpoints. The fake test models retirement with an exception and observes the fake serving thread alive before retirement. No real process/pipe/lifetime qualification ran here.

## Fixed request encoding

ABI `c37-owned-cpu-package/v2`; the compact inner C36 schema remains `c36_c28_public_view_v1`. Outer fields remain abi, kind='recommend', echo_ids, input and optional enabled (default false). Inner enabled is required and must agree. No proof boolean is added.

The total request is exactly 16384 bytes: four-byte little-endian 16380, then canonical JSON followed only by ASCII JSON whitespace to exactly 16380 payload bytes. Canonical serialization is UTF-8, sorted keys, compact separators, finite numbers, no duplicate keys. make_request pads with ASCII spaces; the decoder additionally accepts trailing tab/CR/LF. It rejects leading/internal noncanonical whitespace, non-ASCII padding, extra JSON values and oversize JSON. No fields/history are trimmed. request_wire_sha256 includes the length prefix and every padding byte. The host may prepare current input after initialization without changing the prospective size reservation.

Responses retain correlated READY then RESULT, at most 2048 and 16384 JSON bytes respectively, aggregate <=18440 wire bytes; the host's original <=64-read and <=8192 chunk policy must remain. Initialization event and request-correlated READY have different roles. READY is never a result, completion event or source proof. There is no unsolicited stdout; diagnostics do not print native handle values or exception tracebacks.

## Single frozen computation

frozen_c28.py is byte-identical SHA256 70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4. The same recommend.__code__ is called once per eligible enabled invocation through the inherited isolated globals with only _validate replaced. Numerical helpers/constants, exact absolute uint63 ns to Fraction(ns,1000000) conversion, source quality/held rules and output mapping are unchanged. Disabled or malformed input does not enter the core. A fresh computation may return STOP. Nothing here creates actual source/admission/current/capture/BOOT evidence; host C36 must fully validate and retain original proof before dispatch, with zero host core calls. Passing this compact child check cannot replace that gate.

## Unresolved genuine integration dependencies

A105 `2a5e57ff7dc78763bc98352e6cb02e2510d370ea` seals one raw response frame. Its unmodified API does not support this READY+RESULT pair, regardless of this child lifecycle fix. A owns the separately pinned pair extension, original one-use transcript/custody and aggregate budgets. No provider/native/multicycle acceptance is claimed here.

The recorded original host_envelope source is commit `5c192f34bad064b14e238747c2c569347257a62c`, path `competition/deepeye/integration/host_envelope.py`, SHA256 `025adf0eee851327f6492ac853b77bc6ebfbb26c17eb7960f01baf644de4b7fd`. Lines431–435 _check_candidate compare the scalar completed_monotonic_ns to caller now_ns, then validate target/observation. This does not authenticate when CPU inference finished. It is a historical pinned source, not verified current at A35. The child has no completion timestamp. A must specify how original dispatch/result-read/completion-observation intervals legitimately map to the original field and fresh result admission; projection.now, max(inputs), child time, arbitrary read-end or a claimed exact CPU finish must not be invented. input-pins-and-dependencies.json records the original GET evidence. No time adapter is implemented pending that original-source contract.

## Dependency closure and staging

runtime-inventory-v2.json inherits the exact 633 CPython3.12.14 runtime/license file pins (35473690 bytes) previously inventoried for C37 and substitutes only this version's four package files. No runtime binary is downloaded/copied or rediscovered. The original runtime rows are mechanically identical; their current on-disk bytes were not rehashed in this phase. The new stage helper is the sealed lexical-alias-rejecting C37 repaired helper, with only its returned arguments template changed to v2/K/fixed16384. Its source/destination checks, hashes, no-overwrite behavior and byte budget remain identical. It is not an actor launcher; K must be chosen 1..16 before launch. No staging was executed here. Stage completion, relocated runtime qualification, original ACL/package approval and native inherited-handle execution remain NOT_RUN for this candidate. Only trusted Windows system DLL/API dependencies remain external as in the prior inventory; no new third-party module is introduced. Runtime binaries are not public artifacts.

## Actual new controls and retained failures

run01: NEW test_c40_new.py, 25-second limit, exit1: nine tests passed; test05 assertion wrongly expected result.recommendation.action instead of the frozen result.status, raising KeyError. Original test bytes and raw stdout/stderr/exit retained. Product code was unchanged. Only that assertion was corrected, and run02 selected only test05: exit0. The nine already-passing methods were not repeated. Thus ten distinct new methods have passing evidence against the same exact package pins, across the two runs; this is not a claim that the final ten-method file was run as a whole.

Coverage: fixed padding/canonicality/full-wire hash and limit; 16 serial original-code calls, no 17th read; fake final wait alive until retirement; default-off and stale STOP; bounds and old-mode rejection; replay/context refusal; partial IO terminal; malformed input core0; high uint63 exact Fraction conversion. Synthetic fixtures carry no real proof/owner. No old suite, actual C36 host call, original actor/native/model/PDE/board, network, Git or public mutation ran. Any original host provenance/CPU completion/physical or final acceptance remains unproved.

# C37 owned CPU package, first invocation

This default-off package executes the same frozen C28 planner once on a bounded public input. It provides a concrete Windows inherited-handle entry and a hash-checked runtime staging helper. It does not grant host dispatch or completion authority. C36/A must retain the full original proof and bind its projection to the exact request, original process/package/pipe, one-use invocation, current source and host freshness checks.

Operation C-DEEPEYE-OWNED-C28-CPU-PACKAGE-20261031-37; task DEEPEYE-IMPLEMENTATION-20261014/version1. The previously published abi-v1/ABI.md remains unchanged. This runtime-v1 directory is the implementation delivery. C36 host implementation is separately under repair/review and is not approved by this package.

## Implementation and use

`c37-owned-cpu-package/c37_entry.py` verifies the fixed package manifest, initializes the inherited ready event and synchronous input/output handles, then reads the exact trusted request length. The original host supplies:

```text
runtime/python.exe -I -B c37_entry.py --actor-stdio-v1 --max-invocations 1 --request-bytes N READY_HANDLE INPUT_HANDLE OUTPUT_HANDLE
```

The ActorPolicy arguments end at N; its original launcher appends the final three handles. N includes the four-byte length prefix and is at most16384, so JSON is at most16380. No unsolicited stdout: the initialized native event is signaled; one complete request produces a correlated framed READY followed by RESULT. Read/write chunks are at most8192, total output at most18440, host maximum reads64. Short writes terminate without remainder/replay. More than one invocation is rejected. A's new105 serial transport is pending separate C39 review; it does not enable multiple invocations in this entry.

The compact input has the frozen nine-field public schema. All supplied fields validate before the disabled decision; invalid, contradictory or disabled input runs the core zero times. Enabled valid input calls the original `recommend.__code__` using a private globals copy where only `_validate` differs. Frozen C28 SHA256 is70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4. Numerical helpers/constants remain unchanged. Absolute uint63 QPC nanoseconds become exact Fraction(ns,1000000) internally and are restored exactly in output, without rebasing, rounding or invented action timestamps. Original held EM pose/time/counts are preserved. Child results explicitly carry authority=none and completion_grant=false.

`stage_package.py` materializes only explicit exact inventoried bytes into a new directory. It now rejects supplied root/ancestor/intermediate/final aliases before reads/creation. It does not launch an actor, fetch dependencies, overwrite/delete old files, or change services. Runtime binaries are not included. `runtime-inventory.json` lists633 existing CPython3.12.14 runtime files,35473690B, plus four package files. A must supply those exact bytes or review a replacement inventory and separately retain approved OS/system DLL, license, ACL and ownership conditions. No fallback interpreter or arbitrary dependency path is accepted from request JSON.

## Evidence and limits

- Author:16 NEW offline methods passed, exit0, on the unchanged delivered package/entry/core. Fake transport controls do not prove native handle behavior.
- Independent review: the original helper accepted three forbidden alias cases (exit1); an ordinary source passed. Exact637-file staging succeeded (exit0). A relocated synthetic smoke using the staged Python passed (exit0), with66 loaded file-backed module origins under stage and one original C28 code-object call. The first smoke exit1 was a reviewer framing/UTF-8 assertion error; original script/logs are retained. This is not exhaustive DLL-loader or OS ABI qualification.
- Helper repair: three original RED cases now reject. Twelve distinct completed controls pass across runs with exits1,0; run1 stopped at an actual file-symlink creation permission error. Eleven controls use actual paths, one simulates the stat mode. Actual file-symlink execution is NOT_RUN. No package tests or relocated smoke were replayed after this helper-only change. Main independently verified exact source/diff/raw evidence and closes C37-R1 as described in REPAIR-CLOSURE.md.
- `REVIEW-original.md` is the unchanged review before repair and correctly retains its original OPEN finding. `evidence.zip` preserves selected raw source/test versions, commands, logs and outputs; its index records original hashes. Runtime binaries and private native-session logs are excluded. The recorded683-file private review manifest covers the original stage as evidence, not files promised inside this archive.

Run `python -I -S -B verify_delivery.py` in this directory for byte/archive verification only; it invokes no planner or actor. `test_c37_new.py` is included for explicit reproduction, not automatically replayed by the verifier. Historical archive scripts retain original paths and are evidence, not an instruction to overwrite/reuse old destinations.

Actual original native event/pipe invocation, A provider integration, source/startup/BOOT/authentication, production control and physical board are NOT_RUN. C38's e794 finding remains valid for that exact old source; A's claimed108 fix and105 serial transport are pending separate C39 static review. Source approval here is limited to the reviewed C37 package and helper. It cannot close any missing C36/A proof or formal acceptance gate.

Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, source f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; fixed design1011259415a0916054eb580687612580bc1e5f09. H01–H15, original29, both H12 paths, final100MHz/timing and1%/100ms remain unchanged and unaccepted. A alone operates the physical board.

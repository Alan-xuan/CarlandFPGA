# C26 identity source proposal — execution closed

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`; work
`C26-IDENTITY-SOURCE-AUTHOR-20261029-v1`; operation
`C-DEEPEYE-OWNED-LIFECYCLE-IDENTITY-20261029-26`.
Author canonical identity: `/root/cpu_package_runner`. Sole current main:
`01a14025-4dfd-7ec3-aebb-57be48daba59`. A's source-only request is PR25
comment6481254925, original UTF-8 SHA256
`70e2a47121b3c4421fbccf9341d97537c6860ec861496e2bb656ef42941fed88`.

This delivery is an unapplied source proposal. It executes no identity collector,
candidate import, native API, actor, Job, case, model or controller. AST parsing
and compilation to discarded code objects are administrative static work; they
do not execute the compiled code and do not validate native behavior.

`ROOT.false.json` has `enabled=false`, `execution_authorized=false` and no nonce,
new guard or independent execution authorization. Each patched entry first calls
its local `_identity` gate. False/missing/invalid configuration rejects before
helper import, identity collection, Popen or native setup. The local gate also
unconditionally rejects if somebody merely changes those booleans. The helper's
`SOURCE_ONLY=True` and `require_root` independently have no success branch.
Consequently the identity bodies below are deliberately unreachable proposals.
Another reviewed source revision is required to implement actual authorization,
resource closure and staging. Changing flags cannot authorize this release.
These facts were inspected as source, never checked by importing/running it.

## Exact patch bases and private projection

`C25-identity.patch` is a four-target UTF-8 unified diff. Do not apply it to C25's
retained product, launcher or evidence directories. Its old bytes are:

| Target | Bytes | SHA256 |
|---|---:|---|
| owned_lifecycle.py | 49610 | c7063da8cecea366f2f0cced2f1e99357d779b927e3302464a0dc140e6a06b00 |
| case_actor.py | 487 | 17682adb9a79c029da231c2cc0faf2346154a49edad3ddd79890954f4e9e3c78 |
| run_once.py | 7199 | 791bc253963a3b9bdde737d4696b0340f3681f1274b2f8402c1620e277f129e3 |
| launch_once.py | 6221 | 4b0bd164b955e93c7a81881690850572a62edef3dc296db299755c6b06b4103d |

The first three are C25's exact committed product bytes. The fourth is the
original private Popen supervisor text embedded verbatim under
`private_original_Popen_supervisor_source.original_UTF8_source` in C25 EVIDENCE.
The author extracted UTF-8 bytes and verified its original length/hash before
projection. Old README, configuration, raw outputs, spent guard and seals remain
unchanged. Private `author/base` and `author/derived` hold all four text versions.
The administrative verifier independently restores every hunk to text in memory,
compares that result byte-for-byte to the derived projection, then parses and
compiles the four bases, four projections and new helper without exec/import.

The first static attempt found an inserted launcher block indentation error
(line67; exit1). Its complete source snapshot and raw stdout/stderr/exit remain
under `author/static-01-source-snapshot` and `static-01.*`. Corrections include
indentation, retaining binding errors separately from original execution errors,
and preserving raw `sys.version` characters. A later static check is attributed
to its own final-source hashes. Neither attempt is a runtime or lifecycle test.

The diff keeps the original C25 lifecycle code. It changes future operation and
paths to closed placeholders rather than reusing C25's configuration/guard/raw
directories. Future pin sets contain the four original product roles plus helper
and ROOT. The helper is bounded to32768B and SHA checked before its proposed
absolute sibling load; `-I` therefore does not require adding the script directory
to `sys.path`. No alternative PE selection or automatic retry is proposed.
Future staging must provide newly pinned six-source configuration and the new
launcher pin. That staging and its execution authorization do not exist here.

## Proposed identity and original-handle flow

The helper's future entry points are `capture_original_handle(handle, origin)`,
`capture_current()`, `emit_current(role=..., case=...)`, `actor_stream(...)` and
`observer_channel(...)`. All runtime entry points first reject through
`require_root`. Original process HANDLEs are borrowed, never reopened, duplicated
or closed by the helper. The original observer/outer owner retains all Wait and
Close responsibilities. The current self pseudo HANDLE is never closed.

Native capture records pointer-width HANDLE, capturing self PID, target PID,
actual image, creation FILETIME, origin, completeness and explicit unknown reasons.
Each API has its own inputs, original return and immediately captured LastError.
`GetProcessId` uses DWORD uint32 and zero means failure. Image query uses BOOL
int32, flags0, a writable2048-WCHAR buffer and in/out DWORD character count. One
attempt only: failure, zero/invalid returned length or capacity exhaustion leaves
image unknown and completeness false; no silent resizing or metadata fallback.
`GetProcessTimes` uses four two-DWORD FILETIME structures. Raw words and combined
uint64 integers are retained exactly, without float conversion. Creation is in
100ns UTC units since1601; kernel/user are durations. The raw exit buffer has
`exit_time_defined=false` in this probe and cannot prove exit, especially before
Resume. Only original Wait/GetExit evidence establishes exit. Successful BOOL/PID
returns define success; captured LastError is retained without overriding them.

Native prototypes follow primary Microsoft documentation for
[GetProcessId](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocessid),
[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)
and [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).
No native ABI/API was instantiated to verify these declarations. JSON consumers
must preserve integers; the two raw DWORD words avoid dependence on a consumer's
floating-point representation of the combined64-bit number.

Immediately after each successful original CreateProcessW, the projection reads
that PROCESS_INFORMATION.hProcess before Assign and Resume. Native PID must equal
that same PROCESS_INFORMATION PID and all required native queries must complete.
Failure retains the original native record and prevents Resume, using the
existing directed cleanup. Member slots are still registered before Create so
an exception before later Python flags cannot discard an acquired HANDLE.

Current self identity uses os.getpid and the current pseudo HANDLE only. Native
GetProcessId must match self PID. Runtime metadata includes raw sys.executable,
optional _base_executable, prefix/base_prefix, raw version and18 fixed flags.
Missing optional fields are null with an explicit attribute-unavailable reason.
Paths are bounded to512 characters, version384; no field is silently truncated.
These runtime strings and file metadata do not prove launch behavior.

## Exact channels and bounded handshake

The outer supervisor retains C25's original stdout/stderr FILE channels opened as
`RUN/stdout.txt` and `RUN/stderr.txt` and passed to the original Popen. These were
never an outer PIPE. Actor output alone uses the existing restricted CreatePipe.
The Popen was not suspended; it has no proposed pre-Resume outer thread claim.

The future outer records GetProcessId/image/creation from its original retained
Popen HANDLE immediately after Popen returns, checks PID against proc.pid,
performs original bounded Wait/cleanup, then validates the observer's first
stdout-file line before the original HANDLE Close. File output is at most8192B
for this parser and consists of exactly the observer handshake plus one bounded
JSON driver summary line (<=4096B). The original stderr file remains separately
measured in the total output evidence. A matching record binds original HANDLE
tuple, original file-channel association and nonce; it does not authenticate the
physical writer of every byte or establish ancestry. Raw file bytes/hash remain
evidence, with original native logs in a separate bounded owner artifact.

Actor grammar on its original pipe is exactly:

```
C26_IDENTITY <one ASCII JSON object> LF
C25_PRIMARY LF
```

or the unchanged `C25_OWNED_RESIDUAL LF` fixed second line for that role. The
handshake line including LF is <=3072B; total combined actor stream remains
<=4096B. No extra line or bytes, malformed/duplicate JSON keys, missing/extra
schema fields, wrong nonce/role/case, wrong native/self PID, image or creation
tuple may pass. Role is primary/owned-residual, case normal/owned-residual; the
observer uses role observer/case batch. Fresh nonce is exactly32 lower-case hex
characters supplied by a future reviewed ROOT, never derived from a PID.

Top-level handshake keys are schema (`C26.identity.v1`), nonce, role, case and
identity. Identity has self_pid, runtime and native. Native carries the full raw
self API log, origin/current self namespace PID, numeric pseudo HANDLE, PID,
actual image, lossless creation words/unit, completeness and unknown reasons.
It is compared to the independently captured original real HANDLE tuple; the
numeric pseudo HANDLE itself is not compared across processes. The complete
handshake must fit the cap, or emission fails. Length adequacy for this machine
has not been tested. Write count/flush failure is unknown; no retry is added.
Raw bytes, length/hash and complete self record are retained in pipe/file output.

The receiver validates all four nested raw-call key sets, input handles, API
order, integer types and successful return values against the selected native
identity. The image query retains its fixed capacity and UTF-16 code-unit output
length; creation/exit/kernel/user raw FILETIME words must be lossless and creation
must agree with the selected tuple. Live exit remains explicitly undefined.
Captured LastError integers are preserved without overriding successful returns.
These are checks of self-reported data consistency, not independent proof that
the reported calls occurred or that a particular process wrote every byte.

The original `exact_expected_line` output key in the private projection now means
both this exact handshake and the original fixed line match; EOF/Wait/exit/Close
remain independent gates. The owned set still comes exclusively from original
Create slots. Handshakes and Job PIDList cannot add members, replace handles,
backfill ownership or infer ancestors. Additional unknown members still throw
`job_membership_unknown`. The old unknown PID5356 is not investigated or
attributed. Residual remains an observer direct child, not a primary descendant.

## Original gates, limits and unresolved blockers

Normal still requires original primary exit0 and natural original Job0 by the
fixed exit-to-Job0 deadline. Cleanup termination followed by Job0 cannot satisfy
that gate. Negative still requires original residual HANDLE live plus original
same-Job accounting/PIDList before and after its fixed250ms gate, exact known
member identity, expected refusal, original Job termination, original waits,
verified final Job0 and every original Close. First snapshot completion<=gate and
second snapshot start>=gate remain intact. A failed normal blocks negative;
cumulative TotalProcesses is never treated as simultaneous membership.

Future plan only: one complete command<=30s, per-process512MiB, actor Job1GiB,
actor Job active2, total output<=1MiB. Original observer24/work20/cleanup4 and
outer wait26/cleanup29 boundaries remain. Queries and handshakes consume those
same budgets. Existing limits include <=256 events, <=65536B owner JSON and
finite4096B actor streams; new field overflow, API/serialization/time/cleanup
unknowns cannot pass. A final output count must include identity artifacts,
original lines, driver/supervisor files and their metadata/terminal tails. This
source does not enforce a hard disk quota or provide a general sandbox.

**Concrete execution blocker:** observer/driver and outer supervisor remain
outside the actor Job hard limits. PSAPI peak samples and sums are observations,
not hard512MiB/process or1GiB enforcement or complete-command budget closure.
Putting observer plus two actors in one Job would mean three processes; this
proposal does not change active2 to3 or silently exempt an owner. The unresolved
hard-limit membership/enforcement and final serialization/tail accounting need
another design and review before a new execution can be authorized. ROOT stays
false and these proposals cannot run. No behavior, API success, identity match,
control result or resource compliance is claimed by static compilation.

Root's pinned read-only PE/config metadata is referenced under
`main/PE-config-metadata.json`: target PE SHA256
`4623dc531b0883c3e714da5cb30e9b73e12aa5145f0d92c7b191ab1dcf699dfe`
and adjacent DLL `9930d881ee11a91f7fd43ab28d5305194fbd2f88ea4a07661453c6885f409afd`.
Three specified files exist and two pyvenv.cfg paths are missing. This author did
not rerun that metadata collection. MZ/path/version/imports are not startup or
loaded-image evidence, and cannot justify changing PE or retrying a case.

## Fixed requirements and historical status

H01–H15, both full H12 requirements and all29 points remain unchanged. Fixed
contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
design `1011259415a0916054eb580687612580bc1e5f09`.

C25 normal FAILED/negative NOT RUN, its cleanup evidence and unknown member
remain historical facts. C24 resource failure is not repaired or reclassified.
FORCE quality, sim_em/map/planner/runtime/H12/G03/G09/R03/board/formal gaps are
unchanged. Format/source review, transport ACK, software checks, native controls,
physical board evidence and formal acceptance are separate. A alone operates
the physical board. C26 grants no movement, runtime replacement, BOOT/clock,
controller/service/SQL/credential/lock/queue or publication authority.

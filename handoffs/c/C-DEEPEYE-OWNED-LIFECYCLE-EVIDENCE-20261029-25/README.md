# C25 owned lifecycle evidence: source and two new controls

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; author
`C25-OBSERVER-AUTHOR-20261029-v1`; operation
`C-DEEPEYE-OWNED-LIFECYCLE-EVIDENCE-20261029-25`. Base
`3e38757db74cdfe5a00a1868af8f93194e2b65d3`,1572 existing entries unchanged.
A original comment6478717675 exact UTF8 SHA256:
`6c43d4c38d3c99f25956e1b63fd5bd9a49798b330b77e2f4046eeb96a4c1d671`.

This is a small Windows original-HANDLE/Job observer for two **new** controlled
actors. Source-only author delivery is not execution or acceptance. Root alone
may run after frozen source/configuration and both independent static reviews.
Each case may run once, with no retry. It does not replay, repair or approve
C24: C24 producer/CLI0 and later cleanup do not change its original whole-batch
resource/lifecycle failure. The unidentified C24 member stays unidentified;
no retrospective PID scan or attribution is attempted.

## Fixed API and invocation owner

```text
run_batch(*, base_python:Path, expected_base_sha256:str,
          output:Path, expected_source_pins:dict) -> dict
```

There is no observer CLI, generic command/provider/factory input, fake mode or
background worker. Import defines ordinary Python source; kernel32 is loaded
only inside the authorized run_batch invocation. Module invocation is consumed
once, including a preflight failure. Root's original guard supplies cross-run
single-attempt enforcement; this local flag is not a persistent service/lock.

`base_python` and `output` are absolute native Path objects. Base PE is read
once with a64MiB+1 cap, verified against the external lowercase64-hex SHA and
MZ marker. The expected pin identifies root's previously verified **direct
base Python PE**, not a venv launcher. MZ/hash alone do not identify an arbitrary
executable as an approved interpreter. Paths reject reparse/symlink components,
quotes/NUL/newlines and lengths above1024 characters. Files/runtime must remain
stable; these checks are not authentication of a hostile Python environment.

`expected_source_pins` has exactly four keys `owned_lifecycle.py`,
`case_actor.py`, `README.md`, `run_once.py`; each value has exact `bytes,sha256`.
All four sibling files are bounded, hash checked and total<=256KiB before
native execution. Root separately checks the frozen files before and after
execution. `output` already exists and must be empty; root may keep its driver
intent beside this directory. Observer creates only `normal/` and
`owned-residual/` there and exclusive bounded `primary.combined.bin` /
`owned-residual.combined.bin` raw pipe files. No existing evidence is replaced.

Root-owned run_once loads the pinned sibling module by absolute path and calls
the API. A private ordinary supervisor owns its original Popen process HANDLE,
raw outputs and complete <=30s command budget. It may terminate/wait only its
original observer handle on timeout, never a discovered PID. No outer wrapper
is implemented by this author, and no product/native/control import or run was
performed by the author.

## Two precise cases

Normal creates one direct `primary`. Negative creates two direct children of
the **observer**: `primary` and explicitly `owned-residual`. Residual is not
represented as a child/descendant of primary. Actor code imports only built-in
sys/time, creates no process, loads no plugin/model/product module, opens no
GUI and dispatches only fixed role strings. Base Python still has its ordinary
interpreter/DLL startup; this is not a claim of zero OS module loading.

Actor argv is the pinned direct PE followed by
`-I -S -B -X utf8 <absolute case_actor.py> <fixed role>`. Primary writes exactly
`C25_PRIMARY\n`, flushes and exits0. Residual writes exactly
`C25_OWNED_RESIDUAL\n`, flushes, sleeps15s and then exits0 if not terminated.
Roles cannot select code, scripts, model files or subprocesses.

Each case creates an unnamed non-inheritable Job with these exact limits:

| Limit | Value |
|---|---:|
| Process committed virtual memory | 512MiB |
| Job committed virtual memory | 1GiB |
| Active processes | 2 |
| Job user CPU time | 20s in100ns units |
| Kill on last Job handle close | enabled |
| Breakaway / silent breakaway | absent |

LimitFlags is0x230C. CreateProcessW uses CREATE_SUSPENDED,
EXTENDED_STARTUPINFO_PRESENT and CREATE_NO_WINDOW (0x08080004), an explicit
application path and STARTF_USESTDHANDLES/hidden window configuration.
Only one pipe write HANDLE and a NUL stdin HANDLE appear in the inherited
HANDLE_LIST, installed through UpdateProcThreadAttribute. The read end is
non-inheritable. Job/process/thread handles are not inherited. stdout+stderr
share one pipe per actor. The owner retains original PROCESS_INFORMATION,
process/thread handles and original Job. AssignProcessToJobObject occurs
before any ResumeThread, and ResumeThread must return previous suspend count1.
Assignment/limits/size/API failures block and clean; no breakaway fallback.

Before any Create, events record fixed deadlines: observer24s total,20s work
cutoff and4s cleanup reserve; primary wait<=5s, negative residual-line readiness
<=2s, normal primary0-to-Job0<=1s and negative gate250ms after observed primary0.
These relative deadlines are not widened by remaining budget. Each derived
absolute monotonic gate is recorded before its wait/poll. Native calls and
host scheduling are not hard realtime; actual late return cannot pass.

In negative, residual is assigned/resumed and its original line is observed
before primary is resumed, avoiding a false startup race. Original primary
HANDLE must become signaled and GetExitCodeProcess must report0. Immediately
after primary0, original Job accounting/PIDList is retained. At/after the
fixed250ms gate, the owner retains another same-Job snapshot and checks the
original residual HANDLE again with timeout0. Both Job snapshots must show
exactly active1 / complete PIDList containing the originally created residual
PID, and original residual HANDLE waits must return WAIT_TIMEOUT, including
the post-gate check. The absolute gate is recorded before the first snapshot.
Each snapshot retains its actual sampling start and completion times; the first
must complete at or before the gate, and the second must start at or after it.
A late first snapshot fails and cleans without retry. This brackets separate original observations; it is not
an invented atomic multi-API snapshot or an A clock binding.

That condition sets expected_rejection=true while lifecycle_gate_passed stays
false. The owner requests TerminateJobObject once, then waits every retained
original process HANDLE, queries final original Job accounting/PIDList0, drains
to EOF and closes original process/thread/pipe/NUL/Job handles. Request success
alone never establishes termination. For interrupted/unassigned Create/failed
Job cleanup, only an originally returned process HANDLE may additionally be
terminated, never a PID. Such unexpected errors still cannot pass.

Normal must observe primary0 and original Job active0/empty PIDList within the
fixed1s exit-to-zero gate. It then independently confirms cleanup0, original
HANDLE signaled, EOF and every required Close result. It does not need an
unnecessary TerminateJob request after a proved natural Job0.
Negative starts only after normal proves final0/signaled/Close/control gates.
A failing normal case does not trigger retries or an extra experiment.

## Evidence and cleanup rules

PROCESS_INFORMATION and pipe HANDLE output slots are registered **before**
their Create calls. Cleanup inspects the original native fields even after
BaseException or an interruption before Python created/assigned flags update.
No global/session enumeration, OpenProcess, PID reopen, IsProcessInJob lookup
of other processes or unknown PID kill is used. JobObjectBasicProcessIdList is
queried only on this original Job into a fixed2-PID buffer. Truncation/error,
unexpected PID or unknown membership vetoes success; it never authorizes a
PID lookup. QueryInformationJobObject classes1/3/9 preserve accounting, member
IDs and limits/peaks. TotalProcesses is explicitly **cumulative**, never a peak
concurrency metric. Kernel active2 enforcement and original active snapshots
are separate from that cumulative field.

BaseException cleanup targets only original returned process HANDLEs and the
original Job. Terminate/Close are not retried after an unknown result. Required
created HANDLE labels are checked against successful Close records, so a set
flag alone cannot certify a Close. The current-process pseudo HANDLE is not
an owned handle and is never closed. Attribute-list deletion is a void API;
its return-without-exception is logged as that contract, not a fabricated BOOL.

The program cannot promise recovery after its own hard crash, machine loss or
an outer kill in the transient suspended Create-before-Assign interval. Normal
Python BaseException paths inspect original PI handles and clean this interval;
an unobserved abrupt loss remains unknown, never PASS. Kill-on-close covers
members actually assigned to the original Job. No PID-rescue operation is
introduced to hide that limitation. Original root supervision and actual exit
and cleanup evidence remain necessary.

Each synchronous read is bounded by remaining4096B per stream. PeekNamedPipe
precedes a ReadFile of at most the already available byte count; no other
reader exists and pinned actors emit one tiny line. No pipe-read threads or
unbounded buffered wait/drain is used. EOF and exact original role line are
required. Failed/partial raw file writes, missing EOF, output excess or unknown
read completion vetoes success; unknown total output is null, never recast as
captured bytes. Raw files use exclusive creation. These byte caps are not an
OS disk quota or protection from a compromised filesystem/runtime.

Ordered events preserve API inputs, actual returns/GetLastError, original
HANDLE/PID identities, assign-before-resume, waits/exits, pre/post gates,
same-Job snapshots, cleanup/termination and Close results. Event count<=256,
event payload budget44000B, owner JSON including LF<=64KiB. Logging errors/
overflow never prevent cleanup and always veto success. Exact raw actor output
is at most3*4096B, plus<=64KiB observer JSON, within1MiB. If a report would exceed
its cap, a small explicit failed report marks lost proof rather than claiming
success. No raw output is reinterpreted as a model, transport or physical result.

## Memory scope and return value

Same-Job extended accounting retains PeakProcessMemoryUsed and
PeakJobMemoryUsed with their actor Job scope. Observer memory is separately
sampled using K32GetProcessMemoryInfo on GetCurrentProcess's pseudo HANDLE and
PROCESS_MEMORY_COUNTERS_EX; PeakPagefileUsage is the lifetime peak private
Commit Charge, not working-set size. The observer is **not** governed by its
child Job hard limits. Before cases, after cleanup/Close and after initial
report materialization, actual owner peak is recorded. Unknown/zero query,
owner peak>512MiB or max actor-Job peak + owner peak>1GiB cannot pass. The sum
is a conservative sum of sampled lifetime peaks, not measured simultaneous
allocation. Parent sample cutoff excludes later serialization/driver/supervisor
growth and unrelated host processes; root retains the outer process evidence.
This is neither a whole-host memory measurement nor a general security sandbox.

Top-level returned dictionary contains `schema_version,operation_id,status,
all_cases_passed,cases,budgets,cleanup,evidence,C24_validation_upgraded,
formal_acceptance`, with bounded reason on failure. `cases` names are `normal`
and `owned-residual`; each distinguishes `lifecycle_gate_passed`,
`expected_rejection`, `control_passed`, original raw gate snapshots,
`final_job_zero`, `all_original_handles_signaled`, `all_closes_succeeded`, raw
output and explicitly created members. A skipped case is marked attempted=false.
Top all_cases_passed requires both new control oracles plus complete cleanup,
measured resources, output, deadline and evidence gates. A successful negative
control never becomes lifecycle success. There is no authorization output.

## Static sources and preserved limits

ABI layouts and prototypes are reviewed against primary Microsoft references:

- [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)
- [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
- [QueryInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)
- [Job PID list](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list)
- [Extended Job limits/peaks](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)
- [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)
- [PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex)

Win64 sizes are checked only at authorized runtime: SA24, STARTUPINFOEX112,
PROCESS_INFORMATION24, BASIC_LIMIT64, EXTENDED_LIMIT144, ACCOUNTING48,
PID_LIST(two)24, PROCESS_MEMORY_COUNTERS_EX80. Static AST checking does not prove
these runtime ABI/native results. No author product import, Win32 call, actor,
smoke/control or old test was run. Root must retain genuine static approvals,
raw one-shot cases and exact hashes/exits before claiming any new control pass.

H01-H15 remain fixed: contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
frozen design `1011259415a0916054eb580687612580bc1e5f09`.
Both full H12 paths/all29/G03/G09/R03 remain unmet; candidate data approval,
new-domain model, online endpoint/P95 and C24 complete validation are not
upgraded. FORCE quality remains FAIL. Only A operates the physical board.
No A factory/HANDLE/interface or old C22-C24 byte is changed. The original C
main remains the only publication/acceptance owner; no group announcement,
service, model polling, lock/credential/controller/SQL/queue change occurs.

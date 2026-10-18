# Verifier reentrancy and audit-alias repair

Work: `C-motion-adapter-verifier-reentrancy-fix-20261018-v1`,
`DEEPEYE-IMPLEMENTATION-20261014/version1`. Original source head:
`31267d6c4ae284b8788ebb457f49c4ae5a49c60c`. Fixed design:
`1011259415a0916054eb580687612580bc1e5f09`.
Human contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
All H01-H15 remain unchanged. Scope identity passed; this is not product acceptance.

The input is [A's later PR25 feedback](https://github.com/carolwjade/CarlandFPGA/pull/25#issuecomment-6206605911),
following [approval5541868728](https://github.com/carolwjade/CarlandFPGA/pull/25#pullrequestreview-5541868728).
Their raw authenticated GitHub API responses, commands, exit codes and byte
hashes are preserved here. The later feedback identifies public callback
reentrancy: candidate10's verifier can emit candidate11/seq0 STOP, then return
None and let the original source emit stale candidate10/seq1 SET_TARGET.
It also identifies a shared OriginalTiming object: forcing mutation through a
retained verifier check changes the decision's returned audit.

Before edits, `pre_repair/` preserved the actual original adapter and test
bytes. Both were compared byte-for-byte to their exact base Git blobs;
`original_manifest.json` records SHA256, Git blob identity, source head and
contract. No old run001/run002/run003 files or evidence were modified.

The repair keeps safety STOP callable inside the verifier. A constant-size
generation token changes on each newly registered observation, valid candidate
retirement (including a subsequently blocked candidate), and valid STOP call
(including identity exhaustion). The token captured before verification must
still be current before an outer request can emit. A newer generation returns
`must_stop=True`, `request_bytes=None`, `reason='superseded_during_verification'`.
Newer high-water marks, STOP bytes and command allocations stay intact. Reads,
exact observation duplicates and invalid calls produce no generation change.
There is no blanket public-method lock and no additional history ledger.

The verifier receives fresh context, observation and timing objects. The
authoritative OriginalTiming returned to the caller is never given to the
verifier. Forced mutation of a callback snapshot during verification or after
return cannot change the original sample, issue or deadline audit. Private
attribute tampering and cross-thread synchronization remain outside this
single-owner helper's stated contract.

Before the source repair, eight new targeted test methods ran against the
unchanged original source. `red_original` records exit1 and ten assertion
failures (subtests included), including the exact stale candidate10 bytes and
the changed timing audit. This is a real unsafe RED, not a passing safety gate.
`red_test_motion_request.py` preserves those exact test bytes. The same RED
can be replayed without overwriting current source:

```powershell
python -B -X utf8 competition/deepeye/evidence/ai/motion_request/review_repair2/replay_original.py
```

Run that command from the product worktree root. Its expected exit is1;
`red_original_replay` records the same eight methods and ten failures using
only the preserved original source and RED tests.

The repaired source first passed the eight targeted methods (`green_targeted`,
exit0). A ninth targeted method then checked nested STOP at candidate identity
exhaustion. The complete current adapter suite passed38 tests; existing
mailbox44 and deadline34 tests also passed (116 total, all exit0). Those suites
include unchanged exact-blob A schema/target interoperability tests. New cases
cover nested STOP at equal/later time, newer blocked/accepted candidates,
observation registration/eviction, harmless reads/duplicates and rejected
calls, detached timing during/after callbacks, verifier exceptions/non-None
results, and exhaustion without reviving outer motion. All fixtures remain
explicitly synthetic; no runtime verifier proof is claimed.

The `.command.json` records contain the exact interpreter arguments, working
directories, timestamps, expected and actual exit codes, tested source hashes
and raw stdout/stderr identities. `manifest.json` inventories every new
evidence artifact and the final source hashes. Git diff whitespace checks
passed. Changed production/test paths are limited to `motion_request.py` and
`test_motion_request.py`; all new evidence is inside this repair2 directory.

Missing measured clock/source/model liveness, transport/ACL integration,
PC_DIRECT/HIL execution, physical board and system acceptance remain not_run.
The default absent runtime verifier still blocks motion; every decision still
reports movement_authorized=False. No A schema, grant authority, service,
credential, SQL, hardware or external publication change was made.

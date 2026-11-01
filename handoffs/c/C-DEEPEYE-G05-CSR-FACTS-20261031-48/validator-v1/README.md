Main delivery note: exact repair module 925ca8ec has bounded independent source approval; see REVIEW.md and main-approval.json. Historical pending/rejected statements below describe predecessor stages and are superseded only for this exact repair.

# C48 G05P pure CSR bridge — bounded delivered slice

`g05_csr_bridge_v1.py` performs bounded detached consistency validation. It does
not import A's issuer, access a device, sample a clock, invoke a planner, accept
a provenance callback, register an owner, or grant motion/source authority.
Only C48's new private implementation directory is writable. C49 independently
owns the opt-in runtime/profile/channel changes. Original classes, four C42 pins,
legacy defaults, native actor, executor/CAS and final fences are untouched here.

The fixed contract is DEEPEYE-HUMAN-LOCK-20261014 revision1, requirements
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, design
`1011259415a0916054eb580687612580bc1e5f09`. All H01-H15 and both H12 remain.
G05P/layout2/50MHz is an explicit development profile, not final 100MHz acceptance.

## Published transaction entry

```python
validate_transaction_v1(
    facts_raw: bytes, *, policy_raw: bytes,
    expected_identity: tuple[int, ...],
    expected_commands: tuple[tuple[int, ...], ...],
    stop_requested: bool,
    host_qpc_interval: tuple[int, int],
    host_clock_domain: str,
) -> DetachedFacts
```

The input is the exact A210 result-object JSON, not the outer transport envelope.
C49/Root must first retain and associate the original request/response and their
enclosing host QPC bracket. Each JSON receipt has `index`, `started_raw_hex`,
`returned_raw_hex`; original byte strings are preserved without canonicalizing.
The full input/policy bytes are returned as `facts_raw`/`policy_raw` too. No helper
converts arbitrary objects into original producer identity.

This branch matches published A207/A210 at
`f65f31dfb73dd4a86fcd7b8824dd14dd75f1ee11`:

* A207 functional50_g05_transaction_a.py SHA256
  `480ef6c485933db9766c2f6fab45df081b1b913a9005561b4f416ec303ebfbcf`.
* G05 port functional50_g05_a.py SHA256
  `a25b26f6a4c58bd65dbacea865b3d356fe6a10cc07a51e38794c2f020ebcbe9e`.
* A210 board encoder functional50_chain_board_a.py SHA256
  `4d951a1163992e4f1170592d1f5c9466a2f337b78ff19be841037de5ccaa5011`.

Raw GET outputs, exact argv/exit, source tree and Git blob equality are in
`source/` and `source-tree.json`. These sources are read only; no A script runs.

Operation is taken strictly from exact policy.binding.operation_id. Policy has
the five original binding fields and all six finite quotas. Full source/request
digests, canonical board boot UUID, nonzero 128-bit build identity and policy
canonical digest are checked. Digest equality proves only consistency. All 13
numeric identity words remain distinct from legacy context7/C42 context8 or tag.

The parser consumes an exact finite method sequence: original factory reads
G05P/layout2/status/fault; identity stage; BEGIN with statuses; all 13 actual
identity readbacks; each original seven-word stage/acceptance; global bounded
status polling; LATCH; status/sequence-bracketed full32 snapshot; RELEASE; optional
selected STOP and actual status/fault. It rejects omitted/extra/reordered IO,
missing return, differing intent/return identity, request-ID noncontiguous reuse,
PID replacement, bool-as-int, unknown fields, malformed JSON and duplicate keys.
Repeating the same request ID within a single original multi-IO method is valid.
Seven selected words are associated with accepted command sequence; they are not
used to synthesize captured motion output. B132 owns output decoding/equivalence.

Input limits: result <=1MiB; policy <=128KiB; IO1..2048 (complete prefix has at
least four entries); each raw started/returned <=4096B; commands1..16; global
polls<=1024 for A207. The A210 wrapper's narrower 2/64 selection does not silently
replace A207's published limits. Each phase's actual source must select its own
limits. Integer board/host nanoseconds are uint63; all CSR words are uint32.

Initial factory IO completes at or before deadline selection. Later intent timestamps must
be inside the selected fixed board deadline, with ordered started<=returned and
previous-returned<=next-started. A final MMIO return at/after deadline remains
actual evidence: no in-call hard timeout or early return is fabricated. The
selected deadline is finite <=10 seconds and never renewed. Host QPC is a
separate caller-supplied enclosing interval/domain; this function does not verify
actual clock provenance or equate host ticks with board monotonic/cycles.

DetachedFacts preserves identity, accepted_commands, original captures,
status/fault, deadline selection/deadline, original receipts, host interval/domain,
full input bytes, phase_io_first/last and authority=`not_evaluated`.
Transaction state is `TRANSACTION_COMPLETE`, not a claim that the board stopped.
CaptureFacts preserves all32 words and `tick_unit='50MHz_cycles'`. Exact RTL at
Morde-cloud/CarlandFPGA `dd52028af809363bd445fae8e7b4cf10ec7753ad`, wrapper SHA256
`99cdb09399466966458343351d0d941191f34cc9af6f9808c5fb3cc58086ea5a` lines220–235,
defines words0=result_seq,1=command_seq,2=tag,3=speed8/profile8 with high16 zero,
4=pitch16/yaw16,5=ttl16 with high16 zero,6/7=applied64,8/9=deadline64,
10/11=result64,12..14=period32,15..17=high32,18..23=start64 per channel,
24..29=end64 per channel,30=numeric session,31=G05P magic.
The original engine SHA256 `fcdb04d1e307506328c205154730e1cf8c5bff2efe72727a46a2f3f4b856ed8a`
lines201–223 supplies coherent nonwrapping witness invariants. The validator checks
global applied<result<deadline, and separately local 0<high<period,
0<start<end<=UINT32_MAX, end-start=period, and joined
channel starts/ends within one cycle. It returns immutable CaptureCycles with
original global uint64 values (including above2^63) and independent zero-extended
local uint32 witnesses. It does not infer an offset between their origins. Submitted metadata matches
the seven accepted words; measured PWM is not replaced by command echo. B132
still owns PWM-to-motion decoding, physical wiring and transfer equivalence.
No cycle value is compared to or converted into host QPC. CSR alone cannot
establish a sensor origin; `sensor_origin='not_established_by_csr'`. Root/C49 must
preserve actual source4 as simulation even after real physical TRACE transport.

## Published session v2 entry

The implemented signature is:

```python
validate_session_v2(
    facts_raw: bytes, *, policy_raw: bytes,
    expected_identity: tuple[int, ...],
    expected_command: tuple[int, ...] | None,
    previous: DetachedSessionState | None,
    host_qpc_interval: tuple[int, int], host_clock_domain: str,
) -> DetachedFacts  # includes next_state
```

The previously missing A216 is now pinned at actual A source
`0469345fd1eef2884de1417f0f4eb5b67688f84c`:

* functional50_g05_session_a.py SHA256
  `646d0b8e65d6aaf8c527fba83f61a996124a5f448c488d4e2f98bf6a1bc8215d`.
* functional50_chain_v2_board_a.py SHA256
  `f19769e8ad13c90897d590b68ff56269141346a41bcc9a3a793a5a2fc983f0fa`.
* Original G05 port remains exact `a25b26...be9e`, unchanged from A207.

Exact grammar: init includes all factory receipts but phase starts at5, stages
identity/BEGIN, reads13 words, then fresh status/fault (39 cumulative IO). Apply
first re-reads13 identity words, then command/capture/release grammar. Apply
facts.status/fault refer to the poll before latch, not the release status. Status
re-reads13 identity words then status/fault. Close(stop=False) has no new IO and
both phase bounds/status/fault null. Explicit STOP close has exactly write3 plus
actual status/fault reads. It remains a software CLOSED state, not electrical
stop proof. The API has no separate close-stop intent parameter: the original
Root caller must correlate original request.stop with these exact returned IO;
this pure function validates only the actual facts it receives, not authorization
to issue STOP. Original producer correlation must reject unsolicited effects.

Only COMPLETE/ACTIVE or COMPLETE/CLOSED facts produce DetachedFacts. Nonempty
unresolved_receipts or CLOSED_AFTER_FAILURE raises Rejected, even if some raw
operations returned. The original caller must retain the entire original response
and irreversible unknown state; it cannot turn refusal into STOP/healthy output.
This slice does not attempt to recover unknown effects or decode partial tails.

Previous.next_state contains exact policy/identity/domain plus all prior original
phase JSON, selected commands and enclosing host brackets. Every supplied prior
phase is revalidated, including byte-identical cumulative receipt prefix,
immutable deadline, nondecreasing host intervals, init once, <=2commands,
increasing command/result sequence and no phase after close. This is detached
history; a caller can construct it and it is not an authentication or one-use
token. C49/Root's original retained event ledger must provide actual ownership
and consumption. No callback, verified flag, hash or JSON is authority.

The session budget counts all status-register reads, including hidden method
reads, excluding factory status. Exact64 allows,65 refuses. Current A218 encoding
adds <=450 cumulative receipt indices and <=512B per started/returned record;
those limits apply here in addition to policy. At most68 retained phases and
68MiB aggregate prior JSON keep validation finite. Revalidating history has cost;
actual source-owner cadence/performance has not been qualified. There is no new
quality relaxation, source-age selector or altered frozenC42 gate in this pure
CSR module. Operation-bound demo budgets belong to the actual Root selector and
never grant IO/motion. Default source/AI validity remains outside this validator.

## Evidence and resume

Original work was interrupted by quota termination without product FINAL; main
verified actual stopped calls/processes and preserved a62-file ZIP. Resume is
the same owner/taskversion1, work version2, not a second writer. All12 A55–A73
saved bodies and the unchanged H01–H15 contract were read. New pins and computed
body hashes are in resume-source/. Actual source uses original issuer/encoder
and RTL only; no already supplied provider/type is reported missing.

| phase | exact scope | result |
|---|---|---|
| run01 | earlier A2075 NEW methods | exit0; earlier source only |
| run02 | earlier exact policy/raw preservation method | exit0; earlier source only |
| run03 | NEW7–12: A216 grammar/prefix/caps/close/unknown/layout32 and affected v1 positive | 6 methods exit0 |
| run04 | NEW13: exact64 allows/65 refuses | 1 method exit0 |
| run05 | NEW14: factory return equals selected lower allows; one nanosecond after refuses, both APIs | 1 method exit0 |

Every process had a25-second timeout. Final source is the run05 version, adding
only the common factory-return-before-selection rule to run03/run04 source.
Those prior passing methods were not rerun after that narrow change; their exact
versions remain available. Old5 methods were not rerun and their opaque-cycle fixture is
historical. All executed versions are retained. New controls reuse only the old
C48 fixture constructors, not its test methods; this dependency is separately
pinned. Fixtures synthesize receipts and never import/execute A's producer or
RTL. Original stdout/stderr/argv/exit and invalid inputs remain intact.

One resumed RTL fetch attempt failed before network GET with Windows path length
206. Its original script and native error are retained; a shorter private archive
path then fetched the same exact immutable source once, exit0. No service/Git/
credentials/old-suite/C28/model/PDE/native/board execution or publication occurred.


## R1 successor: separate global and rearm-local cycle domains

This replacement is pending independent rereview. The previous 814783f module
and draft are not approved. The original review run02 exit1 and exact input
remain unchanged in predecessor-review/. Earlier passing positives used
global-sized local witnesses and do not establish valid RTL domain behavior.
Their original outputs remain historical; they were not rerun or relabeled.

At fixed dd52028af809363bd445fae8e7b4cf10ec7753ad, engine98–103 zero-extends
32-bit capture witnesses, while385/407 retain global result/application clocks.
The actual primitive competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv
SHA256 4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456
sets tick=0 on rearm (178–181), takes witness=tick+1 (230), and records that
positive witness at239/315–316. Therefore local start0 is refused. No inferred
global epoch or offset is added. Matching units do not imply a common origin.

repair01 executes only13 new domain controls against925ca8ec: local20/global>2^63,
local1, uint32 upper boundary, retained history/software close, v1 shared capture,
and impossible high32, zero, reversed ordering, period/high/join violations.
All pass with raw inputs/outputs and executed source retained. Fixtures are
synthetic; no A producer, RTL, native, core, model or board was executed.
repair02 only applies both replacement and incremental patches to bytes and
checks exact equality. Neither grants authority or proves physical mapping.
All H01–H15/both H12 and original fixed requirements hash remain unchanged.

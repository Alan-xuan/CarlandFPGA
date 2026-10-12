# C controlled cohort preparation v1

Owner: C/Astra-C, official gpt-6-astra / ultra. Task:
`MESH-20261011-132845-c94f2686-controlled-cohort-C`, version 1.
Work: `C-controlled-cohort-preparation-v1`.

This package is preparation only. No nonce, ARM, outage, original Task Stop or
original Task Start has occurred. No physical hardware is involved.

## Evidence already complete

`reused-obligations.json` reuses PR4 APPROVED review 5490272933 at head
0c44e6fa05b37cadb810fab29c0e729880b18dd9, including the original real GitHub API
response hashes and the completed controller terminal receipt. No second API
read, ACK, test suite, PR or merge is necessary.

It also records the three exact original inbound message IDs, raw UTF-8 payload
hashes, received/processed times and completed original main results. These are
historical receipts; they do not establish a new all-online cohort or successful
B/C communication while A remained offline.

## Current waiting program

`prepare_standby.py` runs once under an ordinary Scheduler task with the original
principal/logon/runlevel (Interactive/Limited), one trigger, zero restart count,
IgnoreNew concurrency, and a bounded execution time. It has no model dispatch,
stop/start or ARM acceptance capability. It uses the original resident's
`main_wait` event to observe this preparation turn's actual terminal result.
After the parent review and hashes match, it rereads health and real Job
isolation, then makes exactly one READY submission through the original
resident's durable peer outbox. An unknown submission outcome is not replayed.
It subsequently waits unarmed for up to 30 minutes and exits.

`standby-isolation.json` contains measured PID/creation/parent evidence, full
original Task XML fingerprint and actual original supervisor Job membership.
The original full XML and local principal remain local and are excluded from
public checkpoints. Parent chain alone is not isolation proof.

## Root-controlled final scenarios

1. **All online:** Root chooses fresh fixed nonce(s), exact direction/message IDs,
   task versions and a UTC interval. Each peer sends via its existing resident
   exactly once. Receiver evidence includes original inbound raw payload hash,
   received time, terminal main result/model/effort/turn and result hash. Outbox
   transport ACK and terminal model processing are recorded separately.
2. **C original control plane offline:** After all current preparation work is
   terminal, Root authorizes a short fixed stop/recovery interval. Recapture the
   original Task XML, service root/supervisor/worker/all descendants and the real
   Job, because preparation PIDs may have changed. A dedicated one-shot C guard
   must positively prove it is outside that original Job and publish readiness
   bound to the immutable armed plan before any stop is allowed. An external
   stop driver must hold all three `stop_idle_node` ledger writer locks and prove
   every actual main/child/inbound obligation idle. No fabricated completion,
   queue clearing, human pause, interrupted-side-effect replay, or parallel
   controller/sender is permitted. A and B measure new bidirectional messages
   and completed model receipts during C's proven offline interval.
3. **A original control plane offline:** A owns its independent recovery guard.
   B and C use their original residents to exchange new fixed messages in both
   directions. Preserve sender outbox ACKs plus both original inbound hashes and
   durable terminal model receipts. Root correlates all timestamps against A's
   measured offline/recovery interval. Late receipts outside that interval do
   not qualify as offline bilateral success.

## Recovery contract

The C recovery guard is derived in `derived/` from the hash-verified A reference;
the A guard is never executed. The future root ARM binds a new fixed nonce,
operation, plan hash, preparation time, restore time (at most 10 minutes later),
expiry (at most 2 minutes after restore), original full XML, original PIDs with
creation/parent identities, and actual original Job evidence. The raw plan file
is immutable. Only a matching STOP_ATTEMPTED phase can permit recovery.

Before one original Task Start, both UTC and monotonic windows must remain valid,
the old service leases must be released, all bound old PIDs must be absent, and
the original Task must be Ready with exactly unchanged full XML. A unique
durable exclusive Start claim precedes the sole Start command. Unknown outcomes
never retry. Success requires actual fresh resident health, Feishu connection,
network/transport readback; an accepted Start command alone is not recovery.

No recovery schedule or armed plan is installed by this preparation. The
unarmed standby PID proves the permitted Scheduler launch/isolation mechanism;
it is not claimed to be an armed recovery watcher. Root's later ARM must launch
the reviewed bounded guard and obtain its own matching READY before Stop.

`stop_prepared_c.py --armed-plan-sha256 <exact raw hash>` is the staged external
stop driver. It has never been used against C. It requires the exact immutable
armed plan, the matching live recovery guard PID/creation/parent and READY,
its own real Job isolation, all three existing ledgers, and an actually idle
fence before its single fixed Stop. It records a unique stop claim and holds
the writer locks through the old service lease and PID disappearance checks.

## Validation scope

Only focused C fake refusal/success/at-most-once/window tests apply. A's prior
25+15 fake tests remain A evidence. No full suite or original 28 tests are rerun.
No fake evidence is described as a real stop/restart or hardware result.

Root declares final acceptance only after all scenario obligations are terminal,
the original services are healthy, no active tests remain and no side-effect
outcomes are unknown. This preparation does not make that declaration.

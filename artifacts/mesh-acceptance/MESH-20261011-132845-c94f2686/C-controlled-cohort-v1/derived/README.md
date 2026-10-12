# C outage restoration guard v1 (derived, unarmed, not executed)

Derivative of A's reference v7 for round `MESH-20261011-132845-c94f2686`, fixed
to node C's Task, paths, ladder and original Task/PID identities. This package
was written and unit-tested with fake probes only: no real ScheduledTask,
process, service, network, model, config or ledger action was performed, and
the guard itself has not been run against the live Task.

## Provenance

Reference files live in `../reference/` and were hash-verified by the parent;
hashes recomputed here match `../reference/MANIFEST.json`:

| reference file | sha256 |
|---|---|
| `ab_outage_guard_v2.py` | `c103302049b194cfcce7340a83afa829dca59f32c90324884694495767a8d687` |
| `service_job_isolation.py` | `57a2a1ff9cf808954bee83ce20d1cd5db12732110d2eaaf5004bfd5b5c1c4ade` |
| `test_ab_outage_guard_v2.py` | `f1e19968662e066c1217e8f0ed10e52c07af06ed1444fcb0bfa79ad56f547d06` |
| `test_ab_outage_guard_v3.py` | `1a6d74ac22cc19b443a15cc4c38588aaabb0ebfe16eeb535db53342d7709fea1` |

Derived here: `c_outage_guard_v1.py`, `service_job_isolation.py` (docstring
only difference), `test_c_outage_guard_v1.py`, this README.

## Fixed identity

| item | fixed value |
|---|---|
| round | `MESH-20261011-132845-c94f2686` |
| node | `C` |
| Scheduled Task | `\FPGA-Mesh-Node-C` |
| task_id | `MESH-20261011-132845-c94f2686-controlled-cohort-C` |
| work_id | `C-controlled-cohort-preparation-v1` |
| task_version | `1` |
| owned output dir (plan/phase/ready/attempt/log) | `<repo>/artifacts/mesh-acceptance/<round>/C-controlled-cohort-v1` |
| scripts | `.../C-controlled-cohort-v1/derived/` |
| helper interpreter | `<repo>/.local/venv/Scripts/python.exe` |
| shell | `powershell.exe -NoProfile -NonInteractive -Command` (no ExecutionPolicy flags) |

`verify_fixed_layout()` refuses unless the script is installed in exactly that
derived directory chain. Round files: `c-outage-plan-v1.json`,
`c-outage-phase-v1.json`, `c-outage-restore-attempt-v1.json`,
`c-outage-watch-ready-v1.json`, `c-outage-watch-v1.jsonl`.

## Guard behavior

`--execute-watch` requires ALL of: unchanged raw plan bytes matching
`--plan-sha256`; plan/phase schemas `mesh-c-outage-plan/v1` /
`mesh-c-outage-phase/v1`; the fixed identity above; `armed` exactly `true` in
BOTH plan and phase; a nonce (>=8 chars) present and equal in both; bounded
windows; full-Task fingerprint; original process proof including `task_root_pid`
(the original Task launcher); exact original service config and state paths
under `.local/deployment/node-c/`. Absent nonce or absent/false
`armed` always refuse. The guard has no stop, disable, unregister or kill
capability anywhere; the only mutating call is one `Start-ScheduledTask` for
the fixed Task after the single durable exclusive claim.

Restoration order (at/after `restore_at_utc`, phase must be `STOP_ATTEMPTED`):

1. bounded `python -m fpga_mesh.service --wait-stopped --config <service_config> --timeout <= remaining` (waits only; never stops),
2. UTC + monotonic bound re-check,
3. final Task checks: name/path/full-XML sha; `Ready` required (`Running` -> `STILL_RUNNING`),
4. old-PID probe: any original PID alive -> `OLD_PID_PRESENT`,
5. bound re-check, then exclusive claim `c-outage-restore-attempt-v1.json` (`START_ATTEMPTED`),
6. bound re-check immediately before the single `Start-ScheduledTask` (a slow probe/wait can never cause a late start),
7. health loop (bounded by the remaining window and `health_timeout_seconds`) via `python -m fpga_mesh.project_cli health --control-file <state_dir>/main-control.json`, requiring: resident pid changed (not an original PID), pid alive, `started`, `feishu_connected`, `network_enabled`, transport (`peer_listen_port` > 0, no `peer_error`/`feishu_error`), and Task running with the same XML,
8. outcome appended to the attempt file. Any rerun after a claim -> `NO_REPLAY`. Unknown start (`START_OUTCOME_UNKNOWN`) and unknown health (`START_HEALTH_UNKNOWN`) are terminal for the round; `START_STARTED_UNHEALTHY` marks an answered-but-negative service.

## Plan template (parent-owned; illustrate fields, not a live plan)

```json
{
  "schema": "mesh-c-outage-plan/v1",
  "out_dir": "<abs>/artifacts/mesh-acceptance/MESH-20261011-132845-c94f2686/C-controlled-cohort-v1",
  "round_id": "MESH-20261011-132845-c94f2686", "node_id": "C",
  "task_id": "MESH-20261011-132845-c94f2686-controlled-cohort-C", "task_version": 1,
  "work_id": "C-controlled-cohort-preparation-v1", "operation_id": "<parent op>",
  "nonce": "<parent arm nonce >=8 chars>", "armed": true,
  "task_name": "FPGA-Mesh-Node-C", "task_xml_sha256": "<64 lowercase hex>",
  "prepared_at_utc": "...", "restore_at_utc": "...", "expires_at_utc": "...",
  "task_root_pid": 0, "supervisor_pid": 0, "worker_pid": 0,
  "original_processes": [{"pid": 0, "parent_pid": 0, "created_at_utc": "..."}],
  "service_config": "<abs C config .toml>", "state_dir": "<abs C service state dir>",
  "wait_stopped_timeout_seconds": 20, "health_timeout_seconds": 60
}
```

Phase carries the same identity keys plus `state` (`PREPARED` or
`STOP_ATTEMPTED`), `armed: true`, and `stop_attempted_at_utc` within
`[prepared_at_utc, restore_at_utc)`.

## Commands (not run here)

```
<repo>/.local/venv/Scripts/python.exe c_outage_guard_v1.py                       # read-only Task probe, no writes
<repo>/.local/venv/Scripts/python.exe c_outage_guard_v1.py --execute-watch --plan-sha256 <plan file sha256>
cd derived && <repo>/.local/venv/Scripts/python.exe -B -m unittest -v test_c_outage_guard_v1
```

Exit codes: `0` = accepted (`START_HEALTH_VERIFIED`, `STILL_RUNNING`,
`NO_STOP`); `2` = refusal, unknown or failure. Unknown outcomes are never
replayed.

## Gaps and limits

- Not executed and not armed: no plan/phase exist for C; nothing here proves
  a live outage restoration. Parent owns arming, the stop driver, the separate
  unarmed Scheduler helper, and acceptance.
- `--wait-stopped` may create/acquire `supervisor.lock`/`resident.lock` files in
  the service state dir; it never stops anything.
- Health uses the service's local control file (loopback IPC with the discovery
  token), not an external send.
- The attempt file is a one-shot latch for the round; any post-claim refusal
  needs a new plan/work id (parent decision), never an automatic retry.
- Watch arming requires the Task `Running` at preparation time; if the stop
  driver stops it before the watch is armed, preparation refuses.
- Tests are targeted fakes only (19 tests) and do not replace the reference
  suites; they were the only tests run for this derivation.

Parent review subsequently added 5 focused guard regressions and 3 stop-driver
fakes. The stop-driver fakes use three scratch SQLite databases to demonstrate
that all original writer locks remain held during its fake Stop callback, and
that queued work or an unknown Stop outcome cannot be replayed. No live service
Stop/Start was executed. Parent hardening also rechecks raw immutable plan bytes
after probes/before Start, requires the actual Task launcher, fixes the exact C
config/state paths, checks node/project on health, rejects health arriving after
expiry, and enforces both UTC and monotonic restore/expiry bounds.

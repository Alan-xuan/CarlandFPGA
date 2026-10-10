# Autonomous routing implementation plan

> **For agentic workers:** Use TDD and scoped ownership. The main agent retains decisions and acceptance. Execute continuously within the user's approved v0.7 requirements.

**Goal:** Persist autonomous main-session/model/effort routing and two nonduplicating subagent entrances, remove fixed child counts, repair retries, enable and verify the resident A service.

**Architecture:** Main session directory and allowed catalog route each task. A shared delegation ledger protects DeepSeek and native GPT execution. Existing Feishu roles and controller priority remain authoritative.

**Tech Stack:** Python 3.12, SQLite, Codex app-server JSON-RPC, project MCP/CLI, Windows Task Scheduler, existing Feishu SDK.

## Global constraints

- Secrets remain in existing local secret files; never copy ChatGPT credentials.
- DeepSeek requests are deepseek-flash/deepseek/max throughout lifecycle.
- No default/minimum/fixed number of subagents.
- Best main model owns decisions, acceptance, difficult work, key optimization and evaluation.
- Native GPT requires a shared execution lease; no duplicate replay after a crash.

## Tasks

1. [x] Reproduce structured retry notification failures; fix gateway and selector filtering and retry handling. Owner: native protocol worker; test_app_gateway/test_effort.
2. [x] Add task/work leases with cross-route deduplication, file ownership and on-demand DeepSeek growth; expose native reserve/validate/complete. Tests: test_child_control plus lease integration.
3. [x] Add allowed model catalog, quality guard, persistent main session directory and autonomous task routing; expose session tools and stable main-task CLI. Tests: test_sessions and live real requests.
4. [x] Wire runtime and all project chats, remove legacy count defaults/config/templates, update agent instructions and project book. Verify existing permissions and Feishu identity reuse.
5. [x] Add service single-instance protection and live health/control endpoints; activate existing scheduled task, test failure recovery and persisted task/subtask state.
6. [x] Run full regression, live DeepSeek/native GPT mixed entrance verification, session/model transitions and Feishu identity acceptance; retain sanitized evidence and update operations.

Each code task starts with a test that fails against the old implementation and ends with the relevant test passing. Final acceptance uses live provider/session data, not only configuration or mock results.

Final verification: 271 tests passed. Three real DeepSeek workers and a real native GPT worker completed bounded execution. The quality main verified child output. Same-thread model/effort changes and autonomous new-task creation were verified. Feishu identity acceptance was read-only; no new group messages were sent. Resident worker crash recovery and stopping all 16 owned processes were verified. Evidence and current interface boundaries are recorded in `docs/deployment/AUTONOMOUS_ROUTING_ACCEPTANCE_2026-10-10.md`.

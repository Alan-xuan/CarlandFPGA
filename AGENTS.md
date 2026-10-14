# CarlandFPGA project rules

- This repository contains a three-machine control plane and a separate PYNQ-Z2 single-machine development skill. On machine A, use `skills/pynq-z2-single-node/SKILL.md` for local design, verification, toolchain, and physical board work. On B/C, use the node-matched installed client skill ZIP for design and Git handoff; the repository copy includes A's board upload entrypoint and is not the client workflow. Use `fpga_mesh/` and `docs/deployment/OPERATIONS.md` for group coordination.
- The drilling-logging draft and attached skill packs are references. Do not treat AD7606, 300 bps, compression ratio, latency, Ryzen AI, or the final host application as settled requirements until a task version chooses them.
- In group work, only machine A may operate the physical board. B/C may design and simulate, then submit a code commit, test plan, and evidence manifest through a repository PR. A reports actual board results against that PR's operation ID, request hash, and tested commit.
- Keep simulation, synthesis, implementation, and actual PYNQ-Z2 measurements distinct. Preserve commands, tool versions, reports, logs, and artifact hashes; do not claim board results from a model or simulator.
- Keep project code and distributables inside this repository. Large vendor installers and board images may live outside it with recorded source and hash. Build the FPGA teammate ZIP from committed tracked files with `python -m fpga_mesh.distribution`; unrelated product packages and rules are outside this project.

## Autonomous routing v0.7 (2026-10-10)

- All GPT main conversations on a node use its existing Astra Feishu identity. All DeepSeek execution children use its existing DeepSeek identity. Permissions and human > main > child priority are unchanged; the main authorizes child group reports.
- For an independent task use `fpga_session_open`; followups use the registered task_id. Use `fpga_session_route` to choose an allowed GPT model/effort for the next turn. If these tools are not loaded, run the local Python entry point `-m fpga_mesh.project_cli` using `.local/venv/Scripts/python.exe`; `session_list`, `main_submit`, `main_wait`, `session_route` use the same resident controller. Payloads may be UTF-8 JSON files passed with `--args-file`. Never change global providers or copy credentials to accomplish routing.
- There is no default, minimum or prescribed number of subagents. Use none when delegation adds cost or risks quality; otherwise prefer the specified API-key DeepSeek Flash at fixed highest `max`, automatically allocated per assignment and dynamically reclaimable.
- Subagents exist to reduce GPT usage without lowering quality and to relieve main execution work. Decisions, acceptance, hard problems, key optimization and evaluation must be completed by the quality GPT main model at its highest available effort. Read allowed models/efforts from the running controller. Main model/effort changes apply between turns, never during generation.
- Both DeepSeek and native GPT assignments require stable task_id/task_version/work_id and explicit ownership for file writes. Reuse a duplicate job's result; do not launch a second executor. Overlapping file ownership cannot run concurrently.
- Native GPT subagents are allowed only for a stated special capability need. Before spawning, the parent calls `fpga_native_reserve`. If it returns duplicate=true, reuse the existing assignment and do not spawn. Pass the returned lease and the canonical child agent ID to the native child, which MUST call `fpga_native_validate` (or the CLI equivalent) and receive `execution_allowed=true` before any project execution, then `fpga_native_complete` with actual evidence. A native child without a valid bound lease must stop without executing. Native subagents cannot independently publish to Feishu or promote themselves to a main role.
- Do not replay interrupted/failed side effects automatically. Inspect persisted evidence, supersede the old task version or make a new explicit work assignment after the quality main decides how to recover.

## Official model updates v0.8 (2026-10-10)

- Main and native GPT inference use the builtin `openai` provider and this member's official Codex login. DeepSeek execution uses its separate direct API provider at fixed Flash/max. Do not introduce a local inference router, custom private catalog or cross-role credential copying.
- Use `fpga_models_refresh` or `project_cli models_refresh` to refresh the actual official model/effort catalog and native role files. The human update page opens with `deploy/更新官方模型.cmd`. Refresh makes no inference call and retains current tasks, leases and credentials. Newly discovered official visible models get native roles automatically; `official-latest` follows the official default. Missing legacy names remain explicitly documented aliases until listed by the official catalog.
- Role definitions apply to newly loaded conversations. An already generating turn keeps its model. Supported model access must be verified by actual completed turns; catalog membership alone is not an access guarantee.

## In-place distribution and Astra files (2026-10-11)

- Existing nodes use `deploy/Update-FPGAMesh.ps1`: update changed source files only, preserve local configuration/credentials/state, and do not rerun onboarding. The updater fences ledger admission and verifies idle before stopping the existing service.
- Astra requires tenant scope `im:resource` for file upload/readback. Astra-A received explicit human authorization and its grant was verified. Existing B/C must obtain their own app owner's authorization on the existing Astra app; an update ZIP cannot grant a cloud scope. Run `python -m fpga_mesh.feishu_permissions --config <existing-config>` for a read-only audit. Never add file scope to DeepSeek or change the human > main > child priority.

<!-- deepeye-human-lock:begin -->
## DeepEye human-locked final acceptance scope

For every DeepEye proposal, fusion, implementation, review, new main/work chat,
and subagent, read `docs/competition/deepeye-2026/immutable_scope.md` and `.json`
before work. Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Preserve every H01-H15 requirement. This direct human scope overrides AI plans,
scores, deadlines, budgets and fallback suggestions. Only a new explicit human
instruction can amend it. Preserve game-level 3D/UI, framed hollow cube, solid
drill/obstacles with volume collision, live free camera/editing/random placement,
free blue/red equal-size entry/exit circles and full correct crossing, hidden
truth and causal sourced sensor observations, meaningful PC AI and both PC-direct
and PC-AI-to-FPGA-to-simulator control. No 2D/video/precomputed-route replacement,
truth leak, or FPGA-only control restriction. Every handoff carries this contract
and verifies the pinned hash before task execution. Children cannot edit it.
<!-- deepeye-human-lock:end -->

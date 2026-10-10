# Findings

## Source of Truth

- Design: `docs/superpowers/specs/2026-09-29-fpga-multi-agent-design.md`, version v0.6, dated 2026-09-29.
- The design explicitly says P0/P1 can be validated with local test doubles and do not require GitHub, Feishu, credentials, or real hardware.
- P2-P5 require external inputs that are not present in the design file.

## Local Environment

- Codex CLI: `0.159.0`.
- App-server: experimental, supports `stdio://`, `unix://`, WebSocket and JSON Schema generation.
- Bundled Python: `3.12.14`; pip `26.2.1`.
- Bundled Node.js: `v24.19.0`.
- Git: `2.53.0.windows.3`.
- `tailscale`: not found.
- `git-lfs`: not found.
- `docker`: not found.
- Global `~/.codex/config.toml` currently selects `gpt-6-astra` through the local `codex_model_router_v2` provider and must not be modified by this deployment.
- Global `~/.codex/models.json` contains `deepseek-flash` and `deepseek-v4-pro`.
- `codex login status` reports an API-key login, not a verified member ChatGPT subscription login.

## External Inputs Still Missing

- Node-to-member mapping and operating systems for B/C.
- GitHub private repository URL, account ownership and commit identity.
- Feishu group ID, three human member identities and six app credentials.
- DeepSeek billing-account relationship and API credentials for isolated child homes.
- Real Tailscale installation and authentication on all three machines.
- FPGA board model, driver, toolchain, capture interface and test connection.

These values are intentionally left blank in generated configuration.

## Protocol Decisions

- Messages are immutable after persistence; edits create a new revision.
- Idempotency keys are based on the platform event identity where available and on stable content-derived IDs for local events.
- Ownership is append-only and becomes effective only after a remote fast-forward push succeeds and is read back.
- `instance_id` is unique and never reused after reaping.
- Waiting is event-driven; no idle poll may invoke a model.
- Hardware operations are idempotent by `operation_id`; an interrupted operation becomes `unknown` and requires reconciliation before retry.

## Verification Limits

- OpenAI documentation pages attempted on 2026-09-30 timed out or returned HTTP 403 from this environment. The implementation uses the locally generated `codex app-server` JSON Schema for the fixed local CLI version.
- DeepSeek official documentation was fetched successfully on 2026-09-30: `deepseek-flash` is the V4.1 Flash alias, supports reasoning effort `max`, and the Responses API base URL is `https://api.deepseek.com`.
- No real Feishu, Tailscale, GitHub private repository or FPGA operation may be claimed from local tests.

## 2026-10-03 Follow-up: Native parent-child calling

- Current Desktop-bundled Codex is `0.160.0` and this machine now reports ChatGPT login. Astra live turns use `modelProvider=openai` and `gpt-6-astra`; isolated children use `deepseek-flash` / `deepseek` / `max`.
- `thread/start.dynamicTools` exposes five child-control tools to a native Astra turn. A live Astra turn delegated to DeepSeek, waited for the job, and returned the persisted `CHILD_OK` result. Per-thread MCP registration worked at protocol level but the Code Mode tool catalog did not expose it; the CLI/MCP bridges remain fallback interfaces.
- A separate Astra selector turn chose `low` then `high` for simple and complex tasks on one thread; `thread/read.reasoningEffort` reflected each choice. The selector itself costs a GPT call, so a net usage-saving claim still requires a representative comparison.
- The Codex Desktop bottom-right picker could not be visually verified through allowed tooling. The backend metadata evidence does not establish that this current chat's picker changes when an independent background Astra thread changes effort.
- A Windows scheduled task cannot see the AppData installation path created in this execution context, while it can see the workspace. Installing under ignored `.local/deployment` fixed the service: task running, live DeepSeek assignment returned `SERVICE_OK` at `max`, stop/start recovered two standby children and persisted result. Scheduled tasks are triggered at logon, not before login.
- Feishu credentials, B/C machines, Tailscale, GitHub private remote, real FPGA board and quality/usage/time comparison remain external gates.

## 2026-10-07 Deployment refresh

- 用户把仓库最终设为 **public**：`https://github.com/carolwjade/CarlandFPGA.git`，B/C 可直接克隆，但没有自动写权限，分发包采用 fork/PR。
- A 已安装并登录 Tailscale 1.102.4，地址 `100.121.238.56`。本机跨机密钥只在 `.local/deployment/node-a`，未进入 Git；防火墙规则限制到 Tailscale 接口、地址和 100.64.0.0/10 的 TCP 8787。
- 旧计划任务包装器停止时曾留下 Python 子进程，使本地控制发现文件指向已退出 PID。改为 Task Scheduler 直接执行 Python；运行时端口绑定失败会清理控制文件。签名健康探针和实机后台子派工已重新通过。
- 真实 A 机 Astra→DeepSeek 调用返回 `CHILD_OK`，父选 `low`，子固定 `max`。本轮 150/150 回归通过。飞书六应用尚未授权创建，群 ID 未提供；B/C、板卡与界面下拉框仍不可宣称实测。

## 2026-10-10 Route audit (initial live observations)

- 当前桌面线程 01a12548-f7fb-7df2-bc8c-9d992dff8b99 的 session_meta 为 provider=openai，turn_context 为 gpt-6.1-sol / max；全局 config.toml 同样为该模型/档位，未配置 model_providers。不能沿用旧记录中的 Astra/CCSwitch 路由描述。
- 当前 Desktop 附带 Codex 为 0.162.0-alpha.17.2，项目兼容标记仍写 0.159.0；需以当前真实请求验收协议。
- 项目 runtime.py 的 Astra gateway 固定 gpt-6-astra/openai，effort selector 每任务选择档位；Gateway 复用单个 _thread_id，没有主模型选择器或主会话新建动态工具。
- 原生 collaboration 工具本轮列出的角色均为 GPT 系列，未列 DeepSeek；本会话并发槽位为总计 4。FPGA 自建池是另外一套接口。
- 生产计划任务 FPGA-Mesh-Node-A 当前为 Ready，未发现生产 child-control.json 和 Python 服务进程。隔离实测不会自动启动生产飞书服务。
- 官方文档说明 turn/start 可按回合覆盖 model/effort，并成为同线程后续默认值；底层 API 能力须与项目控制器已有功能区分。

## 2026-10-10 Route audit (verified conclusions)

- 原生 default 子代理两个持久会话均为 openai/gpt-6.1-sol/max；显式请求 deepseek-flash/max 被 spawn_agent 以 Unknown model 拒绝。原生 subagent 和 FPGA 子池不能混为同一通道。
- 三个真实底层回合全部通过：本仓库新线程 sol/low，同线程换 luna/high，另建 astra/max；项目控制器尚无主模型选择器或按任务创建/切换主工作会话工具。
- 真实 Astra 动态工具完成 0/1/3/2 规模控制，另外一个不指定工作数量的独立样本自行选择 3 并行；持久结果与独立算术核对一致，最后恢复 2 待命。
- 三路并发复测、恢复、新增、同线程复用均通过；采集的实际 DeepSeek 请求、HTTP 200 response.completed 及服务端回包的模型和 effort 均为 deepseek-flash/max。
- 首轮一项串流失败及其 max 重试请求保留。合成协议稳定复现 gateway 把 willRetry=true 的通知提前判失败、读取错误字段位置不正确；生产实现未修改。
- 57/57 相关回归及 14/14 证据核对通过；最终报告为 docs/deployment/AGENT_ROUTING_AUDIT_2026-10-10.md，原始脱敏证据和哈希在 artifacts/agent-routing-2026-10-10。

## 2026-10-10 v0.7 current verified implementation

- 上述审计是实施前快照。用户随后授权完整实施；当前主会话路由、双入口、常驻服务与数量规则以 AUTONOMOUS_ROUTING_ACCEPTANCE_2026-10-10.md 为准。
- 新主任务按 task_id 建立持久线程，主模型实际调用开会话及下一回合路由工具。真实目录支持质量主 Astra/ultra；关键任务降档拒绝，旧线程换模型与重启恢复已验。
- NodeConfig 已删除 default_children；启动不预建实例，三项实际执行按需分配三名 Flash/max，回收及重启均为 0。模型/provider/effort 与实际 API 回包固定，程序不规定业务数量上限。
- 两派工入口共用幂等任务和写路径互斥。原生必须验证绑定 canonical agent_id 的父租约；双向重复任务复用持久结果，取消后未确认实际停止不会释放原生文件占用。
- 真实 HTTP 采样 11 次皆 Flash/max、HTTP 200；10 个终结流、1 个未终结流，最终三执行任务完成并由 Astra 独立核对。不把未终结流计为完整响应。
- 原 Astra 和 DeepSeek 飞书身份只读在线验过；主前门的共享身份工具与发布角色用测试核对，不为验收发送消息。权限、优先顺序、板卡职责不变。
- 直接 Task Scheduler 重启策略不足以覆盖强杀工作进程，已改程序监督器。真实进程故障自动恢复、同线程继续、16 进程树停止无残留均已验；后台等待与监督不发起模型回合。
- 271/271 回归通过。普通 Desktop 生成中模型/下拉框不在后台控制器接口内，模型调节在受控回合边界生效；原生供应商和并发限制仍有效。B/C 物理部署与 GPT usage 节约比例未在本次验收。

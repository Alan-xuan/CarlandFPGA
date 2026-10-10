# Progress Log

## 2026-10-10 Route audit

- 已读取现有计划、项目书 v0.6、操作手册和当前控制器代码；本次只新增隔离审计材料与说明，不改变生产路由。
- 当前桌面主会话实际为 openai/gpt-6.1-sol/max；CCSwitch selected=codex-official，proxy/live takeover 均关闭。生产任务 Ready，无生产 child-control 服务文件。
- 57 项路由、app-server、档位选择、动态池、CLI/MCP 和守卫相关回归全部通过，日志在 artifacts/agent-routing-2026-10-10/regression.log。
- 两个原生 default 子代理已分别返回 NATIVE_ROUTE_A_OK / NATIVE_ROUTE_B_OK，随后从各自持久 session_meta/turn_context 核对实际模型。
- 底层真实 app-server 已完成三个回合：新线程 gpt-6.1-sol/low，同线程改为 gpt-6-luna/high，再新线程 gpt-6-astra/max；三个线程读回字段与请求一致，认证 type=chatgpt。
- 隔离项目 runtime 已证实默认 2 个待命，程序侧 0/1/3/2 扩缩无需模型请求。正在实测实际 Astra 动态工具派工与 DeepSeek HTTP 请求参数；生产飞书、同伴与板卡通道保持隔离。
- 完成实际 Astra 工具侧 0/1/3/2 伸缩；首轮一项子任务串流失败已保存，加入诊断采集后的三路复测全部完成，HTTP 请求执行区间有交集，服务端 echo model/effort 与请求一致。
- 自主数量样本未指定工作数量，Astra 实际决定 3 个并行，取回 11011111、13、6 三个正确结果后恢复 2 个待命；自身档位由 low 提升到 high，全部子回合仍 max。
- 重启恢复保留三个完成结果与两个待命；恢复实例新会话、同子线程复用、动态新实例各一项真实 DeepSeek 回合通过，均有持久元数据、请求和服务端 max 字段。
- 原生 spawn_agent 对 deepseek-flash/max 的明确覆盖在创建前被 Unknown model 拒绝。已把原生工具限制与项目独立子池能力分别报告。
- 使用 systematic-debugging 记录首轮异常，并独立稳定复现当前 gateway 对 willRetry=true 通知的处理缺陷；未修改生产代码或全局配置。
- 完成报告、哈希清单与 14 项证据核验，全部隔离 runtime 已停止，生产计划任务仍 Ready。任务完成内容为查明、对照和实测，不把尚未接入的主模型/主会话调度宣称已完成。

## 2026-09-30

- Read the v0.6 design document in full.
- Loaded `using-superpowers`, `planning-with-files`, `verification-before-completion`, `openai-docs`, `executing-plans`, `using-git-worktrees`, `finishing-a-development-branch`, `test-driven-development` and its test-writing reference.
- Confirmed the repository is a normal checkout with no commits; created `codex/fpga-multi-agent-deploy`.
- Inventoried local runtimes and external dependencies.
- Confirmed Codex CLI `0.159.0`, app-server JSON Schema generation, bundled Python 3.12 and Node 24.
- Fetched DeepSeek official Responses API, Codex integration and changelog documentation.
- OpenAI official web access was not reliable in this environment; recorded the limitation.
- Next: write P0 tests and observe RED.
- Wrote `tests/test_protocol.py` and observed the expected import failure (RED).
- Implemented `fpga_mesh/protocol.py` and package exports.
- P0 GREEN: 7/7 protocol tests pass.
- Next: write P1 tests and observe RED.
- Wrote P1 store/controller tests and observed expected missing-module RED.
- Implemented SQLite inbound/outbox/task persistence and event-driven controller.
- Fixed failure retry so a failed event is attempted once per run and remains recoverable after restart.
- Added local persistent peer transport with offline queue and duplicate delivery handling.
- P1 GREEN: 20/20 tests across protocol, store, controller and transport.
- Next: implement P2 with isolated Codex homes and a fake-supported app-server adapter.
- Generated the app-server JSON Schema bundle for `codex-cli 0.159.0`.
- Added isolated Astra/DeepSeek Codex homes, pool lifecycle, route guard, JSON-RPC, app-server adapter and quota monitor.
- Verified a real isolated DeepSeek app-server thread with `modelProvider=deepseek`, `model=deepseek-flash`, `reasoningEffort=max`; a minimal turn returned `OK` and `turn/completed`.
- Added Feishu six-role routing, delegation checks, shared child identity and recovery-gap handling.
- Added persistent HMAC HTTP peer transport, append-only ownership claim coordination and Git checkpoint/push retry.
- Added an exclusive hardware queue with operation-id idempotency, safe stop and unknown-after-restart handling.
- P2-P5 local implementation tests pass; real Astra subscription, Feishu, Tailscale, GitHub private repo and FPGA hardware remain unavailable and are recorded as skipped.
- Next: CLI/runtime wiring, node templates, local simulation and final deployment status.
- Added CLI/runtime wiring, node templates, deployment scripts and operations documentation.
- Full verification run passed 67/67 tests.
- Local three-node simulation passed with zero idle model calls and successful offline recovery.
- Live DeepSeek app-server verification passed with `deepseek-flash` / `deepseek` / `max` and response `OK`.
- DeepSeek account balance query returned API availability without storing balance amounts.
- Generated `docs/deployment/DEPLOYMENT_STATUS.md`.
- Final full verification passed 67/67 tests; local simulation and live DeepSeek/balance checks passed again.
- Secret scan found no credential material outside ignored local/artifact directories.
- Next: commit the branch and shut down the machine.

## 2026-10-03

- Followed the previous branch and design v0.6; kept fixed six Feishu identities and a dynamic, Astra-controlled child count.
- Added persistent child jobs, local authenticated control, native Codex dynamic tools, MCP/CLI fallback, real app-server invocation, and a per-task Astra effort selector.
- Wrote failing tests before implementing and fixed independent review findings for RPC string IDs, selector interruption, environment isolation, tool-result serialization, and scale/claim concurrency. Added a human-version race test.
- Verified real Astra→DeepSeek delegation (`CHILD_OK`), three concurrent DeepSeek children all at `max`, and one Astra thread moving `low`→`high` with matching persisted metadata.
- Installed A under ignored workspace `.local/deployment` and registered `FPGA-Mesh-Node-A` as a logon task. Diagnosed Task Scheduler's inability to see the prior AppData directory. Background service returned `SERVICE_OK` at `max`; stop/start recovered standby workers and job history.
- Updated operations and deployment status with the unverified native dropdown visual behavior and remaining external gates.
- Next: final full verification, secret scan, commit, and previously requested shutdown.
- Final hardened regression: 116/116 tests pass. Live Astra effort selection again persisted `low` then `high` on one thread; scheduled A service restarted and returned `FINAL_RUNTIME_OK` via DeepSeek at `max` with the one-hour watchdog loaded.

## 2026-10-07

- 确认 GitHub 仓库改为公开，绑定本机 `origin`；飞书群当前只有真人，没有六个应用，群 ID 尚待人提供。
- 添加官方飞书长连接的 Astra 入站、双角色出站、去重与持久发送队列；DeepSeek 不监听群。修复人类新指令抢占、跨机项目/来源校验、一个同伴离线不阻塞另一个、签名健康探针和配额预警。
- 完成 B/C 引导脚本、角色指令、队友 Codex 提示和本地配置生成器。密钥仅保存在本地文件，公开仓库采用 fork/PR。
- A 已安装/登录 Tailscale，创建限于 Tailscale 的 Windows 防火墙规则，本地签名健康端点与后台 DeepSeek 派工通过。计划任务改为直接管理 Python，清理旧孤儿进程。
- 全量本地回归 152/152 通过；真实 Astra→DeepSeek 返回 `CHILD_OK`，父 `low`、子 `max`。下一步：远端 GitHub 首推/读回、分发包解包烟测、飞书授权与群 ID 到位后的联调。
- 从飞书桌面端 `FPGA/AI/DEV` 群设置读出 Chat ID `oc_e0de73230fd64dd2da3e52fc781dffb1`；Bots 页面为空，并提示这是外部群，仅接受自定义机器人或允许外部共享的应用机器人。群邀请链接无需提供给应用机器人，且短期过期。
- 全量回归增至 167/167，通过本地 Git 快进认领、失联节点恢复、永久暂停及过期消息等测试。GitHub Desktop 发布 `main`，远端 `git ls-remote` 读回 `88930ff6a33eaad1636514292c888f11ed49abd4`。
- 首次分发 ZIP 的 405 文件 CRC/逐文件 SHA-256 与解包副本 167/167 测试通过。按队友路径从公开 GitHub 克隆 B 节点时发现 Windows Store Python 别名和 PowerShell 参数数组拼接问题；已修复为自动寻找 Codex 捆绑 Python、分别传递参数和值。随后实跑接入脚本生成 B 本地配置并通过 167/167 测试，未提供密钥时保持飞书和直连关闭。可编辑安装生成的 `*.egg-info/` 已加入忽略规则，防止阻碍下一次快进更新。
- 再查飞书开发者后台：企业自建应用创建表单提示默认仅当前组织内部可用且发布需管理员审核；外部群应用机器人还须实际获准外部共享。未把表单可打开误记为六机器人已创建或已入群。

## 2026-10-10 v0.7 implementation and acceptance

- 本轮用户明确授权实施，替换历史 v0.6 的固定主模型与预建子数量规则；历史关机步骤不执行，常驻服务保持运行。
- 持久主会话目录及允许目录路由已接入实际 app-server：Astra 真正调用 session_open/route，旧线程 Luna/low→Astra/ultra，新任务与当前下一回合自主选择 Luna/low，重启复用线程。
- DeepSeek Flash/max 使用原指定本机 key，按任务从 0 扩为 3，实际计算、写文件和读回，主 Astra/ultra 独立验证后回收为 0，重启仍为 0；11 请求均 Flash/max，10 终结流与 1 未终结流如实保留，三个任务完成。
- 原生 GPT 真正执行返回平方和 385，与 DeepSeek 共用工作账本。两个方向的重复请求均复用原 job；活动写路径冲突拒绝，原生必须先绑定父租约并取得 execution_allowed=true。
- 原 Astra/DeepSeek 飞书身份只读核对成功，权限和 human > main > child 不变；14 项 Desktop MCP 工具及共享 Astra 主入口实测通过，未为验收发送群消息。
- 修复结构化重试通知、线程/回合过滤及大 JSON-RPC 帧；补齐持久错误记录、Windows 文件大小写互斥与取消后停止确认。
- Task Scheduler 在直接杀死旧服务进程后未自动恢复，故增加程序监督器及双独占锁。真实强杀工作进程后自动恢复；Windows Job Object 为每个工作进程回收子进程树。停止服务清理 16 个进程、残留 0，重启原线程和完成任务保留，飞书重新连接。
- 最终完整回归 271/271 通过。公开脱敏摘要与证据哈希保存到 docs/deployment/evidence/autonomous-routing-2026-10-10.json，当前验收报告为 docs/deployment/AUTONOMOUS_ROUTING_ACCEPTANCE_2026-10-10.md。
- 受控会话在回合边界切换模型，不改写未接入控制器的普通 Desktop 聊天正在生成的模型或下拉框；本轮未在 B/C 物理电脑、跨机网络或板卡验收，也未量化 GPT usage 节约百分比。

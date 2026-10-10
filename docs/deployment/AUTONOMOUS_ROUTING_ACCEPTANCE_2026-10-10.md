# 自主会话与双派工入口验收

2026-10-10，机器 A，实施基线 v0.7。此次由用户明确授权开设任务会话、选择模型与深度、启用执行子代理及常驻服务。原 v0.6 的固定主模型与预建子实例数量规则已被替换。

本机项目控制器已实现并通过实际调用验收。完整回归 **271/271** 通过；`FPGA-Mesh-Node-A` 为 **Running**，飞书长连接正常。模型切换在回合之间生效；普通 Desktop 聊天正在生成的模型及其下拉框不由此控制器改写。

## 要求与结果

| 用户要求 | 已落实行为 | 实测证据 |
| --- | --- | --- |
| 旧主会话按独立任务开新会话 | 主模型调用 `fpga_session_open`，按 task_id 建立持久会话；跟进与重启复用原线程 | Astra 实际调用 session_list/open/route；新任务产生不同 thread ID，在同一仓库 cwd 运行，Desktop 会话列表可检索 |
| 自主选择当前及新会话的模型、深度 | 使用真实允许目录；session_route 安排当前会话下一回合；关键工作强制质量主模型最高可用 effort | 同一主线程 `gpt-6-luna/low → gpt-6-astra/ultra`；Astra 给新任务选 Luna/low，并给自身下一回合选 Luna/low；实际 turn/start 与持久元数据对应 |
| DeepSeek 优先、最高深度、按需增减 | 原指定本机 key 文件，始终 `deepseek-flash/deepseek/max`；不预建实例，无默认、最低或业务上限数量 | 实际子池 `0 → 3 → 0 → 重启后 0`；三名执行子代理真实计算、写文件、读回；主 Astra/ultra 独立核对 `5050/20100/45150` |
| 保留 GPT 原生入口且不重复、不冲突 | 两入口共用 task_id/version/work_id、请求哈希及文件 ownership；原生执行前绑定唯一父级租约与 canonical agent_id | 原生 GPT 真正执行并持久返回 `NATIVE_LEASE_EXECUTION_OK sum_squares_1_to_10=385`；双向重复派工均复用原 job；跨入口文件占用冲突在启动前拒绝 |
| 主模型保留关键职责 | 决策、验收、重难点、关键优化、评估使用质量主模型最高档位；子代理只承担有明确边界的执行工作 | 当前真实目录的质量路由是 Astra/ultra；关键分类及文本降档拒绝测试通过；本次三个子结果由主模型验收 |
| 原身份、权限和优先关系 | 本机所有 GPT 主会话共用 Astra；所有 DeepSeek 子代理共用 DeepSeek；human > main > child | 原两个应用 `/bot/v3/info` 与原群历史只读核对通过；未创建新身份、未修改应用权限；出站角色映射与父级授权发布测试通过 |
| 修复重试、稳定常驻 | 结构化 error、willRetry、线程/回合过滤；服务双独占锁、监督器退避重启、Windows 子进程树清理、持久恢复 | 重试故障注入回归通过；实际强杀工作 PID `20744` 后自动恢复为 `26472`；原主线程与完成任务保留；停止服务清理 16 个所属进程，残留 0，重启恢复成功 |

DeepSeek 实际 HTTP 记录共 11 次，全部请求和服务端响应元数据均为 Flash/max，全部 HTTP 200。其中 10 个流记录 `response.completed`，1 个没有终结事件；最终三个子任务均完成且文件与主模型计算一致。保留该未终结流记录，不将它计作已完成的 HTTP 流。

原生 GPT 验收线程 `01a12603-7149-73c3-ba2a-8e40245ec8ff` 的真实父线程、worker 来源及 `gpt-6.1-sol/openai/max` 元数据已保存。原生通道继续遵守 Codex 本身可用模型与并发限制；项目没有把原生模型入口改为 DeepSeek。

## 固化位置

- `fpga_mesh/sessions.py`：允许目录、质量保护、主会话登记、下一回合路由与持久结果。
- `fpga_mesh/project_control.py`、`project_cli.py`、`project_mcp.py`：统一的本机鉴权入口。Desktop MCP 实测列出 14 个不重复工具，包括会话、双派工及共享 Astra 群入口。
- `fpga_mesh/child_control.py`：按需 DeepSeek 分配、共享任务账本、文件互斥、租约绑定、取消确认与不重放语义。
- `fpga_mesh/notifications.py`、`gateway.py`、`effort.py`、`rpc.py`：继续可重试原回合，正确处理终止错误及较大 JSON-RPC 帧。
- `fpga_mesh/service.py`、`supervisor.py`、`windows_job.py`、`deploy/register-autostart.ps1`：单实例、程序监督、故障退避、所属进程树回收和脱敏日志。
- `AGENTS.md`、`agent_policy.py`、安装生成的本机 `.codex` MCP/原生角色指令、项目书与队友入口：执行职责、共同身份、无数量规定及 CLI 兼容入口。

指定 key 仅从原本机密钥文件读取；没有改全局 provider，没有把 ChatGPT 凭据复制给子代理。凭据、控制端口令牌、数据库、角色租约及主从运行目录保持 Git 忽略。Windows 子执行 profile 使用本机已经授权的 danger-full-access；文件所有权与主从职责仍由项目租约和角色规则约束，不将其描述成操作系统文件沙箱。

已有 Desktop 聊天未加载新 MCP 时，用仓库 `.local/venv/Scripts/python.exe -m fpga_mesh.project_cli` 接入同一常驻控制器；新聊天加载本机安装的 MCP。自动新会话通过受控任务入口生效，未接入控制器的普通聊天不会被后台改写。新线程的仓库 cwd 已验；没有把它等同于 Desktop 侧栏 projectId 自动归组。

## 证据与复核

公开脱敏摘要及逐文件 SHA-256：[autonomous-routing-2026-10-10.json](evidence/autonomous-routing-2026-10-10.json)。本机原始脱敏记录位于 `artifacts/agent-autonomy-2026-10-10/`，摘要指明实际文件与哈希；不包含 API key、认证头或原生租约 token。

| 本机记录 | 内容 |
| --- | --- |
| `live-acceptance.json` | 主模型真实会话工具调用、turn/start/resume、模型/effort 元数据、三子执行及扩缩 |
| `http-fixed/deepseek_http_metadata.json` | 请求与服务端 model/effort、HTTP 状态、终结状态；不记录认证头或请求正文 |
| `resident-acceptance.json`、`native-runtime-metadata.json` | 常驻入口、双路任务、去重互斥、原生实际执行、原群身份及恢复 |
| `mcp-acceptance.json` | 14 工具、会话与子池实时读取、共享 Astra 入口注册；未发送群消息 |
| `supervisor-crash-recovery.log`、`final-service-recovery.log` | 实际崩溃自动恢复、相同主线程继续响应 |
| `service-stop-tree.json` | 停止前 16 个所属进程与停止后 0 残留 |
| `single-instance-rejection.log`、`final-regression.log` | 重复服务启动拒绝与 271 项完整回归 |

复核命令从仓库根目录运行：

```powershell
Get-ScheduledTask -TaskName 'FPGA-Mesh-Node-A' | Select-Object State
& .local\venv\Scripts\python.exe -m fpga_mesh.project_cli health
& .local\venv\Scripts\python.exe -m unittest discover -s tests -q
```

服务异常恢复不自动重放中断或失败的副作用。主模型先检查持久结果，再用新版本或明确的新工作恢复。原生已运行任务在实际停止确认前保留文件占用，防止取消后另一入口抢占。

B/C 的同版代码与部署入口已更新，本次没有在其物理电脑部署；板卡和跨机互通仍按各自证据门槛验收。子代理节约 GPT usage 的策略已经固化，代表性任务的节约百分比和耗时改善尚未量化。飞书本次仅只读核对身份，角色发布的实际授权语义用本地回归验证，未为验收发送新群消息。

对应运行说明：[OPERATIONS.md](OPERATIONS.md)。分发包使用 `python -m fpga_mesh.distribution` 从已提交的跟踪文件构建，修订号和每个文件哈希以 ZIP 内 `MANIFEST.json` 为准。框架接口参考：[Codex app-server](https://learn.chatgpt.com/docs/app-server)、[DeepSeek Responses API](https://api-docs.deepseek.com/api/create-response/)、[Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)；是否通过以此次实际记录为准。

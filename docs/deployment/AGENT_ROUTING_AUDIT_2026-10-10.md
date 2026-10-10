# 当前 agent 路由与自主控制实测

本文保留当日实施前 v0.6 审计快照。之后用户已授权并完成 v0.7 实施；当前行为以 [自主路由验收](AUTONOMOUS_ROUTING_ACCEPTANCE_2026-10-10.md) 为准，本文的默认待命数量与尚未接入项均已失效。

本机实测确认：项目自建 DeepSeek 池支持默认两个待命、主代理按任务决定数量、超过两个并发及回收，子请求固定为 `deepseek-flash / deepseek / max`。主代理自主选择推理档位已接入。按任务自主切换主模型、创建新的主工作会话，底层接口可行，但当前控制器尚未接入这两项调度能力。

审计日期：2026-10-10，Asia/Shanghai。仓库：`main`，提交 `63120938084628bc2be1282c32ff526630146a77`。实际执行程序为 Desktop 附带的 `codex-cli 0.162.0-alpha.17.2`；源码中的 `client_version=0.159.0` 是客户端声明，不能作为当前二进制版本。

## 当前路由

| 对象 | 实际模型及档位 | 路径与证据 |
| --- | --- | --- |
| 当前桌面聊天 | `gpt-6.1-sol / max` | `session_meta.model_provider=openai`，`turn_context` 与全局配置一致 |
| 两个原生 default 子代理 | 均为 `gpt-6.1-sol / max` | 各自持久记录关联当前父线程，分别返回 `NATIVE_ROUTE_A_OK`、`NATIVE_ROUTE_B_OK` |
| 项目控制器 Astra | `gpt-6-astra / openai`；每个任务选择 effort | 隔离运行中认证为 `chatgpt`，同一主工作线程实际从 `low` 变为 `high` |
| 项目自建子池 | `deepseek-flash / deepseek / max` | 独立 Codex home、DeepSeek API key 环境变量，实际向 `https://api.deepseek.com/responses` 发请求 |

当前 CCSwitch 数据库选中 `codex-official`，代理和 live takeover 均关闭，未观察到 CCSwitch 进程。旧记录中的 MultiRouter 路径已不适用于当前聊天。生产计划任务 `FPGA-Mesh-Node-A` 为 `Ready`，没有运行中的生产 Python 服务或生产 `child-control.json`；本轮启动的是隔离控制器。

原生 subagent 与项目子池是两个不同入口。原生 `spawn_agent` 不指定模型时，本轮实测继承父模型和档位；请求 `deepseek-flash / max` 被工具明确拒绝，错误为 `Unknown model deepseek-flash`。本聊天工具声明的并发槽位总数为 4，包含主代理；本轮没有测试把这个平台限制改大。项目子池使用 `fpga_child_*` 或 `fpga_mesh.child_cli`，不依赖原生 subagent 的模型列表与槽位。

## 与项目书、最新要求逐项对照

| 能力 | 项目书或最新要求 | 当前结果 |
| --- | --- | --- |
| 主模型选择 | 项目书第 1、6 节固定 Astra；本次新增按任务选择主模型的要求 | 控制器 `runtime.py:376` 仍固定 `gpt-6-astra`，没有模型选择器。底层同线程换模型已实测通过 |
| 按任务创建新主工作会话 | 本次要求；项目书要求隔离会话和子实例生命周期 | `thread/start` 在本仓库 cwd 创建持久线程已通过。控制器首次工作会创建主线程，后续复用 `_thread_id`；没有供 Astra 决定何时创建或切换主工作线程的动态工具。档位选择器另外创建临时线程 |
| 主推理深度自主调整 | 当前操作手册已有任务档位选择器 | 实际选择简单任务 `low`、派工任务 `high`，持久 `reasoningEffort` 与选择一致；子档位不受主档位影响 |
| 默认两个与自主伸缩 | 第 1、2 节及 A21：两个只为初始准备，数量由 Astra 决定 | 默认 2，实际工具调用完成 `0 → 1 → 3 → 2`；另外未指定工作数量时，Astra 自行选择 3 个并行后恢复为 2 |
| 子模型与最高档位固定 | 第 6 节及 A24：所有创建、唤醒、恢复、重试保持 Flash/max | 新增、唤醒、同线程再次调用、重启后新会话均实测为 Flash/max。请求及服务端回包都确认 `max`；首轮自动重试请求也保持 `max` |
| 异常恢复可靠性 | A24：不合规调用阻止并报告；异常状态可核查 | 模型、provider、effort 三类违规输入均被守卫阻止。另复现可重试错误通知被提前判失败的缺陷，可靠性验收仍有缺口 |

项目书依据：[v0.6 设计第 1、2、6 节及 A21/A24](../superpowers/specs/2026-09-29-fpga-multi-agent-design.md)。当前代码依据：[runtime.py](../../fpga_mesh/runtime.py)、[gateway.py](../../fpga_mesh/gateway.py)、[effort.py](../../fpga_mesh/effort.py)、[pool.py](../../fpga_mesh/pool.py)、[RouteGuard](../../fpga_mesh/codex.py)。

“两个待命”是两个独立身份与配置准备就绪；gateway 和 app-server 在收到任务时才创建，没有两个后台模型持续推理。规模没有写死的数量上限，但缩容不能移除正在承担任务的实例，仍受实际资源和服务条件约束。

## 实测记录

底层接口测试创建了两个持久后台线程，cwd 均为本仓库：

| 操作 | 线程 ID | 实际读回 | 返回 |
| --- | --- | --- | --- |
| 新建并运行 | `01a1254f-acdd-78e3-a2c2-0034d32db3d4` | `gpt-6.1-sol / openai / low` | `API_ROUTE_1_OK` |
| 同一线程换模型及档位 | 同上 | `gpt-6-luna / openai / high` | `API_ROUTE_2_OK` |
| 另建线程运行 | `01a1254f-cd2e-7370-b665-4381d3670e95` | `gpt-6-astra / openai / max` | `API_ROUTE_3_OK` |

这是后台持久 Codex 线程能力证据；桌面侧栏的项目归属、当前聊天的模型选择器联动没有做 UI 验收。更改其他后台线程不构成更改本次聊天正在执行的模型。官方 [app-server 文档](https://learn.chatgpt.com/docs/app-server)也说明 `turn/start` 可以覆盖 model/effort，并成为同线程后续回合默认设置。

项目实际 Astra 主线程接到了已存在的动态工具，实际调用 `status`、`scale`、三次 `delegate`、`wait`、最后 `scale(2)`。复测三路 HTTP 请求同时处于执行区间，每路都收到 HTTP 200 与 `response.completed`，三个不同实例返回了各自的持久结果。请求 body 的 `model=deepseek-flash`、`reasoning.effort=max` 与服务端回包字段一致。

自主数量测试没有指定工作数量，只要求把三个独立验证单元交给子任务、由 Astra 决定串行或并行及实例数。它选择 `scale(3)`，同时提交三项任务，并返回：

```json
{"chosen_count":3,"scheduling":"concurrent","A":"11011111","B":"13","C":"6"}
```

三个答案分别通过独立的异或、FIFO 数量和排列数核对，全部 `terminal=true`、`stale=false`；最后保留两个待命。该样本证明数量决策和执行通道有效，不用于推断复杂 FPGA 任务的质量、套餐节约比例或整体效率。

恢复测试重新打开已有状态目录，保留此前三个完成结果，恢复两个待命且未先发起模型调用；一个恢复实例新建会话完成 `RECOVERY_ROUTE_OK`，第二项 `REUSED_ROUTE_OK` 使用同一子线程，动态新增的实例完成 `NEW_ROUTE_OK`。三项持久元数据及请求、回包全部保持 Flash/max。DeepSeek 当前官方 [Responses 参数](https://api-docs.deepseek.com/api/create-response/)列出 `none/low/high/max`，最高档位为 `max`；[模型说明](https://api-docs.deepseek.com/quick_start/pricing/)将 `deepseek-flash` 对应到 V4.1 Flash。

## 保留的失败与缺口

首轮三个子任务中两个成功、一个报 `RuntimeError: Codex error`，随后重新发出的实际 HTTP 请求仍为 Flash/max。该轮失败材料保留在 `attempt-01`，没有合并成通过。第二轮加入错误与服务端字段采集后，三项全部成功；没有重现首轮串流错误，尚不能确认其上游具体原因。

协议缺陷可以单独稳定复现：给当前 gateway 先投递带 `error.message`、`willRetry=true` 的通知，再投递正常完成通知，gateway 立即抛出笼统的 `RuntimeError: Codex error`，完成通知未被消费。`gateway.py:195` 和 `effort.py` 的等待逻辑读取顶层 `message`，没有正确处理 app-server 的 `error.message` 与 `willRetry`。这是当前源码缺陷；本轮没有修改生产实现。建议读取结构化错误、按目标线程/回合处理可重试通知，并以终态确认任务结果后，再做故障注入验收。

要完整实现本次新增要求，项目还需要主模型选择与允许模型列表、主工作会话创建/切换工具及持久任务关联，并把当前桌面调用入口与项目子池接通。DeepSeek 路由守卫应继续固定 Flash/max。原 v0.6 固定 Astra 的主模型规则也需要随这项新需求更新。

## 证据与验证

相关回归 57/57 通过，覆盖配置、app-server、gateway、effort、pool、child control、动态工具、MCP 与 CLI。合成错误复现单独作为已确认缺陷记录，不计入“功能全部通过”。此次没有改全局模型配置、CCSwitch 路由或生产服务配置；没有发送飞书消息、调用同伴节点或操作板卡。

- [当前配置、进程、原生子代理持久路由](../../artifacts/agent-routing-2026-10-10/state_snapshot.json)
- [原生 DeepSeek 模型覆盖被拒绝](../../artifacts/agent-routing-2026-10-10/native_deepseek_override.json)
- [新线程与同线程换模型](../../artifacts/agent-routing-2026-10-10/app_server_trials.json)
- [项目动态池复测及实际工具调用](../../artifacts/agent-routing-2026-10-10/attempt-02/pool_trials.json)
- [三路请求与服务端模型/档位回包](../../artifacts/agent-routing-2026-10-10/attempt-02/deepseek_http_metadata.json)
- [Astra 自主数量选择及实际结果](../../artifacts/agent-routing-2026-10-10/autonomy/pool_trials.json)
- [重启、新会话、会话复用](../../artifacts/agent-routing-2026-10-10/recovery/recovery_trials.json)
- [可重试通知缺陷复现](../../artifacts/agent-routing-2026-10-10/recovery/retry_notification_reproducer.json)
- [首轮失败](../../artifacts/agent-routing-2026-10-10/attempt-01/pool_trials.json)
- [回归日志](../../artifacts/agent-routing-2026-10-10/regression.log)

审计脚本保存在同一证据目录：`inspect_state.py`、`live_audit.py`、`recovery_audit.py`。证据目录被 Git 忽略，未将认证或本机运行状态放入公开仓库。原始 SDK/工具请求中的凭据与完整提示未写入 HTTP 采集文件。

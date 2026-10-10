# FPGA 三机多 Agent 部署状态

更新：2026-10-10。设计基线：`docs/superpowers/specs/2026-09-29-fpga-multi-agent-design.md` v0.7；仓库可见性按用户后续决定改为**公开**。自主会话与双入口的当前实测见 [2026-10-10 验收](AUTONOMOUS_ROUTING_ACCEPTANCE_2026-10-10.md)，早前分发与群上线证据保留日期，不混作本轮结果。

| 范围 | 当前证据 | 状态 |
| --- | --- | --- |
| 控制器、飞书适配、三节点协议、双入口、离线队列与分发 | `python -m unittest discover -s tests -q`，271/271 通过；覆盖原协议与新增模型路由、去重、文件冲突、原生租约、重试通知、大 RPC 帧、监督器崩溃和进程树清理 | **本地验证通过**；真实调用和服务验收另见下行 |
| Astra→DeepSeek 实际执行 | 2026-10-10 父 Astra/ultra 实际派出三名 Flash/max 子代理，真实计算、写文件、读回并由父独立核对；子池 `0→3→0→重启后0`。11 请求均 Flash/max，10 终结流、1 未终结流，最终三任务完成 | **A 机真实路由与执行通过**；无默认子数量 |
| 自主主会话及模型/推理路由 | Astra 实际调用 session_open/route；旧线程 Luna/low→Astra/ultra，新任务 Luna/low，Astra 自选自身下一回合 Luna/low；同仓库持久线程重启恢复 | **受控会话实测通过**；切换在回合边界，未改写普通 Desktop 聊天当前生成或下拉框 |
| GPT 原生与 DeepSeek 共存 | 真正原生 GPT 执行返回 385 并持久完成；双向重复派工均复用原 job；跨入口写路径冲突拒绝，原生执行前绑定父租约 | **双入口实际派工、去重与互斥通过** |
| A 机后台常驻 | `FPGA-Mesh-Node-A` 登录后运行监督器和服务；强杀工作进程后自动拉起，完成任务与原主线程保留；停止时清理 16 个所属进程，残留 0；再次启动飞书连接正常 | **本机实际崩溃/停止/恢复通过**；B/C 仍待部署 |
| GitHub 仓库 | `https://github.com/carolwjade/CarlandFPGA.git` 公开；A 机通过 GitHub Desktop 推送，并用 `git ls-remote origin refs/heads/main` 回读确认本地与远端 `main` 一致。最新分发包的修订号见 `MANIFEST.json`；B/C 走 fork/PR | **A 机真实读写已通过**；每次提交后远端回读 |
| 队友分发包与接入 | 入口默认尝试工具安装、fork、两应用注册及各自发信读回、真实主从调用、常驻任务；外部授权不成时继续独立步骤，重复运行保留本机密钥路径与同伴地址。`.local/deployment/node-*/setup-status.json` / `NEXT_STEPS.md` 按 Git、飞书、同伴、真人指令和主从结果实际证据判定。多机包与 PYNQ-Z2 单机技能分开生成，均从干净已提交的 Git 文件制作，校验 CRC、逐文件 SHA-256 和修订号。解压多机包后运行 181 项适用测试通过；单机技能从 ZIP 安装通过；无凭据 B 路径实际克隆、安装依赖、201 项测试、生成待办报告成功；再次运行保留密钥路径、绑定地址与同伴 URL | **分发和无凭据接入烟测通过**；B/C 真人账号、密钥、机器人和跨网实机仍待验收 |
| 飞书六机器人 | A 机 `FPGA Astra A`（`cli_aa4c9f58dd385cc9`）和 `FPGA DeepSeek A`（`cli_aa4c9f8c59785cd1`）的外部群版本 `1.0.2` 均已发布，两个机器人已加入 `FPGA/AI/DEV`。各自发信并同身份读回成功，群内可见原消息；Astra 长连接收到真人 `/fpga A` 指令并两次回复指定 ACK，常驻服务复测零重试、无错误 | **A 机两身份与真人群指令线上验收通过**；B/C 四身份尚未创建/入群 |
| 跨网 B/C 与 Tailscale | A 已安装并登录 Tailscale 1.102.4，取得 `100.121.238.56`；只允许 Tailscale 接口/地址、100.64.0.0/10 来源访问 TCP 8787 的防火墙规则已生效 | **A 机就绪**；B/C 尚未入网，无法验收真实跨机互通 |
| 板卡烧录及日志 | A 为唯一可烧录电脑，但未得到型号、工具链与实机接口 | **未实测**，`hardware_enabled=false` |
| 使用量、质量、耗时改善 | 子池动态扩缩、最高 `max`、零模型调用等待等单项行为已有测试；尚无三机代表任务对照 | **成效量化未验收**，不能声称已节省 GPT 套餐用量 |

飞书群 ID 已直接从群设置取得，群邀请链接不是应用机器人入群的必要条件。接入使用官方 `lark-channel-sdk` 长连接仅给 Astra；DeepSeek 应用不订阅群消息，只在入群自测时做一次性发送与读取。A 机配置保存了两个应用的非秘密 ID 和本机 Secret 路径，`feishu.enabled=true`；入群自测回执和 Secret 均只在 Git 忽略的本机目录。管理员接手要点见 [飞书应用上线交接](FEISHU_APP_HANDOFF.md)。HTTP 同伴连接由各机直连，HMAC 认证且对来源/项目/接收者做检查；各机 SQLite 出站队列可在断线后补发。后台健康探针和配额读取都不调用模型，额度阈值 20%/10% 报告会持久排队。

队友入口 `deploy/Join-FPGAMesh.ps1`、`deploy/TEAMMATE_PROMPT.md` 和 `deploy/HUMAN_STEPS.md` 不含 Secret。工具安装、配置、回归和服务注册可自动尝试；本机 GitHub CLI 的 winget 安装曾停在 Windows 管理员确认，脚本现设 180 秒超时并继续其余步骤，管理员确认仍须真人完成。ChatGPT 登录、飞书授权/实名认证/发布/入群、Tailscale 加入同一 tailnet、GitHub 本人登录/所有者邀请、跨机密钥交换以及 A 机板卡验收需要对应成员/平台参与。公开克隆不提供直接写权限，个人 fork/PR 也不等同于上游共享认领分支写权限。

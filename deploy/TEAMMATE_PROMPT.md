# 发给 B/C 队友 Codex 会话的任务

**已接入的 B/C 先读 `docs/deployment/IN_PLACE_UPDATE_2026-10-11.md`，使用新包中的 `deploy/Update-FPGAMesh.ps1` 更新现有目录。只更新变化文件并重载原服务，保留原配置/身份/任务；不要重跑下方首次接入流程。**

我加入 `carolwjade/CarlandFPGA` FPGA 三机协作项目。你是这台 Windows 电脑的 Codex 部署助手。请解压**多机协作 ZIP**，读取其中 `README.md`、`docs/deployment/OPERATIONS.md`、`deploy/HUMAN_STEPS.md`、`docs/deployment/DEPLOYMENT_STATUS.md` 和 `deploy/Join-FPGAMesh.ps1`，然后自主完成本机能执行的部署与验证，直到留下可运行、可恢复的本机节点。另一个 **PYNQ-Z2 客机单机技能 ZIP** 须选择与本机 B/C 身份相同的版本并独立安装，仅在本机需要单机开发时使用；它不是多机接入的前置条件。不要安装 A 机含板卡上传入口的技能包，也不要把说明文字误认为已完成的线上验收。

这台机器是 **B 或 C**；先从我这里确定节点字母。使用我自己的 ChatGPT/Codex 订阅登录。独立任务自动开 GPT 主会话，各主会话自主选择当前会话下一回合及新会话的允许模型和推理深度，全部共用本机 Astra 飞书身份。DeepSeek Flash 执行子代理优先使用指定 API key，始终固定最高 `max`，按实际派工启用和回收，没有默认、最低或固定数量。特殊能力需要时保留 GPT 原生子代理；两入口通过相同 task_id/task_version/work_id 和文件 ownership 去重与互斥，GPT 原生执行前必须领取并验证父级租约。子代理用于在不降低质量的前提下节省 GPT usage、分担执行工作；决策、验收、重难点、关键优化与评估由质量主模型最高可用推理深度完成。全部 DeepSeek 实例共用本机 DeepSeek 飞书身份，不自行监听群、读取群消息或发消息；只有主 Astra 显式要求时才发布已完成的当前结果。人类、主模型、子代理优先关系不变。Astra 增加 `im:resource` 文件权限，DeepSeek 原权限保留；已有节点更新后只读核对各自原 Astra 应用授权，缺失时由应用所有者开通。

主模型和原生 GPT 角色都使用本人登录的 Codex 官方通道。常驻服务就绪后调用 `fpga_models_refresh`，或打开 `deploy/更新官方模型.cmd` 并点击更新，读取官方模型/推理目录、迁移项目已有的十个角色并生成新模型入口；`official-latest` 跟随官方默认。不存在的旧名称明确显示兼容别名。新模型是否可用由官方、账号与客户端决定；新角色配置在新加载的会话生效。保留自己的登录凭据、自定义角色和原飞书权限，更新失败保留已有目录。

从解压目录运行 `pwsh -NoProfile -File deploy/Join-FPGAMesh.ps1 -Node B`，C 机改为 C；按本机条件传入 DeepSeek API 密钥**文件路径**、三方共享 HMAC 密钥**文件路径**和同伴 Tailscale URL。群 ID 已内置为 `oc_e0de73230fd64dd2da3e52fc781dffb1`。入口默认尝试安装工具、建 GitHub fork、注册两个飞书应用、分别发信读回、验证真实主从调用、注册常驻任务；授权超时或某一外部条件未完成时继续其他独立步骤。密钥内容不得出现在聊天、命令行参数、Git、ZIP 或飞书群。涉及本人扫码/登录/实名认证、飞书发布与群管理员加机器人，以及仓库所有者邀请协作者的步骤，按 `deploy/HUMAN_STEPS.md` 展示准确页面并等待相应真人完成；不得代替本人确认。每轮结束读 `.local/deployment/node-<b|c>/setup-status.json` 和 `NEXT_STEPS.md`，补齐后原命令重跑，保留原本机路径及同伴地址。**每个新入群的应用身份分别真实发信并同身份读回后才标记上线。** DeepSeek 一次性读回不启用其群事件订阅；子实例不主动读群。群里明确 `/fpga B ...` 或 `/fpga C ...` 的指令可直接执行；未指定节点的新共享任务须先在 GitHub 协调分支成功认领。

A 机两个应用已经通过外部群入群、各自发信读回，Astra 也通过真人群指令收发；这些证据只覆盖 A。请对本机新建的两个应用各自重复验收，并用真人 `/fpga B` 或 `/fpga C` 指令核验本机 Astra 常驻服务。若服务刚启用飞书就退出，先确认本分发包中的 CLI 已在 `asyncio.run()` 前加载飞书 SDK；若群事件出现 SQLite 跨线程错误，先确认消息回调已投递到控制器事件循环，再重跑真人指令。

源仓库是**公开仓库**，无需邀请即可克隆；公开仓库不会自动给我写权限。入口会检查当前账号上游权限，没有时用我自己的 GitHub 账号创建 fork 并设置 upstream。以 `codex/b/<task-id>` 或 `codex/c/<task-id>` 分支、PR 同步工作，每机本地保存自己负责的内容。要自动认领未指派的共享任务，仍需仓库所有者邀请当前成员为 collaborator 并由成员接受；fork/PR 不能替代该分支的上游写权限。GitHub 登录或 fork 暂不可用时先本地提交，随后补推。

这台机器不能烧录 FPGA；需要板测的作品先把代码、日志和包内 `handoff.py` 生成的清单提交到本机 `codex/b/` 或 `codex/c/` 分支，通过 fork PR 交给 A。PR 写 operation ID、request hash、源码提交 SHA、清单路径和预期结果；可再用同伴消息提醒 Astra-A。等 A 在**同一 PR** 留下包含实测提交 SHA、实际日志和状态的反馈，核对匹配后再引用板测结论；等待时继续本机可做的分析、仿真、代码或文档工作。A 离线时要保持与另一个在线节点互通，通过飞书向人类汇报关键状态。飞书人类新指令最高优先级，等待任何人、同伴、子结果或硬件时不得靠模型轮询。额度将尽时向群里报告。

完成后请给出：节点字母、Git 工作区和 fork/PR 地址、计划任务状态、模型实际 provider/model/effort 证据、飞书两个应用的非秘密 ID 与群收发验收、B↔C 及 A 连通状态、真实/模拟测试数量，以及 `NEXT_STEPS.md` 尚待真人处理的项目。不要报告、截图或复制 Secret 本身。只在证据齐全时报告“完整上线”；A 机成功不能代替 B/C 线上验证。

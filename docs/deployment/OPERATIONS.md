# FPGA Mesh 部署与运行

每台电脑运行一个本地控制器和一个用该成员 ChatGPT 订阅登录的 Astra 主实例。Astra 根据任务调用本机 DeepSeek V4.1 Flash 子池，默认两个待命，但没有数量上限规则；子实例只用 `deepseek-flash` / `deepseek` / `max`。等待飞书、同伴、子结果和硬件时由网络与本地事件唤醒，不进行模型轮询。

## 队友入网

把**多机协作 ZIP**和 `deploy/TEAMMATE_PROMPT.md` 交给 B/C 的 Codex 会话；单机技能分别发 `pynq-client-b`、`pynq-client-c` ZIP，不能把 A 机可上传的 `pynq-skill` ZIP 给客机。B/C 各自从对应 ZIP 运行 `skills/pynq-z2-single-node/Install.ps1`。在各自 Windows 电脑上运行 `pwsh -NoProfile -File deploy/Join-FPGAMesh.ps1 -Node B` 或 `-Node C`。入口先尝试用 winget 安装缺失的 Git、Python、GitHub CLI 和 Tailscale，再从公开 GitHub 仓库克隆源码，创建被 Git 忽略的 `.local/venv`，安装飞书 SDK，生成该机配置，运行自检、真实主从调用，并在登录与密钥就绪时注册常驻任务。工具安装、网页授权或账号权限失败时，保留已完成步骤；入口每次生成 `.local/deployment/node-<字母>/setup-status.json` 和 `NEXT_STEPS.md`，详细本人操作见 [人工步骤](../../deploy/HUMAN_STEPS.md)。重跑会沿用已有本机密钥文件路径、同伴地址，不覆盖队友改动；现有工作区只在干净时快进。

脚本依次尝试 `py`、系统 Python 和 Codex 捆绑的 Python 3.12+；若路径特殊，可用 `-PythonExe 'C:\path\to\python.exe'` 指定解释器。本机 B 无凭据烟测已验证 Codex 捆绑解释器可完成虚拟环境与安装。

完整参数示例（路径和值由各机填写，绝不要把密钥内容贴进命令行或 Git）：

```powershell
pwsh -NoProfile -File deploy\Join-FPGAMesh.ps1 -Node B `
  -DeepSeekKeyFile 'C:\secure\deepseek-key.txt' `
  -SharedSecretFile 'C:\secure\fpga-mesh-secret.txt' `
  -GroupId 'oc_e0de73230fd64dd2da3e52fc781dffb1' `
  -PeerA 'http://100.x.x.a:8787' -PeerC 'http://100.x.x.c:8787' `
  -RegisterApps -SetUpFork
```

`-RegisterApps` 和 `-SetUpFork` 当前默认开启，示例显式列出便于审阅。`-RegisterApps` 对每机的 Astra 和 DeepSeek 形象使用飞书官方设备授权流程建两个应用；成员须在网页确认。Astra 应用订阅群消息；DeepSeek 应用不订阅群事件，正常运行时仅按 Astra 委托发信。两者都申请 `im:message:send_as_bot`；Astra 申请 `im:message`、`im:message.group_msg`，DeepSeek 为一次性入群读回另申请 `im:message:readonly`、`im:message.group_msg`。六个应用都要在飞书开发者后台核对实际生效的机器人能力、消息权限、事件订阅和可用范围，然后在群设置 → Bots → Add Bot 中加入 `FPGA/AI/DEV`。机器人必须先入群才可读取该群历史，因此“先自测”指**入群后、标记上线前**：入口脚本给每个新身份发送一条带随机标记的消息，再用同一身份的群历史 API 读回完全相同的消息 ID、群 ID 和文本。每身份只发送一条；读回失败会保留发送回执，重跑时先补读而不重复发信。只有各身份分别读发通过才报告其上线；Astra 未通过时本机飞书保持关闭，DeepSeek 未通过时其共享群身份保持关闭。此读回不启动 DeepSeek 模型，也不使其常驻监听。群 ID 已从飞书桌面端「群设置 → 底部 Chat ID」核实为 `oc_e0de73230fd64dd2da3e52fc781dffb1`，脚本已将它设为默认值。群分享链接是给人类加入用的临时链接，机器人入群不依赖它。补齐发布、权限或入群条件后重跑脚本。A 机的本地路径为 `.local/deployment/node-a`，不在仓库提交本地凭据及自测回执。

未指明节点的新共享任务只在 `codex/coordination` 分支的追加认领记录快进推送成功后执行；其他节点读取胜出的负责人并跳过重复执行。公开仓库允许克隆却不授予推送权限，所以 B/C 在获得写入该协调分支的权限前不能独立认领新的共享任务。明确写 `/fpga B ...`、`/fpga C ...` 或 `Astra-B:`、`Astra-C:` 的指令无需认领分支。`/fpga pause`、`/fpga resume` 会发送到全部在线主节点；暂停状态跨服务重启保存。模型或网络错误按持久退避重试，不会每秒发起新模型请求。

三台电脑在不同网络，使用同一 Tailscale tailnet，三个节点都要有可互访的 100.x 地址。每机配置另两台的 URL，B/C 不经过 A 中转。HMAC 共享密钥文件必须由三位成员通过可信渠道放在本机；公开分发包没有这个文件。健康探针和持久发件箱在无模型调用的后台运行，某节点离线时其他节点仍可相互收发。Windows 防火墙和 tailnet 权限须允许节点的 8787 端口。

仓库为**公开**。队友可直接克隆；没有上游写权限时，用 `gh auth login --web` 登录自己的 GitHub，入口默认建立 fork，用 `codex/b/<task-id>` 或 `codex/c/<task-id>` 分支向 `carolwjade/CarlandFPGA` 提交 PR。fork/PR 只解决代码贡献；自动认领无指定节点的共享任务需要 B/C 在上游 `codex/coordination` 分支快进推送，因此仓库所有者须[邀请其为 collaborator](https://github.com/carolwjade/CarlandFPGA/settings/access)，各成员接受邀请。代码、约束、日志和可公开的实验结果进入远端；密钥、令牌、SQLite、私有硬件标识不进入公开仓库。

## 客机单机成果交接

B/C 在各自客机技能中先完成本机可做的开发与验证，提交源码和可公开日志，再用包内 `handoff.py` 对仓库内文件生成不可覆盖的 `manifest.json`；硬件阶段记 `blocked` 或 `not_run`。仓库忽略 `logs/`、`*.log` 和 `artifacts/`，供交接的原始日志须按字节保存为任务目录内被 Git 跟踪的 `.txt`。随后把清单提交到 `codex/b/<task-id>` 或 `codex/c/<task-id>` 分支，推送 fork 并向本仓库 `main` 发 PR。PR 正文给出 operation ID、request hash、源码提交 SHA、清单路径、测试步骤和预期结果；同伴消息可提醒 A，但 PR 是正式交接。没有 GitHub 认证/网络时保留本地提交，不能报告 A 已收到。

A 取到指定 PR head SHA 后，先核对仓库清单、全部文件哈希和测试要求，再按本机已安装的单机技能与实际板卡条件执行上传/验证。`board_run.py` 的 Python 探针结果只证明传输，不能代替自定义 `.bit/.hwh`、接口或性能实测。A 将 operation ID、request hash、实际测试的完整 PR head SHA、板卡/镜像/工具版本、运行命令、退出码、阶段状态和可公开证据路径/哈希反馈在**同一 PR**。失败时给出复现条件；无法测试时标 `blocked` 并说明缺项。B/C 读取反馈时核对以上身份与提交，后续新提交须重新请求板测。A 机本地技能和硬件队列设置不因客机打包而改变。

## 运行与诊断

本机配置位于 `.local/deployment/node-<a|b|c>/node-<a|b|c>.toml`。计划任务 `FPGA-Mesh-Node-<A|B|C>` 在成员登录 Windows 后运行。检查：

```powershell
Get-ScheduledTask -TaskName 'FPGA-Mesh-Node-A' | Select-Object State
& .local\venv\Scripts\python.exe -m unittest discover -s tests -q
```

不经计划任务也可前台运行：

```powershell
$config = (Resolve-Path '.local\deployment\node-a\node-a.toml').Path
pwsh -NoProfile -File deploy\run-node.ps1 -Node A -Config $config -Python '.local\venv\Scripts\python.exe'
```

主 Astra 回合有五个 `fpga_child_*` 动态工具，以及 `fpga_group_report`、`fpga_peer_send`、`fpga_child_group_report`。子实例不能主动读取飞书群或发消息；父 Astra 显式发布一个当前、已完成的子任务结果时，使用本机共用的 DeepSeek 飞书形象。父实例对重要子结果独立验证。人类新指令会排在同伴报告之前，并中断当前较早回合；暂停/恢复命令立即改变分派状态。每个回合有故障看门狗，不会因等待无限占用模型。

A 机是唯一烧录者。当前 `hardware_enabled = false`，直到板卡型号、驱动、烧录命令、日志采集与操作授权完成实机联调；B/C 只能请求 A 实测。后台配额读取不发起模型回合，剩余 20% 和 10% 时在飞书队列生成预警。Astra 的工作回合推理档位由选择器按任务选择，子回合始终是 `max`。当前仅验证 app-server 线程实际档位变化；Codex Desktop 当前聊天窗口右下角下拉框的视觉联动仍未确认。

当前群在飞书客户端被标为**外部群**。Add Bot 页面限定只能添加自定义机器人或已开启 external sharing 的应用机器人。自定义 Webhook 机器人只能主动推送，不能替代需接收群内新指令的 Astra 应用机器人。参见[飞书群机器人说明](https://www.feishu.cn/hc/zh-CN/articles/360024984973-%E5%9C%A8%E7%BE%A4%E7%BB%84%E4%B8%AD%E4%BD%BF%E7%94%A8%E6%9C%BA%E5%99%A8%E4%BA%BA)。
2026-10-09 A 机账号本人完成个人实名认证；Astra、DeepSeek 两应用发布允许加入外部群的 `1.0.2` 版本后，已在目标群逐一入群，并分别发信、同身份读回。Astra 常驻长连接还接收了真人群指令并回复；修复 SDK 事件回调跨线程投递后，第二次真人指令零重试、无错误。B/C 各应用仍须在队友机器上重复授权、外部群发布、入群、自测与真人指令验收，不可把 A 机的实测推断为三机联通。

线上与本地验证的区别见 [部署状态](DEPLOYMENT_STATUS.md)。

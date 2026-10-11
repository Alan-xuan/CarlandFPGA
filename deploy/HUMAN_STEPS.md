# B/C 机接入时需要本人完成的步骤

先把多机 ZIP 解压到本机，让自己的 Codex 会话读取 `deploy/TEAMMATE_PROMPT.md`，确定机器字母 B 或 C，然后运行 `pwsh -NoProfile -File deploy/Join-FPGAMesh.ps1 -Node B`（C 机把 B 换成 C）。脚本会尝试安装 Git、Python 3.12、GitHub CLI 和 Tailscale，克隆最新源码、安装依赖、创建本机配置、注册应用、实测主从调用、注册常驻任务，并在 `.local/deployment/node-b/` 或 `node-c/` 写出 `setup-status.json` 和 `NEXT_STEPS.md`。若 Windows 在安装工具时弹出管理员权限确认，须由本机成员批准；长时间未批准，安装器会超时并继续其余步骤，成员之后可手动完成安装再重跑。授权暂未完成时继续独立步骤，补齐后重跑同一命令；重跑会保留本机密钥文件路径、同伴地址与现有改动。

以下项目不能由分发包替个人完成。对应成员操作完成后，通知本机 Codex 重跑并核验状态报告。不要把任何 Secret、API Key 或共享 HMAC 明文发送到飞书群、Codex 聊天、GitHub 或分发 ZIP。

1. **Codex 订阅与 GitHub 身份。** 三位成员各用自己的账号登录 Codex Desktop/CLI 和 GitHub。Codex 用 `codex login status` 核验；GitHub CLI 用 `gh auth login --web` 显示一次性网页登录流程，再以 `gh auth status` 核验。公开仓库可直接克隆；脚本会在没有上游写权限时建立个人 fork 和 `origin`。若要求自动认领未指定节点的共享任务，仓库所有者必须在 [仓库访问设置](https://github.com/carolwjade/CarlandFPGA/settings/access) 邀请 B/C 的 GitHub 用户为 collaborator，成员在 GitHub 接受邀请。未获授权时仍可在 fork 上做代码并发 PR，不能把共享认领分支写入上游。
2. **DeepSeek 与跨机密钥。** 每机成员通过 DeepSeek 官方后台取得自己的 API Key，保存到仅本机可读的 UTF-8 文件；将文件路径交给入口的 `-DeepSeekKeyFile`。A 机维护的 HMAC 共享密钥由三人经私密可信渠道交换并各存一份本机文件，入口只接收 `-SharedSecretFile` 路径。不要让三机使用不同值；不应为重试把文件内容写到命令行。文件权限由本机成员核对。
3. **Tailscale 身份与地址。** 本人登录 Tailscale，加入三台电脑共同可访问的 tailnet。Codex 运行 `tailscale ip -4` 取得本机 100.x 地址，和另外两机的 100.x 地址分别组成 `http://<地址>:8787`，B 机传 `-PeerA`、`-PeerC`，C 机传 `-PeerA`、`-PeerB`。成员在 Tailscale 管理端批准设备或访问规则；Windows 防火墙只允许受信 tailnet 到 TCP 8787。某机离线时健康检查保持未通过，但另外两机继续工作。
4. **飞书开发者身份与应用授权。** 本机 Codex 运行入口时，官方设备授权页会给出链接/二维码；由本人登录 [飞书开放平台](https://open.feishu.cn/) 并同意创建本机 Astra 和 DeepSeek 两个应用。若网页要求个人实名认证，必须由账号本人在开放平台账号中心完成实名后再重试。Codex 随后检查两个应用的机器人能力、`im:message:send_as_bot`，Astra 的群消息订阅及 `im:resource` 文件权限，以及 DeepSeek 用于一次性入群读回的权限。打开“允许机器人被添加到外部群中使用”，创建并发布新版本；发布/审核由有权的人在平台完成。外部群开关灰色通常表示实名或应用条件未满足，不能靠脚本绕过。
5. **飞书入群和收发验收。** 在 `FPGA/AI/DEV` 群设置的 Bots / Add Bot 中，由有权限的群成员分别加入该机 Astra 和 DeepSeek 应用。群 ID 已内置，成员不必手抄。重跑入口后每个身份分别发送一次带标记消息，并用相同应用身份从同一群读回完全一致的消息 ID、群 ID 和正文。发送成功而读回失败时，回执留在本机，重跑只补读。两身份通过后，由真人在群中发 `/fpga B 链路自测：只回复 ACK_<随机标记>`（C 机用 C），查实际回复及本机入站处理记录。DeepSeek 的读回只用于初次验收，不开启其群监听；日后只有 Astra 明确要求才由该形象发结果。
6. **物理板卡。** 只有 A 机可烧录；B/C 把代码提交、测试方案、证据清单交 A。A 尚需根据实际板卡、Vivado/驱动和操作接口联调后才可开启硬件服务。不要把仿真结果当板测结果。

首次入口运行后让 Codex 打开对应 `.local/deployment/node-<字母>/NEXT_STEPS.md`。它按实际证据列出尚未通过的项目；补齐某项只需重跑入口，不用重新创建应用或覆盖本机代码。不能用 A 机的通过记录代替 B/C 自测。

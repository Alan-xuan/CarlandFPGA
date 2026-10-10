# CarlandFPGA 三机协作控制器

本项目把三位成员各自的 Codex/ChatGPT 订阅用于 GPT 主会话。独立任务自动建立会话，模型与推理深度按任务选择；本机所有主会话共享原 Astra 飞书身份。执行工作优先交给指定 API key 的 DeepSeek Flash，始终为最高 `max`；没有默认数量，按需启用与回收。特殊需要保留 GPT 原生 subagent 入口，两入口共享任务去重和文件所有权账本。决策、验收、重难点、关键优化、评估由质量主模型完成。全部 DeepSeek 实例共用本机 DeepSeek 群身份，六个群角色及权限不变。只有 A 机接板卡。

GPT 主会话与原生角色均使用 Codex 官方 `openai` 通道。双击 [更新官方模型](deploy/更新官方模型.cmd)，再点击页面的“更新官方模型”，即可重新读取官方目录、推理档位及新模型的原生入口；`official-latest` 跟随官方默认。更新失败保留旧目录、角色和正在执行的任务，不修改账号凭据。新模型须已由官方向当前账号/客户端开放，原生角色定义在新加载的会话生效。十个旧角色的实际迁移及双入口验收见 [官方模型路由验收](docs/deployment/OFFICIAL_MODEL_ROUTING_ACCEPTANCE_2026-10-10.md)。

分发包按用途拆开：多机协作 ZIP 用于 B/C 接入 GitHub、Tailscale、飞书和本机主从 Agent；B、C 各有一个独立的 PYNQ-Z2 客机技能 ZIP。客机技能保留预检、RTL/仿真、Vivado 构建与证据清单，要求将作品通过仓库 PR 交给 A，由 A 实板验证并在同一 PR 反馈。客机包不含板卡上传脚本。A 机现有的 [pynq-z2-single-node 技能](skills/pynq-z2-single-node/SKILL.md)及其分发 profile 保持独立，含真实板测入口；边界见[单机运行说明](docs/deployment/SINGLE_NODE_PYNQ_Z2.md)。

公开源码仓库：[carolwjade/CarlandFPGA](https://github.com/carolwjade/CarlandFPGA)。公开克隆不等于写入权限；其他成员默认在自己的 fork 上提交并向此仓库发 PR。API 密钥、飞书应用 Secret、跨机共享密钥和各机 SQLite 状态都只保存在本机被忽略的 `.local/` 路径。

队友把[分发提示](deploy/TEAMMATE_PROMPT.md)和**多机协作 ZIP**交给自己的 Codex 会话。入口 [Join-FPGAMesh.ps1](deploy/Join-FPGAMesh.ps1) 会尝试安装缺失工具、克隆仓库、建 GitHub fork、创建本机依赖与配置、注册两个飞书应用、逐身份发信读回、真实验证主从调用，并在登录与密钥就绪后注册常驻任务。每次输出本机 `setup-status.json` 与 `NEXT_STEPS.md`；外部授权暂缺时继续独立步骤，补齐后重跑。对应真人的详细流程见[人工步骤](deploy/HUMAN_STEPS.md)。群 ID 已由 A 机取得并内置；飞书实名认证/发布/入群、三方密钥和账号登录仍由各成员完成，仓库所有者须授予上游写权限才可自动认领未指派共享任务。

各 ZIP 均从**已提交且干净**的 Git 文件生成，附 `MANIFEST.json`、修订号和逐文件 SHA-256；客机包由相同的已提交源码按节点 B/C 生成，A 机技能源码与本机安装不被改动：

```powershell
python -m fpga_mesh.distribution --profile mesh --output artifacts/CarlandFPGA-mesh.zip
python -m fpga_mesh.distribution --profile pynq-skill --output artifacts/pynq-z2-single-node.zip
python -m fpga_mesh.distribution --profile pynq-client-b --output artifacts/pynq-z2-client-b.zip
python -m fpga_mesh.distribution --profile pynq-client-c --output artifacts/pynq-z2-client-c.zip
```

本机回归：

```powershell
& .local\venv\Scripts\python.exe -m unittest discover -s tests -q
```

详细操作和逐项验收见 [运行说明](docs/deployment/OPERATIONS.md) 与 [部署状态](docs/deployment/DEPLOYMENT_STATUS.md)。设计依据见 [多 Agent 设计稿](docs/superpowers/specs/2026-09-29-fpga-multi-agent-design.md)。

# 已接入节点的原地更新

本次更新沿用各成员现有项目目录、Codex 登录、指定 DeepSeek key 文件、两个飞书身份、任务记录、节点地址和 Git/fork。独立 PYNQ 单机技能不需要重装。请将新 Mesh ZIP 解压到临时目录，**不要直接覆盖工作区，不要重跑 Join-FPGAMesh**。已有节点等当前主/子任务完成，确认没有待处理派工后更新。

把下面任务交给本机 Codex：

> 我已接入 CarlandFPGA。请用此包的 `deploy/Update-FPGAMesh.ps1` 原地更新我的现有工作区，使用原节点字母、配置和 `.local/venv/Scripts/python.exe`。先 `-CheckOnly` 核对；已知旧版本只替换实际变化文件。遇到本地文件冲突，先比较并保留我的改动，合并后重新检查，禁止强制覆盖。不要重克隆、重建节点、创建新飞书应用、复制别人凭据或重跑接入。完成后核验原常驻服务、官方模型目录及权限、Flash/max 双入口，提供本机真实结果。不要把 A 的验收当作本机已上线。

例如 B 机，路径替换为本机实际路径，C 机把 B 改成 C：

```powershell
pwsh -NoProfile -File C:\Temp\MeshUpdate\deploy\Update-FPGAMesh.ps1 `
  -Node B -Workspace C:\Users\User\Documents\CarlandFPGA `
  -Package C:\Downloads\CarlandFPGA-mesh-update-v0.8-2026-10-11.zip -CheckOnly

# 检查通过后去掉 -CheckOnly，执行同一命令。
```

自定义配置/Python 路径可追加 `-Config <原配置路径> -Python <原venv Python>`。脚本停止原节点任务，备份改动文件，更新源码，安装本项目 MCP，复用原配置重载同名常驻任务，再刷新官方模型和角色。整个更新不发起模型推理，不重新安装工具链。新角色/MCP 在新加载的 Codex 项目会话生效；已生成的回合保持原模型。源码以包内 MANIFEST 的 revision 为准；当前 GitHub 远端尚未包含本次源码，不要以 `git pull` 替代此包。

更新器默认只检查，`--apply` 才写入。每个路径验证 ZIP CRC、大小、SHA-256、旧版本哈希和目标范围；Windows Git 的文本 LF/CRLF 差异兼容。未知本地编辑、缺失基础文件、路径越界或活动任务会在写入前阻止更新。未改动文件不写入，Git 记录不重置。备份保存在 `.local/update-backups/<id>/`，回执包含本次修改清单；写入故障回滚自身已完成写入，不覆盖其间产生的新编辑。异常终止后应由主模型检查回执和备份；若留下 `update.lock`，先确认没有另一个更新进程再处理，不自动重放。

本轮变化：独立主任务自动开会话；主会话在回合边界自主选官方模型和深度；十个旧 GPT 角色迁移至官方 Codex，兼容别名明确标记；新增 `deploy/更新官方模型.cmd`；DeepSeek Flash 固定最高 `max`，按实际派工分配与回收，无默认两个/最低/固定数量；特殊需要保留原生 GPT，租约/去重/文件所有权阻止重复或并发冲突；修复重试、大帧与常驻故障恢复。

新 runtime 不再读取旧 `target_children` 设置，本机 Codex 可仅删除原节点配置顶层的这条废弃设置；其余配置保留。所有 GPT 主会话沿用本机 Astra，所有 DeepSeek 子实例沿用本机 DeepSeek。人类 > 主 > 子及原权限不变；决策、验收、重难点、关键优化和评估仍由质量主模型最高可用深度完成。子代理用于节省 GPT usage 和分担执行，不能承担质量主模型的职责。

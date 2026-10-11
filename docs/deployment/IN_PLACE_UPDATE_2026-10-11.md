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

自定义配置/Python 路径可追加 `-Config <原配置路径> -Python <原venv Python>`。脚本先锁定主任务、子派工和收件箱的现有账本写入，再检查空闲并保持锁直到原服务完全停止，避免检查后新派工抢入；活动任务或写入竞争会在停止服务前拒绝更新。之后备份改动文件，更新源码，安装本项目 MCP，复用原配置重载同名常驻任务，再刷新官方模型和角色、只读核对本节点 Astra 文件权限。整个更新不发起模型推理，不重新安装工具链。新角色/MCP 在新加载的 Codex 项目会话生效；已生成的回合保持原模型。源码以包内 MANIFEST 的 revision 为准；当前 GitHub 远端尚未包含本次源码，不要以 `git pull` 替代此包。

更新器默认只检查，`--apply` 才写入。每个路径验证 ZIP CRC、大小、SHA-256、旧版本哈希和目标范围；Windows Git 的文本 LF/CRLF 差异兼容。未知本地编辑、缺失基础文件、路径越界或活动任务会在写入前阻止更新。未改动文件不写入，Git 记录不重置。备份保存在 `.local/update-backups/<id>/`，回执包含本次修改清单；写入故障回滚自身已完成写入，不覆盖其间产生的新编辑。异常终止后应由主模型检查回执和备份；若留下 `update.lock`，先确认没有另一个更新进程再处理，不自动重放。

本轮变化：独立主任务自动开会话；主会话在回合边界自主选官方模型和深度；十个旧 GPT 角色迁移至官方 Codex，兼容别名明确标记；新增 `deploy/更新官方模型.cmd`；DeepSeek Flash 固定最高 `max`，按实际派工分配与回收，无默认两个/最低/固定数量；特殊需要保留原生 GPT，租约/去重/文件所有权阻止重复或并发冲突；修复重试、大帧与常驻故障恢复。

主请求若已有持久 `failed` 或 `interrupted` 结果，控制器直接保留原错误并退役待重试收件项，禁止重新打开客户端或重放副作用；质量主模型检查后使用新的显式任务版本/工作分配恢复。已完成请求仍复用原结果。若旧 runtime 留有失败收件项而阻止更新，先由质量主模型逐条核对持久失败证据并明确退役；不要停掉正在执行的任务或清空任务数据库。

原生 GPT 租约标为取消或中断并不证明执行进程已停止。与文件所有权规则一致，原生 `interrupted` 或 `native stop unconfirmed` 记录继续阻止更新；父级取得子进程实际停止证据并通过原 `fpga_native_complete` 确认后再更新，不清空或改写租约来绕过。

本轮还增加 Astra 的 `im:resource`（获取/上传图片与文件），用于由主身份发送更新包、读回并核对下载哈希。Astra-A 已在本人明确授权后开通，原应用和密钥沿用；DeepSeek 权限完全保留，人类 > 主 > 子不变。新建 Astra 的注册配置已包含该权限，DeepSeek 注册配置不变。已有 B/C 的云端权限不能通过源码 ZIP 自动复制：更新后若回执为 `needs_admin_grant`，由该机应用所有者在回执的 `manage_url` **仅为现有 Astra 应用**添加应用身份 `im:resource`，按后台要求发布，再执行以下只读核对；禁止创建新应用或给 DeepSeek 增权。缺少此权限时如实报告文件功能待开通，不能标记已可上传。

```powershell
.\.local\venv\Scripts\python.exe -m fpga_mesh.feishu_permissions `
  --config .local\deployment\node-b\node-b.toml
```

新 runtime 不再读取旧 `target_children` 设置，本机 Codex 可仅删除原节点配置顶层的这条废弃设置；其余配置保留。所有 GPT 主会话沿用本机 Astra，所有 DeepSeek 子实例沿用本机 DeepSeek。决策、验收、重难点、关键优化和评估仍由质量主模型最高可用深度完成。子代理用于节省 GPT usage 和分担执行，不能承担质量主模型的职责。

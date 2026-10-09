# 节点 @NODE@ 的 PYNQ-Z2 客机技能

此 ZIP 仅供客机 @NODE@。先解压，再从解压根目录运行：

```powershell
pwsh -NoProfile -File .\skills\pynq-z2-single-node\Install.ps1
```

脚本将本包安装到当前用户 `$CODEX_HOME/skills/pynq-z2-single-node`，未设置时为 `$HOME/.codex/skills/pynq-z2-single-node`；旧版自动备份。安装后确认 `client-role.json` 的节点字母与当前机器一致。它不安装 Git、GitHub CLI、Vivado 或三机控制器，也不配置板卡；多机入网按独立协作包的 `deploy/Join-FPGAMesh.ps1 -Node @NODE@` 进行。

交接工具只需 Python 标准库；Git 与 GitHub CLI 用于提交分支和 PR。没有 GitHub 登录或网络时，先保留本地提交和清单，恢复后继续推送；不能把本地提交当作 A 已收到。此包不含实板上传脚本、SSH 密钥或板卡依赖。

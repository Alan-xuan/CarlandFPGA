# 单独安装 PYNQ-Z2 单机技能

这个 ZIP 只包含 `skills/pynq-z2-single-node/`，不配置三机控制器、飞书、GitHub 或 DeepSeek。解压后在 PowerShell 中运行：

```powershell
pwsh -NoProfile -File .\skills\pynq-z2-single-node\Install.ps1
```

脚本将技能复制到当前用户的 `$CODEX_HOME/skills/pynq-z2-single-node`；未设置 `CODEX_HOME` 时使用 `$HOME/.codex/skills`。已有不同版本会移入同目录的带随机后缀备份；同版本重跑不会重复安装。安装后在新的 Codex 会话中要求使用 `pynq-z2-single-node` 技能，先执行技能内的预检脚本，再按真实板卡和工具输出工作。B/C 仅能仿真与提交证据，实板由 A 操作。

实板自动上传需要主机 Python 的 `pyserial>=3.5,<4`、Windows OpenSSH `ssh.exe`/`ssh-keygen.exe`，以及已登录的板卡 USB 串口 shell 和直连以太网。先安装 `python -m pip install -r skills/pynq-z2-single-node/requirements-board.txt`，再运行 `python skills/pynq-z2-single-node/scripts/board_run.py`。首次运行会在当前用户 `.ssh` 生成专用客户端密钥并通过物理串口固定板卡 SSH 主机密钥；密钥文件不在 ZIP 内。若有多个 FTDI 串口或网卡，传 `--serial COMx --ifindex N`。运行输出及原始日志保存到 `artifacts/pynq-z2-single-node/live/`。

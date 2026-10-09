# PYNQ-Z2 单机开发包实板上传与回传记录（2026-10-09）

本次只验收主机到开发板的连接、文件上传完整性和板上 Python 返回值。选题初稿的采样、压缩和遥测方案仍未确定。

## 实际连接与修正

Windows 枚举出 FTDI `USB Serial Port (COM8)`；115200/8N1 串口返回 `xilinx@pynq` shell。主机直连以太网接口编号为 8，IPv4 只有 169.254 地址；板卡 `eth0` 为 `192.168.2.99/24`，两端 IPv4 不在同一子网。通过板卡 IPv6 本地地址 `fe80::200:5ff:fe6b:1f5%8` 连接 SSH 22 端口成功，无须修改 Windows 网卡地址。板卡 ED25519 主机密钥经物理串口读取并固定，指纹为 `SHA256:dhJ3JZQRqeE5qv6ZQiMIyGhcLpOS1QXuPbQdJ6V8vwU`；主机专用 SSH 公钥经串口加入板卡用户的 `authorized_keys`，私钥仅保存在当前用户 `.ssh`，未纳入开发包。

第一次上传的临时探针以系统 `/usr/bin/python3` 执行，返回 `ModuleNotFoundError: No module named 'pynq'`。板上 Jupyter 进程实际使用 `/usr/local/share/pynq-venv/bin/python3`，该环境可导入 PYNQ 3.0.1。`board_run.py` 因此优先选择 PYNQ 虚拟环境，并把串口命令回显与真实返回标记分开解析；这两项均已修进单机开发包。

## 自动运行结果

从仓库根目录执行，无须手填串口或网卡编号：

```powershell
& D:\PynqZ2\host-venv\Scripts\python.exe skills\pynq-z2-single-node\scripts\board_run.py --output-dir artifacts\pynq-z2-single-node\live
```

2026-10-09 20:02（北京时间）最终完整自动运行检测 `COM8` 与接口 8，把开发包内的 `board_probe.py` 上传到 `/tmp/carlandfpga-board-run/board_probe.py`。本地与板端 SHA-256 同为 `06aa181e2753ebb2d9f4e5fdb30d80c09abc0e73c8fa126f13772b51486afaad`。板端退出码为 0，`timed_out=false`，stderr 为空；stdout 返回 PYNQ `3.0.1`、ARM `armv7l`、Python `3.10.4`、内核 `5.15.19-xilinx-v2022.1`，以及配套 `base.bit`/`base.hwh` 文件均存在。原始记录：[result.json](evidence/pynq-z2-live-2026-10-09/result.json)、[stdout.txt](evidence/pynq-z2-live-2026-10-09/stdout.txt)、[stderr.txt](evidence/pynq-z2-live-2026-10-09/stderr.txt)。三者 SHA-256 分别为 `04e99c8f7b23dbe8c7c7557fa8c8fdb5086c6a313098aa605c3da3ec45c43eae`、`6215330dcc108c3732d391fa61eb63733a2189491ea352c64b483a859d9bb7e9`、`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

板上当前是 PynqLinux 3.0 / PYNQ 3.0.1，未把主机已下载的 PYNQ 3.1.1 镜像写入 SD 卡。本次没有加载自定义 `.bit/.hwh`，没有进行采样、时序或随钻测井指标实测；这些阶段保持 `not_run`。

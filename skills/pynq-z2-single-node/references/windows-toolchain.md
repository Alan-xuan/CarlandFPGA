# Windows 上位机与工具链

## 最小开发链路

- 主机：VS Code、Python 3 虚拟环境、串口终端、浏览器。串口或其他数据通道的最终协议由任务版本确定；当前阶段不要预设采样帧、波特率或图形界面。
- RTL 验证：已安装的 ModelSim/Questa 可用；记录 `vlog`、`vsim` 的真实版本和日志。
- PYNQ-Z2 Overlay 构建：本机已安装并激活 Vivado 2026.1 BASIC，`xc7z020clg400-1` 可用。它与 PYNQ 3.1.1 基础 Overlay 所用的 2024.1 版本不同；自定义 Overlay 的构建和板端兼容性须分别实测。Vivado 自带 XSim；若要用它，再验证 `xvlog`、`xelab`、`xsim`。
- PYNQ 运行：官方 PYNQ-Z2 v3.1.1 SD 镜像和至少 8 GB microSD；主机浏览器访问板上 Jupyter，USB 串口可用 PuTTY。主机无需另装 PYNQ/Jupyter 才能操作默认镜像。
- 直连实板传输：`scripts/board_run.py` 使用 FTDI USB 串口建立可信 SSH 连接，在直连网线的 IPv6 本地链路上传、校验并运行 Python 文件；Windows 网卡即使只有 169.254 IPv4 地址也可使用该链路。板上 PYNQ 可能装在 `/usr/local/share/pynq-venv`，系统 `python3` 未必能 `import pynq`，须以实际探测的解释器为准。
- 官方 PYNQ-Z2 board files 当前位于 `D:\PynqZ2\board_files\pynq-z2\A.0`；批处理先执行 `set_param board.repoPaths {D:/PynqZ2/board_files}`，也可直接选 part 并使用经核对的 XDC。找到板卡定义仍不能代替创建工程、综合实现和板测。

Vitis Embedded/HLS 和 PetaLinux 只有任务要求 ARM 裸机程序、HLS 或重建系统镜像时再加入。AMD Ross Vivado MCP 是可选的 AI 接口；使用旧版 Vivado 时应先实测 MCP 启动、Tcl 执行和退出，不以产品兼容声明代替测试。

AMD 官方下载安装需要 AMD 账号。选择安装版本前，核对当前 Windows 版本与 AMD 支持矩阵；安装完成后运行 `vivado -version`，再用真实 XC7Z020 工程做综合、实现和 bitstream 验证。没有这些输出时将 Vivado 阶段记为 `blocked`。

工具若不在 PATH，从本仓库根目录可这样运行静态探测：

```powershell
& .local\venv\Scripts\python.exe .\skills\pynq-z2-single-node\scripts\preflight.py --modelsim-home C:\modeltech64_2020.4
```

上面的路径是本机当前实测安装路径。其他主机应替换路径；Vivado 装妥后再加 `--vivado-home`。`preflight.py` 不启动工具，也不探测板卡。

官方资料：[AMD 2024.1 下载](https://www.amd.com/en/support/downloads/adaptive-socs-and-fpgas/development-tools/2024-1.html)、[AMD 2024.1 支持系统](https://docs.amd.com/r/2024.1-English/ug973-vivado-release-notes-install-license/Supported-Operating-Systems)、[PYNQ-Z2 设置](https://pynq.readthedocs.io/en/v3.1/getting_started/pynq_z2_setup.html)、[PYNQ Overlay 设计](https://pynq.readthedocs.io/en/latest/overlay_design_methodology/overlay_design.html)、[AMD XUP board files](https://github.com/Xilinx/xup_embedded_system_design_flow/tree/main/board_files/pynq-z2/A.0)。

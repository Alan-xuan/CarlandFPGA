# PYNQ-Z2 上位机与 FPGA 工具链部署记录（2026-10-08，许可于 2026-10-09 激活）

本记录区分“软件已装并运行”“安装资料已备齐”“受账号/实板条件阻断”。选题初稿尚未锁定上位机数据协议，因此此处部署可复用的开发、采集和观察环境，不把任一串口帧格式或性能指标写成最终方案。

## 本机已验证

| 项目 | 实际状态与路径 | 本次证据 |
| --- | --- | --- |
| Windows 主机 | Windows 11 Home 25H2，x64，build 26200 | `Get-CimInstance Win32_OperatingSystem` 与 CurrentVersion 注册表 |
| RTL 仿真/编译 | ModelSim SE-64 2020.4，`C:\modeltech64_2020.4\win64\` | 上一轮最小 RTL smoke 通过；本轮 preflight 发现 `vsim.exe`，见下方命令 |
| 编辑与 Python 调试 | VS Code 1.140.0，`C:\Users\CarlJade\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd` | `code.cmd --version`；Python、Pylance、debugpy 扩展清单核验 |
| 串口/SSH 终端 | PuTTY 0.85（含 Plink），WinGet 用户安装目录 | `PLINK.EXE -V` 输出 Release 0.85 |
| SD 镜像写入工具 | balenaEtcher 2.1.7，`C:\Users\CarlJade\AppData\Local\balena_etcher\balenaEtcher.exe`；Rufus 4.15，`C:\Users\CarlJade\AppData\Local\Microsoft\WinGet\Packages\Rufus.Rufus_Microsoft.Winget.Source_8wekyb3d8bbwe\rufus.exe` | 两者文件签名有效；尚未指定 SD 卡，均未执行写入 |
| 独立上位机 Python | `D:\PynqZ2\host-venv\Scripts\python.exe`，Python 3.12.10、pyserial 3.5、NumPy 2.5.3、Matplotlib 3.11.2 | `pip check` 无冲突；`loop://` 串口回环收发、无窗口 Agg 绘图均通过 |
| PYNQ-Z2 board files | `D:\PynqZ2\board_files\pynq-z2\A.0\` | 来源 commit 和 SHA-256 见 `D:\PynqZ2\board_files\SOURCE_MANIFEST.json`；3 个 XML 可解析 |
| PYNQ-Z2 v3.1.1 SD 镜像 | `D:\PynqZ2\downloads\pynq_z2_v3.1.1.zip`，1,926,017,023 bytes | SHA-256 `d7774bb6c56b79ea67e4dbfadca443c51ae6152b8c71799e79dd81e4782d6b03`；ZIP CRC 通过；完整清单见同目录 `SOURCE_MANIFEST.json` |
| Vivado 2026.1 | `D:\AMDFPGA\2026.1\Vivado\`，包含 VLM 和 XC7Z020 器件数据 | 2026-10-09 批处理报告 BASIC 许可证有效、XC7Z020 可用，退出码 0；详见下节 |

2026-10-08 的 `python -m serial.tools.list_ports` 返回 `no ports found`；2026-10-09 接入板卡后已发现 FTDI `COM8` 并完成真实串口/SSH 上传回传测试，详见 [板测记录](SINGLE_NODE_BOARD_LIVE_2026-10-09.md)。早期上位机环回测试仍不能当作板卡通信测试。

2026-10-09 更新后的全仓 `python -m unittest discover -s tests -q` 为 **207/207 通过**；`compileall` 与 `git diff --check` 退出码为 0。测试运行时已有 Feishu 验证链接输出和第三方 deprecation/asyncio 警告，本轮没有按该链接操作；它们不构成 FPGA 实板证据。

可复核的静态工具发现命令：

```powershell
& .local\venv\Scripts\python.exe skills\pynq-z2-single-node\scripts\preflight.py --vivado-home D:\AMDFPGA\2026.1\Vivado --modelsim-home C:\modeltech64_2020.4
```

当前返回 `modelsim.available=true`、`vivado.available=true`，分别定位 `C:\modeltech64_2020.4\win64\vsim.exe` 和 `D:\AMDFPGA\2026.1\Vivado\bin\vivado.bat`；`board.status=not_checked`。该脚本只检查可执行文件，不验证许可证或板卡。

## Vivado 2026.1 许可状态

本机已安装 Vivado 2026.1。AMD 从该版开始要求启动前有许可证；[2026.1 器件表](https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Device-Availability-by-Subscription-Tier)列明免费的 BASIC 层级支持全部 Zynq-7000 器件，包含 PYNQ-Z2 使用的 XC7Z020。[AMD 许可 FAQ](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/licensing-faq.html)说明 BASIC 需要免费、按年续期的许可证文件。2026-10-09 已在 AMD 产品许可门户生成 `Vivado Basic Tier License, Node Locked License` 的 1 席节点锁定证书，并从门户下载、安装到 `C:\Users\CarlJade\AppData\Roaming\XilinxLicense\Xilinx.lic`。原始下载文件与安装副本的 SHA-256 一致；许可文件不进入 Git 或分发包。

按 [AMD 安装说明](https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Install-Certificate-Based-Node-Locked-License-Key-File)放入 `%APPDATA%\XilinxLicense` 后，运行 `vivado.bat -mode batch -source <Tcl> -nolog -nojournal`，输出 `A valid Vivado Design Suite BASIC license has been detected. Your current license is active and will expire on 08-oct-2027.`；`get_parts xc7z020clg400-1` 返回 1，`create_project -in_memory -part xc7z020clg400-1` 成功，进程退出码为 0。`vivado.bat -version` 单独调用仍返回 1，因此以真实批处理会话和许可诊断为激活依据。尚未运行具体设计的综合/实现，也未生成 `.bit/.hwh`。

批处理 Tcl 内容（实际文件位于 `%TEMP%\pynq_vivado_license_probe.tcl`）：

```tcl
set_param board.repoPaths {D:/PynqZ2/board_files}
puts "PART_COUNT=[llength [get_parts xc7z020clg400-1]]"
puts "BOARD_COUNT=[llength [get_board_parts *pynq-z2*]]"
create_project -in_memory -part xc7z020clg400-1
puts "PROJECT_PART=[get_property PART [current_project]]"
exit
```

PYNQ 3.1 的基础 Overlay 由 Vivado 2024.1 构建；本机当前版本为 2026.1，后续 Overlay 兼容性必须实测。官方 PYNQ-Z2 board files 位于 `D:\PynqZ2\board_files\pynq-z2\A.0`；批处理执行 `set_param board.repoPaths {D:/PynqZ2/board_files}` 后，`get_board_parts *pynq-z2*` 返回 1，无须向受保护的 Vivado 安装目录写入。

安装器和许可证文件不得混入 Git/分发 ZIP。AMD Ross Vivado MCP 仅在 Vivado 本体可用后再连接并做 Tcl 烟测。

## 开发板启动与下一阶段

官方 PYNQ-Z2 v3.1.1 镜像已下载并校验，ZIP 内是单个 `pynq_z2_v3.1.1.img`。已展开到 `D:\PynqZ2\downloads\pynq_z2_v3.1.1.img`，8,337,309,696 bytes，SHA-256 为 `4a6ac1cdbb413d768fcb059b7182e1f53aa7f728b898b7f5061cbb0b7cc93aab`。写卡前必须核对可移动盘设备，不能根据盘符猜测；当前没有明确 SD 卡目标，尚未写卡。板上 Jupyter 由镜像提供，主机浏览器通过以太网访问；USB 串口可用 PuTTY，官方设置为 115200/8N1、无流控。板卡接入后再保存端口枚举、镜像版本、启动日志和 Overlay 实测。

Rufus 启动验证触发 Windows 管理员授权提示，已中断启动；随后复查 `consent.exe` 已退出，没有授权或执行写卡。Raspberry Pi Imager 的安装因需要同类授权而取消；已安装的 Etcher/Rufus 已备好，待确认可移动 SD 卡后再验证实际写卡。

参考：[PYNQ-Z2 设置](https://pynq.readthedocs.io/en/v3.1/getting_started/pynq_z2_setup.html)、[PYNQ Overlay 文件要求](https://pynq.readthedocs.io/en/latest/overlay_design_methodology/overlay_design.html)、[PYNQ 3.1 镜像构建版本](https://pynq.readthedocs.io/en/v3.1/pynq_sd_card.html)、[AMD XUP PYNQ-Z2 board files](https://github.com/Xilinx/xup_embedded_system_design_flow/tree/main/board_files/pynq-z2/A.0)。

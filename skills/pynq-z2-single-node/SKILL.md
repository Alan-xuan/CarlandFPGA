---
name: pynq-z2-single-node
description: Use when developing or verifying an FPGA design for the AMD PYNQ-Z2 on one computer, including RTL simulation, Vivado implementation, PYNQ overlay board tests, or evidence handoff to machine A in a multi-machine project.
---

# PYNQ-Z2 单机 FPGA 开发

本技能在单机上独立完成一次可复现的设计迭代；三机服务不是前置条件。选题初稿与外来技能包只提供候选思路，不能把 AD7606、300 bps、压缩率、延迟、Ryzen AI 或数字孪生当成已确定的接口和验收线。

## 开始一次迭代

1. 记录任务 ID/版本、代码提交与未提交改动、实际器件/板卡、输入输出、时钟与复位、接口和本轮验收指标。由当前需求确定阈值；未确定的项标为待定，不生成声称达标的结果。
2. 运行 `python <skill-dir>/scripts/preflight.py`，保存 JSON。工具不在 PATH 时传 `--vivado-home` 或 `--modelsim-home` 指向安装目录；脚本只探测命令路径，板卡恒为 `not_checked`。另行核实工具版本、镜像、线缆、外围电路和真实板卡状态。查板卡与工具细节时读 [PYNQ-Z2 参考](references/pynq-z2.md) 和 [Windows 工具链](references/windows-toolchain.md)。
3. 建立独立于 RTL 的黄金模型和可重放激励，再实现 RTL。按实际模块验证边界值、协议字段/CRC/序号、背压及 FIFO 满空。涉及多个时钟/复位时，核对 CDC/RDC 与所选 FIFO 的复位契约；异步复位按域同步释放，覆盖时钟延迟/停止、不同释放顺序、FIFO 空/满/传输中重启和单侧复位策略。对 XPM FIFO 遵守其 `rst`/`wr_rst_busy`/`rd_rst_busy` 门控要求。仿真不能代替亚稳态或板上证明。
4. 用现有 Vivado Tcl/命令行或 GUI 复现综合、实现和 bitstream；记录实际约束、工具版本、LUT/FF/BRAM/DSP、未约束路径、DRC 与实现后时序报告，含适用的复位 recovery/removal 检查。指标由本轮批准的设计目标给出，不能只用综合估计声称时序收敛。若系统使用 PYNQ Overlay，保留同一次构建的 `.bit` 与 `.hwh`。
5. 有实板和必需外围条件时，在板上加载、执行并保存版本、串口/程序日志、测量数据及异常恢复结果。没有工具、镜像、外围器件或板卡时，分别记 `blocked` 或 `not_run`，不写成板测通过。

## 实板自动上传与回传

板卡已通过 USB 串口登录且直连以太网可用时，运行 `python <skill-dir>/scripts/board_run.py`。首次运行需要主机 Python 安装 `pyserial`、Windows OpenSSH，并保持板卡串口处于已登录的 shell；脚本自动找 PYNQ FTDI 串口、通过串口读取并固定 SSH 主机公钥、给当前板卡用户安装本机专用 SSH 公钥，通过 IPv6 本地链路上传 `board_probe.py`，对比两端 SHA-256，使用板上 PYNQ 虚拟环境执行，并保存 stdout、stderr、退出码和连接元数据。私钥留在当前用户的 `.ssh`，不可打入 Git 或分发包。执行自己的 Python 文件时传 `--script <文件>`；日志目录可用 `--output-dir <目录>` 指定。串口不在已登录 shell、没有直连网络或主机密钥不匹配时，按脚本错误定位，不能把传输失败写成板测通过。已引导的板卡可用 `--host <IPv6本地地址> --ifindex <网卡编号>` 跳过串口。

上传/解释器烟测只证明传输与板上 Python 运行。自定义 FPGA 设计仍须按上面的阶段单独构建、加载同次生成的 `.bit/.hwh`，再验证目标接口与实测指标。

## 工具与协作

本地已可用的仿真器与 Vivado Tcl 是默认执行通道；发现并验证 AMD 官方 Vivado MCP 后可选用，仍以真实工具输出为证据。公众号的 Codex + DeepSeek + Vivado MCP 组合是可参考的协作形式，不要求特定模型、全局权限设置或 MCP 才能运行本技能。

三机使用时，B/C 可开发、仿真并交付代码与测试建议；只有 A 安排物理 PYNQ-Z2 操作。按 [交接清单](references/handoff.md) 生成并核验请求、日志与文件哈希。该清单不自动提交现有 `HardwareService`，也不启用 `hardware_enabled`；`passed` 必须对应非空、真实可审阅的运行日志。若课题采用随钻测井链路，另读 [遥测方案选项](references/telemetry-option.md)。

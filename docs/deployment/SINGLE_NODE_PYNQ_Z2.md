# PYNQ-Z2 单机 FPGA 开发技能

## 用途

本技能在一台机器上完成 PYNQ-Z2 设计的需求整理、RTL 与黄金模型、仿真、Vivado 构建、板测和证据归档。它也能脱离三机控制器单独使用。选题初稿只是方向：AD7606、300 bps、压缩方案、Ryzen AI 和数字孪生在任务明确选定后才进入验收指标。

源码入口是 [SKILL.md](../../skills/pynq-z2-single-node/SKILL.md)。安装后可向 Codex 提出“使用 pynq-z2-single-node 技能检查/开发这个 PYNQ-Z2 任务”。技能的板卡资料和低速遥测候选检查分别放在 references 目录。外来 ZIP 里的六个技能没有直接安装，也没有赋予它们隐式触发权。

## 本机入口

从仓库根目录运行下列命令；Windows 上用实际 Python 3.12 解释器代替失效的 WindowsApps python 别名：

    & .local\venv\Scripts\python.exe skills\pynq-z2-single-node\scripts\preflight.py

preflight 输出 JSON，报告 Vivado、ModelSim 的本机发现结果。board.status 为 not_checked 时，表示脚本没有连接或操作开发板。环境探测不能代替仿真、综合、时序和实板测量。

本机已安装的 ModelSim 不在 PATH 中，可加 `--modelsim-home C:\modeltech64_2020.4`。本次 Windows 上位机软件、板卡资料、Vivado 账号门槛和实际验证记录见 [HOST_TOOLCHAIN_2026-10-08.md](HOST_TOOLCHAIN_2026-10-08.md)。

确定本次任务后，先锁定代码提交、目标板、外设和接口，再逐层保留记录：

1. RTL 和独立黄金模型：保留刺激、期望值、日志和失败最小反例；在设计采用 CDC/FIFO/复位时验证这些路径。
2. 综合与实现：保留实际 Vivado 命令、资源与时序报告，和本次任务明确的阈值比较。
3. PYNQ 运行：使用相互匹配的 .bit/.hwh；记录镜像、上板命令、外设连接、原始测量和结果。只有真实执行的阶段可标为 passed。
4. 缺少工具、外设或开发板时，把对应阶段记录为 blocked 或 not_run。不能用理论估计冒充板测。

官方器件为 XC7Z020-1CLG400C，Vivado part 为 xc7z020clg400-1。PYNQ-Z2 仍可使用 PYNQ 3.1.1 镜像；PYNQ 4.0 已移除该板支持。板文件、XDC 和 Overlay 使用约束详见技能参考文件。

## 与三机协作系统的边界

单机技能的 handoff.py 创建 request + stages + 文件 SHA-256 的 JSON 清单。request 字段与 fpga_mesh.hardware.HardwareRequest 一致：operation_id、task_id、task_version、requester、code_commit、test_steps、expected_result。调用格式：

    & .local\venv\Scripts\python.exe skills\pynq-z2-single-node\scripts\handoff.py create --root <任务根目录> --input <输入JSON> --output <交接JSON>
    & .local\venv\Scripts\python.exe skills\pynq-z2-single-node\scripts\handoff.py verify --root <任务根目录> --manifest <交接JSON>

输入 JSON 包含 request 对象、artifacts 相对路径数组及 stages 映射。阶段状态使用 passed、failed、blocked、not_run；passed 必须附带 root 内存在的非空日志路径。create 与 verify 会核验文件相对路径、大小与 SHA-256，但并不判断日志里技术结论是否正确；A 和同伴仍需审阅实际输出。

B/C 可以独立开发和仿真，通过现有 fpga_peer_send 通道把提交号、清单位置及测试建议交给 A。板卡只能由 A 操作。当前三机控制器的真实硬件适配器和自动提交工具尚未交付，且未知状态保护有待补强，因此安装这个技能不会自动启用硬件队列或远程烧录。相同 operation_id 的重试必须先核对既有结果；不确定的上板状态应先人工/实测核对，再继续操作。

## 当前验收边界

本机可验证技能结构、脚本行为、ModelSim 可用性及与三机 HardwareRequest 的数据兼容。若 Vivado 不在本机、开发板未接入，综合实现与板测须在具备工具/硬件的机器上用真实记录补验。本技能不假定最终随钻测井实现方案。

2026-10-09 已接入板卡并完成真实串口、SSH、上传及板上 Python 回传烟测。运行入口为 `skills/pynq-z2-single-node/scripts/board_run.py`；无参数时自动选择唯一的 FTDI 串口和可达网卡，上传 `board_probe.py`，比对 SHA-256 并保存原始 stdout/stderr 与退出码。主机运行示例：

```powershell
& D:\PynqZ2\host-venv\Scripts\python.exe skills\pynq-z2-single-node\scripts\board_run.py --output-dir artifacts\pynq-z2-single-node\live
```

首次使用要求串口已登录到板卡 shell；脚本在用户 `.ssh` 下建立并固定 SSH 密钥，不将私钥放进项目 ZIP。板卡本次实际镜像为 PYNQ 3.0.1，包在 `/usr/local/share/pynq-venv`；系统 `python3` 找不到 `pynq`，脚本会选择正确的虚拟环境。原始板测证据与本次问题详见 [SINGLE_NODE_BOARD_LIVE_2026-10-09.md](SINGLE_NODE_BOARD_LIVE_2026-10-09.md)。这一步验证连接与板端运行，不代表自定义 RTL、Overlay 或随钻测井链路已经上板通过。

参考：[AMD PYNQ-Z2](https://www.amd.com/en/corporate/university-program/aup-boards/pynq-z2.html)、[XilinxBoardStore](https://github.com/Xilinx/XilinxBoardStore/tree/master/boards/TUL/pynq-z2/A.0)、[PYNQ 3.1.1 XDC](https://github.com/Xilinx/PYNQ/blob/3.1.1/boards/Pynq-Z2/base/vivado/constraints/base.xdc)、[PYNQ Overlay](https://pynq.readthedocs.io/en/latest/pynq_libraries/overlay.html)、[AMD Vivado MCP](https://www.amd.com/en/support/downloads/ross-agentic-ai.html)、[公众号参考文章](https://mp.weixin.qq.com/s/0UOMTskrAL640sUBV0A01Q)。

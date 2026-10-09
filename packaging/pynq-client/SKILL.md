---
name: pynq-z2-single-node
description: Use when developing or verifying PYNQ-Z2 FPGA work on client node @NODE@ without physical board access, including RTL simulation, Vivado reports, Git handoff, and review of A's board feedback.
---

# PYNQ-Z2 单机开发：客机节点 @NODE@

本包安装到节点 @NODE@。先读取同目录 `client-role.json`，确认 `node` 为 `@NODE@` 且 `board_access` 为 `false`；若机器身份不符，改用对应客机包。该节点可独立设计、仿真、综合和实现，但不连接、上传、配置或声称测过物理 PYNQ-Z2。只有 A 机上板。课题初稿中的器件、链路速率与指标都是候选，先按当次任务确定验收条件。

## 本机开发

1. 在 CarlandFPGA 仓库的节点 @NODE@ 功能分支工作。记录任务 ID/版本、输入输出、时钟/复位、实际本机工具版本和目标器件。运行 `python <skill-dir>/scripts/preflight.py`；它只发现 Vivado/ModelSim 路径，`board.status=not_checked` 不代表硬件可用。
2. 用独立黄金模型、可重放激励和真实日志验证 RTL。若本机有 Vivado，可保存综合、实现、DRC、未约束路径、利用率和实现后时序报告；若无工具，将该阶段记为 `blocked` 或 `not_run`。需要板级资料时读 [PYNQ-Z2 参考](references/pynq-z2.md)；任务选择随钻测井链路时再读 [候选检查](references/telemetry-option.md)。
3. 保存源文件、约束、测试脚本、可公开的原始日志和必要的 `.bit/.hwh` 对应关系。仓库忽略 `logs/`、`*.log` 和 `artifacts/`，供交接的日志应保留原始字节并放到任务目录内的 `.txt` 文件，再确认 Git 实际跟踪。仿真、综合、实现和 A 机板测分别记状态；客机的硬件阶段始终是 `blocked` 或 `not_run`，不得因存在 bitstream 记为 `passed`。

## 提交 A 机板测

按 [Git 交接与反馈](references/handoff.md) 完成以下闭环：先提交设计与本机证据，记录源码提交 SHA；用 `scripts/handoff.py` 为仓库内文件生成并校验包含 `request_hash` 与 SHA-256 的清单；再提交清单、推送节点 @NODE@ 分支，向 `carolwjade/CarlandFPGA` 的 `main` 发 PR。PR 写明 operation ID、源码 SHA、清单路径、测试步骤与预期结果。公开仓库不提交凭据、私人板卡标识或未脱敏日志。现有多机控制器可用时，把 PR 地址和 request hash 通知 Astra-A；PR 是可追溯的正式交接，不依赖飞书在线。

A 在 A 机核对 PR、上传并测试同一提交后，将包含 operation ID、request hash、实测提交 SHA、阶段状态及证据位置/哈希的反馈留在该 PR。节点 @NODE@ 收到通知再读取反馈，核对身份与版本；只有引用真实板卡日志且对应本次提交的 A 机结果，才可把硬件阶段标记为实测。失败时修正代码，提交新版本和新 operation ID/清单，请 A 重测。等待期间继续本机可做的开发，避免轮询或重复提交。

安装本包不会启用三机控制器的硬件队列，也不向客机提供 `board_run.py`。`Install.ps1` 仅安装本技能；多机控制器另由其部署包安装。

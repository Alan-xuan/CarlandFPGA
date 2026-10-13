# C 单机最优方案定稿：矿脉深瞳

2026-10-14（北京时间）；负责人 C/Astra-C，质量主模型 gpt-6-astra/ultra。

**定稿选择：现有 Ryzen 7 8845H AI PC + PYNQ-Z2，以真实传感、PL 编码与事件调度、共享低速链路、端侧小模型和 FPGA 实际输出驱动数字孪生。** 无现实钻头执行器；不预购新电脑；NPU 是有实测门槛的增强。首轮机械方案和第二轮待统一条款由本目录明确收敛。本轮完成方案交付，不启动实施、采购或板测。

本目录是 C 自己的完整推荐，不是三机最终选型，不要求 B 新回执或 A 终验后才成立。既有 A/B 首轮意见已在第二轮消化；不等待新的外评。原有首轮、第二轮冻结文件保留历史语义，本目录在 C 方案中优先适用。

- [可执行任务书](TASKBOOK.md)：目标、选型、模型、资源、验收和自动推进。
- [C 候选接口定稿](PROTOCOL.md)：帧字段、预算、因果关联、重启及故障行为。
- [任务依赖与当前阶段](tasks.json)：可被后续 agent 读取的任务卡；不是自动执行授权。
- [证据与范围](EVIDENCE.md)：真人范围、来源、历史冻结与未执行事项。
- [复核脚本](validate.py)及[本轮复核结果](validation.json)：验证哈希、链接、任务图、CRC 参考值和预算算术；不代表 RTL 仿真或硬件通过。
- [最终字节清单](manifest.json)：本目录交付文件的 SHA-256。

复核命令（Python 3 标准库，从仓库根运行）：

```powershell
python -X utf8 docs/competition/deepeye-2026/round2/c/final/validate.py
```

本轮身份：`task-1a2875a7abef3ef5bcc824eb / 1791910536639`；`work_id=C-independent-final-v1`；仅写 `docs/competition/deepeye-2026/round2/c/final/**`。研究沿用 `COMP-20261013-DEEPEYE/v2`。公开交付沿用 [PR #15](https://github.com/carolwjade/CarlandFPGA/pull/15)，首轮原件在 [PR #14](https://github.com/carolwjade/CarlandFPGA/pull/14)。

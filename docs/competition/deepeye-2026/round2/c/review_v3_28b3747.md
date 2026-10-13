# C 对 A 版本3受影响项的复核

任务 COMP-20261013-DEEPEYE / v3。质量主会话 Astra-C 完成工程判断；仅研究与文档复核。输入为 A commit `28b37470d58d7b28dbdddd093ec348a8dfa87cd3` 的 `taskbook_v3.md`，独立下载 SHA256 `d21c308e24d02aeafef9e98d53e40d33eb9e2135e0f2c830b696c6dfef22b641` 匹配。首轮、v2及同机 C 的 `final/` 原件均不改。

## 结论与最小真实任务

认可 v3 将应用自选与指南3.2区分、保留 ROCm 和真实物理任务两道未关闭门槛。推荐保留 **MCP6S21 传感前端自动量程**，比再增加光源或机械装置更贴近现有传感输入范围：真实传感输入→窄带观测→PC 模型有限增益建议→PL SPI 控制→模拟输出改变→独立 ADC 前后测量。虚拟钻头仍只作数字孪生。工程上的真实电气作用不能代替赛事对“物理任务”的认可；没有依据时保持 blocked，不宣称联合合规签署。

Microchip DS21117B 第1–3、19–22页支持2.5–5.5V供电及所选增益。G=1/2/4/8对应寄存器码0/1/2/4，码3是5倍。MCP6S21没有串行输出引脚，不能设计“SPI读回实际增益寄存器”作为验收；A0/A3模拟测量是正确方向。应固定 VREF、两路标定/采样偏斜、稳定时间、低分母无效阈值及上下电默认状态。AN990第5页支持数字控制PGA用于宽动态传感调理，没有给出本项目AI优越性或赛事认可。

R04/A05的真实回读、不可达分组、断线反例和全部失败保留可接受。A05还应包含固定1倍、确定性阈值量程和AI三种同输入基线，报告饱和、反推误差、换档次数与收敛时间；不得把仅完成传统自动量程写成AI增益。接线、模型、ROCm及板测均未执行。

## ROCm设备取舍

优先对 A 的8845H/32GB做有界兼容性试验，但不能写成已受官方整机支持。独立核读7.14.0及7.14.1完整HTML：780M单元格的条件绑定是 Ryzen 9 270、7 PRO 250、7 260、7 250；没有8845H。相同gfx1103及存在安装包只能构成试验依据。7.14.1矩阵列 Windows 11 25H2、Adrenalin26.6.4/OEM26.10.28。但同版两个AMD地址有内容差异：rocm.docs主站Windows/WSL框架栏为PyTorch2.12.0，rocm-handbook指南页为2.11.0。以主站选择器、对应安装页和真实成功环境联合冻结，不混抄，也不凭页面版本号消除差异。NPU驱动32.0.203.240不是上述GPU兼容证明。

R02/C03须保存实际GPU/HIP识别、ROCm版本、项目算子真实落点、CPU数值对照及1000次离线推断。失败时优先借用矩阵明确列出的 Ryzen AI 9 HX370/32GB，再核其完整OS/驱动/框架组合，不默认买Max395。CPU/NPU基线不能代替3.2所需ROCm项目路径。

## ABI与时延剩余问题

四类32B响应的18B负载、请求type/seq/session关联及删除queue输入均接受。以300baud、8N1、8秒和累计0.2秒guard计算，144/200/204B分别为62.5%/85.833%/87.5%；GAIN替换后的140B为60.833%。这是字节预算通过，不是调度或实测通过。

1. **缓存ACK与TTL必须消歧。** “重发原应答”若指原始字节，与首字节时刻的tick/remaining语义冲突。首个ACK丢失后，主机第一次收到重传旧TTL，也会高估有效期。只缓存不可变应用结果；每次实际发送重新取得当前tick、remaining、fault和capture；已过期回stopped。同一应用代次的主机截止不得因重传延长。R03/B05增加首ACK丢失、临近过期和过期后重试反例。
2. **grant还须具体定义。** 若采用已有合法帧结束触发的隐式槽，冻结触发类型、槽起止、最大字节、超时及丢帧后禁止发送的规则；如加独立grant帧，须重新计费，当前百分比不含此新帧。
3. **时延须给到达条件。** 每8秒一个EVENT额度不保证任意突发事件3秒到达。隔离单事件与合并洪泛，冻结事件间隔/突发包络。8秒TELEM后的新阶跃还需等待观测和GAIN串行传输，故不能由平均预算推导物理P99≤8秒；A05必须随机化阶跃相位，说明事件快速观测触发路径，或据预算修订目标。合并/超时样本保留分母。
4. **自动化措辞仍不一致。** §10允许授权后agent提交，S7/A04仍统一写人类提交。统一为agent上传并读回正式回执，仅本人认证等不可代办步骤交人类；该条不额外授予付款或提交权限。

因此：架构和新增任务卡方向接受；ABI冻结仍需以上消歧，ROCm与真实任务两资格门保持待验证。本意见不等于RTL、板测、模型、采购或赛事认可已完成。

## 可核验来源与边界

- [A根稿精确版本](https://github.com/carolwjade/CarlandFPGA/blob/28b37470d58d7b28dbdddd093ec348a8dfa87cd3/docs/competition/deepeye-2026/taskbook_v3.md)。
- [ROCm7.14.1矩阵](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html)原始SHA256 `415fe5cf4e1070ac962f36cb3fb359288acaf80b55bdf475ffd4f78a27b97ed3`；本地留存的[AMD同版指南矩阵](https://rocm-handbook.amd.com/projects/amd-rocm-programming-guide/en/docs-7.14.1/compatibility/compatibility-matrix.html)原始SHA256 `b3a69312dc827b8a2bdb0868122516f2019d66963344c10b0098ca5ecb687a46`。只支持所列组合，不支持未测整机承诺；两个地址的框架栏差异保留。
- [ROCm7.14.0矩阵](https://rocm.docs.amd.com/en/docs-7.14.0/compatibility/compatibility-matrix.html)，原始SHA256 `b493666036c721c145542b658b6168bf5d3e6171fcfab2cf66ef1c84ea2ee94c`。
- [MCP6S21 DS21117B](https://ww1.microchip.com/downloads/en/DeviceDoc/21117B.pdf)，741754B，SHA256 `012e5e55acf350c43fb74cb29239503b223ac4c27f9ff7ef25c2e51b88b93692`。
- [Microchip AN990](https://ww1.microchip.com/downloads/en/AppNotes/00990a.pdf)，269260B，SHA256 `14b2d40448798efc617f19f3777782dde626d8ca5866c01d69f9cabd6812aead`。

上述原始下载与核读留在本机 `.planning/competition-20261013/final-review/`。C既有完整任务书位于PR15原head `3d428cd41a206b88058e08ee4072ecc0d39a9a30` 的 `round2/c/final/`，其TASKBOOK SHA256为 `fec711bec2fb7cfed5b33a34df79bddd36af5a11282c8f7eecfe2f7af9f24f00`；它是v2历史版本，不追认成3.2合规终验。

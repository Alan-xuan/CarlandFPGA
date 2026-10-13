# 矿脉·深瞳：真实案例与可用技术来源

任务：COMP-20261013-DEEPEYE v1；work_id：A-technical-case-sources-v1。A 本地研究子任务，供质量主模型比较与选题。检索日：2026-10-13，以下链接均在当日检索；截至 2026-11-04 的方案仍由主模型确定。本文件没有板测、综合、模型训练或钻进实验结果，外部实现不能证明本装置已实现同等性能。

## 一手来源：支持范围与迁移边界

| 来源与检索日期 | 支持什么 | 不支持什么；可用经验 |
|---|---|---|
| [SLB《Measurements at the Bit》](https://www.slb.com/-/media/files/oilfield-review/p44-54)，2026-10-13；历史 Oilfield Review 技术文章 | PowerPulse 使用泥浆脉冲上传，文章给出最高 10 bit/s，并介绍通过泵流量变化下发控制。 | 是油气钻井特定系统，不是煤矿有线通信；更不能证明统一 300 bps。经验：先注明介质、井深、上下行及年代，再谈带宽。原 PDF 本轮直开超时，数值由官方搜索索引读回，正文需归档复核。 |
| [NOV IntelliServ 产品页](https://www.nov.com/products/intelliserv-wired-drill-pipe)，2026-10-13 | 厂商说明有线钻杆最高 57,600 bit/s，服务于井下数据和钻井自动化。 | 厂商标称不是独立测量，也不是煤矿系统规格。经验：同属钻井，链路差异就跨多个数量级，不能用“井下”概括带宽。数值来自官方索引，直开正文未完整呈现。 |
| [CCSDS 121.0-B-3](https://ccsds.org/Pubs/121x0b3.pdf)，2026-10-13；2020-08 标准 | 规定整数样本无损编码、单步预测、残差映射、按块选择 Rice 类编码选项、参考样本及无压缩选项；见 §3–5。 | 不保证固定压缩比，不自动等于“差分+RLE+字典”。经验：残差小才受益；块头、参考点和最坏情况回退必须入码流预算。 |
| [CCSDS 120.0-G-4](https://ccsds.org/Pubs/120x0g4.pdf)，2026-10-13；2021-11 技术报告 | §5.5–5.6 给出 FIFO、整数算术、位打包和块并行的 FPGA 实现路径，并引用真实 FPGA/IP 案例。 | 报告中的 Virtex-5QV 吞吐与利用率不能搬到 XC7Z020。经验：独立块、有限缓冲、编码顺序和可恢复参考点，适合形成可审计的流式原型。 |
| [NASA/GSFC fpack](https://heasarc.gsfc.nasa.gov/docs/software/fitsio/fpack/fpack.html)，2026-10-13；页末更新 2025-12-16 | 真实科学软件对整数 FITS 图像使用无损 Rice；说明压缩比依赖噪声，浮点量化可换取更高压缩率。 | 是图像与软件案例，不能证明传感流 8:1 或 FPGA 加速。经验：对真实噪声与异常段实测；先量化浮点再编码不等于对原浮点无损。 |
| [AMD Vitis 压缩库](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vitis/vitis-libraries/vitis-data-compression.html)及[固定版本 2022.1 要求](https://xilinx.github.io/Vitis_Libraries/data_compression/2022.1/source/overview.html)，2026-10-13 | 官方库提供 HLS C++ 压缩模块/核；2022.1 要求明确针对 Alveo U200/U280，Apache 2.0。 | 不能把 Alveo L2/L3 overlay 当作 PYNQ-Z2 可直接运行包，也不能由开源推出资源必然够用。经验：选定版本后逐原语移植、综合与联调；字典 BRAM、并行度和接口是显式成本。 |
| [FORCE 官方仓库](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition)、[主办方数据说明](https://thinkonward.com/app/c/challenges/force-well-logs/overview)，2026-10-13 | 井日志岩性分类，12 类含砂岩、页岩、煤等；训练标签字段为 FORCE_2020_LITHOFACIES_LITHOLOGY，另有解释置信度；缺失曲线常见。 | 煤类别不等于煤矿场景；岩性、含水性、断层是不同标签。说明页列 98 训练井，旧 starter 写 83，发布包说明列总 118，不能混作同一划分。经验：锁定具体文件及井清单，按井验证，报告缺失值和类别分布。 |
| [FORCE 官方许可规则](https://thinkonward.com/app/c/challenges/force-well-logs/rules)与[作者 Zenodo 数据记录](https://zenodo.org/records/4351156)，2026-10-13 | 主办方明确解释标签 CC-BY-4.0、原日志 NLOD 2.0；要求注明 FORCE 数据来源及 Bormann 等作者。Zenodo DOI 为 10.5281/zenodo.4351156。 | 不能将代码许可替代数据许可，也不能凭开放数据推出任意派生标签的科学有效性。经验：打包保存出处、许可、预处理和引用；Zenodo 本轮全文直开超时，数据说明由官方索引及仓库 DOI 链接交叉定位。 |
| [Equinor Volve](https://www.equinor.com/energy/volve-data-sharing?source=post_page-----ef7dfed94077--------------------------------)与[权利人许可 PDF](https://www.equinor.com/content/dam/statoil/documents/what-we-do/Equinor-HRS-Terms-and-conditions-for-licence-to-data-Volve.pdf)，2026-10-13 | 真实北海油田公开资料约 40,000 文件，生产期 2008–2016；官方授权学习研究使用，具体许可约束应随文件保存。 | 不保证所需水层/断层标签已齐全；生产水量也不是井下含水层真值。经验：可作钻井报告、时间序列的第二阶段来源，先确定小数据切片。许可 PDF 直开受 content-type 限制，精确条款需下载归档复核。 |
| [TUL PYNQ-Z2 手册 v1.1](https://dpoauwgwqsy2x.cloudfront.net/Download/PYNQ_Z2_User_Manual_v1.1.pdf)及[AMD UG480 XADC](https://docs.amd.com/r/en-US/ug480_7Series_XADC/Analog-to-Digital-Converter)，2026-10-13；手册 2019-10-28 | XC7Z020、512 MB DDR3；§16–18 给 Pmod/Arduino/RPi 引脚，Pmod A 与 RPi 存在共享，Arduino A0–A5 有板载分压，接口输入 0–3.3 V。 | UG480 确认 XADC 原生 12 位，存为 16 位字不等于 16 位测量精度；接口不是电机功率驱动。经验：真正 16 位采样需外部 ADC；核对电平、共享脚、外部驱动与传感标定。 |
| [AMD PG021 Applications](https://docs.amd.com/r/en-US/pg021_axi_dma/Applications)与[UG585 UART](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/UART-Controller)，2026-10-13 | AXI DMA 提供内存与 AXI4-Stream 间传输；Zynq PS UART 为已定义外设。 | 文档功能不证明当前 overlay 的 DMA 正常，不证明 300 bps 信道质量。经验：DMA 接口需验证 TLAST/长度/背压；UART baud、有效载荷与应用限速分别计量。 |
| [MathWorks/Speedgoat PMSM 实验白皮书](https://www.speedgoat.com/Portals/0/speedgoat_whitepaper_motor-control_doc.pdf)，2026-10-13 | 真实电机、轴上编码器、CPU+Artix-7 系统；FPGA 生成 PWM，论文给实验台及实测位置/速度图。 | 不等于 PYNQ-Z2 钻进或 NPU 控制已完成。经验：“显示角度”不足以证明闭环，必须回读实际位置，比较指令与响应，并区分快本地环和慢上位机环。 |

## 300 bps 的算术约束

假设每通道每秒采 100 点，4 通道，每点打包 16 bit，未计时间戳和协议：原始速率 `4×100×16=6400 bit/s=800 B/s`。这里是编码字宽假设，不能替代 ADC 精度证明。

| 条件 | 输出/传输结果（理想净荷） |
|---|---|
| 无压缩 | 6400 bps；1 秒数据在 300 bps 上传需 21.33 秒 |
| 4:1 | 1600 bps；需 5.33 秒 |
| 8:1 | 800 bps；需 2.67 秒；连续流每秒积压 500 bit |
| 300 bps 连续全量传输 | 至少 21.33:1；尚未计帧头、CRC、重传、参考样本 |

若 300 是 UART 的 baud 且使用 8N1，理想字节净荷只有 240 bps，此时所需比至少 26.67:1。若它是应用净荷限速，则不再扣这部分串行开销。8:1 下理想每通道上传采样率上限为 `300×8/(4×16)=37.5 Hz`。上述只是算术，不是对采样率的选型决定。

候选替代是本地保留原始流，低速发送降采样或窗口特征；必须写明传输对象和信息损失。例：每秒发四个 16 位特征与 16 字节总开销，需 192 bps；若通过 8N1 UART 则线路需 240 bps。这只证明预算可列出，不证明特征足以识别地层。32 字节完整报文在 300 bps 净荷上单程串行化需 0.853 秒，不能承诺毫秒级远程闭环。

## 可验证的桌面代理任务与风险证据

候选代理是低能量、非切削的导向指示台：压力/电流/位置等物理信号进入 FPGA，压缩与限速上传，上位机分析后下发慢速方向目标，舵机移动指针或无刃杆；独立位置回读进入 FPGA。记录采样、接收、推理、命令、实际动作时间及同一序号，演示扰动、失联保持/停止与限位。这能检验真实信号到真实动作的闭环，不能称煤岩钻进、断层避让或防突实验。FORCE 回放应明确标为公开日志岩性任务，不能把回放曲线冒充当前传感器的地质真值。

待主模型审定的证据缺口：

- **压缩承诺**：需真实 ADC 噪声、静态/斜坡/跳变/随机段的原始字节与码流字节；回解逐位一致；分别统计包开销、膨胀块与队列上界。RLE 对无重复样本可膨胀，字典需重置与丢包恢复机制。
- **推理承诺**：本次来源未证明 Ryzen AI NPU 支持 Rice/RLE/字典解码；“NPU 解压”仍是未验证假设。需单独取得实际设备、算子支持、执行提供者及运行证据；CPU 解码与 NPU 分类分别报告。
- **地质承诺**：FORCE 提供岩性解释及置信度，没有直接赋予断层、含水层真值；地层界面预测也不等于超前探测。水层任务需另取有许可、定义清楚的标注来源。
- **物理承诺**：参考资料提供接口与他人实验，不提供本板供电、电平、ADC、驱动、反馈和延迟测量。可视动画被 FPGA 信号驱动只证明显示链路；实际导向需独立角度/位置证据。

本轮只保存研究稿，没有下载大型数据或更改服务；全部指标均为外部资料、明确假设下的计算或待验证候选，不构成获奖、工业部署或本机验收声明。

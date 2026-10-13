# AMD 具身智能赛道：原件核实与 AI PC 候选

任务 `COMP-20261013-DEEPEYE` v1；A 本地资料研究；检索跨越北京时间 2026-10-13 至 2026-10-14。本文提供规则与采购候选证据，最终方案、采购和验收由质量主会话决定。

## 原件与日期

已从[赛事官方下载中心](http://www.fpgachina.cn/?page=download)的公开列表取得 AMD 指南（文件 id 25）和第一轮通知（id 18），不是仅依据 GitHub 镜像。HTTPS 入口本轮出现证书名称不匹配/超时，HTTP 页面可读；依页面公开请求流程只读获取列表，未登录或改变凭据。OSS 返回临时签名下载地址，长期引用应回到下载中心重新取得地址。

| 原件 | 本轮核对结果 |
|---|---|
| 2026 FPGA 选题指南 AMD | 28 页；上传 2026-08-31 22:26:33，更新 22:26:58；PDF 创建/修改 22:24:58，UTC+8；950,952 字节 |
| 第一轮赛事通知 | 7 页扫描件；列表更新 2026-08-27 16:57:59；779,290 字节；已查看第 2–5 页图像 |

AMD PDF SHA256：`c6ad82acd4f7bdcd13bd412e232ed85d05f2a87dd5e2cdd04f9d219f88b569fc`；MD5 `c108764280fb1fc74372fd23aad6d244` 与官方 OSS ETag 相同。通知 SHA256：`c17611b45a66121cd93f421e7fdee50f1743b1eb0cb5d9f930c57578d480ef9f`。整文件下载曾截断，后以 HTTP Range 拼接完整字节读取，完整长度与 ETag 核对通过；未将截断下载算作原件证据。

官方对象记录（以下去掉临时签名，不能保证匿名直开）：

- AMD：`https://fpgaceshi.oss-cn-shanghai.aliyuncs.com/profoss/upload/2026/08/31/8c7a809f-f0b8-42e4-996a-3a5f2f132288.pdf`
- 通知：`https://fpgaceshi.oss-cn-shanghai.aliyuncs.com/profoss/upload/2026/08/27/ff581b85-e214-4b8f-a044-3287f8825750.pdf`

通知第 5 页确认：报名截止 **9 月 22 日 24:00**；作品提交 **11 月 4 日 18:00**；决赛安排为 **11 月 20–22 日，南京江北新区**，具体安排另行通知。第 3 页写队员不超过 3 人、指导教师不超过 2 人；第 4 页写通过 FPGA 基础编程设计能力考核后才取得决赛评奖资格。报名资格是否已审核通过需从队伍自己的报名记录确认。

## 3.2 具身智能的实际门槛

以下页码为 PDF 文件页序（正文印刷页码一般减 3）。官方指南第 13–17 页要求 AMD Ryzen AI PC 与 AMD FPGA/Zynq 协作完成至少一项**真实物理任务**。PC 本地 AI 参与感知、理解、规划或决策；FPGA 必须有硬件逻辑或系统设计，如实时控制、安全状态机、传感同步或预处理。机械结构允许简化，但从 AI 判断到执行器动作的闭环必须完成。

PYNQ-Z2 是指南列举的可用平台，适合桌面原型。Python 调用接口不能替代 Overlay 或 Zynq PL/PS 设计；普通 USB、串口、GPIO 转接不满足要求。10G Ethernet、高清视觉、多传感器与技能包是鼓励/加分方向，不能改写为统一必选硬件。

PC 型号不限，须声明整机、处理器、内存及驱动；FPGA 板卡及器件也须声明。PC 软件栈要求 **ROCm 7.14.0 及以上**；真实硬件运行和实测输出必须具备，纯仿真不能满足交付。

| 官件评分（第 19–20 页） | 分值 | 应准备的证据 |
|---|---:|---|
| 物理系统完整度 | 20 | 成功率、干预次数、异常安全状态、端到端响应 |
| PC 本地 AI | 20 | 任务效果、单样本推理与总感知延迟、持续性能、离线能力 |
| FPGA 设计质量 | 25 | 实时控制/处理实测、P99 抖动、时序收敛、资源 |
| 两端协同 | 20 | 协议、数据流、同步、通信延迟/吞吐/错误与超时处理 |
| 工程与创新 | 15 | 稳定性、部署复现、场景价值、复用结果 |

同一数据只能在一项中计分。官件不设统一绝对性能门槛，但每项技术评分至少有一项可复测数据；须覆盖五类核心指标，并增加至少两项场景专项指标。端到端延迟须定义采集到实际物理响应的端点，报告 P50/P95/P99/最大值；AI 测试原则上 batch=1，分预处理、推理、后处理；对比须同条件，持续吞吐不能用瞬时峰值代替。保留原始日志、测试脚本及波形/仪器证据，并记录模型精度、输入规格、版本、FPGA 时钟、功耗模式、次数与时长。

工程包需包含 RTL/HLS 或 BD/Overlay、可复现构建脚本、bit/xsa/hwh、综合实现报告（WNS 与 LUT/FF/BRAM/DSP）、主机代码/模型来源、部署依赖及接线供电说明。目录文件名须英文，正文可中文。技能包加分需要干净部署或跨设备/场景复用证据。

**日期与版本边界：**官件第 20 页 3.2.6 和第 26 页 4.2 均写 AI PC 申请 10 月 9 日、结果/发放 10 月 13 日、10 个项目；本轮也读到第 16 页 3.2.3.2 的结果与发放为 10 月 13 日。[TOMBOSS 镜像](https://github.com/TOMBOSS885/fpga/blob/main/fpgachina26-amd/TRACK_GUIDE_2026.md)的同节出现 9 月 2/24 日，与其后文及官件不一致，不据此安排借机。[Qian-Sai](https://github.com/nbstarhkc/Qian-Sai)自称非官方，版本索引称 8 月 31 日；未完成其 PDF 与官件整文件一致性比对。下载中心本轮 25 条中未见 2026 AMD 独立评分细则；指南末页明确后续细则优先，不能声称已取得最新版细则或借机批准。

## AMD 软件支持：GPU 与 NPU 分开

[AMD 当前迁移指南](https://rocm.docs.amd.com/en/latest/about/transition-guide-TheRock.html)明确：7.14.0 是 TheRock 首个生产版，当前生产版为 **10.1.0**。因此 7.14 要求有真实版本依据，旧 Radeon/Ryzen 7.2.1 页面不能作为满足赛题版本的证明。

| 路径 | 本轮官方依据与配置边界 |
|---|---|
| ROCm GPU | [10.1.0 矩阵](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html)列 Ryzen AI 300/Max 300；HX370 为 gfx1150，Max+395 为 gfx1151。表列 Ubuntu 26.04.1（GA 7.0）或 24.04.5（HWE 7.0），Windows 11 25H2；Adrenalin 26.10.41.05、Windows CDE CPR 26.10.48。部署前用具体 SKU 选择器核对 |
| Ryzen AI NPU | [1.8.0 发布说明](https://ryzenai.docs.amd.com/en/latest/relnotes.html)支持 Strix/Strix Halo，即两候选所属系列；INT8/BF16 CNN、BF16 NLP、OGA LLM 有模型限制 |
| Windows NPU | [安装页](https://ryzenai.docs.amd.com/en/latest/inst.html)，2026-10-07 更新：Windows 11 build≥22621.3527、VS2022、cmake≥3.26，驱动≥32.0.203.280，.376 为所列平台生产驱动 |
| Linux NPU | [安装页](https://ryzenai.docs.amd.com/en/latest/linux.html)列 Python 3.12、Ryzen AI 1.8.0 和 Ubuntu 24.04 命名的 XRT 2.25.37/amdxdna 包；发布说明提醒此版 LLM 模型生成需 Windows，生成后可在 Linux 使用 |

上述是文档支持，不是本机已验证。ROCm 是 GPU 路径，NPU 用 Ryzen AI 软件与相应执行后端；NPU TOPS 不能换算成 VLM 延迟。只用 NPU/DirectML 能否同时满足赛题的 ROCm 使用口径，需最新版细则确认。不要把“安装了 ROCm”当成模型实际使用 AMD GPU 的证据。

## PC 候选与采购条件

研究层面主推 **Ryzen AI Max+395、64GB 起步**作为 GPU 模型试验候选，预算充足且有模型/并发内存需求再选 128GB；理由是 8060S 的 40 CU 与更大整机内存选择，而不是已测得固定速度。低成本替代为 **HX370、32GB**，条件是本地报价更低、能尽快交付，并把任务限定到已验证可容纳的小模型/单路感知。两者都应先跑真实模型的 batch=1 延迟与离线闭环，内存容量建议不是性能保证。

| 候选整机 | 厂商证据 | 适用条件与可获得性限制 |
|---|---|---|
| [GMKtec EVO-X2](https://www.gmktec.com/products/amd-ryzen%E2%84%A2-ai-max-395-evo-x2-ai-mini-pc) | Max+395、8060S 40 CU、64/128GB 焊接内存、2.5GbE；官方页面标 In Stock，有下单入口 | 优先候选；查具体 SKU 的内存、BIOS、地区保修和到货日期。官网售卖状态不证明国内现货 |
| [Beelink SER9 Pro](https://www.bee-link.com/products/beelink-ser9-ai-9-hx-370) | HX370、890M 16 CU、32GB 焊接内存、Windows11 Pro；可加入购物车；厂商写其他地区从 CN 仓发货 | 轻量替代；内存不能靠后续加条升级。到货/模型延迟需实核 |
| [ASUS Zenbook S16 UM5606](https://www.asus.com/laptops/for-home/zenbook/asus-zenbook-s-16-um5606/techspec/) | 官方规格含 HX370，亦含其他处理器配置 | 已有或需移动演示时考虑；必须核对型号尾缀，不把系列名等同 HX370 |
| [HP Z2 Mini G1a](https://www.hp.com/us-en/workstations/z2-mini-a.html) | Max+ **PRO**395、最高128GB，可分配最高96GB给GPU | 工作站与售后替代；PRO SKU与非PRO不同，价格/本地库存未查明 |

不采用商家“比某显卡快若干倍”的宣传作为竞赛实测。当前没有中国含税报价、借机结果和承诺到货证据，因此不编人民币预算，不以海外网页价格决定采购。建议主会话立即确认预算、借机资格和可交付库存，再在“11 月 4 日 18:00”前留出环境重建与实物测试时间。

## 本轮证据范围

规则：官方列表、AMD 原 PDF 字节/哈希及文本、原通知扫描图像。软件与整机：以上 AMD/厂商页面于本轮实时读取。未操作板卡、安装软件、采购、发群消息或读取 B/C 方案；没有运行模型性能测试，没有将资料核实写成最终架构或正式验收。

# 三机最终融合评析与来源

规范合同 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804；逐模块取长补短，不用总分抵消硬要求。原始五案与两轮选择详见taskbook_final.md第3节、selection_audit.md及round1/round2原件。

- A实际原件：[74c854d74baf](https://github.com/carolwjade/CarlandFPGA/tree/74c854d74baf817beafcbd1d4d52a8dd4450bbca)，taskbook_v4.md，86841B，SHA256 1b71bb268c140c6cab526c239f5bba28f702668e4c9d8c4e561ef03c39aceb30。
- B-initial实际原件：[1f85095b1f54](https://github.com/carolwjade/CarlandFPGA/pull/20)，reviews/v5/b/review.md，6783B，SHA256 d973d3371e851ac7a9b1955d2978ea19bd216b1c59c52edaf2475082eb41063d。
- C-initial实际原件：[68423d6c40cf](https://github.com/carolwjade/CarlandFPGA/pull/19)，v5/c/review.md，15421B，SHA256 780d94bf19a1921f19c9d317b409762d23d13a9f4a5b4ecca4715cb65e6aa56b。
- B-final实际原件：[a5fd908656f5](https://github.com/carolwjade/CarlandFPGA/pull/23)，round3/b/fusion_review.md，5323B，SHA256 1d17710e3f16b34183a93523ef48b034fc52f64d827003d045da8c5f6241a401。
- C-addendum实际原件：[5a9682f3c1d4](https://github.com/carolwjade/CarlandFPGA/pull/21)，round3/c/scope_and_peer_addendum.md，5573B，SHA256 99935688559baa31bc36ad74285f49b91cb1c260caa9c82e95ad7bcaf0ae579f。

B PR20首版明确尚未读A候选，原件保留该事实；其后B桌面和B正式PR23均实际核对A精确候选，PR23的P0+五项P1全文已读。吸收latest-completed邮箱/四项历史观察、共同sample-age截止、线上短帧与本地原始捕获计数边界、+Z符号/四元数、源到判定与剩余延迟分账、双模式各90试次。C PR19已核A候选并给10子门，PR21复用同字节核心，新增合同/两机取舍和实际pivot包络警示；原文件均保留，新增补充已实际读核。B/C相互评析后的修正由A逐项吸收，最终同件读回另存交接记录。

采用：完整游戏品质、独立凸体与旋转扫掠、编辑glTF/许可；体坐标双轴/四元数；单源模式和真实捕获；0.001°/s及加减速曲率耦合；源/在线检测与真实时标；独立3D正演和多解地图；短前缀+制动尾段；解析双圈/36面对照；实际权限拒绝和真实AMD并发。

未选B的64点ToF/新高带宽ABI/2m几何为共同主线，它们有独立预算和工程价值，但传感意义、字节和几何与当前共同案不同。保留四通道EM/振动、真实DAC/XADC/PL/RS485、9600现场与300压力。分机渲染只作附加部署，不替代正式AMD主站并发。引擎采用B建议Godot4.7.2稳定版，C4.6.3建议为可行未选备选。

C十卡作为根卡内补充验收规范，pass/evidence/failure全部采用；若其候选单位、引擎、写者或覆盖组合与最终正文不同，以本书已明确修正为准：A/R03唯一冻结ABI、36对独立几何测试、30盲布局分母不改、root_cards不是反向依赖、C5-10启动核验不要求先完成产品A04。研究原件不回改。

评析、源哈希和数学复算通过不等于游戏、模型、RTL、ROCm或板卡通过；产品卡全部not_run。最终方案同件读回、实际发布和新主/工作会话启动分别记录在implementation_handoff.json。

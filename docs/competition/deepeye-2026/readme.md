# 矿脉深瞳参赛规划

当前实施规范：[taskbook_v4.md](taskbook_v4.md)；阅读版：[deepeye_taskbook_v4.pdf](deepeye_taskbook_v4.pdf)。29卡DAG：[execution_plan_v4.json](execution_plan_v4.json)；三维参数：[simulation_contract_v4.json](simulation_contract_v4.json)；来源：[research_v4.md](research_v4.md)；变更：[revision_v4.md](revision_v4.md)。

v4落实人类10月14日新增的游戏级3D要求：边框立方体、实体钻头/五类障碍、编辑/镜头、任意六面蓝红圈、隐图传感与三维规划。PC AI为主感知/规划端，HIL经FPGA执行为主，PC_DIRECT为完整对照，板端规则提供快速保护。9600baud交互演示与300baud压力工况分别验收，3D不得退2D。

本批是已完成研究与可验收任务书，不表示游戏、RTL、模型、ROCm或实物任务已实施。R01赛事/实际物理任务认定、R02/C03现有PC的ROCm项目运行继续独立设门；动画不能替代真实PGA任务。A唯一物理板卡操作者。

v1/v2/v3修订1保留原始历史与清单；真实三机首轮各五案和第二轮模块融合见selection_audit.md。本次增补为A统筹，未捏造新的B/C共同签署。产品路径在competition/deepeye/，不混入协作平台。

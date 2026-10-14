# 自动化实施入口

任务COMP-20261013-DEEPEYE/v4，owner A。唯一规范是taskbook_v4.md；execution_plan_v4.json给29卡DAG，simulation_contract_v4.json为第7/8节结构化参数。v3历史不覆盖新版本。

R01/R02/R03/G01从各自准备开始。B01/C01与原采样/编码/物理PGA卡继续；三维子线G01→G02、R03→G03、G03+C02→G04、B05/B06→G05、G03+A01+B02→G09，然后G06合流，A02/G07盲测/性能和G08发布。A唯一实板和AMD主站操作者，B/C各自单一writer提交。完整依赖以JSON为准。

所有产品命令入口尚待所列任务创建，当前均not_run。plan/status/verify只读；run/resume核task_version=4、work_id、租约、归属和原操作。失败保留，不重放未知副作用；等待由原常驻程序完成，不模型轮询。

ROCm与真实物理任务门保留；NPU可选，游戏级完整3D/编辑/体积碰撞/真值隔离为标准必交，不能退2D。PC直控与经板输出按模式分别取合法证据，不能越过真实板端观测。FAST9600现场与STRESS300性能分别报告。

此文件不启动服务、不启用硬件队列、不安装驱动/引擎、不购买、不授予账号/正式比赛提交权限。实际实施须有对应任务原始日志及精确commit/哈希；文档校核不是产品验收。

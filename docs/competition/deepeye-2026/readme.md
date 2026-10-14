# 矿脉深瞳最终任务书

入口：taskbook_final.md与deepeye_taskbook_final.pdf（版本5）；最高约束immutable_scope.md/json H01-H15，SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804。

执行：execution_plan_final.json，29根卡全部初始not_run；simulation_contract_final.json；execution_orchestration_v5.md。补充C10子门见v5/c/acceptance.json及最终融合修正，不新增自环依赖。源码根competition/deepeye/，设计根本目录。

证据：fusion_review_final.md/json保存三机精确来源及取舍；checks_final.json和verification_final.txt只证明文档/算术/DAG/PDF；release_manifest_final.json锁文件；implementation_handoff.json记录之后的真实发布、同件读回与新主/工作启动。v1–v4保留历史，不能用旧结果通过新卡。

校验：python verify_immutable_scope.py --expected-sha c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 --book taskbook_final.md --plan execution_plan_final.json；python verify_taskbook_final.py。游戏、RTL、AMD和板测须按任务书在新主会话另做。

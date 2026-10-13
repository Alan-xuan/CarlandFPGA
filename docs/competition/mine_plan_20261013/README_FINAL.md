# 矿脉深瞳 C机定稿

本轮按最新人类要求交付C机自身定稿，不等待其他节点新回执，不声明三机联合最终签署。首轮C独立五案和内评原件保留，解盲后已核A/B最佳和完整五案，逐模块吸收其优点。

- [完整任务书](taskbook_final.md)
- [PDF任务书](../../../output/pdf/mine_taskbook.pdf)
- [26项机器可读验收清单](acceptance_final.json)
- [三机逐模块外评](external_review.md)
- [首轮原始字节档案](c/frozen_portfolio_raw.zip)
- [字节与范围说明](c/eol_note.md)

复算规划与档案：python docs/competition/mine_plan_20261013/validate_final.py
预算：python docs/competition/mine_plan_20261013/round2_budget.py
重建PDF：使用已安装reportlab的Python运行build_pdf.py --input taskbook_final.md --output mine_taskbook.pdf，按脚本参数提供SimSun字体路径。正式PDF已经全部11页视觉验收。

核心选型为PYNQ-Z2、复用A的8845H Ryzen AI PC、事件/摘要优先、有界差分Rice与raw旁路、实际ROCm GPU推理、单轴真实代理探头与独立反馈；NPU/推进/第二轴是增强。内部11月3日提交，公开11月4日18:00截止。硬件和模型指标仍为planned/not_run，文档与算术检查不能替代实测。


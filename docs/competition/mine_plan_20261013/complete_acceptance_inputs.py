"""Complete explicit inputs and reviewer/evidence defaults for planned gates."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
inputs={"G0.1":"本机真实库存、PC/板卡/工具发现输出","G0.2":"人类要求、三机全部候选、内评、最佳封存文件与SHA-256","G0.3":"G0.1库存与G0.2统一方案、物理成功/失败定义草案","G1.1":"授权原始数据包、许可、单位和井号/场次元数据","G1.2":"已冻结接口草案、数据量程、E集合和边界激励","G1.3":"G1.2黄金模型、板卡原理图与时钟/复位清单","G1.4":"G1.1至G1.3产物、证据schema与正负验收样例","G2.1":"G1契约/黄金模型/激励、最小RTL源码","G2.2":"G2.1源码SHA、XDC、器件/板卡版本与构建脚本","G2.3":"G2.2同次bit/hwh和manifest、A批准的接线与板测步骤","G3.1":"已冻结E/码流规则、黄金向量与编码RTL","G3.2":"通过的编码器、仲裁协议、UART时钟/波特率配置、仪器","G3.3":"G3.2稳定链路、故障注入种子、状态机恢复契约","G4.1":"冻结训练/验证/盲测分组、因果窗口及基线定义","G4.2":"G4.1模型/ONNX/量化hash、实际PC/驱动/SDK及校准集","G4.3":"通过的固定模式、允许模式表、版本事务和相同线预算","G5.1":"已验收硬件/应用/模型、训练外布局与封存真值","G5.2":"G5.1冻结版本、故障矩阵、数字/采样/制动保护定义","G5.3":"真实trace、后端信息、测量日志与界面显示规范","G6.1":"冻结代码/设备/模型/线预算、30个盲测布局及种子","G6.2":"G6.1冻结条件、各对照配置、相同硬保护和计分定义","G6.3":"冻结系统、稳定性输入/断链工况、计数与功耗仪器","G7.1":"冻结工程、依赖lock、数据/模型/bit/hwh manifest与启动步骤","G7.2":"全部已测指标/原始日志、RTL贡献、失败记录与正式模板","G7.3":"G7.2提交材料、产物清单、秘密扫描规则及演示流程","G8.1":"G7冻结包/SHA-256、提交账号权限及最新报名后台通知"}
p=ROOT/"acceptance_matrix.json"
d=json.loads(p.read_text(encoding="utf-8"))
for s in d["steps"]:
    s["input"]=inputs[s["id"]]
    if not s["reviewer"]:
        s["reviewer"]={"G3.3":"B","G5.2":"C","G7.1":"A最终确认，B/C互核"}[s["id"]]
    if not s["evidence"]:
        s["evidence"]="metrics/logs/stability.csv、power.csv；缺仪器时功耗blocked日志及原因"
    assert s["status"]=="planned"
d["contract"]="Each step has concrete input, procedure, pass criteria, evidence and reviewer; no hardware pass is implied."
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
rows=["# 每步输入与复核补充","",
"下列输入是任务书第9节的明确执行契约。每步输出保存原始命令、版本、退出码、日志与SHA-256；验收矩阵所有步骤仍为planned。","",
"| 步骤 | 必须输入 | 复核 |","| --- | --- | --- |"]
for s in d["steps"]:
    rows.append("| "+s["id"]+" | "+s["input"]+" | "+s["reviewer"]+" |")
rows += ["","G6.3必须输出稳定性原始CSV和功耗CSV/缺仪器blocked证据；G3.3由B复核，G5.2由C复核，G7.1由A确认且B/C互核。",""]
(ROOT/"acceptance_contract.md").write_text("\n".join(rows),encoding="utf-8")
print(json.dumps({"steps":len(d["steps"]),"null_fields":0,"status":"planned"},ensure_ascii=False))


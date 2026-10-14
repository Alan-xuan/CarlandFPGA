# 终稿实施的三机主会话与并行工作会话

本文件服从immutable_scope.md/json全部H01-H15，固定规范SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804。技术/任务调整不授予AI删改人类硬要求的权力。最终实施只使用A发布的taskbook_final.md、execution_plan_final.json和精确Git commit；旧v1–v4材料保留但不作为新验收通过证据。

## 1 单一主会话与真实创建

实施任务标识为DEEPEYE-IMPLEMENTATION-20261014/version1。每机只建立一个该task_id的质量主会话，A统筹全项目；B/C主会话分别管理本机任务、模型、文件和结果，互相直接通信。旧方案会话只完成确认/发布/交接，之后不继续写产品或派工。实际thread_id、创建回执和主会话接管结果保存在implementation_handoff.json及各机只追加的执行账本，不能以“准备创建”冒充已开始。

新实施主用既有fpga_session_open(category=decision，根任务按quality_route)创建，复用同task_id即复用同一实际thread，不重复创建。现有工具事实：mesh新task会thread_start，生成真实Codex thread，Codex App可列出/读取；质量根会话使用当前允许的质量route。不要先用App create_thread再把同逻辑任务session_open一次，两者没有绑定API，会变成两个主会话。若已有同任务的真实App主聊天，则沿用并准确记录其独立身份，不伪造已绑定mesh；派工只用一个协调入口。

本机并行工作会话采用人类已明确授权的App create_thread独立聊天，由新主先list_projects选本机项目再创建；工作会话不是第二个项目总主。当前mesh gateway一次只派发一个主回合，不能把多个session_open队列称为实际并行。App工作会话与Flash子执行池可在独立工具通道推进，实际并发以启动/终态与作业记录证明，不靠会话数量。工作会话不再对自己的同逻辑根任务session_open造成双重入口；它使用明确的worker task_id管理Flash工作。

跨机调用只能由各节点自己的原控制器/账号执行。A不能拿本地App API伪造创建B/C的本地线程。B/C旧主会话在收到A精确最终commit/hash及启动指令后，各自调用本机原工具创建本机新主，并回A实际thread_id、节点、任务版本、合同校验、职责接受和已启动工作会话清单。无需等待三机所有卡完成才交接，至少要有真实新主和首批工作启动证据。

## 2 主与工作会话分工

以下是本机可并行的工作包；只有依赖已具备的工作才运行，缺依赖时可以准备独立向量/素材/合法数据，但不得提前标卡passed。每个工作包用独立task_id和稳定work_id，主会话分配精确文件列表及互斥ownership。

|节点/会话角色|首批任务与文件归属|依赖及边界|
|---|---|---|
|A实施主|R01/R02的关键核对、R03接口冻结和质量决策、唯一实板/AMD主站、跨机整合与最终签收|板资源覆盖准备/上传/运行/采证/清理；不授权其他会话自行连板|
|A工作会话ui|G02，simulator/ui、viewer、editor及其独立测试|G01资产未到时按冻结资源接口开发，完整验收仍依赖G01；不改B资产/C模型|
|A工作会话sensing|G03/G09，simulation/authority、sensors、bridge和tests/simulation|真值仅authority持有，控制器白名单；板端激励试验提交A主排队，不自行占板|
|A工作会话pipeline|R03公共编排/接口工具实现与后续A02/A03/G07/G08集成脚本|R03技术决策由A主冻结；只写A主分配的tools/integration子文件，先基础检查后真实测量|
|B实施主|B卡/G01/G05协调、代码审查、Vivado构建资源及提交A|一个Vivado大构建同时运行；不直连共享板|
|B工作会话codec|B01/B03，fpga/codec、stream、golden/codec和各自RTL测试|R03冻结ABI/样本契约后验收；保留RAW/有限unary/误差证明|
|B工作会话control|B02/B04/B05/G05，采集/链路/双轴与捕获逻辑及测试|严格按最终profile计费和时效；与codec共享top只由B主集成|
|B工作会话assets|G01，simulator/world、assets和资产契约测试|可首先启动；必须游戏级实体视觉/完整碰撞，不用二维替交|
|C实施主|C01–C05/G04/G06本机协调、数据与模型关键决策、提交A|不能读truth或把C的CPU/NVIDIA结果当A的AMD执行结果|
|C工作会话data-model|C01/C02/C03的准备，data/和ai_pc/model及训练/独立测试|按井/完整场景分组；sim_em与FORCE/物理量程分profile；A主执行正式AMD实测|
|C工作会话planner|G04，ai_pc/mapping、planning及独立小图测试|只用合法观测/里程计/门信息，受完整体积/曲率约束；不调用真图oracle|
|C工作会话broker|C04/C05/G06，ai_pc/policy、control_broker和协议客户端测试|HIL和PC_DIRECT分别取合法证据，旧ACK不续期，不能改范围/公共ABI|

目录均相对competition/deepeye/。表为工作域，派工前要展开为精确文件路径；共享project.godot、锁文件、top、公共schema由各指定主集成，禁止多个会话同时写。每次进入板测还须A主发唯一operation_id/request_hash，绑定实际commit与bit/hwh，不重放未知副作用。

## 3 节省usage与并发约束

质量主会话负责架构取舍、难点定位、验收和对外结论，按当前实际quality_route最高允许深度运行。工作会话承担有边界的组织/整合，普通代码/测试/文档执行优先委派DeepSeek Flash/max；原生GPT子代理只有具体工具/原生上下文能力理由才reserve/validate/complete。配置名、租约与真实provider/model/effort分别记录。

每个原生App工作会话同样遵守有效租约与边界：主先reserve，首次创建prompt只允许等待真实thread_id绑定；创建ready后主以实际thread_id绑定validate并向该线程发送启动/自校验信息，只有execution_allowed=true才执行。原生worker主要持有自己的上下文记录/视觉取证路径，普通源码文件由其Flash子作业各自独占，不能让父原生租约与子源码ownership重叠。原生worker不得直接写未登记路径或接任最终验收。创建时不擅改用户默认模型；普通编排可用受支持的低推理档，关键决定一律回质量主；实际使用何种模型/effort留真实记录。

初始每机最多3个工作会话，但一次只启动确实有独立输入/文件归属的2至3个；每会话不预热无限子代理，默认一个Flash执行，有明确收益才扩展。每机Flash并发初始最多2，后续按CPU/RAM/任务证据调整；Vivado构建每机最多1；GPU训练与正式计量按A主预约，G07的游戏/ROCm并发是有意测试条件。无可执行依赖时写准确状态，结束有效模型回合，由既有普通常驻程序/回调唤醒，不模型轮询和重复READY。

新工作会话通过不同task_id创建，不冒充独立机器；本机多聊天/子代理的成果不能计作三机独立意见。被否决/失败/中断的工作和测量保留；任务版本或输入hash变化后重验受影响卡，不复用旧pass标签。

## 4 从头推进与首批可见产出

从头指产品卡R01/R02/R03/G01及后继依赖重新落实；复用本轮可信研究/材料和已有协作程序，不能把旧BRAM或文档检查当产品实现，也不要求重复五案研究。所有产品卡初始not_run。

第一批：A主核规则/资源并冻结最小ABI；B资产工作会话先交可启动三维灰盒/钻头和五类实体；C数据工作会话锁合法输入/分组、规划工作会话先做独立已知小图和运动学向量；A UI与传感会话分别搭可操作界面/真值隔离模型。资源接口未冻结前先写独立材料与测试，禁止两边各自改公共协议。

下一批：板采集/编码/调度/保护与PC模型/规划按DAG并行；A串行模块板测；G06合流后做A02/G07盲测和现场并发性能，A05真实PGA任务单验。G08/A04整包与复现。不把打开游戏窗口、得到模型输出或传输ACK当正式任务完成。

## 5 权限和交接完成条件

本轮人类已授权新会话启动三机产品实施、各主开多个会话与子代理。此授权不等于付款、改账号/云权限、启用自动硬件队列或代为正式比赛提交。需要真实接线/本人管理员认证/购买的步骤，先备齐具体可审阅方案，再集中报必要人类动作；其它独立卡继续。

方案聊天只有在以下实际证据齐全后才能声称交接全部完成：固定终版及合同已发布GitHub；飞书群实际显示精确终版链接/文件并读回；A/B/C新主均真实创建并接管；首批并行工作归属与启动记录可查。各机接管回执必须含合同hash、最终commit、节点、主thread、worker task/thread、work_id/ownership和下一卡。只说queued不能称已开始实施；存在真实阻塞时保留未完成状态，不谎称三机接管完成。

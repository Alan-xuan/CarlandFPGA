# 矿脉深瞳 FPGA参赛项目任务书

基于Ryzen AI与PYNQ Z2的低带宽随钻感知及数字孪生闭环

任务COMP-20261013-DEEPEYE，版本2，统筹A。计划期2026年10月14日至11月4日；11月4日12时冻结交付包，18时为官方提交截止。

## 1 最终目标与作品范围

本项目参加2026全国大学生嵌入式芯片与系统设计竞赛FPGA创新设计赛道AMD自主选题方向3.3。采用真实传感输入、PYNQ-Z2自研数据处理和通信逻辑、AMD本地AI与PC数字孪生，实现“采集→压缩与选择→受限上传→判断→参数回写→FPGA实际确认→孪生推进”的可验证闭环。工程目标是通过同条件对比、真实板级证据、清楚的演示和可复现交付争取奖项。

本届不配置真实电机、舵机或钻头执行机构。虚拟钻头在PC软件中运动，运动必须使用FPGA返回的已应用控制状态，不能直接用PC刚生成的期望指令。传感器实采、公开井日志回放、数字场景真值和FPGA实板结果各自标记来源。校内传感器和软件模拟含水区不构成煤矿含水层识别、现场超前探测或矿用安全认证证据。

最终融合采用“事件优先多速率遥测、独立可逆块与RAW退化、本地完整档案、受限AI参数决策、FPGA确认驱动数字孪生”。基础层保证正确与可交付；标准层增加真实NPU、误差受限档位和完整消融；强化层按预算余量加入渐进细节和更复杂场景。学习式编码器、复杂字典、压缩感知及强化学习不进入本届关键路径。

现有三机协作程序提供开发和交接能力，参赛产品单独放competition/deepeye/。已有协作平台或旧BRAM验收不能替代本产品新Overlay的验证。

## 2 官方规则与人类约束

官方AMD指南共28页，原始SHA256为c6ad82acd4f7bdcd13bd412e232ed85d05f2a87dd5e2cdd04f9d219f88b569fc；第一轮通知7页，SHA256为c17611b45a66121cd93f421e7fdee50f1743b1eb0cb5d9f930c57578d480ef9f。A从官方列表取得原件依据，再独立获取同字节文件核对。源文件和provenance.json保存在本研究目录sources/，正式引用入口为[赛事官方下载中心](http://www.fpgachina.cn/?page=download)。

AMD指南文件页22至25的3.3节适用于本项目：PYNQ-Z2在允许器件范围内；工具推荐Vivado/Vitis2026.1或2025.2，其他版本须说明并保证复现；必须上板提供实测输出、完整源码、构建脚本及综合实现报告；提交大模型交互与自纠错记录，并提炼可复用Skill。通用PYNQ Skill有单独加分价值。推荐GitHub或Gitee开源及可再分发许可证。目录文件名使用小写英文、数字、下划线或连字符。

3.3初级组与高级组按队伍最高学历分组，评价项相同、分别排名。人类已确认报名和资格审查完成，R01归档既有报名组别和材料，研发不重新办理或替人类改报名。基础编程能力考核仍按赛事流程保存结果。后续组委会正式变更优先于本版指南。

|3.3官方评价项|权重|本作品的对应证据|
|---|---:|---|
|创新性与应用价值|30|受限带宽下保留任务信息、AI策略与FPGA反馈的因果对比|
|性能与资源优化|20|同输入编码/线码/任务效果，时序、资源、持续吞吐和最坏退化|
|正确性与完整性|20|独立黄金、RTL、实现、真实传感、实板码流和孪生闭环|
|大模型协作与技能包|15|三机择优、自纠错、有效租约和可复用验证/部署流程|
|文档与可复现性|15|英文路径、依赖锁定、原始证据、冷启动复建和操作册|

ROCm指定版本及现实执行器不是3.3的硬门槛。Ryzen本地AI是本项目主题目标；NPU作为标准层特色验收，CPU基线始终保留。不得把3.2具身智能的评分权重或硬件要求套到3.3。

人类的工程约束为PYNQ-Z2、11月4日提交、传感器输入加数字孪生、物料由三机自主选择、适度预算、基础至强化分级、全工作链路尽量由agent执行。只在真实接线、无法代办的账号/管理员交互或正式提交等必须人类参与时集中报告。

## 3 两轮择优和最终取舍

三机第一轮各形成五套完整架构，在分享设计前分别封存。A本地两项研究子代理只负责官方规则和技术取证，均有reserve/validate/complete；它们归A，不计为B/C。原始候选中的赛道及实物假设保留为版本1历史，版本2按已核对的人类更新和3.3统一调整，不回改初轮原件。

|节点|五套完整候选|内部融合骨架|封存证据|
|---|---|---|---|
|A|无损预测、有界趋势、多分辨率、摘要事件、学习式编码|定长摘要事件加独立无损块及本地保护|16:23:34 UTC；best d9716026…11416；commit1412d6d70985848fff1332479c98a8be54f15e87|
|B|全曲线无损、双时间尺度事件、近无损、本地模型监督、学习式遥测|事件优先与独立无损块、命令时效及恢复状态机|16:12:22 UTC；best6088bb2d…439c8；PR13 head ec0675dfb2f1f86c6201b2d1e2ea27d3f5a04ff8|
|C|事件多速率、关键点渐进、任务驱动AI、无损档案、压缩感知|多速率事件、有界Rice、包络/年龄/缺失与置信门控|16:05:55 UTC；best5243500c…1889af；commitab527e20eb7bc8a0cdeab0409943ec17510830fe|

A封存前仅检查收件身份和消息类型，封存后才读取B设计摘要。A独立核验B的17项清单及六工况预算；C五案/最佳正文哈希匹配，预算JSON的Git LF与原CRLF有字节差异，换行定位和只读数值复算一致，分别记录。C采用不同内部权重，三机内部总分不能直接排名。第二轮按以下模块重新评析和融合，不简单取一个总分最高方案。

|模块|原方案的不足|融合采用的优点|最终处理及重验|
|---|---|---|---|
|实时观测|A摘要不足以完整重建；B全曲线遇噪声超额|C多速率与事件；A固定预算|核心定长状态，选择性独立样本块；原始全量留PS；线上缺段显式标记|
|编码|字典/学习式硬件成本高，固定压缩比无依据|B独立块/RAW；C闭环量化与Rice界|无损E=0为基础，E=1/2/4/8为标准档；各档独立黄金及任务损失测试|
|调度|单方向或平均预算漏ACK、换向、洪泛|A共享线速；C滑窗、短帧；B有限重传|双向统一记账，事件优先不饿死状态；容量/丢弃/年龄均回读|
|模型|NPU解码不合适；低维摘要和原曲线分布不同|C因果窗口、mask、分井；B真实落点日志|CPU解码，AMD NPU小CNN；按实际回传信息训练，传统基线和CPU同条件保留|
|控制|旧命令、重复包或PC崩溃使状态不一致|B会话/TTL/幂等；A边界生效|新会话、观察序号、TTL、影子配置；重复包不续期；断链保持停止，显式重新使能|
|孪生|按期望指令画动画可能绕开FPGA|C真值隔离和反例；B物理因果思路|改为FPGA实际确认驱动孪生；切断板通信或拒绝命令必须停止推进，不能主机旁路|
|资源|A/B初轮默认新PC，机械台架额外拖期|A实际设备盘点；人类无执行器约束|复用A的Ryzen8845H/32GB；传感和可编程输入夹具，去除机械执行器|
|交付|仅成功展示无法复现|三机原始证据、C盲场景、B恢复步骤|全链路流水线、故障矩阵、三级交付、通用PYNQ Skill和交互自纠错记录|

最终选择A内部A6的任务信息优先骨架，形成融合版F2；用B的独立块和可靠命令状态机替换薄弱模块，用C的多速率、误差/缺失/年龄语义及模型评估改进数据路径。移除不符合人类范围的现实执行器；保留真正FPGA采集、编码、仲裁、控制确认和状态反馈。获奖主张只使用后续真实测量结果。

## 4 硬件 软件和三级交付

A实际设备为MECHREVO Yilong15Pro，AMD Ryzen7 8845H、约32GB内存、Radeon780M、Windows11 Home build26200；NPU设备present/OK，驱动32.0.203.240。优先复用此机作为AMD主站。另有NVIDIA显卡可用于开发训练，但不能把其训练/推断成绩冒充AMD NPU效果。B/C各自设备数据加入环境清单，开发角色与主站实际执行设备分开。

本轮未见RyzenAI1.7.x/1.8.0安装目录，未跑项目模型。优先验证[AMD Ryzen AI1.7.1的PHX/HPT X1流程](https://ryzenai.docs.amd.com/en/1.7.1/inst.html)，固定形状INT8 CNN使用X1及对应phoenix xclbin；当前驱动低于所查SDK要求，R02准备OEM/AMD签名驱动升级及可审阅安装方案，再实测。版本与算子分配以实际成功运行后锁定；不因一个quicktest或NPU硬件存在宣称模型已在NPU运行。1.8的默认quicktest针对较新设备，不直接套到HPT。

FPGA使用xc7z020clg400-1；Vivado2026.1为主构建工具，PYNQ沿用实际兼容的3.1.1环境。PYNQ4.0移除Z2支持，不升级到该版本。bit/hwh同次构建。A唯一准备、加载和运行板卡，B/C提交脚本和哈希，通过A获取真实输出。

|层级|工时参考 机器工作日|必含内容|新增外设规划上限 不含已有PC和板卡|
|---|---|---|---|
|基础|7至10|真实传感/XADC、无损黄金与Overlay、真实限速、CPU模型基线、2D孪生、自动验证|800元|
|标准 参赛主交付|14至18|实际AMD NPU、受限参数反馈、3D孪生、场景盲测、失联恢复、完整消融及Skill|1500元|
|强化|18至21及后续|有界趋势/渐进细节、更多数据域、功耗测量与复用案例|2500元；增购PC须单独有理由与授权|

金额为设计支出上限，不是商家报价；脚本采购清单先核实际含税/到货条件再选同规格常见模块。增加人力和工时优先提高测量、鲁棒性和可复现性，不无限叠加功能。基础层也需完整FPGA实板证据；NPU未通过时如实说明层级，不取消整个研发。

|物料|选型和数量|用途与核对|
|---|---|---|
|PYNQ-Z2与MicroSD|现有1套|兼容镜像、512MB DDR、实际板卡修订和电源|
|模拟传感器|FSR402压力、3.3V电容式土壤湿度、TEMT6000光照各1；第4通道校准输入|XADC A0至A3，板卡允许0至3.3V的具体电路和接线先核；标明代理单位|
|自动输入夹具|MCP4728四路DAC或等价3.3V可编程源1套|给ADC产生可重放阶跃/斜坡/噪声，不是钻头执行器；实传感与DAC模式分别标记|
|串行链路|3.3V逻辑兼容RS485收发模块2块、PC USB-RS485适配器1|A核电平、方向和终端；实测300/1200/9600baud；无高速业务旁路|
|逻辑分析仪|现有优先，否则常见8通道USB款1|统一测串口位宽、换向、PL调试标记和反馈时刻|
|接线和固定|共地、限流保护、线材/底板1套|不直接接超过允许电平，ADC精度和容器位宽分别记录|

外设最初接线必须由能接触实物的人完成；之后校准、DAC激励、采集、回归、构建、加载、测量和报告均交agent脚本。需要管理员确认的驱动交互集中一次处理，不要求人类逐条执行普通命令。

## 5 数据与AI任务

三种模式必须分开。sensor_live记录实际压力/湿度/光照等代理信号及12bit XADC原码；geo_replay将有许可的GR、RHOB、NPHI、RDEP井曲线经PS/DMA送入实际PL，用于编码和岩性任务；twin_fixture通过独立场景生成器及DAC/数据入口产生模拟工况，评测数字矿井导向。界面和每条日志都带source_mode。

FORCE数据锁定具体文件、井列表、SHA和许可。按井划分训练/验证/测试；插补、缩放、对数变换、量化校准只拟合训练井。同一井或同一完整模拟运行的原始、压缩及增广版本不得跨集合；模型窗口只读当前及历史。真实传感器数据按采集批次/日期隔离。公开岩性标签不直接生成含水层或断层真值。

候选小CNN固定输入[1,8,128,1]，四通道值与四mask；Conv2D小核、ReLU、池化、Flatten/Gemm，先以实际X1编译通过的算子组合冻结，再训练。CPU规则/轻量树模型、浮点CNN、INT8 CPU和NPU分别对照。在线模型只读取真正经过受限链路的信息，禁止从调试以太网读取全量或未来曲线；必要时训练摘要模型与稀疏曲线模型两个明确profile，不能向原曲线模型悄悄灌不同分布。

摘要profile固定[1,13,32,1]，四均值、四极差、四valid mask和归一化age；曲线profile使用上述[1,8,128,1]。两profile分别训练/校准并绑定模型哈希，启动历史不足用mask标记。事件峰值经同通道特征适配器进入当前窗口，不生成未来样本。基础实时传感任务用摘要profile；公开岩性主指标用曲线profile，摘要岩性另报效果，不将两种分布混算。

主指标为公开岩性Macro-F1、每类Recall、压缩相对原始信息的损失；模拟风险另列事件Recall、误报及盲场景任务成功率。FORCE原始Macro-F1目标0.60，回传信息下降不超过0.03；模拟危险Recall目标90%、误报不超过每10分钟1次。未达标时先修数据/输入与任务，不删失败样本。NPU不保证比CPU更快；报告相同batch1条件的效果、时延、冷编译及1000次热推断。

## 6 采样 编码与低带宽守恒

基础采样为4通道100Hz、uint16容器，真实XADC有效12bit；公开日志量化16bit另标。每帧带来源/质量/序号和采样tick。4×100×16=6400bps是容器速率，实际12bit信息另列4800bps。8倍容器压缩仍800bps，超过300baud8N1的30byte/s，不能保证全量实时上传。PL/PS保存完整原值；低速曲线是明确选择后的在线信息。

核心编码采用独立锚点的差分ZigZag/Rice，k按块选择，unary有长度上限，不如RAW时整块旁路。E=0逐位无损；标准层闭环预测量化步长Δ=2E+1，编码器以自己的重建值更新预测，E取1/2/4/8。差分中间位宽至少17bit有符号，饱和/极端跳变均测。每块从绝对锚点开始，坏块不污染下一块。

E只保证已编码且完整收到的点。未发区间另显示包络、GAP和年龄，不用平滑插值冒充真实曲线。码率不足时降低趋势选择率、暂停历史细节、合并最新事件，同时保留原始历史及合并计数。FIFO仅吸收有限突发，PS环形区初始16MiB，容量与覆盖策略在运行日志中核算，不作为无限断连承诺。

## 7 统一接口与调度预算

协议abi_v1使用小端多字节字段。帧为magic2、version1、type1、payload_len1、config_epoch1、seq2、tick_ms4、payload、CRC2，固定开销14byte，payload最多32byte，最长普通帧46byte。magic线字节A5 5A，version=1。CRC16/CCITT-FALSE，poly0x1021、init0xFFFF、refin/refout=false、xorout0；覆盖version起至payload尾，结果小端存放。独立测试向量ASCII123456789的CRC为0x29B1。

|类型|总长上限|核心负载与语义|
|---|---:|---|
|TELEM 0x01|32B|4均值uint16、4极差uint16、quality_flags uint16，18B；采样模式/profile由epoch配置表确定|
|EVENT 0x02|20B|事件bitmap2、通道1、severity1、peak_value2；6B|
|CONTROL 0x03|28B|session_id4、cmd_id2、action1、yaw_rate_q2、speed_code1、ttl_ms2、observed_seq2；14B|
|ACK 0x04|24B|session_id4、cmd_id2、status1、applied_yaw_q2、applied_speed1；10B，实际应用值|
|CONFIG 0x05|24B|session_id4、profile1、E1、rate_code1、threshold2、apply_block_code1；10B|
|HELLO 0x06|18B|新session_id4；重连握手，epoch回绕前必须换会话|
|TRACE 0x07|46B|独立块/锚点/选择时间偏移和可逆样本；全部元数据在32B负载内计费|

yaw_rate_q按0.1度/秒定点，限定±15度/秒；speed_code0至20对应0至2mm/s模拟推进。CONTROL只允许hold、turn、advance、stop等有限动作；TTL上限12000ms，接收时依据当前会话、观察序号/数据年龄和范围判断。重复cmd_id重发同ACK，不再次应用、不刷新TTL；旧会话拒绝；新配置只在块边界生效，ACK后才承认生效。

300baud8N1半双工统一预算窗口8秒：TELEM32B每4秒共64B，EVENT20B最多一次，CONTROL28B最多一次，ACK24B一次，CONFIG及其ACK每16秒各24B折算共24B；平均160B/8s=200线bit/s，基础占用5.333秒，再给换向总0.2秒，约69.2%。余量覆盖有限重传和事件突发；TRACE只在余量内发送。连续事件洪泛先停止虚拟推进并保留本地历史，不无限排队。异常下可跳过低优先TELEM/TRACE，计数和GAP明确，不牺牲控制/状态语义。

CONFIG不是每窗半包：有配置的8秒窗实际184B、加guard占79.2%，无配置窗136B、占59.2%。配置与命令重传/额外事件不叠同窗，先延期CONFIG和TRACE；重传窗最多再计CONTROL28B和ACK24B，所有发出字节按实际计。初期TRACE不占硬保证预算，后续按实测余量开启。FPGA作总线调度主站，PC只在明确grant窗口发送，换向guard实测后锁定；若USB驱动延迟增加guard，重算预算而不沿用0.2秒。

46B帧内不可抢占会阻挡最多1.533秒，20B事件再占0.667秒；无错竞争条件的事件到达目标P99≤3秒，一次重传目标≤6秒；两者须上板实测。正常采样到FPGA确认再到孪生响应目标P99≤8秒/max≤12秒。不能把PL微秒处理延迟写成整个弱链路微秒响应。

AXI寄存器以构建HWH为地址依据：偏移0x00 ID，0x04 ABI版本，0x08 CTRL，0x0C STATUS，0x10影子配置，0x14生效请求，0x18采样档，0x1C E，0x20编码profile，0x24队列水位，0x28溢出/合并计数，0x30实际yaw，0x34实际speed，0x38已应用cmd_id，0x3C session摘要，0x40/0x44采样tick低/高。CTRL上电未使能，stop优先；clear_fault与enable分开。R03生成registers.csv与独立读写向量，未核真实HWH不试写旧地址。

## 8 数字孪生与因果验收

标准层采用本地WebGL或等价桌面3D界面，基础可用2D。显示钻头、分层/模拟禁入区、原始来源曲线、实际回传点/包络、AI置信、期望与已应用参数、线速/队列/age/GAP。模拟推进最大2mm/s，默认前视50mm，场景根据最坏延迟及误差重新核算；不能用未来几何真值替模型提前避障。

孪生积分器只消费从板卡实际返回、合法会话和序号匹配的applied状态。目标指令显示为pending，ACK丢失或数据老化时暂停推进。场景真值只供评估器和生成器，控制进程不可访问；只提供当前位置及历史应有观测。高级回放倍速必须显示倍率，正式指标用真实速率。

必跑反例包括拔掉板通信、暂停PC模型、改坏CRC、过期/重复命令、错误epoch及FPGA复位。原板反馈消失时孪生不能照着期望命令继续完成任务；虚拟场景安全停止不计为目标到达。实板采样/控制确认与软件物理模型分开报告，动画截图不能证明FPGA结果。

## 9 分工与文件归属

所有路径相对competition/deepeye/；每文件单一writer，公共接口由A维护，B/C提交PR建议。A是唯一板卡操作者，AMD主站实测也由A集成执行。

|节点|独占路径|职责|独立复核|
|---|---|---|---|
|A|docs/、hardware/、integration/、tools/pipeline/、evidence/system/|接口/资源、编排器、唯一实板、整合和终验|B审协议预算，C审模型输入及测量口径|
|B|fpga/、golden/codec/、tests/rtl/、evidence/rtl/；tools/verify_codec.py、run_rtl.py、verify_link.py、check_build.py|采样、编码、FIFO/复位、串口调度、配置/控制状态机、构建|C独立解码，A板上复测|
|C|ai_pc/、data/、twin/、tests/ai/、evidence/ai/；tools/verify_data.py、verify_policy.py|数据与模型、NPU适配、PC协议、孪生与盲测统计|B查字节互操作，A查实际设备/板反馈|

三机各自分支提交，源码commit、输入哈希和测试证据进入清单；A接受精确PR head后反馈，发送方读回。共享top/接口/状态机不并行改写。纯status不提交模型、不升级版本、不夺权。

其他tools检查脚本由A唯一维护，调用B/C模块；表中仅简写文件名的工具仍位于tools/。根目录README、依赖锁文件和公共任务清单由A维护。每个阶段运行前pipeline将上述ownership展开为精确文件列表后做冲突检查。

## 10 自动化执行契约

工具入口为python tools/pipeline.py。plan/status只读取阶段和证据；run --stage s1 --task-version 2 --work-id stable-id创建有界执行；verify重算证据；resume首先核对暂停、任务版本、租约和原操作回执。每次合法stage都完成“检查先决条件→预订唯一文件/板资源→执行固定命令→独立黄金比较→收集原始输出→质量主会话签收→更新ledger→启动已具备条件的后继”。等待由原常驻程序和外部进程回调承担，不使用模型轮询。

执行优先DeepSeek Flash/max；需要原生浏览、工具上下文或视觉能力时按reserve/validate/complete使用Native，reason具体、ownership不重叠。决策、疑难修复和验收由质量主会话最高可用深度完成。日志记录实际provider/model/effort，不用配置名替代完成回合证据。

pipeline的ledger.json每任务记录task/version/work_id、owner、输入/源码/配置哈希、状态、命令/退出码、证据、已验证提交与下一依赖。状态为not_run/running/passed/failed/blocked；失败保留，未知板副作用只查原operation，不自动重烧。恢复失败保持停止状态并报告一次真实阻塞。新版本只重跑受影响任务，不能改变旧测量分母或原错误。

板卡加载和采集使用现有A单机工具，完整绑定operation_id/request_hash/tested_commit和bit/hwh哈希，覆盖准备、加载、运行和清理。不因任务书加入自动化就打开hardware_enabled队列、建立第二常驻服务、改凭据或新增云scope。资料下载/解包先哈希和许可检查；模型和工具安装使用隔离依赖及签名来源。

自动化可直接完成资料清单、黄金/仿真、Tcl构建、上传与实测、DAC激励、训练/量化/部署、盲场景、图表、报告与打包。包准备并通过校核后，agent可在本人账号和工具可用、已有明确提交授权时完成上传并读回回执。人类最少参与是首次接线/上电确认、必须由账号本人完成的交互或考核、购买审批；这些是物理/账号事实依赖，不把普通命令逐步交回人类。

## 11 日程与分步自验收

|阶段|最迟完成日|核心产出|退出条件|
|---|---|---|---|
|S0|10月15日|3.3规则/资源、ABI、输入/模型/自动化任务登记|三机意见闭合；资源和许可清楚；无需现实执行器|
|S1|10月17日|黄金、协议、信道模型、采集输入、CPU/2D基线|基础路径和独立向量通过|
|S2|10月21日|采样/编码/调度/状态Overlay|仿真、实现及模块实板分别通过|
|S3|10月23日|因果模型、NPU、PC服务与孪生|数据隔离、实际落点和互操作通过|
|S4|10月26日|传感/回放与实际板反馈闭环|冻结盲场景和因果反例通过|
|S5|10月30日|消融、可靠性、资源和原始指标|核心目标通过，增强去留明确|
|S6|11月2日|工程包、报告、视频、海报、Skill|冷启动3次及独立环境复建通过|
|S7|11月4日12时|最终字节包与提交准备|最终版本重测；人类18时前提交并读回回执|

以下命令是由各任务必须创建并验证的入口契约，当前不是已实现脚本。全部从competition/deepeye/运行；成功输出structured.json和原始日志，失败非零退出，不删失败样本。

### R01 规则 数据与既有报名登记

A执行读取sources原件和人类已确认报名资料，登记3.3组别、模板/考核状态、许可证及对应产物。输出docs/rules.json、requirements_trace.csv；python tools/check_rules.py要求每条3.3约束有来源/页码和责任任务、无3.2错误门槛，路径合规。已有资格只归档，不代改。任何最新规则变化形成版本差异记录。

### R02 设备和采集夹具

A只读预检各机CPU/OS/NPU及现有板环境，复用8845H；核四通道电平、传感和DAC接线，记录实际ADC精度。输出hardware/bom.csv、wiring.pdf、calibration.json与environment.json。python tools/preflight.py不得启动模型/烧板；python integration/input_calibrate.py --levels 8要求每通道至少8点标定、越界与饱和可识别、模式和有效位数明示。NPU驱动/SDK另留安装清单和实际smoke证据，缺项不伪造通过。

### R03 协议 寄存器和编排器

A维护ABI和pipeline，B/C独立互操作。输出docs/interface.json、registers.csv、tests/vectors及tools/pipeline.py。python tools/check_interface.py核长度/CRC/端序/会话/预算；python tools/pipeline.py verify --selftest核status不发模型、重复work_id不重排、文件冲突拒绝、failed/unknown不重放。错误格式、有界长度、seq/epoch回绕全部有向量。

### B01 编码和独立回解

B编码，C独立解码，A签收；输入固定uint16向量及ABI。覆盖静态/斜坡/窄峰/极值/随机噪声、E=0/1/2/4/8、RAW、块重启和饱和。python tools/verify_codec.py --samples 1000000 --seed 20261014要求E=0逐位一致、已编码点误差违规0、unary长度有界、不可压缩块无死锁；原始、编码及全线字节分别统计。输出golden/codec和反例日志。

### C01 因果数据和模型输入

C锁定FORCE版本、井/运行划分、许可和缩放；实传感、公开回放与孪生数据分域。python tools/verify_data.py要求井/整次运行交叉0、未来标签访问0、同轨迹增强不跨集合、预处理只拟合训练集。输出data/manifest.json、splits.json、label_schema.json、dataset_card.md与许可。没有真值的水害不建立真实性能指标。

### A01 自动激励和传感基线

A执行可编程源阶跃/斜坡/噪声及传感静态采集，不连接执行器。python integration/input_fixture.py --trials 100要求刺激种子/量程/回读同trace_id、DAC与sensor_live清楚区分、采集值有标定依据、全过程超时有停止输出/现场保留。输出原始ADC字节、校准曲线和接线照片；软件回放不当实传感pass。

### B02 实际采样与时间戳

B实现XADC/输入流、通道顺序、sample_id/tick/quality、DMA与PS原始记录。python tools/run_rtl.py --suite acquisition覆盖100Hz/通道、输入无效、饱和和重启；A运行python integration/board_acquisition.py --duration 600，通道错位、重复和静默丢样0。实际采样时序/偏斜与理想档位分报，12bit数据不能称16bit测量精度。

### B03 流水线 FIFO和复位

B实现独立编码块、有限队列、背压与跨域同步释放；明确单侧复位/停钟契约。python tools/run_rtl.py --suite stream_reset --seed 20261014覆盖满空、TLAST/长度、长背压、停止时钟、半帧复位、所有合法释放顺序；接收样本唯一去向、溢出计数一致。保存CDC/RDC和时序例外，仿真不能证明亚稳态可靠性。

### B04 线速 调度与恢复

B实现Q0事件/控制、Q1当前趋势、Q2历史；C对端独立收发。python tools/verify_link.py --baud 300 --duration 1800覆盖正常、事件洪泛、5%损坏/丢帧、噪声RAW和断链；长期队列有界、坏CRC拒绝、错误长度重同步、无静默历史丢失。A逻辑分析仪核真实8N1/换向/所有业务计费，含guard和重传；事件P99≤3s无错、≤6s一次重传。

### B05 控制确认与保守状态

B实现session/观察seq/TTL、影子配置、stop优先和上电未使能。python tools/run_rtl.py --suite control_state覆盖重复、旧会话、超范围、TTL、epoch回绕、ACK丢失和重启；重复命令不刷新TTL。A运行python integration/board_control.py --trials 100核实际寄存器/ACK值，非法命令应用次数0，本地故障至停止状态目标≤10ms，恢复须新握手和enable。此为逻辑保护，非矿用安全认证。

### B06 实现和模块板测

B构建、A加载。vivado -mode batch -source fpga/build.tcl固定2026.1、xc7z020clg400-1、目标100MHz；python tools/check_build.py要求实现后WNS≥0/TNS=0、关键未约束0、错误DRC0，LUT/FF/BRAM/DSP各目标≤75%。A运行python integration/board_modules.py，配对bit/hwh、真实黄金一致，报告每模块周期/吞吐/背压影响。不用综合估计替实现，不用旧BRAM替新设计。

### C02 模型与公平基线

C先做规则/树模型、原始CNN，再做基于实际回传信息的CNN/摘要模型。python ai_pc/evaluate.py --split test --batch 1输出Macro-F1、每类Recall、混淆矩阵与置信区间；FORCE目标≥0.60，回传下降≤0.03。模拟风险至少100事件及30分钟无事件输入，Recall≥90%、误报≤1/10min。模型固定后再盲测，不以更易样本或相邻窗口泄漏达标。

### C03 AMD NPU实际部署

C准备包，A在8845H执行。先验证X1支持的小INT8图，再部署冻结项目模型；保存SDK/驱动/模型/输入和EP分配日志，核心CNN算子实际落NPU，CPU回退数量明示。python ai_pc/benchmark.py --batch 1 --warmup 100 --runs 1000目标P95≤100ms，报告P50/P95/P99/max、冷编译、CPU同条件与数值差异。不用INT8不支持的Analyzer功能作不存在的必交证据；NPU未通过仅保留CPU开发基线和明确层级。

### C04 受约束反馈策略

C只在有限动作/通信档位内决策；输入为实际接收的信息、age、queue和置信，不读真值。python tools/verify_policy.py覆盖低置信/OOD、缺段、旧观察、参数越界、配置未ACK；所有非法回写拒绝。策略不能改硬限和TTL，E/采样/发送率在块边界生效。输出ai_pc/policy及独立决策轨迹，正常与退化分开计任务结果。

### C05 孪生和故障显示

C构建twin及PC界面。python twin/verify_causality.py --scenario disconnect_reject_reset要求只凭已应用板反馈积分、pending不冒充执行、断板/错误ACK/重启均暂停推进，GAP和误差阴影不伪造连续曲线。标准3D目标≥30FPS仅为界面流畅指标，不能算弱链路吞吐。输出trace一致截图/录像和因果反例。

### A02 盲场景全链路

A统测，C评估、B核字节。场景生成器真值与控制进程隔离，冻结30个布局/扰动种子、每配置重复3次，共90次；目标到达且禁入区不侵入、无人工干预为成功，停在原地不算成功。python integration/system_trials.py --layouts 30 --repeats 3 --seed 20261014要求成功率≥90%、侵入0；正常采样至板确认及孪生响应P99≤8s/max≤12s。原始/帧/AI/下行/板反馈/孪生同trace_id，全部失败保留。

### A03 消融 故障与持续运行

同一数据/场景/线速比较RAW低频保底、固定编码、事件优先、自适应；比较规则/CPU/NPU和原始/回传信息。python integration/ablation.py --trials-per-mode 30分别报任务效果/年龄/线字节/资源，不同时改条件归因。python integration/endurance.py --duration 7200要求2小时无未处理崩溃/无界队列/静默丢失/人工重启。坏CRC、重复、乱序/过期、断链、PC崩溃、FPGA复位各20次，100%符合预定义保守状态，恢复不自动执行旧动作。

### A04 复现 Skill与提交包

A整合，B/C在独立环境复核。python tools/verify_release.py核需求覆盖100%、证据哈希/源码/bit一致、英文小写路径、许可和无凭据/SQLite/私人板标识。冷启动3次均复现；第二环境软件重建与A实板重建分别留证。skill/至少含通用Overlay校验、黄金/指标采集、DMA/metadata错误定位和已验证复用例；report/含真实大模型提示/回答/纠错及两轮择优。11月4日12时冻结包，人类18时前提交并读回平台回执，上传文件不等于提交成功。

## 12 指标 失败与变更规则

metrics/summary.csv每项记录名称/值/单位、型号/模型/精度/输入、软件/时钟/功耗、起终点与同步误差、次数/时长、原日志、tested_commit和status。P99采用nearest-rank，1000样本取升序第990项；超时/错误不能静默剔除。成功率附二项比例区间，90场景不能夸为工业可靠率。

|项目|本版目标|证据|
|---|---|---|
|核心编码|100万样本E=0逐位一致；各E已编码点误差违规0|原始/码流/独立回解、最坏块|
|真实链路|300baud8N1共享预算，30min队列有界|位宽/换向波形、字节账、age和丢弃计数|
|FPGA实现|100MHz，WNS≥0/TNS=0，关键未约束0，DRC错误0|布局布线/CDC/RDC报告、配对bit/hwh|
|告警到达|无错P99≤3s；一次重传≤6s|同仪器时标或有同步误差界的trace|
|逻辑保护|故障至停止状态≤10ms，100次全通过|真实PL标记/寄存器及异常用例|
|公开岩性|raw Macro-F1≥0.60，回传降幅≤0.03|分井盲集、类别/缺失统计|
|模拟危险|≥100事件Recall≥90%，误报≤1/10min|固定生成器/种子，控制无真值访问|
|AMD NPU|项目图实际执行，batch1 P95≤100ms|实际EP日志/模型哈希、1000次分布和CPU对照|
|孪生闭环|90试次≥90%成功，侵入0；P99≤8s/max≤12s|板确认到孪生积分因果trace、全部失败|
|持续/恢复|2小时无未处理异常，每类故障20次全符合契约|完整日志、窗口账、恢复会话与状态|
|复现/协作|3次冷启动、独立软件环境、Skill复用及真实交互记录|构建和运行证据、需求映射与清单|

这些是工程验收线，不是已测成绩或官方统一门槛。simulation、synthesis、implementation、board、system分别标not_run/failed/blocked/passed。变更输入规格、模型、阈值或硬件须更新版本并重验受影响任务；不得改结果分母来追认通过。

## 13 风险 分级降级与交付

10月23日后不换核心算法；10月30日未通过增强项退出当前参赛包；11月2日后只修可复现阻塞，修后重跑相关验收。队列过载先撤历史和增强，不隐性降低测量口径；NPU驱动/模型失败保留CPU基础结果，先修同设备部署，不立即要求增购PC；数据无水害真值就只输出地层变化/模拟风险；3D拖期退2D但仍由实际板反馈驱动。强层级只加测量和鲁棒性，不以新功能掩盖正确性缺口。

最终包包含产品源码、Tcl/XDC、bit/hwh/xsa、模型与许可、数据清单/划分、依赖锁定、BOM/接线/标定、指标原始证据、交互纠错/择优记录、Skill、报告、视频、英文海报与操作册。研究原件按来源存档，受限数据或第三方大包用合法下载清单，不混入凭据。参赛成绩只描述完成实测的能力，模拟和未来拓展标记明确。

任务书后续由pipeline从R01/R02/R03开始推进，B01与C01在接口确定后并行，S2/S3并行，A串行板测后进入系统验收。阶段失败保存证据并自动分派明确归属的修复；只有必须人类参与的真实依赖才提出集中请求。

## 14 原始案例和技术来源

|来源|本项目采用的经验|适用边界|
|---|---|---|
|[CCSDS121.0-B-3](https://ccsds.org/Pubs/121x0b3.pdf)和[120.0-G-4](https://ccsds.org/Pubs/120x0g4.pdf)|预测残差、Rice、分块/RAW及有限缓冲|自研协议不宣称CCSDS合规，不保证固定压缩比|
|[NASA Rice原报告](https://ntrs.nasa.gov/citations/19790014634)|整数源编码与自适应思想|不能把其他硬件吞吐当Z2实测|
|[AMD Vitis压缩库](https://xilinx.github.io/Vitis_Libraries/data_compression/2022.1/source/overview.html)|L1模块和移植参考|Alveo Overlay不是Z2即用；许可证随实际借鉴模块保留|
|[TUL Z2手册](https://dpoauwgwqsy2x.cloudfront.net/Download/PYNQ_Z2_User_Manual_v1.1.pdf)和[UG480 XADC](https://docs.amd.com/r/en-US/ug480_7Series_XADC/Analog-to-Digital-Converter)|电平、共享引脚、ADC真实精度|以实物修订和实际XDC验证，不裸接超限电压|
|[FORCE官方仓库](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition)和[作者数据](https://zenodo.org/records/4351156)|分井岩性、缺失/置信与许可|北海油气日志不是煤矿现场，也没有自动水害真值|
|[SDT原论文](https://xk.sia.cn/en/article/id/2635)和[两阶段测井压缩研究](https://www.mdpi.com/1424-8220/25/14/4512)|趋势与下游任务保真评估|只借鉴思路，增强另测，不能套论文成绩|
|[SLB MWD案例](https://www.slb.com/-/media/files/oilfield-review/p44-54)|低速遥测与本地档案分层|特定油气泥浆脉冲，不证明所有煤矿线缆300bps|
|[Ryzen AI1.7.1部署](https://ryzenai.docs.amd.com/en/1.7.1/inst.html)和[模型分区](https://ryzenai.docs.amd.com/en/1.6/modelrun.html)|HPT X1、小CNN、CPU回退/实际落点日志|设备存在不等于本模型NPU执行，不以TOPS换算响应|
|[A冻结源](https://github.com/carolwjade/CarlandFPGA/tree/1412d6d70985848fff1332479c98a8be54f15e87/docs/competition/deepeye-2026/round1/a)、[B PR13](https://github.com/carolwjade/CarlandFPGA/pull/13)、[C冻结源](https://github.com/Alan-xuan/CarlandFPGA/tree/ab527e20eb7bc8a0cdeab0409943ec17510830fe/docs/competition/mine_plan_20261013/c)|真实三机五案、内部融合、封存及第二轮输入|版本1历史假设不直接升级成版本2要求；新测量按实际提交归档|

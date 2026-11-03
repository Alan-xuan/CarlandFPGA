# A98C/A100C：原 UI 演示可读性检查

结论：可以复用原 UI 和 A 已保存的场景，但现有显示不能保证完整视频所需的六段证据同时可读。当前 A488 原始报告仍是 **0 AI / 0 APPLY / 无运动 / 无完整蓝入红出 / 无成功视频**。本交付只做源码与已发布数据字节审阅，没有运行产品、UI、板卡或数值测试。

原 C main `01a14025-4dfd-7ec3-aebb-57be48daba59`；task `DEEPEYE-IMPLEMENTATION-20261014/version1`；work `C58-A98C-VIDEO-READINESS-20261103-v1`；operation `C-A98C-VIDEO-READINESS-20261103-v1`。A99延期是A报告的阶段背景，非本聊天合同修改；原5–10分钟窗口已过，不宣称准时。

## 立即采用的镜头顺序

1. 复用 A 的原实例、已保存场景与既有 WGC 录制，不重新 Save、载入C布局或创建第二控制实例。先确认左栏“选择”模式，再点空白处取消选择；左栏下滚“相机”→“聚焦选中”→“等轴测”，给出蓝红门、障碍的总览。保留右栏与底部事件。整场30m与约0.24m钻头/0.30m标称门比例悬殊，不能保证同一远景辨清门孔和完整钻体。
2. 入蓝前点“聚焦钻头”，中央3D区滚轮拉远，右拖环绕、中拖平移，使完整头/杆/尾、蓝圈及门平面参照同框。取略斜侧视，避免纯轴向视角把钻杆尾部重叠到钻尖。转向避障时保留最近障碍与完整钻体；红出圈时同样保留红圈和尾部穿出。镜头是操作建议，**本轮未实际验证动态可见性**，不给伪造的固定相机坐标或预置路径。
3. 聚焦钻头只定位一次，不自动跟随。六方向/等轴测按钮保留焦点与距离；F聚焦选中或场景中心，Esc发停止请求。不要误按R/S修改选中障碍。右栏竖滚到对应信息；长串换行会把pose/周期推到下方。必要时在连续原始录像中分段展示同一周期/源时间/绑定身份，不能把不同周期的值剪接成一次成功链。
4. 不以画面重叠/间隙代替全体积碰撞判定；不以“几何有效”、STOP、已停止、TRACE COMPLETE或任何“已报告”代替整钻体积过蓝/红门的原权威记录。安全停止仍须实际确认，完成仍须原完整穿越判定。

## 六段信息的准确位置与缺项

以下行号基于 `6c92f9a01bd0c6aed8b66aaef6346171e11210eb`；三个UI文件与 `d4095b9abbf27fcfe7bb66a11e4f27da2cf72ee0` 和C57已核原件完全同字节。

| 信息 | 原右栏“30h闭环演示”字段 | 本次核实与限制 |
|---|---|---|
| raw | `data.raw` → 原始值；`data.source_time` → 源时间 | shell.gd105–112/618。A488 summary保留3组真实来源payload，其channel_counts/channel_values是数组；若直接传数组/字典到显示函数，会显示“未知”。建议原coordinator提供真实短标量摘要，并保留完整原payload与周期，不把摘要当完整原数据。实际producer如何填UI未验证。 |
| E4 | `data.encoded` → 编码数据；`data.codec_mode` → 还原差异/模式 | shell.gd619–630。“编码数据”不是E4专用成功字段；只有真实mode/原帧验证才能标E4。A488 `02-response.json`的`result.response.raw_wire_hex`为292字符/146字节、4帧；若原样作为encoded传入，会被160字符上限截掉132字符。不能从录像中只见前缀就宣称完整帧已展示。 |
| decoded | `data.decoded` → 解压值；`reconstruction_error`、`e0_match` | shell.gd618–630。非标量/缺失显示未知，e0_match仅布尔值映射一致/不一致。E4原始帧存在不等于UI已获解码值或E=0通过。本次没有解码/质量测试。 |
| AI | `stages.ai_decision` → AI决策；`data.ai_decision` → AI判断；`control_command` → 控制指令 | shell.gd101–112/611–618。A488 summary明确actual_AI=false，不可补造AI输出。阶段observed只显示“已报告”，不是独立AI资格证明。 |
| actual G05 | `stages.board_readback` → 板端回读；`data.board_output` → 板端输出/回读值 | 无专用G05身份/接受/应用成功显示。通用board_output不可自动等同真实G05；需要A原回复里的同build/BOOT/op/request/周期与实际动作绑定。A488 actual_APPLY=false，不能展示成已执行。 |
| pose | `stages.motion` → 模拟器实际运动；`data.drill_pose` → 钻头姿态（读回）；`cycle` → 周期 | shell.gd101–112/611–618。若pose直接为数组/字典仍是未知；短串只能辅助观察连续变化。A488 actual_motion=false。该UI没有已核专用完整蓝入/红出、最小障碍距离或整钻避让成功字段。 |

`viewer/main.gd137–140`仅在原owned-ready后将status转交shell，`shell.gd585–636`校验显示schema并渲染coordinator传入值，不做独立板端证明。UI字段表不能证明A的新driver已经成功填值。A应先检查已有真实字段；缺失就保留“未知/等待/失败”，不能为了录屏把状态置成observed。

## 具体可见性问题与两行候选补丁

- `shell.gd572–582`：只接受String/Int/Float/Bool；null、Array、Dictionary、非有限Float和空白返回“未知”。超过160字符静默截断。自动换行或滚动不会恢复已经截掉的数据。
- `shell.gd265–269/559–569`：右栏是竖滚，标签自动换行；没有一屏同时显示所有字段的保证。只读源码审查不证明当前真实屏幕是否正好溢出。
- `main.gd807–815/915–923`：实体/门标签采用billboard与no_depth_test。C57原图05已有近景大文字遮挡；该图作为历史视觉证据，不是本轮A现场复现。“坐标刻度”开关只控制刻度，不能当作隐藏所有资产/门标签。优先调整角度/距离保留完整轮廓，不改变几何或碰撞比例。
- `main.gd412`：聚焦钻头日志固定附带“权威未连接”，不是连接检查。连接状态应读右栏真实status，不能用这条相机日志判断。

`display-clarity.patch`只改两行，供A在自己的受控集成流程审阅：相机日志改为“连接状态见右栏”；长标量仍最多160字符，但末尾用`...`明确截断。它**不补造缺失值，不显示完整长帧，不修复全部标签遮挡，不改authority/门/碰撞/时间预算/判定**。只做了精确文本diff与独立静态审查，**未做Godot导入或UI运行验证，不自动部署**。无需为了此补丁重启正在运行的A实例。

## 原件与验收边界

A100发布commit为 `6c92f9a01bd0c6aed8b66aaef6346171e11210eb`；其partial manifest SHA `1e0d2510dc829cee04049bb05b42acaf1cbd44502d47b93173fc0a1543fdfd22`，manifest注明实际tested software commit为 `2f303122f9635ce874da04a61891036ba7d579d7`，不能混用。已下载并逐项核验01/02/03/04与summary五个原文件的manifest长度/SHA及Git blob；这证明远端字节身份，不是C重跑实板。

A报告的实际batch `1607450232ns`、TRACE COMPLETE/QUIESCENT与完整3s target残余预算拒绝被保留。summary的actual_AI、actual_APPLY、actual_motion、whole_blue_red_crossing、successful_video均false；source_observations仍标twin_fixture/candidate_only。新8s/C0只属A报告的演示工程配置，不提升最终100ms、模型/传感质量或双H12验收。A已Save场景SHA d475a484046dd65d45f458f49a2062f39b233feecd2033313a3abe7e01e8876f仅引用A身份，不重建场景。

交付目录仅 `handoffs/c/C-DEMO3H-VIDEO-READINESS-481/`，附source pins、A字节核验摘要、两行patch、独审及只读字节校验器。未拷贝/修改A运行实例、driver或录制器；原C56 helper ACK/terminal/worker-join缺口不提升。原peer不可用记录保留，本轮不重试/重启或建立第二发送器；GitHub交付不冒充peer ACK。

合同 `DEEPEYE-HUMAN-LOCK-20261014/revision1`；source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`；requirements SHA `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`；fixed design `1011259415a0916054eb580687612580bc1e5f09`。H01–H15/原29/双H12/final100MHz/1%/100ms全部保留，formal acceptance=false；物理板仅A。

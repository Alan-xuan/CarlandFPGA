# A102C：公共蓝入/红出分阶段目标

**需要修正，现有投影没有等价的入口目标切换。** 在 A 指定发布源 `45bbe744c9889ede53169138acdd2013429513b0`，`g05_csr_projection_v1.py:207–215` 默认取红圈中心；有 navigation profile 时改为红圈外整钻余量目标，无论当前是否已经入蓝。因此它可能让初始仍在蓝圈外的钻头提前朝红圈侧转。A102 所述 yaw5013/pitch0/speed14/3s 是 A 报告，本次没有读入511原始场景或重新执行来归因；仅能确认当前代码缺少入口阶段选择。

原 C main `01a14025-4dfd-7ec3-aebb-57be48daba59`；同任务 `DEEPEYE-IMPLEMENTATION-20261014/version1`；work `C59-A102C-PUBLIC-PORTAL-GOAL-20261103-v1`，operation `C-A102C-PUBLIC-PORTAL-GOAL-20261103-v1`。仅 handoff patch/evidence；A/B产品文件、B12s profile、A519 bit/driver保持各自归属。

## 最小候选及边界算术

令蓝/红圈公开中心为 `b/r`，其立方体面单位外法线为 `n_b/n_r`，公开capsule半轴长 `h`、半径 `rho`，原声明的数值及资产误差上界为 `epsilon_n/epsilon_a`。沿任意单位法线的轴投影最大值不超过h，所以使用原代码已接受的保守上界：

`D = h + rho + epsilon_n + epsilon_a + 0.05m`

- 未完整入蓝：`goal = b - D*n_b`，沿法线方向再向内 `nextafter` 一次。
- 同一次运行已提交完整 ENTERED：`goal = r + D*n_r`，沿法线方向再向外 `nextafter` 一次。

已有 `_nav_exit_goal`（16–38行）采用 Fraction 求精确输入值和，轴向 nextafter 使取整向安全方向。候选直接复用它，把入口法线取反；不新增距离常数、不按当前钻尖或当前姿态缩小完整刚体余量。示例 h=.4、rho=.12、numeric=.001、asset=.002 得 D约.573m，仅为显式算术示例，**不是已核A现场误差值**。真实代码始终使用原values/envelope/budget/profile。六面正负法线均适用，圈中心来自当前自由编辑后的公开layout，不限定固定面或预置路线。

目标位于入口内侧不证明从现有任意姿态到该目标可行，也不证明门孔、其他五面或障碍安全。极近边界、同面邻近门、小门、转弯半径、速度/时效等仍可能导致原规划或执行拒绝；拒绝必须保留。不要放宽碰撞、移动门、扩大门径、减小钻体或延长原deadline来让目标通过。

## 切换必须绑定已执行历史

候选 `public-portal-goal.patch` 只在现有navigation分支改变目标选择，旧None profile行为不动。使用原executor的 `passage_state()` 读取**已提交执行链的门事件**，不是新collision probe、未提交preview、屏幕推测或请求ACK。这里只把自己已执行的入蓝事实用于目标选择；没有读取障碍位置、solid/PDE字段、地图种子、场景快照或精确碰撞失败信息，向PC的既有公开schema仍只输出goal_m与原传感/pose/history。

关键绑定与易错点：

1. 原投影173–191行已绑定当前getter、registry hold、owner/BOOT、book/executor同一Root；候选在此范围内再核Root对象未换、pose_revision及pose相同、同layout/envelope，world_invalid/trial_failed未置位。未知/不一致直接拒绝，不退回红目标。
2. `root_source_book.py:324–340` 的原current_pose_interval给出实际getter及有效区间；`_actor_source_custody.py:166–190`只有原STEP committed、getter_admitted、receipt及执行区间一致后才闭合。因此必须继续原获取/关联流程，不能用UI字符串或外部字典输入entered。
3. **不能直接读 `root.phase.entered`。** `motion_executor.py:385`提交新Root时仍保存relative.previous；`passage_state():211–223`才按已提交frame/fence物化事件。候选使用该原方法，且再次检查当前Root身份。该方法失败会按原设计撤销后续动作，候选不吞异常。
4. `passage_phase.py:219–221`只有蓝侧及所有面whole-body严格inside且原切片校验成功才生成ENTERED。使用完整历史中的ENTERED和phase一致性；不以中心刚过平面、钻尖入圈或目标距离为切换依据。
5. `navigation_session_profile.py:86–104`仅保留24个公开观测/动作。若从这个滚动列表临时重建entered，旧入口证据可能丢失；同面蓝红出口时当前位置还会再次靠近蓝面。候选依赖同一执行链保留的累计门事件，入蓝后不会因为窗口滚动或同面退出而重新瞄准蓝圈。

`passage_state`是宿主原执行历史访问器，并非增加给PC的全场接口。A集成时须确认这部分自身已执行门事件按当前公共策略可用于goal选择；若仅允许数值pose，不能用一个未绑定bool替代，应保留缺口，补上绑定getter/执行链的公共门事件投影后再采用。候选没有新增或运行该公共接口。

## AI职责与验收界限

分阶段goal只是使用公开蓝红目标进行任务分解，不给预计算航点、绕障路线、yaw/pitch/speed脚本或全图。原PC core仍须从实际板返回的因果四通道观测估计/建图/规划方向和速度；原安全层继续做完整体积、门孔、六面和障碍的执行约束。H11是否有真实收益仍须独立实证，不能把直线目标选择当AI验收。

已执行：原源码远端bytes/SHA/Git blob核验，候选语法解析，隔离的原坐标纯函数六面×入/出共12例与NaN/Inf拒绝2例，exit0；没有导入产品模块。补丁对应原投影SHA `4559bd81501c9f1c843648c95adb331332dd51f1dabbd13a80d41834c1ff6d43`。本轮由原C主独立审查A实现，未创建新工作会话；未宣称有第二名补丁审查者。

**尚未执行**：真实typed getter/phase集成、Godot/native、模型、旧PDE/数值suite、板测、应用补丁、录屏、实际入蓝/出红。候选仅供A独立审查及受控集成；A应核自己新head及pins（特别B12s并行改动），不直接复制覆盖整文件或热改运行实例。原是否采用、部署及实际板视频验证归A。当前watchdog fault4并非此补丁所修复。

固定合同 `DEEPEYE-HUMAN-LOCK-20261014/revision1`；source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`；requirements SHA `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`；design `1011259415a0916054eb580687612580bc1e5f09`。H01–H15、原29、双H12、final100MHz/1%/100ms不变；G03/R03/all29与formal acceptance未提升；实板仅A。

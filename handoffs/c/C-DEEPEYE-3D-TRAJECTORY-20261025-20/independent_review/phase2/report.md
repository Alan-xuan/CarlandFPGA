# Independent 3D trajectory review — FINAL

任务 DEEPEYE-IMPLEMENTATION-20261014/v1；工作 C-3D-TRAJECTORY-INDEPENDENT-REVIEW-20261025-v1。
主会话01a14025-4dfd-7ec3-aebb-57be48daba59，复核者/root/cpu_independent_review。
基线5b237220c6ca87bdea0fbba79f8f1b379d5d4304，冻结design/H01–H15及固定合同不变。

**结论：固定源码的限定几何准备范围内未发现阻塞。独立黑盒exit0；不代表C02/C03或任何完整控制/正式验收通过。**

| 固定输入 | SHA256 |
|---|---|
| trajectory_candidates.py | ede34dfa38f093c7ba0858ca211b824e08268447846a0859b9a69cb4cb7a0c15 |
| swept_capsule.py | 765b83405a4773c2e4da4806d9d42bd39bc66bda6e78f0a4acf9e3d86eba5b4a |
| TRAJECTORY_CANDIDATE.md | 87daba843f69425a7d8db78fc2ba382586770fb581586003601c79e4cf3294b9 |
| 作者delivery manifest | f1f128b867acb623f2aea49cab00e9c453312e93cb5e8ac786f46e7a01e43ad1 |

1. Phase1的11份原工件逐项哈希未变；oracle在阅读新实现前独立封存。本次只加载固定两模块及未改kinematics，未导入作者测试。11个解析单原语端点加两原语非共面控制均符合预期，最大位置差约1.07e-14m。覆盖正负yaw/pitch、body右乘/世界初姿态、加减速及停车、stress映射，尤其步内命中目标速度的路程.002498m。未把单恒曲率圆弧错误要求成有扭率曲线。
2. 共23组既定小控制exit0，原始argv/stdout/stderr在independent.*。除解析组，还核正例非空3D fixture、初始/侧/尾/相切、未知与覆盖优先、有限预算无部分输出、输入类型/别名/确定性、位姿和占据膨胀。所有结果movement_authorized=false。
3. Phase1的10ms微薄尾部反例未被false-clear。实际返回conservative_occupied_overlap、blocking_interval0：保守AABB在真实中途胶囊接触之前已拒绝。此结果不证明精确接触定位，也不单靠采样证明连续覆盖。
4. 静态连续包络链完整：swept116–133行以起始姿态的全胶囊在chord两端的脊线极值构成AABB，再加半径.12、max(.0005,2*.52*sin(theta/2))、完整子步路程L、累计路程S传播的初始位姿误差和独立数值余量。任意弧上中心距起点不超过L，起点在chord上，因此L是有效的保守平移偏离界；转动刚体点距pivot不超过.52，旋转位移界成立。多项相加及向外nextafter只扩大支持，不遗漏真实几何。此胶囊总长1.04m是有意包住.80m模型的假设，不是A实物/pivot测量。
5. occupied/unknown先于单free覆盖；无覆盖、仅free并集无单盒证明均unknown。固体cube严格内含、接触拒绝，无门洞或arrived例外。轨迹/候选/批次和geometry预算耗尽均返回明确budget_exhausted并清空相应部分输出；类型/有限性、归一化输入、profile和合成曲率通过原kinematics校验，不作clip。
6. 数值余量是该double/libm实现的显式工程预算及本次有限对照，非所有平台的区间算术证明或A引擎误差标定。实际模型/pivot、速度或位姿误差超过声明界时不继承clear结论。AABB及完整L可能强烈多拒绝，不能当精确碰撞求解器、完整地图或搜索器。
7. 原始作者tests-01/tests-final/examples均记录exit0，流哈希与保存source-before已独立核对。tests-01绑定早期源码；只有tests-final及examples绑定本次最终源码，已区分。作者25项未重跑。source-review.diff的两模块及文档新增文本与最终输入相符。作者Python3.13；本独立控制Python3.12.14。source/证据读取中一个不存在的namespace __init__.py探查产生exit1，原输出保留；它不是黑盒或产品失败。

未触及产品/index、网络外发、凭据/SQL、服务/controller、训练/CPU推理/heldout、旧套件或板卡；仅写private phase2目录，保留phase1原字节。没有学习模型、真实观测地图、sim_em、全局规划、门洞到达、runtime授权或完整路径证据；C02/C03及所有相关正式门仍未完成。只有A操作物理板。当前无活动复核作业，完成后释放。

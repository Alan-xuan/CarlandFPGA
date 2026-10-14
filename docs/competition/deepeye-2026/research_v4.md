# v4 三维演示研究依据

核对日期2026-10-14。只采用引擎官方文档、制造商原始资料及研究作者资料。下表把厂商事实、工程推断与本项目假设分开；来源证明已有技术依据，不证明本项目已实现。v3的赛事、编码、FORCE、ROCm和PGA原始依据继续有效。

|来源|本轮实际核到的依据|本项目采用方式与边界|
|---|---|---|
|[Godot发布政策](https://docs.godotengine.org/en/stable/about/release_policy.html)、[4.6发布](https://godotengine.org/releases/4.6/)|4.6为受维护分支，Windows图形后端包含D3D12/Vulkan|锁同分支维护版及导出模板hash，先在目标AMD PC实测后端；不是已做GPU兼容测试|
|[Godot PBR材质](https://docs.godotengine.org/en/4.6/tutorials/3d/standard_material_3d.html)|材质提供金属度、粗糙度和法线等能力|用于钻头金属与地质体视觉；具体资产与帧时由G01/G07验收|
|[Godot碰撞体](https://docs.godotengine.org/en/4.6/tutorials/physics/collision_shapes_3d.html)、[运动查询API](https://docs.godotengine.org/en/4.5/classes/class_physicsdirectspacestate3d.html)|存在凸体/形状运动查询；cast可能忽略初始已相交对象|独立初始overlap、旋转细分和完整钻具扫掠；API依据不等于已覆盖薄层/尾部碰撞|
|[Godot导航边界](https://docs.godotengine.org/en/4.6/tutorials/navigation/navigation_using_navigationmeshes.html)|NavMesh表示角色可以站立的表面，视觉/碰撞体不自动加入规划|采用三维体积图与姿态/曲率基元；不把默认地面导航包装成三维钻进规划|
|[Godot Windows导出](https://docs.godotengine.org/en/4.6/tutorials/export/exporting_for_windows.html)、[命令行导出](https://docs.godotengine.org/en/4.6/tutorials/export/exporting_projects.html)、[许可](https://godotengine.org/license/)|Windows x64导出、匹配模板、MIT及第三方组件声明|G08交付原生离线包和许可，不能只交编辑器工程或截图|
|[Halliburton EarthStar3DX原始发布](https://www.halliburton.com/en/about-us/press-release/halliburton-launches-earthstar-3dx-horizontal-look-ahead-resistivity-service)|2025-05-19介绍水平钻进前方最多50ft的地层电阻率信息|50ft换算15.24m仅为适用量级上界依据；本模型8m是公开工程假设，不等于厂家保证8m检测所有障碍|
|[SLB IriSphere说明](https://www.slb.com/resource-library/interview/drl/irisphere-see-ahead-bit)、[官方首发](https://www.slb.com/newsroom/press-release/2019/pr-2019-0506-schlumberger-irisphere)|前视电阻率与建模/反演结合；量程依工具布局和敏感性，资料给100ft量级|只模拟连续电性响应及方向差分，不输出精确物体坐标，不声称微型低价探头具有商用整套系统能力|
|[SLB实际geo-stopping案例](https://www.slb.com/resource-library/tech-report/dr/irisphere-middle-east-tr)|案例中在前方40ft获得响应并据此停钻，实施前有敏感性研究|采用可观测性试验和风险停止，不把最大宣传量程当固定触发开关；不套用其现场成功率|
|[ADXL355 RevD原始数据手册](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl354_adxl355.pdf)、[ADI产品页](https://www.analog.com/en/products/adxl355.html)|±2/4/8g，20bit，±2g档噪声密度22.5µg/√Hz|采用±2g及25Hz等效带宽噪声计算112.5µg。振动仅接触/负载后反应；12bit实物注入量化另外计算，不称20bit实测|
|[Honeywell ABP2官方页](https://automation.honeywell.com/us/en/products/sensing-solutions/sensors/pressure-sensors/board-mount-pressure-amplified/basic-abp2-series-board-mount-pressure-sensor)|整个系列约200Hz、2.5mbar–20bar；TEB随具体型号变化|只作可选接触压力profile依据，0m超前距离；替换现有通道并重训重验，不新增免费通道或强制购置|
|[LaValle作者在线教材](https://msl.cs.uiuc.edu/planning/web.html)|有微分约束/运动基元/非完整与动力学规划的成熟体系|用姿态/曲率限制和有限基元代价搜索；本项目当前观测下候选最小代价，不声称未知全图全局最优|

## 明确由项目选择的参数

30m立方体、0.24m钻径、0.80m钻具长度、0.30m蓝红圈、2m演示转弯半径、0.25m/s最高演示速度、EM8m支持/20Hz更新/0.03log噪声/30度主瓣和方向差分，均是为可控缩尺演示公开定义的工程假设。厂家资料未提供这些模拟器参数，更未保证这些条件下的准确率。G03通过响应曲线与负例测实际模拟器检测距离/误报，再限制速度。

模型只输出四通道物理量代理；实际DAC、XADC、PL及RS485把测量送回PC AI。矿用高压温度、地质多解性、全波传播、真实井眼/钻杆动力学不在本届仿真验证范围；界面和报告标注适用边界，演示不能升级为现场安全声明。

## 需要留待实施取得的证据

Godot具体补丁/导出模板/后端与hash；资产真截图；实际三维应用帧时间；controller文件/IPC隔离与远场同输入反例；DAC/XADC标定和延迟；EM合成检测曲线；ROCm项目模型与规划现场并发日志；三路实板捕获；90次盲场景；同信息PC_DIRECT对照。以上当前均not_run。网页事实、文档数学校核及产品实测不混为一类。

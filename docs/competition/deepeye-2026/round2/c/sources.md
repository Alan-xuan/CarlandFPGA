# 输入、来源和支持边界

本轮质量主模型为本机控制器登记的 `gpt-6-astra/ultra`。主模型实际读取A/B/C最佳并作模块融合；已有DeepSeek只做公开资料检索，没有替代决策。未调用新的架构子任务。所有版本在2026-10-13 UTC检索；动态网页只支持当时快照，不保证之后的安装兼容。

## 三机封存输入

|节点|冻结时间 UTC|实际读取及字节核验|SHA256|
|---|---|---|---|
|A|2026-10-13T16:23:34.937482|[精确公开commit的best](https://raw.githubusercontent.com/carolwjade/CarlandFPGA/1412d6d70985848fff1332479c98a8be54f15e87/docs/competition/deepeye-2026/round1/a/best.md)4640B下载并核hash，保存于inputs/a_best_verified.md；与先前解盲消息正文补回末尾LF完全一致|d9716026589a298e4554d018c9478539cf9a2840458129e246e1134173911416|
|B|2026-10-13T16:12:22.122304Z|[PR13](https://github.com/carolwjade/CarlandFPGA/pull/13) 的冻结head ec0675dfb2f1f86c6201b2d1e2ea27d3f5a04ff8，[完整最佳任务书](https://raw.githubusercontent.com/carolwjade/CarlandFPGA/ec0675dfb2f1f86c6201b2d1e2ea27d3f5a04ff8/docs/competition/deepeye-2026/round1/b/PROJECT_TASKBOOK_DRAFT.md) 32186B|6088bb2de9e220f751f0623774f0cba91c0b88ba3fdcfcd0abf179ad483439c8|
|C|2026-10-13T16:05:55.279944Z|桌面C独立研究原件；本地ab527e20eb7bc8a0cdeab0409943ec17510830fe，另公开[PR14](https://github.com/carolwjade/CarlandFPGA/pull/14) head850dd499dae69446545e96a3a2b92d6e4b4b7cc9同树；[最佳原文](https://raw.githubusercontent.com/Alan-xuan/CarlandFPGA/850dd499dae69446545e96a3a2b92d6e4b4b7cc9/docs/competition/mine_plan_20261013/c/best_proposal.md)6085B已下载核验|5243500c579b3a24e097b2a1d41e038d09128b635648968f313a00bf0a1889af|

C的[冻结清单](https://raw.githubusercontent.com/Alan-xuan/CarlandFPGA/ab527e20eb7bc8a0cdeab0409943ec17510830fe/docs/competition/mine_plan_20261013/c/freeze_manifest.json)对应本地六个原始文件全部复核一致。公开Git blob中最佳及四份候选/审查共五项字节一致；budget_result.json在Git中为922B、26行LF，SHA256为7262a4843883dddac32dc0cafbee9f3f81cca2da8011bcac01d028d5a375d5da，转换回CRLF才等于封存87fb5e57a7e24cfbbcedc0f28885d38a8ae349beb7e05e08bd90b68a24ea1f11。因此不称六项公开raw均符合原hash。A/B亦独立确认该差异；不修改原freeze。初版16:05:30后仅在交流前修正算术，最终六文件hash见input_hashes.json。C另一个主会话是本机桌面会话，不算第四台机器。本会话复用其首轮；没有将本会话中断前仅做的取证冒充另一组五案。

解盲消息ID `C:COMP-20261013-DEEPEYE:round2:C:unblind-v1`。v2范围依据B回报 `C:B-COMP-20261013-DEEPEYE-r2-C-provenance-v2`：A真人更新为AMD3.3、真实传感+FPGA反馈+数字孪生。3.3正文已由C独立读完；不依赖转述推断规则。A的自动化要求来自用户所附补充消息 `main:632f38ac8da68c57400653bed46849fefaea6cf51fcac96a54db0aae075a0349`，A独占automation_contract，不改变本轮仅研究授权。

## 官方与原始材料

|ID|URL与定位|支持范围|不能推出什么|
|---|---|---|---|
|S1|[AMD选题指南官件同哈希镜像](https://raw.githubusercontent.com/nbstarhkc/Qian-Sai/main/sources/amd.pdf)，3.3印刷19–22页/物理22–25页；[赛事官网](http://www.fpgachina.cn/)|A从官网file25取得原件，C下载镜像950952B并核SHA256 c6ad82acd4f7bdcd13bd412e232ed85d05f2a87dd5e2cdd04f9d219f88b569fc。C提取并读完整3.3：板级实测、工程包、协作记录、技能包、30/20/20/15/15评分与工具说明|3.2限制不自动适用于3.3；不能把镜像仓库当官方发布者；资格组别以报名记录为准|
|S1b|[大赛通知同哈希镜像](https://raw.githubusercontent.com/nbstarhkc/Qian-Sai/main/sources/notice.pdf)|779290B，SHA256 c17611b45a66121cd93f421e7fdee50f1743b1eb0cb5d9f930c57578d480ef9f，与A官网file18一致|本机文本提取为空（扫描件），截止18时来自A实际原件核读报告，C只独立核了文件字节；提交前A核后台|
|S2|[AMD ROCm7.14兼容矩阵](https://rocm.docs.amd.com/en/docs-7.14.0/compatibility/compatibility-matrix.html)，[安装说明](https://rocm.docs.amd.com/en/docs-7.14.0/install/rocm.html)|所取快照列HX370/gfx1150、Max+395/gfx1151；可作GPU候选路线的依据|具体框架/整机驱动组合及项目模型仍需实测；3.3不要求这一个ROCm版本|
|S3|[Ryzen AI1.8发布说明](https://ryzenai.docs.amd.com/en/latest/relnotes.html)，[安装](https://ryzenai.docs.amd.com/en/latest/inst.html)，[算子支持](https://ryzenai.docs.amd.com/en/latest/ops_support.html)|Strix及Strix Halo属于支持系列，CNN可走INT8/BF16；CPU回落与算子分配须核实|NPU不能因此被安排任意字节流解压；TOPS不是batch1速度；不预填PyTorch/ORT版本|
|S4|[MINISFORUM AI X1 Pro官方规格](https://www.minisforum.com/products/minisforum-ai-x1-pro)|HX370及32GB/1TB等配置可作为明确SKU候选|网页价格/库存会变，不保证本地含税成交价或到货；先查可借实际机器|
|S5|[CCSDS121.0-B-3](https://ccsds.org/Pubs/121x0b3.pdf)|可逆熵编码、预测与独立实现的参考来源|不是煤矿4:1/8:1或Z020实测速率依据；本项目不宣称标准认证|
|S6|[FORCE2020原始仓库](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition)，[Zenodo数据记录](https://zenodo.org/records/4351156)，[DataCite许可元数据](https://api.datacite.org/dois/10.5281/zenodo.4351156)|原始任务是井曲线岩性预测；DataCite返回CC-BY4.0；适合整井划分、编码和任务保真度回放|不是矿井随钻危险/含水标签；再分发前还须按实际下载文件核许可归属和署名|
|S7|[PYNQ changelog](https://pynq.readthedocs.io/en/latest/changelog.html)|4.0不再支持PYNQ-Z1/Z2；版本锁要以实际镜像和overlay配套为准|不能自动升级PYNQ来解决所有驱动问题；本轮未重装或板测|
|S8|[Microchip MCP3204官方数据手册](https://ww1.microchip.com/downloads/en/DeviceDoc/21298e.pdf)|4路12位SPI ADC，供电范围允许3.3V设计；足以支持低速真实采样提案|数据手册不是现成模块电平担保；12位容器扩成16位不能虚增压缩收益|
|S9|[原始地质导向研究](https://arxiv.org/abs/1903.03933)，[后续地质导向方法研究](https://arxiv.org/abs/2011.00733)|为不确定性下的决策和仿真评测提供方法来源|不能替代本台架实测，更不是煤矿下井验证；未来虚拟前视模型必须明确公开|
|S10|A实机回报 `C:COMP-20261013-DEEPEYE:round2:C:a-public-platform-v2`|A实测8845H/32GB/780M、Win11 Home build26200、NPU present/OK、驱动32.0.203.240、未发现1.7/1.8 SDK；此信息优先于首轮新机候选|C未远程操作A主机；NPU枚举正常不等于项目推理已通过；驱动/SDK适配仍not_run|

原始网页/PDF在本机 `.planning/competition-20261013/` 留存取证；不将第三方整篇文章复制到公开提交。可公开的URL、字节哈希、取得时间与边界记录在source_hashes.json。文档中的预算是本质量主模型推导，验证输出只证明算术，不计作仿真或硬件证据。

## 研究评分与否决门

三套首轮权重有历史差异：请求中的研究权重为25/20/20/20/10/5，C桌面原稿采用另一组权重。本轮不回改独立封存，也不把C旧分和A/B分相加。3.3官分为30/20/20/15/15。第二轮依据模块证据融合，不用总分代替关键缺陷审查。

否决门：板端输入/输出电平未核；新设计无同版bit/hwh及实测；AI读取测试真值或高速原始旁路；数据无使用许可；协议漏计命令/反馈造成持续拥塞；反馈由PC虚构；版本不匹配仍声称测量。NPU增强失败、未加机械机构、未使用ROCm均不自动否决v2核心，必须如实缩减展示主张。

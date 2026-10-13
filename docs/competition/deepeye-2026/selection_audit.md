# 两轮择优审计

任务COMP-20261013-DEEPEYE/v3。主会话A负责最终工程选择。15套完整首轮候选的设计内容在A封存前不互传；A研究子代理不是B/C。

|节点|首轮封存|主成果|第二轮实际成果|
|---|---|---|---|
|A|2026-10-13T16:23:34.937482Z|五套完整方案、内部A6融合；commit1412d6d70985848fff1332479c98a8be54f15e87；best SHA d9716026589a298e4554d018c9478539cf9a2840458129e246e1134173911416|质量主会话读B/C原文、预算与规则，形成taskbook_v3.md；原初轮不改|
|B|2026-10-13T16:12:22.122304Z|[PR13](https://github.com/carolwjade/CarlandFPGA/pull/13)；head ec0675dfb2f1f86c6201b2d1e2ea27d3f5a04ff8；17项交接清单核通过|[PR16](https://github.com/carolwjade/CarlandFPGA/pull/16) head43068749dc62435aadd94724064b08985dc2420c；冻结15项blob全部匹配；review SHA821a52d3ff405263cadddaebf0cf048f1a977dcc953f850cc1b916fb89fd6db8；根稿补评SHA b358702911b6f06047353908fe7b5245d263f5a7577e93a6e40befeb592b8a6e|
|C|2026-10-13T16:05:55.279944Z|[PR14](https://github.com/carolwjade/CarlandFPGA/pull/14)；五案正文及best核符；预算JSON保留CRLF/LF差异|[PR15](https://github.com/carolwjade/CarlandFPGA/pull/15) head11ecdc42cf1aad66624eb37c301700599cb9e62a；冻结8项blob全部匹配；review SHA1def955b0f29e041828f693f43d6196b8bdf9a368a9e6d9154dac8edd829b25e|

三机首轮研究权重存在差异，不横比旧总分。最终逐模块采用：A定长任务信息/共享容量骨架，B独立块、RAW、17位差分及命令恢复，C缺测/年龄/因果数据和独立输出回采。舍弃复杂字典、学习式遥测、压缩感知、先购高价PC和真实钻头机构作为关键路径。分级提高测量和复现，增强不得掩盖基础错误。

B实际针对根稿77722819…f30c指出配置ACK无唯一关联、TTL后旧状态持续推进、queue无线上出处。终版abi_v2逐项改为type/seq/session唯一键与CONFIG_ACK实际值、捕获反馈及主机保守截止、删除在线queue，并重新按144/200/204B最坏窗口计费。C提出GPIO/PWM独立回采和断线反例已纳入；不照搬其16B新帧头或旧平均预算。

C实际读完同一根稿并核PDF/MD哈希，追加指出grant未定义、事件包络与3秒指标关系及提交人类/agent口径冲突。终版grant使用既有quality_flags bit15/14及冻结槽表，无新增未计费帧；给独立告警间隔≥8秒正常包络，洪泛另报且不删分母；S7/A04统一为有既有明确授权/本人账号时agent代办、人类仅必要本人交互。两机对旧稿的意见是实际完成复核；终版新内容是否签署须以新回执为准。

B实际读回PR17首发head1d4374fcc0f5ba1bf07b80d5e7f3487816af0143及正文SHA a9ea6bd2b61ac5be804f0a0a0f889be3dbad4b4a5d08082497e7070803ce14b8，核20卡和预算字段，指出首次ACK丢失后的旧缓存延长租期、204B窗没有第二授权槽两处P0。修订1仅缓存事务结果，每次重编码当前TTL/phase/tick，并以主机first_send＋originalTTL作上界；用quality_flags bit13预授权第二个同键重试槽，完整slot表锁定超时/偏移、bit14互斥，实际字节与空等分别计费。B05/C05加入精确反例。旧提交保持可追溯，不把首发的文档检查冒作修订后的产品通过。

后续人类最新口径由A实时UI逐字核到：“AMD Ryzen AI PC＋任意AMD FPGA，无进一步细分和分组，应用自主选题”；同时要求不再追问新细节，A/C若B中断可各自先定稿交付。A据官件3.2纠正版本2的3.3判断，明确ROCm及真实物理任务门槛；不冒称B/C版本2已经评审这个新修订。真人先前传感/无现实钻头执行器约束保留，最小物理任务候选为传感前端量程调节，其赛事认可尚待资料核验。

只将已实际取得的主会话评析、原始blob、哈希与复算计为完成；peer delivered表示传输，不表示模型完成或签署。所有产品实现、训练、综合、实现和实测仍not_run。原件source和收件记录本地保存，不把私人账户、机器标识、凭据或完整协作数据库上传。

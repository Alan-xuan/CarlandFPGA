# 飞书应用上线交接

2026-10-11 权限补充：本人已明确允许仅 Astra-A 增加 `im:resource`，飞书实际返回应用身份 `grant_status=1`；原三个消息权限保留，DeepSeek 的三个原权限未变。注册模板及原地更新的只读权限检查已同步。B/C 已有应用必须由各自所有者在原 Astra 的权限页开通，不能通过分发 ZIP 自动授权、不能给 DeepSeek 增权。详见 [原地更新说明](IN_PLACE_UPDATE_2026-10-11.md)。

目标群：`FPGA/AI/DEV`，Chat ID `oc_e0de73230fd64dd2da3e52fc781dffb1`。这是外部群，应用机器人需具备外部共享资格；自定义 Webhook 机器人不能接收人类群指令，不能替代 Astra。

| A 机身份 | 应用 ID | 应用身份权限 | 事件订阅 |
| --- | --- | --- | --- |
| FPGA Astra A | `cli_aa4c9f58dd385cc9` | `im:message:send_as_bot`、`im:message`、`im:message.group_msg`、`im:resource` | `im.message.receive_v1`，长连接 |
| FPGA DeepSeek A | `cli_aa4c9f8c59785cd1` | `im:message:send_as_bot`、`im:message:readonly`、`im:message.group_msg` | 无 |

A 机两应用已建立、启用机器人能力并开通表中权限；账号本人完成个人实名认证后，两个应用的 `1.0.2` 版本已发布，开启外部群使用资格，并以独立机器人身份加入 `FPGA/AI/DEV`。密钥只在 `.local/deployment/node-a/feishu/`，未进入 Git 或分发包。Astra 的 `im.message.receive_v1` 已发布，使用长连接；DeepSeek 不订阅群事件。

2026-10-09 真实入群自测：Astra 发信并同身份读回 `om_x100b63bf43487ca0ddcb678dbbf1b38`，DeepSeek 发信并同身份读回 `om_x100b63bf40e1acacc3e1441b46f594e`，两条命令均返回 `"status": "verified"`，群客户端能见到对应机器人消息。A 机配置的 `feishu.enabled=true`，计划任务 `FPGA-Mesh-Node-A` 运行中。真人在群内发送 `/fpga A` 链路指令后，Astra 回复 `ACK_7e2d1a`；修复 SDK 回调线程与 SQLite 所在线程不一致的问题后，常驻计划任务再次接收真人指令并回复 `ACK_39c4f1`，该次入站记录为零重试、无错误。以上证明 **A 机两个身份入群发读、Astra 群指令接收与回报**；B/C 尚未部署，不能据此声称三机联通。

B/C 各自在自己的账号创建对应两应用；若其外部共享开关被禁用，各账号本人须完成实名认证。发布权限与外部共享后，到群设置 → Bots → Add Bot 逐一加入机器人，再做各身份自测与真人群指令验收。自定义 Webhook 机器人只有群消息推送能力，不能代替本方案的 Astra 群指令接收。

入群后、标记上线前，逐身份运行下列 A 机自测；B/C 由 `deploy/Join-FPGAMesh.ps1` 自动执行同样的检查。每个身份用自己的凭据只发送一条带标记的消息，再读回相同的消息 ID、群 ID 和文本。失败保持该身份关闭。发送成功但读回失败时，本机回执保留，重跑只补读。此操作没有模型调用；DeepSeek 不会订阅群消息或自主读群。

```powershell
.local\venv\Scripts\python.exe -m fpga_mesh.feishu_selftest --node A --role astra --app-id cli_aa4c9f58dd385cc9 --secret-file .local\deployment\node-a\feishu\astra-secret.txt --group-id oc_e0de73230fd64dd2da3e52fc781dffb1 --state-file .local\deployment\node-a\feishu\astra-selftest.json
.local\venv\Scripts\python.exe -m fpga_mesh.feishu_selftest --node A --role deepseek --app-id cli_aa4c9f8c59785cd1 --secret-file .local\deployment\node-a\feishu\deepseek-secret.txt --group-id oc_e0de73230fd64dd2da3e52fc781dffb1 --state-file .local\deployment\node-a\feishu\deepseek-selftest.json
```

A 机已完成上述门槛并保持服务运行；B/C 上线也必须分别通过这两条检查，并由真人群指令核验 Astra 的长连接接收。API 必要条件与返回码见[飞书获取会话历史](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/list)。

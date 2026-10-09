# 客机 @NODE@：仓库交接和实板反馈

`scripts/handoff.py` 是纯本机清单工具。`request` 字段与 `fpga_mesh.hardware.HardwareRequest` 对齐，`passed` 阶段需要非空真实日志；SHA-256 只证明文件字节一致，不能证明测试判定正确。所有清单文件路径以仓库根目录为 root，使用 `/` 分隔并保持在仓库内。

## 提交顺序

1. 在节点 @NODE@ 的 `codex/@NODE_LOWER@/<task-id>` 分支提交设计源文件、约束、测试和可公开日志；记录这次源码提交的完整 SHA。仓库忽略 `logs/`、`*.log` 和 `artifacts/`；把要交接的原始日志按字节复制为任务目录下的 `.txt`，用 `git ls-files` 确认它已进入提交。不要在 `main` 工作，也不要把密钥、许可证、SQLite、私有硬件标识或临时构建缓存加入公开仓库。需要 `.bit` 等大文件时遵守仓库 Git LFS 规则。
2. 在仓库内建立唯一的 `handoffs/@NODE_LOWER@/<operation-id>/`。写 `input.json`，其 `request.requester` 为 `node-@NODE_LOWER@`，`code_commit` 为上一步源码提交；`operation_id`、`task_id`、正整数 `task_version`、非空 `test_steps` 和 `expected_result` 填写本轮实际内容。`artifacts` 列出仓库相对源码/约束/测试文件；`stages` 列出仿真与实现等真实结果，硬件用 `blocked` 或 `not_run`。需要记录日志的阶段引用仓库内文件。
3. 从仓库根目录执行：

```powershell
python skills/pynq-z2-single-node/scripts/handoff.py create --root . --input handoffs/@NODE_LOWER@/<operation-id>/input.json --output handoffs/@NODE_LOWER@/<operation-id>/manifest.json
python skills/pynq-z2-single-node/scripts/handoff.py verify --root . --manifest handoffs/@NODE_LOWER@/<operation-id>/manifest.json
```

若从安装目录运行，把脚本路径替换为该目录的绝对路径。清单创建后不要改动它引用的文件；如需修改，建立新的 operation ID 与清单。提交 `input.json` 和 `manifest.json`，确认工作树干净，再推送自己的 fork 分支并向上游 `carolwjade/CarlandFPGA:main` 创建 PR。没有上游写权限时走 fork/PR；不要尝试直接推送上游 `main`。PR 正文给出 `operation_id`、`request_hash`、源码提交 SHA、PR 当前 head SHA、清单路径、测试步骤、预期结果以及未运行阶段。确认 PR 链接可打开后再通知 A。

## A 机回传格式

A 机只在核对清单、取到 PR 指定提交并完成真实上传/运行后，在同一 PR 留下可审阅反馈。反馈至少记录：

- `operation_id` 与 `request_hash`，用于对应不可覆盖的交接清单；
- `tested_commit`，为 A 实际检出的完整 PR head SHA；
- 硬件阶段 `passed`、`failed` 或 `blocked` 与具体测试步骤；
- 实际板卡/镜像/工具版本、运行命令、退出码，及可公开日志或报告路径与 SHA-256；
- 失败现象、复现条件和需客机修改的代码位置。

节点 @NODE@ 仅在收到 PR/同伴通知后读取反馈，逐项核对 `operation_id`、`request_hash`、`tested_commit` 和证据。若 PR 后续又有提交，旧反馈只对旧 SHA 有效。可用 `gh pr view <PR号> --repo carolwjade/CarlandFPGA --comments` 查看回传；没有实时网络时记录等待状态，不猜测 A 的结果。飞书或同伴消息可提供即时提醒，但以 PR 的持久记录为准。

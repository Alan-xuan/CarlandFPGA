Node C real local evidence for MESH-20261011-132845-c94f2686

The original dirty workspace and all credentials, identities and ledgers were retained.
This independent branch starts at the latest 7ad82d2 MANIFEST revision.
Only the node-owned handoffs/c directory is changed.

Actual commands used on C (resident workspace):
  codex login status
  gh api user --jq .login
  python -m fpga_mesh.project_cli health
  python -m fpga_mesh.project_cli session_list
  python -m fpga_mesh.feishu_permissions --config <existing-node-c-config>
  Tailscale status --json (public evidence retains only peer count)
  ProjectActions fpga_group_report/fpga_peer_send through LocalControlFileClient
  ProjectActions delegate/wait/native_reserve for completed Flash/max and guard checks
  ProjectActions main_submit/main_wait/session_route for actual official model turns
  Existing Astra-C Feishu SDK upload, message readback, resource download and SHA-256

The first Luna probe was interrupted by a real human C ingress event. The persisted
interruption and duplicate queued=false receipt were retained. A new explicit v2
completed on the same thread with Luna/low after Astra/ultra completed.
A file resource first returned API 234003 when the upload key was used as the
message resource key. Reading the actual message key fixed only the GET; no resend.

Replay evidence checks, without network/model calls:
  python handoffs/c/MESH-20261011-132845-c94f2686/verify_evidence.py
This validates saved real receipts and hashes, not a new live acceptance run.
Network/HMAC, A-assigned work and A PR acknowledgement remain blocked.

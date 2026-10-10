"""Astra-only dynamic tools for group reports and direct peer communication."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .protocol import Envelope, MessageKind, SourceKind


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function", "name": name, "description": description,
        "inputSchema": {
            "type": "object", "properties": properties,
            "required": required, "additionalProperties": False,
        },
    }


class MeshDynamicTools:
    def __init__(
        self, *, node_id: str, project_id: str, child_tools: Any,
        children: Any, store: Any, peer: Any | None, feishu: Any | None,
    ) -> None:
        self.node_id = node_id
        self.project_id = project_id
        self.child_tools = child_tools
        self._child_tool_names = {
            spec["name"] for spec in child_tools.specs()
        }
        self.children = children
        self.store = store
        self.peer = peer
        self.feishu = feishu

    def specs(self) -> list[dict]:
        return self.child_tools.specs() + self.main_specs()

    @staticmethod
    def main_specs() -> list[dict]:
        return [
            _tool(
                "fpga_group_report",
                "Report a key fact to the human team as this node's Astra bot. "
                "The message is durably queued and retried without model polling.",
                {"operation_id": {"type": "string"},
                 "text": {"type": "string"}},
                ["operation_id", "text"],
            ),
            _tool(
                "fpga_peer_send",
                "Send a task report to another Astra node over the private peer mesh. "
                "Offline messages stay queued locally and retry without model polling.",
                {"peer_id": {"type": "string", "enum": ["A", "B", "C"]},
                 "task_id": {"type": "string"},
                 "task_version": {"type": "integer", "minimum": 1},
                 "operation_id": {"type": "string"},
                 "text": {"type": "string"}},
                ["peer_id", "task_id", "task_version", "operation_id", "text"],
            ),
            _tool(
                "fpga_child_group_report",
                "On explicit parent request, publish a completed, current child result "
                "through the shared DeepSeek bot for DeepSeek jobs, or Astra for native GPT jobs. "
                "Children never listen to the group.",
                {"job_id": {"type": "string"},
                 "operation_id": {"type": "string"}},
                ["job_id", "operation_id"],
            ),
        ]

    async def call(self, name: str, arguments: dict) -> object:
        if name in self._child_tool_names:
            return await self.child_tools.call(name, arguments)
        if name == "fpga_group_report":
            self._require_feishu()
            operation_id = self._required(arguments, "operation_id")
            text = self._required(arguments, "text")
            queued = self.store.enqueue_group_report(operation_id, text)
            self.feishu.notify_report()
            return {"queued": queued or bool(self.store.pending_group_messages()),
                    "operation_id": operation_id, "role": "astra"}
        if name == "fpga_peer_send":
            peer_id = self._required(arguments, "peer_id")
            if peer_id not in {"A", "B", "C"} or peer_id == self.node_id:
                raise ValueError("peer_id must be a different A/B/C node")
            task_id = self._required(arguments, "task_id")
            operation_id = self._required(arguments, "operation_id")
            text = self._required(arguments, "text")
            task_version = int(arguments["task_version"])
            if task_version < 1:
                raise ValueError("task_version must be positive")
            message = Envelope(
                message_id=f"{peer_id}:{operation_id}", project_id=self.project_id,
                sender=f"{self.node_id}/Astra-{self.node_id}",
                recipient=f"{peer_id}/Astra-{peer_id}",
                task_id=task_id, task_version=task_version,
                sent_at=datetime.now(timezone.utc),
                kind=MessageKind.AGENT_REPORT, source=SourceKind.ASTRA,
                payload={"text": text},
            )
            if self.peer is None:
                self.store.enqueue_outbound(message, peer_id=peer_id)
                return {"delivered": False, "queued": True,
                        "operation_id": operation_id}
            delivered = await self.peer.send(peer_id, message)
            return {"delivered": delivered, "queued": not delivered,
                    "operation_id": operation_id}
        if name == "fpga_child_group_report":
            self._require_feishu()
            job_id = self._required(arguments, "job_id")
            operation_id = self._required(arguments, "operation_id")
            job = self.children.job(job_id)
            if job["stale"]:
                raise ValueError("stale child job cannot be published")
            if job["status"] != "completed":
                raise ValueError("child job is not completed")
            content = str((job.get("result") or {}).get("text", "")).strip()
            if not content:
                raise ValueError("child result has no text")
            role = "astra" if job.get("route") == "gpt_native" else "deepseek"
            if role == "deepseek" and self.feishu.deepseek_sender is None:
                raise RuntimeError("DeepSeek Feishu sender is not configured")
            identity = "Astra" if role == "astra" else "DeepSeek"
            text = f"{identity}-{self.node_id} · {job['task_id']} · {job_id}\n{content[:4000]}"
            queued = self.store.enqueue_group_report(
                operation_id, text, role=role, job_id=job_id,
            )
            self.feishu.notify_report()
            return {"queued": queued or bool(self.store.pending_group_messages()),
                    "operation_id": operation_id, "role": role}
        raise ValueError(f"unknown mesh tool: {name}")

    def _require_feishu(self) -> None:
        if self.feishu is None:
            raise RuntimeError("Feishu group is not configured")

    @staticmethod
    def _required(arguments: dict, key: str) -> str:
        value = arguments.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} is required")
        return value.strip()

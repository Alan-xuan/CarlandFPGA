"""Verify Astra's model-chosen effort persists on one Codex thread."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from fpga_mesh.protocol import Envelope, MessageKind, SourceKind
from fpga_mesh.runtime import NodeConfig, NodeRuntime


def message(number: int, text: str) -> Envelope:
    return Envelope(
        message_id=f"effort-smoke-{number}", project_id="fpga-main",
        sender="human-smoke", recipient="A/Astra-A",
        task_id=f"effort-smoke-{number}", task_version=1,
        sent_at=datetime.now(timezone.utc),
        kind=MessageKind.HUMAN_INSTRUCTION, source=SourceKind.HUMAN,
        payload={"text": text},
    )


async def main() -> None:
    root = Path(__file__).resolve().parent.parent
    runtime = NodeRuntime(NodeConfig(
        node_id="A", project_id="fpga-main",
        state_dir=root / ".local" / "effort-switch",
        mode="app_server",
        hardware_enabled=False, peer_urls={},
        shared_secret_env="FPGA_MESH_SHARED_SECRET",
    ))
    await runtime.start()
    try:
        tasks = [
            "Reply with exactly ACK. This is a simple one-line acknowledgement.",
            ("Review this FPGA design concern: asynchronous reset deassertion "
             "feeds three unrelated clock domains, one of which crosses data "
             "through a FIFO. Give three concrete verification checks and a "
             "short risk assessment. Assume no board access."),
        ]
        samples = []
        for number, task in enumerate(tasks, 1):
            result = await runtime.astra_gateway.handle(message(number, task))
            thread = await runtime.astra_gateway._client.session.request(
                "thread/read", {"threadId": result.output["thread_id"],
                                "includeTurns": False},
            )
            samples.append({
                "selected_effort": result.output["reasoning_effort"],
                "persisted_effort": thread["thread"]["reasoningEffort"],
                "thread_id": result.output["thread_id"],
                "response_length": len(result.output["text"]),
            })
        print(json.dumps(samples, ensure_ascii=True))
    finally:
        await runtime.stop()


if __name__ == "__main__":
    asyncio.run(main())

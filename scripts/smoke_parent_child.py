"""Exercise one real Astra → local DeepSeek child round trip."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from fpga_mesh.protocol import Envelope, MessageKind, SourceKind
from fpga_mesh.runtime import NodeConfig, NodeRuntime


def build_smoke_message(node: str) -> Envelope:
    if node not in {"A", "B", "C"}:
        raise ValueError("node must be A, B, or C")
    instruction = (
        "Use the native fpga_child_delegate dynamic tool with task_id "
        "smoke-parent-child, task_version 1, and text 'Reply exactly "
        "CHILD_OK.' Read the returned job_id and use fpga_child_wait to "
        "read the persisted child result. Report only its actual text. "
        "Do not guess, do not answer yourself, and do not print secrets."
    )
    return Envelope(
        message_id=f"live-parent-child-{node}", project_id="fpga-main",
        sender="human-smoke", recipient=f"{node}/Astra-{node}",
        task_id="smoke-parent-child", task_version=1,
        sent_at=datetime.now(timezone.utc),
        kind=MessageKind.HUMAN_INSTRUCTION, source=SourceKind.HUMAN,
        payload={"text": instruction},
    )


async def run(key_file: Path, node: str = "A") -> None:
    root = Path(__file__).resolve().parent.parent
    runtime = NodeRuntime(NodeConfig(
        node_id=node, project_id="fpga-main",
        state_dir=root / ".local" / f"live-parent-child-{node.lower()}",
        mode="app_server",
        hardware_enabled=False, peer_urls={},
        shared_secret_env="FPGA_MESH_SHARED_SECRET",
        deepseek_key_file=key_file,
    ))
    await runtime.start()
    try:
        message = build_smoke_message(node)
        parent = await runtime.astra_gateway.handle(message)
        jobs = runtime.children.status()["jobs"]
        print(json.dumps({
            "parent_accepted": parent.accepted,
            "parent_text": parent.output.get("text", ""),
            "parent_effort": parent.output.get("reasoning_effort"),
            "parent_thread_id": parent.output.get("thread_id"),
            "child_jobs": [{"status": j["status"],
                            "result_text": (j["result"] or {}).get("text")}
                           for j in jobs[-1:]],
            "pool_efforts": sorted({i["reasoning_effort"] for i in
                                    runtime.pool.snapshot()["instances"]}),
        }, ensure_ascii=True))
    finally:
        await runtime.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--node", choices="ABC", default="A")
    args = parser.parse_args()
    asyncio.run(run(args.key_file, args.node))

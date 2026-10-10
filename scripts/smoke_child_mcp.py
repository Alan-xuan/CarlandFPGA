"""Verify that a Codex app-server thread can call the local child MCP."""

from __future__ import annotations

import asyncio
import argparse
import json
from pathlib import Path

from fpga_mesh.app_server import AppServerClient
from fpga_mesh.runtime import NodeConfig, NodeRuntime


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turn", action="store_true")
    parser.add_argument("--cli-turn", action="store_true")
    parser.add_argument("--dynamic-turn", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    runtime = NodeRuntime(NodeConfig(
        node_id="A", project_id="fpga-main",
        state_dir=root / ".local" / "MCP-中文路径",
        mode="test_double",
        hardware_enabled=False, peer_urls={},
        shared_secret_env="FPGA_MESH_SHARED_SECRET",
    ))
    await runtime.start()
    client = None
    try:
        client = await AppServerClient.start_stdio(
            codex_home=Path.home() / ".codex",
            client_version="0.159.0", role="astra",
        )
        await client.initialize()
        if args.dynamic_turn:
            started = await client.session.request("thread/start", {
                "cwd": str(root), "model": "gpt-6-astra",
                "modelProvider": "openai", "config": runtime.astra_tool_config(),
                "dynamicTools": [{
                    "type": "function", "name": "fpga_child_status",
                    "description": "Read the live standby count from the local DeepSeek child pool.",
                    "inputSchema": {"type": "object", "properties": {},
                                    "required": [], "additionalProperties": False},
                }],
            })
        else:
            started = await client.thread_start(
                cwd=str(root), model="gpt-6-astra",
                model_provider="openai", config=runtime.astra_tool_config(),
            )
        thread_id = started["thread"]["id"]
        result = await asyncio.wait_for(client.session.request(
            "mcpServer/tool/call", {
                "threadId": thread_id, "server": "fpga_children",
                "tool": "child_status", "arguments": {},
            }), timeout=15)
        content = result.get("content", [])
        status = json.loads(content[0]["text"]) if content else {}
        print(json.dumps({
            "ok": not result.get("isError", False),
            "standby": status.get("pool", {}).get("standby"),
            "tools": len(content),
        }, ensure_ascii=True))
        if args.turn or args.cli_turn or args.dynamic_turn:
            instruction = (
                "Call the fpga_children child_status MCP tool now. "
                "Report only whether the tool call succeeded and "
                "the integer standby count. Do not guess."
            )
            if args.cli_turn:
                control_file = runtime.config.state_dir / "child-control.json"
                instruction = (
                    "Use your shell tool to run the following PowerShell command "
                    "and report the standby count in its JSON output. Do not "
                    "guess: & '" + str(Path(__import__('sys').executable)) +
                    "' -m fpga_mesh.child_cli --control-file '" +
                    str(control_file) + "' status"
                )
            if args.dynamic_turn:
                instruction = (
                    "Call the dynamic tool fpga_child_status now. Report "
                    "only its live standby count. Do not guess."
                )
            await client.turn_start(
                thread_id=thread_id,
                text=instruction,
                model="gpt-6-astra", effort="low",
            )
            seen = []
            dynamic_calls = 0
            while True:
                event = await asyncio.wait_for(
                    client.session.next_notification(), timeout=90,
                )
                if event.method == "item/tool/call":
                    dynamic_calls += 1
                    live = runtime.children.status()
                    await client.session.respond(event.request_id, {
                        "contentItems": [{"type": "inputText",
                                          "text": json.dumps(live, ensure_ascii=True)}],
                        "success": True,
                    })
                if event.method in {"item/completed", "turn/completed", "error"}:
                    seen.append({
                        "method": event.method,
                        "item_type": event.params.get("item", {}).get("type"),
                        "text": str(event.params.get("item", {}).get("text", ""))[:300],
                        "status": event.params.get("turn", {}).get("status"),
                    })
                if event.method in {"turn/completed", "error"}:
                    break
            print(json.dumps({"events": seen, "dynamic_calls": dynamic_calls},
                             ensure_ascii=True))
    finally:
        if client is not None:
            await client.close()
        await runtime.stop()


if __name__ == "__main__":
    asyncio.run(main())

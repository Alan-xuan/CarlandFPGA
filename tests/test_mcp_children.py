import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fpga_mesh.child_control import ChildCoordinator, LocalControlClient, LocalControlServer
from fpga_mesh.codex import CodexHomeFactory
from fpga_mesh.controller import ActionResult
from fpga_mesh.mcp_children import McpChildServer
from fpga_mesh.pool import InstancePool


class Gateway:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def handle(self, message):
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return ActionResult(accepted=True, output={"text": "child result"})


class McpChildServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.gateway = Gateway()
        pool = InstancePool(
            node_id="A", gateway=self.gateway,
            home_factory=CodexHomeFactory(root / "中文工作区"),
            state_path=root / "pool.json",
        )
        await pool.ensure_standby(2)
        self.coordinator = ChildCoordinator(
            node_id="A", project_id="fpga-main", pool=pool,
            state_path=root / "jobs.sqlite",
        )
        self.control = LocalControlServer(self.coordinator, token="private")
        await self.control.start()
        self.mcp = McpChildServer(LocalControlClient(
            host="127.0.0.1", port=self.control.port, token="private",
        ))

    async def asyncTearDown(self):
        await self.control.close()
        await self.coordinator.close()
        self.temp.cleanup()

    async def test_mcp_lists_only_parent_control_tools(self):
        initialized = await self.mcp.process({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        })
        self.assertIn("tools", initialized["result"]["capabilities"])
        listed = await self.mcp.process({
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        })
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertEqual(names, {"child_status", "child_scale", "child_delegate",
                                 "child_wait", "child_cancel", "native_reserve",
                                 "native_validate", "native_complete"})
        self.assertEqual(self.gateway.calls, 0)

    async def test_mcp_delegation_and_wait_use_real_pool_without_polling(self):
        assigned = await self.mcp.process({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "child_delegate", "arguments": {
                "task_id": "task-1", "task_version": 1, "text": "review timing",
            }},
        })
        job_id = json.loads(assigned["result"]["content"][0]["text"])["job_id"]
        await asyncio.wait_for(self.gateway.started.wait(), 1)
        waiting = asyncio.create_task(self.mcp.process({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "child_wait", "arguments": {"job_ids": [job_id]}},
        }))
        await asyncio.sleep(0)
        self.assertFalse(waiting.done())
        self.assertEqual(self.gateway.calls, 1)
        self.gateway.release.set()
        result = await asyncio.wait_for(waiting, 1)
        completed = json.loads(result["result"]["content"][0]["text"])
        self.assertEqual(completed[0]["result"]["text"], "child result")
        self.assertEqual(self.gateway.calls, 1)

    async def test_mcp_unknown_tool_reports_error_without_running_child(self):
        response = await self.mcp.process({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "unsafe_tool", "arguments": {}},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(self.gateway.calls, 0)

    async def test_stdio_tool_result_is_utf8_even_with_windows_legacy_encoding(self):
        env = dict(os.environ)
        env.update({
            "FPGA_CHILD_CONTROL_PORT": str(self.control.port),
            "FPGA_CHILD_CONTROL_TOKEN": "private",
            "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
            "PYTHONIOENCODING": "gbk",
        })
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "fpga_mesh.mcp_children",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "child_status", "arguments": {}}}
            process.stdin.write((json.dumps(request) + "\n").encode("utf-8"))
            await process.stdin.drain()
            raw = await asyncio.wait_for(process.stdout.readline(), 2)
            response = json.loads(raw.decode("utf-8"))
            self.assertEqual(response["result"]["isError"], False)
        finally:
            process.terminate()
            await process.wait()


if __name__ == "__main__":
    unittest.main()

import tempfile
import asyncio
import unittest
from pathlib import Path

from fpga_mesh.app_server import AppServerClient
from fpga_mesh.gateway import AppServerGateway, GatewayConfig
from fpga_mesh.protocol import Envelope, MessageKind, SourceKind
from fpga_mesh.rpc import JsonRpcNotification
from datetime import datetime, timezone


class FakeSession:
    def __init__(self):
        self.requests = []
        self.notifications = []

    async def request(self, method, params=None):
        self.requests.append((method, params or {}))
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}}
        if method == "turn/start":
            return {"turn": {"id": "turn-1"}}
        return {}

    async def notify(self, method, params=None):
        self.requests.append((method, params or {}))

    async def respond(self, request_id, result):
        self.requests.append(("response", {"id": request_id, "result": result}))

    async def next_notification(self):
        return self.notifications.pop(0)

    async def close(self):
        self.requests.append(("close", {}))


def message() -> Envelope:
    return Envelope(
        message_id="msg-1",
        project_id="fpga-main",
        sender="human-1",
        recipient="A/Astra-A",
        task_id="task-1",
        task_version=1,
        sent_at=datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc),
        kind=MessageKind.HUMAN_INSTRUCTION,
        source=SourceKind.HUMAN,
        payload={"text": "inspect"},
    )


class AppServerGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = FakeSession()
        self.client = AppServerClient(self.session, client_version="0.159.0")
        self.config = GatewayConfig(
            node_id="A",
            role="astra",
            model="gpt-6-astra",
            provider="openai",
            reasoning_effort="max",
            cwd=str(Path.cwd()),
            codex_home=str(Path(self.tmp.name)),
        )
        self.gateway = AppServerGateway(
            self.config,
            client_factory=lambda: self.client,
        )

    async def asyncTearDown(self):
        await self.gateway.close()
        self.tmp.cleanup()

    async def test_no_model_call_until_a_message_is_handled(self):
        self.assertEqual(self.session.requests, [])
        self.session.notifications.append(
            JsonRpcNotification(
                method="turn/completed",
                params={
                    "threadId": "thread-1",
                    "turn": {
                        "id": "turn-1",
                        "status": "completed",
                        "items": [{"type": "agentMessage", "text": "done"}],
                    }
                },
            )
        )
        result = await self.gateway.handle(message())
        self.assertTrue(result.accepted)
        self.assertEqual(result.output["text"], "done")

    async def test_astra_receives_authoritative_task_identity_for_delegation(self):
        self.session.notifications.append(JsonRpcNotification(
            method="turn/completed",
            params={"threadId": "thread-1", "turn": {
                "id": "turn-1", "status": "completed", "items": [],
            }},
        ))
        await self.gateway.handle(message())
        turn = next(params for method, params in self.session.requests
                    if method == "turn/start")
        prompt = turn["input"][0]["text"] if "input" in turn else turn["text"]
        self.assertIn("task_id: task-1", prompt)
        self.assertIn("task_version: 1", prompt)
        self.assertIn("source: human", prompt)
        self.assertIn("inspect", prompt)

    async def test_second_message_reuses_the_same_thread(self):
        self.session.notifications.extend(
            [
                JsonRpcNotification(
                    method="turn/completed",
                    params={"threadId": "thread-1", "turn": {
                        "id": "turn-1", "status": "completed", "items": [],
                    }},
                ),
                JsonRpcNotification(
                    method="turn/completed",
                    params={"threadId": "thread-1", "turn": {
                        "id": "turn-1", "status": "completed", "items": [],
                    }},
                ),
            ]
        )
        await self.gateway.handle(message())
        await self.gateway.handle(message())
        methods = [method for method, _ in self.session.requests]
        self.assertEqual(methods.count("initialize"), 1)
        self.assertEqual(methods.count("thread/start"), 1)
        self.assertEqual(methods.count("turn/start"), 2)

    async def test_child_gateway_uses_provider_and_max_from_config(self):
        config = GatewayConfig(
            node_id="A",
            role="deepseek_child",
            model="deepseek-flash",
            provider="deepseek",
            reasoning_effort="max",
            cwd=str(Path.cwd()),
            codex_home=str(Path(self.tmp.name)),
        )
        gateway = AppServerGateway(config, client_factory=lambda: self.client)
        self.session.notifications.append(
            JsonRpcNotification(
                method="turn/completed",
                params={"threadId": "thread-1", "turn": {
                    "id": "turn-1", "status": "completed", "items": [],
                }},
            )
        )
        await gateway.handle(message())
        turn = [
            params
            for method, params in self.session.requests
            if method == "turn/start"
        ][0]
        self.assertEqual(turn["model"], "deepseek-flash")
        self.assertEqual(turn["effort"], "max")
        await gateway.close()

    async def test_parent_gateway_registers_tool_config_on_thread_start(self):
        tool_config = {"mcp_servers": {"fpga_children": {
            "command": "python", "args": ["-m", "fpga_mesh.mcp_children"],
        }}}
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            thread_config_factory=lambda: tool_config,
        )
        self.session.notifications.append(
            JsonRpcNotification(method="turn/completed",
                                params={"threadId": "thread-1", "turn": {
                                    "id": "turn-1", "status": "completed", "items": [],
                                }})
        )
        await gateway.handle(message())
        start = [params for method, params in self.session.requests
                 if method == "thread/start"][0]
        self.assertEqual(start["config"], tool_config)
        await gateway.close()

    async def test_parent_gateway_installs_node_policy_on_thread_start(self):
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            developer_instructions="Astra-A: prioritize humans and verify child work",
        )
        self.session.notifications.append(JsonRpcNotification(
            method="turn/completed",
            params={"threadId": "thread-1", "turn": {
                "id": "turn-1", "status": "completed", "items": [],
            }},
        ))
        await gateway.handle(message())
        start = next(params for method, params in self.session.requests
                     if method == "thread/start")
        self.assertIn("prioritize humans", start["developerInstructions"])
        await gateway.close()

    async def test_failed_turn_is_not_reported_as_accepted(self):
        self.session.notifications.append(JsonRpcNotification(
            method="turn/completed",
            params={"threadId": "thread-1", "turn": {"id": "turn-1", "status": "failed",
                             "error": {"message": "provider rejected request"},
                             "items": []}},
        ))
        with self.assertRaisesRegex(RuntimeError, "provider rejected request"):
            await self.gateway.handle(message())

    async def test_retryable_errors_wait_for_successful_turn_completion(self):
        self.session.notifications.extend([
            JsonRpcNotification(method="error", params={
                "threadId": "thread-1", "turnId": "turn-1",
                "error": {"message": "temporary provider interruption"},
                "willRetry": True,
            }),
            JsonRpcNotification(method="error", params={
                "threadId": "thread-1", "turnId": "turn-1",
                "error": {"message": "retrying stream"}, "willRetry": True,
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "phase": "final_answer",
                     "text": "recovered"},
                ]},
            }),
        ])
        result = await self.gateway.handle(message())
        self.assertTrue(result.accepted)
        self.assertEqual(result.output["text"], "recovered")
        self.assertEqual(self.session.notifications, [])

    async def test_terminal_error_surfaces_structured_provider_message(self):
        self.session.notifications.append(JsonRpcNotification(method="error", params={
            "threadId": "thread-1", "turnId": "turn-1",
            "error": {"message": "provider quota exhausted"}, "willRetry": False,
        }))
        with self.assertRaisesRegex(RuntimeError, "provider quota exhausted"):
            await self.gateway.handle(message())

    async def test_errors_from_other_threads_and_turns_do_not_fail_current_work(self):
        self.session.notifications.extend([
            JsonRpcNotification(method="error", params={
                "threadId": "another-thread", "turnId": "turn-1",
                "error": {"message": "another thread failed"}, "willRetry": False,
            }),
            JsonRpcNotification(method="error", params={
                "threadId": "thread-1", "turnId": "an-earlier-turn",
                "error": {"message": "earlier turn failed"}, "willRetry": False,
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "text": "current result"},
                ]},
            }),
        ])
        result = await self.gateway.handle(message())
        self.assertEqual(result.output["text"], "current result")

    async def test_completion_requires_matching_thread_and_explicit_turn_id(self):
        self.session.notifications.extend([
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "another-thread",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "text": "foreign result"},
                ]},
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"status": "completed", "items": [
                    {"type": "agentMessage", "text": "unidentified result"},
                ]},
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "text": "current result"},
                ]},
            }),
        ])
        result = await self.gateway.handle(message())
        self.assertEqual(result.output["text"], "current result")

    async def test_transport_error_without_turn_ids_remains_fatal(self):
        self.session.notifications.append(JsonRpcNotification(
            method="error", params={"message": "app-server connection closed"},
        ))
        with self.assertRaisesRegex(RuntimeError, "app-server connection closed"):
            await self.gateway.handle(message())

    async def test_retry_wait_timeout_interrupts_turn_and_closes_client(self):
        events = [JsonRpcNotification(method="error", params={
            "threadId": "thread-1", "turnId": "turn-1",
            "error": {"message": "temporary stream failure"}, "willRetry": True,
        })]

        async def stalled_retry():
            if events:
                return events.pop(0)
            await asyncio.Event().wait()

        self.session.next_notification = stalled_retry
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client, timeout_seconds=0.01,
        )
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(gateway.handle(message()), 1)
        self.assertIn(("turn/interrupt", {
            "threadId": "thread-1", "turnId": "turn-1",
        }), self.session.requests)
        self.assertIn(("close", {}), self.session.requests)

    async def test_cancel_during_retry_interrupts_turn_and_closes_client(self):
        waiting = asyncio.Event()
        events = [JsonRpcNotification(method="error", params={
            "threadId": "thread-1", "turnId": "turn-1",
            "error": {"message": "temporary stream failure"}, "willRetry": True,
        })]

        async def stalled_retry():
            if events:
                return events.pop(0)
            waiting.set()
            await asyncio.Event().wait()

        self.session.next_notification = stalled_retry
        pending = asyncio.create_task(self.gateway.handle(message()))
        try:
            await asyncio.wait_for(waiting.wait(), 0.2)
        finally:
            pending.cancel()
            try:
                await pending
            except asyncio.CancelledError:
                pass
        self.assertIn(("turn/interrupt", {
            "threadId": "thread-1", "turnId": "turn-1",
        }), self.session.requests)
        self.assertIn(("close", {}), self.session.requests)

    async def test_gateway_uses_final_message_and_skips_old_turn(self):
        self.session.notifications.extend([
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "earlier", "status": "completed", "items": []},
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "phase": "commentary", "text": "working"},
                    {"type": "agentMessage", "phase": "final_answer", "text": "done"},
                ]},
            }),
        ])
        result = await self.gateway.handle(message())
        self.assertEqual(result.output["text"], "done")

    async def test_parent_dynamic_tool_call_is_answered_during_turn(self):
        calls = []

        async def handler(name, arguments):
            calls.append((name, arguments))
            return {"standby": 2}

        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            dynamic_tools=[{"type": "function", "name": "fpga_child_status",
                            "description": "status", "inputSchema": {"type": "object"}}],
            dynamic_tool_handler=handler,
        )
        self.session.notifications.extend([
            JsonRpcNotification(method="item/tool/call", request_id=73,
                                params={"threadId": "thread-1", "turnId": "turn-1",
                                        "tool": "fpga_child_status", "arguments": {}}),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": []},
            }),
        ])
        await gateway.handle(message())
        self.assertEqual(calls, [("fpga_child_status", {})])
        self.assertEqual([params for method, params in self.session.requests
                          if method == "thread/start"][0]["dynamicTools"][0]["name"],
                         "fpga_child_status")
        response = [params for method, params in self.session.requests
                    if method == "response"][0]
        self.assertEqual(response["id"], 73)
        self.assertTrue(response["result"]["success"])
        self.assertIn("standby", response["result"]["contentItems"][0]["text"])
        await gateway.close()

    async def test_non_json_tool_result_returns_failure_response(self):
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            dynamic_tool_handler=lambda _name, _args: {"bad": {1, 2}},
        )
        self.session.notifications.extend([
            JsonRpcNotification(method="item/tool/call", request_id="tool-1",
                                params={"threadId": "thread-1", "turnId": "turn-1",
                                        "tool": "fpga_child_status", "arguments": {}}),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": []},
            }),
        ])
        await gateway.handle(message())
        response = [params for method, params in self.session.requests
                    if method == "response"][0]
        self.assertEqual(response["id"], "tool-1")
        self.assertFalse(response["result"]["success"])
        await gateway.close()

    async def test_parent_uses_model_selected_effort_for_substantive_turn(self):
        class Selector:
            async def choose(self, client, *, cwd, model, text):
                return "medium"

        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            effort_selector=Selector(),
        )
        self.session.notifications.append(JsonRpcNotification(
            method="turn/completed",
            params={"threadId": "thread-1", "turn": {
                "id": "turn-1", "status": "completed", "items": [],
            }},
        ))
        result = await gateway.handle(message())
        turn = [params for method, params in self.session.requests
                if method == "turn/start"][0]
        self.assertEqual(turn["effort"], "medium")
        self.assertEqual(result.output["reasoning_effort"], "medium")
        await gateway.close()

    async def test_selector_failure_closes_session_before_work_turn(self):
        class Selector:
            async def choose(self, client, *, cwd, model, text):
                raise RuntimeError("selector turn could not be interrupted")

        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            effort_selector=Selector(),
        )
        with self.assertRaisesRegex(RuntimeError, "could not be interrupted"):
            await gateway.handle(message())
        methods = [method for method, _ in self.session.requests]
        self.assertIn("close", methods)
        self.assertNotIn("turn/start", methods)

    async def test_turn_start_without_response_is_bounded_and_session_closed(self):
        original_request = self.session.request

        async def hanging_turn(method, params=None):
            if method == "turn/start":
                await asyncio.Event().wait()
            return await original_request(method, params)

        self.session.request = hanging_turn
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            timeout_seconds=0.01,
        )
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(gateway.handle(message()), 1)
        self.assertIn(("close", {}), self.session.requests)

    async def test_stalled_completion_and_interrupt_close_session(self):
        original_request = self.session.request

        async def hanging_interrupt(method, params=None):
            if method == "turn/interrupt":
                await asyncio.Event().wait()
            return await original_request(method, params)

        async def no_notifications():
            await asyncio.Event().wait()

        self.session.request = hanging_interrupt
        self.session.next_notification = no_notifications
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            timeout_seconds=0.01,
        )
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(gateway.handle(message()), 1)
        self.assertIn(("close", {}), self.session.requests)


if __name__ == "__main__":
    unittest.main()

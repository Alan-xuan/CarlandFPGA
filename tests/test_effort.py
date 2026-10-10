import asyncio
import unittest

from fpga_mesh.effort import AstraEffortSelector
from fpga_mesh.rpc import JsonRpcNotification


class Session:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []
        self.interrupt_fails = False

    async def request(self, method, params):
        self.calls.append((method, params))
        if method == "thread/start":
            return {"thread": {"id": "selector-thread"}}
        if method == "turn/start":
            return {"turn": {"id": "selector-turn"}}
        if method == "turn/interrupt":
            if self.interrupt_fails:
                raise RuntimeError("interrupt unavailable")
            return {}
        raise AssertionError(method)

    async def next_notification(self):
        return JsonRpcNotification(method="turn/completed", params={
            "threadId": "selector-thread",
            "turn": {"id": "selector-turn", "status": "completed", "items": [
                {"type": "agentMessage", "phase": "final_answer",
                 "text": self.answer},
            ]},
        })


class Client:
    def __init__(self, answer):
        self.session = Session(answer)

    async def thread_start(self, **kwargs):
        return await self.session.request("thread/start", kwargs)

    async def turn_start(self, **kwargs):
        return await self.session.request("turn/start", kwargs)

    async def turn_interrupt(self, **kwargs):
        return await self.session.request("turn/interrupt", {
            "threadId": kwargs["thread_id"], "turnId": kwargs["turn_id"],
        })


class AstraEffortSelectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_decision_sets_next_work_turn_effort(self):
        client = Client('{"effort":"high"}')
        selector = AstraEffortSelector()
        chosen = await selector.choose(client, cwd="C:/project",
                                       model="gpt-6-astra", text="complex timing")
        self.assertEqual(chosen, "high")
        start = client.session.calls[0][1]
        turn = client.session.calls[1][1]
        self.assertTrue(start["ephemeral"])
        self.assertEqual(turn["effort"], "low")
        self.assertEqual(turn["output_schema"]["properties"]["effort"]["enum"],
                         ["low", "medium", "high", "xhigh", "max"])

    async def test_unclear_model_decision_fails_closed_to_max(self):
        client = Client('{"effort":"none"}')
        selector = AstraEffortSelector()
        chosen = await selector.choose(client, cwd="C:/project",
                                       model="gpt-6-astra", text="unclear task")
        self.assertEqual(chosen, "max")

    async def test_retryable_selector_error_preserves_the_model_decision(self):
        client = Client('{"effort":"high"}')
        notifications = [JsonRpcNotification(method="error", params={
            "threadId": "selector-thread", "turnId": "selector-turn",
            "error": {"message": "temporary stream interruption"},
            "willRetry": True,
        })]
        original_next = client.session.next_notification

        async def next_event():
            return notifications.pop(0) if notifications else await original_next()

        client.session.next_notification = next_event
        chosen = await AstraEffortSelector().choose(
            client, cwd="C:/project", model="gpt-6-astra", text="task",
        )
        self.assertEqual(chosen, "high")
        self.assertFalse(any(method == "turn/interrupt"
                             for method, _ in client.session.calls))

    async def test_foreign_selector_errors_do_not_trigger_max_fallback(self):
        client = Client('{"effort":"medium"}')
        notifications = [
            JsonRpcNotification(method="error", params={
                "threadId": "work-thread", "turnId": "selector-turn",
                "error": {"message": "work thread failed"}, "willRetry": False,
            }),
            JsonRpcNotification(method="error", params={
                "threadId": "selector-thread", "turnId": "old-selector-turn",
                "error": {"message": "previous selector failed"}, "willRetry": False,
            }),
        ]
        original_next = client.session.next_notification

        async def next_event():
            return notifications.pop(0) if notifications else await original_next()

        client.session.next_notification = next_event
        chosen = await AstraEffortSelector().choose(
            client, cwd="C:/project", model="gpt-6-astra", text="task",
        )
        self.assertEqual(chosen, "medium")

    async def test_foreign_or_unidentified_completion_is_not_selector_decision(self):
        client = Client('{"effort":"high"}')
        notifications = [
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "work-thread",
                "turn": {"id": "selector-turn", "status": "completed", "items": [
                    {"type": "agentMessage", "text": '{"effort":"low"}'},
                ]},
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "selector-thread",
                "turn": {"status": "completed", "items": [
                    {"type": "agentMessage", "text": '{"effort":"low"}'},
                ]},
            }),
        ]
        original_next = client.session.next_notification

        async def next_event():
            return notifications.pop(0) if notifications else await original_next()

        client.session.next_notification = next_event
        chosen = await AstraEffortSelector().choose(
            client, cwd="C:/project", model="gpt-6-astra", text="task",
        )
        self.assertEqual(chosen, "high")

    async def test_timeout_interrupts_selector_turn_before_fallback(self):
        client = Client('{"effort":"low"}')

        async def blocked():
            await asyncio.Event().wait()

        client.session.next_notification = blocked
        selector = AstraEffortSelector(timeout_seconds=0.01)
        chosen = await selector.choose(client, cwd="C:/project",
                                       model="gpt-6-astra", text="task")
        self.assertEqual(chosen, "max")
        self.assertIn(("turn/interrupt", {
            "threadId": "selector-thread", "turnId": "selector-turn",
        }), client.session.calls)

    async def test_unconfirmed_interrupt_blocks_parent_work(self):
        client = Client('{"effort":"low"}')
        client.session.interrupt_fails = True

        async def blocked():
            await asyncio.Event().wait()

        client.session.next_notification = blocked
        selector = AstraEffortSelector(timeout_seconds=0.01)
        with self.assertRaisesRegex(RuntimeError, "could not be interrupted"):
            await selector.choose(client, cwd="C:/project",
                                  model="gpt-6-astra", text="task")

    async def test_selector_start_without_response_does_not_start_parent_work(self):
        client = Client('{"effort":"low"}')
        original_request = client.session.request

        async def hanging_start(method, params):
            if method == "turn/start":
                await asyncio.Event().wait()
            return await original_request(method, params)

        client.session.request = hanging_start
        selector = AstraEffortSelector(timeout_seconds=0.01)
        with self.assertRaisesRegex(RuntimeError, "setup timed out"):
            await asyncio.wait_for(selector.choose(
                client, cwd="C:/project", model="gpt-6-astra", text="task",
            ), 1)


if __name__ == "__main__":
    unittest.main()

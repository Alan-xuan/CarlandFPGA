import tempfile
import unittest
from pathlib import Path

from fpga_mesh.mesh_tools import MeshDynamicTools
from fpga_mesh.store import SQLiteStore


class FakeChildTools:
    def specs(self):
        return [{"name": "fpga_child_status", "type": "function", "parameters": {}}]

    async def call(self, name, arguments):
        return {"child": name}


class FakeChildren:
    def job(self, job_id):
        return {
            "job_id": job_id, "status": "completed", "stale": False,
            "task_id": "task-1", "result": {"text": "child evidence"},
        }


class FakePeer:
    def __init__(self):
        self.sent = []

    async def send(self, peer_id, message):
        self.sent.append((peer_id, message))
        return False


class FakeFeishu:
    def __init__(self):
        self.wakes = 0
        self.deepseek_sender = object()

    def notify_report(self):
        self.wakes += 1


class MeshToolsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(Path(self.tmp.name) / "store.sqlite")
        self.peer = FakePeer()
        self.feishu = FakeFeishu()
        self.tools = MeshDynamicTools(
            node_id="A", project_id="fpga-main", child_tools=FakeChildTools(),
            children=FakeChildren(), store=self.store, peer=self.peer,
            feishu=self.feishu,
        )

    async def asyncTearDown(self):
        self.store.close()
        self.tmp.cleanup()

    async def test_astra_can_queue_group_report_and_offline_peer_message(self):
        names = {tool["name"] for tool in self.tools.specs()}
        self.assertIn("fpga_group_report", names)
        self.assertIn("fpga_peer_send", names)
        report = await self.tools.call("fpga_group_report", {
            "operation_id": "status-1", "text": "board test waiting",
        })
        self.assertTrue(report["queued"])
        self.assertEqual(self.store.pending_group_messages()[0][2], "astra")
        self.assertEqual(self.feishu.wakes, 1)
        sent = await self.tools.call("fpga_peer_send", {
            "peer_id": "B", "task_id": "task-1", "task_version": 2,
            "operation_id": "a-to-b-1", "text": "please review",
        })
        self.assertFalse(sent["delivered"])
        self.assertTrue(sent["queued"])
        self.assertEqual(self.peer.sent[0][1].recipient, "B/Astra-B")

    async def test_only_parent_requested_completed_child_result_uses_child_role(self):
        result = await self.tools.call("fpga_child_group_report", {
            "job_id": "child-1", "operation_id": "child-post-1",
        })
        self.assertTrue(result["queued"])
        self.assertEqual(self.store.pending_group_messages()[0][2], "deepseek")
        self.assertIn("child evidence", self.store.pending_group_messages()[0][1])

    async def test_child_role_rejects_stale_job(self):
        class StaleChildren(FakeChildren):
            def job(self, job_id):
                return {**super().job(job_id), "stale": True}
        self.tools.children = StaleChildren()
        with self.assertRaisesRegex(ValueError, "stale"):
            await self.tools.call("fpga_child_group_report", {
                "job_id": "old", "operation_id": "old-post",
            })
        self.assertEqual(self.store.pending_group_messages(), [])

    async def test_native_gpt_result_uses_astra_identity(self):
        class NativeChildren(FakeChildren):
            def job(self, job_id):
                return {**super().job(job_id), "route": "gpt_native"}
        self.tools.children = NativeChildren()
        self.feishu.deepseek_sender = None
        result = await self.tools.call("fpga_child_group_report", {
            "job_id": "native-1", "operation_id": "native-post-1",
        })
        self.assertEqual(result["role"], "astra")
        self.assertEqual(self.store.pending_group_messages()[0][2], "astra")
        self.assertIn("Astra-A", self.store.pending_group_messages()[0][1])

    async def test_child_group_report_requires_deepseek_sender(self):
        self.feishu.deepseek_sender = None
        with self.assertRaisesRegex(RuntimeError, "DeepSeek Feishu sender"):
            await self.tools.call("fpga_child_group_report", {
                "job_id": "child-1", "operation_id": "child-post-1",
            })
        self.assertEqual(self.store.pending_group_messages(), [])

    async def test_same_operation_id_to_two_peers_has_distinct_message_ids(self):
        for peer_id in ("B", "C"):
            await self.tools.call("fpga_peer_send", {
                "peer_id": peer_id, "task_id": "task-1", "task_version": 1,
                "operation_id": "shared-update", "text": "same update",
            })
        self.assertEqual(
            [message.message_id for _, message in self.peer.sent],
            ["B:shared-update", "C:shared-update"],
        )


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from fpga_mesh.runtime import NodeConfig, NodeRuntime
from fpga_mesh.child_control import LocalControlFileClient


class ProjectControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        config_path = Path(self.tmp.name) / 'node.toml'
        config_path.write_text('node_id="A"\nstate_dir="state"\nmode="test_double"\n', encoding='utf-8')
        self.runtime = NodeRuntime(NodeConfig.load(config_path))
        await self.runtime.start()
        self.client = LocalControlFileClient(Path(self.tmp.name) / 'state/main-control.json')

    async def asyncTearDown(self):
        await self.runtime.stop()
        self.tmp.cleanup()

    async def test_live_health_reports_no_preallocated_workers_or_secrets(self):
        health = await self.client.call('health', {})
        self.assertTrue(health['started'])
        self.assertEqual(health['pool']['instances'], [])
        self.assertEqual(health['identities'], {'main': 'Astra-A', 'deepseek': 'DeepSeek-A'})
        self.assertNotIn('token', str(health))

    async def test_task_submission_is_durable_idempotent_and_waits_for_actual_result(self):
        args = {'task_id': 'new-task', 'task_version': 1, 'text': 'work'}
        a = await self.client.call('main_submit', args)
        b = await self.client.call('main_submit', args)
        self.assertEqual(a['message_id'], b['message_id'])
        self.assertFalse(b['queued'])
        result = await self.client.call('main_wait', {'message_id': a['message_id'], 'timeout_seconds': 2})
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['result']['message_id'], a['message_id'])

    async def test_child_calls_through_same_front_door_use_one_coordinator(self):
        job = await self.client.call('delegate', {'task_id': 't', 'task_version': 1, 'text': 'bounded execution'})
        results = await self.client.call('wait', {'job_ids': [job['job_id']]})
        self.assertEqual(results[0]['status'], 'completed')
        self.assertEqual(len(self.runtime.children.status()['jobs']), 1)

    async def test_desktop_main_front_door_queues_reports_with_shared_astra_identity(self):
        class Feishu:
            def notify_report(self):
                pass
        self.runtime.mesh_tools.feishu=Feishu()
        result=await self.client.call('fpga_group_report',{'operation_id':'desktop-report','text':'verified main evidence'})
        self.assertTrue(result['queued'])
        self.assertEqual(self.runtime.store.pending_group_messages()[0][2],'astra')

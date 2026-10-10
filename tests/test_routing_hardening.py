import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
from fpga_mesh.child_control import ChildCoordinator
from fpga_mesh.pool import InstancePool
from fpga_mesh.codex import CodexHomeFactory
from fpga_mesh.store import SQLiteStore
from tests.test_sessions import Wire
from fpga_mesh.app_server import AppServerClient
from fpga_mesh.gateway import AppServerGateway, GatewayConfig


class HardenedRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.pool = InstancePool(node_id='A', home_factory=CodexHomeFactory(root/'homes'), state_path=root/'pool.json')
        self.children = ChildCoordinator(node_id='A', project_id='fpga-main', pool=self.pool, state_path=root/'jobs.sqlite')

    async def asyncTearDown(self):
        await self.children.close()
        await self.pool.close()
        self.tmp.cleanup()

    def native(self, task='t', work='w', ownership=None):
        return self.children.native_reserve(task_id=task, task_version=1, text='bounded native execution', work_id=work, ownership=ownership, reason='native route acceptance')

    async def test_superseded_native_lease_cannot_execute_or_publish_completion(self):
        job = self.native()
        self.children.native_validate(job_id=job['job_id'], lease_token=job['lease_token'], agent_id='agent')
        self.children.update_task_version('t', 2)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.children.native_validate(job_id=job['job_id'], lease_token=job['lease_token'], agent_id='agent')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.children.native_complete(job_id=job['job_id'], lease_token=job['lease_token'], text='late result')

    async def test_unconfirmed_native_cancel_keeps_file_ownership(self):
        job = self.native(ownership=['rtl/shared.v'])
        self.children.native_validate(job_id=job['job_id'], lease_token=job['lease_token'], agent_id='agent')
        await self.children.cancel(job['job_id'])
        with self.assertRaisesRegex(ValueError, 'ownership conflict'):
            self.native(task='other', ownership=['rtl/shared.v'])

    async def test_native_work_cannot_complete_before_execution_validation(self):
        job = self.native()
        with self.assertRaisesRegex(ValueError, 'validate'):
            self.children.native_complete(job_id=job['job_id'], lease_token=job['lease_token'], text='unvalidated work')

    async def test_validation_without_an_agent_id_is_only_a_preflight(self):
        job = self.native()
        check = self.children.native_validate(job_id=job['job_id'], lease_token=job['lease_token'])
        self.assertEqual(check['status'], 'reserved')
        self.assertFalse(check['execution_allowed'])

    async def test_windows_file_ownership_is_case_insensitive(self):
        with patch('fpga_mesh.child_control.os.name', 'nt'):
            self.native(ownership=['RTL/Shared.v'])
            with self.assertRaisesRegex(ValueError, 'ownership conflict'):
                self.native(task='other', ownership=['rtl/shared.V'])

    async def test_parallel_client_initialization_uses_one_connection(self):
        class YieldingWire(Wire):
            async def request(self, method, params=None):
                if method == 'initialize':
                    await asyncio.sleep(.01)
                return await super().request(method, params)
        wire = YieldingWire()
        client = AppServerClient(wire, client_version='test')
        gateway = AppServerGateway(GatewayConfig(node_id='A', role='astra', model='gpt-6-astra', provider='openai', reasoning_effort='max', cwd='.', codex_home=self.tmp.name), client_factory=lambda: client)
        try:
            await asyncio.gather(gateway._ensure_client(), gateway._ensure_client())
            self.assertEqual(len([r for r in wire.requests if r[0] == 'initialize']), 1)
        finally:
            await gateway.close()

    async def test_equal_clock_group_reports_keep_insertion_order(self):
        store = SQLiteStore(Path(self.tmp.name)/'messages.sqlite')
        try:
            with patch('fpga_mesh.store._utc_now', return_value=datetime(2026,10,10,tzinfo=timezone.utc)):
                store.enqueue_group_report('z-first', 'online')
                store.enqueue_group_report('a-second', 'offline')
            self.assertEqual([m[1] for m in store.pending_group_reports()], ['online','offline'])
            self.assertEqual([m[1] for m in store.pending_group_messages()], ['online','offline'])
        finally:
            store.close()

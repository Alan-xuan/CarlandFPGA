"""Task isolation, quality guard and durable routing against a protocol boundary."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fpga_mesh.app_server import AppServerClient
from fpga_mesh.gateway import AppServerGateway, GatewayConfig
from fpga_mesh.protocol import Envelope, MessageKind, SourceKind
from fpga_mesh.rpc import JsonRpcNotification


class Wire:
    def __init__(self):
        self.requests = []
        self.queue = asyncio.Queue()
        self.sequence = 0

    async def request(self, method, params=None):
        p = params or {}
        self.requests.append((method, p))
        if method == 'model/list':
            return {'data': [
                {'model': 'gpt-6-astra', 'supportedReasoningEfforts': [{'reasoningEffort': v} for v in ['low', 'high', 'max', 'ultra']]},
                {'model': 'gpt-6-luna', 'supportedReasoningEfforts': [{'reasoningEffort': v} for v in ['low', 'high']]},
                {'model': 'gpt-6.1-sol', 'supportedReasoningEfforts': [{'reasoningEffort': v} for v in ['low', 'high', 'max']]},
            ]}
        if method == 'thread/start':
            self.sequence += 1
            return {'thread': {'id': f'thread-{self.sequence}'}}
        if method == 'thread/resume':
            return {'thread': {'id': p['threadId']}}
        if method == 'turn/start':
            tid = f'turn-{len(self.requests)}'
            await self.queue.put(JsonRpcNotification(method='turn/completed', params={
                'threadId': p['threadId'], 'turn': {'id': tid, 'status': 'completed',
                    'items': [{'type': 'agentMessage', 'phase': 'final_answer', 'text': 'OK'}]},
            }))
            return {'turn': {'id': tid}}
        return {}

    async def notify(self, *args):
        pass

    async def next_notification(self):
        return await self.queue.get()

    async def close(self):
        pass


def event(task, text='Reply exactly OK.', category=None):
    payload = {'text': text}
    if category:
        payload['category'] = category
    return Envelope(message_id=f'{task}-{text}', project_id='fpga-main', sender='human', recipient='A/Astra-A', task_id=task, task_version=1, sent_at=datetime.now(timezone.utc), kind=MessageKind.HUMAN_INSTRUCTION, source=SourceKind.HUMAN, payload=payload)


class SessionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from fpga_mesh.sessions import MainSessionRouter
        self.tmp = tempfile.TemporaryDirectory()
        self.router = MainSessionRouter(Path(self.tmp.name) / 'sessions.sqlite')
        self.wire = Wire()
        self.client = AppServerClient(self.wire, client_version='test')
        self.gateway = AppServerGateway(GatewayConfig(node_id='A', role='astra', model='gpt-6-astra', provider='openai', reasoning_effort='max', cwd=str(Path.cwd()), codex_home=self.tmp.name), client_factory=lambda: self.client, session_router=self.router)

    async def asyncTearDown(self):
        if hasattr(self, 'gateway'):
            await self.gateway.close()
            self.router.close()
            self.tmp.cleanup()

    async def test_independent_tasks_get_distinct_threads_and_followup_reuses(self):
        a = await self.gateway.handle(event('a'))
        b = await self.gateway.handle(event('b'))
        again = await self.gateway.handle(event('a', 'Reply exactly AGAIN.'))
        self.assertNotEqual(a.output['thread_id'], b.output['thread_id'])
        self.assertEqual(a.output['thread_id'], again.output['thread_id'])

    async def test_critical_work_upgrades_even_when_a_low_model_was_requested(self):
        await self.gateway.handle(event('a'))
        await self.router.schedule_route(self.client, task_id='a', model='gpt-6-luna', effort='low', category='execution')
        result = await self.gateway.handle(event('a', '验收 CDC 关键优化并评估质量', 'acceptance'))
        self.assertEqual(result.output['model'], 'gpt-6-astra')
        self.assertEqual(result.output['reasoning_effort'], 'ultra')

    async def test_current_session_changes_model_and_depth_on_next_turn(self):
        a = await self.gateway.handle(event('a'))
        await self.router.schedule_route(self.client, task_id='a', model='gpt-6.1-sol', effort='high', category='execution')
        b = await self.gateway.handle(event('a', 'Reply exactly B.'))
        self.assertEqual(b.output['thread_id'], a.output['thread_id'])
        self.assertEqual((b.output['model'], b.output['reasoning_effort']), ('gpt-6.1-sol', 'high'))

    async def test_invalid_route_and_downgrading_critical_work_are_rejected(self):
        await self.gateway.handle(event('a'))
        for model, effort, category in [('deepseek-flash', 'max', 'execution'), ('gpt-6-luna', 'max', 'execution'), ('gpt-6-luna', 'low', 'decision')]:
            with self.assertRaises(ValueError):
                await self.router.schedule_route(self.client, task_id='a', model=model, effort=effort, category=category)

    async def test_restart_resumes_the_persisted_thread_and_completed_event_is_not_replayed(self):
        a = await self.gateway.handle(event('a'))
        turns = len([x for x in self.wire.requests if x[0] == 'turn/start'])
        same = await self.gateway.handle(event('a'))
        self.assertEqual(same.output['thread_id'], a.output['thread_id'])
        self.assertEqual(turns, len([x for x in self.wire.requests if x[0] == 'turn/start']))
        await self.gateway.close()
        self.router.reset_connection()
        self.wire = Wire()
        self.client = AppServerClient(self.wire, client_version='test')
        self.gateway.client_factory = lambda: self.client
        b = await self.gateway.handle(event('a', 'Reply exactly RESUMED.'))
        self.assertEqual(a.output['thread_id'], b.output['thread_id'])
        self.assertIn('thread/resume', [x[0] for x in self.wire.requests])

    async def test_new_session_tool_persists_allowed_route_without_starting_a_model(self):
        result = await self.router.open_session(self.client, task_id='child-task', task_version=1, text='Bounded execution', cwd=str(Path.cwd()), model='gpt-6.1-sol', effort='high', category='execution')
        self.assertEqual(result['model'], 'gpt-6.1-sol')
        self.assertFalse(any(x[0] == 'turn/start' for x in self.wire.requests))

    async def test_explicit_new_session_execution_route_is_used_by_first_task(self):
        await self.router.open_session(self.client, task_id='child-task', task_version=1, text='Run the bounded formatting operation', cwd=str(Path.cwd()), model='gpt-6.1-sol', effort='high', category='execution')
        result = await self.gateway.handle(event('child-task', 'Run the bounded formatting operation'))
        self.assertEqual((result.output['model'], result.output['reasoning_effort']), ('gpt-6.1-sol', 'high'))

    async def test_failed_turn_start_wakes_waiters_with_a_terminal_result(self):
        original = self.wire.request
        async def request(method, params=None):
            if method == 'turn/start':
                raise RuntimeError('start failed')
            return await original(method, params)
        self.wire.request = request
        work = event('start-failure')
        with self.assertRaisesRegex(RuntimeError, 'start failed'):
            await self.gateway.handle(work)
        self.assertEqual(self.router.result(work.message_id)['status'], 'failed')

    async def test_terminal_failed_notification_is_saved_as_failure(self):
        original = self.wire.request
        async def request(method, params=None):
            result = await original(method, params)
            if method == 'turn/start':
                notification = await self.wire.queue.get()
                notification.params['turn']['status'] = 'failed'
                notification.params['turn']['error'] = {'message': 'server failed'}
                await self.wire.queue.put(notification)
            return result
        self.wire.request = request
        work = event('end-failure')
        with self.assertRaisesRegex(RuntimeError, 'server failed'):
            await self.gateway.handle(work)
        self.assertEqual(self.router.result(work.message_id)['status'], 'failed')

    async def test_persisted_failed_or_interrupted_work_never_reopens_a_client(self):
        for status in ('failed', 'interrupted'):
            work = event(status)
            self.router.record(work.message_id, work.task_id, status, error='original failure')
            result = await self.gateway.handle(work)
            self.assertFalse(result.accepted)
            self.assertTrue(result.output['recovery_required'])
            self.assertEqual(self.router.result(work.message_id)['error'], 'original failure')
        self.assertEqual(self.wire.requests, [])
        from dataclasses import replace
        recovery = replace(event('failed'), task_version=2, message_id='failed-explicit-v2')
        self.assertTrue((await self.gateway.handle(recovery)).accepted)
        self.assertEqual(self.router.result(event('failed').message_id)['error'], 'original failure')

    async def test_failed_real_turn_is_retired_from_inbox_with_original_evidence_preserved(self):
        from fpga_mesh.runtime import NodeConfig, NodeRuntime
        runtime = NodeRuntime(NodeConfig(
            node_id='A', project_id='fpga-main', state_dir=Path(self.tmp.name) / 'runtime',
            mode='test_double', hardware_enabled=False, peer_urls={}, shared_secret_env='TEST_MESH_SECRET',
        ))
        runtime.astra_gateway = AppServerGateway(self.gateway.config,
            client_factory=lambda: self.client, session_router=runtime.main_sessions)
        runtime.controller.gateway = runtime.astra_gateway
        original = self.wire.request
        async def request(method, params=None):
            result = await original(method, params)
            if method == 'turn/start':
                notification = await self.wire.queue.get()
                notification.params['turn']['status'] = 'failed'
                notification.params['turn']['error'] = {'message': 'original provider failure'}
                await self.wire.queue.put(notification)
            return result
        self.wire.request = request
        work = event('provider-failure')
        try:
            await runtime.controller.offer(work)
            await runtime.controller.run_until_idle()
            before = runtime.main_sessions.result(work.message_id)
            runtime.store.mark_inbound_failed(work.message_id, 'original provider failure',
                                              retry_at=datetime.now(timezone.utc))
            requests = len(self.wire.requests)
            await runtime.controller.run_until_idle()
            self.assertEqual(len(self.wire.requests), requests)
            self.assertEqual(runtime.main_sessions.result(work.message_id), before)
            self.assertEqual(runtime.store.pending_inbound(), [])
        finally:
            await runtime.stop()

    async def test_duplicate_submit_cannot_change_the_next_turn_route(self):
        from types import SimpleNamespace
        from fpga_mesh.project_control import ProjectActions
        await self.gateway.handle(event('duplicate'))
        args={'task_id':'duplicate','task_version':1,'text':'Reply exactly DONE.'}
        runtime=SimpleNamespace(main_sessions=self.router,astra_gateway=self.gateway)
        class Inbox:
            async def offer(self, message):
                return False
        runtime.controller=Inbox()
        runtime.config=SimpleNamespace(node_id='A',project_id='fpga-main',state_dir=Path(self.tmp.name))
        actions=ProjectActions(runtime)
        submitted=await actions.call('main_submit',args)
        self.router.record(submitted['message_id'],'duplicate','completed',result={'text':'DONE'})
        await actions.call('main_submit',{**args,'model':'gpt-6.1-sol','effort':'high'})
        self.assertIsNone(self.router.db.execute("SELECT pending_json FROM main_sessions WHERE task_id='duplicate'").fetchone()[0])


if __name__ == '__main__':
    unittest.main()

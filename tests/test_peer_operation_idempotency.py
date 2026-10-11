import asyncio
import concurrent.futures
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fpga_mesh.mesh_tools import MeshDynamicTools
from fpga_mesh.protocol import Envelope
from fpga_mesh.store import SQLiteStore


class ChildTools:
    def specs(self):
        return []


class RecordingPeer:
    def __init__(self, store):
        self.store = store
        self.sent = []

    async def send(self, peer_id, message):
        self.store.enqueue_outbound(message, peer_id)
        self.sent.append(message.to_json())
        return False


def tools(store, peer=None):
    return MeshDynamicTools(node_id='A', project_id='fpga-main',
        child_tools=ChildTools(), children=None, store=store, peer=peer,
        feishu=None)


REQUEST = dict(peer_id='B', task_id='task-1', task_version=1,
               operation_id='operation-1', text='bounded read-only task')


class PeerOperationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'store.sqlite'
        self.store = SQLiteStore(self.path)

    async def asyncTearDown(self):
        self.store.close()
        self.tmp.cleanup()

    async def test_offline_repeat_reuses_original_wire_payload(self):
        peer = RecordingPeer(self.store)
        adapter = tools(self.store, peer)
        first = await adapter.call('fpga_peer_send', REQUEST)
        original = self.store.pending_outbound()[0].message.to_json()
        second = await adapter.call('fpga_peer_send', REQUEST)
        self.assertTrue(first['queued'] and second['queued'])
        self.assertEqual(len(self.store.pending_outbound()), 1)
        self.assertEqual(self.store.pending_outbound()[0].message.to_json(), original)
        self.assertEqual(peer.sent, [original, original])

    async def test_acked_repeat_does_not_call_transport(self):
        peer = RecordingPeer(self.store)
        adapter = tools(self.store, peer)
        await adapter.call('fpga_peer_send', REQUEST)
        self.store.ack_outbound('B:operation-1')
        original = peer.sent[0]
        second = await adapter.call('fpga_peer_send', REQUEST)
        self.assertTrue(second['delivered'])
        self.assertFalse(second['queued'])
        self.assertEqual(peer.sent, [original])
        self.assertEqual(self.store.pending_outbound(), [])

    async def test_material_changes_rejected_without_mutating_original(self):
        adapter = tools(self.store)
        await adapter.call('fpga_peer_send', REQUEST)
        original = self.store.pending_outbound()[0].message.to_json()
        for fields in ({'task_id':'other'}, {'task_version':2}, {'text':'other'}):
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(ValueError, 'different content'):
                    await adapter.call('fpga_peer_send', {**REQUEST, **fields})
                self.assertEqual(self.store.pending_outbound()[0].message.to_json(), original)

    async def test_restart_preserves_original_envelope(self):
        await tools(self.store).call('fpga_peer_send', REQUEST)
        original = self.store.pending_outbound()[0].message.to_json()
        self.store.close()
        self.store = SQLiteStore(self.path)
        result = await tools(self.store).call('fpga_peer_send', REQUEST)
        self.assertTrue(result['queued'])
        self.assertEqual(len(self.store.pending_outbound()), 1)
        self.assertEqual(self.store.pending_outbound()[0].message.to_json(), original)

    async def test_concurrent_connections_reuse_one_record(self):
        def submit(_):
            store = SQLiteStore(self.path)
            try:
                return asyncio.run(tools(store).call('fpga_peer_send', REQUEST))
            finally:
                store.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(submit, range(8)))
        self.assertTrue(all(r['queued'] for r in results))
        self.assertEqual(len(self.store.pending_outbound()), 1)

    async def test_generic_enqueue_keeps_strict_timestamp_comparison(self):
        await tools(self.store).call('fpga_peer_send', REQUEST)
        original = self.store.pending_outbound()[0].message
        fields = json.loads(original.to_json())
        fields['sent_at'] = (original.sent_at + timedelta(seconds=1)).isoformat()
        changed = Envelope.from_json(json.dumps(fields))
        with self.assertRaisesRegex(ValueError, 'different content'):
            self.store.enqueue_outbound(changed, 'B')

    async def test_sender_identity_change_rejected(self):
        await tools(self.store).call('fpga_peer_send', REQUEST)
        adapter = tools(self.store)
        adapter.node_id = 'C'
        with self.assertRaisesRegex(ValueError, 'different content'):
            await adapter.call('fpga_peer_send', REQUEST)

    async def test_same_operation_to_two_peers_keeps_distinct_records(self):
        adapter = tools(self.store)
        for peer_id in ('B', 'C'):
            await adapter.call('fpga_peer_send', {**REQUEST, 'peer_id':peer_id})
        self.assertEqual({i.message.message_id for i in self.store.pending_outbound()},
                         {'B:operation-1', 'C:operation-1'})

    async def test_generic_platform_dedupe_collision_still_returns_false(self):
        await tools(self.store).call('fpga_peer_send', REQUEST)
        fields = json.loads(self.store.pending_outbound()[0].message.to_json())
        fields.update(message_id='generic-1', platform_group_id='group',
                      platform_message_id='platform-message')
        self.assertTrue(self.store.enqueue_outbound(Envelope.from_json(json.dumps(fields)), 'B'))
        fields['message_id'] = 'generic-2'
        self.assertFalse(self.store.enqueue_outbound(Envelope.from_json(json.dumps(fields)), 'B'))


if __name__ == '__main__':
    unittest.main()

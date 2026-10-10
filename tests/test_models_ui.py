import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from fpga_mesh.models_ui import ModelsHttpServer


class ModelsUITests(unittest.IsolatedAsyncioTestCase):
    async def test_external_sites_cannot_trigger_update_but_local_button_can(self):
        class Actions:
            def __init__(self):
                self.calls = []
            async def call(self, action, args):
                self.calls.append(action)
                return {'provider': 'openai', 'models': {}, 'roles': {}}
        with tempfile.TemporaryDirectory() as tmp:
            actions = Actions()
            server = ModelsHttpServer(actions, discovery_path=Path(tmp) / 'ui.json')
            await server.start()
            async def call(origin, token):
                reader, writer = await asyncio.open_connection('127.0.0.1', int(server.host.split(':')[1]))
                headers = f'POST /update HTTP/1.1\r\nHost: {server.host}\r\nOrigin: {origin}\r\nX-Model-Update: {token}\r\nContent-Length: 0\r\n\r\n'
                writer.write(headers.encode())
                await writer.drain()
                response = await reader.read()
                writer.close()
                await writer.wait_closed()
                return response
            try:
                self.assertIn(b'403', await call('https://external.example', server.token))
                self.assertIn(b'403', await call(server.url, 'wrong-token'))
                self.assertFalse(actions.calls)
                self.assertIn(b'200', await call(server.url, server.token))
                self.assertEqual(actions.calls, ['models_refresh'])
                self.assertEqual(json.loads((Path(tmp) / 'ui.json').read_text())['url'], server.url)
            finally:
                await server.close()

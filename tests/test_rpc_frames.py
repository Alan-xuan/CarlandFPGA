import sys
import unittest
from fpga_mesh.rpc import StdioTransport


class LargeFrameTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_subprocess_json_frame_larger_than_64k_is_read_intact(self):
        transport = StdioTransport([sys.executable, '-c', "print('x' * 180000, flush=True)"])
        await transport.start()
        try:
            line = await transport.recv()
            self.assertEqual(len(line), 180000)
            self.assertEqual(set(line), {'x'})
        finally:
            await transport.close()

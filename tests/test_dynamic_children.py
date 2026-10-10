import unittest

from fpga_mesh.dynamic_children import ChildDynamicTools


class Client:
    def __init__(self):
        self.calls = []

    async def call(self, action, arguments):
        self.calls.append((action, arguments))
        return {"ok": True}


class ChildDynamicToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_route_tools_map_to_one_local_controller(self):
        client = Client()
        bridge = ChildDynamicTools(client)
        names = {tool["name"] for tool in bridge.specs()}
        self.assertEqual(names, {
            "fpga_child_status", "fpga_child_scale", "fpga_child_delegate",
            "fpga_child_wait", "fpga_child_cancel",
            "fpga_native_reserve", "fpga_native_validate", "fpga_native_complete",
        })
        self.assertEqual(await bridge.call("fpga_child_delegate", {
            "task_id": "t", "task_version": 1, "text": "inspect",
        }), {"ok": True})
        self.assertEqual(client.calls[0][0], "delegate")
        with self.assertRaises(ValueError):
            await bridge.call("fpga_child_unknown", {})


if __name__ == "__main__":
    unittest.main()

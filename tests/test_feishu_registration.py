import json
import tempfile
import unittest
from pathlib import Path

from fpga_mesh.feishu_registration import registration_addons, register_role


class FeishuRegistrationTests(unittest.TestCase):
    def test_astra_receives_group_events_but_deepseek_has_no_subscription(self):
        astra = registration_addons("astra")
        child = registration_addons("deepseek")
        self.assertEqual(
            astra["events"]["items"]["tenant"], ["im.message.receive_v1"],
        )
        self.assertNotIn("events", child)
        self.assertIn("im:message:send_as_bot", child["scopes"]["tenant"])

    def test_only_astra_requests_file_scope_without_expanding_child_permissions(self):
        self.assertEqual(set(registration_addons("astra")["scopes"]["tenant"]), {
            "im:message:send_as_bot", "im:message", "im:message.group_msg", "im:resource",
        })
        self.assertEqual(set(registration_addons("deepseek")["scopes"]["tenant"]), {
            "im:message:send_as_bot", "im:message:readonly", "im:message.group_msg",
        })

    def test_registration_writes_only_local_secret_and_nonsecret_manifest(self):
        calls = []
        def fake_register(**kwargs):
            calls.append(kwargs)
            kwargs["on_qr_code"]({"url": "https://accounts.feishu.cn/verify", "expire_in": 300})
            return {"client_id": "cli_role_a", "client_secret": "secret-value"}

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            info = register_role(
                node="A", role="astra", output_dir=output,
                register_fn=fake_register,
            )
            self.assertEqual(info["app_id"], "cli_role_a")
            self.assertNotIn("secret-value", json.dumps(info))
            self.assertEqual((output / "astra-secret.txt").read_text(), "secret-value")
            manifest = json.loads((output / "astra.json").read_text())
            self.assertEqual(manifest["app_id"], "cli_role_a")
            self.assertNotIn("secret-value", json.dumps(manifest))
            self.assertFalse(calls[0]["addons"]["preset"])


if __name__ == "__main__":
    unittest.main()

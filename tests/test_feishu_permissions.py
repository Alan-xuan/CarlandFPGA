import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fpga_mesh.feishu_permissions import check_file_scope
from fpga_mesh.feishu_selftest import FeishuSelfTestAPI
from fpga_mesh.runtime import NodeConfig


class FeishuPermissionTests(unittest.TestCase):
    def config(self, directory):
        path = Path(directory) / 'node.toml'
        path.write_text('node_id="B"\nstate_dir="state"\n[feishu]\n'
                        'enabled=true\ngroup_id="oc_team"\nastra_app_id="cli_astra_b"\n'
                        'astra_secret_file="existing.txt"\n', encoding='utf-8')
        (Path(directory) / 'existing.txt').write_text('local-secret', encoding='utf-8')
        return NodeConfig.load(path)

    def test_scope_audit_uses_existing_astra_only_and_does_not_grant_or_send(self):
        with tempfile.TemporaryDirectory() as directory:
            api = FeishuSelfTestAPI()
            rows = {'data': {'scopes': [
                {'scope_name': 'im:resource', 'scope_type': 'tenant', 'grant_status': 1},
            ]}}
            with patch.object(api, 'access_token', return_value='local-token') as auth, \
                    patch.object(api, '_request', return_value=rows) as request:
                result = check_file_scope(self.config(directory), api=api)
            auth.assert_called_once_with('cli_astra_b', 'local-secret')
            request.assert_called_once_with('GET', '/application/v6/scopes', token='local-token')
            self.assertEqual(result['status'], 'ready')
            self.assertNotIn('local-secret', json.dumps(result))
            self.assertNotIn('local-token', json.dumps(result))

    def test_ungranted_or_user_token_scopes_do_not_claim_file_access(self):
        with tempfile.TemporaryDirectory() as directory:
            api = FeishuSelfTestAPI()
            rows = {'data': {'scopes': [
                {'scope_name': 'im:resource', 'scope_type': 'tenant', 'grant_status': 0},
                {'scope_name': 'im:resource', 'scope_type': 'user', 'grant_status': 1},
            ]}}
            with patch.object(api, 'access_token', return_value='local-token'), \
                    patch.object(api, '_request', return_value=rows):
                result = check_file_scope(self.config(directory), api=api)
            self.assertEqual(result['status'], 'needs_admin_grant')
            self.assertEqual(result['manage_url'], 'https://open.feishu.cn/app/cli_astra_b/auth')

    def test_disabled_feishu_does_not_attempt_auth_or_read_any_secret(self):
        config = NodeConfig(node_id='C', project_id='p', state_dir=Path('state'),
                            mode='test_double', hardware_enabled=False,
                            peer_urls={}, shared_secret_env='TEST_MESH_SECRET')
        with patch.object(FeishuSelfTestAPI, 'access_token') as auth:
            self.assertEqual(check_file_scope(config)['status'], 'disabled')
        auth.assert_not_called()

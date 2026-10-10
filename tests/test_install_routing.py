import tempfile
import tomllib
import unittest
from pathlib import Path


class InstallRoutingTests(unittest.TestCase):
    def test_local_bridge_preserves_settings_and_installs_native_lease_policy(self):
        from fpga_mesh.install_routing import install
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / '.codex/config.toml'
            existing.parent.mkdir()
            existing.write_text('model="gpt-6.1-sol"\n', encoding='utf-8')
            control = root / 'main-control.json'
            install(root, python='python.exe', control_file=control)
            install(root, python='python.exe', control_file=control)
            result = tomllib.loads(existing.read_text(encoding='utf-8'))
            self.assertEqual(result['model'], 'gpt-6.1-sol')
            self.assertEqual(result['mcp_servers']['fpga_mesh']['args'], ['-m', 'fpga_mesh.project_mcp'])
            self.assertEqual(result['mcp_servers']['fpga_mesh']['env']['FPGA_MAIN_CONTROL_FILE'], str(control))
            self.assertNotIn('max_threads', result.get('agents', {}))
            self.assertTrue((root / '.codex/agents/worker.toml').is_file())

import sys
import tempfile
import unittest
from pathlib import Path
from fpga_mesh.service import service_output


class ServiceLoggingTests(unittest.TestCase):
    def test_background_unicode_logs_remove_connection_credentials_and_restore_streams(self):
        original = sys.stdout
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'service.log'
            synthetic_key = 'sk-' + 'A' * 32
            with service_output(path):
                print('连接成功 wss://example.org/ws?access_key=private&ticket=private')
                print(synthetic_key)
            self.assertIs(sys.stdout, original)
            text = path.read_text(encoding='utf-8')
            self.assertIn('连接成功', text)
            self.assertNotIn('private', text)
            self.assertNotIn(synthetic_key, text)
            self.assertIn('[redacted]', text)

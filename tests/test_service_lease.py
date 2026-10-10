import tempfile
import unittest
from pathlib import Path


class ServiceLeaseTests(unittest.TestCase):
    def test_second_process_owner_is_rejected_and_release_allows_restart(self):
        from fpga_mesh.service import ServiceLease
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'resident.lock'
            with ServiceLease(path):
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    with ServiceLease(path):
                        self.fail('duplicate owner acquired the node')
            with ServiceLease(path):
                self.assertTrue(path.exists())

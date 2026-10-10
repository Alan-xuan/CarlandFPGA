import tempfile
import unittest
from pathlib import Path
from fpga_mesh.service import ServiceLease


class ServiceRestartTests(unittest.TestCase):
    def test_restart_waits_for_both_resident_and_supervisor_leases_to_release(self):
        from fpga_mesh.service import wait_stopped
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in ('supervisor.lock', 'resident.lock'):
                with ServiceLease(directory / name):
                    with self.assertRaisesRegex(TimeoutError, 'still stopping'):
                        wait_stopped(directory, timeout=0.05)
                wait_stopped(directory, timeout=0.2)

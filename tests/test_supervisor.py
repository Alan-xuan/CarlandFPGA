import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from fpga_mesh.supervisor import Supervisor


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_worker_crash_restarts_and_cancellation_stops_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            worker=root/'worker.py'
            worker.write_text('import pathlib,sys,time\np=pathlib.Path(sys.argv[1])\nn=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\nif n==1: sys.exit(9)\ntime.sleep(30)\n',encoding='utf-8')
            runner=Supervisor([sys.executable,str(worker),str(root/'starts')],state_file=root/'state.json',restart_seconds=.05)
            task=asyncio.create_task(runner.run())
            try:
                for _ in range(100):
                    if task.done():
                        await task
                    if (root/'starts').exists() and (root/'starts').read_text()=='2':
                        break
                    await asyncio.sleep(.05)
                else:
                    self.fail('the crashed worker was not restarted')
                state=json.loads((root/'state.json').read_text(encoding='utf-8'))
                self.assertEqual(state['restarts'],1)
                self.assertIsNone(runner.process.poll())
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertIsNotNone(runner.process.poll())

    @unittest.skipUnless(os.name == 'nt', 'Windows job ownership check')
    async def test_restart_kills_previous_workers_grandchild_before_new_worker(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            worker = root / 'worker.py'
            worker.write_text(
                'import pathlib,subprocess,sys,time\n'
                'p=pathlib.Path(sys.argv[1])\n'
                'if not p.exists():\n'
                ' child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],creationflags=0x08000000)\n'
                ' p.write_text(str(child.pid))\n'
                ' sys.exit(9)\n'
                '(p.parent/"restarted").write_text("ready")\n'
                'time.sleep(30)\n', encoding='utf-8')
            runner = Supervisor([sys.executable, str(worker), str(root / 'child-pid')],
                                state_file=root / 'state.json', restart_seconds=.05)
            task = asyncio.create_task(runner.run())
            try:
                for _ in range(100):
                    if task.done():
                        await task
                    if (root / 'restarted').exists():
                        break
                    await asyncio.sleep(.05)
                else:
                    self.fail('the replacement worker did not start')
                child_pid = int((root / 'child-pid').read_text())
                handle = kernel.OpenProcess(0x00100000, False, child_pid)  # SYNCHRONIZE
                if handle:
                    try:
                        self.assertEqual(kernel.WaitForSingleObject(handle, 1000), 0,
                                         'old worker descendant survived the restart')
                    finally:
                        kernel.CloseHandle(handle)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

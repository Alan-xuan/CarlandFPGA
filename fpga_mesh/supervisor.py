"""Resident worker supervision without any model requests during recovery."""
import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path
from .service import ServiceLease,service_output


class Supervisor:
    def __init__(self,command,*,state_file,restart_seconds=1):
        self.command=list(command)
        self.state_file=Path(state_file)
        self.restart_seconds=restart_seconds
        self.process=None
        self.restarts=0

    def record(self,**values):
        data={'supervisor_pid':os.getpid(),'worker_pid':self.process.pid if self.process else None,
            'restarts':self.restarts,'updated_at':datetime.now(timezone.utc).isoformat(),**values}
        self.state_file.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.state_file.with_suffix('.tmp')
        temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
        os.replace(temporary,self.state_file)

    async def run(self):
        job=None
        try:
            while True:
                if os.name=='nt':
                    from .windows_job import WindowsJob
                    job=WindowsJob()
                flags=(0x08000000|0x00000004) if job else 0  # NO_WINDOW | SUSPENDED
                self.process=subprocess.Popen(self.command,stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags,
                    env={**os.environ,'PYTHONUTF8':'1'})
                if job:
                    job.attach_and_resume(self.process)
                self.record(status='running')
                code=await asyncio.to_thread(self.process.wait)
                if job:
                    job.close()
                    job=None
                self.restarts+=1
                self.record(status='restarting',last_exit_code=code)
                print(json.dumps({'event':'worker_exited','exit_code':code,'restarts':self.restarts}),flush=True)
                await asyncio.sleep(min(30,self.restart_seconds*self.restarts))
        finally:
            if job:
                job.close()  # Kernel stops the complete owned process tree.
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(asyncio.to_thread(self.process.wait),timeout=10)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await asyncio.to_thread(self.process.wait)
            self.record(status='stopped')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--ready-file',type=Path,required=True)
    parser.add_argument('--log-file',type=Path,required=True)
    args=parser.parse_args()
    from .runtime import NodeConfig
    config=NodeConfig.load(args.config)
    command=[sys.executable,'-m','fpga_mesh.cli','serve','--config',str(args.config.resolve()),
        '--ready-file',str(args.ready_file.resolve()),'--log-file',str(args.log_file.resolve())]
    with ServiceLease(config.state_dir/'supervisor.lock'),service_output(args.log_file):
        asyncio.run(Supervisor(command,state_file=args.config.parent/'supervisor.json').run())


if __name__=='__main__':
    main()

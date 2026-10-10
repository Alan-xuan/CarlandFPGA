"""Operating-system lease preventing two services from recovering one ledger."""
import os
import re
import sys
from contextlib import contextmanager
from contextlib import ExitStack
from pathlib import Path


class RedactingStream:
    """UTF-8 service sink that removes connection query credentials."""
    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        safe = re.sub(r'(wss?://[^\s?]+)\?[^\s]+', r'\1?[redacted]', text)
        safe = re.sub(r'\bsk-[A-Za-z0-9_-]{12,}\b', '[redacted]', safe)
        self.stream.write(safe)
        self.stream.flush()
        return len(text)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


@contextmanager
def service_output(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    old_stdout, old_stderr = sys.stdout, sys.stderr
    with path.open('a', encoding='utf-8', buffering=1) as stream:
        sys.stdout = sys.stderr = RedactingStream(stream)
        try:
            yield
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr


class ServiceLease:
    def __init__(self, path):
        self.path = Path(path)
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open('a+b')
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise RuntimeError('FPGA node service is already running') from exc
        self.file = stream
        return self

    def __exit__(self, *args):
        if self.file:
            self.file.close()
            self.file = None


def wait_stopped(state_dir, *, timeout=20):
    """Do not race a scheduled restart against the old process-tree cleanup."""
    import time
    directory = Path(state_dir)
    deadline = time.monotonic() + timeout
    while True:
        try:
            with ExitStack() as stack:
                for name in ('supervisor.lock', 'resident.lock'):
                    stack.enter_context(ServiceLease(directory / name))
                return
        except RuntimeError as exc:
            if str(exc) != 'FPGA node service is already running':
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Previous FPGA service is still stopping; do not start a duplicate') from exc
            time.sleep(min(0.1, remaining))


def main():
    import argparse
    from .runtime import NodeConfig
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait-stopped', action='store_true', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=20)
    args = parser.parse_args()
    wait_stopped(NodeConfig.load(args.config).state_dir, timeout=args.timeout)
    print('Previous supervisor and resident leases are released.')


if __name__ == '__main__':
    main()

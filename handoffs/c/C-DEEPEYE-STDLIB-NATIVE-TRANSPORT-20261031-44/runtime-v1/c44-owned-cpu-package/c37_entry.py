"""Finite live inherited-handle entry v2; no original actor/SDK imports."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def load_package():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'package-manifest.json').read_text(encoding='utf-8'))
    names = {'c37_entry.py', 'c37_package.py', 'frozen_c28.py'}
    if type(manifest) is not dict or set(manifest) != {'schema_version', 'files'} or manifest['schema_version'] != 1:
        raise ValueError('invalid package manifest')
    if type(manifest['files']) is not dict or set(manifest['files']) != names:
        raise ValueError('fixed package paths required')
    for name in names:
        path = root / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest['files'][name]:
            raise ValueError('package hash mismatch')
    spec = importlib.util.spec_from_file_location('_c37_fixed_package', root / 'c37_package.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def serve(transport, request_bytes, max_invocations, package):
    """Serial finite computation; owner alone retires the live initialized child.

    The host must not pipeline. This loop never reads the next request until the
    prior pair is fully written; after K it does not read or infer again.
    """
    if type(max_invocations) is not int or not 1 <= max_invocations <= 16:
        raise ValueError('prospective invocation count must be 1..16')
    if type(request_bytes) is not int or request_bytes != 16384:
        raise ValueError('fixed total request must be 16384')
    previous = None
    try:
        transport.signal_ready()
        for _ in range(max_invocations):
            chunks, remaining = [], request_bytes
            while remaining:
                data = transport.read(min(8192, remaining))
                if type(data) is not bytes or not 0 < len(data) <= min(8192, remaining):
                    raise ValueError('short/invalid request stream')
                chunks.append(data)
                remaining -= len(data)
            wire = b''.join(chunks)
            identity = package.request_identity(wire)
            if previous is not None:
                if (identity['invocation_id'] != previous['invocation_id'] + 1
                    or any(identity[k] != previous[k] for k in identity if k != 'invocation_id')):
                    raise ValueError('serial identity mismatch')
            output = package.process_wire(wire)
            for offset in range(0, len(output), 8192):
                chunk = output[offset:offset + 8192]
                count = transport.write(chunk)
                if type(count) is not int or count != len(chunk):
                    raise ValueError('short output; no remainder or replay')
            previous = identity
        # No pipe read, output, clock sample, inference, or normal exit after K.
        # The original owner must enforce its already fixed bounded lifetime.
        transport.wait_for_owner_teardown()
        raise RuntimeError('owner teardown wait returned unexpectedly')
    finally:
        transport.close()


class NativeSetupFailure(Exception):
    """Fixed local diagnostic only; no handle values or arbitrary error text."""
    def __init__(self, close_available, attempted, failed):
        super().__init__('native setup failed')
        self.close_available = close_available
        self.close_attempted = tuple(attempted)
        self.close_failed = tuple(failed)


class HandleCloseFailure(Exception):
    pass


def _get_winapi():
    import _winapi
    return _winapi


def _get_set_event():
    from _overlapped import SetEvent
    return SetEvent


def _new_wait_event():
    from threading import Event
    return Event()


class NativeTransport:
    """One-use inherited handles. Original owner retains custody and lifetime."""
    def __init__(self, ready, input_handle, output_handle):
        self._handles = (ready, input_handle, output_handle)
        self._closed = False
        self._ready_attempted = False
        self._ready = False
        self._wait_started = False
        self._close_handle = None
        self.close_attempted = []
        self.close_failed = []
        try:
            if sys.platform != 'win32' or any(type(h) is not int or not 0 < h < (1 << 64) - 1 for h in self._handles) or len(set(self._handles)) != 3:
                raise ValueError('three distinct Windows handles required')
            self._api = _get_winapi()
            self._close_handle = self._api.CloseHandle
            self._set_event = _get_set_event()
            # Initialized before readiness/inference; never set or timed here.
            self._owner_wait = _new_wait_event()
        except Exception:
            available = self._close_handle is not None
            if available:
                try:
                    self.close()
                except HandleCloseFailure:
                    pass
            else:
                self._closed = True
            raise NativeSetupFailure(available, self.close_attempted, self.close_failed) from None

    def _live(self):
        if self._closed or self._wait_started:
            raise RuntimeError('transport already retired')

    def signal_ready(self):
        self._live()
        if self._ready_attempted:
            raise RuntimeError('readiness already attempted')
        self._ready_attempted = True
        if self._set_event(self._handles[0]) is not None:
            raise OSError('invalid readiness result')
        self._ready = True

    def read(self, size):
        self._live()
        if not self._ready or type(size) is not int or not 1 <= size <= 8192:
            raise ValueError('read state/chunk budget')
        result = self._api.ReadFile(self._handles[1], size, overlapped=False)
        if (type(result) is not tuple or len(result) != 2
            or type(result[0]) is not bytes or not 0 < len(result[0]) <= size
            or type(result[1]) is not int or result[1] != 0):
            raise OSError('invalid synchronous read result')
        # Positive partial byte-stream reads remain legal, as in C40.
        return result[0]

    def write(self, raw):
        self._live()
        if not self._ready or type(raw) is not bytes or not 1 <= len(raw) <= 8192:
            raise ValueError('write state/chunk budget')
        result = self._api.WriteFile(self._handles[2], raw, overlapped=False)
        if (type(result) is not tuple or len(result) != 2
            or type(result[0]) is not int or result[0] != len(raw)
            or type(result[1]) is not int or result[1] != 0):
            raise OSError('short/invalid synchronous write result; no retry')
        return result[0]

    def wait_for_owner_teardown(self):
        self._live()
        if not self._ready:
            raise RuntimeError('readiness required')
        self._wait_started = True
        self._owner_wait.wait()
        raise RuntimeError('owner teardown wait returned unexpectedly')

    def close(self):
        if self._closed:
            return
        self._closed = True
        for slot, handle in enumerate(self._handles):
            self.close_attempted.append(slot)
            try:
                if self._close_handle(handle) is not None:
                    raise OSError('invalid close result')
            except Exception:
                self.close_failed.append(slot)
        if self.close_failed:
            raise HandleCloseFailure('inherited handle close failed; no retry')


def main(argv):
    # Original ActorOwner appends the final three native handle strings.
    if len(argv) != 8 or argv[0:2] != ['--actor-stdio-v2', '--max-invocations'] or argv[3] != '--request-bytes':
        return 64
    try:
        values = [int(argv[i]) for i in (2, 4, 5, 6, 7)]
        if any(str(value) != argv[index] for value, index in zip(values, (2, 4, 5, 6, 7))):
            return 64
        count, size, ready, inp, out = values
        if not 1 <= count <= 16 or size != 16384 or len({ready, inp, out}) != 3:
            return 64
        if not all(0 < handle < (1 << 64) - 1 for handle in (ready, inp, out)):
            return 64
    except Exception:
        return 64
    try:
        package = load_package()
    except Exception:
        return 70
    try:
        transport = NativeTransport(ready, inp, out)
    except NativeSetupFailure as error:
        # 71: all three closes attempted and succeeded; 74: no close API;
        # 75: all attempted, at least one failed. OS exit is final cleanup.
        return (71 if not error.close_failed else 75) if error.close_available else 74
    except Exception:
        return 74
    try:
        serve(transport, size, count, package)
        return 72  # A returning serve is not a successful live child.
    except HandleCloseFailure:
        return 73
    except Exception:
        return 72


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

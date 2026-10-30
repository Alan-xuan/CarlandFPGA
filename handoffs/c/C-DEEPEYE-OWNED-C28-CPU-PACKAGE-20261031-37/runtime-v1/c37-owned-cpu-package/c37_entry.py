"""Single inherited-handle child entry; no original actor/SDK imports."""
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
    """Injectable byte transport for NEW offline tests, never host provenance."""
    if type(max_invocations) is not int or max_invocations != 1:
        raise ValueError('original host supports one invocation only')
    if type(request_bytes) is not int or not 5 <= request_bytes <= 16384:
        raise ValueError('exact request byte count required')
    try:
        transport.signal_ready()
        chunks, remaining = [], request_bytes
        while remaining:
            data = transport.read(min(8192, remaining))
            if type(data) is not bytes or not 0 < len(data) <= min(8192, remaining):
                raise ValueError('short/invalid request stream')
            chunks.append(data)
            remaining -= len(data)
        output = package.process_wire(b''.join(chunks))
        for offset in range(0, len(output), 8192):
            chunk = output[offset:offset + 8192]
            count = transport.write(chunk)
            if type(count) is not int or count != len(chunk):
                raise ValueError('short output; no remainder or replay')
    finally:
        transport.close()


class NativeTransport:
    """Only inherited child synchronous handles; original parent owns custody."""
    def __init__(self, ready, input_handle, output_handle):
        import ctypes as c
        from ctypes import wintypes as w
        if sys.platform != 'win32':
            raise ValueError('Windows child handles required')
        self._c, self._w = c, w
        self._handles = (ready, input_handle, output_handle)
        self._closed = False
        self._api = c.WinDLL('kernel32.dll', use_last_error=True)
        self._api.ReadFile.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, c.POINTER(w.DWORD), w.LPVOID]
        self._api.ReadFile.restype = w.BOOL
        self._api.WriteFile.argtypes = [w.HANDLE, w.LPCVOID, w.DWORD, c.POINTER(w.DWORD), w.LPVOID]
        self._api.WriteFile.restype = w.BOOL
        self._api.SetEvent.argtypes = [w.HANDLE]; self._api.SetEvent.restype = w.BOOL
        self._api.CloseHandle.argtypes = [w.HANDLE]; self._api.CloseHandle.restype = w.BOOL

    def signal_ready(self):
        if not self._api.SetEvent(self._handles[0]):
            raise OSError('readiness event failed')

    def read(self, size):
        if type(size) is not int or not 1 <= size <= 8192:
            raise ValueError('read chunk budget')
        buffer = self._c.create_string_buffer(size)
        count = self._w.DWORD()
        if not self._api.ReadFile(self._handles[1], buffer, size, self._c.byref(count), None):
            if self._c.get_last_error() == 109:
                return b''
            raise OSError('input read failed')
        if count.value > size:
            raise OSError('invalid read count')
        return buffer.raw[:count.value]

    def write(self, raw):
        if type(raw) is not bytes or not 1 <= len(raw) <= 8192:
            raise ValueError('write chunk budget')
        buffer = self._c.create_string_buffer(raw, len(raw))
        count = self._w.DWORD()
        if not self._api.WriteFile(self._handles[2], buffer, len(raw), self._c.byref(count), None):
            raise OSError('output write failed')
        return count.value

    def close(self):
        if self._closed:
            return
        self._closed = True
        failed = False
        for handle in self._handles:
            if not self._api.CloseHandle(handle):
                failed = True
        if failed:
            raise OSError('inherited handle close failed')


def main(argv):
    # Original ActorOwner appends the final three native handle strings.
    if len(argv) != 8 or argv[0:2] != ['--actor-stdio-v1', '--max-invocations'] or argv[3] != '--request-bytes':
        return 64
    try:
        values = [int(argv[i]) for i in (2, 4, 5, 6, 7)]
        if any(str(value) != argv[index] for value, index in zip(values, (2, 4, 5, 6, 7))):
            return 64
        count, size, ready, inp, out = values
        if count != 1 or not 5 <= size <= 16384 or len({ready, inp, out}) != 3:
            return 64
        if not all(0 < handle < (1 << 64) - 1 for handle in (ready, inp, out)):
            return 64
        package = load_package()
        transport = NativeTransport(ready, inp, out)
        serve(transport, size, count, package)
        return 0
    except Exception:
        # No arbitrary exception text, native handle or traceback on either pipe.
        return 65


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

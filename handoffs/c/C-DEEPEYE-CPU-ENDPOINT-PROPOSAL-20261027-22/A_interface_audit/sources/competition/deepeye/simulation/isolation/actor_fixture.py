"""Cooperative CPU lifecycle fixture; no model, authentication or native probes.

The launcher appends exactly its inherited input/output endpoints. Native import
and endpoint access occur only in main(), never on offline test import.
"""
READY = b'DEEPEYE-ACTOR/1 READY\n'
EXIT = b'X'
MAX_OUTPUT = 256


def decode_command(raw):
    if type(raw) is not bytes or raw != EXIT:
        raise ValueError('only one exact EXIT byte X is accepted')
    return 'exit'


def validate_mode(mode, delay_ms):
    if type(mode) is not str or type(delay_ms) is not int:
        raise ValueError('strict mode and integer delay required')
    if mode == 'natural' and 1 <= delay_ms <= 10000:
        return mode, delay_ms
    if mode in ('wait','exit') and delay_ms == 0:
        return mode, delay_ms
    raise ValueError('fixed finite natural delay or explicit wait/exit mode required')


class ReadyBuffer:
    def __init__(self): self.raw = b''

    def feed(self, raw):
        if type(raw) is not bytes or len(self.raw)+len(raw)>MAX_OUTPUT:
            raise ValueError('bounded bytes required')
        self.raw += raw
        if not READY.startswith(self.raw):
            raise ValueError('unexpected fixture bytes')
        return self.raw == READY


def main(argv=None):
    import sys
    import time
    import _winapi as kernel
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 4: raise ValueError('mode delay input output required')
    mode, delay = validate_mode(args[0], int(args[1]))
    endpoints = tuple(int(x) for x in args[2:])
    if any(x<=0 for x in endpoints) or endpoints[0]==endpoints[1]:
        raise ValueError('two distinct inherited endpoints required')
    count, error = kernel.WriteFile(endpoints[1], READY)
    if type(count) is not int or count != len(READY) or error:
        raise OSError('incomplete READY output')
    if mode == 'natural':
        time.sleep(delay/1000)
        return
    raw, error = kernel.ReadFile(endpoints[0], 1)
    if error: raise OSError('fixture input failed')
    decode_command(raw)
    if mode == 'wait':
        # Parent never sends in this mode; a misplaced command is a failure.
        raise ValueError('wait fixture must be retired by original owner')


if __name__ == '__main__': main()

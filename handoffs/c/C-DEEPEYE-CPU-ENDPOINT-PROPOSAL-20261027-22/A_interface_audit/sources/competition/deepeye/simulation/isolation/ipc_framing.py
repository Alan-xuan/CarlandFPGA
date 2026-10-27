"""Inactive DEEPEYE-PRIVATE-FRAMES/1 codec for bounded, untrusted bytes.

No source, clock, completion or execution authority is created here. Future
original endpoints must explicitly adopt this format before it can be used.
"""

MAX_PAYLOAD = 16384
MAX_CHUNK = 8192
MAX_FRAMES_PER_FEED = 4


def encode_frame(payload: bytes) -> bytes:
    """Encode one opaque payload; accept exact bytes only."""
    if type(payload) is not bytes or not 1 <= len(payload) <= MAX_PAYLOAD:
        raise ValueError('payload must be exact bytes with length 1..16384')
    return len(payload).to_bytes(4, 'little') + payload


class FrameDecoder:
    """One stream, one bounded partial frame, irreversible close or refusal.

    A failed feed returns no frames from that call. Frames returned by earlier
    successful calls remain the caller's responsibility. Instances have a
    single owner; this class does not serialize concurrent calls.
    """

    __slots__ = ('_buffer', '_payload_size', '_closed')

    def __init__(self):
        self._buffer = bytearray()
        self._payload_size = None
        self._closed = False

    def _require_open(self):
        if self._closed:
            raise ValueError('frame stream is closed or retired')

    def _retire(self):
        self._closed = True
        self._buffer.clear()
        self._payload_size = None

    def _refuse(self, message):
        self._retire()
        raise ValueError(message)

    def feed(self, chunk: bytes) -> tuple[bytes, ...]:
        """Consume up to 8192 bytes and return at most four opaque frames.

        Empty input is neither EOF nor a liveness observation. There is no
        resynchronization after malformed or excessive input.
        """
        self._require_open()
        if type(chunk) is not bytes or len(chunk) > MAX_CHUNK:
            self._refuse('chunk must be exact bytes with length 0..8192')
        frames = []
        offset = 0
        while offset < len(chunk):
            target = 4 if self._payload_size is None else self._payload_size
            take = min(target - len(self._buffer), len(chunk) - offset)
            self._buffer.extend(chunk[offset:offset + take])
            offset += take
            if len(self._buffer) != target:
                break
            if self._payload_size is None:
                size = int.from_bytes(self._buffer, 'little')
                self._buffer.clear()
                if not 1 <= size <= MAX_PAYLOAD:
                    self._refuse('frame length must be 1..16384')
                self._payload_size = size
            else:
                if len(frames) == MAX_FRAMES_PER_FEED:
                    self._refuse('more than four completed frames in one feed')
                frames.append(bytes(self._buffer))
                self._buffer.clear()
                self._payload_size = None
        return tuple(frames)

    def finish(self) -> None:
        """Close on an explicitly observed EOF; refuse a truncated frame."""
        self._require_open()
        if self._buffer or self._payload_size is not None:
            self._refuse('truncated frame at EOF')
        self._retire()

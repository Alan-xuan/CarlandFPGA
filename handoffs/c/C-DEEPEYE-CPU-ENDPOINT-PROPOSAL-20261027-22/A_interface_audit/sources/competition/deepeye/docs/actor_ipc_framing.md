# Bounded private byte framing

`simulation/isolation/ipc_framing.py` provides an inactive stream codec for
`DEEPEYE-PRIVATE-FRAMES/1`. Each frame is a four-byte unsigned little-endian
length followed by 1–16384 opaque bytes. The future original endpoints must
explicitly agree to this version; it is not the public ABI3, the existing
READY/EXIT fixture protocol, or an adopted C inference format.

`encode_frame(payload)` accepts exact `bytes` and returns one encoded frame.
One `FrameDecoder` belongs to one stream and one serialized owner.
`feed(chunk)` accepts exact `bytes` of length 0–8192 and returns a tuple of at
most four complete immutable payloads, preserving byte order. Headers and
payloads may cross any chunk boundary. Binary zeroes, newlines and other bytes
are allowed; this layer performs no content/schema validation.

Only one partial header or payload is retained. Its logical buffer length is
at most 16384 bytes (at most four while reading a header). Temporary input
slices are at most 8192 bytes, and returned payload storage is bounded by
4 × 16384 bytes. Python allocation overhead is additional to these byte counts.
The implementation checks chunk type/size before appending and never buffers
an unbounded stream or invokes a callback.

Invalid input type, excessive chunk size, invalid frame length, or a fifth
completed frame in one call raises `ValueError`, clears the partial buffer and
permanently retires the decoder. That failing call returns no payload tuple,
including any complete frames preceding the error in that same call. Frames
returned on previous successful calls cannot be recalled; a future provider
must retire its own epoch on framing failure. There is no reset, silent drop,
automatic retry or resynchronization. Four complete frames plus a partial next
frame are allowed; the partial frame may complete in a later call.

`feed(b'')` returns an empty tuple and makes no EOF or health claim. A transport
must explicitly call `finish()` on actual EOF. EOF between frames closes the
decoder; a partial header/payload raises `ValueError` and retires it. Every
`feed` or `finish` after close or refusal raises `ValueError`.

This module has no imports or I/O and returns bytes only. It creates no actor
identity, authenticated endpoint, BOOT binding, timestamp, observation,
completed inference or motion permission. Production channels and Run remain
unchanged. Persistent native I/O, cancellation, original dispatch identity,
measured clocks, approved model/broker code, board observations and both H12
routes still need their own integration and evidence.

The focused tests are `tests/simulation/test_ipc_framing.py`. They check the new
stream contract, not existing native pipe, model, board or whole R03 behavior.
H01–H15 remain unchanged.

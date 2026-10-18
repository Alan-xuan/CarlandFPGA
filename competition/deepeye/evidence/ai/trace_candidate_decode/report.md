# Independent C offline TRACE candidate decode

Completed under `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`C-independent-trace-candidate-decoder-20261018-v1`, actual native agent
`/root/trace_decoder`. The persisted parent assignment is
`watch-20261018/trace-decoder-assignment.json`. All writes are under
`competition/deepeye/evidence/ai/trace_candidate_decode/`; no production, schema,
RTL, existing test, service, credential, SQL or board file was changed. No
network send, commit, push, peer or group action was performed.

Input PR30 head: `781be78d9da77a75ea711cf690eeea6523733d3a`.
Operation: `B-DEEPEYE-TRACE-CANDIDATE-20261017-05`.
Request SHA256: `abe52729c5bb46944ec8c55dd92481af9362b4d5a92b0bdefd13d1061038de4a`.
Local base: `cdbb6b4daef1ae1df324accd4d5086b48d005c6b`.
Frozen design: `1011259415a0916054eb580687612580bc1e5f09`.
Human lock: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, H01-H15 requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
The scope verifier passed; this establishes requirement identity only.

`candidate_decode.py` implements an independent exact-bytes payload/frame
parser, bit-serial CCITT-FALSE CRC, strict metadata and canonical RAW/Rice
checks, and a pure candidate receiver. It was written from the five copied
normative/opaque input files. B's `trace_candidate.py`, `codec_reference.py`,
encoder/decoder tests and review scripts were never opened, imported or run.
The read-only B review report was consulted only for input SHA pins. There is
no candidate encoder or production integration in this experiment.

`replay.py` independently derives reconstructed expected values, mode/k/bit
costs and longest legal prefix sizes from the original synthetic source
points. It does not encode bytes or call the decoder's canonicality helper.
The decoder's re-encoding-like local predicate is used only to enforce
canonical bytes after parsing, as expressly permitted by the candidate prose.
The pinned restored values and ledgers are also compared, but are not the
sole acceptance oracle. `independent_expected.json` saves the source-derived
values and full per-block cost expectations. No B roundtrip oracle is used.

Final replay: **81 case groups passed**, exit 0:

- 8 hand-derived manual vectors and 32 synthetic streams: 126 frames,
  1,046 points, including 908 valid values and 138 quality-only invalid points.
- 23 malformed payloads and 11 malformed frames rejected. Every case also
  leaves receiver state unchanged and accepts a valid higher-sequence next
  frame. Independent error wording need not match B's prose strings.
- Source index, full uint64 acquisition tick, source-update origin, validity,
  saturation, held and source-fault masks agree exactly; no point is invented,
  dropped, reordered or renumbered. Each valid block anchor is exact and each
  valid point's absolute error is at most E. The all-E fixture errors are
  respectively 0, 0, 2, 3 and 8 for E=0,1,2,4,8.
- The 16-packet cache, duplicate zero-point/no-renewal response, sequence
  conflicts, stale eviction, future sequence gaps, four independent channel
  high waters, both index and tick order, failed-accept atomicity, sequence
  65535/no wrap, terminal idempotent close, copied binding and detached output
  and snapshots are exercised.
- Independent literal expectations confirm TC01 k1/26bits and k3/28bits,
  stored-byte RAW ties, equal-value Rice and the 41-point/32-byte boundary.
  Additional cases reject 12 explicitly constructed malformed payloads,
  all 37 truncated prefixes of a 37-byte valid frame, one trailing frame byte,
  and all 296 single-bit corruptions of that frame. Two cases specifically
  reject impossible endpoint clamping residuals.
- 11 exact-type/bounds tests reject subclasses, bool integers, nonbytes,
  noncanonical E, extra keys and out-of-range bindings before user operators.
- The two opaque packer cases are checked by independent exhaustive legal
  prefix sizing. The capacity fixture requires 30 frames and has capacity
  for 6; no-wrap incompatibility is established arithmetically. There is no
  encoder API here, so this does not claim to test an encoder's partial-output
  behavior.

Aggregate positive-fixture accounting (overlapping fixture families are
intentionally counted as individual replay cases):

| Quantity | Count |
|---|---:|
| Selected original valid RAW bytes | 1,816 |
| Significant code bits | 4,044 |
| Stored code bytes | 534 |
| Zero padding bits | 228 |
| Metadata bytes | 3,048 |
| Payload bytes | 3,582 |
| Outer framing/CRC bytes | 1,764 |
| Total frame bytes | 5,346 |
| 8N1 line bits (10 per frame byte) | 53,460 |

These numbers expose metadata/framing expansion. They do not establish a
compression ratio for real sources, bitrate, latency, slot legality,
continuous sampling, a scheduling budget, or an actual transport result.

Seven exact input copies and their source-byte equality, length, SHA256 and Git
blob SHA1 are recorded in `input_manifest.json`. Four externally documented
SHA pins (layout, vectors, manual vectors and spec) were verified. Both
installed client role records are version `2026.10.15.1`; existing deployment
configuration identified node C. The preflight result is discovery only:
ModelSim was found, Vivado was not found, and board status is `not_checked`.
No FPGA tool or physical board test was run.

Raw stdout/stderr bytes, command arrays, cwd, timestamps, exit codes and source
hashes are in `captures/`. The initial `replay-01` exited 1 because the harness
compared numeric max error 0 to a pinned null summary for a mixed valid/invalid
stream. The underlying per-valid-point checks passed. The harness now compares
that optional summary only when supplied; it always independently checks every
valid point's E bound. This failed run is preserved. `replay-02` and
`replay-03` passed; the final replay adds the independent adversarial cases.

Portable peer reproduction from a checkout root using Python 3.10 or later:

```text
python -B -X utf8 competition/deepeye/evidence/ai/trace_candidate_decode/provenance.py --check-only
python -B -X utf8 competition/deepeye/evidence/ai/trace_candidate_decode/replay.py
```

The copied fixtures plus `candidate_decode.py` and `replay.py` are standalone:
`python -B -X utf8 replay.py` can be run from any cwd. `provenance.py` additionally
verifies copied pins, the human lock and import boundary using only its own
inputs by default. Its optional `--source-root <deployment-root>` checks exact
copy equality against the author's assigned originals. `capture.py` is an
author-side raw evidence helper whose root inference intentionally matches this
deployment layout; peers do not need it, installed skills or any private
`.local` tree. No controller, authentication or network dependency is used.

This is offline candidate compatibility evidence only. All input samples are
opaque synthetic software fixtures; no source clock, BOOT/full digest trust,
session uniqueness, authoritative retirement, calibration, physical units,
four-channel real-source simultaneity, runtime scheduling, observation lease,
motion authority or live AI feed is verified. The receiver can test explicit
closure and a new expected binding but cannot prove an authoritative handshake.
No normative ambiguity blocked the available decoder subset. All A approval
gates remain open; production type7 stays rejected and was not enabled or
modified here. Production rejection was not separately rerun by this worker.
No H01-H15 runtime acceptance, B01, R03, source acceptance, board acceptance,
or whole-system acceptance is claimed. The parent independently reviews and
decides how to use this isolated experiment.

# Independent targeted TRACE candidate review

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work
`C-independent-trace-adversarial-review-20261018-v1`; reviewer
`/root/data_boundary_repair`. Writes are confined to this private review directory.
The C implementation remains owned by `/root/trace_decoder`.

Bounded conclusion: no defect found in the code inspection and targeted checks
below. The tested C candidate SHA256 is
`b02010280b72d3a94842db627f733df9c1fa6ecfe54f572509d57869d2d3d72c`.
`candidate_snapshot.py` preserves those exact reviewed bytes; `result.json`
records that the live C file retained the same hash across execution.

Only the C implementation and its five copied normative/raw inputs were read.
No B implementation, codec_reference.py, B review script or B roundtrip oracle
was opened or imported. Challenge payloads were constructed independently from
the written layout, quantizer equation, Rice bit rules and mode-selection rules.
The only candidate calls under test were its decode and receiver APIs.

## Actual results

Python 3.12.14; five unittest methods, exit 0, zero failures. Exact command,
timestamps, source/input hashes and raw-output hashes are in `result.json`;
raw stderr is `stderr.txt`, stdout is `stdout.txt` and counts are `metrics.json`.

- Independent canonical grid: 300 accepted examples across E=0/1/2/4/8,
  five anchor levels including uint16 endpoints and 12 residual patterns.
  The decoder agreed with independent restored values and E bounds in all
  cases: 46 RAW and 254 Rice. It rejected 154 crafted RAW encodings when Rice
  was strictly byte-better and 254 alternate nonoptimal Rice-k encodings.
- Explicit canonical boundaries: TC01 `[10000,10001,10002,10004]` selects k1,
  26 significant bits; `[0,8,16]` selects k3, 28 bits. Both stored-byte RAW tie
  examples `[0,64]` and `[0,2048,4096]` accept RAW and reject Rice. Nonzero
  padding and an impossible endpoint-clamping residual reject.
- Held metadata: ages 1 and 65535 use short form; 65536 uses long form;
  uint64 endpoint/origin cases retain exact source/acquisition ticks.
  A short-form block retains one origin even when a later point's age exceeds
  65535. Four zero/underflow short ages and four noncanonical/future long origins
  reject. Six positive and eight negative constructions passed.
- Acquisition/mask metadata: all four channels accept a quality-only 128-point
  block with sparse 65535 strides and exact invalid/fault masks, None values
  and None source ticks. Saturated nonendpoint values remain unchanged.
  Six positive and 21 negative progression/flag/length cases passed, including
  exact final uint32 index/uint64 tick bounds and overflow rejection.
- Eighteen receiver operations verified independent channel high waters,
  last-point rather than first-point water updates, strict index AND tick
  advance, invalid acquisitions advancing their channel water, old held origin
  remaining distinct from acquisition tick, uint32/uint64 acquisition nonwrap,
  low32 acquisition-tick rollover, unchanged state after each rejection and
  successful subsequent recovery with the rejected frame's sequence available.

The parent already separately covered CRC/cache/retirement behavior. Those
checks were not duplicated or counted here. The five raw input files include
8 manual, 32 synthetic, 23 malformed-payload and 11 malformed-frame fixtures;
this review did not rerun the worker's complete fixture replay or packer tests.
The tested standard-library CRC construction is only a way to build local
challenge frames; it is not a production transport implementation.

## Scope limits and immutable requirements

This is an offline software-candidate review, not a public ABI freeze,
production type7 enablement, source authentication, acquisition-clock proof,
physical-unit mapping, scheduling result, throughput/latency/compression claim,
runtime integration, R03/C01 acceptance, RTL result or board/system acceptance.
A alone owns the public ABI, clock/units/schedule decisions and physical board.
No C worker-owned file, production source, service, credentials, SQL state,
Git state or peer communication was changed.

H01-H15 remain unchanged under
`DEEPEYE-HUMAN-LOCK-20261014/revision1`; contract source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
was independently verified before execution. Frozen design:
`1011259415a0916054eb580687612580bc1e5f09`.

The final release and artifact hashes are in `release.json` and `manifest.json`.

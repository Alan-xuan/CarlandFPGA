# Synchronous causal FORCE stream core

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`C-CPU-CAUSAL-STREAM-CORE-20261025-v1`, operation
`C-DEEPEYE-CPU-STREAM-CORE-20261025-21`; source base
`e3f86f7301abef866c30de2ec851e4a939198381`. All H01-H15 remain under
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design remains `1011259415a0916054eb580687612580bc1e5f09`.

This new core makes the existing real learned FORCE CPU component callable one
causal observation at a time. It contains no observation-file argument,
iterator/suffix consumption, output path, transport, IPC/process, executor,
clock, verifier, broker, map/planner, scene or hardware access. Its C API format
has not been adopted as an A runtime/transport format. All values remain
non-authorizing: `movement_authorized` is a fixed false property; emitted result
JSON also contains `motion_bytes:null` and incomplete formal acceptance.

## Fixed component and call sequence

```python
from ai_pc.cpu_package.stream_core import FrozenForceStream

core = FrozenForceStream()
token = core.start_session(generation=1, epoch=0, run_id="my-public-replay")
result = core.observe(token, one_raw_json_record_bytes)
assert result.movement_authorized is False
assert core.latest_result(token) is result
receipt = core.end_session(token)
# Both local identifiers must increase; the same opaque label does not reuse state.
token2 = core.start_session(generation=2, epoch=1, run_id="my-public-replay")
```

The `ai_pc` import root is the checkout's `competition/deepeye` directory.
`FrozenForceStream` constructor accepts an optional exact native Path/string
pointing to the same frozen manifest bytes and an expected hash that must equal
`0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959`.
It checks the unchanged C19 runner (`92114790259b7e35e8bf7b1a0519f0e3f68da52729d08b5b9862c992deae70af`),
curve builder (`c017729a2d5717ff2bbf5a6c591320519c415ac10068b4cee19b3136913d848c`),
model source (`5003427e1ac01e50b612d8f4f9c674c7df352b3942a5cc39978e23bdfbdb1260`),
all graph/weight/label/scaler pins, and the original finite JSON model loader.
The model and frozen train-only scaler objects are instantiated once per core.
Constructor verification may read pinned asset bytes more than once; it does
not repeatedly instantiate or load a model for observations. After construction
the public session/observation/read methods perform no file reads.

Every new-core preflight has an explicit **2MiB per-read cap**: three source
files, the already bounded manifest, four referenced assets, and the separate
direct preprocessing read (nine actual calls, including both preprocessing
reads). The unchanged helper requests at most `cap+1` bytes and rejects length
above the cap before hashing or parsing. This bounds rejection of an enlarged
invalid asset as well as normal valid files. It is not a2MiB whole-process or
Torch workspace limit and does not modify the old runner, loader, frozen model
format, scaler or any original artifact.

Only `force_curve_v1` / `geo_replay` / **CPU** are supported. Explicit HIP or
another device is rejected, with no fallback. The core uses four torch CPU
threads, deterministic algorithms and inference/eval mode. It does not change
A's installed environment or establish compatibility with it. C controls used
existing CPython3.12.14/Torch2.9.0+cpu; no dependency install or NumPy was added.
Torch's actual NumPy-unavailable warning is preserved in raw evidence.

`sim_em_v2` returns blocked `sim_em_model_missing`. There is no alternate model,
input-selected code, weights provider, fake-logits mode, callback or result
injection argument. FORCE remains public lithology; it is not remapped to water,
obstacles, sensor_live or 3D truth.

## Local lifecycle identifiers

`generation` is an exact built-in integer in1..2^32-1. `epoch` is an exact
built-in integer in0..2^32-1. Both must increase **strictly** on every successful
start over this object's lifetime. Initial high-water sentinels are0 and-1.
There is no wrap or reuse; reaching the maximum cannot be recovered by wrapping.
Rejected start attempts do not advance high waters or consume transition counts.

A start is allowed only when inactive. An active session must be ended
explicitly before a new start. The returned `SessionToken` is a deeply immutable
tuple. Every observe/end/latest call requires **that exact active object by
identity**, not merely equal fields. Constructed, copied, `_replace`d, old,
foreign-core and inactive tokens are rejected. A label is an opaque binding,
never proof of freshness. End discards active window/hash/latest state; next
start is cold even with the same run label. Object-lifetime counters and high
waters survive end/start and cannot be reset by label reuse.

These identifiers/token are **only C in-process API bookkeeping**. They are not
A BOOT/run authorization, CONFIG epoch, observed_seq, capture proof, clock,
deadline, physical stop, grant, security principal or transport credential.
An end receipt is not an A STOP acknowledgement. Restarting a Python core does
not prove a new authorized A session; A/runtime must establish that separately.

## One raw record and bounded state

`observe(token, raw)` requires exact built-in immutable `bytes`, not a subclass,
bytearray, memoryview, iterator or arbitrary mapping. One JSON object is parsed;
unknown/duplicate fields, additional objects, invalid UTF-8/nonfinite JSON and
extra labels/confidence/coordinates/truth/timestamps are rejected. It must have
the unchanged thirteen `CurveObservation` fields:

`run_id, source_domain, profile_id, preprocessing_sha256, sequence,
value_0..value_3, valid_0..valid_3`.

The binding must exactly match explicit start and fixed preprocessing
`cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef`.
The sequence is the original exact uint64 acquisition index, not a derived wire
sequence or invented time. The unchanged builder preserves masks, missing
startup/gap slots, positive-RDEP policy, duplicate/regression rejection and
bounded huge-gap handling. At the uint64 maximum, an exact duplicate can still
be accepted within API budgets; a wrapped or regressed sequence cannot.

`StreamLimits` permits only reductions of these hard bounds:

| Limit | Meaning |
| --- | --- |
|16,384 bytes|Each supplied raw record|
|8,192 bytes|Each emitted result/end JSON; configurable minimum512bytes|
|128 UTF-8 bytes|Each opaque run binding label; other binding strings are fixed|
|65,536 deliveries|All accepted calls over the core object's lifetime|
|64MiB raw bytes|All accepted exact raw bytes over the core object's lifetime|
|1,024 starts /2,048 transitions|Object lifetime; start and end each count once|

Exact integer/bool/subclass checks apply. Limits are defensively copied from
the caller's frozen configuration. Per-session bytes/deliveries reset at start
but are bounded by the same surviving lifetime limits. All builder counters are
therefore bounded by accepted lifetime deliveries; rejected calls consume none.
Output/record reductions can intentionally block observation acceptance; the
minimum output size still accommodates the bounded end receipt.

Retained stream state consists of the fixed model/scaler/class/pin constants,
one bounded128-slot active builder, one incremental SHA object, bounded scalar
counters, the current token and only the latest result. There is no list of raw
records, result history or replay of the entire prefix. Model tensors are fixed
by the declared4916-parameter graph. Temporary trial/tensor/output state is also
bounded and discarded after the call. Caller retention of old returned values
does not become internal history.

## Atomic observation transaction and duplicate semantics

Every public session/state/read/observe method uses a local nonblocking lock.
It creates no thread or background work; a reentrant or concurrent call receives
`busy` instead of racing lifecycle changes. No user callback is invoked by the
production API while committing state.

For a candidate observation, the core shallow-copies the **pinned** builder and
copies its deque independently. All other retained builder fields are immutable
tuples/frozen objects or scalar counters. It applies the original builder to
this trial only, builds the tensor through the original C19 float32/shape/finite
checks, invokes the real stateless learned model, copies the prefix SHA and
prepares the deeply immutable result and bounded finite JSON. Only then does
one assignment replace the committed state while holding the lock.

Malformed input, binding conflict, old sequence, conflicting duplicate,
float32 overflow **after valid float64 normalization**, model/finite-output
failure, serialization/output bound failure or stale token cannot advance
window/history/counters/prefix/latest result. End likewise serializes its
bounded receipt before dropping the active session. Input-derived exception
detail is bounded to256characters; normal rejections use `StreamError(code,
detail,blocked=...)`. Public read methods return immutable values, not builder,
model, hash or mutable state aliases.

An exact current-sequence duplicate with equal values/flags retains original
builder idempotence: no new acquisition slot or observation is invented. The
**accepted delivery** still advances zero-based `delivery_index`, raw-byte
count and SHA of the concatenated accepted raw deliveries, including exact
whitespace/newline. The builder's idempotent-repeat count increases. The exact
previous probabilities and feature digest are reused because features did not
change; output serialization and every limit still happen before commit.
Rejected duplicate deliveries advance nothing.

Results contain the current original sequence, binding, cold/gap/mask metadata,
twelve finite probabilities and official class order/source code, actual
float32 little-endian C-order `[1,8,128,1]` tensor digest/encoding, exact raw
prefix digest, delivery index/bytes and all fixed model/source artifact pins.
All nested values are tuples, primitive immutable values or bytes; even
`object.__setattr__` cannot alter their tuple fields. `encoded` is bounded
canonical JSON plus one LF. No method accepts externally computed results to
overwrite latest; copying/replacing a returned result cannot install it.

## Actual scoped controls and remaining gates

Run only the new controls from checkout root:

```text
python -B -X utf8 competition/deepeye/tests/ai/cpu/test_stream_core.py -v
```

The first author run passed16new methods, zero skips, exit0. A subsequent narrow
change normalized unexpected end-receipt serialization exceptions into bounded
`StreamError`; only that affected end control was rerun on final source and
passed1method/exit0. The entire16-method run belongs to its preserved pre-change
snapshot, not a claimed full final-source rerun. Independent final-source review
is pending. No actual RED occurred or was fabricated in those author runs.

Subsequent independent Phase2 review found a genuine additional constructor
boundedness defect in source
`0ddbe6710be81df3e428f63809257dea69c35fee1aabd24cd9bb58eb71b41976`:
eight preflights lacked their own finite read caps, so the helper requested an
unbounded read before rejecting a wrong hash. The independent one-method RED
recorded `read_size=-1` and actual exit1, without loading a model or allocating a
large asset. That RED and the original author evidence/manifest remain immutable
historical evidence; the preceding no-RED statement refers only to the first
author16/end1 runs, not to this later independent finding.

Repair work `C-CPU-STREAM-BOUNDED-INIT-REPAIR-20261025-v1` supplies the explicit
2MiB caps described above. Its new constructor-only controls intercept actual
read requests at all nine positions and exercise each position's oversize,
short bad-SHA and missing-asset rejection before model loading. The oversize
control returns a synthetic length-only probe, with no oversized bytes, file
or model allocation; it verifies `cap+1` request/length rejection, not an actual
production oversized-file incident. One separate successful initialization and
one real learned observation cover the changed path. These controls neither
rerun the original16 nor repeat old suites or benchmarks. New repair evidence
is in `../../evidence/ai/cpu_stream_20261025/bounded-init-fix/`; it explicitly
distinguishes current source from historical `author/delivery-manifest.json`.

Controls include8new actual FORCE prefix calls and exact comparison of saved
C19 indices0/1/7 for probabilities/tensor/prefix/sequence/masks; the saved raw
baseline SHA is `e84bdfe850efb8a231f72c98a5fb05cc20c7f6036014f4db77ef3f6cf44b418f`.
They do not call old `execute`, its old suites, all128baseline inference or its
ten-repeat benchmark. Other controls cover load-once, prohibited observation
file reads, invalid future suffix independence, float32/model/serialization
failure atomicity including duplicates, masks/gaps/huge gaps/uint64, lifecycle
strictness/stale tokens, exact bytes and subclass bounds, immutable results,
lifetime caps across sessions, reentry and explicit profile/model refusal.
Private test failure injection only raises or wraps real functions; it adds no
public fake-model/logit mode and never supplies fake successful predictions.

The existing graph's held-out quality remains **FAIL**: macro-F1 about0.1827348,
below centroid0.2047005 and target0.60. No training, tuning or held-out evaluation
was repeated. Missing sim_em/scales, qualified causal sensing/mapping/planning,
A lifecycle/clock/runtime integration, both control paths, board work and every
unmet formal H01-H15/product gate remain incomplete. Model presence or this
software API is not substantive full-system AI benefit or formal acceptance.

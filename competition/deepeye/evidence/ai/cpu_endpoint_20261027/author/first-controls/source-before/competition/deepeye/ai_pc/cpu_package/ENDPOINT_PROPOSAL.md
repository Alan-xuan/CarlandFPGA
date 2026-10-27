# C22 private diagnostic endpoint proposal

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work
`C-ENDPOINT-AUTHOR-20261027-v1`, operation
`C-DEEPEYE-CPU-ENDPOINT-PROPOSAL-20261027-22`. This is source for A's review,
not an adopted A wire protocol, factory, launch stage, authority or completed
transport. Base: `b898e90c7248dec5a6dd0ee850c8a07e097e83aa`.
Main design v2 SHA256:
`437aedcf1f09f11109632f4f101a6851c07a2ba2a6f65939fe35cbf92540d07f`.

H01–H15 remain fixed under `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen product design is `1011259415a0916054eb580687612580bc1e5f09`.
Both H12 paths and every unmet formal acceptance item remain incomplete.
Only A operates the physical board.

## Private byte format

`endpoint_protocol.py` is a stdlib-only codec. A frame begins with exactly
16 bytes `struct.Struct('>4sBBHII')`: ASCII `C22E`, version 1, kind, zero
reserved flags, unsigned big-endian metadata length, unsigned big-endian
payload length. Input OBSERVE=1 and END=2; output RESULT=129 and ENDED=130.
There is no READY banner, stdout diagnostic or error frame.

| Bound | Bytes / count | Scope |
|---|---:|---|
| Metadata | 2048 | Each request and each response independently |
| Request | 16384 | Entire header + metadata + payload |
| Original encoded reply | 4096 | Includes its unchanged original LF |
| Response | 6160 | Entire header + metadata + encoded payload |
| Input wire total | 64 MiB | One driver lifetime |
| Successfully emitted output wire total | 64 MiB | One driver lifetime; checked before every write |
| Frame index | 1..65536 | Adjacent, strictly increasing, no wrap |
| OBSERVE count | At most65535 | Reserves a final END at index65536 |

The independent raw record cap remains16384 in the unchanged C21 API, but a
record in this envelope has less usable capacity because its header and
metadata share the same total request cap. A future owner must budget full
response frames, not4096 alone. `EndpointLimits` permits only lower lifetime
caps for pure controls; the CLI offers no configuration/bypass switches.

Request metadata has exactly `identity`, `frame_index`, `payload_sha256`.
Identity has the exact seven fields and validation shapes of A's source
`integration/cpu_invocation_transcript.py` at PR24 commit
`5c192f34bad064b14e238747c2c569347257a62c`, source SHA256
`444f68e94a9adaaab0406b7402fb8029319bc192052b861f520b8982f89a4266`:

| Field | Validation |
|---|---|
| operation_id, run_id, actor_instance_id | Exact str, ASCII regex `[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}` |
| request_hash, package_manifest_sha256 | Exact str,64 lowercase hex |
| tested_commit | Exact str,40 lowercase hex |
| invocation_id | Exact int,1..2^63−1; bool rejected |

Invocation IDs must strictly increase (not necessarily by1); the other six
identity fields are frozen from first OBSERVE through END. Metadata rejects
duplicate/extra/missing keys, malformed UTF8, nonfinite constants, wrong types,
and bool-as-int. Incoming metadata need not use canonical order/spacing.
Outgoing metadata is ASCII JSON, sorted keys, compact separators, no NaN.
Parsed identity/request objects and retained raw bytes are immutable.

Response metadata has exactly `identity`, `frame_index`,
`request_frame_sha256`, `request_payload_sha256`, `payload_sha256`. It echoes
the current identity/index and hashes, respectively, every original request
frame byte (including original header/metadata serialization), original input
payload bytes, and unchanged core reply bytes including LF. The operation's
`identity.request_hash` remains a distinct correlation label. Future A
`prepared.request_raw_sha256` would equal `request_frame_sha256` if it writes
this complete frame. These hashes do not establish authentication, trusted
provenance, completion, availability, timing or permission.

END has an empty input payload and SHA256 of empty bytes. END response contains
the original local C21 EndReceipt encoded bytes, not a fabricated stop ACK.
The codec does not parse or JSON-roundtrip the model result. The exact original
2007B A result SHA256 is
`3cbffc7619558619bde6f1b25e53f3cb7225855b79aea45417e2fcf33cd4034b`;
its354B original first record SHA256 is
`9c9200453ca7feab036ee9e41b9b78f9b61df5d672792961379d5daa920d1eb8`.
They are copied byte-for-byte into the author evidence fixtures.

## Binding, core and retirement

`process_endpoint.py` imports only its codec eagerly. First validated OBSERVE
causes finite source reads (2MiB+1 each) and exact SHA checks of runner and
curve_input **before either parser import**. It then calls the unchanged
stdlib-only `runner.strict_json` and `CurveObservation.from_mapping`. All
13 original fields are required; geo_replay/force_curve_v1/frozen preprocessing
and a nonempty original record run_id of at most128 UTF8 bytes are required.
All subsequent records are strictly parsed and retain that binding.

Before importing/constructing the real core, `_new_core` independently checks
the actual sibling stream_core source hash with the same finite read cap. It
constructs exactly one `FrozenForceStream(limits=StreamLimits(max_output_bytes=4096))`.
All other core defaults, fixed manifest/model/scaler, CPU4 threads and
deterministic/eval settings remain unchanged. There is no input model path,
factory callback, profile switch or fake public mode. Imports check resolved
module file paths as well. Hash checks assume an immutable, correctly staged
trusted Python environment and module cache; they are not authentication or
defenses against an already compromised interpreter, concurrent source
replacement or arbitrary in-process monkeypatching.

Start is called once with generation=1, epoch=0 and the **original record**
run_id, e.g. `C-FORCE-CPU-20261024-v1`. The distinct A envelope run_id is not
rewritten or required to equal it. This preserves the original C21 binding;
the superseded main design v1 derived run_id would have rejected the unchanged
record. The C token/generation/epoch stay in process and never become BOOT,
A lifecycle identity, clock, authentication or a wire-adopted capability.
Each observe receives exact original immutable bytes; duplicates are forwarded
unchanged so the original C21 idempotent-builder/raw-prefix semantics apply.
No endpoint result setter or external result ingestion exists.

`EndpointDriver(read, write).run()` borrows synchronous local callables for
pure controls and runs once. Production proposal command, **not executed in
this slice**, from `competition/deepeye`:

```text
<A-approved-python> -B -m ai_pc.cpu_package.process_endpoint
```

The CLI accepts no extra arguments. It uses ordinary fd0/fd1, setting Windows
binary mode, and only `os.read(0, exact_remaining)` for header/metadata/payload.
Partial positive reads advance only by returned bytes. It never uses buffered
stdin/stdout, consumes future headers before an exact successful current
response write, closes borrowed test streams or adopts Win32 HANDLEs. A future
trusted owner must serialize one request followed by its complete reply; there
is no multiplexer, background thread, service or asynchronous cancellation.

Each complete response has exactly one `os.write(1, frame)`. Only an exact
built-in integer equal to the entire frame length is success. Partial/zero,
None/bool/invalid count, or exception retires immediately: no remainder,
retry, fallback stream or error frame. All framing/hash/schema/core/read/EOF
errors likewise retire permanently; EOF at a boundary without END is abnormal.
On error after successful start, local end is attempted at most once and its
receipt is discarded. A failed explicit end is never retried in cleanup. A
failed constructor/start/observe/write is never retried. Successful END emits
its one reply and returns immediately without examining trailing bytes. CLI
exit0 requires successful END reply; abnormal paths exit nonzero. A failing
cleanup also exits nonzero. At most one fixed bounded ASCII diagnostic goes
to stderr; no payload, raw exception, credential or traceback is echoed.
RunOutcome counters distinguish observe calls from successfully emitted replies;
a partial write does not count as a completed response or motion authorization.

## Source and dependency closure

Keep the product-relative layout. Existing9 selected C files total231397B;
the exact pins are unchanged:

| Product-relative path | SHA256 |
|---|---|
| ai_pc/cpu_package/stream_core.py | 0a8c07f34080784f36180951b28873b43de5e3f80ad201325254b274bd01217b |
| ai_pc/cpu_package/runner.py | 92114790259b7e35e8bf7b1a0519f0e3f68da52729d08b5b9862c992deae70af |
| ai_pc/model/curve_input.py | c017729a2d5717ff2bbf5a6c591320519c415ac10068b4cee19b3136913d848c |
| ai_pc/model/force_cnn.py | 5003427e1ac01e50b612d8f4f9c674c7df352b3942a5cc39978e23bdfbdb1260 |
| ai_pc/cpu_model/force_v1/model_manifest.json | 0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959 |
| ai_pc/cpu_model/force_v1/graph.json | 6fd93fab7e65b56b1cd9473475c54b071b3e82ff09549ee447675988f07efee2 |
| ai_pc/cpu_model/force_v1/weights.json | 8988f4bbcf425d9b48c9a62866ac350e6096ea43fabdd9b1e616b22ba4b6d187 |
| data/preprocessing.json | cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef |
| data/label_schema.json | 0913ff5a59085b47802a9902f23a836f4fa1129700de8e6593840416f4d7beed |

New runtime source is endpoint_protocol.py + process_endpoint.py; the proposal
is documentation. Preserve the existing cpu_package/__init__.py and namespace
layout; model manifest references resolve to the unchanged data directory.
Author manifest separately binds the five new source/doc/test files and
evidence. The small source/JSON closure is not a complete executable stage.
Python executable, stdlib, Torch package, native DLL/runtime dependencies,
environment/cache/temp/load access and interpreter metadata are **not**
enumerated/hash-staged here. C's prior2.9.0+cpu and A's reported2.12HIP are
different dependency environments; this proposal neither changes A nor proves
that one is inside its approved stage. A must establish the actual approved
runtime closure, initialization/lifetime constraints and256MiB stage policy;
an exceeded real budget is a blocker, not permission to widen it.

## A integration gap and evidence limits

A InvocationTranscript is one original request write per object with immutable
request bytes, finite raw read/journal budgets and no model-payload codec. It
does not manage reusable C stream sessions. Its one16384B request cap includes
all C22 framing. A's separate ActorPolicy8192B output cap accommodates6160B as
a numerical bound, but does not establish wire adoption or framing validation.
A current ActorRegistry appends two Win32 HANDLE arguments and its fixture
uses READY/X (READY buffer256B); this proposed zero-extra-argv fd0/fd1 CLI is
incompatible with that launch contract. No adapter exists in this delivery.
A's inactive multi-frame decoder is not used. Prior128B transport evidence
does not demonstrate this2007B recorded model result crossing a real endpoint.

A must source-review and choose its trusted HANDLE/fd owner adaptation,
per-frame InvocationIdentity/request journal, deadlines/cancellation/EOF/raw
read budgets, complete dependency staging, resource closure and factory
adoption. No A authority modules are imported/modified; the original factory
provider remains unavailable. No BOOT/QPC/authentication/completion verifier,
mailbox/handle adoption, runtime writer or motion bytes are supplied.

Only new pure byte/driver tests run for C22. They privately replace `_new_core`
with a labelled FakeCore, retain actual original record parsing, and treat the
2007B result as opaque static bytes. No endpoint subprocess/CLI, real learned
constructor/forward, training, old suite, heldout evaluation or benchmark runs.
Passes establish only those byte/lifecycle controls. Existing FORCE heldout
quality remains FAIL; sim_em_model_missing remains blocked. Live sensors,
map/planner/runtime/board, both H12 routes and formal acceptance remain open.
Source snapshots, actual argv/raw stdout/stderr/exit, fake/real counts and
stopped ownership release are in the new author evidence; independent review
and main publication follow a source freeze.

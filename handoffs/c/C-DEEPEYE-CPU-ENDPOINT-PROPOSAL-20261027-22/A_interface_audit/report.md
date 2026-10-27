# Exact A endpoint interface audit for the C21 proposal

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`; work `C-ENDPOINT-A-INTERFACE-AUDIT-20261027-v1`; actual agent `/root/sim_em_contract_audit`. Main remains `01a14025-4dfd-7ec3-aebb-57be48daba59`. Exclusive writes: this private `interface-audit/**` only. No product/index ownership or changes.

H01–H15 remain `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256 verified `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`; frozen design `1011259415a0916054eb580687612580bc1e5f09`. A alone operates the physical board. This reuses the prior interface inventory and does not reopen the sim_em audit.

## Finding and minimal proposal

**There is no currently adopted A reusable C inference endpoint.** A currently has (1) a one-write, finite-read raw transcript; (2) an explicitly inactive private length codec; (3) a retained native actor lifecycle launcher/READY-X fixture; (4) a production authority factory that unconditionally rejects before staging/acquisition. The C21 process proposal can add a bounded, persistent fixed-core diagnostic endpoint, but must describe the future A owner/handle/framing/parser/staging integration as unimplemented. It must not change A's public ABI or claim factory adoption, authenticated completion or motion authority.

The simplest compatible proposal is: one fixed C21 core/model/scaler per process; a private binary frame carrying exactly one original 13-field record as an opaque byte payload; strict request/reply sequencing; write the exact `StreamResult.encoded` bytes as the result payload; explicit END or actual EOF/error permanently retires this endpoint. Keep the seven A InvocationIdentity fields out of the FORCE record and out of the encoded core reply. The trusted A owner retains per-request sideband identity and exact raw-frame/raw-record/result hashes; any optional wire correlation header is a separately versioned private envelope, not a mutation of the original record/result or a production host schema. C local generation/epoch/token remain local.

## Current source pins and evidence

Actual PR24 GET on this audit returned head `5c192f34bad064b14e238747c2c569347257a62c`, repo `carolwjade/CarlandFPGA`, ref `codex/a/deepeye-implementation-20261014`, unchanged from the earlier exact source inspection. The prior nontruncated tree was reused only after this exact-head check. Eight necessary A files were retained and checked against their current tree Git-blob SHA1; `A-source-manifest.json` records SHA256/bytes/origin. Four cached exact source files were reused and four narrowly selected source blobs newly fetched. The actual PR24 and original comment `6416227814` were also GET/read back. Original API argv/stdout/stderr/exit/hashes are under `GET/`. All six recorded API requests exited 0; no endpoint, A module or learned model was executed.

Selected C closure was read with exact `git show b898e90c7248dec5a6dd0ee850c8a07e097e83aa:<path>` for ten files. Each current working file matches its exact Git blob. Source paths/bytes/hashes/argv/exit 0 are in `C-source-manifest.json`. `stream_core.py` SHA256 is `0a8c07f34080784f36180951b28873b43de5e3f80ad201325254b274bd01217b`; original C21 source is `80238476e72d217c48723276ab28d0c033084901`, published head is the above b898 commit, as confirmed in the original A comment. This audit does not revalidate A's actual forward or promote its result to model-quality acceptance.

## The exact 2007-byte A result

`A-original-encoded-reply-2007.bin` is recovered from the original comment's fenced UTF-8 payload, **including its final LF**. Its length is 2007 and SHA256 is exactly `3cbffc7619558619bde6f1b25e53f3cb7225855b79aea45417e2fcf33cd4034b`. It was never JSON-reserialized, rounded, normalized or recomputed. Removing its final LF yields 2006 bytes and the different hash `180468f9dbb2c665498389a8e695b5a77e9d639abba63c3b45de8896ed58386e`.

The first integrity extraction incorrectly omitted that LF and failed the advertised pin; preserving the original encoded LF resolves the mismatch exactly. This was a byte-boundary audit correction, not a product/core failure or new learned forward. `A-original-reply-byte-pin.json` retains that distinction. `stream_core.py:170–174` corroborates that `_encode` appends `b'\n'` to the canonical JSON. The 4096-byte result cap must include this LF; an outer framing header has its own additional bytes.

The original A comment says its API first-prefix forward/retirement completed and records an actual 2007B result, while explicitly refusing to count its earlier 128B native fixture as coverage of that result. Do not substitute the 128B fixture, a truncated result, a checksum-only echo or reconstructed probabilities for this actual immutable result in byte controls. The existing actor fixture's separate source bounds below do not change this evidence limitation.

## A InvocationIdentity and immutable request bytes

`competition/deepeye/integration/cpu_invocation_transcript.py:20–54` defines the exact frozen dataclass:

| Field | Exact constraint |
|---|---|
| operation_id | exact str; regex `[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}` |
| request_hash | exact str, 64 lowercase hex |
| tested_commit | exact str, 40 lowercase hex |
| package_manifest_sha256 | exact str, 64 lowercase hex |
| run_id | same bounded-label rule as operation_id |
| invocation_id | exact int, excluding bool/subclasses; 1..2^63−1 |
| actor_instance_id | same bounded-label rule |

These are correlation labels, not authenticated provenance. The operation's **request_hash is not the opaque request SHA256**. The transcript computes `request_raw_sha256=SHA256(request_raw)` and records exact request hex/byte count separately (`:130–142,207–212,284–300`). Preserve both meanings. Do not derive A BOOT/context/time/authority from the record run_id, C generation/epoch or matching hashes.

`InvocationTranscript(input_fd, output_fd, identity, *, request_raw, journal_path, max_output_bytes, max_reads, read_size, host_clock=None)` (`:94–154`) requires:

- exact `InvocationIdentity`, exact immutable nonempty `bytes` request of **1..16384 bytes total**;
- integer max_output_bytes 1..16MiB; max_reads 1..65536; read_size 1..8192;
- existing descriptors with pipe/socket/character file type; regular replay files rejected. This type check does not authenticate/exclusively own a connected producer;
- owned `os.dup` descriptors, noninheritable and Windows binary mode; new exclusive `xb` journal, no resume;
- original owner thread and fixed clock identity. Non-None must be the exact existing fresh-run QpcHostClock binding; None retains the existing monotonic diagnostic route. C must not manufacture that binding or turn raw stamp brackets into an availability/acquisition/completion interval.

The **16384 cap includes all bytes written by this transcript**, such as a proposed length/kind/identity header. A raw record cap of 16384 plus four framing bytes cannot be dispatched through this unchanged class. If the private header has H bytes, the compatible per-request raw-record maximum is at most `16384−H` (and no more than C's hard 16384). Similarly, the unchanged encoded result can be ≤4096 while its complete outer frame is `header+result`; size the future A read/output budget for the complete frame. A cap is not an OS atomic-write guarantee.

## One input / finite reads versus a reusable process

`dispatch_once()` (`cpu_invocation_transcript.py:202–239`) reserves and fsyncs the attempt before exactly **one os.write**. Partial, error or interrupted writes are terminal/uncertain; it cannot write a remainder, retry or resend. A successfully returned count is preserved; unknown consumption/count remains unknown. Calling dispatch again cannot perform another write.

`read_once()` (`:241–282`) is allowed only after fully recorded dispatch. It performs finite original OS reads with a fixed read size clipped by the remaining byte budget. It distinguishes data, actual BlockingIOError/EAGAIN as `empty`, and zero returned bytes as actual `eof`; empty is not EOF/readiness/completion. EOF or spent budgets prevents additional reads. It contains **no frame parser or response-completion check**. Byte availability may predate the request. Stamps and raw returns do not establish that this invocation caused inference. `close()` (`:308–327`) closes only its duplicated endpoints/journal; originals remain the owner’s responsibility.

A persistent C process therefore needs a future trusted A owner that keeps the **one original endpoint pair and actor instance**, permits one outstanding input only, supplies a fresh independent InvocationIdentity/journal per actual dispatch, accumulates/frames exactly that result and never replays an uncertain operation. Another transcript can record a later newly authorized input on the same owned pipe, but this reuse/uniqueness/causation adapter is **not implemented by the class**. New transcript objects cannot be used to retry an old request. Waiting for process EOF as the end of each response would hang a deliberately persistent endpoint; a proposed length envelope must delimit replies independently of process EOF. All correlation remains diagnostic until A independently adopts and verifies its original completion provider.

## Existing private framing and native owner are different interfaces

`simulation/isolation/ipc_framing.py` (`:7–16,19–91`) is **inactive** DEEPEYE-PRIVATE-FRAMES/1: four-byte uint32 little-endian length followed by 1..16384 opaque payload bytes. `FrameDecoder.feed` accepts chunks 0..8192 and at most four completed frames per call; no content validation. `feed(b'')` is not EOF; `finish()` handles actual EOF and rejects a partial frame. Type/size/length/excess-frames/truncation errors permanently retire it; no reset, resync or retry. The source and docs explicitly require future endpoints to adopt it.

Crucially, a failed `feed` call returns **no frames from that call**, including good frames preceding a bad later header in the same chunk. Direct `read(8192) -> feed` is not appropriate for C21's desired “consume one record, finish and write its reply before reading the next” flow. Use a bounded exact current-header/current-body reader with no read past the current frame; unbuffered raw I/O avoids Python BufferedReader prefetch of a future record. An invalid later frame must not suppress or rewrite an earlier completed reply. Do not call a new C kind/header format this existing codec or public ABI3.

`simulation/isolation/actor_owner.py:60–112` defines exact `ActorPolicy` fields: run_id, evidence_parent, source_root, files, executable, arguments, system_root, local_appdata, max_stage_bytes, output_limit, readiness_timeout_ns, lifetime_timeout_ns, sample_age_cap_ns, max_probe_ns. Required budgets are positive; output_limit≤8192 and stage≤268435456 bytes. Probe < sample age ≤ lifetime; readiness ≤ lifetime. `files` is a nonempty tuple of safe relative POSIX path/SHA256 pairs with no casefold duplicates; executable must be included; ≤128 argument strings totaling ≤16384 characters; source/evidence roots existing absolute directories without aliases/reparse points.

`ActorRegistry.launch(policy)` (`:169–200`) only constructs a fresh retained owner; no PID/handle/process adoption. `_stage_files` (`:281–297`) checks every approved ordinary single-link source byte/hash, rejects aliases, copies exclusively and counts the complete selected stage budget. `_launch` (`:300–358`) creates restricted process resources, requires original endpoint inheritance flags and process policy inspection, and appends **two inherited Win32 HANDLE decimal arguments** to the supplied arguments. A generic POSIX-FD or stdin/stdout CLI is not automatically that interface; a future A adapter must deliberately bind HANDLE/FD ownership and closure. No such conversion should be pretended by this proposal.

Current `_close_internal` (`:405–426`) may read at most 8192 diagnostic bytes and apply policy.output_limit **after** the helper read; it does not export that raw child output as trusted model evidence or frame/associate replies. Its policy cap is not an adopted result protocol. `actor_fixture.py:6–9,12–15,28–40,44–69` is a cooperative READY-line / exact `b'X'` EXIT fixture; its ReadyBuffer cap is 256 bytes. A prior run configured/read 128B does not verify 2007B model-result transport. None of these numbers should be conflated.

## Production factory remains closed

`simulation/authority/actor_composition.py:30–42` defines private trusted-main `AuthorityConfig`: actor_policy, initial_state, scene, model, budget, heartbeat_timeout_ns, max_slices, progress_max_age_ns, ai_model_sha256, optional pc_direct_window_v2. `create_authority(config, *, host_clock=None)` (`:560–583`) validates that exact configuration/model hash, calls `_production_channels` **before** registry/stage/acquisition and only then could create/start an ActorComposition. `_production_channels` (`:165–167`) unconditionally raises `ActivationUnavailable('original authenticated AI/channel/package unavailable')`.

There is no public C callback/provider/verified-boolean bypass. Private fixture patches are not production admission. Original BOOT/channel, mailbox activation, completion/slot verification, measured clock bounds, model usefulness, true board observations and both H12 routes remain A-owned missing providers, not fields for C to fill. A bounded endpoint proposal can be reviewed without supplying or modifying any of them.

## Concrete proposal options and retirement rules

**Preferred: serial private binary framing with owner-side correlation.** One process holds exactly one constructor and one fixed model/scaler. Trusted launch arguments select only this fixed package/core; no model/scaler/path/callback from a request. A minimal possible wire format is a versioned fixed header carrying frame-kind plus bounded payload length, followed by the exact opaque record/reply bytes. A concrete example is `u32le(body_length) || u8(kind) || body`; this example has five framing bytes and therefore a record maximum of 16379 for compatibility with one unchanged transcript. This is an option for the main to choose, not an existing adopted format. END can be a separately valid kind with zero body; it cannot masquerade as a legal zero-length payload in A's existing inactive codec. Length/kind/version/header and all caps must be frozen before implementation.

Have exactly one outstanding request. Read only the current header/body; validate length/type and the original thirteen fields; call the core once; write exactly the returned immutable `encoded` result as the payload; complete that write before reading another header. Log only sanitized bounded diagnostics to stderr so binary output contains no READY banner, warning, traceback or probability reserialization. Keep operation request_hash, full request_raw SHA256, raw record SHA256 and result SHA256 distinct in the owner-side ledger. Original record bytes, including permitted whitespace/LF, must reach `observe` unchanged and contribute unchanged to C's prefix hash. C result delivery_index/prefix hash may cross-check sequence correlation but are not authentication.

Use `StreamLimits(max_output_bytes=4096, max_record_bytes=<compatible reduced raw cap>, ...)` with the unchanged source's other hard bounds. The core default output cap is 8192; the proposal must explicitly reduce it. `start_session(generation=1,epoch=0,run_id=<validated original binding>)` returns a C-local token; retain that exact token, do not serialize/adopt one from an A request. A minimal one-session endpoint retires on END rather than accepting arbitrary session replacement. Core exceptions are transactional but do not automatically permanently retire the core; the endpoint must impose that stronger retirement policy itself.

Explicit END calls local end once and may return the unchanged local EndReceipt encoded payload within the agreed cap, then closes. Actual clean EOF between frames retires the local session without inventing a requested response or STOP acknowledgment. Partial header/body EOF, invalid/missing/extra/duplicate fields, length/type/correlation mismatch, core exception, partial/failed output write or invalid later frame retires permanently, stops further input and never retries, resumes, resets or reloads the model. Prior completed replies remain immutable. A local successful end is not A lifecycle/Job cleanup, BOOT deactivation or physical stop evidence; parent A still needs actual wait/exit/resource closure.

**Alternative, narrower single-transcript diagnostic batch:** freeze one finite request containing a bounded sequence of private frame records and an end marker whose *entire* byte string fits 16384. Process one frame at a time with no future pre-read, one core lifetime, finite framed outputs. This gives one transcript correlation for the whole batch and separate C per-record prefix/result correlation. It does not provide a reusable interactive multi-request process or per-input A InvocationIdentity and cannot embed the full original 128-record ~45KB input under the unchanged request cap. Do not present it as equivalent to the preferred serial endpoint. Creating a new model process for each one-record invocation is also not an equivalent continuous C21 history/lifetime solution.

Neither option is a production ABI/factory adoption. Before any A endpoint execution, publish the chosen exact format, minimal source, fake-core pure byte/error lifecycle controls, stage manifest and test plan on original PR25 for A source review as requested in comment 6416227814.

## Exact static C dependency closure and staging gap

The existing C21 core's runtime source imports are `stream_core.py -> runner.py + curve_input.py`, then constructor-local `torch` and `force_cnn.load_frozen_model` (`stream_core.py:15–16,218–256`). Nine selected original source/asset files total **231397 bytes** (not including new endpoint code):

1. ai_pc/cpu_package/stream_core.py
2. ai_pc/cpu_package/runner.py
3. ai_pc/model/curve_input.py
4. ai_pc/model/force_cnn.py
5. ai_pc/cpu_model/force_v1/model_manifest.json
6. ai_pc/cpu_model/force_v1/graph.json
7. ai_pc/cpu_model/force_v1/weights.json
8. data/preprocessing.json
9. data/label_schema.json

Preserve the product-relative layout: stream_core derives product from `__file__.parents[2]`; graph/weights are direct manifest siblings; preprocessing and label_schema resolve through the frozen manifest's `../../../data/` references and must match the fixed product paths. Core verifies runner/builder/model source byte hashes before model import; changing line endings or flattening paths breaks those identities. Namespace/package root and the exact new endpoint module must be explicit in the launch plan. No training scripts, FORCE archive, heldout labels, scene assets or whole evidence tree are required runtime inputs. The label-schema file is the frozen class-order metadata already loaded by this code, not a per-observation target stream.

This source/JSON set **does not include Python, stdlib, Torch packages/native DLLs, native runtime dependencies, environment/cache/temp requirements, executable or interpreter metadata**. It is not a complete runnable A stage manifest. A's approved runtime closure, version/source hashes, load access, AppContainer policy and total stage-size/initialization/lifetime constraints must be checked by A's original owner. Do not copy C's virtualenv, use a whole repo in place of closure, widen ACLs, change providers/credentials or claim an external installed Python/Torch is automatically inside the stage. If actual required runtime exceeds the launcher's 256MiB stage budget, record that concrete target-runtime gap for A instead of silently bypassing the budget. This audit did not inventory/copy or execute that runtime.

C21 constructor loads the fixed scaler/model once, sets CPU/deterministic/eval, and permits no per-observation model replacement. Its raw record schema remains exactly run_id, source_domain, profile_id, preprocessing_sha256, sequence, value_0..3 and valid_0..3. The public FORCE component, quality FAIL, no sim_em conversion, no motion_bytes and all unmet formal cards remain unchanged by adding framing. Model initialization/bytes alone do not close C02/C03/H11.

## Review of the main's chosen design v1

The main requested a read-only check of its locked `main/design-v1.md`, SHA256 `e4c4cde80852c60a647f0893f89f33de5b8437bc125ba3f5dd388a709e789a0b`. Exact readback is retained as `main-design-readback.md`. Its chosen private 16-byte `>4sBBHII` C22E header, metadata cap 2048, whole input cap 16384 and whole response cap 6160 (=16+2048+4096) correctly account for the current A transcript/ActorPolicy limits. The identity/request-frame/payload hash meanings, original LF, no A module import, no prefetch, one response write and explicitly missing owner/staging/factory adoption are consistent with the audited A source. The one new C22E proposal is distinct from A's inactive codec.

**One blocking conflict was reported immediately to the main before release:** v1 selected `start_session(..., run_id='c22-'+identity_hash)` while leaving the original thirteen-field input unchanged. Frozen C21 `stream_core.py:331–334` parses the observation then strictly requires `observation.binding == active.builder.binding`; `start_session:288–293` embeds exactly its given run_id in that binding. The fixed original record has run_id `C-FORCE-CPU-20261024-v1`. Using a derived run_id therefore makes the first observe fail `binding_invalid`, even if a loose fake core accepts it.

Required correction: fully validate the first original record through the original strict field/binding semantics; use **that original record's run_id** to start the C-local session with generation 1/epoch 0; forward the original record bytes unchanged. Keep A `identity.run_id` separate in metadata/ledger; do not equate A labels with C binding or change record values to match them. All later input must retain the same C binding. Pure fake controls need a case where valid A identity.run_id deliberately differs from original record.run_id, plus a later changed C record binding that must fail. None of this grants A authority or requires a learned forward. Until this correction is recorded, the observed design v1 is not interface-accepted. The main owns its revised design and author instructions; this audit did not edit either.

**Main correction confirmed:** `main/design-v2.md` was subsequently read back, its complete SHA256 independently verified as `437aedcf1f09f11109632f4f101a6851c07a2ba2a6f65939fe35cbf92540d07f`, and exact bytes retained in `main-design-v2-readback.md`. Its line 21 now requires original pinned strict JSON/CurveObservation validation before constructing the core, starts using the original record run_id, preserves that C binding and keeps A identity.run_id separate. Line 31 records v1 supersession. This resolves the identified source/design binding conflict; the chosen v2 limits/correlation fit the audited A constraints **as a private proposal**. This is not a review of evolving author source or evidence that the endpoint ran or A adopted it. The author/reviewer were notified by the main; their implementation/tests remain separate work.

## Principal current A hashes

All paths below are relative to A's `competition/deepeye/`, exact source `5c192f34bad064b14e238747c2c569347257a62c`:

| Path | SHA256 |
|---|---|
| integration/cpu_invocation_transcript.py | 444f68e94a9adaaab0406b7402fb8029319bc192052b861f520b8982f89a4266 |
| docs/cpu_invocation_transcript.md | 42fca58970a140c4b59423387231a7001837cf1236597df7413a0edde6478cfb |
| simulation/isolation/ipc_framing.py | a134af7e8ade69a4624abf780575785dff76612454cf83f0ec92ff8b1da0ee09 |
| docs/actor_ipc_framing.md | 02c115882bac7dfbe2a42553a33a2b4896b439e72217a41ca5a0b08d795c3922 |
| simulation/isolation/actor_owner.py | cb3f8319627fbbf94ce3d250173d97f7e6f1ea09b5bf5fd530c741d4e5f857b9 |
| simulation/isolation/actor_fixture.py | 47946ba137eb61aa9d4d2357487c28210314bd4642ad7b1b4d781d052abab3b6 |
| simulation/authority/actor_composition.py | dd940de436f441acfd1dcfe5cfeaa0a2a86aac05c513893e1dc19d95410a3a8d |
| docs/actor_composition.md | 7cf201a1d333bffa81bd87a72376919e8739a07edb06941e07b2879e9cc5494b |

## Completion

Read-only audit complete. No endpoint/process/model execution, learned forward, training, product test, product/index edit, remote mutation, peer send, UI, SQL, credentials/controller/service or board operation. All synchronous source reads/GETs returned. No background job or child was launched. `active_jobs=[]`; private audit ownership is released at final return. A source pins are confirmed current at this audit's GET, not a promise that remote state cannot later change. All unmet H01–H15, both H12 routes and formal product cards remain incomplete.

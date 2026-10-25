# Bounded causal CPU stream core

Operation C-DEEPEYE-CPU-STREAM-CORE-20261025-21; task DEEPEYE-IMPLEMENTATION-20261014/version1; work C-CPU-CAUSAL-STREAM-CORE-20261025-v1, continuing C-LIVE-DECISION-PACKAGE-20261023-v1. Source/evidence commit `80238476e72d217c48723276ab28d0c033084901`, tree `de03b7b9d15fa9d1958d78a2e4d5c162d16112fe`; canonical request SHA256 `edfbf60f84e2dd7f174a4306d947b3290455f3869f94a597b0de1a4f56b70f19`. The next commit adds only README/input/manifest metadata.

The previous offline runner validates an entire observation file before producing its first result. The new `FrozenForceStream` in `competition/deepeye/ai_pc/cpu_package/stream_core.py` instead loads the same fixed learned FORCE model/scaler once and accepts one bounded exact13-field raw JSON byte record per synchronous call. It has no input-file/iterator, future suffix, output path, transport, process or IPC interface. See `STREAM_CORE.md` for call signatures and limits.

Window/history, tensor construction, inference, exact raw-prefix SHA and bounded immutable result serialization all complete on trial state before one committed-state replacement. Malformed/forbidden later inputs, regressed/conflicting records, float32 overflow and inference/serialization/output-size failure preserve the previous committed result/history/prefix. Semantic duplicates retain the original builder acquisition semantics while advancing accepted-delivery bytes/digest/index. Explicit start/end with strictly increasing local generation/epoch and exact returned-token identity rejects stale/foreign/copied tokens and silent reset. These C bookkeeping values do not establish A BOOT, observation age, observed_seq, source authentication, deadline or motion authority.

Hard limits: one record16,384bytes; result/end JSON8,192bytes; run label128UTF8bytes; lifetime65,536accepted deliveries/64MiBraw/1,024starts/2,048transitions; at most128history slots. All new constructor preflight source/asset reads now have an explicit2MiB cap (cap+1 read rejection). The existing model JSON loader remains unchanged. Model/scaler objects are instantiated once; constructor verification can read fixed assets more than once. Observation methods perform no asset/file reloads.

The original model manifest remains `0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959`. CPU only, four threads, deterministic algorithms; FORCE/geo_replay only. `sim_em_v2` remains blocked. Results include finite12probabilities, class/source code and official class order, float32 tensor identity, exact raw prefix, original sequence, binding and zero authority. There is no A model_candidate, passing verifier, fabricated BOOT/clock/observed_seq, action or motion bytes.

## Actual evidence and revisions

Author first16new controls passed/zero skips/exit0. A narrow end-error normalization was then checked by its affected1control/exit0, without calling the whole16 a final-source rerun. Eight real prefix calls compared saved C19 indices0/1/7 exactly; no old batch execution, training, heldout or benchmark was repeated.

Independent review then found R1: eight constructor preflight reads omitted a finite cap. Its genuine minimal RED exit1 recorded `read_size=-1`, without allocating a large file or loading a model. Root independently confirmed the source issue and preserved the pre-fix source/doc/test and release/manifest. The author repaired only new-module constructor caps and documentation, adding new constructor controls. Original author evidence remains immutable. Historical author/phase2 manifests refer to their recorded snapshots; they are not claims that pre-fix hashes identify the current source. `prior_freeze/` preserves those exact bytes. The current canonical manifest and bounded-init repair manifest identify current files.

Final-source author constructor controls passed4methods/exit0. Independent final review passed18methods/zero skips/exit0, including the original R1 trap now requesting2,097,153bytes and all17frozen groups. Its only3actual model forwards used the first3public oracle records with exact feature/prefix/class/probability parity;42private prediction-stub calls exercised history/lifecycle/failure paths and are not learned-model performance evidence. Root separately compares3saved-prefix predictions and performs5actual model forwards across explicit session/continuation controls; the duplicate reuses probabilities. Exact argv/stdout/stderr/exit/hash records are retained. Raw NumPy-unavailable warnings are retained. Test elapsed times are not performance guarantees.

Portable root probe, with a compatible existing CPU Torch environment and a new output file in an existing directory:

```text
python -B -X utf8 handoffs/c/C-DEEPEYE-CPU-STREAM-CORE-20261025-21/main_review/main_probe.py --root <checkout> --oracle <checkout>/handoffs/c/C-DEEPEYE-CPU-STREAM-CORE-20261025-21/main_review/selected-prefix-oracle.json --expected-stream-sha256 0a8c07f34080784f36180951b28873b43de5e3f80ad201325254b274bd01217b --output <new-output.json>
```

Original captured commands retain historical C paths; do not treat them as A paths. Original C19/C20 tracked bytes and their exact commits/manifests are unchanged. No old suite was replayed for publication.

## Remaining acceptance

A reported the original C19 portability operation `A-C19-CPU-PORTABILITY-ENV2-20261025-v1` in PR25 comment6395841435: Python3.12.14/Torch2.12.0+rocm7.14.1 on explicit CPU, exit0, original128prefix/tensor/class parity, max probability difference1.7881393432617188e-07. This is A's original C19 feedback, not a C rerun, new C21 acceptance, bitwise probability equality or runtime format adoption. A's earlier USERNAME environment failure is retained separately.

FORCE quality remains FAIL: heldout fixed12Macro-F1 .1827348057438266 below centroid .2047004573101128 and target .60. The model is not a water/obstacle detector. Qualified sim_em source/profile, legal scenario data/targets/time alignment, train-only scales/model, authenticated observations/historical odometry/clock, causal map, complete3Dplanner and A process/IPC/registration/permissions integration remain incomplete. C20 is a separate fixture-only conservative geometry kernel, not a global planner or control permission. B56's failed zero-capture board attempt does not supply live C input.

H01-H15, both complete H12 paths and all unmet29formal cards remain mandatory/incomplete. Frozen design `1011259415a0916054eb580687612580bc1e5f09`; contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`. Only A operates the physical board.

# C offline causal CPU package

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`; work
`C-CPU-CAUSAL-RUNNER-20261024-v1`. The frozen design is
`1011259415a0916054eb580687612580bc1e5f09` and all H01-H15 remain required under
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.

`../run_cpu.py` runs the actual frozen learned FORCE lithology CNN on public
curve observations. It reads no labels, scene, world, controller, hardware or
network. It produces a prediction for each successive causal prefix, retaining
the exact existing `CurveWindowBuilder` semantics. The input is a JSONL file of
the exact thirteen fields in `public_observation.schema.json`. Values are
`GR, RHOB, NPHI, RDEP`; validity flags are exact JSON booleans. `sequence` is an
acquisition index, never an invented sample rate, timestamp or physical depth.
Integers are parsed exactly; float32-overflowing features are rejected. Unknown
fields, including labels, confidence, truth, coordinates and future timestamps,
are rejected. A source-domain declaration alone does not attest data origin;
the fixed public input has separate source/hash evidence in the model package.

The scaler is the original frozen train-only preprocessing bytes, SHA256
`cb66fd302165c86344f3b8d1af9d9c4e4e229621cef44cbfa6fb8cd121a63eef`.
The unchanged builder source at the original C head `942fa309ffc8f1d32c816cfa643b009b031d7d0a`
is additionally pinned to
`c017729a2d5717ff2bbf5a6c591320519c415ac10068b4cee19b3136913d848c`.
Each invocation starts cold; missing startup/history/gap channels have explicit
zero masks. Later observations cannot modify prior features or predictions.

The model manifest SHA256 must come from the independently delivered handoff,
not be silently recalculated as permission to run modified assets. The loader
checks graph/source, weights, preprocessing and label-schema hashes, fixed
graph/shape/class order, and finite tensor keys/shapes/values before using the
JSON weights. It never loads pickle or an input-selected Python module. A
missing model or scaler returns nonzero `blocked`, with no fabricated logits.
An invalid input/hash/model returns nonzero `failed`. Neither writes an output.

Run with any current directory using absolute paths:

```powershell
& '<C Python or compatible Python>' -B -X utf8 '<checkout>\competition\deepeye\ai_pc\run_cpu.py' `
  --manifest '<checkout>\competition\deepeye\ai_pc\cpu_model\force_v1\model_manifest.json' `
  --expected-manifest-sha256 '<external frozen manifest SHA256>' `
  --input '<checkout>\competition\deepeye\ai_pc\cpu_model\force_v1\public_input.jsonl' `
  --expected-input-sha256 '<external fixed input SHA256>' `
  --output '<existing output directory>\new-result.json' --device cpu --threads 4
```

Frozen manifest SHA256:
`0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959`.
Fixed public input SHA256:
`d81b29a6200d83133eda22149c70d2a0f6b3db06f9885ae669ddaffc75e99b37`.
The final evidence README supplies the exact C command and raw output.
`--output` must name a new file in an existing directory. Existing files,
hardlink aliases and symlinks are rejected; the final create is exclusive even
if another process creates the path after the early check. There is no overwrite
flag or resumable side effect. Success emits identical JSON bytes to stdout and
the output. Exit codes are `0=offline inference completed`, `1=rejected/failed`,
`2=prerequisite blocked`; these are not product acceptance codes.

The result records model/graph/weights/scaler/label/input/builder/runner hashes,
every exact input-prefix digest, actual float32 little-endian feature-tensor
digest, binding/latest acquisition sequence/masks, twelve finite probabilities
and official class order. It always returns `movement_authorized:false` and
`motion_bytes:null`; it has no passing runtime verifier or motion adapter.

Default execution is CPU. `--device hip` is explicit: it requires an actual
HIP torch build and usable device, then selects `cuda:0`; otherwise it returns
blocked with no CPU fallback. C's tested environment is isolated CPython 3.12
with official `torch==2.9.0+cpu`. A's existing `torch2.12.0+rocm7.14.1` environment
is not modified or claimed compatible by C. A must measure its actual runtime
against the same graph, JSON weights, hashes and fixed input. No NumPy package
is required by this runner.

`--benchmark-repetitions 10` adds ten bounded repeats on the final observed
tensor. Timings use `perf_counter_ns`; each timed operation includes forward,
softmax, finite checks and materialization of probabilities on the host. Tensor
construction, model load and training are excluded. Prefix forward times and
model-load time are reported separately. Benchmark repeats do not retrain or
advance observation history, and are not real-time, board, scheduling or sensor
measurements.

The one C baseline used 128 real input prefixes (TRAIN well `15/9-13`, rows
7327..7454), CPython 3.12.14, Torch 2.9.0+cpu and four CPU threads. Ten repeats
on the final observed tensor measured a median **0.30615 ms**, range
0.2874..0.3373 ms, with the full timing scope above. Across the 128 prefixes,
forward/softmax/check/materialization time totalled 64.3935 ms; scaler/window/
tensor/hash preprocessing totalled 50.5441 ms. Input file/hash/JSON/schema
validation separately took 11.813 ms. Whole package compute including runtime
import, model loading, record assembly and the ten repeats took 2560.9894 ms;
JSON serialization/output I/O are excluded. These are this bounded run's
observations, not guaranteed latency or throughput. Raw stage arrays are in
`../../evidence/ai/cpu_package_20261024/cpu-baseline/prediction-result.json`.

This package's format is C's offline interface. **A has not adopted it.** A's
current opaque invocation limit of 16,384 bytes does not establish agreement
on these fields or license sending the whole JSONL/result into that interface.
No production integration is performed here.

The actual FORCE learned component does not supply the missing trained
`sim_em_v2` model or train-fitted summary scales; requesting that profile returns
`sim_em_model_missing`. FORCE lithology classes are not remapped into water,
obstacle, live sensor or 3D truth. Complete held-out-well quality, causal
sensor-to-map/planner benefit, A runtime/source/clock integration, both control
paths, R03/C01-C05/G01-G09 and physical/system/formal gates remain incomplete.
The mandatory H01-H15 game-quality application and substantive online AI are
unchanged. Only A operates the physical board.

The actual learned graph **fails the fixed quality target**: trainer evidence
reports fixed-12 held-out-well macro-F1 0.1827348, below the train-fitted centroid
baseline 0.2047005 and the 0.60 target (majority baseline 0.0676299). This is a
real learned offline CPU component, with no demonstrated improvement over the
centroid, useful full-system AI benefit, or quality acceptance. See
`../../evidence/ai/force_cpu_training_20261024/heldout_metrics.json` and
`scalar_baselines.json`. This runner does not retrain, tune on test, or turn
these failed metrics into a pass.

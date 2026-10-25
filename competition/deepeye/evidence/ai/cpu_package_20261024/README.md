# C CPU causal runner evidence, 2026-10-24

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`C-CPU-CAUSAL-RUNNER-20261024-v1`, actual native worker
`/root/cpu_package_runner`. Current main remains
`01a14025-4dfd-7ec3-aebb-57be48daba59`. No separate App UUID was exposed or
invented. The root recorded assignment before START; the worker owns only the
new runner/package/test/evidence paths. Only the root publishes or commits.

All H01-H15 remain required. Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`,
source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
design `1011259415a0916054eb580687612580bc1e5f09`. Original C base
`942fa309ffc8f1d32c816cfa643b009b031d7d0a` was retained. These are offline
software evidence, not product, runtime, sensor, physical or formal acceptance.

Actual entrypoint: `../../../ai_pc/run_cpu.py`; full API, scope and portable
command: `../../../ai_pc/cpu_package/README.md`. In this evidence directory,
`cpu-baseline/command.json` preserves the exact executed C argv, arbitrary
working directory, Python executable and external hashes. Paths in that raw
command are authoring-machine paths; the portable README uses checkout paths.

The fixed actual trained manifest SHA256 is
`0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959`;
weights `8988f4bbcf425d9b48c9a62866ac350e6096ea43fabdd9b1e616b22ba4b6d187`;
graph `6fd93fab7e65b56b1cd9473475c54b071b3e82ff09549ee447675988f07efee2`;
public input `d81b29a6200d83133eda22149c70d2a0f6b3db06f9885ae669ddaffc75e99b37`.
Source preparation/training/held-out evaluation are separate evidence in
`../force_cpu_training_20261024/`; this worker did not retrain or tune them.
The 128 public records are actual TRAIN well `15/9-13` rows7327..7454, run
`C-FORCE-CPU-20261024-v1`, `force_curve_v1`, `geo_replay`. Labels remain in the
separate evaluator file and never enter the runner's thirteen-field input.

The measured command ran CPython3.12.14/Torch2.9.0+cpu, four CPU threads, no
NumPy installation. Torch's actual NumPy-unavailable warning is preserved in
stderr. C ran only CPU and tested that explicit HIP is blocked on this CPU
runtime. A's existing Torch2.12 HIP build was not changed or exercised.

| Raw command directory | Actual result |
| --- | --- |
| `boundary-tests-1` | First 14 boundary methods passed, exit0 |
| `cli-help` | Actual help command, exit0 |
| `affected-suite-final` | First complete new suite: 20 methods, 19 pass / 1 fail, exit1 |
| `portable-diagnostic` | One affected method reproduced the missing-weights classification defect, exit1 |
| `portable-repair-green` | Affected missing/corrupt/shape method passed, exit0 |
| `affected-suite-green` | Final common-path verification: 20 methods / zero skips, exit0 |
| `cpu-baseline` | Actual CLI, 128 real prefixes + ten final-tensor repetitions, exit0 |

The failure was real runner behavior: the frozen loader converts missing JSON
weights into its generic unreadable-artifact error, and the initial runner
therefore returned failed1 instead of prerequisite-blocked2. The owned runner
now preflights pinned assets before invoking that unchanged loader. Missing
model/weights/scaler are blocked2, corrupt graph hashes fail1, and a tampered
tensor shape with recalculated container pins is still rejected1. All mutations
occur in a temporary copied product tree, never the actual frozen assets. The
first RED/diagnostic raw logs were preserved; no pre-repair source snapshot was
recorded. Final source hashes are in `delivery-manifest.json`, and the actual
baseline also records its runner source hash. No frozen model source or model
manifest was edited to repair this integration behavior.

The 20 final methods exercise causal prefix and fresh cold-start behavior,
exact input fields and booleans, unknown labels/confidence/truth/coordinates/
timestamps, duplicate JSON fields/nonfinite constants, future-suffix invariance,
sequence conflict/gaps, input/model/scaler pins, missing assets, copied-tree
portability, malformed tensor shape, output no-clobber/hardlink aliases, actual
finite12-class output and explicit HIP no-fallback. Constructed boundary values
in the test file are unit fixtures, not licensed-source/model quality evidence.
The actual model tests and baseline use the fixed real public input.

`cpu-baseline/prediction-result.json` is byte-identical to raw stdout, SHA256
`e84bdfe850efb8a231f72c98a5fb05cc20c7f6036014f4db77ef3f6cf44b418f`.
It stores all 128 exact input-prefix/feature hashes, current binding/sequence/
masks, probabilities, source pins, actual runtime and stage arrays. Its first
float32 feature hash is
`8bd61940ded56e13271e13bc0bd6f2c618d3b34c73e671ee6e9710fbb0af962c`;
last is `d21c9ad75718dc2f8bac40d6494fe8c58f3127002388543cc30951fb277939b5`.
Every record and result retain `movement_authorized:false`; no motion bytes or
passing runtime verifier is created. A has not adopted this C offline format,
and its separate opaque16KiB invocation is not declared interoperable.

The one bounded timing baseline measured ten repeats on the final observed
tensor: median0.30615ms, range0.2874..0.3373ms. That scope includes forward,
softmax, finite checks and host probability materialization; it excludes
preprocessing, model load and training. All128 prefix forwards total64.3935ms;
scaler/window/tensor/hash preprocessing total50.5441ms; input read/hash/JSON/
schema validation11.813ms; whole compute including import/load/record assembly
and repeats2560.9894ms, excluding JSON/output I/O. These are measured values
from this run, never real-time guarantees or board/acquisition measurements.

The learned FORCE graph's actual held-out fixed12 macro-F1 is0.1827348, below
the train-fitted centroid0.2047005 and target0.60 (majority0.0676299): **quality
FAIL**. This package supplies an actual learned offline CPU component and
honest failed quality evidence; it does not establish substantive full-system
AI benefit or C01 acceptance. Trained `sim_em_v2` and fitted summary scales,
sensor/water/obstacle mapping, online map/planner benefit, source/clock/runtime
integration, both complete control paths and all final product/physical/formal
gates remain incomplete. FORCE is never remapped into live or 3D truth. Only A
operates the physical board. No controller, credentials, services, locks, SQL,
old queue, peer chat or hardware action was used by this worker.

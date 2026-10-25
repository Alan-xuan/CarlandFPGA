# Frozen FORCE CPU baseline, 2026-10-24

This package supplies an actual learned graph and weights for the offline public
FORCE lithology profile. **Its quality target failed.** It is a runnable baseline
component, not useful-core-AI acceptance, a sim_em_v2/water/obstacle model, a
perception/map/planning system or a motion authority.

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`C-FORCE-CPU-CNN-20261024-v1`; frozen design
`1011259415a0916054eb580687612580bc1e5f09`. Full H01–H15 contract
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
is unchanged. Physical board operations belong to A alone.

## Exact artifact identity

- `model_manifest.json`: `0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959`
- `weights.json`: `8988f4bbcf425d9b48c9a62866ac350e6096ea43fabdd9b1e616b22ba4b6d187`
- `graph.json`: `6fd93fab7e65b56b1cd9473475c54b071b3e82ff09549ee447675988f07efee2`
- `public_input.jsonl`: `d81b29a6200d83133eda22149c70d2a0f6b3db06f9885ae669ddaffc75e99b37`

The fixed 4,916-parameter graph is `[N,8,128,1]` -> Conv2D(8,16,k5x1),
ReLU, AvgPool(4x1), Conv2D(16,24,k5x1), ReLU, AvgPool(4x1), Flatten(192),
Gemm(12). Small fixed operators bound this CPU run; no graph or hyperparameter
search was performed. `graph-freeze-before-optimizer.json` records the graph
hash before the first optimizer step. JSON weights contain finite float32 state
values only. The loader does not unpickle or import a graph-selected class.

`load_frozen_model(manifest_path, expected_manifest_sha256, device="cpu")` in
`ai_pc/model/force_cnn.py` verifies externally pinned manifest bytes, exact source,
graph, weights, official class order and existing preprocessing/label bytes.
References resolve relative to the manifest. CPU torch 2.9.0+cpu / CPython 3.12.14
actually ran here. A's different HIP installation must run its own compatibility
check; this package does not establish ROCm, AMD/NPU or board performance.

## One bounded training run and the failed quality gate

The frozen book's section 5 target is **original FORCE Macro-F1 >= 0.60**, over
the fixed 12 classes. That exact target is retained, not replaced by the scores
below. The selected model's heldout result is:

| Same heldout 19 complete wells | Fixed12 Macro-F1 |
| --- | ---: |
| This CNN | 0.1827348057 |
| Current-point 8-feature nearest TRAIN centroid | 0.2047004573 |
| TRAIN majority class | 0.0676298759 |

CNN accuracy is 0.6344808663; the class imbalance makes it insufficient as a
quality claim. The CNN is worse than the centroid baseline. Of 376,319 test rows,
244,176 have targets; the 132,143 missing-target positions remain in causal input
histories and are excluded only from supervised scoring. The complete confusion,
per-class support/recall, confidence strata and a 200-resample parent-well
bootstrap interval `[0.1408611049,0.2148043055]` are in the evidence. Chalk,
Halite and Basement have zero test support; their fixed12 F1 remains zero and
recall is null. Dolomite has 358 test examples and **zero true positives**.
No unsupported-class success is claimed.

Seed 20261024, exactly five epochs, Adam 0.001, batch 256, TRAIN stride 8,
sqrt-inverse TRAIN class weighting, 4 CPU threads / 1 interop / 0 loader workers
were fixed before training. Every TRAIN well is used; each epoch has 122,023
labeled selected points. The frozen well split is 82 TRAIN / 17 validation /
19 test (81/17/19 parent groups). Existing train-only scaler bytes are unchanged.
Validation fixed12 Macro-F1 selected epoch 5 (0.2135030090), with first ties kept.
Graph, selected weights and manifest were frozen before opening any test member;
then one heldout evaluation ran. There was no retraining or test-based selection.
Centroids and majority use all labeled TRAIN rows; that differs from the CNN's
stride8 training and is disclosed rather than presented as identical sampling.

The successful training command, unedited stdout/stderr, exit code 0, environment
wheel hashes, all five epoch metrics, exact member-open journal and safe-load
checks are under `evidence/ai/force_cpu_training_20261024/`. The only stderr in
the actual train is torch's missing-NumPy warning; native tensor paths ran without
NumPy. `requirements-cpu-lock.txt` records all actually installed package hashes.

## Fixed causal public observations and attribution

`public_input.jsonl` has exactly the existing thirteen CurveObservation fields:
opaque run/domain/profile/scaler identity, acquisition sequence, four sensor
values and four bool validity flags. Labels and confidence are separate
evaluator-only evidence, never model inputs. No depth, coordinates, hidden scene
layout, future samples or motion grant is in this stream. A fresh builder masks
its initial unavailable history; the last row has the full 128 supplied points.

The 128 observations are the previously selected real TRAIN member `15_9-13.las`,
zero-based rows 7327–7454, original member SHA256
`933752fd96b8c286b17d125b28d8a53dcd1d4c69e179a482cfaedfc2ace5fb00`.
This is a deterministic reproduction input, **not heldout accuracy** or a physical
sensor stream. The complete archive SHA256 is
`042ef1d473100dc12768cae7107a8cead071a394f137af3bc1ddaf8a5d1b8dda`.
During the actual source read, 18 real startup/boundary windows over three TRAIN
wells compared exactly in float32 with the existing CurveWindowBuilder.

Attribution: Bormann, Aursand, Dilib, Manral and Dischington (2020), FORCE 2020
well logs, DOI [10.5281/zenodo.4351156](https://zenodo.org/records/4351156),
[authors' repository](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition)
at `c8d01ee92c1c8e1ecba36f96cca6ea7b689338a1`. The deposited resource declares
CC BY 4.0; its original-log licensing text separately says “NOLD 2.0”, as retained
in `data/dataset_card.md`. These source facts do not relicense all upstream code.

The raw-to-compressed quality-loss gate, sim_em_v2 fitted model, online causal
perception/map/planning, full C01–C05, R03/runtime, AMD and physical/system/H01–H15
acceptance remain incomplete. Software process success does not pass those gates.

# Independent frozen CPU package review

Task DEEPEYE-IMPLEMENTATION-20261014/version1; work C-CPU-FROZEN-ARTIFACT-REVIEW-20261024-v1; actual native agent /root/cpu_independent_review. Main remains 01a14025-4dfd-7ec3-aebb-57be48daba59. App child thread UUID is not exposed. Prior recipe review had actually finalized and released before this separately recorded work.

The bounded independent check completed exit 0. Artifact integrity, causal feature construction, actual learned weights and one real fixed-window CPU forward passed. Model quality failed: fixed-12-class heldout Macro-F1 is 0.1827348057438266, worse than the TRAIN-only current-vector centroid baseline at 0.2047004573101128 and below the fixed 0.60 target. This is a reproducible failed-quality learned offline component, not admitted online AI.

## Independently verified identities

- Trainer delivery manifest 44e9fa1c3396bcf2f019623ac149dfcb847107f02adc82f5b910709aa8756158: all 69 listed source/model/evidence files match actual byte counts and SHA256.
- Runner delivery manifest 9fc1dfc5c048e379b53da9a3dc9ca1ccf5dac288c6ad3be12dd96e2eace8c6c2: all 41 listed source/evidence files match actual byte counts and SHA256.
- Model manifest 0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959.
- Graph 6fd93fab7e65b56b1cd9473475c54b071b3e82ff09549ee447675988f07efee2; weights 8988f4bbcf425d9b48c9a62866ac350e6096ea43fabdd9b1e616b22ba4b6d187.
- Public fixed input d81b29a6200d83133eda22149c70d2a0f6b3db06f9885ae669ddaffc75e99b37.
- Model source 5003427e1ac01e50b612d8f4f9c674c7df352b3942a5cc39978e23bdfbdb1260; runner source 92114790259b7e35e8bf7b1a0519f0e3f68da52729d08b5b9862c992deae70af.
- Saved actual runner output e84bdfe850efb8a231f72c98a5fb05cc20c7f6036014f4db77ef3f6cf44b418f.

These checks verify the released bytes. They do not independently reproduce every author test, training operation or benchmark. No author test module was imported, and no suite was repeated.

## Actual training evidence and saved-metric arithmetic

The raw train-01 command/result and stdout/stderr hashes match. Its captured process exited 0, started 2026-10-24T12:16:53.037775Z and finished 12:18:09.917919Z. Raw stdout contains exactly epoch events 1 through 5, 82 TRAIN and 17 validation prepared-well events before one model freeze event, then 19 test prepared-well events after that event, and one final completion event. Graph freeze metadata records zero optimizer steps and predates final model freeze. The pre-test journal has exactly 99 TRAIN/validation members and is the exact prefix of the 118-member completed journal. Highest validation score selects epoch 5 consistently with the frozen manifest. Source inspection from the prior independently pinned recipe review establishes the call order; current raw evidence agrees with it.

This audit recomputed Macro-F1 from saved 12x12 integer confusions without rerunning training or heldout inference. It also checked each saved per-class support/predicted/true-positive/F1 value and that all 19 distinct well matrices sum to the aggregate. Each method contains 244176 labeled heldout rows.

| Method | Recomputed fixed-12 Macro-F1 |
|---|---:|
| Learned CNN | 0.1827348057438266 |
| TRAIN-only centroid | 0.2047004573101128 |
| TRAIN-only majority | 0.06762987587142284 |

Supports in fixed class order are [34615,20586,166742,5143,358,12188,0,0,132,3250,1162,0]. Chalk, Halite and Basement have no support in this pinned heldout split; the fixed-12 calculation still includes their zero F1. Dolomite has support 358 and zero CNN true positives. These limitations must remain visible; supported-class-only summaries cannot replace the required fixed-12 metric. The saved target status is correctly false. No post-test retraining, split change or score-based retuning was performed by this reviewer.

## One new real-fixture numerical control

The independent script read exactly the public 128-observation fixture, sequence 7327 through 7454. Every record contains only the five binding/sequence fields and four scalar values plus validity flags. It calculated normalization directly from the frozen JSON means/effective scales: identity transforms for GR/RHOB/NPHI, log10 for positive RDEP, missing value zero plus explicit mask. It did not call the author's normalization/training/runner helpers for this independent calculation. All four channels happen to be valid in these 128 real fixture observations; this real-fixture control therefore does not claim missing-channel coverage.

Direct scalar results packed as 1024 little-endian float32 values exactly equal the existing causal builder's final tensor bytes. The resulting SHA256 is d21c9ad75718dc2f8bac40d6494fe8c58f3127002388543cc30951fb277939b5, exactly matching saved runner record 127. Final sequence, complete input-prefix SHA and class index also match.

With seed 20261024 restored before constructing the recorded initial graph, all 4916 parameter elements differ from their initial values; the six per-tensor change counts exactly match the frozen manifest. The safe JSON loader read the actual frozen learned weights. Exactly one CPU model forward and softmax at the final real window returned finite 12-class probabilities, class index 2, and maximum absolute difference 0.0 from the saved actual runner probabilities. Runtime was Python 3.12.14, torch 2.9.0+cpu, four intra-op threads and one inter-op thread. This is an output consistency control, not an independent latency benchmark or heldout-quality rerun. The captured NumPy-absent warning is retained in stderr; it did not prevent the control from completing exit 0.

## Acceptance and execution limits

Preserve DEEPEYE-HUMAN-LOCK-20261014/revision1, source f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804, frozen design 1011259415a0916054eb580687612580bc1e5f09. This package remains an offline FORCE lithology component only. It is not sim_em_v2, a calibrated physical sensor model, water/obstacle detection, online mapping/planning or motion control. Real AI admission, full product cards, both complete control chains, runtime, board and system acceptance remain incomplete. Only A operates the physical board.

Reviewer writes were confined to the assigned private final/ directory. The raw argv, stdout, stderr, exit code, independent script and detailed result are retained here. No product code was edited. No archive was opened; no training, heldout inference/evaluation, author test or suite was rerun. No network, UI, peer message, subagent, Git publication, controller/service, credentials or board operation was performed.

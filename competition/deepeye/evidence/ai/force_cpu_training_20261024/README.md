# Actual bounded FORCE CPU experiment evidence

This is one new experiment; inventories found no previous trained graph or
weights. No old fit or test run was repeated to manufacture this delivery.
The retained frozen taskbook requirement is original FORCE fixed12 Macro-F1
0.60. This model achieves 0.1827348057 and **fails that target**, below the
current-point centroid 0.2047004573. No full C01/C02/C03 or useful-core-AI,
sim_em_v2, online route, physical sensor/board or formal acceptance is claimed.

`run/train-01.command.json` is the actual argv and working directory;
`run/train-01.stdout.txt` / `stderr.txt` are unedited process bytes;
`run/train-01.result.json` records actual exit 0 and their SHA256. No second
training run was launched. The model manifest and graph/source identities stayed
unchanged after the heldout result. Timing of this train/evaluation process is
not a batch1 inference latency benchmark.

Review the sequence using `recipe.json`, `pre-test-open-journal.json`,
`graph-freeze-before-optimizer.json`, `epoch-01.json` through `epoch-05.json`,
`freeze-before-test.json`, `source-open-journal.json`, `heldout_metrics.json`
and `training-result.json`. The two journals record exact source member hashes
and complete CRC reads; only TRAIN/validation are opened before freezing.
The full TEST pass covers 19 complete wells. Missing targets preserve their
positions and sensor history, and are excluded only from supervised metrics.
All confidence levels, including 25 labeled test points missing confidence, are
reported. Confidence stratum 0 means missing confidence, not a source code 0.

`causal-window-equivalence.json` compares 18 real startup/boundary windows over
three TRAIN wells with the prior causal builder, after float32 conversion.
`data-preparation-summary.json` records well/label/confidence counts and the
previously chosen fixed public input. `public_input_evaluator_labels.json` is
offline scorer data; it must never enter the online input or learned features.

`environment/` contains byte-exact installer, pip report, installed dependency
URL/hash, raw command/exit and new behavioral test evidence. Torch's wheel comes
from the official CPU download host; some dependencies used the existing USTC
mirror, with actual URLs preserved. The missing-NumPy warning is retained and
no NumPy-based code is used. New loader hardening justified the second behavior
test pass; no environment check was repeated. `authoring-diagnostics.json`
honestly summarizes the initial pre-test syntax typo and mistaken read paths
whose raw tool responses remain in task history, rather than calling that
summary raw process output.

The model artifacts and exact quality limitations are documented in
`ai_pc/cpu_model/force_v1/README.md`. Full H01–H15 and their fixed contract hash
remain in force; physical board operations are A-only.

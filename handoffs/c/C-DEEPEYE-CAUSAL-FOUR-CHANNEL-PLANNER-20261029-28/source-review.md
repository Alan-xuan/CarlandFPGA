# C28 main source review and local functional evidence

Approved scope: default-disabled, bounded pure-function candidate only.

Native EM, ADC and current own pose must be pairwise within 0.25m and 15 degrees; every suggested direction stays within the original EM forward 30-degree cone. Otherwise the candidate stops. These are candidate software policies, not physical accuracy or clearance guarantees.

17 author tests and 21 independent tests passed with actual exit code 0. The C main independently reproduced the former 180-degree failure on the exact repaired source and obtained STOP with zero direction/speed and risk=uncertainty=1 (exit 0). The original v1 independent failure (exit 1) remains preserved.

Main inspected the full candidate and contract, actual v1-to-v2 code/document/test diffs, independent test implementation and raw outputs. C28-R1 was independently reproduced before the repair and independently closed afterward. The independent reviewer exercised all original 14 checks plus seven support-policy groups, including actual 15-degree/30-degree/0.25m boundaries, yaw90/180, translation, roll and common-world-frame rotation. All 10 saved examples matched exactly. Worker completion was verified against original native session tool results and FINAL events, with no active subprocesses before ownership transfer.

Candidate SHA256: `70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4`.
Author session: `01a18676-bad1-7031-b26e-7da2ef7dc2dc`.
Independent reviewer session: `01a18686-39ad-75d3-8bb4-90836d2ac026`.
Original sole C main: `01a14025-4dfd-7ec3-aebb-57be48daba59`.
Task: `DEEPEYE-IMPLEMENTATION-20261014/version1`; operation: `C-DEEPEYE-CAUSAL-FOUR-CHANNEL-PLANNER-20261029-28`.

Public raw evidence is in `independent.stdout.json`, `independent.stderr.txt` and `author.stderr.txt`. Exact argv, exits, source pins and the main counterexample result are in `local-evidence.json`. Reproduce from this directory with `python -B test_candidate_four_channel_planner_v1.py` and `python -B independent_checks.py .`. The private v1 RED report, full v2 reviewer report, original tool records and prior source snapshots remain retained locally.

Untrained and uncalibrated heuristic; software_fixture/twin_fixture only. Actual raw4 board association, original timing/own-pose/executed-action trust, physical applicability, collision checking and both H12 chains require A integration. Final 1%/100ms and formal acceptance remain unpassed.

This delivery neither authenticates caller-supplied board identity nor issues control authority. No full-chain, physical-board, old model/training/PDE or C27 normal/negative run is included. C27 remains frozen RED; all 297 private files and five public source files were rechecked unchanged. H01-H15 and both H12 remain in force.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, fixed design `1011259415a0916054eb580687612580bc1e5f09`.

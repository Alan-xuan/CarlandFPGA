# C 3D trajectory kernel: author evidence

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`C-3D-TRAJECTORY-KERNEL-20261025-v1`, operation
`C-DEEPEYE-3D-TRAJECTORY-20261025-20`. Actual worker
`/root/cpu_package_runner`; assignment was recorded before this START. The old
CPU work was already stopped/released, and this job writes only its five new
files and this new evidence directory. No App UUID is invented; the main stays
`01a14025-4dfd-7ec3-aebb-57be48daba59`.

The unchanged design is `1011259415a0916054eb580687612580bc1e5f09`; all H01-H15
remain under `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Base HEAD is `5b237220c6ca87bdea0fbba79f8f1b379d5d4304`. `examples/stdout.txt`
records the actual requirements/kinematics/taskbook identity readback.

The actual source and conservative mathematics are documented in
`../../../ai_pc/planning/TRAJECTORY_CANDIDATE.md`. Scope is bounded pure-stdlib
software-fixture candidate generation/analytic rollout and continuous capsule
support checking, not C02/C03 acceptance, a qualified sensor map, learned
perception, whole planner, world, engine, control path, gate passage or physical
board result. Only A operates the board. All results retain
`movement_authorized:false`. No motion/model-candidate/wire bytes are emitted.

Raw runs use the actual Python3.13.5 executable:

| Directory | Actual result |
| --- | --- |
| `tests-01` | First new suites:25methods/zero skips, exit0 |
| `tests-final` | Final output-boundary hardening:25methods/zero skips, exit0 |
| `examples` | Real bounded software fixture examples and dependency hashes, exit0 |

The initial new suites passed. Subsequent self-review replaced a batch tuple
with an immutable result carrying the fixed false authorization field, and made
that field non-constructor-settable on the other outputs. The final suites
verify the resulting source. There was no actual RED result in these runs; none
is fabricated. Each raw run includes exact argv/cwd, stdout/stderr hashes and
exit code, plus the four Python source bytes **before** execution. The source
snapshot metadata makes the first and final sources distinguishable.

The25methods include positive nonempty combined-yaw/pitch candidates, independent
analytic straight/combined arcs, body signs/right multiplication under global
rotation, non-coplanar primitive sequences, acceleration target-hit integration,
zero/braking/no pivot, FAST/STRESS speed/horizon bounds,100Hz/rotation substeps,
immutable aliases/canonical inputs, stable candidate ordering and budgets,
initial/side/tail/tangent/full-body rejection, a thin contact internal to the
rollout and outside both actual endpoint capsules, independent capsule-point
support checks at five interior fractions, unknown/partial/union-only free
coverage, occupied/unknown priority and monotonic inflation.

The fullL translation-deviation proof and orientation uncertainty growth are
given in the source document. Conservative support/occupied AABB overlap only
establishes potential contact; it is not proof that the exact capsule touched.
Single-free-box coverage and AABB inflation deliberately cause false rejections.
Only entire known-free conservative support can yield
`clear_for_supplied_fixture`. Unknown, any overlap, or exhausted budget cannot
yield that result. Numerical reserves are explicit fixture engineering budgets,
with outward rounding; they are not a measured A engine/model error certificate.

The example produces9legal candidates. Its FAST20/yaw4000/pitch3000 trajectory
has final center `(0.008721109564642381,0.00654083217348179,0.24968281098843725)`
after100ticks. Complete fixture free coverage returns
`clear_for_supplied_fixture`; an empty map returns `unknown_missing_coverage`;
a supplied occupied tail region returns `conservative_occupied_overlap`.
Inputs, fixture digests, first/last supports and final poses are raw JSON in
`examples/stdout.txt`.

`source-review.diff` contains only this assignment's five new source/document/
test files. `delivery-manifest.json` binds all delivered artifacts to their
actual byte hashes; report/release remain honest about pending independent main
review. No previous CPU/Force training/held-out/broker/graph or hardware suites
ran. No Git index/commit/push, external message, new child, service, credentials,
SQL, lock, scene or board operation was performed.

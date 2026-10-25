# Bounded 3D trajectory and conservative capsule support

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`C-3D-TRAJECTORY-KERNEL-20261025-v1`, operation
`C-DEEPEYE-3D-TRAJECTORY-20261025-20`. Frozen design
`1011259415a0916054eb580687612580bc1e5f09`; all H01-H15 remain required under
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Original source base is `5b237220c6ca87bdea0fbba79f8f1b379d5d4304`.

These two new modules are pure standard-library calculation preparation. They
accept **software_fixture** inputs only. They contain no observed-map adapter,
learned model, global search, scene/truth service, gate exemption, entered or
arrived state, model-candidate or wire bytes, broker, controller or runtime
authorization. Existing C19 CPU/model, graph, broker and frozen kinematics are
unchanged. C02/C03 dependencies, qualified perception/mapping/planning benefit,
both full control paths and all formal/system/physical gates remain incomplete.
Only A operates the physical board. Fixture-clear is not permission to move.

## APIs and bounded input

`trajectory_candidates.py` defines immutable `Pose3`, `Command`, `Candidate`,
candidate generation and rollouts. Pose contains finite xyz within +/-1000m
and already normalized xyzw (squared-norm tolerance1e-12). Inputs are rejected,
never clipped or silently normalized. q/-q use one canonical sign; computed
quaternions are normalized after right multiplication to remove roundoff.
Lists become immutable tuples. Bool/NaN/Inf/lossy integers, malformed shapes,
unsupported profiles/codes and illegal curvature are rejected.

`generate_candidates` creates a deterministic Cartesian fan in sorted integer
code order, with explicit rejected in-range combinations; it never clips an
illegal combined yaw/pitch into a legal turn. It accepts at most512 Cartesian
combinations and32 legal candidates. Duplicate codes are malformed. If the
candidate budget is insufficient, status is `budget_exhausted` with no partial
candidate list. Generation source/budget/normalized inputs have a canonical
SHA256; no seed or mutable global state is used.

`Command` duration is an exact integer count of nominal100Hz ticks. Each
candidate has at most8 commands and **one profile**. Its entire horizon is at
most300ticks FAST or1200ticks STRESS. Initial speed must not exceed that
profile's maximum (FAST0.25m/s, STRESS0.002m/s). Switching profile within a
candidate is rejected; mode transitions belong to a separate runtime task.
These bounds are calculation scopes, not TTL/observation-age/grant semantics.

`rollout_candidate(pose, initial_speed, candidate, max_substeps=8192)` yields
immutable samples or `budget_exhausted` with no partial sample list. Samples
include time, pose, actual speed, cumulative/interval travelled length and
interval rotation. `rollout_candidates` sorts unique candidate IDs and shares
one <=8192substep budget. Any incomplete batch returns no partial trajectories.
Its result, single trajectory, candidate and fan all carry fixed
`movement_authorized:false` fields that cannot be enabled by constructor input.

`swept_capsule.check_candidate` accepts the original pose/commands, initial
speed and immutable `FixtureMap`, not caller-produced sample arrays. It rolls
out the canonical input internally. Maps contain at most128 identified AABBs
of `free`, `occupied` or `unknown` kind and a closed axis-aligned cube. Region
insertion order does not change the canonical fixture digest or check order.
Bounds are finite within +/-1e6m and have positive extents. Candidate/pose/map/
uncertainty/budget identity is reported through separate fixture/input digests.

The map has no automatic free default. Empty maps, missing coverage and even
free-box unions that lack a **single box containing the whole support** return
`unknown_missing_coverage`. This deliberate sufficient-only coverage test can
reject paths whose exact geometry or union coverage would be adequate.

## Dynamics and analytic arc

The unchanged `kinematics.validate_primitive`, `angular_rate_rad_s` and
`step_speed_m_s` supply legal quantized codes, reference rates and bounded
speed. No reverse, slip or pivot is added. At each nominal tick the rotation
rate upper bound uses max(current,target) speed. The tick is split sufficiently
that each substep rotates <=0.05degree; its time step is <=0.01s.

For a substep of duration h, speed v approaches target vt at a=0.25m/s².
For v!=vt, let tau=min(h,abs(vt-v)/a), signed acceleration
as=sign(vt-v)*a. Integrated travelled length is

`L = v*tau + 0.5*as*tau² + vt*(h-tau)`.

For v==vt, L=v*h. This includes target hit inside a step and the stationary
remainder of braking. It does not approximate the distance by an end-speed
rectangle or by a trapezoid when saturation occurs inside the substep.

Let body curvature u=(-k_pitch,k_yaw,0), k=norm(u), forward e=(0,0,1),
theta=k*L. For k>0 the exact constant-body-curvature displacement is

`d = e*sin(theta)/k + cross(u/k,e)*2*sin(theta/2)²/k`.

For k=0 it is e*L. The increment quaternion is
`dq=((u/k)*sin(theta/2),cos(theta/2))`; new world center is p+R(q)*d and
new attitude is **q*dq**, body-side right multiplication. Stable sin² avoids
small-angle cancellation in 1-cos. A single constant command correctly lies
in an arbitrary oriented plane. Different body primitives form non-coplanar
3D trajectories; the kernel does not invent torsion to make one arc look 3D.

## Continuous whole-body support proof

The declared center-pivot capsule has spine endpoints p+/-0.40*forward and
radius0.12m. Its total envelope length is1.04m: this intentionally encloses
the taskbook's0.80m rigid model conservatively. The enclosing body radius is
Rb=0.40+0.12=0.52m. These are fixture geometry assumptions, not measurements
of A's actual complete model or pivot.

Each substep is checked as an interval, with a separate support for initial
overlap. Fix the start attitude and translate that entire capsule along the
chord p0..p1. The support AABB bounds its two spine endpoints at each chord
endpoint, expanded by the capsule radius and all following margins:

1. **Rotation**: every body point is <=Rb from the pivot. A rotation through
   at most theta moves it by <=2*Rb*sin(theta/2). The allowance is at least
   `max(0.0005,2*Rb*sin(theta/2))` metres.
2. **Translation arc departure**: every actual center on this substep is at
   distance <=L from p0, by travelled arc length and the triangle inequality.
   Since p0 is on the chord, distance to the chord is <=L. The kernel adds the
   **full L**, deliberately much looser than a sagitta bound. Thus a translated
   Euler chord is never silently treated as the true arc, and start/end-only
   overlap is never used as the continuous check.
3. **Initial pose uncertainty**: caller center error delta_p and initial
   angular error phi are relative to the declared initial center/attitude.
   The same body-command sequence leaves the orientation mismatch at phi;
   a path point at cumulative length S has translation error
   <=2*S*sin(phi/2). Including the body, the added allowance is
   `delta_p+2*(Rb+S_end)*sin(phi/2)`. Bounds delta_p in[0,10]m and phi in[0,pi]
   ensure monotonic inflation. This does not prove A's actual pose, pivot,
   odometry history, capture timing or clocks.
4. **Numerics**: an extra caller allowance >=1micrometre (default1micrometre),
   plus `(interval_index+1)*1e-8`m accumulated reserve and32coordinate ULPs.
   Final min/max bounds are rounded outward with `math.nextafter`.

Under the declared geometry/dynamics/error budgets, every continuous capsule
point is in the support. AABB conversion only enlarges this set. Floating
arithmetic's positive extra/accumulated reserve is an explicit engineering
budget exercised on this Python double/libm implementation, not an interval
arithmetic proof for every platform/compiler or an engine numeric calibration.
Before adoption into another runtime its actual numeric/model discrepancy
must be shown within the supplied allowances. Nothing here closes that gate.

Closed occupied/unknown AABBs are tested before free coverage; tangency of the
conservative support is overlap. Optional nonnegative occupied-box inflation
only increases rejection. The entire support must be strictly inside the cube;
there are no doors or crossing exemptions. Support overlap with occupied data
reports **`conservative_occupied_overlap`**, not proof of actual capsule contact.
Unknown and boundary overlaps are similarly named. Both AABB and inflation can
cause false positives; these are potential collisions requiring rejection.

`clear_for_supplied_fixture` is returned only when every full support is inside
the closed world, disjoint from all supplied occupied/unknown regions and fully
contained by explicit free coverage. The conclusion applies only to the supplied
fixture and declared errors. Missing knowledge cannot become clear. Geometry
work is bounded by <=1,000,000 comparisons; exhausting any substep/geometry
budget returns `budget_exhausted`, no partial-clear classification or supports.

## Actual new verification

From a checkout root, with a standard Python interpreter and no third-party
dependencies:

```text
python -B -X utf8 -m unittest competition.deepeye.tests.ai.planning.test_trajectory_candidates competition.deepeye.tests.ai.planning.test_swept_capsule -v
```

The final author run is25methods/zero skips/exit0, including independent analytic
straight and combined-curvature references, body signs/global attitude/right
multiplication, non-coplanar sequences, exact acceleration/stop, actual positive
3D candidates, initial/side/tail/tangent rejection, a thin internal-trajectory
contact outside both actual rollout-endpoint capsules, and independent interior
capsule-point enclosure at five fractions of every checked interval. It also
checks unknown/default/partial/union-only map behavior, occupied/unknown priority,
monotonic uncertainty/occupancy inflation, deterministic shared budgets, canonical
digests and immutable aliases. The support enclosure checks sample interior
reference points; continuous completeness comes from the conservative proof,
not from claiming those sample points exhaust the continuum.

Raw command/log/source snapshots and examples are in
`../../evidence/ai/trajectory_candidate_20261025/`. Only the two new suites ran;
no old CPU, training, held-out, broker, graph, hardware or product suite was
rerun. Independent root/reviewer review is still required before publication.

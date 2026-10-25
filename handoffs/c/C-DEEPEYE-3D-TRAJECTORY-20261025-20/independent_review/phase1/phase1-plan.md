# Phase1 independent geometry oracle plan — completed

Work C-3D-TRAJECTORY-INDEPENDENT-REVIEW-20261025-v1, task DEEPEYE-IMPLEMENTATION-20261014/v1, operation C-DEEPEYE-3D-TRAJECTORY-20261025-20.
Reviewer /root/cpu_independent_review; main01a14025-4dfd-7ec3-aebb-57be48daba59.
Base5b237220c6ca87bdea0fbba79f8f1b379d5d4304; frozen design1011259415a0916054eb580687612580bc1e5f09.
All H01-H15 remain fixed; only A operates the physical board.

## Source basis and independence

Read the prewritten review/main assignments, original planning/kinematics.py and frozen taskbook_final CONTROL3D line138, kinematics/sweep lines200-204 and stopping/control boundaries454/471. Actual dependency SHA256 values match the assignment:
- kinematics.py770f8b4e1ff1e626df385bf220f79a8f4be8a9e9cd05c8070cd0d0dc8c01561a
- taskbook_final.md7f5c94f7fc73698236be954ae7818266d6dfe8b4949d1752dd045d76f4b71f18
- sorted compact requirements arrayc229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804, all15 IDs checked.

No new author source or tests were read/imported/executed. derive_oracles.py uses only standard-library mathematics and frozen-file hash/requirements reads; no product imports. Original tool results retain one initial incorrect simulator/kinematics git-show path (exit1), corrected using the discovered planning path, plus overbroad/truncated taskbook reads; neither was a product test or oracle failure. The actual independent oracle computation exits0 with empty stderr.

## Independent closed form

Let target speed vt use the fixed profile mapping. For vt>0, ky=yaw_q*pi/(180000*vt), kp=pitch_q*pi/(180000*vt), K=hypot(ky,kp), body curvature vector=(-kp,ky,0). Signed acceleration a is +/-0.25 toward vt. For duration T, tau=min(T,abs(vt-v0)/0.25):

s = v0*tau + (a/2)*tau^2 + vt*(T-tau).

For K>0, phi=K*s and initial local frame:
- local displacement = (ky*(1-cos(phi))/K^2, kp*(1-cos(phi))/K^2, sin(phi)/K)
- dq_xyzw = (-kp*sin(phi/2)/K, ky*sin(phi/2)/K, 0, cos(phi/2))
- world p=p0+R(q0)*local; world q=q0*dq (body-right).
For K=0 use displacement(0,0,s) and unchanged orientation. Zero target requires both angular codes0, including braking from nonzero initial speed. Rotation follows actual travelled distance, not target-speed time. A constant primitive gives a planar circular arc in an arbitrary world plane, not torsion; two successive differently oriented primitives can be noncoplanar.

## Small frozen numerical controls

Full values in phase1-oracles.json; input parameters are explicit in derive_oracles.py.

| Control | Independent expectation |
|---|---|
| fast speed20, straight, v0=.25,T2 | distance.5, position(1,2,3.5) from(1,2,3) |
| accelerate0→.25,T1.5 | distance.25, final speed.25 |
| start.249→.25,T.01 | target hit at.004s; distance.002498, not whole-step endpoint trapezoid.002495 |
| brake.25→0,T1.5 | distance.125 then hold; zero rotation |
| fast20 yaw3000/pitch4000,v0=.25,T2 | K=.3490658503988659, angle10deg, displacement(.02611354901162455,.034818065348832736,.4974653850226493) |
| same with yaw/pitch sign flips | x/y sign changes respectively; z unchanged |
| same after initial90deg world-Z orientation | displacement(-dy,dx,dz); verifies body-right multiplication/global rotation |
| accelerate under same curvature,T1.5 | distance.25 and angle5deg, not target-speed angle7.5deg |
| fast10 yaw1200/pitch1600,initial.25,T1 | distance.15625 with actual-speed angular coupling |
| stress20 yaw30/pitch40,v0=.002,T1 | distance.002 and angle.05deg; distinct profile mapping |
| pure yaw then body pitch,1s each | four-point determinant nonzero; arbitrary 3D chaining without requiring torsion of one primitive |

Phase2 target tolerances initially: position2e-9m, travelled distance2e-10m, forward/quaternion orientation2e-9 (quaternion sign equivalent). Any documented larger numerical bound must be justified against its collision expansion, not silently accepted. No frame/sample performance or physical interpretation follows from these scalars.

## Whole-volume adversaries and continuous-bound proof obligations

Capsule is p+[-.4,.4]*forward plus radius.12, center-pivot radius bound.52. Include initial central overlap, side contact away from tip, rear-body contact, tangent face contact (failure), and solid cube boundary contact. These use explicit software_fixture occupied/free/unknown AABBs only.

A quantified between-step example already generated: fast20/yaw5000/pitch0 at.25m/s for.01s (rotation.05deg), start p(10,10,10), identity q. Occupied box center(9.880972401695242,10,9.584707848786946), half-width2e-7m. At its center, capsule distance-minus-radius at start/mid/end is approximately(+5.91255e-6,-1e-6,+5.91255e-6)m. Subtracting the entire box half-diagonal leaves both endpoint clearances greater than5.5661e-6m; midpoint is occupied. Therefore a complete candidate must never call it clear. If the public geometry API rejects this resolution, retain the analytic counterexample and check the documented domain; do not silently count invalid-input rejection as demonstrated collision detection.

Continuous inclusion: for every body point |b|<=Rb, rotational displacement is bounded by2*Rb*sin(delta_theta/2) at the small substep angle. Use at least max(this,.0005m), plus separate numerical error, translation-arc deviation and finite caller pose/orientation uncertainty. Rotation term alone at.05deg is.0004537855911194633m. A chord of length within travelled arc L can use a general nearest-endpoint translation deviation bound L/2 (or the looser L): every intermediate point is at path distance<=min(prefix,L-prefix)<=L/2 from an endpoint, both endpoints lie on the chord. This is conservative without an unproved small-curvature sagitta approximation. The current circle's exact sagitta is2.7270769136177656e-7m for the.0025m step. False-positive rejection from a larger proven bound is acceptable; missing any continuous bound blocks acceptance.

## Free coverage, unknown, budgets and authority

A roomy single free AABB can supply a positive nonempty3D fixture. It is sufficient, conservative, to require the entire expanded support AABB inside one free region; no requirement to solve exact multi-box free-union coverage. Missing coverage is unknown, and occupied/tangent or explicit unknown support cannot become clear because a free box also overlaps. Expanding occupied geometry or caller uncertainty cannot create a new clear result. Zero uncertainty is only a stated exact fixture assumption, not a calibrated real pose.

After API freeze, use one deliberately insufficient valid substep/geometry budget: require explicit budget_exhausted and no optimistic clear classification for an unchecked suffix. Check finite input rejection (bool/NaN/Inf, invalid/un-normalized quaternion/codes), no clipping, deterministic ordering/digests and immutable input/result ownership with small controls only. These remain planned until phase2; no author API or new implementation was inspected to formulate them.

Every result must retain movement_authorized=false with no motion/model_candidate/wire bytes or entered/arrived interpretation. No real observed map, sim_em, learned policy, global search, gate passage, full control chain, runtime, C02/C03 or formal product acceptance is established.

## Phase boundary

Phase1 source pinning, derivation and oracle recording are complete. No active reviewer jobs remain. End this bounded turn; do not model-poll or idle-loop. Only the main's later exact author freeze/release followup triggers phase2 code/black-box review. Phase2 and overall acceptance are not complete.

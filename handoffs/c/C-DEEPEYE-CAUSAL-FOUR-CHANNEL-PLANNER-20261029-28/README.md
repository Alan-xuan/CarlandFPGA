# C28 four-channel causal planner proposal

`candidate_four_channel_planner_v1.py` is a directly importable, deterministic
stdlib function for candidate perception, causal own-position risk memory and
finite three-dimensional goal planning. It produces advice only. A owns actual
board association, trusted timing/odometry, full-volume collision, control,
source scheduling and both H12 modes. There is no world, filesystem, network,
process, clock, controller, FORCE model or hardware import.

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`; work
`C28-FOUR-CHANNEL-PLANNER-IMPLEMENTATION-20261029-v1`; operation
`C-DEEPEYE-CAUSAL-FOUR-CHANNEL-PLANNER-20261029-28`. Contract
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
fixed design `1011259415a0916054eb580687612580bc1e5f09`. All H01-H15,
both complete H12 paths, final1%/100ms and formal acceptance remain unchanged
and unproved by these local controls. Old C27 and old tests are untouched.

## API and explicit proposal boundary

`recommend(request: dict) -> dict` and `recommend_json(raw: bytes) -> bytes`
perform no I/O or side effects. `Rejected(ValueError)` means a malformed,
contradictory or over-budget request. A structurally valid but unusable current
sample returns STOP with a reason. `enabled` must be explicitly present;
the supplied default example has `false`. Only explicit true enables advice,
never execution. Omission is rejected, so an omitted option cannot enable.
JSON rejects duplicate keys, foreign types, bool-as-number, nonfinite values,
unknown fields, excessive depth and all hidden-layout/oracle extensions.

`interface-examples.json` contains synthetic local fixture inputs and actual
local function outputs. Its repeated letter hashes are deliberate dummy
labels, never board receipts or production IDs. The wrapper labels examples;
only its nested `request` is passed to the strict API.

Request exact keys: `schema_version,enabled,binding,now_tick_ms,pose,goal_m,
observation,history,executed_actions`. Version is1. `pose` and historical poses
contain exactly `position_m` (three metre values, absolute<=1000) and
`orientation_xyzw` (four finite values, squared norm within1e-12 of1).
`goal_m` is the authority-approved legal goal, not obstacle geometry; its
legality cannot be independently established by this function. Goal proximity
returns STOP requiring authority completion, never gate/traversal success.

Binding exact keys: `run_id,build_sha256,boot_sha256,session,config_epoch,
clock_domain,source_id,source_mode,profile_id,producer_sha256,topology_id`.
Source ID4 remains `software_fixture` in A's enum; the distinct outer source
mode remains `twin_fixture`. Profile is exactly
`deepeye_forward_profile_candidate_v1`, with pinned producer source hash from
`producer-contract.json`. Topology1/2 preserves HIL/PC-direct. There is no
invented acquisition-profile ID or claim this is em_surrogate_v2/sim_em_v2,
real ADC or FORCE8. Every history/action binding must equal the request binding,
including the same build/session/BOOT/time domain. Labels are1..96 ASCII bytes;
hashes are64 lowercase hex. These are supplied byte identity references, not
authentication. Numeric session/epoch preserve uint32/uint8 bounds.

Observation exact keys: `binding,sample_id,trigger_id,sequence,
board_frame_sha256,source_record_sha256,adc_tick_ms,em_tick_ms,
em_origin_sample_id,counts,quality,adc_pose,em_pose,cause_action_id`.
Original sample/trigger labels and uint32 sequence are preserved verbatim.
The adapter supplies original raw-frame/source-record SHA references without
rewriting the acquisition's original identity. No `board_verified` boolean,
fixture label, hash value or enabled flag proves actual acquisition. A must
establish original board return, source association and trigger/sample mapping
outside this function before using advice in a real chain.

All times are exact original millisecond integers0..2^31-1 in the one named
source-clock domain; `now_tick_ms` must be supplied by A's trusted mapping in
that same domain. It is never frame receipt time. Future ADC rejects; current
ADC/original EM age greater than100ms returns STOP; exactly100ms is allowed.
An unavailable source clock/identity must not be filled with a receipt or zero.
Missing required identity/time is rejected or, for legitimately faulted null EM,
STOP. This proposal does not install clock synchronization or a watchdog.

`history` is an oldest-first array of this identical observation shape. Native
EM records bind their own sample_id and adc_pose. A held record must find that
original sample in retained history, with unchanged EM counts, saturation and
em_pose; the immediately prior observed EM identity must still match, preventing
revival after fault. No replay/dedup ambiguity: duplicate sample IDs, sequence
or ADC reversal reject, including an exact duplicated record. History eviction
is explicit caller work; a held origin cannot be evicted while still referenced.
Sparse native history is permitted; it does not claim a complete ADC stream.

Actions contain exactly `binding,action_id,observation_sample_id,at_tick_ms,
from_pose,to_pose`. These are only the caller's already executed displacements,
not proposed/unacknowledged actions. Their sample cause must be retained and
no later than action time. Action times are nondecreasing and no later than now.
An observation with a cause_action_id requires that action strictly before its
ADC sample, preventing temporal cycles. Null cause is allowed for samples with
no declared executed-action cause. Structural consistency is not proof of actual
execution; A supplies that association. The last executed displacement gives
a small penalty to directions which undo it.

## Actual producer semantics

Producer `forward_profile.py` at A PR24 head
`5c192f34bad064b14e238747c2c569347257a62c`, SHA256
`6a5f70a6acdaa6de52fc72d678d452956861370e1d143b70219ced107c5a04c9`,
uses four normalized12-bit counts0..4095. The producer's exact nine-field
record and the existing host schemas remain untouched. This new proposal
selects counts/quality and externally associated original times/identity.

| Channel | Quantized inverse centre | Meaning |
|---|---|---|
| C0 | `log10(0.2)+4*q/4095` | Forward apparent log10 resistivity, numerical ohm m |
| C1 | `-2+4*q/4095` | +yaw minus -yaw log10 resistivity |
| C2 | `-2+4*q/4095` | +pitch minus -pitch log10 resistivity |
| C3 | `2*q/4095 g` | Ten-sample trailing contact/load vibration RMS |

Forward mapping is Python ties-to-even round of the normalized4095 scale.
Half-bin uncertainty is2/4095 for C0-C2,1/4095g for C3. A zero count is a value.
2047/2048 straddle zero for differential channels. Endpoint count alone does
not imply saturation. Inverse centres are estimates, not original floating
values or calibrated DAC/XADC signals. No lossy compression error is accepted
implicitly; A must provide exact reconstructed producer counts or separately
review a new bounded-error contract before adopting a lossy transport.

Body +Z is forward, +X right, +Y up. Positive C1 means right more resistive;
positive C2 means up more resistive. Original `em_pose` determines these axes,
even if the drill moved/rotated since acquisition. These signals are spatially
integrated responses, not obstacle locations, clearance or material labels.
C3 reports already-occurred contact/load, not a future collision query.

Original observation reuse is additionally gated in the v2 support repair.
The native EM, current ADC and current controller own poses must satisfy BOTH
conditions for every pair: Euclidean position separation<=0.25m, and angle
between their forward +Z axes<=15degrees. Comparing all three pairs avoids
accepting opposing offsets around the native pose. The angular dot comparison
normalizes both axes and permits1e-12 numerical cosine tolerance only. Roll
around a shared forward axis is permitted: it changes coordinate components,
not the forward observation direction. Exceeding either bound returns STOP,
`original_observation_pose_inapplicable`, risk=uncertainty=1 and zero speed/
direction; original historical map poses and identity are retained.

The0.25m displacement bound is an explicit candidate engineering reuse limit
of one planner trial length; it is not derived from the producer's8m cropped
kernel, not an observed clear region, not a speed/pose-error qualification and
not evidence that signals remain accurate under that displacement. The15degree
forward-axis reuse bound is likewise deliberately restrictive software policy,
not vendor calibration. They merely reject plainly unsupported reuse; A must
establish a justified physical/odometry applicability bound before real control.
The gate applies to fresh and held records alike, including a stale-position
current controller pose paired with a fresh ADC/native pose.

Quality is the producer namespace: bits0..3 valid,4..7 saturated,8..11 held,
12 source_fault,13..15 zero. Board summary grants must not be silently imported
into it. EM C0-C2 validity is all-or-none; source_fault iff all EM invalid.
Invalid channels carry null counts and clear saturation/held. Invalid EM has
null original time/pose/id; C3 can remain valid. C3 is never held. Saturated EM
requires endpoint counts. C3 saturation can be below2g: at least one clipped2g
sample implies RMS>=sqrt(0.4), allowing its half-bin rounding interval.
Both valid saturated and valid source-fault records are conservatively STOP
advice, not mislabelled malformed producer records.

ADC grid10ms, EM grid50ms. EM source age0..100ms; all three held bits iff age>0.
C3 cannot be valid before90ms. A's source/board adapter remains responsible
for verifying the complete ten-sample contiguous RMS support; sparse planner
history cannot certify it and does not invent missing rows. All channels must
be valid, unsaturated and source-fault-free for advice. Legal startup invalidity
returns STOP. Held current samples may advise while retaining original age.

## Candidate perception, memory and goal search

This is an explicit untrained heuristic, not calibrated material perception.
The provisional preferred apparent log10rho is1 (10ohm m); low and high
deviations both raise risk. It cannot label water or rock, prove free space or
inherit FORCE performance. C0 supplies baseline contrast; C1/C2 materially
alter direction; C3 slows or stops. No input supplies hidden geometry.

Only clean native observations (`quality==15`, ADC==EM tick) create own-position
risk cells: `clip(abs(C0-1)/2+C3/2,0,1)`. Held records add no cell and never
reduce uncertainty. Cell poses are the original historical EM poses, not current
pose. These are a bounded causal risk memory of visited poses, not exact hidden
occupancy. Old cells conservatively retain their recorded risk.

Nine current-body directions normalize `(x,y,1)` for x/y in{-0.35,0,0.35}.
Each is transformed into world and then original EM body frame. Candidates
without positive dot product toward the goal are rejected. Each candidate
must also lie within30degrees of the original EM forward +Z axis (normalized
dot>=cos30 minus1e-12 numerical tolerance). This uses the central candidate
beam's angular envelope as a conservative subset; it does not expand to the
union of offset lobes, an opposite hemisphere or a hypothetical newly sensed
position. Even an admissible current forward axis cannot make an out-of-cone
lateral candidate eligible. Predicted apparent
logrho is `C0+0.5*(C1*native_x/0.35+C2*native_y/0.35)`. This lobe interpolation
is a candidate assumption, not a validated inversion. Candidate risk is
`clip(abs(predicted-1)/2+C3/2,0,1)`. Visited-cell risk cost is the maximum
`cell_risk/(1+distance_squared)` at a0.25m trial endpoint. Cost is
`1-goal_dot+2*risk+0.2*map_cost+0.1*undo_last_executed_displacement`.
Deterministic ties prefer smaller total lateral magnitude, then x, then y.

Uncertainty is `clip(0.5+0.4*original_EM_age/100+2/4095,0,1)`; the high base
marks the candidate model ambiguity and cannot fall with held repetitions.
It is an engineering score, not a statistical confidence interval. Risk>=0.8,
C3>=0.8g, no forward goal progress, unusable quality/time, disabled mode or goal
within0.02m yields STOP. Otherwise speed limit is
`0.25*(1-risk)*(1-uncertainty)*min(1,goal_distance/0.5)` m/s. This is a proposed
speed ceiling/direction, not a legal quantized motion primitive or collision
proof. A must respect curvature/acceleration and authority checks before action.

Output includes original observation unchanged, risk/uncertainty, bounded map,
independent EM count, direction_world, speed_limit_m_s, reason, status and
`authorization="none"`. STOP direction/speed are zero. Existing host
`model_candidate` cannot receive these extra fields; A decides an adapter.

## Bounds, integration gap and verification

Combined past observations+executed actions+current observation<=32; map<=32
cells (below requested256); exactly9 direction trials and at most288 map-cost
evaluations. JSON input<=262144bytes; direct objects<=16000 nodes, depth<=10,
strings<=192, arrays<=32, keys<=96. No hidden retained state, caching or threads.

Current TELEM carries means/ranges, EVENT a single peak, and cannot reconstruct
these four original samples. Existing offline TRACE preserves per-channel
source ticks but A's pinned production wire still rejects type7. This source
does not close the actual board grouping/quality/time/receipt association gap.
It can be imported and locally tested independently; actual integration requires
A's trusted adapter and original evidence. No full-chain, physical, model
qualification or formal numerical acceptance is claimed.

Only the new `test_candidate_four_channel_planner_v1.py` unittest file runs.
From this directory: `python -B test_candidate_four_channel_planner_v1.py`.
The private author evidence preserves exact five-file snapshots, command,
stdout/stderr, exit status, hashes and actual same-goal contrasting outputs.
New controls exercise signs in3D, held poses and dedup, original100ms boundary,
quality/null/saturation, both H12 labels, goal changes, disabled mode, strict
JSON, binding/causes and resource rejection. They prove local function behavior
only. Main independent source review precedes Git delivery.

The v2 controls also cover held yaw180/yaw90 rejection, inclusive15degree and
0.25m software boundaries, out-of-bound cases, all pose pairs,10m translations,
roll-only support, small legal moves and per-direction original-cone checks.
The original v1 source and failed independent R1 evidence are preserved in
private immutable evidence. The unchanged independent C28 reproducer is rerun
against the repaired pins; this is a new local execution, not a retroactive pass
for v1 and not an independent reviewer approval of v2.

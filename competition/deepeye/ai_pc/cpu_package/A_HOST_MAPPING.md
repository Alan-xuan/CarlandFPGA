# C CPU observation, inference and broker boundary

DEEPEYE-IMPLEMENTATION-20261014/version1; work C-CPU-CAUSAL-PACKAGE-20261024-18.
H01–H15 remain fixed by DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements
SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09. A alone operates the board.

A's actual priority response is [6384117078](https://github.com/carolwjade/CarlandFPGA/pull/24#issuecomment-6384117078).
The exact A interface reference is
[5c192f34bad064b14e238747c2c569347257a62c](https://github.com/carolwjade/CarlandFPGA/tree/5c192f34bad064b14e238747c2c569347257a62c/competition/deepeye/docs):
host_contract.json, host_timing_contract.md and pc_direct_runtime.md.
C inspected the raw host schema/envelope and current opaque CPU transcript;
A has adopted no C executable or CPU inference format. This document proposes
no change to A's public ABI, authority, activation factory or simulator.

## Actual bounded result

The package performs learned twelve-class FORCE lithology inference from four
real public well curves plus four validity masks, strictly trailing128positions.
It is an offline geo_replay / force_curve_v1 component. The fixed real stream
has128records from TRAIN well15_9-13, rows7327–7454. Labels/confidence and upstream
well metadata are evaluator/provenance files, never fields in online input.
Each process starts with missing-history masks; it does not read earlier or
future well rows from an archive. The supplied inference command requires no
archive, labels, training cache or scene truth.

The last recorded decision has latest_sequence7454, record_index127,
predicted_class_index2 (Shale), probability0.7047013640403748, and tensor SHA256
d21c9ad75718dc2f8bac40d6494fe8c58f3127002388543cc30951fb277939b5.
This is a lithology inference, not a water/obstacle coordinate or motion target.
CNN heldout fixed12Macro-F1 is0.1827348057438266, below the frozen0.60 target and
below the centroid baseline0.2047004573101128. Its use as useful core control AI
is unaccepted; C02/C03 and the remaining model/map/planner work remain open.

## Exact field and time mapping

|C package field/source|A observation / decision / broker meaning|Current disposition|
|---|---|---|
|Input run_id/source_domain/profile_id/preprocessing_sha256|C public replay binding|Exact parser binding only; not A session/config_epoch/BOOT/source identity|
|Input sequence; predictions[].window.latest_sequence|Original public well row acquisition order|Not a source tick or milliseconds; not an authenticated board observed_seq|
|predictions[].input_prefix_sha256|Exact original JSONL byte prefix consumed for that decision|Evidence of the selected bytes, not proof of sender/OS provenance or source liveness|
|predictions[].feature_tensor_sha256|Actual float32 little-endian C-order [1,8,128,1] tensor|Model input identity; no raw labels, coordinates or future fields|
|predictions[].probabilities and predicted_class_index|Actual learned perception output, fixed12class order|No target action/yaw_q/pitch_q/speed_code/duration_ms is generated|
|pins.model_manifest_sha256|Proposed future model_sha256 registry identity|Binds graph+weights+scaler+class schema. A must explicitly approve this interpretation and a suitable model; the weight-only hash is separately recorded|
|timing.clock=perf_counter_ns and stage/forward durations|C same-process elapsed measurements|Not observation age, completion timestamp, shared QPC binding, source tick, holdover/error bound or a consumption window|
|movement_authorized=false; motion_bytes=null|Broker/authority boundary|No motion adapter, permissive verifier, BOOT/STATE or raw board frame is fabricated|

The offline result has no valid A model_candidate: candidate_id, A context,
trusted sent-observation association, qualified source-age/clock mapping,
completed_monotonic_ns and a legal motion target are not provided. C cannot
fill these from arrival time, wall time, feature durations or hidden authority
logs. A's current InvocationTranscript records one <=16384byte opaque request
and finite OS output; it does not adopt the JSONL/result schema or grant control.
The fixed file can be passed to this CLI by a locally verified path/hash; it
must not be silently embedded as an oversized private request or treated as an
A production-channel factory. No repeated benchmark renews an observation,
original command TTL, heartbeat or grant window.

For a future live adapter, C must consume the actual legal TELEM/EVENT observation
and context, preserve original observed_seq and conservative sampling bounds,
produce a qualified domain model/policy result and map it to model_candidate.
The existing C non-authorizing broker/mailbox and MotionRequestAdapter remain
separate. Their actual runtime verifier and A's stateful authority must enforce
original deadlines, STOP retirement and source/clock/liveness/capture/slot gates.
A should choose any format/identity/time-binding changes explicitly. Existing
forward/source diagnostic records, truth, editor data and board_response are
not a replacement AI input channel.

## Reproduction and remaining work

README.md supplies the one CLI command and device selection. The fixed model
manifest SHA256 is0b76bcd1b21b6b1e254eef0e2e5815a15121fdb8ac48c33710f2b2d85bdf2959;
input SHA256 isd81b29a6200d83133eda22149c70d2a0f6b3db06f9885ae669ddaffc75e99b37.
The recorded CPU output SHA256
e84bdfe850efb8a231f72c98a5fb05cc20c7f6036014f4db77ef3f6cf44b418f
identifies one actual run, including its original timing arrays. A later run's
timing bytes naturally differ; compare the exact feature/class/prediction fields
and report numerical differences separately. C did not execute A's HIP device
or promise identical floating output across Torch2.9CPU and A2.12HIP.

C still owes a suitable separately trained sim_em_v2 model/scales, substantive
causal map updates and online constrained3D planning/policy. FORCE does not
supply those or validate sensor physics/water risk. A/B source/profile/units/
clock/grouping/BOOT and real-PL observation contracts must be bound for the live
path. Missing final ADC, public TRACE or full hardware does not block this
bounded offline package. Neither this package nor a backend run closes full
C01–C05/G04/G06, H11/H12, all29cards, R03, board or system acceptance.

# Host timing adapter, revision 1

Owner: A main. Implementation task DEEPEYE-IMPLEMENTATION-20261014/v1.
Design input: 1011259415a0916054eb580687612580bc1e5f09, taskbook sections 4/8 and simulation_contract_final.json.
Human contract: DEEPEYE-HUMAN-LOCK-20261014/revision1; H01-H15 canonical SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804. No scope change.

This document freezes software arithmetic and transport provenance. It supplies no measured USB latency, oscillator drift, physical capture validation, sensor calibration, or permission to ENABLE. Those measurements remain not_run. Missing bounds produce an unknown sample time and prohibit an executable motion grant.

## Time domains

Host timestamps are nonnegative integer monotonic nanoseconds from one process clock domain. They are never wall-clock strings. Session/profile changes invalidate anchors, observations and grants. Each timestamp carries the session and complete BOOT profile SHA256; receipt alone does not establish sample freshness.

TELEM.header.tick_ms is the final included ADC sample acquisition tick. EVENT.header.tick_ms is the trigger sample acquisition tick. ACK/STATE header ticks identify first-byte transmission, not a newly acquired observation. Heartbeats, ACK retries and STATE traffic cannot update an observation's acquisition interval or observed_seq.

The board tick is a uint32 floor-millisecond counter. Unwrap only relative to a same-session anchor, with a separation strictly less than 2^31 milliseconds. Exactly half-range is ambiguous and rejected. Counter extension does not establish oscillator synchrony. Delayed samples may precede an anchor; an old or regressing anchor cannot replace the active anchor. New sessions require new anchors.

## Bounded anchor

An anchor is obtained only from a validated frame whose tick is the first-byte transmit tick, together with the host interval [r_lo,r_hi] in which the final received byte became available. It requires measured nonnegative bounds d_lo,d_hi from first-byte transmission to that receipt interval, including the ENTIRE 8N1 frame, physical baud tolerance, USB buffering, bridge/read processing and timestamp uncertainty not already in [r_lo,r_hi]. Bounds refer to the selected transport/profile and complete BOOT hash. No percentile may be used as a hard upper bound.

Let q_hi be a conservative upper bound on the host duration of one board millisecond, including fractional tick quantization and oscillator uncertainty. The host interval of the anchor's floor-millisecond boundary is:

    a_lo = max(0, r_lo - d_hi - q_hi)
    a_hi = r_hi - d_lo

Reject a_hi < 0, a_lo > a_hi, invalid integer types (including booleans), unmeasured bounds and mismatched identity. A negative candidate lower bound is conservatively clipped to monotonic epoch zero; this cannot make an old observation younger.

For a sample tick separated by signed delta_ms, nominal delta_ns = delta_ms * 1_000_000. A measured relative-rate bound p in parts per million is defined here as |actual_elapsed_host_ns - delta_ns| <= ceil(abs(delta_ns)*p/1_000_000). It is NOT an unconverted crystal tolerance in board seconds. Include synchronization uncertainty and holdover effects in the measured interval/rate bound; expire the anchor at a bounded age. The sample interval is:

    e = ceil(abs(delta_ns) * p / 1_000_000)
    sample_lo = max(0, a_lo + delta_ns - e)
    sample_hi = a_hi + delta_ns + e + q_hi

Adding q_hi covers the unknown position of the acquisition within the floor tick. Reject a negative upper bound, empty interval, unbounded holdover, a future lower bound beyond current host time, or identity mismatch. A sample upper bound extending slightly into the future is uncertainty, not proof of a future sample; use the lower bound for all age/deadline checks. Source injection separately rejects samples generated after injection time.

No number is currently supplied for d_lo/d_hi/p/q_hi or permitted anchor holdover. The software reference accepts explicit validated test fixtures; runtime callers require an independently verified measurement record bound to operation_id, request_hash, tested_commit, profile and tool/board evidence. A caller-provided boolean is not measurement authentication.

## Observation windows

At 100 ADC samples/channel/second, FAST uses 50 actual samples and STRESS uses 800. First-to-last nominal span is (N-1)*10ms: 490ms or 7990ms, NOT the frame receipt time and NOT N*10ms. Derive the start interval using measured sample-period bounds; missing samples or quality/source faults remain explicit. Assign historical odometry over this acquisition interval; do not use current viewer truth pose. Native 20Hz EM update time remains null unless a separately verified source-phase mapping exists. Held bits alone do not identify that update time.

## Expiration

Observation expiration uses sample_lo + age_cap, with age caps 1500ms FAST and 12000ms STRESS for both required topologies. Reject future sample_lo and clock regression. All arithmetic is integer and rounds delays/errors upward. The deadline never increases for the same command.

For HIL:

    deadline = min(first_send_ns + original_ttl_ns,
                   receipt_ns + max(0, remaining_ttl_ns - frame_serial_upper_ns
                                       - usb_processing_upper_ns - clock_error_upper_ns),
                   sample_lo + observation_age_cap_ns,
                   previous_deadline_ns if present)

Each delay component must have a documented non-overlapping meaning. A response with unknown terms is not usable. first_send/original_ttl are immutable across retries. ACK accepted/applied are insufficient: current session, matching request_type/seq, valid capture, faults and current profile are also required by authority. A deadline at or before now grants no motion.

PC_DIRECT uses min(host_issue_ns + bounded_duration_ns, sample_lo + age_cap, previous_deadline if present). It still requires actual FPGA observations for the formal chain; there is no fictional board motion ACK/capture. STOP requires no fresh observation. A heartbeat never extends any command or observation deadline.

## Local process boundary

host_contract.json is a strict whitelist for transport envelopes, with additionalProperties=false at every object boundary. Runtime validation additionally enforces the cross-field rules in this document and enums.json. JSON validation alone does not prove process/ACL isolation, model usefulness, calibrated sensing or either complete control chain.

world_authority alone issues motion grants and integrates physics. ai_controller supplies candidates; hardware_bridge supplies received framed observations/capture facts. No controller pipe admits obstacle identifiers, layout/seed/editor history, exact collision queries, future sensor values, screen access or a hidden-map route. Public task geometry contains only cube/drill, chosen gates and uncertain initial odometry. Both HIL and PC_DIRECT remain required.

The bridge-to-authority `board_response` envelope transports the exact bounded ABI3 STATE (0x08, 32 bytes), CONFIG_ACK, GAIN_ACK, BOOT_ACK, ACK3D or STATE3D bytes and receipt interval, plus nullable measurement-record SHA256 references. It is not available to ai_controller and never itself authorizes motion. Authority reparses CRC/type/length/session/epoch and binds the original request and capture history. BOOT_ACK uses the proposed stopped-state context until exact handshake verification succeeds. Nullable measurement references are explicit unknowns; nonnull hashes still require independently authenticated records.

STATE 0x08 carries physical GAIN or PC_DIRECT clock/health diagnostics using the frozen 18-byte payload. Its capture-shaped fields never authorize three-axis movement. PC_DIRECT STATE requires a null physical motion-capture reference. Fault/phase changes are delivered to authority, which stops when required; STATE never creates an observation, changes its acquisition time, or renews any command deadline. A missing heartbeat remains a separate runtime stop gate; structural parsing is not proof that a live board is present.

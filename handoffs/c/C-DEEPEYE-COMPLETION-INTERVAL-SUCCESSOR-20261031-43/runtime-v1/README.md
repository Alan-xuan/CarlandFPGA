# C43 opt-in completion interval successor

The original A source is fixed at 42f3de654aef3d52300ae1cfb16e3ac512ea2cea. The three provided source files and the two explicitly authorized wire.py/motion.py dependencies are pinned in input-pins.json. No deployed A/C file is changed. `patched/` is a private review/test tree. The distribution delta is completion_interval.py, completion_interval.schema.json, host_envelope.py.patch and this specification; baseline/ and dependencies/ are evidence, not an alternate deployed runtime.

## Concrete APIs

The minimal host patch adds keyword-only `enable_completion_interval=False, completion_bounds=None` to the original validate_message. Default calls continue the original body; no successor module is loaded. An enabled call lazily loads the new sibling and uses its v2 branch:

```
checked = host_envelope.validate_message(
    original_candidate_bytes,
    producer=original_producer, context=original_context,
    now_ns=original_host_now, consumer=original_consumer,
    enable_completion_interval=True,
    completion_bounds={
        'max_age_ns': original_candidate_max_age_ns,
        'source_deadline_ns': original_source_deadline_ns,
        'dispatch_deadline_ns': original_dispatch_deadline_ns,
        'previous_deadline_ns': original_previous_deadline_or_None,
    })
```

The standalone adapter is `completion_interval.validate_message(raw_bytes, *, legacy, producer, context, now_ns, consumer=None, enable_interval=False, bounds=None)`. `legacy` is the actual original host module, not a JSON proof label. Its default forwards to the exact scalar/v1 entry. The new opt-in branch takes only schema_version=2/kind=model_candidate. It never temporarily synthesizes completed_monotonic_ns to trick the old candidate checker.

New wire fields replace the scalar: `completion_observed_interval_ns:{lower_ns,upper_ns}` and `basis:'host_dispatch_to_complete_result_observed_v1'`. All other fields, observation/context/target definitions, enum types and producer/consumer restrictions remain those of the pinned original. Every original definition is retained verbatim structurally in the successor schema; only a new model_candidate_interval definition and root selection are added. The old JSON schema file is unchanged. Runtime regenerates the same schema from the pinned canonical original schema; the separately saved new JSON is its exact equivalent.

## Original timing bounds and expiry

Lower is the actual original host observation before request dispatch; upper is the actual original host observation after the entire RESULT was observed. Both must be in the same original fixed host clock. They are uint63 integers, never booleans/floats; `lower<=upper<=now`. This interval is not an exact CPU-finish measurement. Actual provider/pipe/process/transcript/source association belongs to A; serialization and the legacy module call contract authenticate nothing.

The bounds dictionary must have exactly all four keys. max_age_ns is an integer1..100000000. Original source and dispatch deadlines must be supplied; None is Unavailable, not infinity. previous_deadline_ns must be explicitly supplied as an original integer or None only when no previous deadline exists. Missing keys are rejected. Checked uint63 addition refuses lower+max_age overflow; it does not wrap, round or silently saturate.

```
valid_until_ns = min(lower + max_age_ns,
                     original_source_deadline_ns,
                     original_dispatch_deadline_ns,
                     original_previous_deadline_ns if present)
```

Admission requires valid_until_ns>now. This is an exclusive deadline, matching the existing timing contract's rule that a deadline at or before now cannot support motion. Thus at the age expiry point no residual validity is granted, even though an unrelated source-age consistency check may include exactly100ms. C28/C40 source checks are unchanged. A later upper bound, process survival, initialization event, READY, reconnect or retry cannot move this deadline. Bounds are retained in the immutable checked result for downstream review. Missing evidence does not become a fallback scalar.

The new result is a frozen IntervalCandidate with recursively immutable original document, valid_until_ns, validated_at_ns and bounds. It is consistency data, not ValidatedMessage authority, _CompletedInference, registration, BOOT or a motion grant. Caller creation of the dataclass is not evidence; the original provider must retain the actual validator result and live association.

## Concrete provider / PC_DIRECT handoff

After the real C41 pair verifier and original provider bindings pass, A's original provider serializes its real candidate_id/model_sha256/context/observation/target with the two observed bounds and fixed basis. The code above validates this explicit v2 document. No identifier or successful receipt is derived here. The finite downstream adapter is implemented, not deferred:

```
finite = completion_interval.adapt_action_candidate(
    checked, host_issue_ns=original_issue_ns,
    now_ns=original_host_now,
    previous_deadline_ns=original_action_previous_deadline_or_None)
```

The adapter requires issue>=checked.validation_time and issue<=now. For SET_TARGET, it preserves the exact existing target and computes issue+target.duration_ms*1000000 with checked uint63 addition. The entire requested duration must fit within the checked interval/source/dispatch/previous caps AND the explicitly supplied action previous deadline. Otherwise it returns Unavailable; it never silently truncates duration or refreshes from upper. It returns the original immutable candidate plus host_issue_ns and the finite requested end as deadline_ns, with authority='none'. The original authority/PC_DIRECT path must still apply its normal live source/observation/BOOT/run/fault/collision/command-consumption checks and take the minimum with its actual current PC_DIRECT/HIL bounds. No motion_request, command_seq, grant, owner registration or runtime state is synthesized.

STOP retains the original requirement of zero yaw/pitch/speed/duration and may use null observation. The checked v2 candidate still needs its stated interval bounds at validation. Adapting that STOP produces deadline_ns=None: no positive lease or motion duration, even if subsequently used to request stopping after the candidate expires. Original STOP channels and scalar/v1 behavior remain available and unmodified by default.

## Evidence and integration limits

NEW changed-path controls cover strict v2 schema, original producer/context/observation/motion gates, scalar default compatibility, exact uint63/overflow/order, each original cap/missing distinction, nonrenewal by upper, exclusive expiry, immutable returned data and finite requested duration/STOP handling. They do not run old suites, planner/core/model/PDE, native actors or a board.

The first test attempt (run01) exited1 on ModuleNotFoundError: jsonschema before collecting/running any method. This is a dependency failure, not a product RED. Dependencies are prepared only under this task's private dependencies tree with explicit main authorization, leaving global/venv state unchanged. The first dependency download timed out15s; inherited pip extra-index settings also caused unintended mirror lookups. Its full stdout/stderr/log is retained, no wheel was retained or installed from it, and it must not be counted as an official-only successful preparation. Any corrected isolated attempt is recorded separately.

A's reported C40 native exit65 is not diagnosed here and is not evidence of a numerical/package defect. A owns its current native startup and pair-transcript qualification. No original A process, handle, board, service, SQL, credentials or public repository is operated by this task. H01-H15/design/final acceptance remain fixed and unaccepted.

Final dependency/test outcome: main authorized a corrected isolated attempt after the confirmed pip configuration leakage. attempt02 removes child PIP_* variables, sets PIP_CONFIG_FILE=os.devnull, fixes the official PyPI index and exact five versions, disables retries/cache, then installs offline with --no-index --find-links into a fresh private target. Download25s and install15s bounds both completed exit0. Original URLs and wheel SHA256/version records are dependencies/attempt02/resolved-wheels.json. jsonschema4.23.0, attrs24.2.0, jsonschema-specifications2024.10.1, referencing0.35.1 and rpds-py0.20.0 are test dependencies only; the latter uses its ordinary Python extension, not an original actor/native control API. No global or existing venv was modified. The failed first mirror-inheriting attempt was not reused.

run02 executes all11 NEW methods with the explicit vendor directory inserted into sys.path under -I/-B: exit0. Original runtime SHA05da98393d47f3eaf4690d8979d2e37d2e4f1e0b00c801177a3fb6a3f84bbe96 and patched host SHA20b2221491825964f91381f68053a13bf3867347d35896ce1dd132c4a8972c3b stayed identical across run01(dependency missing,0methods) and run02. No product RED, blind replay or old test group. A separate static audit checks exact retained old function bodies, old schema bytes and complete delta layout; it is not a functional/model test.

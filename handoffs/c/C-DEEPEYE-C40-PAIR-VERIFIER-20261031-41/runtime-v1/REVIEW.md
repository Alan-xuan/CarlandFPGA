# C41 independent pure pair-verifier review

**Pass within the declared consistency-only scope; no source blocker found.** Source approval is not proof of original process/source identity, planner execution, CPU completion, freshness, BOOT or movement authority.

Input FINAL SHA-256: `adcc6e6e3bbc72c47e92dfea5b4f7cd45d275ec4f19421183d62abd8da966d66`. Final verifier: `fc00cd1441e0dc15a092e601bb2864419e19ca688ba508c0b5a52faee429dd9b`. Thirty-two artifact/source pins were verified, including the frozen C40 package/core/manifest. All 28 claimed copied definitions independently match the pinned C40 AST. The original A39 comment 6531554988, author numeric ID 328016885 and original JSON-body hash were checked from the saved authenticated response. No network or old-source execution was needed.

## Exact admitted scope

Lines 385–403 validate the caller's exact six IDs and fixed manifest pin, the complete canonical padded C40 outer request, correlated request IDs, exactly two bounded response frames, expected order/ABI/IDs, exact padded-wire hash, fixed core pin and authority fields. Early null-ID or invalid outer-envelope diagnostics are outside admission and rejected, as documented; the verifier does not claim C40 cannot emit those diagnostics. It supports malformed compact input only after the outer correlated scope is established.

The request checks are mechanically equivalent to C40: exactly 16,384 total bytes, LE4 length 16,380, canonical JSON followed by ASCII JSON whitespace. Duplicate keys, nonfinite values, wrong JSON types, hidden fields, excessive collections/tree depth/node count, lossy/noninteger QPC and inconsistent native/held/null quality are rejected. Response framing at lines 292–301 requires READY then RESULT, payload limits 2,048/16,384 and aggregate 18,440, with no extra frame or residual bytes. The response need not itself use the producer's exact canonical JSON whitespace spelling; strict JSON/schema and original whole-wire hashing are the declared contract, not byte-for-byte reserialization of inferred output.

Hash and label equality are consistency checks only. The fixed pins cannot be changed merely by supplying matching wrong caller labels. The original expected IDs, process/package identity and original request/response custody remain A's responsibilities.

## Result/flag semantics

Lines 304–314 retain C40's public-validation order. Lines 409–427 distinguish exact pre-core rejection, valid default-disabled output, enabled internal failure, post-entry rejection and normal RESULT. Malformed public input requires its first actual validation reason with `core_ran=false` and null result. Valid disabled input requires DISABLED/disabled/false/null. Enabled INTERNAL_ERROR can preserve either flag because conversion occurs before the flag assignment. OUTPUT_TOO_LARGE and the enumerated post-entry C40 Rejected codes preserve `core_ran=true`; rejected records cannot carry partial advice. This reports child data, not measured execution.

The final change after author run01 only expands the fixed post-core reason surface and its rejection condition. The literal code inventory was checked against the pinned validator/conversion/output call surface; unknown codes remain rejected. The set is deliberately a conservative failure-diagnostic surface, not a proof that any particular failure actually happened for a specific input. No accepted REJECTED record grants completion.

Normal advice has exact keys, planner/schema markers, candidate-only/no-authority flags and fixed STOP/ADVISE reason shapes. The verifier checks finite bounded risk/uncertainty, bounded speed, a unit ADVISE direction and global speed cap, or zero STOP action. It requires output observation equality to the validated original input. Map cells at lines 356–366 correspond in order to all clean native input samples, with exact IDs/QPC/original EM pose; held samples do not create independent cells. Counts and independent count remain bounded. Early quality and exact >100 ms expiry branches match original C28 source lines 294–301, with early empty map and unit risk/uncertainty.

No numerical search, pose applicability decision, map-risk recomputation or optimality proof is performed. The accepted output shape can be handcrafted; that is an expressly documented limitation rather than evidence of genuine inference. Full source/causal action authority must still be established by the host before input reaches the child.

## Immutability and time proposal

Parsing creates detached JSON values. `_freeze` recursively turns dictionaries into mapping proxies and lists into tuples; the frozen slotted result contains those detached values and two immutable wire hashes. Caller expected-ID mutation cannot change returned correlation. No mutable source bytes or external dictionaries are retained as writable aliases. The module imports only stdlib parsing/data utilities; it neither imports C40/C28 nor samples clocks or performs I/O.

`validate_observed_interval` accepts only exact uint63 values with dispatch lower <= all-result-observed upper <= supplied now. It creates no deadline, exact CPU-finish scalar or freshness grant. The README proposes a NEW host-envelope interval field/basis, explicitly not implemented or approved in A. It correctly warns that `now-upper` alone could make a delayed result appear fresh; an original deadline or a conservative `now-lower` test must remain separately enforced. Genuine host clock domain, all-result observation, matching original transcript and dispatch provenance are outside this helper. The historical host_envelope source is not claimed current. A's reported pair-transport work remains a separate source/native qualification.

## Evidence and new checks

Author run01 tested 12 methods against source `2f776a47…`, exit 0. Final source `fc00cd14…` was tested only by the changed test06 and new test13, exit 0; static audit exited 0. These raw versions, commands and logs were read, not rerun, and are not relabelled as a final whole-suite execution. The author preparation newline mismatch is preserved as a preparation error, not a product RED. The review's initial lookup used the nonexistent shorthand filename `pair_verifier.py`; the actual file was then read as `c40_pair_verifier_v1.py`. That was a read-only tooling error.

The portable `independent_checks.py` ran once, under a 25-second subprocess bound, exit **0**, empty stderr. Four new handcrafted-data checks:

- Accepted a held current observation following two native samples with different original poses and exact QPC above 2^53; retained both ordered native map origins.
- Rejected the same pair with reversed native map cells (`MAP_ORIGIN_MISMATCH`).
- Accepted quality-first STOP for a simultaneously saturated and expired sample, with no map contribution.
- Rejected replacing that reason with expiry (`EARLY_QUALITY_REASON`).

Positive returns were additionally checked for immutable nested mappings and independence from later caller-ID mutation. Each request/pair's exact bytes and SHA-256, results, raw stdout/stderr and actual command/exit are retained. There were no new failing product cases. No author tests, old groups, C40 runtime, C28 core, native actor, model, PDE or board ran. Only the new verifier was imported.

All H01–H15, original 29 requirements, both H12 obligations, fixed design and 100 MHz/timing/1%/100 ms requirements remain unchanged and unaccepted. Physical-board authority remains A alone. This review wrote only its exclusive directory; main owns publication and final disposition. Ownership is released with no active jobs/subprocesses.

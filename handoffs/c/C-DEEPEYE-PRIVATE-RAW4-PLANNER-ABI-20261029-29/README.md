# C29 private raw4 diagnostic planner ABI v1

This separate, disabled-by-default ABI accepts A's existing private raw4 candidate
shape without fabricating protocol BOOT, epoch, topology or an integer session.
It reuses the **one frozen C28 `recommend` code object**, with new strict input
validation and exact time units. It does not provide movement authority, CPU
completion, physical sample authentication, H12 or formal100ms acceptance.

Operation `C-DEEPEYE-PRIVATE-RAW4-PLANNER-ABI-20261029-29` continues
`DEEPEYE-IMPLEMENTATION-20261014/version1`. Contract
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
fixed design `1011259415a0916054eb580687612580bc1e5f09`: all H01–H15,
including both complete H12 modes, remain unchanged.

## Existing inputs versus the proposed Root receipt

The candidate is the exact `candidate_four_channel_input` shape from
`simulation/authority/live_chain_channels.py` at A source
`708603c53efc020e7fbbc5eefe58d304943b8ca5`. Its nested context preserves
operation_id, request_hash, tested_commit, build_manifest_sha256, boot_id,
full printable string session_id, tag and clock_domain_id. Generation, trigger,
request sequence and source admission remain distinct. The output semantic alias
`kernel_boot_id` equals original context.boot_id; it is never protocol BOOT.

The **new `c29_root_association_v1` receipt is a proposed integration interface**.
It is not a field claimed to exist in A's current candidate. It contains:

* `config`: the original context/generation, source pins/policy and schedule
  anchor, approved goal, original ready baseline counters and initial trigger.
* `source_admissions`: the retained original admission sequence, its source
  hashes/counts/quality, original model ticks and receipt QPC, and native flag.
* `captures`: one per supplied candidate, in the same order; original request and
  response UTF8 lines, source/frame hashes, ADC/EM own-pose receipts, retained
  native board-origin capture hash and optional earlier occurred-action cause.
* `current_pose`: same-run own pose at now_qpc_ns.
* `action_registry`: same-run, as-of-now receipt containing occurred actions, or
  an explicitly observed empty list. Missing registry is not an empty history.

Every receipt ID and hash only identifies supplied evidence. Structural matching
of JSON **does not authenticate a source or prove that an action occurred**.
Setting evidence_scope to `root_supplied_diagnostic`, or creating matching hashes,
cannot close this trust boundary. Real integration requires A's original trusted
Root to construct these associations from its actual owner-held records. No
`board_verified` boolean, fixture label or protocol placeholder is accepted as
evidence. All public examples are clearly labelled synthetic local data or
synthetic illustrations of the actual candidate shape; none is an A board run.

**Current A payloads lack these Root associations.** With root_receipt=null they
return INPUT_UNAVAILABLE / STOP / core_ran=false, retaining their counts, null C3,
original ages and full identity. No current integration or successful actual run
is claimed. No stale source can be repaired by a later receipt.

## Deliberately small availability window

This version requires source admissions **from original index0 with no omitted
admission**, at most32 records. At continuous100Hz this covers ticks0..310ms,
not arbitrary long-running collection. Gaps remain gaps and can invalidate C3;
they are never backfilled. A later32-record slice starting at a nonzero index is
rejected. Do not reset/rebase the original anchor or indices to fit the cap.
History plus current capture plus occurred actions is separately bounded to32.
Held needs its actual native board-return origin retained in that history;
source-only origin or evicted board evidence is unavailable. Long-running Root
integration needs a separately reviewed change; this module is not that change.

A valid original admission prefix that lacks the referenced candidate's tail
record returns INPUT_UNAVAILABLE / STOP / core_ran=false. A null registry or
empty prefix also means unavailable evidence; neither supplies an admission.
Disabled mode stays STOP/core_ran=false for these missing-evidence cases.
Nonzero starts, internal index gaps and contradictory supplied records remain
Rejected. Complete core input still requires1..32 original admissions.

## Exact clocks, quality and unchanged computation

Original source QPC is derived only as original_anchor_ns +
(original_model_tick - original_start_tick)*1000000. Raw lane injection times,
admission receipts, receiver bounds and recommendation now remain separate.
Source ages are cross-checked against receiver QPC; current age is compared using
integers to100000000ns inclusive.100000001ns fails, also above2^53. No conversion
to float/int milliseconds, origin reset or functional2s relaxation occurs.
C3 startup90ms and its ten-contiguous-ADC rule use original **model ticks**, never
absolute QPC milliseconds. Null remains null. EM fault/all-invalid, C3 independent
validity, held saturation and legal non-fullscale C3 saturation retain producer
semantics. Legal low quality can invoke the core and produce a quality STOP.

At module load, only the fixed sibling C28 file is read and checked against
SHA256 `70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4`;
mismatch raises ImportError. No caller-selectable dependency path exists.
Every core call uses a new FunctionType with the exact original code object and
private copied globals, replacing only `_validate` with a fixed, per-call
validated-association check. The original module/helpers are untouched. There is
no second planning loop, source rewriting, global monkeypatch or supplied plugin.

Only after strict JSON, raw capture, source, Root association and integer-age
checks pass does the internal view use `Fraction(original_qpc_ns,1000000)`.
These are lossless absolute units for the existing core's100ms arithmetic, not
new model ticks. Native mapping requires original native admission, identical
ADC/EM acquisition QPC and original own pose, plus unique retained capture. Held
has distinct original times and does not add independent map evidence.
The frozen pairwise0.25m/15degree pose envelope,30degree native direction cone,
roll support, 3D goal search, count-derived risk/uncertainty and speed rules stay
unchanged. The0.25m bound is candidate policy, not measured physical precision.

Outputs reconstruct exact integer original QPC and full native source/capture
identity. No Fraction or private pseudo-ms fields escape. All results are
detached, strict bounded JSON and authorization=none. `core_ran=true` means the
actual frozen function was invoked, including its quality/pose STOP branches;
disabled/missing/stale paths never invoke it. STOP describes advice only.

## Use and local controls

Import `private_raw4_planner_abi_v1.py` from this directory, keeping its original
C28 sibling directory present. Call `recommend(mapping)` or
`recommend_json(utf8_bytes)`. Envelope keys and receipt fields are documented in
abi-contract.json and complete interface-examples.json. Omitted `enabled` means
false; otherwise it must be a boolean. Missing evidence is explicit null.
Unknown fields, malformed types, contradictory evidence or oversized inputs raise
Rejected. This includes hidden truth fields even while disabled or unavailable.

The known-local dependency read is limited to import. `recommend` and
`recommend_json` perform no file, network, process, model or control operations.

Run only these new controls, bounded externally to30seconds:

```text
python -B test_private_raw4_planner_abi_v1.py
```

They use synthetic receipts, including >2^53 QPC/1ns boundaries, full192-character
sessions, missing evidence, raw/held/action tampering, legal quality, pose/goal
behavior, source hash failure, strict JSON, detached outputs and concurrent
context isolation. The frozen old C28 suites are not imported or replayed.
Original failed local runs and corrected runs are retained in private author
evidence; independent review applies to the final frozen five source files.

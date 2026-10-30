# C30 private raw4 time association diagnostic ABI

This additive ABI separates the producer's nominal source schedule from actual own-pose reads and ADC calls. It defaults off, returns `authorization: none`, and grants no movement authority. Missing original Root evidence yields `INPUT_UNAVAILABLE`, `STOP`, `core_ran: false`. Structural conflicts raise `Rejected`, even when disabled. `abi-contract.json` lists the exact fields and resource limits; the Python validator is executable enforcement.

Current A source `9a2e3f093966230375c35dc65792f6d46f35039c` does **not** supply the historical Root pose book, independently recorded ADC pose-read bracket, committed-revision validity spans or the complete execution association proposed here. All examples in this directory are explicitly synthetic; one illustrates the actual collector field shape with missing Root association, null C3 and a 317 ms age. It is not copied actual capture evidence. No physical, full-chain, H12, compression or formal 100 ms acceptance is claimed.

## Minimum original Root fields

All objects are closed whitelists. Missing evidence uses explicit `null`; arbitrary extra fields are rejected. Root must originate these receipts; client C must not reconstruct them from a later equal pose, ACK, planner advice, fixture label or boolean. Book and owner labels declare a namespace under the **complete** context and generation; JSON consistency does not authenticate ownership or physical sampling.

| Record | Minimum meaning and fields |
|---|---|
| Complete context | Original operation_id, request_hash, tested_commit, build_manifest_sha256, kernel boot_id string, session_id string, tag, clock_domain_id; generation remains separate. No fabricated protocol BOOT, epoch or topology. |
| config | Existing source/config receipt, original clock anchor and model start, goal, counters, initial trigger; add original pose_book_id and owner_binding_id. |
| source_admissions | Complete original index prefix, original ADC/EM model ticks, counts/quality, source hash, actual received QPC, native flag. |
| capture association | Original capture/source hashes, exact request_raw/capture_raw bytes encoded as strings, adc_pose, em_pose, original native capture hash, nullable cause_action_id; add actual adc_call begin/end QPC. |
| adc_pose / em_pose | Original receipt_id, source admission index, nominal_source_qpc_ns, own pose, committed pose_revision, actual pose_read begin/end, original proven valid_span. |
| valid_span | Original receipt_id and **closed** from_qpc_ns / through_qpc_ns for that committed revision. It must prove historical validity, not merely absence of a later observed change. |
| current_pose | Original receipt, complete context/generation, at_qpc_ns equal now, own pose/revision, actual read bracket and proven span covering read and now. |
| action_registry | Original receipt and context/generation, as_of_qpc_ns equal now, actual executed actions. Explicit empty actions is valid only when actually supplied by Root; null is unavailable. |
| executed action | Original receipt_id/action_id, state=executed, original observation capture hash, from/to own pose and committed revisions, actual at_qpc_ns completion/commit point. |

For actions, `at_qpc_ns` specifically means the original Root-recorded instant at which `to_pose_revision` became committed after execution. It is not dispatch/start, transport ACK, callback arrival or advice time. If that fact is unknown, supply missing execution receipt/registry and do not enter the core. This defines the detail left unspecified in the provisional Root table discussed at PR25 comment 6517883393. No action duration is inferred.

## Time and revision checks

All QPC and revisions are exact uint63 integers; booleans/floats are rejected. Nominal QPC remains `original_anchor + (original_tick - original_start_tick) * 1000000`, with no subtraction of a new origin. All supplied events, bracket endpoints and proven span endpoints are non-future.

ADC requires `nominal <= read.begin <= read.end <= adc_call.begin <= adc_call.end <= admission_received`. Its closed proven span covers nominal, the complete read and its own ADC call. Native EM requires its own read before the original native ADC call; its span covers its original nominal, read and that native call. Native evidence also requires the actual original native source admission and equal ADC/EM nominal time, pose and revision. A later equal numerical pose cannot establish earlier validity.

Held EM retains the exact original native receipt, pose, revision, read and span. Its coverage is checked against the **original native call**, not the later held ADC call. Held ADC has a separate original read/call/span. Missing retained native capture is unavailable; history eviction never turns held EM into independent new evidence.

Same revision under the same complete namespace must have the same pose. Different-revision closed proven spans cannot overlap, even if their pose numbers match. Time-ordered disjoint spans cannot reverse revision order. For each executed commit `(to revision R, time T)`, every supplied span with revision below R must end strictly before T; every supplied span with revision at least R must start at or after T. Current revision cannot precede the latest supplied executed to revision; equality requires equal pose. Executed actions follow their actual received observation, and an action claimed to cause a capture must finish strictly before that capture's original nominal ADC time.

Missing span/read/call/revision/book/registry, legal missing admission tail or insufficient historical coverage is unavailable. Reversed intervals, incompatible supplied identities/revisions, future events and hidden fields are rejected. The ADC read is currently absent in A's pump and must not be copied from its EM read.

The pinned pump reads QPC and floors a nominal 10 ms slot before the synchronous EM scope, actual pose read, acquisition and ADC call. Its enter/exit boundary checks do not prove a historical nominal pose span. The source model's first ten contiguous ADC admissions govern C3 availability (`<90 ms` startup lacks C3); those model ticks are separate from QPC freshness. A gap resets that continuity rather than manufacturing healthy C3.

## One numerical core

At module load, only the fixed sibling C28 source is read and SHA-256 checked against `70b317681fee8c9182c342fe8d2f94eaecc957c62231a74a080d213bb5e0eab4`; mismatch fails import. No caller-selected dependency path exists. `recommend` itself has no I/O. There is no C29 import or second planner implementation.

The exact frozen C28 `recommend.__code__` executes with a private globals dictionary. Only `_validate` is replaced by the fixed per-call strict association seam; the original module and its helpers stay unchanged. Original integer QPC ages are gated first: exactly 100000000 ns is allowed, +1 ns is unavailable even above 2^53. A private absolute `Fraction(qpc_ns, 1000000)` view preserves C28 native equality and ages without rounding. No Fraction or synthetic ms escapes output; map cells restore original integer QPC, original native identity and full original EM pose receipt.

C28's 0.25 m pairwise displacement, 15 degree forward-axis support, roll-only support, 30 degree native direction cone, counts/quality/null/held behavior, risk/uncertainty and goal-sensitive 3D advice remain unchanged. The 8 m risk kernel is not an observed clear-space range. A successful diagnostic result is not a command.

## Bounded interface and use

Input and output each allow 1048576 UTF-8 bytes, 65536 nodes, depth 16, 32 object fields, 96-character keys and 192-character ordinary strings. Only the exact `root_receipt.source_admissions` path permits 1001 entries; it preserves original indices 0 through 1000 within the first 10000 source-model milliseconds. No sliding origin/reset is permitted. Missing legal tail is unavailable; nonzero start or internal index hole is rejected. This remains a bounded initial-source diagnostic, not indefinite collection support.

All other arrays cap at 32. Before any missing-evidence or disabled return, `max(len(history)+1, len(supplied root.captures or [])) + len(supplied actions or []) <= 32` must hold. Null contributes zero supplied items to this resource calculation; it never supplies missing evidence. The later association check also retains its combined bound. Exact channel/vector/raw-word sizes still apply. Raw request/capture strings at their exact capture-record paths cap at 16384 characters/bytes; embedded raw JSON has ordinary array limits and cannot exploit the source-prefix exception. Strict JSON rejects duplicate keys, nonfinite numbers and foreign fields. Every returned disabled/unavailable/advice result passes the same output budget check.

Import this directory's `private_raw4_time_association_v1` and call `recommend(mapping)` or `recommend_json(utf8_bytes)`. Omit `enabled` to keep it off. Preserve the original candidate and supply only genuine original Root receipts if enabling in a future diagnostic integration. Returned candidates/context/Root receipts are detached copies.

`interface-examples.json` contains synthetic input/output pairs for native advice, held evidence after a small executed displacement, default-off and missing-Root collector shape. The first two deliberately have `enabled: true`; they are local diagnostic fixtures only.

## New local verification

Only `test_private_raw4_time_association_v1.py` contains this phase's new focused controls. The initial phase's thirteen methods cover separate nominal/actual intervals, missing coverage, closed boundaries, revision chronology, held native retention, action causality and commit points, high-QPC 1 ns age boundary, complete 1001 prefix, strict path-specific limits, hidden fields/default-off, exact code-object reuse and supplied time contradictions despite a missing book. No old C28/C29 suite or A script was run.

Author run01: eleven methods passed; the 1002-entry negative fixture incorrectly omitted the held native record and raised a fixture-construction IndexError. The raw RED and source snapshot were retained. Only that construction was corrected and test08 rerun in run02, passing. The module was unchanged between those runs. Run03 produced and checked the four examples. A later narrow validation change moved checks of supplied nominal/read/call ordering ahead of missing-book exits; only the newly added test13 ran in run04 and passed, including adjacent complete native/held inputs. No unchanged test group was rerun. Main independently reviews the frozen result before delivery.

C30-R1 repair v2: independent review of module `cbf2077281e3683fe9a9b6d3b5ef36e1da2a54da27daab84b10f7d18cc6f07b7` found twelve RED cases where missing evidence or default-off bypassed the combined capture/action32 budget. That original review and five-file snapshot remain preserved; the reviewed version was not approved. The narrow repair adds the early structural formula above and leaves the later bound intact. Only the new test14 was run: enabled/disabled missing-evidence paths, exact32/33 boundaries, supplied receipt count, retained candidate count, and null registry semantics all passed. Earlier author methods and independent57/22 checks were not rerun by the author. Existing interface examples retain their original generation evidence; they were not regenerated during this repair.

DEEPEYE-HUMAN-LOCK-20261014 revision1, source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, fixed design `1011259415a0916054eb580687612580bc1e5f09`: all H01–H15 and both H12 items remain unchanged.

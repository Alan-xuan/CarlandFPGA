# C36 host ABI v2: A108 original old-pose span

Entry remains `host_projection.project_interval_json(full_proof: bytes) -> bytes` in this new package only. Host request schema_version=2 and abi_id=moving_interval_book_bridge_v2. Response schema_version=2 and abi_id=moving_interval_book_projection_v2. Input ActorBook.schema remains the original3; its source_commit is exactly51c48e106c76f3e4d18000da61be17dd8a4b6623. The original host v1 files and e794 evidence remain immutable and are not relabelled. They are not silently accepted as v2.

Child input remains exactly schema_version=1/projection_id=c36_c28_public_view_v1, with unchanged bytes/schema pin. Host performs zero C28 calls and produces only a structural/numerical diagnostic. The separate C37 envelope must still fit16384 bytes including its4-byte prefix; no proof/history is truncated.

## New transition field and interval rules

Every reserved, failed, complete STEP and complete BOOT/COMMAND representation requires `old_pose_span`, nullable with the existing finite Span structure: from_qpc_ns, through_qpc_ns, root_revision, pose_revision. Null means actual evidence unavailable. Each supplied original field retains its exact value; the validator never substitutes lower-1, end+1 or any inferred timestamp.

A108 reserve takes actual old_end, calls original `_span(old_end)`, then takes a separate actual lower observation and refuses lower<=old_end before retaining a transition. C36 therefore requires supplied old_pose_span.through_qpc_ns < transition.lower_observed_qpc_ns for every kind, and matches its Root/pose to before_root_revision/from_pose_revision. It correlates all four span fields to a supplied original closed_spans entry, with unique full matches and no array-position identity. Known ties/late endpoints/identity mismatch reject. A missing endpoint or originalspan remains unavailable after checking all supplied decidable constraints. The compatible-closed-span search is only a necessary consistency check; it does not construct an absent association or proof.

Every source old-Root span must end before the actual lower boundary to be usable; every new-Root span must begin at/after real completion. Gaps remain unavailable. Same-pose BOOT/COMMAND still requires its real lineage. Previous R1 getter lower/pre/post-CAS consistency, R2 independent successor comparisons, and R3 custody label consistency remain in source; no old suite was rerun to relabel their prior evidence.

## Genuine current getter field mapping

A32 explicitly selects the original `book.current_pose_interval()` method, verified at target51c. It polls, samples begin, calls the original pose_reader, samples end, polls/checks and returns `_span(end)`. Its source bytes are SHA f80a6dbb4c264253759ce910c69ef75ae8a774f8d3b8ae22dee9121839e4e2cb. It does not return a native getter/board receipt or authentication grant.

| Actual method field | Host actor_book.current_read | Host root_receipt.current_pose |
|---|---|---|
| pose | exact pose | exact pose |
| pose_revision | exact pose_revision | exact pose_revision |
| at_qpc_ns | exact at_qpc_ns | exact at_qpc_ns |
| pose_read.begin_qpc_ns/end_qpc_ns | exact original bracket | exact original bracket |
| valid_span.from_qpc_ns/through_qpc_ns | exact original endpoints | same endpoints in valid_span |
| valid_span.root_revision | retained in valid_span | root_revision from that actual span |
| valid_span.pose_revision | retained in valid_span | must equal actual pose_revision |
| claim/native_interval_atomic | exact numerical-only/false | diagnostic wrapper retains overall numerical-only/false |

The original method guarantees at_qpc_ns=pose_read.end_qpc_ns=valid_span.through_qpc_ns. This adapter also requires these equal supplied now_qpc_ns under the selected observation contract; it never samples or renews now. The actual current read must be covered by its genuine span and agree across both supplied representations. A mismatched end or Root identity rejects; missing actual read/span stays unavailable.

`receipt_id`, `valid_span.receipt_id`, context and generation in the host Current wrapper are NOT fields returned by this method. They must be actual independent provider-held associations, supplied separately or left unavailable; C36 generates none. Current Root identity derives only from the supplied actual valid_span.root_revision, never from an interval-only export or guessed array position.

`actor_book.current_pose_interval` is only the original evidence interval export (four Span fields). It cannot populate pose, pose_read, at_qpc_ns or current_read. Supplying that export while current_read is null remains unavailable even when other external current metadata is present. Presence alone never proves the method actually ran: original book object/custody/call identity and all wrapper receipt provenance remain provider obligations.

## Unchanged provider boundary

C36 does not authenticate actual owner/source/BOOT/native capture, original receipt digest/getter binding, inherited actor process/pipe custody, admitted immutable readback frame identity, one-use invocation or post-dispatch freshness. These remain with A's original provider. A108's genuine pointer/time/digest readback-retention checks are not replaced by JSON labels or enabled=true. Missing expected public facts remain unavailable; provider-only facts are expressly not certified by PROJECTED. H01-H15/fixed contract,100ms/quality/calibration and A-only board authority are unchanged.

# C33: completion-time judgment and one retired-input diagnostic

**CURRENT_NOT_DIRECTLY_COMPATIBLE.** A later Root completion-observed upper
bound cannot directly populate frozen C30 `actions[].at_qpc_ns`. This delivery
provides a bounded interface judgment, a non-executable minimum-evidence
inventory, and a diagnostic for one exact retired source70 artifact. It creates
no action, authority, current capture, admission, or executable actor adapter.

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`; operation
`C-DEEPEYE-ACTOR-COMPLETION-TIME-SEMANTICS-20261030-33`.

## Why the timestamps are different

Frozen C30 [README](../C-DEEPEYE-PRIVATE-RAW4-TIME-ASSOCIATION-20261030-30/README.md)
line23 and [ABI timing.action](../C-DEEPEYE-PRIVATE-RAW4-TIME-ASSOCIATION-20261030-30/abi-contract.json)
require the original Root-recorded completion/commit point at which the actual
`to_pose_revision` became committed after execution. They expressly exclude
dispatch/start, ACK, callback receipt and advice time. A recorded CAS bracket
and a later successful getter do not identify the point inside that bracket.
Passing numeric comparisons cannot establish the missing semantics.

A's proposed `completion_observed_qpc_ns` is a real, separately sampled QPC
AFTER the receipt/result, execution deadline, getter, custody and revocation
checks. It can establish a conservative observation upper bound if those
records are genuine and consistent. It is not an exact CAS or original commit
instant, and must not be calculated as a convenient maximum of other fields.
`model_executed_until` is not proof of completion merely because that deadline
has passed: actual success, no cancellation/revocation, ownership and getter
conditions must also be evidenced. Transport ACK and a successful model return
remain different events from physical board/ADC evidence or formal acceptance.

Compatibility could be reviewed for a **future** authority protocol only if
that protocol actually defines and records its final committed/executed
effective point at a particular barrier event. Original lifecycle receipts
must prove that meaning and the from/to revisions. Relabeling a callback after
an earlier commit is not such a protocol. If only an interval is known, an
interval-aware interface needs its own reviewed version. This delivery neither
changes frozen C30 nor implements either future alternative.

## Required original evidence and boundary rules

[minimum-evidence-contract.json](minimum-evidence-contract.json) separates the
exact existing C30 field lists from **proposed, non-executable** prerequisite
records. The latter are an inventory for A's future recorder, not fields that
this diagnostic accepts or claims A already produced. References require their
actual retained records; IDs, hashes and booleans do not authenticate them.

| Evidence | Minimum meaning retained outside the frozen ABI |
| --- | --- |
| Complete namespace | Original operation/request/tested commit/build, boot/session/tag/clock domain, generation, original book/owner/actor identities. Private boot labels are not verified board BOOT. |
| Execution/CAS | Original receipt/action and observation capture; actual result, cancellation and revocation records; real pre/post CAS QPC and success/from/to identity; model execution receipt and executed-until; separately sampled completion observation. Unknown original commit remains null. |
| Clock correspondence | All compared QPC fields in the same original domain. If model time differs, original conversion/epoch evidence is required before comparison; no guessed scale, reset or offset. |
| Numerical custody | Actual exclusive owner/actor/Root revision, guarded interval, revocation generation and retained guard/result receipts. A label or unchanged coordinates is insufficient. |
| Getter endpoint | Original begin/end QPC, returned own pose, revision/owner association and guard/postcheck results. An endpoint check is not native interval atomicity. |
| Original EM scope | Actual original scoped EM call begin/end and scope open/close, closed receipt, numerical pose/read/span, source hash, explicit source admission and original native capture linkage. A cleared scope cannot be reconstructed afterwards. |
| Physical ADC/board | Separate actual acquisition/capture, board identity/BOOT, transport and calibration evidence. The source70 numerical ADC-call bracket and model values provide none of these. |

Necessary future ordering includes original pre-CAS <= post-CAS <= sampled
completion observation, actual model executed-until <= observation in the same
clock domain, and all successful postchecks completed before that separately
sampled observation. These are prerequisites only; they do not supply an exact
commit point. A single positive getter or absence of a later observed mutation
does not prove continuous native custody or physical movement.

For an **actual known** commit `(to_revision=R, at=T)`, frozen C30 requires
every supplied lower-revision closed span to end strictly before T and every
span at/above R to begin at/after T. Distinct revision spans are disjoint and
ordered; same revision has the same pose. Original spans may have gaps, never
invented coverage. Do not crop recorded spans or choose `T-1 ns` to force a
fit. A future recorder must supply genuinely proven boundaries; an uncertainty
interval is not an exact T. Executed actions must follow their original
received observation, and a caused capture's nominal ADC time must be strictly
after the actual execution commit. Current revision cannot precede it.

For a separately reviewed future upper-bound barrier, old-revision evidence
needs an actual proven endpoint strictly before the earliest possible transition
(normally pre-CAS), and new-revision evidence needs actual proof beginning at or
after the completion-observed event. Custody must keep every relied-on check
valid through that observation; the uncertain gap remains unproved. For example,
actual commit110 / observation200 / old span through150 satisfies `through<200`
but falsely covers time after commit110. A genuine new span starting130 also
cannot be relabeled as starting200. These are semantic counterexamples, not
executed synthetic timeline tests or a new adapter. This conservative proposal
still does not supply frozen C30's missing exact commit point.

Held EM keeps the **exact original** native receipt, pose, revision, read,
closed span and original call/capture linkage. Its span covers its original
native call, not a later held ADC call. The later ADC requires its own original
proof. Values, timestamps and original per-point quality bits stay unchanged;
held delivery cannot refresh time or turn one sample into independent evidence.
Missing original scope/capture remains unavailable even if coordinates match.
Book canonical source hash and wire/admission source hash are separate domains.

## Frozen C31 is not a moving multi-revision bridge

C31 runtime SHA256
`506219cf445001c46f2f4e1ffd411829ea9d184d4260d18af9e45aa3787993ee`
pins A source `54e1fd6c5795cc2f1247866dd8783331f615ef66`. Its `_crosschecks.bound`
binds all supplied sample/current poses and Root/pose revisions to one explicit
committed binding. That fixed numerical Root projection does not automatically
support a moving multi-revision/held bridge, even though C30 has separate
revision/action relationships. New movement associations require a separately
reviewed interface/version and actual evidence.

The JSON inventory copies the exact C31 `input` table and selected original
association rules from its hash-pinned
[mapping-contract.json](../C-DEEPEYE-ROOT-BOOK-C30-PROJECTION-20261030-31/mapping-contract.json).
These include envelope, binding, external receipts, capture metadata,
ADC/EM receipt metadata and current receipt metadata. In particular, original
`adc_book_source_sha256`, `em_book_source_sha256` and
`em_origin_capture_sha256` link distinct canonical-book and wire namespaces;
receipt/span IDs and admission indices must be original, not derived from list
positions. A genuine `book_current` and its external metadata are required,
with the current view obtained before the covering evidence snapshot.
Supplying these fields alone does not remove the fixed-source/single-binding
restriction. C31 still binds frozen C30, not the separate C32 implementation.

Source70 is the original **schema1** run at
`4dc91fd24531b3df53fc916e8b7f509ad524592c`, exported at
`d0185d335747acb26439f40a8ce945f7f4eaa9af`. The whole runtime commit differs from
the pinned book-code contract commit54e1; these are different provenance fields.
Main fetched the book source at BOTH immutable commits: the25692 bytes are
identical, SHA256 `624c84f8de949c7c078ca0b7afa84c295804d7bc881527e9b91c38ba645004ef`.
[book-provenance.json](book-provenance.json) records both URLs and Git blob identity.
The earlier draft's claim that different commit labels alone prove incompatibility
was too strong and is withdrawn. C31's `book_source_commit` identifies its code
contract; an independently established contract54e1 statement need not rewrite
the actual runtime4dc91 field. Passing4dc91 as that contract field would reject,
but it is not the correct way to express both independently verified versions.

This code-byte equality does not supply original owner/current/EM/capture/
admission/action/BOOT receipts or prove a complete accepted C31 request. The
static source70 example remains unavailable for those missing original facts.
C31's fixed-binding limitation concerns a future moving bridge, not an invented
missing field in this revision0 sample. A's later scoped-EM schema2 candidate
is separate and cannot upgrade these saved samples. C33 never calls C31 or
claims it accepted source70. All numerical claims remain
`numerical_immutable_committed_root_only` and `native_interval_atomic=false`.

## The executable slice accepts exactly one historical file

`diagnose_retired(raw: bytes) -> dict` and `diagnose_json(raw: bytes) -> bytes`
accept only [retired-source70.json](retired-source70.json), exactly **82496 B**,
SHA256 `63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c`.
Its [original companion](retired-source70.README.md) remains part of the evidence
and complete package cost. The type must be exactly `bytes`; length and SHA
are checked before parsing. All other inputs return the fixed exception
`Rejected('C33_RETIRED_INPUT_NOT_PINNED')` without echoing values. This includes
reformatted or semantically equivalent JSON. There is no general schema,
duplicate-key, depth, authority or timeline validator: different bytes never
reach parsing. The SHA selects reviewed bytes, not an authenticated owner.

Only stdlib `hashlib` and `json` are imported. The diagnostic has no file,
network, clock, actor, source kernel or planner operations; callers provide
bytes. C28/C30/C31/C32 are neither imported nor invoked. The output is a compact
whitelist, at most 65536 B, with `INPUT_UNAVAILABLE`, `STOP`, `authorization=none`,
`projection=null`, `c30_called=false`, `c31_called=false`, `core_ran=false`.
It cannot be enabled or supplied with an alternative now/time/identity.

Rows copy original source_count, ADC/EM tick, nominal QPC, actual record-end QPC,
canonical source hash, channel counts/values and quality. Source_count is not
an admission index. The export's original parallel arrays associate its record
end with that record only; their positions never create identity or admission.
Own pose/private book contents, canonical payload hex and owner fields are not
echoed. The original pinned input is not modified.

The 20 historical records retain 4 fresh and 16 held EM **source timestamps**,
9 null C3 samples and 11 valid count-zero C3 samples with distinct positive RMS
values. Valid zero is not missing. The maximum of
`record_end - (original_origin + em_tick_ms * 1000000)` is **43130900 ns**,
labeled only *nominal EM timestamp age at original record completion*. This
is not current freshness, original EM-call latency, end-to-end 100 ms proof,
calibration, physical vibration, board processing or AI execution. No origin
is rebased and no value is re-quantized.

Fixed missing codes distinguish the six original export omissions from the
additional interface conclusions: no opaque original book/owner identity,
original EM scope receipt, live current capture, original admission/capture
times, executed-action receipts or verified board BOOT; the actual commit
point is also absent. Fixed-binding and future schema2 limits are documented
separately from actual missing evidence; runtime/code-version label differences
are not themselves a missing-proof reason. Zero numerical commits does not
create an observed empty action registry.

## Verification scope and authority

Revision2 removes the incorrect version-mismatch missing code and separates
the future moving-bridge restriction from actual missing data. Original v1
sources,5 author checks and6 independent checks remain version-specific evidence;
they are not relabeled as a full v2 rerun. Only new narrow correction controls
are needed for the changed provenance/missing-reason behavior.

Only NEW focused checks of this exact input gate, original historical values,
bounded whitelist, immutability and absence of executable dependency imports
are authorized here. They are not tests of a generic validator, actual actor
completion or frozen C30/C31 acceptance. Raw command/exit/source snapshots are
retained by the original C main; independent review and publication follow the
author's release. No old suite, source/model kernel, native run or board run is
part of this implementation.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, fixed design
`1011259415a0916054eb580687612580bc1e5f09` remain unchanged. H01-H15, both H12,
original29 and final1%/100ms unfulfilled gates remain unfulfilled. A alone
operates the physical board. Formal acceptance is false.

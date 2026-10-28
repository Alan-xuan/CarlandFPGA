# C24 offline candidate catalog and causal data preparation

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; operation
`C-DEEPEYE-CAUSAL-DATA-PREPARATION-20261028-24`, author work
`C24-TOOL-AUTHOR-20261028-v1`. Baseline
`c4722d8252e0b5e22cfdadcf71905b92d45f811b`. Frozen interface SHA256
`2ec7e7ae1407232abba7f21c68528d6345445f5af48b8610f9303b2dff2c806b`.
A's original task is PR25 comment6469933721, exact original UTF8 SHA256
`fd42e1d92cc49cdc1a0acd7f106f697c3344d65af63b6dfb90499be934dab46f`.

This stdlib tool validates an offline candidate definition. Its outputs always
distinguish `format_valid`, `candidate_only` and `approved_training_data`:
successful reports have true, true and **false**, respectively. `status` is
`candidate` or `blocked`; a format error is an exception, not approval. No
record may contain an accepted/approved field. Native provenance, declared
calibration IDs and file hashes establish declared identity and byte linkage,
not authentication, real calibration, physical data quality or training
admission. There is no real approved physical dataset/provider in this work.

The existing strict9/strict13/EM/FORCE interfaces are not imported or changed.
No conversion, interpolation, imputation, aggregation, four-to-thirteen
expansion, model training, model load/forward or online activation occurs.
These candidate profile names do not adopt a new physical profile. The prior
candidate_only/twin_fixture/not_em_surrogate_v2 limitations remain.

## API and bounds

`causal_data.py` imports only Python stdlib. It does no work at import except
defining functions/constants. The public API is:

```text
load_catalog(root, expected_catalog_sha256) -> Catalog
check_splits(catalog) -> dict
fit_scaler(catalog) -> dict
validate_scaler(catalog, scaler) -> dict
make_window(catalog, sample_ids, *, cutoff_ns, max_age_ns) -> dict
main(argv=None) -> int
```

`Catalog` is an immutable verified byte snapshot with read-only
`catalog_sha256` and `entry_count`. Returned reports contain detached data;
changing a report cannot change the catalog. Subsequent functions reparse the
bounded snapshot and perform no file reads. This does not claim protection
against arbitrary privileged Python mutation of private implementation state.

| Item | Bound |
|---|---:|
| catalog.json | 65536 bytes |
| each record/provenance/group file | 16384 bytes |
| unique loaded input bytes | 8 MiB |
| entries / selected window rows | 128 |
| channels per record | 16 |
| selection JSON | 16384 bytes |
| supplied scaler / encoded output including LF | 131072 bytes |
| ASCII labels | 1..96 bytes |
| UTF8 reasons | 1..192 bytes |
| original time / age bound | int0..2^63−1 |
| original sequence | int0..2^64−1 |
| delivery_index | int1..2^31−1 |
| native numeric absolute value | <=1e100, finite |

Labels use `[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}`. File basenames use the narrower
`[A-Za-z0-9][A-Za-z0-9_-]{0,63}.json`. These are computation/schema limits,
not claims about physical instrument ranges. Exact built-in int/float/bool
types are required; bool is never an integer. Sensor integer values must be
exactly float-representable. Original uint64 sequences are retained as integers
and need not be float-representable. Null is never replaced with zero.

Every object uses an exact field allowlist, schema_version exact int1 and
finite numeric values. JSON rejects duplicate keys, NaN/Infinity, malformed
UTF8, excessive nesting and wrong types; overflowing finite-looking numeric
tokens are rejected by numeric validation. No arbitrary world/layout/seed/
editor/truth/coordinate fields are allowed. File size is checked and each
read is explicitly cap+1, followed by a complete raw-byte SHA256 check before
parsing. Paths are role-specific root children with no traversal, drive/UNC,
backslash or nested filenames. Reparse/symlink/junction components and
non-regular files are refused. The explicit root directory must remain stable;
this is not race-proof authentication of a hostile filesystem. An otherwise
format-valid catalog whose encoded report exceeds its bound is rejected.

## Input directory and exact objects

There is no directory scan or implicit source discovery. `catalog.json` has
exact keys `schema_version,entries`. Each entry has exact keys
`sample_id,split,record,provenance,group`. Sample IDs are unique delivery labels;
split is exactly `train`, `validation` or `test`. The three references each
have exactly `path,sha256`, where SHA is64 lowercase hex of **actual complete
file bytes**, including original whitespace/LF. Paths are respectively
`records/<label>.json`, `provenance/<label>.json`, `groups/<label>.json`.
The externally expected catalog SHA is mandatory. JSON reserialization is
never used as source-file identity.

Record exact keys:

```text
schema_version, run_id, sequence, source_time_ns, clock_domain,
profile_id, channels
```

`run_id`, `sequence`, `clock_domain` are original source identifiers;
`source_time_ns` is the **original source delivery/acquisition-slot time**, not
receiver receipt time or a new clock estimate. Original per-channel acquisition
time is separately `native_time_ns`. Channel order/quantity bindings are frozen
within one source/run/domain. Each channel has exactly:

```text
channel_id, quantity_id, representation, unit, unit_reason, calibration_id,
value, reason, valid, held, fault, saturated,
native_sequence, native_time_ns, native_reason, native_ref
```

`valid`, `held`, `saturated` are exact bools; `fault` is null or a bounded native
fault reason. `value` is a finite native number for real representation, exactly
`{real,imag}` for complex representation, or null with a nonempty `reason`.
For a non-null value, reason must be null. Validity does not erase a non-null
semantic raw value; null values may preserve the original valid flag but are
always ineligible. Unit is an exact native label or null with unit_reason;
known units require unit_reason null. Calibration ID must match provenance.

Native sequence/time are original integers, or explicit unknown nulls.
`native_reason` is required when either is unknown; it must be null when both
are known. Partial unknowns are retained, not inferred. Known native time must
not exceed the original source slot. Original non-held acquisitions have
native_ref null. Held requires a non-null exact reference object
`{record_sha256,channel_id}` and known original native sequence/time.

Provenance exact keys:

```text
schema_version, record_sha256, source_id, source_kind, native_profile_id,
delivery_index, channel_bindings, clock_context
```

`record_sha256` must match the actual referenced record. Source kind is exactly
`synthetic_definition`, `twin_fixture`, `hardware_unqualified` or
`offline_unqualified`. Native profile must match record.profile_id.
`delivery_index` is explicit bounded offline bookkeeping, never a native
acquisition, trusted BOOT, wall clock or motion authorization.
`channel_bindings` is the same length/order as channels; each exact object has
`channel_id,quantity_id,representation,unit,unit_reason,calibration`.
Each of its first five fields must exactly match the record. Calibration is
exactly `{state,id,reason}`: state `unknown` requires id null and nonempty
reason; `declared` or `synthetic_definition` requires nonempty ID and reason
null. A declared ID remains unapproved native candidate provenance; it is not
an independently validated physical relationship.

Required `clock_context` exact keys:

```text
boot_id, boot_reason, clock_mapping_id, clock_error_ns, clock_reason,
own_odometry_history_ref, history_reason
```

Unknown boot/history are null+nonempty reason; known labels require reason
null. Mapping+nonnegative bounded error must either both be known with reason
null, or both null with clock_reason. These are declared offline context, not
verified BOOT/clock/odometry providers. Synthetic definitions may explicitly
leave all three contexts unknown. No history file is opened or physical pose
invented, and clock domains are never mapped or combined by this tool.

Group exact keys are `schema_version,record_sha256,scene_id,event_id,target`.
Whole-scene/event labels are nonempty; target is exactly
`{definition_id,label,reason}`. Target definition names evaluator semantics;
label is a bounded label/number, or null+reason. Known labels require reason
null. This separate sidecar never enters the feature payload or causal window
metadata. Its hash is recorded in training provenance, not treated as a sensor.

## Native quantities and provenance matching

| Candidate catalog profile | Quantity | Representation | Known native unit |
|---|---|---|---|
| hardware_raw_code_candidate_v1 | hardware_raw_code | real | count |
| full_voltage_candidate_v1 | full_induced_voltage | complex | V |
| born_derivative_candidate_v1 | born_derivative | complex | unresolved |
| logrho_candidate_v1 | candidate_logrho | real | unresolved |
| vibration_candidate_v1 | candidate_vibration | real | unresolved |
| definition_real_v1 | definition_scalar | real | definition_unit |
| definition_complex_v1 | definition_complex | complex | definition_unit |

Unknown units remain null+reason even where a known unit label is listed.
Unresolved physical unit profiles permit only null. There is no Born-to-full-
voltage or ADC-to-voltage renaming. Actual source-side binding must match both
the independent provenance and any linked original native record.
Synthetic-definition profiles require source_kind and calibration.state both
`synthetic_definition` with a definition ID; other profiles forbid synthetic
calibration. This provides numerical control definitions only. It does not
fabricate a physical calibration or allow a synthetic definition to be volts.

Native identity is the tuple
`(source_id,run_id,clock_domain,channel_id,native_sequence)`.
Receipt time, delivery index, rehashed wrapper or changed filename do not make
an acquisition fresh. Repeated identity must keep original native time, value,
binding, native validity/fault/saturation and unknown-time reason identical;
conflicts reject. Non-held native sequences cannot regress or wrap. Delivery
sequence/source slot cannot regress within a source/run/domain. Equal delivery
sequences require byte-identical record hashes and frozen channel bindings.
Delivery indices are unique per source/run/domain.

Held resolves its SHA reference to an explicitly loaded original **non-held**
record with matching source/run/domain/profile/channel and earlier delivery
index/non-future source slot. All original native fields must match exactly.
Changing held native_time while keeping a valid newly rehashed held wrapper
still fails against the original. A held chain, unresolved native support or
future acquisition is not legal support. Replacing all declarations and hashes
cannot prove a real physical source; candidate status never changes.

Canonical original occurrence is minimum delivery_index for a native identity.
Repeated delivery retains its raw value but has effective mask0 and no scaler
contribution. Missing native identity cannot contribute. Native identity reuse
across splits rejects, even if grouping labels were changed.

## Splits and candidate scaler

The tool validates explicit splits, not random row splitting. It unions entries
sharing a namespaced whole scene, whole event, native acquisition identity, or
byte-identical original record. Each complete transitive component must lie in
exactly one train/validation/test split. A scene-event bridge cannot evade this
by assigning individual rows differently. Conservative duplicate-record unions
also reject exact-record reuse when native time/identity is unresolved.

Only **training** entries define the scaler's binding set, manifest, eligible
contributors and numerical statistics. Each component contributes once per
canonical original, valid, non-held, non-faulted, unsaturated acquisition with
known native support/unit and non-unknown calibration. `definition_*` is
numerical synthetic preparation only; declared physical calibration remains a
candidate assertion, never approval. Missing/held/duplicate/fault/saturation,
validation and test values never contribute. Complex real/imag have separate
statistics, not magnitude conversion. No per-window online refitting occurs.

Algorithm `population_native_components_v1` deterministically sorts training
entries/contributions and uses math.fsum for mean and population variance.
Fewer than2 eligible values, zero standard deviation, unknown unit or unknown
calibration gives mean/scale null with explicit reason; no scale1 fallback.
Nonfinite intermediate/results reject. Entirely empty training stays blocked,
with an explicitly empty manifest/statistics/contributors and no fallback data.
Any blocked component makes overall status blocked; other valid candidate
statistics may still be reported.

Scaler output keys, in addition to the common candidate fields, are:

```text
algorithm, full_catalog_sha256, training_manifest,
training_manifest_sha256, contributors, statistics
```

The manifest is exact `{schema_version,algorithm,entries}`. Entries are sorted
by sample ID and contain exactly
`sample_id,record_sha256,provenance_sha256,group_sha256,bindings`.
Each binding has exactly
`source_id,source_kind,profile_id,channel_id,quantity_id,representation,unit,unit_reason,calibration`.
The manifest hash uses ASCII sorted-key compact canonical JSON. Each contributor
has exact `native_key,binding_sha256,record_sha256,provenance_sha256,group_sha256,components`.
Native key fields are the five native identity fields above; components are
`{value}` or `{real,imag}` with original native values. Binding hashes use the
same canonical JSON. Each statistic has exact
`binding_sha256,binding,component,count,mean,scale,reason`.
Statistic reasons are null, `unit_unknown`, `calibration_unknown`,
`insufficient_samples`, `constant_values`. These are candidate train statistics,
not a new approved model scaler.

`full_catalog_sha256` is a separate audit identity. A test-only record change
can change that audit field but cannot change training manifest, contributors
or statistics. `validate_scaler` recomputes the complete current document and
compares all canonical bytes, rejecting altered counts/moments/contributors/
train manifest and any test contamination. It also rejects a stale full-catalog
audit hash; that rejection alone must not be described as numerical training
dependence on test values. A valid check reports `scaler_valid:true` plus the
current full-catalog and training-manifest hashes.

## Causal raw window

`sample_ids` is an explicit nonempty list/tuple of unique selected delivery IDs,
in increasing delivery_index, with one source/run/domain/profile binding.
Every selected original source slot and native acquisition must be at or before
cutoff. A selected future value rejects, rather than being silently included or
dropped. Native age is always cutoff minus **original native time**, never time
since delivery or a resampled receipt. Earlier original held support is checked
by hash, so a later held source slot cannot reduce its age. No padding, physical
conversion, normalization or model-ready tensor is produced.

Window result adds exact keys `features,causal_metadata,cutoff_ns,max_age_ns`.
`features` is a two-dimensional row/channel list. Each channel is exactly
`{raw_value,effective_mask,status_reasons}`; a semantic non-null raw value is
retained even under mask0. Mask1 requires fresh first native acquisition,
valid, non-held, no fault, unsaturated, known native support/unit/calibration
and age<=max_age. Otherwise mask0, ordered fixed reasons:

```text
missing_value, invalid, held, fault, saturated, native_unknown,
unit_unknown, calibration_unknown, duplicate_native, stale
```

Raw input null/fault/native reasons remain in the immutable source snapshot;
feature reasons are bounded codes, not arbitrary source-side text. No group,
label, target, scene/event ID, layout, seed, editor history, truth coordinates or
odometry enters the feature payload. Causal metadata has exactly
`run_id,sequence,source_time_ns,clock_domain,delivery_index,profile_id,clock_context,record_sha256,provenance_sha256,channels`.
Its per-channel object has exactly
`binding,native_key,native_time_ns,native_ref,age_ns,valid,held,fault,saturated`.
It contains declared context and original source hashes/flags, no group/label
sidecar. Unknown native age is null. Any mask0 makes window status blocked;
this is explicit usability status, never permission or a physical safety claim.

## JSON CLI, errors and evidence boundary

```text
python -I -S -B causal_data.py validate ROOT CATALOG_SHA
python -I -S -B causal_data.py fit ROOT CATALOG_SHA
python -I -S -B causal_data.py check-scaler ROOT CATALOG_SHA SCALER_PATH SCALER_SHA
python -I -S -B causal_data.py window ROOT CATALOG_SHA SELECTION_PATH SELECTION_SHA
```

These describe an interface, not author-executed commands. Explicit scaler and
selection files must be regular non-reparse files directly under root, with
the same narrow basename grammar and mandatory raw-byte SHA. Selection has
exact keys `sample_ids,cutoff_ns,max_age_ns`. There are no file outputs, hidden
inputs, code/model callbacks or runtime packages. CLI emits one bounded ASCII
canonical JSON line. Exit0 denotes a format-valid candidate report, which may
be blocked. Invalid input emits `format_valid:false,status:invalid,error:<code>`
with the other common fields unchanged and exit2. `DataError.code` is fixed:

| Code | Meaning |
|---|---|
| schema_invalid | exact schema/type/JSON/null-reason/profile invalid |
| bounds_invalid | bytes, counts, labels, number or encoded-output limit |
| path_invalid | containment/reparse/non-regular/missing/unreadable path |
| hash_mismatch | actual source bytes differ from expected hash |
| binding_mismatch | native profile/quantity/unit/representation/calibration mismatch |
| native_conflict | same native identity changed time/value/binding/native flags |
| held_mismatch | missing/incorrect original native link or native-field mismatch |
| split_leakage | transitive whole scene/event/native/original record across splits |
| future_sample | native after its source slot or selected time beyond cutoff |
| sequence_regression | index/sequence/source-time/native-order regression |
| scaler_mismatch | supplied scaler differs from complete recomputed document |

No author import/smoke/test/tool execution is authorized. Author performs only
static AST/JSON/text review and records source hashes. Root alone owns one new
tiny synthetic-definition control batch, with <=30s wall,512MiB process commit
and1GiB job commit, after author/reviewer freeze/release. The independent source
controls and root's CONTROL-EVIDENCE report actual counts/exits separately.
Scaler fitting in that synthetic batch is numerical tool validation, not model
training or physical dataset acceptance. No old fixture/suite, FORCE/model
forward/train, PDE/NumPy leaf, endpoint/service/owner or board operation occurs.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
and frozen design `1011259415a0916054eb580687612580bc1e5f09` remain unchanged.
All H01–H15, both full H12 paths and unmet formal gates remain incomplete.
FORCE quality FAIL does not establish a new EM domain benefit. A alone operates
the physical board. Only the original main owns publication and final review.

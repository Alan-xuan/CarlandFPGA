# C43 independent review

Decision: source approved within the explicit opt-in, static host-envelope / finite-action-candidate scope. No open source finding. Runtime `05da98393d47f3eaf4690d8979d2e37d2e4f1e0b00c801177a3fb6a3f84bbe96`; author FINAL `a3e14f17983cc0bbb84af66edc5128b0e4ed29e78a1006c34f6910e07949bf28`.

## Verified source and compatibility

Read authenticated A41 body (comment 6532387173) and verified its exact UTF-8 hash against the assignment. Independently verified 206 frozen artifact pins plus three main source pins from exact A commit 42f3de654aef3d52300ae1cfb16e3ac512ea2cea, including the private vendor/wheels, original host/schema/timing bytes, patches, new runtime/schema and versioned logs. Before/after pins match. No source fetch, dependency installation or global configuration change was performed by this review.

The host patch adds only explicit keyword options and a guarded entry branch. All 46 original top-level function bodies are AST-identical except `validate_message`, whose original body remains identical after removing only the three new guard/dispatch statements. The author's 47 audit objects count those 46 functions plus one top-level class, not 47 functions. Default v1 does not load the successor; its prior scalar behavior remains unchanged. New bounds require explicit opt-in. Full patch targets only the host addition, new adapter, new schema and new timing document; published original schema/timing files are retained.

The new schema preserves all original definitions structurally and introduces a separate v2 model-candidate root. Original byte parser/denied-key/type/producer/context/nested-observation/target/profile/consumer gates are called directly. Original model-candidate scalar future checking is replaced by ordered strict uint63 lower/upper/now checking; target and observation gates remain. There is no intermediary synthetic `completed_monotonic_ns`.

## Timing and action findings

`_validity` requires exactly four explicit bounds. Missing source or dispatch deadline yields Unavailable; no infinite default. Previous must be explicitly None or uint63. Age must be 1..100000000. Checked lower+age arithmetic rejects overflow even if another smaller cap could have bounded the result; this is documented conservative behavior. Effective validity is the minimum of lower+age, original source, original dispatch and supplied previous deadline, and must be strictly greater than now. Upper is used only for interval ordering/future validation; it cannot renew validity.

The action adapter preserves the frozen target and computes original issue+duration with checked integer arithmetic. A SET_TARGET's whole duration must fit under retained candidate and newly supplied action previous caps; delayed consumption or a duration one nanosecond beyond a cap fails. It returns a candidate with authority='none', never a command/grant. STOP carries no positive deadline and may be adapted later to stop; this is documented, matches unchanged STOP semantics and does not renew motion. Retained mappings are recursively immutable and input mutations do not alter the validated object. Direct user construction of a dataclass remains possible and is explicitly not provenance; callers must retain the actual validated object and original association.

## Independent execution

One new bounded process, timeout 25 seconds, actual 0.485 seconds, exit **0**, stderr empty. Eight focused checks passed; no author 11-method suite or other historical group was replayed:

- Default v1 retains its original nonnegative, unbounded caller-now behavior even above uint63, without loading the new adapter.
- A new interval/action can end exactly at uint63 maximum without overflow; the full action duration may end exactly at its finite cap.
- An action previous cap one nanosecond shorter refuses the same target duration.
- Advancing observed upper and now does not extend the retained minimum of source/dispatch/previous bounds.
- Now equal to the effective previous cap is expired.
- Changing input bounds/target after validation does not change immutable retained data; delayed full-duration reuse is refused.
- A zero-width observed interval with one nanosecond remaining can validate but cannot support a longer action.
- Lower at uint63 maximum plus a positive age is rejected.

The portable `independent_checks.py IMPLEMENTATION_DIR OUTPUT_DIR` builds new deterministic synthetic inputs directly and reads only the pinned private vendor and host/adapter modules. Exact executed script, case parameters, full observed candidate/error outputs, command, stdout/stderr and exit are retained. Neither author fixture/test code nor C28/C36/C40/model/PDE/native/board runtime was executed. `wire.py` and `motion.py` are original pure host-parser dependencies only.

## Versioned author evidence and limits

Read and verified raw stream hashes/exits [1,0,0]. Run01 failed before collection because jsonschema was missing: zero methods, not a product RED. Run02 passed eleven NEW methods against the same runtime and patched host hashes. Run03 is static verification, not another functional run. Dependency attempt01 timed out after inherited mirror discovery; its evidence remains preserved and is not characterized as official-only success. Attempt02 pins five official wheels and installs only to the private vendor. This review reused those verified bytes without downloading/installing anything.

The implementation supplies concrete validation and finite-action APIs plus an exact current-host patch. It does not yet join A's actual provider/native transcript or operate the PC_DIRECT authority. A must supply the original dispatch lower, entire RESULT-observed upper, immutable source/dispatch/previous caps and actual observation/context identity in the same host clock. Live source, run/BOOT/fault/collision/command-consumption and PC_DIRECT/HIL deadline checks remain required downstream. Serialization and frozen dataclasses are consistency data, not authentication, registration or motion authority. No physical/formal acceptance is implied; H01–H15, original29, bothH12, final100MHz/timing/1%/100ms and A-only board authority remain unchanged.

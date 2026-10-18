# Bounded LAS header and hardlink-fixture repair

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`C-las-header-and-portable-fixture-fix-20261018-v1`, worker
`/root/data_boundary_repair`, baseline
`31267d6c4ae284b8788ebb457f49c4ae5a49c60c`.

The repair addresses the exact B PR25 comments 6196800813, 6197182815 and
6197806056, saved as raw GitHub API response bytes in `review*.stdout.txt`.
`original/` contains byte-identical snapshots of the five owned source/test
files before any edit. `original_sha256.json` binds those snapshots and the
untouched canonical data/verifier files. No canonical data, labels, splits,
statistics, helper-provenance fields or verifier implementation were rewritten.

Both parsers now use one shared critical-header guard. VERS/WRAP/UWI/NULL
declarations may repeat before ASCII only when their parsed value text is
identical; conflicting declarations reject in either order. Every critical
declaration after the first `~A` or `~Ascii` marker rejects, including identical
values and declarations before the first row. Errors retain member and line.
Regression cases cover all four keys, lowercase mnemonics, both conflict orders,
LF/CRLF and one-byte chunk boundaries, and preserve the harmless duplicate case.

The verifier hardlink test copies preprocessing.json and the verifier entrypoint
into one minimal temporary product tree and creates the hardlink there. It runs
the copied entrypoint and checks both linked files and the original remain
unchanged. It uses the normal TEMP/TMP environment.

## Measured checks

Python 3.12.14, Windows; `DEEPEYE_FORCE_ARCHIVE` unset. The capture results retain
the exact commands, working directory, timestamps, normal TEMP/TMP values,
source hashes, exit codes and stdout/stderr SHA256. Raw subprocess bytes live in
the corresponding `.stdout.txt` and `.stderr.txt`; the capture wrapper's own
success is not the subprocess exit code.

| Capture label | Measured result |
| --- | --- |
| baseline_force_inventory | 23 tests, exit 0 |
| baseline_force_preprocess | 33 tests, exit 0 |
| baseline_verify_data | 48 discovered, 45 passed, 3 archive skips, exit 0 |
| red_inventory | 3 regression methods, 72 failing subcases, exit 1 |
| red_preprocess | 3 regression methods, 72 failing subcases, exit 1 |
| red_portable | fixture-layout assertion fails, exit 1 |
| green_inventory | all 26 tests pass, exit 0 |
| green_preprocess | all 36 tests pass, exit 0 |
| green_portable | same fixture-layout assertion plus actual hardlink CLI guard pass, exit 0 |
| candidate_verify_suite | 48 discovered, 41 passed, 4 pin-dependent failures, 3 archive skips, exit 1 |
| candidate_verify_cli | unchanged production verifier refuses both repaired helper hashes, exit 1 |
| verifier_unaffected | the other 44 verifier tests: 41 pass, 3 archive skips, exit 0 |
| verifier_historical | original parser snapshots with unchanged pins/data and repaired verifier test: 48 discovered, 45 pass, 3 archive skips, exit 0 |
| scope | all 15 human requirement identities verified, exit 0 |
| preflight | path discovery only, exit 0 |

The deterministic portable probe asserts that the hardlink source belongs to
the alias's copied temporary product tree. C's baseline test happened to pass
because checkout and default TEMP share C:. This probe is not a claim of an
actual second-volume run. B's actual cross-volume WinError 17 and original
48/44-pass/1-error/3-skip result remain in comment 6197806056.

The four observed repaired-candidate verifier failures are preserved, with no
weakened assertions:

- `CliOutputProtectionTests.test_output_allows_legitimate_report_path`
- `RealPinnedDataTests.test_force_offline_without_archive_is_blocked_not_usage_error`
- `RealPinnedDataTests.test_real_default_full_scope_is_blocked_exit_2`
- `RealPinnedDataTests.test_real_missing_archive_blocked_and_wrong_archive_failed`

Each expects historical production pins to pass before an absent archive yields
exit 2. The repaired helpers make the unchanged verifier return exit 1 first.
`verify_checks.py unaffected` excludes exactly those four, listing them in its
raw output; it is not reported as a full verifier pass. The historical check
uses original source snapshots in a private temporary copy. It is compatibility
evidence for historical inputs, never repaired-candidate production acceptance.

## Source-pin impact and safe follow-up

The unchanged verifier pins both helper sources; the historical preprocessing
document also binds its generating helper hashes. New live source identities:

- `data/force_inventory.py`: `86404425615f7551ce04907c9dbd6d7a40edca76372ad82a1a9655092a186932`
- `data/force_preprocess.py`: `1cc71d045065495d99a3f79c31107705cdc3a4942409a8decf6ae732501bc308`

Historical generator sources are retained byte-for-byte at
`original/data/force_inventory.py` (SHA256
`5bba8316ea36484df058dacb2289073ffb09ce19e401dfb297598b3e3cd10f47`)
and `original/data/force_preprocess.py` (SHA256
`75b2015c0ec9deab9a94a2032b77117124085631f2bd758a54c7ea7fdfdf2848`).

A separate main-owned provenance migration can bind repaired live helpers and
immutable original generator snapshots as distinct identities, keeping the old
JSON lineage unchanged. Merely repinning source hashes or rewriting historical
generator references would conflate the two. This worker changed neither pins
nor provenance and did not refit or reread the real archive.

`reviewable.diff.txt` covers all five source/test changes against the preserved
original bytes. `handoff.json`, `release.json` and `manifest.json` bind final
source identities, unchanged canonical inputs, raw results and ownership release.
The folder's `.gitattributes` preserves raw bytes during staging.

Contract unchanged: H01-H15,
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
frozen design `1011259415a0916054eb580687612580bc1e5f09`.
No model/accuracy, C01, live acquisition, runtime, synthesis, implementation,
board or system acceptance is granted by these software fixture checks.

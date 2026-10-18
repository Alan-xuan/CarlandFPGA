# Parser provenance migration evidence

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work
C-parser-provenance-migration-20261018-v1. Actual owner
`/root/host_contract_review`; source ownership transferred after the preceding
data repair worker's actual final/release. No commits, pushes, services,
credentials, SQL, peer messages, refit, labels or held-out evaluation were used.

The canonical verifier now separately pins three current helper modules and two
historical generator snapshots while preserving six frozen JSON documents.
`preprocessing.json` retains its original inventory/grouping helper hashes and
statistics. The two exact historical snapshot bytes are from published Git
checkpoint `31267d6c4ae284b8788ebb457f49c4ae5a49c60c`; retrieval hashes and
original Git blob identities are in `snapshot-source-receipt.json`.

The current parser modules remain mandatory pins. The historical inventory
cross-link selects the independently pinned snapshot by key membership. Only an
explicitly synthetic spec without that snapshot key can compare with its current
fixture helper. Canonical production cannot drop snapshots or use that fallback.
Missing files remain blocked/exit2; observed corruption remains failed/exit1.
Historical code is never imported or executed; only the unchanged grouping
helper is executed by this verifier. Output guards cover both new snapshot paths.

## Actual RED and GREEN

- Existing data-worker `candidate_verify_suite.*` evidence remains untouched in
  `evidence/ai/data_boundary_repair/`. Its four stale-pin failures are historical
  expected failures; the receipt here binds their exact original hashes.
- `red_new_boundaries.*`: after adding meaningful tests and before implementing
  migration, 57 tests discovered, 3 archive cases skipped, 10 expected failures,
  exit1. These include the four existing stale-pin failures and the new
  provenance-selection, forged-production and output-protection failures.
- `green_full.*`: full verifier suite with explicit
  `DEEPEYE_FORCE_ARCHIVE=<project-root>/.local/datasets/force-2020/LAS_files_Force_2020_all_wells_train_test_blind_hidden_final.zip`:
  57 tests, zero skips/failures/errors, 10.051 seconds, exit0. Exact Python,
  command, working directory, environment, source hashes and raw stdout/stderr
  SHA256 values are in `green_full.command.json`. No broad AI suite was run.
- `diff_check.*`: actual `git diff --check` for the two assigned modified source
  files, exit0. `reviewable.diff.txt` includes the preceding worker's preserved
  same-filesystem hardlink fixture and this migration's independent tests.

The nine added test methods exercise different current/historical hashes,
rejection of relabelled historical metadata, both missing/corrupt archived files,
both corrupt live helpers, failure precedence with a missing snapshot, archived
raising sentinels never executed, a production-labelled spec dropping snapshot
pins rejected before reads, and direct/hardlink output protection on a single
temporary filesystem. Existing ordinary synthetic fixtures keep nine pins and
remain explicitly synthetic. Canonical production and its report have11 pins.

The authorized archive cases hash/read the archive as a raw byte stream.
Existing real ZIP spies and the new synthetic import spy pass. No ZIP member was
opened, no LAS value parsed, and no statistic recomputed by verification. Frozen
JSON, grouping, archive identity and H01-H15 hashes are preserved in
`validation-summary.json`; generated code pins do not claim a repaired-parser
regeneration of those historical documents.

This evidence establishes the stated offline provenance/identity behavior only.
C01, actual multi-channel performance, sensor calibration, R03/runtime truth and
source liveness, HIL/PC_DIRECT, physical board and product acceptance remain open.
Contract DEEPEYE-HUMAN-LOCK-20261014/revision1 requirements SHA256 remains
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.

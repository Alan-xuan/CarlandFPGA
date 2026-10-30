C38 static source-review evidence

Reviewed A source: e794de598a40c11cefb372813aa950f58f03007a.
Parent: d9716760b15cd84c6b60442a9d9368fdcd0e46fa.
C38-R1 is OPEN; source_approved=false. No production occurrence is claimed.

Offline verification with Python 3.11+ standard library:

    python verify_static.py .

Run from this package directory, or give its directory as the only argument.
The script decodes the deterministic gzip/base64 JSON archive in memory, checks
all 21 exact byte counts, SHA256 and Git blob SHA1 pins, parses source without
importing it, reproduces five focused parent diffs and the qualified AST delta,
and checks the unchanged final-fence-through-return AST. It writes no files,
uses no network, and runs no A code or test. Hashes verify integrity, not custody
or authorship. The archive contains source, not API responses or session logs.

verification.stdout.txt/stderr.txt and verification-exit.json record only the
packaging/static verification run. Local function and runtime: NOT_RUN, exit null.
Source/API retrieval command summaries explicitly distinguish actual reviewer
GET exits from reconstructed equivalents for the nine reused cached files.

handoff-input-template.json is NOT a publishable canonical request yet. Main must
replace SOURCE_COMMIT_PENDING with the actual C source-evidence commit after
copying this package. Artifact paths are relative to the implementation-evidence
repository root, with the handoff directory shown in that template. Adjust paths
only if the actual repository layout differs. Then main alone uses canonical
handoff.py to create/verify manifest.json; no request hash is precomputed here.
The reviewed A commit and the future C evidence commit have different purposes.
Template stage status `failed` records the open static source finding; `passed`
applies only to byte/AST packaging verification. No runtime passes are implied.

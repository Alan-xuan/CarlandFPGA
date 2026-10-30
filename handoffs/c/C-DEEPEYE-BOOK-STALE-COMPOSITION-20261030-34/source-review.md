C34 source review and exact evidence package

Final C34 runtime is 849d083885875668f2701fedd1c855e88c81174f312c6e0cfb0619706ef5e336. R1 is closed; bounded diagnostic source approved. Formal/physical acceptance is false. H01-H15, both H12, original contract, acceptance requirements, and A-only board authority remain unchanged.

The original implementation review found one namespace defect, represented by three exact product RED inputs. The narrow repair adds all supplied raw contexts and capture generations to field-by-field consistency checking in _crosschecks. Request generation remains unknown; no config/binding/proof is invented. Independent repair review verified that the remaining module AST is unchanged, all four changed-file diffs and ABI documentation are accurate, and exact C32 -> sole original C28 reuse is retained. See original initial-review.md, REPAIR-REPORT.md, R1-CLOSURE-REVIEW.md, and archived normalized diffs/source pins.

Version-specific author history (process exits, not a single final-version suite):

| Invocation | Runtime SHA-256 | Exit |
| --- | --- | --- |
| run01-core | `ba97841fe4c1615b894ec83dafbf49a067b8cb7abfc07ba57366cb761c576f69` | 0 |
| run02-partial | `ba97841fe4c1615b894ec83dafbf49a067b8cb7abfc07ba57366cb761c576f69` | 1 |
| run03-time | `ba97841fe4c1615b894ec83dafbf49a067b8cb7abfc07ba57366cb761c576f69` | 0 |
| run04-caps | `ba97841fe4c1615b894ec83dafbf49a067b8cb7abfc07ba57366cb761c576f69` | 1 |
| run05-expectations | `ba97841fe4c1615b894ec83dafbf49a067b8cb7abfc07ba57366cb761c576f69` | 0 |
| run06-raw-missing | `ba97841fe4c1615b894ec83dafbf49a067b8cb7abfc07ba57366cb761c576f69` | 1 |
| run07-aggregate | `ba97841fe4c1615b894ec83dafbf49a067b8cb7abfc07ba57366cb761c576f69` | 0 |
| run08-raw-fix | `a8740a8662cbbb1f095bac001390f60b85c19df8c28bcf5ba3e0b192c619b740` | 0 |
| run09-capture-only | `a8740a8662cbbb1f095bac001390f60b85c19df8c28bcf5ba3e0b192c619b740` | 1 |
| run10-capture-fix | `f913c3f0d9188dc9f8d04e6f360061c081cd34da2d0dea57a61170e845333bbd` | 0 |

Author run02/run04 failures were expectation-string mismatches fixed in run05 on the same runtime; raw traces and tests remain intact. Run06 request-only and run09 capture-only failures were product predicates repaired in later runtime versions. The original independent38 on f913 exited1 (35 PASS/3 RED); author R1 eight and independent R1 ten on849d each exited0. Independent final ten consists of the exact original three failing byte strings plus seven NEW controls, not a rerun of old35 or author groups. local-evidence.json records exact runtime/test hashes and exits; the archive contains original logs, snapshots, failure inputs, output journals and source indices. No candidate, old suite or hardware was executed while packaging.

Archive recovery and integrity verification:

    python -B verify_evidence_archive.py PUBLIC_DIR OPTIONAL_NEW_EXTRACTION_DIR

This verifier only decodes/hashes files. evidence-archive.json.gz.b64 is base64 of a deterministic gzip JSON container; each archive entry references a SHA-keyed base64 blob so even compressed journals, BOMs/newlines and empty stderr restore exactly. evidence-index.json provides every source-relative path, byte count/hash and explicit exclusions. Current public sources are archived under final-public; original f913 public bytes under repair-r1-v1/original-public; each original author run carries its actual runtime and test snapshot. The original38 complete compressed input/output journal is included unchanged, not replaced by a summary. Existing successful author logs did not serialize every successful input/output: their exact test body and fixture data are included, but no trace is reconstructed or claimed original. Failed stdout includes original last_input/traceback. Native session/tool transcripts and cache files are excluded; main's compact actual audit records are included. Internal credential material is not part of the selected evidence.

Portable final narrow controls, if independently authorized:

    python -B independent_r1_checks.py PUBLIC_DIR independent-r1-data.json OUTPUT_DIR

These are exact copies of the executed script/data. PUBLIC_DIR needs its documented sibling hash-pinned C32 and C28 layout; archived dependency-snapshots contain exact bytes for offline inspection/reconstruction. The package does not run those controls automatically. Historical test files inside the archive are evidence, not instructions to rerun old suites. Main task and design decision are copied verbatim; task.json now provides18files/2097152B whereas the historical design budget remains unchanged within its original file.

No current/owner/admission/action/pose evidence is invented. Historical source70 remains exact-byte-only and unavailable; no synthetic now or interface upgrade is produced. Tests establish software association/validation, not provenance authentication, native interval validity, action authority or physical sensing. Missing actual Root evidence continues to block projection/core. Existing five public files are copied byte-identically, with no runtime or documentation edits. The main independently compared all199 archived entries to original files and reviewed actual closed worker calls, raw logs, exit codes and the14-line R1 source change. The delivered manifest.json is generated by the canonical project handoff tool and pins source plus frozen dependencies; its own hash is recorded in the delivery receipt. The packaging-only verifier was adapted by main for that canonical format; no runtime or functional-test body was changed. Package totals include the manifest. Main alone publishes.

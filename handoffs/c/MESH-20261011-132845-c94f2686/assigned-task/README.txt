Bounded offline fixture validator - handoff MESH-20261011-132845-c94f2686, C side
================================================================================

WHAT THIS IS
------------
A small, bounded, standard-library-only Python validator for saved JSON
fixture objects used in this handoff. It checks exactly four fields and
nothing else. It is local software only: it is NOT production Envelope
authentication or authorization, it never uses the network, the FPGA board,
credential stores or any external service, and it must not be used to
authorize real work.

FIXTURE CONTRACT (all four fields required; extra fields allowed and ignored)
-----------------------------------------------------------------------------
  task_id       nonempty string; empty or whitespace-only is rejected (the
                bare contract says "nonempty"; this validator additionally
                rejects whitespace-only and documents that choice)
  task_version  strict positive integer >= 1; bool is rejected even though
                Python bool is an int subclass; JSON numbers that are not
                integers (e.g. 1.0) are rejected
  owner         exactly "C/Astra-C"
  direction     exactly "A->C"

Additional fields are allowed and ignored: this is a bounded fixture
checker, not a full Envelope schema or signature check.

CLI
---
  python validator.py FILE
    exit 0  accepted; "ACCEPT: FILE: <summary>" printed on stdout
    exit 1  rejected; "REJECT: FILE: <clear reason>" printed on stderr
    exit 2  usage error (FILE argument missing or extra arguments)

FILES
-----
  validator.py                    validator module + CLI (stdlib only)
  fixtures/valid.json             accepted fixture: task_id
                                  MESH-20261011-132845-c94f2686-C-git-handoff,
                                  task_version 1, owner C/Astra-C, direction
                                  A->C, plus one extra field showing that
                                  extras are allowed
  fixtures/missing-version.json   rejected: task_version missing
  fixtures/negative-version.json  rejected: task_version -1
  test_validator.py               unittest suite: accept case; missing,
                                  negative, zero, bool and string version
                                  rejects; owner/direction missing and
                                  wrong; malformed JSON and non-object;
                                  extra fields; CLI exit code checks
  run_captures.py                 capture runner: re-runs the commands and
                                  writes raw stdout/stderr + metadata
  captures/*.txt                  actual raw captured output and
                                  captures/metadata.txt (command,
                                  interpreter version, exit codes)

COMMANDS AND EXPECTED RESULTS
-----------------------------
Run from this directory with the project venv interpreter; below PY is short
for C:/Users/Alan/Documents/ChatGPT/FPGA/CarlandFPGA-node-c/.local/venv/Scripts/python.exe

  PY -m unittest -v test_validator
      expected: all tests pass (no failures/errors), process exit code 0
  PY validator.py fixtures/valid.json
      expected: "ACCEPT: ..." on stdout, empty stderr, exit code 0
  PY validator.py fixtures/missing-version.json
      expected: "REJECT: ... missing required field 'task_version'" on
      stderr, empty stdout, exit code 1
  PY validator.py fixtures/negative-version.json
      expected: "REJECT: ... positive integer ..." on stderr, exit code 1
  PY run_captures.py --output-dir <new-directory>
      runs the four commands above and stores binary stdout/stderr without
      newline conversion, command lines, interpreter version and exit codes.
      Existing output directories are refused; preserve committed captures/.

SCOPE
-----
Local software only. Hardware: not_run. Synthesis: not_run.
Implementation: not_run. Simulation: not_run. No board results claimed.

EVIDENCE BINDING
----------------
The main agent independently reviewed the implementation, corrected the
capture runner to preserve exact subprocess bytes, and reran all tests.
The assignment.json records A's exact supplied operation and request hash.
The immutable manifest.json binds that supplied hash to the source commit
and the SHA-256 of evidence-manifest.json. The latter is produced by the
installed-equivalent skills/pynq-z2-single-node/scripts/handoff.py helper;
its request_hash is a separately calculated local evidence request hash.
These two request hashes have different definitions and are named separately.
All listed source/evidence bytes must match their blobs at source_commit.
The manifest is committed after that source commit to avoid self-reference.
No evidence covered by either manifest may be refreshed in place.
A's feedback and C's final receipt are separate records keyed to the final
PR head; subsequent commits require fresh review.

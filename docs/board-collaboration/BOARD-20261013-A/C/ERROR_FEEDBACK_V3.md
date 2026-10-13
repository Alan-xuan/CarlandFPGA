# C controlled error feedback, v3

Task `BOARD-20261013-A-C`, version 3; work ID `C-board-error-feedback-v3`;
owner C/Astra-C. This supersedes further large BRAM reviews for the current
delivery. The v2 plan and its immutable manifest remain unchanged historical
records; no new performance or custom RTL requirement is introduced.

`board_error_probe.py` prints one flushed JSON record containing the fixed
operation ID, supplied nonce and actual runtime, then deliberately raises
`RuntimeError('EXPECTED_C_BOARD_FEEDBACK_BOARD-20261013-A')`. It uses only the
standard library, does not import PYNQ, load an overlay or read/write peripherals.
Exit 1 plus the matching traceback is the expected observation. This is a test
of transporting and returning a controlled software error from A's board; it
does not indicate a faulty board or prove FPGA logic operation.

## A-only execution and return

1. Verify this PR's exact final head and
   `C/handoffs/error-feedback-v3/manifest.json` (under this task directory).
   Match operation `BOARD-20261013-A:C:error-feedback-v3`, requester `C`, task
   version 3, source commit and artifact hashes. Record the full PR head actually
   checked out and the script SHA-256 actually placed on the board.
2. A chooses a fresh non-secret nonce for this run. From the checkout containing
   the reviewed script, run with A's real board Python environment:

   ```sh
   python3 -u docs/board-collaboration/BOARD-20261013-A/C/board_error_probe.py --nonce <A-run-nonce> > c-probe.stdout.txt 2> c-probe.stderr.txt
   rc=$?
   printf '%s\n' "$rc" > c-probe.exit.txt
   ```

   If uploaded to a different path, record that actual command and verify the
   same script hash. Capture the exit immediately; do not let a shell pipeline
   replace it. The script needs no board-specific privilege.
3. Expected result: exit 1; stdout JSON has the requested nonce and operation;
   stderr contains a real traceback ending in the exact RuntimeError marker.
   A records the actual Python/environment and confirms execution was on the
   physically connected board. Runtime strings alone are not proof of location.
4. Publish raw stdout/stderr/exit files, sizes and SHA-256 hashes, the command,
   nonce, actual tested commit, request hash and operation ID as durable evidence
   referenced on this same C PR. Do not overwrite v2 evidence or retry an
   unexpected result automatically. C will verify the binding and report readback
   when A's evidence notification arrives. Final acceptance remains A's decision.

## C local evidence and limitations

`host-v3/` contains an actual Windows-host execution with a host-only nonce,
separate raw stdout/stderr, and a receipt. C checked the exit code and exact
exception marker. This host result is **not** a board measurement. C hardware,
RTL simulation, synthesis and implementation are all `not_run`.

The handoff's `code_commit` identifies the committed script and host evidence;
the later manifest commit is the PR head A must record as `tested_commit`.
The request hash follows `HardwareRequest` canonical JSON; the manifest freezes
all listed file bytes. Only the current v3 operation is a new board execution
request. The v2 BRAM check remains available as a short reference; it is not a
dependency of this controlled error roundtrip.

## Quiet notification rule

The installed C client skill already contains the human instruction to stop
automatic local/peer online, offline, reconnect and recovery announcements.
C checked the existing live SQLite suppression trigger read-only and found no
uncancelled pending legacy peer announcements. The existing suppression receipt
is in the separate quiet-presence checkpoint commit
`f9bad22` (this board task does not change that worker's files or restart service).
Only key board-test facts or actionable blockers are reported for this task.

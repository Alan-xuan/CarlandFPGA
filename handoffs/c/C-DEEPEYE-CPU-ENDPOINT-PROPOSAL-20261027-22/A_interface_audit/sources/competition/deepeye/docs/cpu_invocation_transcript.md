# Bounded raw CPU invocation transcript

Work A-CPU-INVOCATION-TRANSCRIPT-20261024-v1, task
DEEPEYE-IMPLEMENTATION-20261014/v1. Contract DEEPEYE-HUMAN-LOCK-20261014/revision1,
H01-H15 unchanged; requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.

`integration.cpu_invocation_transcript` records one opaque request write and
finite original OS output reads. It does not launch/adopt an actor, acquire an
endpoint, choose C's inference format, adopt DEEPEYE-PRIVATE-FRAMES/1, parse a
candidate, establish readiness or return completion/motion authority. It imports
no codec, actor, runtime, mailbox, executor or production provider. The existing
production gate remains closed.

## API and ownership

`InvocationIdentity(operation_id, request_hash, tested_commit,
package_manifest_sha256, run_id, invocation_id, actor_instance_id)` is an exact
frozen correlation record. Labels are strict strings of 1-192 characters using
letters, digits and `._:/-`, beginning with a letter/digit. Digests are complete
lowercase SHA256 values; tested_commit is 40 lowercase hex characters;
invocation_id is a strict integer in 1..2**63-1. Bool and subclasses refuse.
These fields do not authenticate the actual operation, actor, package or model.
request_hash is the operation's supplied correlation hash; the exact opaque
request's separate SHA256 is computed and recorded without confusing the two.

`InvocationTranscript(input_fd, output_fd, identity, *, request_raw,
journal_path, max_output_bytes, max_reads, read_size, host_clock=None)` accepts
only exact nonempty bytes up to 16384. Required budgets are 1..16 MiB output,
1..65536 read attempts and 1..8192 bytes per read. The owner supplies existing
connected descriptors and bounded blocking policy. Descriptor type checks accept
OS pipe/socket/character descriptors and reject regular replay files; they do not
establish connection, exclusive reader/writer, endpoint authenticity or actor
ownership. Each descriptor is duplicated, non-inheritable and binary on Windows;
only those duplicates and the newly created journal are owned here.

The journal uses exclusive `xb` creation and has no resume/reopen branch. Owner
thread and clock/callable identity are fixed. A non-None clock must be the exact
existing fresh-run QpcHostClock; ordinary callables refuse. None retains legacy
monotonic routing. Raw stamps must be strict bounded nonregressing integers;
the initial high-water is None until an actual selected-clock stamp returns.
Clock metadata is diagnostic and never supplies uncertainty. Exact object/type
checks are trusted-process conventions, not an OS security boundary.

This object does not enforce global invocation/session uniqueness across new
objects, processes or different journals. Trusted main must retain the original
owner and reconcile uncertain operations before any new run. Creating another
object or journal is not permission to replay an old invocation.

## One dispatch, original read facts

`dispatch_once()` returns a detached diagnostic row only after one fully recorded
successful OS write. It reserves the attempt before the first clock sample, saves
and flushes/fsyncs `started_unknown`, then performs exactly one os.write with the
original request bytes. There is no remainder write or retry. Actual returned
count is recorded before post-write stamping. Partial/error/interrupted writes,
stamp errors/regression, journal failure and caught reentry/foreign veto close
new I/O admission permanently. A known count remains known; an interrupted write
with no returned count stays None, even if bytes may have been sent.

`read_once()` is allowed only after a fully recorded successful dispatch. It
returns a detached row with kind `data`, `empty` (actual BlockingIOError/EAGAIN)
or `eof` (actual zero-byte return), original raw_hex/count, continuous known
stream offsets, read_index and a raw call bracket. There is no parser/framing or
completion classification. Every read attempt consumes its read budget; requested
size is clipped to the remaining original byte budget. EOF and exhausted budgets
refuse any further OS read.

The read attempt, failure latch and unknown row are reserved before OS I/O. A
started row is also journaled before the read. Returned raw chunk/count/offset
facts are saved before the trailing stamp. If an interrupt consumed bytes without
returning them, raw_hex/returned_bytes remain None, unknown_consumption is true
and the object never reads again. bytes_read always means the known returned
prefix, not total bytes consumed when that total is unknown. Post-read stamp
failure retains all returned bytes/counts and leaves the end None. Any error or
journal failure permanently refuses further read/write admission.

Normal duplicate-dispatch, read-before-dispatch and EOF/budget refusals perform
no new I/O; they do not create an alternate retry or completion path. Caught
reentrant operations cannot reopen an outer operation: the outer transaction
checks its retained veto before reopening admission, and every future entry also
checks the irreversible veto counter independently of the temporary I/O latch.
A veto after the final checkpoint therefore still blocks the next operation.
Unknown side effects never
become a zero-byte claim.

## Evidence and limits

`snapshot()` is detached and remains available to the original owner after
failure/close. It includes exact request bytes/hash, correlation labels, dispatch
and read rows, journal/clock/failure/EOF/budget facts and close errors. Raw brackets
are diagnostic only. write/read call intervals, availability, source sample and
completion intervals remain None in both clock modes. No value is inferred from
100 ns advertised resolution, a read bracket or a READY/model_candidate string.

Output already queued before dispatch is preserved as raw output and is never
marked fresh, ready, complete, useful or caused by this request. A future fixed C
entry/provider must separately establish original endpoint/instance/package,
invocation/causal association, approved input/model computation and actual timing
bounds before constructing any authority record. Hashes/labels do not supply it.

Each journal append flushes and calls os.fsync; a returned OS sync call is not
independent power-loss durability measurement. The module adds no timeout,
background thread, timer, model loop or hard cancellation bound. Main must supply
nonblocking/bounded transport and supervisor policy separately.

`close()` is same-owner and closes each owned duplicate/journal at most once,
retaining any close failures. It never closes the caller descriptors or resumes
I/O. Constructor cleanup attempts each acquired duplicate once even if one close
reports failure, preserving the primary constructor error. Reentrant close only
vetoes admission; actual cleanup waits for the owner operation to unwind.

Verification runs only this module's new focused controls with actual local OS
pipes/journals and private scripted legacy/QPC leaf/capability seams. No actual
product-clock observation, sleep, policy consumption, model, native actor, board,
serial, UI, service, network or old suite is run. Hidden-consumption test witnesses
are explicitly test-seam knowledge and never filled back into the transcript.
G03/R03/all29 and formal acceptance remain not_run/unestablished.

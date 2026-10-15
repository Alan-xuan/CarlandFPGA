# C motion-request adapter software evidence

Work: `DEEPEYE-IMPLEMENTATION-20261014/version1`,
`C-motion-request-adapter-20261015-v1`. Fixed design
`1011259415a0916054eb580687612580bc1e5f09`; initial worktree base
`6e1624d0b0ae3f46adaded330f0bc23840ac9886`. H01-H15 identity:
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
This helper preserves scope; its unit tests do not close product cards.

`motion_request.py` is a pure standard-library helper. `HostContext` holds all
seven A context fields. `SentObservation` explicitly maps an internal sent
ordinal, the wire sample sequence, extended last-ADC tick and measured sample
interval. Register at most four legal sent observations, then call
`MotionRequestAdapter.submit(candidate_bytes, host_issue_ns=..., now_ns=...)`.
The candidate bytes must be a complete A `model_candidate` JSON envelope.
Existing mailbox `Candidate.payload` must pass this strict parser; mailbox
validation alone treats the payload as opaque and is insufficient.
Contexts are revalidated through class methods at public boundaries and before
emission; their negotiated values cannot change. Stored observation values are
detached snapshots, so forged mutation of a caller's original object or a public
copy cannot rewrite the retained sample.

The adapter accepts already quantized integer targets and independently checks
the full target whitelist, combined curvature, zero-speed rule and duration
caps. Candidate IDs are global monotonically increasing session identities,
distinct from mailbox generation ordinals and sent ordinals. Request sequence
is allocated once per emitted request. Neither candidate nor request identity
wraps or reuses; seq16 exhaustion requires STOP and a new session. Extended
uint32 acquisition ticks can cross rollover only within a same-session anchor's
strict half-range bound. Sequence wrapping is a different rule and is refused.

`RequestDecision.request_bytes` contains only A's exact `motion_request` keys.
Original issue, sample interval, requested duration and deadline are frozen
audit metadata outside those bytes. The deadline is the minimum of original
issue plus duration and original sample lower bound plus the profile age cap;
expiry is `now >= deadline`. Replayed/changed/reordered candidate identities
raise `MotionRequestError`. A structurally valid candidate is retired even if
it is blocked. Transport retries must preserve the original bytes and timing;
they cannot resubmit a retired candidate to acquire a new issue or expiry.
An original deadline above signed63 range blocks without fabricated timing.
A's HIL authority still tightens this bound using actual capture and remaining
TTL. Heartbeats and ACK/STATE responses never register as new observations.

The default runtime verifier is absent, so non-STOP candidates return
`must_stop=True`, `request_bytes=None`. A trusted runtime integration must
implement `verify_motion(RuntimeCheck) -> None` and verify actual evidence for
the complete immutable check: authenticated BOOT/context and actual sent
observation provenance, measured clock/USB/rate/holdover bounds, model/source
liveness (including A's source-heartbeat bound), and applicable link and slot
gates. Failure or any non-None result blocks. Numeric fixtures, booleans and
measurement hashes are not authentication. The test verifier is explicitly
fake and supplies no runtime proof. Process/pipe ACL, world authority,
collision/route legality and physical-capture validation remain external gates.

On block, the transport owner must stop; this helper cannot stop hardware.
`safe_stop(now_ns=...)` builds a new all-zero STOP with null observation, even
with an empty/stale mailbox or absent clock/source/model proof. A malformed
host clock or exhausted request identity yields no fabricated request.
`movement_authorized` is always false. No `motion_grant` is constructed.

Use one adapter and one candidate-ID allocator per negotiated session. The
caller must not recreate the object to reset history in an existing session.
No live mailbox/scheduler/pipe integration is claimed by these additions.

`reference/` holds A PR24 exact bytes from commit
`d5bf26adcf76f8c9af3165cdd7043cb3ff19649b`. `manifest.json` binds each copied
file's Git blob SHA1 and SHA256. These are unchanged independent test fixtures,
not C changes to A's schemas or execution authority. The production adapter
does not import them. Tests import A's original validator and compare integer
curvature boundaries against its original motion reference.

From the deployment root, using existing system Python with `jsonschema`:

```powershell
python -B -X utf8 .local/deepeye-implementation-c/competition/deepeye/evidence/ai/motion_request/run_evidence.py
```

Each `run_NNN/` preserves command arguments, working directory, interpreter and
dependency versions, raw stdout/stderr bytes, exit codes, source hashes and
stage limitations. Initial fixture capture additionally used
`--reference-source .local/main-20261015-01a14025/host-contract-review`.
The local deployment virtualenv has no `jsonschema`; system Python's already
installed dependency is used only for A's fixture validator. No dependency or
service was installed or changed. Authenticated runtime, PC_DIRECT/HIL
execution, real sensors, physical board and system acceptance remain not_run.

Root review repair `C-motion-request-adapter-review-repair1-20261015-v1` is
documented in `review_repair1/README.md`. Original sources and run001/run002
evidence are preserved. Its negative control runs the new three regression
tests against the rejected original source and must exit1; current-source
tests must exit0. Command manifests record those distinct expected exits.

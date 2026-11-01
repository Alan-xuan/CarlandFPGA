# C48 R1 independent closure review

**C48-R1 closed; bounded source approval=true** for module
`925ca8ecb9fc4c719e1eb4558cb11346111f77f79b6a6f40a6dc905f5b772ef5`.
There are no open findings in this repair scope. This supersedes the earlier
source rejection only for this exact replacement; the original RED and six
initial parser controls remain sealed with their original limitations.

The exact incremental change affects only `_capture` and the `CaptureCycles`
docstring (AST checked). It separates global64 applied/result/deadline from
zero-extended rearm-local32 start/end, rejects nonzero high words, and retains
local positive start/order, high/period, span length and three-channel join.
It invents no epoch or offset. README and API now describe the separate origins.
Both incremental and full replacement patches independently reconstruct the
exact final module bytes.

The original primitive SHA256
`4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456`
was read in full and verified against retained GitHub response bytes/path/blob.
At lines178–181 rearm sets tick0 and clears the partial candidate; lines218–230
reject witness exhaustion and set witness_now=tick+1; lines237–239 start only
at that positive witness. Lines300–316 require strictly interior falls and
publish original start/end with elapsed period. Thus start0 is not a valid
completed witness. The engine's actual WITNESS_W=32 and zero-extension remain
the reason for the32-bit bound, not a newly invented unit conversion.
Global lifetime and same-local-domain join checks from the first review remain
unchanged and consistent with the inspected source.

Verified62 repair freeze files,13 source byte/hash/blob pins, original repair
FINAL `e7ba201c641dd736b9f53fffcb5a0d2aa9c839977599cc1ac7b46341cc04a39a`,
and author raw repair01/02 exits[0,0]. The13 author's new controls are actual
final-source evidence; repair02 is byte-patch verification, not a product test.
No author's suite was rerun. Exact original source and raw-log matches are in
audit.json.

Only two independent affected controls ran, together once with30s bound, exit0:

1. Replay the original failing input's exact bytes, SHA256
   `00cbe99b27927b3081c8db9f9cd079c725f6ce3b74a36f6020d6fb190b4b5ed2`.
   It now accepts APPLY and retains global applied9223372036855775808,
   result9223372036855776108, deadline9223372036865775808 separately from
   local starts[20,21,20]/ends[147,148,147]. Original words, input bytes and
   immutable CaptureCycles are checked.
2. Set all six local witness high32 words to1 in both capture and original raw
   CSR read copies, preserving periods and joins. It rejects with
   `local witness must be zero-extended uint32`. Exact input SHA256
   `626385627b04bbf79549caed94b9770d49fcab4881b0e64a584bc631c517886c`.

The first static audit attempt exited1 because this review's patch reader did
not account for CRLF patch text versus LF source. It stopped before any candidate
import. The exact initial scripts, command/stderr/exit remain preserved.
Normalizing only patch line terminators fixed the audit reader; audit02 exit0
then rebuilt source byte-for-byte. This was an evidence-tool defect, not a
product RED, and no product controls were repeated.

Approval covers bounded detached CSR consistency only. JSON and constructible
history do not authenticate Root/board/issuer, clock provenance, source origin,
one-use consumption, actual completion, motion or performance. Original
request.stop and selected caps still require original Root correlation.
B132 waveform-to-motion mapping remains outside this module. No A source,
RTL simulation, core, native, model, PDE, board or old suite ran; no publication
occurred. H01–H15 and both H12 remain unchanged and formally unaccepted.

Public excerpt: private session-identification footer omitted. The exact full private review is retained under its SHA256 in main-approval.json.

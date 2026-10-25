# Bounded constructor preflight repair

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, parent
`C-CPU-CAUSAL-STREAM-CORE-20261025-v1`, repair
`C-CPU-STREAM-BOUNDED-INIT-REPAIR-20261025-v1`, operation
`C-DEEPEYE-CPU-STREAM-CORE-20261025-21`. Actual author
`/root/cpu_package_runner`; main `01a14025-4dfd-7ec3-aebb-57be48daba59`.
Both prior author and independent Phase2 reviewer had actually stopped/released
before main transferred this narrow source ownership. Base remains
`e3f86f7301abef866c30de2ec851e4a939198381`.

All H01-H15 remain under `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
design `1011259415a0916054eb580687612580bc1e5f09` unchanged. Only A operates the
physical board. This is scoped software repair evidence, not runtime/quality/
board/formal acceptance.

**Actual independent R1 RED:** constructor source
`0ddbe6710be81df3e428f63809257dea69c35fee1aabd24cd9bb58eb71b41976` passed
no finite cap for3sources+4references+direct scaler. The unchanged helper read
the whole file before checking its hash; a later loader cap did not bound that
earlier allocation. Independent Phase2's one-method assertion recorded
`read_size=-1`, actual exit1, without returning fake model/source bytes or
allocating an oversized file. Exact raw copies and the original control/report
are under `historical-independent-R1/`; originals remain untouched. This was a
new confirmed defect, not a production oversized-asset incident.

The new module now explicitly caps all those eight calls at2MiB; the manifest's
existing2MiB cap is unchanged. Every preflight reads at most2MiB+1 and rejects
length above cap before hash/parse. Source repair is only one fixed cap constant
and those call arguments: see `minimal-source-repair.diff`. No old runner,
loader, model, scaler, C19/C20 evidence, old test or format was edited. This is
not a2MiB bound on the Torch process/workspace.

**New actual author controls:** `controls-01/` contains exact argv/cwd/source
snapshot/raw stdout/stderr/exit;4methods, zero skips, exit0. The underlying
preflight read requests were2097153bytes at all nine positions:
3source, manifest, graph, weights, reference preprocessing, label schema and
direct preprocessing. It also checked27independent invalid-position cases
(9oversize,9short bad-SHA,9missing), each rejecting before model loading.
Oversize uses a length-only synthetic return object: no oversized byte buffer,
file, fake model, logits or model allocation occurs. Bad-SHA uses short wrong
bytes; missing is a synthetic FileNotFoundError. These are instrumentation
controls on actual requested read sizes and rejection order, not claims that
real assets were replaced on C.

One additional successful construction loaded the original real JSON model
once and processed one constructed unit-boundary observation through the actual
learned CPU forward. That observation is not licensed public-row, physical
sensor or model-quality evidence. Its12finite probabilities/tensor digest are
in stdout. C used existing CPython3.12.14/Torch2.9.0+cpu, no installs or NumPy;
the actual NumPy warning remains in stderr. No old/full16 suite, old execute,
all128baseline, training, heldout or ten-repeat benchmark ran.

Historical `../author/delivery-manifest.json` SHA256
`220f3c1bdcfc6722da937be45d9e41da587a09563733e0045894f66471315511` is preserved
byte-for-byte. It binds the **pre-repair** source/doc snapshots and is explicitly
historical, not a verifier of current live source paths. All original author
evidence bytes and old `test_stream_core.py` remain unchanged; historical
16first-snapshot controls and1later end-error control retain their original
source attribution. `historical-author-readback.json` records that byte check.
The new `delivery-manifest.json` binds current source/doc, unchanged original
test, new constructor test and this repair evidence separately.

R1 is author-repaired, awaiting independent Phase3 on the newly frozen source.
No final full16 rerun or independent closure is claimed here. FORCE quality
still FAILs; missing sim_em/scales, qualified map/planner, A lifecycle/clock/
runtime integration, both complete control paths, board and all unmet formal
gates remain incomplete. Results retain `movement_authorized:false`; there are
no motion bytes, services, network/peer sends, credentials, SQL, locks, new
children, Git index/commit/push or board actions in this repair.

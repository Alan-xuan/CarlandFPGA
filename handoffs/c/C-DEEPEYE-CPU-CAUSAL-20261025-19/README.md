# C causal CPU package handoff

Task DEEPEYE-IMPLEMENTATION-20261014/version1; operation C-DEEPEYE-CPU-CAUSAL-20261025-19.
Source commit `2022e767b1ec8243d0ff7b9a0b1577425a37824b`; source tree `e688bd79388e290ef54fe04325790c396842afce`.
Canonical request SHA256 `d3cb13c511db0717983e98273abdf3bed28713dd9e2ca82643520eb759fb1e77`; the manifest binds all 127
source/model/test/raw-evidence files to the source commit. The following metadata
commit adds only this README, input.json and manifest.json.

The frozen design is `1011259415a0916054eb580687612580bc1e5f09`.
DEEPEYE-HUMAN-LOCK-20261014/revision1, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` remains unchanged. All H01-H15 and both H12 control paths are required.

Start with `competition/deepeye/ai_pc/cpu_package/README.md` and
`A_HOST_MAPPING.md`. The package uses actual frozen learned FORCE lithology
weights and a public causal 128-record fixture. It requires no archive, labels,
scene truth, network, broker or board. Output is always non-authorizing.

Original author logs retain one 5-epoch training process exit0, the final
20-method/zero-skip suite exit0, and one real 128-prefix CPU invocation exit0.
The earlier affected-suite-final and portable-diagnostic are RED exit1 and
remain preserved; affected-suite-green is the actual final exit0. The copied
independent_review records an actual separate one-window numerical control
exit0 and saved confusion-matrix arithmetic; it did not rerun training,
heldout inference or the author suite. Captured absolute C paths identify the
original execution and are not the portable invocation instructions. CRLF raw
evidence is intentionally preserved byte-for-byte by .gitattributes.

**Heldout quality FAIL:** fixed12 macro-F1 0.1827348057438266, below the
TRAIN-only centroid 0.2047004573101128 and fixed target0.60. The package does
not establish useful full-system AI or acceptance. A has not adopted this
offline schema. sim_em_v2/fitted scales, causal online map/planner, A source/
clock/runtime integration, both complete control paths, all29 formal cards,
simulation/synthesis/implementation/board/system gates remain incomplete.
Only A operates the physical board. Existing public ABI and runtime authority
are unchanged; no motion bytes, BOOT/STATE, freshness or grant are invented.

The recorded 0.30615ms median covers one final tensor's forward/softmax/finite
checks/host probability materialization only. Whole compute was2560.9894ms,
excluding JSON/output I/O. Neither is a sensor, board or real-time guarantee.
The original Torch2.9CPU environment was used; A's HIP environment was not
modified or tested. Reproduction must report its actual runtime separately.

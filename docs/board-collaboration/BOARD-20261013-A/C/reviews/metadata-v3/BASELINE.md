# C metadata compatibility review baseline

Task `BOARD-20261013-A-C` version 4; work ID
`C-metadata-compat-review-v4`; reviewer C/Astra-C. Only this review directory is
owned by this task. B owns the implementation and tests. A/root Desktop remains
the sole board operator. This baseline does not approve an unfrozen replacement.

## Existing failure and scope

The reviewed old B head is `bb0d302331785defb59fc8d47eeea5d27fb33e81`, source
`3f9e9a52c950c0bbac24675e7fb49c8fe46a50c7`, operation
`BOARD-20261013-A:B:base-bram-v2-reset-origin-r1`, request
`ee52a9f5330b8a5a8a04367a5bd1f18b233d739b1b865941850846fef53dc28d`.
Its script SHA-256 is
`fde7bc99aca19ef32ff0137c5045e4262fa5a3eac1b080465f964105a7c6384f`.

The old `metadata()` unconditionally reads `overlay.ip_dict[IP_NAME]` at line
58. A's actual execution loaded the pinned stock Overlay, then raised metadata
`KeyError('iop_pmoda/mb_bram_ctrl')`: exit 1, no timeout, zero comparisons and no
reset/BRAM test access. B's earlier 22 passing host tests did not cover the
memory-only dictionary. B's additional host diagnostic and C's existing
memory-only reproduction both identify the same failure; neither is a board run.

Read sources and existing conclusions:

- [B memory-only diagnostic](https://github.com/carolwjade/CarlandFPGA/pull/9#issuecomment-6141788284).
- [A measured failure](https://github.com/carolwjade/CarlandFPGA/pull/9#issuecomment-6141929443)
  and [B readback](https://github.com/carolwjade/CarlandFPGA/pull/9#issuecomment-6142007242).
- [C metadata finding and earlier source review](https://github.com/carolwjade/CarlandFPGA/pull/9#issuecomment-6142154924).
- [C reset-origin/counting review](https://github.com/carolwjade/CarlandFPGA/pull/9#issuecomment-6142211820).
- C's tracked old review at commit
  `8945ce2b84236560f84ba297ca9540d9c8862921`, directory
  `docs/board-collaboration/BOARD-20261013-A/C/reviews/pr9-bb0d302-v2/`.

## Gates for B's new frozen delivery

The proposed new B operation is
`BOARD-20261013-A:B:base-bram-v3-metadata-r1`, B task version 3. The new source
commit, final head, request hash and manifest must be recorded explicitly. Old
requests and measurements cannot establish a pass for the new head. Preserve
the old PR7/PR8/PR10 evidence without modifying it.

| Gate | Required review evidence |
| --- | --- |
| File identity | Match actual bit/HWH bytes to the authorized SHA-256 values before trusting their metadata. |
| HWH identity | Prove the exact target module full path `iop_pmoda/mb_bram_ctrl`, AXI BRAM controller VLNV, PS-visible base `0x40000000` and size `0x10000` from the selected HWH. |
| Reset identity | Correlate the selected HWH/reset metadata to `mb_iop_pmoda_reset`, index 0; do not infer a Linux GPIO number from a constant. |
| Memory compatibility | Accept a justified memory-only runtime entry. Its synthetic `DDR4` type is not evidence of AXI core identity. |
| Conflicts | Every present runtime address/range representation and relevant ip/mem entry must agree with the verified HWH. A conflicting alias, wrong HWH or missing identity must fail before reset or MMIO access. |
| Side-effect order | Complete identity/range checks before reset snapshot/export/hold and MMIO construction. Keep Overlay loading distinct from test accesses. |
| Regressions | Review and reproduce B's submitted bounded host regressions; check the existing ip-only path, memory-only path and rejection before side effects. Do not add another implementation or broaden the test scope. |
| Immutable handoff | Recompute canonical request hash and each artifact length/hash using raw Git blobs. Check source/head equality for the executed script and report exact local commands and versions. |

Authorized preinstalled file hashes remain:

- bit: `ecabdcb5d483c75335ab6f043824a2386971c7b0ffd6e3315f24860bf5088eb6`
- HWH: `cbd90c84f3a46d1eba95dff7ba7d0079812f7e46641a08e2318c9928cd36ce8f`

A's actual metadata/HWH export is the pending precise basis for the compatibility
review. A fabricated miniature HWH fixture alone does not prove compatibility
with the real selected HWH. Review output will distinguish real exported data,
host mocks, source inspection and A's later physical measurements.

## Existing behavior that must remain intact

The old source inspection confirms the declared successful path: three rounds,
eight batches per round, 16 words per batch; write all 16, then independently
read all 16. There are 384 test comparisons, separately 16 original snapshot
reads and 16 restoration comparisons. Totals are 400 writes and 416 reads. The
window is offsets `0xFC00..0xFC3C`, occupying 64 bytes ending at `0xFC3F`.

Hold reset as output high while snapshotting, testing and restoring BRAM. Restore
all original words and verify the independent readbacks plus reset-high state
before restoring the observed reset direction/value. Unexport only if this run
exported the GPIO. A newly exported GPIO's initial value is a post-export
observation; the pre-export output latch remains unknown. If BRAM restoration
cannot be verified, withhold reset restoration and unexport, attempt to retain
reset high, and report failure. The metadata fix must not weaken this order.

## Current state

Baseline source and prior evidence read; no new B head was available in the
initial PR9 snapshot (it remained `bb0d302`). New-head compatibility review and
regression reproduction are pending B's frozen handoff and A's export. This C
task has not changed B files, created a worker, run a board probe or repeated
the old tests. C hardware status remains `not_run`. A will decide physical
execution and final functional acceptance after the new review.

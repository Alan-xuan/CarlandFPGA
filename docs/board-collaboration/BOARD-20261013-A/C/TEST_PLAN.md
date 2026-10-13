# C independent AXI BRAM review, v2

Task `BOARD-20261013-A-C`, version 2; owner C/Astra-C; work ID
`C-base-overlay-bram-review-v2`. A/root in the current Desktop session is the
only physical-board operator and final acceptance owner. This document is a
test proposal and review contract, not a board result.

## Scope and provenance

Version 1 proposed LED GPIO readback. A superseded it before C committed a
handoff or operated hardware. AXI GPIO output DATA reads return zero, and an
output driver's software shadow does not establish a hardware observation.
See [AMD PG144](https://docs.amd.com/r/en-US/pg144-axi-gpio/AXI-GPIO-Data-Register-GPIOx_DATA).
Version 2 tests the preinstalled base overlay AXI BRAM; no custom RTL or optical
LED claim is included.

A reports PYNQ 3.0.1, Python 3.10.4, Pynq-Z2, one device, a working root login
environment and `XILINX_XRT=/usr`. Before loading base, A observed null
`PL.bitfile_name` and `timestamp`, with the FPGA manager operating. These are
peer-reported facts until bound to A's durable board evidence, not C measurements.
Only the post-load BRAM words and MicroBlaze reset state are restoration targets.
Loading base is not reversible by this script; no full pre-load configuration
restoration is promised.

Expected preinstalled pair reported by A (A must hash the actual resolved files):

| File | SHA-256 |
| --- | --- |
| base.bit | ecabdcb5d483c75335ab6f043824a2386971c7b0ffd6e3315f24860bf5088eb6 |
| base.hwh | cbd90c84f3a46d1eba95dff7ba7d0079812f7e46641a08e2318c9928cd36ce8f |

Record the absolute resolved preinstalled paths, pairing, file sizes, hashes,
image/package origins available on A, actual versions, command and return code.
Matching these hashes establishes identity with A's selected pair; it does not
independently prove vendor origin. Stop on a mismatch; do not silently substitute
another bitstream. Use generic `pynq.Overlay`, avoiding peripheral initialization
from `BaseOverlay`. Clocks and reset wiring are inherited from the selected base
HWH; this task adds no clocks, timing constraints, synthesis or implementation.

## Identity and boundaries

Before writes, validate the exact B PR head and its immutable manifest:
operation `BOARD-20261013-A:B:base-bram-v2`, task version 2, request hash, code
commit and all artifact hashes. A must execute that reviewed head. Any later
head invalidates the review binding and requires a new review record.

Obtain `iop_pmoda/mb_bram_ctrl` from the loaded overlay's `ip_dict`; require the
`xilinx.com:ip:axi_bram_ctrl` VLNV family and validate its actual physical address
and range. The selected environment expects base `0x40000000`, size `0x10000`.
These are comparison values, never a fallback for missing metadata.
Obtain `mb_iop_pmoda_reset` from metadata too; index 0 is A's reported expectation,
not permission to guess a GPIO number. Record mapped reset identifier and
observed initial/held/final values without publishing private board identifiers.

Use 16 aligned 32-bit words at byte offsets `0xFC00 + 4*i`, `0 <= i < 16`:

| Quantity | Expected |
| --- | --- |
| first word offset / address | 0xFC00 / 0x4000FC00 |
| last word offset / address | 0xFC3C / 0x4000FC3C |
| last occupied byte / exclusive end | 0x4000FC3F / 0x4000FC40 |
| aperture inclusive end | 0x4000FFFF |
| window size / bytes remaining after window | 64 / 960 |

Require nonnegative aligned offset, 16 words and `offset + 16*4 <= addr_range`.
No accesses outside the selected window. Reject wrong IP/type/range, missing
metadata, bad hashes and unsupported reset access before destructive writes.

## Stimulus and observation

For each pattern write all 16 words, then independently read all 16 words.
Repeat eight patterns for three rounds: exactly `8 * 16 * 3 = 384` comparisons.
The separate C reference generator supplies values and addresses:

1. `0x00000000`.
2. `0xFFFFFFFF`.
3. `0x55555555`.
4. `0xAAAAAAAA`.
5. `0xA5A50000 | i`.
6. `(~(0xA5A50000 | i)) & 0xFFFFFFFF`.
7. `1 << i` (bits 0 through 15 only).
8. `random.Random(0x20261013).getrandbits(32)` in index order, 16 calls.

The reference builds this table once and reuses it for each round. Compare B's
documented RNG convention explicitly; do not silently reseed per word or accept
a different stream as matching this reference.

Observations must come from `MMIO.read(offset, 4)` or equivalent actual mapped
memory reads. The PYNQ 3.0.1 [MMIO implementation](https://raw.githubusercontent.com/Xilinx/PYNQ/v3.0.1/pynq/mmio.py)
reads its mapped array (or device register hook); normal memory-mapped writes
assign into that mapping. A must identify the real device/backend used. A Python
list of expected values, return of a written value or GPIO output shadow cannot
substitute for this read. Log each actual read, expected value, round/pattern/index,
offset and comparison outcome. Backup/restore reads do not count toward 384.

## Reset and restoration

Capture post-load reset state before changing its value or direction; hold the
MicroBlaze in reset (`1`) throughout backup, test and BRAM restoration. Confirm
the hold through a real state interface. Back up all 16 words before any test
write. PYNQ 3.0.1 [GPIO source](https://raw.githubusercontent.com/Xilinx/PYNQ/v3.0.1/pynq/gpio.py)
rejects output reads via `GPIO.read()` and writes direction during construction.
Consequently, review acquisition order, sysfs value/direction access and any
constructor-induced transition. A cached reset value is not an observation.

Install exception protection before the first reset or data mutation. In
`finally`, write all saved words, independently reread and compare all 16, then
restore the initial reset state and verify the actual value. Record each phase
separately. Protect reset cleanup if BRAM restoration raises; keep both the
original error and any cleanup error. A failure cannot produce a passing result.
If recovery cannot be verified, A decides safe next action explicitly; no
automatic rerun of destructive writes. An incomplete backup must never be filled
with invented values and written back. Expose Ctrl-C through cleanup; SIGKILL,
power loss and host failure cannot be guaranteed by Python `finally`.

## Local fault checks, then A-only run

C will exercise the exact B source with hardware-free injected interfaces. The
mock must implement reads independently of expected data and allow corrupt reads,
dropped writes and write/read exceptions. Check normal count/order, first/last
address, restored nontrivial initial data, reset initially 0 and 1, mismatch
detection, mid-test exception, incomplete backup and restoration failure. Assert
non-success on failures and inspect reset cleanup order. These are software
tests, not RTL simulation or board results.

A's real run is authorized and scheduled by A after source review. Evidence must
contain all 384 real comparisons with no mismatch, the 16 saved and restored
values with real readback, reset observations, hashes, full tested commit,
operation ID, request hash, command, environment and exit code. C reviews that
record on notification; A retains the final acceptance decision. Any optical,
throughput, latency, timing-closure or whole-BRAM coverage claim is out of scope.

## Current stages

| Stage | Status |
| --- | --- |
| independent plan / reference generation | complete; 128 values independently verified, 384 scheduled comparisons |
| B same-head source and fault review | pending B PR/head |
| RTL simulation / synthesis / implementation | not_run (preinstalled overlay) |
| C physical board execution | not_run (no board access) |
| A physical measurements | pending immutable evidence for selected B head |

The task's exclusive `docs/board-collaboration/BOARD-20261013-A/C/**` ownership
also contains its handoff input and immutable manifest, rather than the skill's
default `handoffs/c/` location. The installed C skill's `handoff.py` will validate
the same schema and hashes. New evidence uses a new operation directory without
changing files referenced by an already published manifest.

Reproduce C's local check from the repository root with
`python -B docs/board-collaboration/BOARD-20261013-A/C/verify_reference.py`.
The observed Python version and result are in `reference-verification.txt`.
`preflight.txt` records static tool discovery only; discovered ModelSim was not
launched and Vivado was not found by that probe. No vendor-tool version or result
is inferred from a path. `vector-generation.txt` is the child execution record;
C main independently checked the resulting bytes and all 128 pattern values.

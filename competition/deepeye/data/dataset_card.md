# Initial source and separation contract

This is C01 preparation for DEEPEYE-IMPLEMENTATION-20261014/version1. The design is
commit `1011259415a0916054eb580687612580bc1e5f09`. Human contract
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA-256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` applies in full.

## Public lithology source

[Zenodo record 4351156](https://zenodo.org/records/4351156), version v1, is the
selected immutable source record. Cite Bormann, Aursand, Dilib, Manral and
Dischington (2020), DOI `10.5281/zenodo.4351156`, and the
[authors' repository](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition).
The repository readback is pinned to `c8d01ee92c1c8e1ecba36f96cca6ea7b689338a1`.
The record describes logs from 118 Norwegian Sea wells and interpreted lithology.

The record API declares `cc-by-4.0` for the deposited resource. Its description
separately states that the original government well logs are under “NOLD 2.0”
(that spelling is retained from the source). Preserve both provenance statements
and attribution; do not silently label all upstream code or derivatives with
the deposit's license. Raw archives are kept outside tracked product files;
`source_inventory.json` records byte checks and acquisition state.

This source supports a public lithology benchmark. It supplies no validation of
coal-mine water detection, the project's synthetic sensor accuracy, or physical
FPGA/AMD performance. Do not use its final/blind labels to tune a held-out score.

## Required separation

Keep public `geo_replay`, real `sensor_live`, synthetic `twin_fixture`, and
`software_fixture` preparation separate in manifests and metrics. FORCE divides
by complete well; real sensor data divides by acquisition batch/run; sim_em_v2
divides by complete scenario. All windows, compressions and augmentations inherit
their root group's split. Preprocessing and calibration fit training groups only.

Training labels and offline scoring may use their documented ground truth.
The online sim_em_v2 controller never receives hidden scene geometry, identities,
seed, editor history, screen captures, truth collision queries, future signals,
or high-rate diagnostic samples. Its four-channel summary/age/mask inputs must
be reconstructed from the legal board interface. Source timestamps absent from
that interface remain unknown unless the public frozen profile defines a valid
derivation; they are not filled from authority logs.

## Current gate state

The complete archive inventory has been independently read back: 118 wells,
2,337,639 rows, with member hashes, well identities, curve names, label counts and
four-input null counts matching. The parser's 23 software tests pass. Raw files
stay in the private local archive; `force_wells.json` contains aggregate metadata.

`label_schema.json` pins the official 12-class mapping. `split_policy.json` fixes
the outcome-independent parent-well hash split, and `splits.json` records its
concrete assignments. Sidetrack variants of one parent remain together. These
are this project's splits, not a reproduction of the original FORCE leaderboard.

C01 remains `not_run`: train-only preprocessing, causal replay windows, the
complete verify_data entrypoint and R03 integration are not accepted.
No trained model, ROCm/NPU result, runtime secrecy proof, physical observation or
product card is claimed by this document or by the initial software unit tests.

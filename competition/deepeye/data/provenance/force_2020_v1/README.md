# Historical FORCE generator source snapshots

These files preserve the historical source identity of the six frozen FORCE
documents. They are known to predate the critical LAS-header boundary repairs.
They are evidence only: **never import, execute, or use them for new fitting or
inventory**. Current supported helpers remain `data/force_inventory.py` and
`data/force_preprocess.py` and have separate current-code pins.

The snapshots were copied as exact Git bytes from published C checkpoint
`31267d6c4ae284b8788ebb457f49c4ae5a49c60c`. That is the retrieval anchor,
not a claim that the original fit ran at this later commit.

|Original logical path|Git blob SHA-1|SHA256|
|---|---|---|
|`competition/deepeye/data/force_inventory.py`|`e37e07250d14fc9031b18a81a3eaa4c752e4a769`|`5bba8316ea36484df058dacb2289073ffb09ce19e401dfb297598b3e3cd10f47`|
|`competition/deepeye/data/force_preprocess.py`|`f3e7036e41d44362f65ed0b887ea62070a639f2d`|`75b2015c0ec9deab9a94a2032b77117124085631f2bd758a54c7ea7fdfdf2848`|

`preprocessing.json` retains its historical inventory/grouping helper references,
generation time and statistics. It has no embedded fitter helper hash. The
fitter snapshot separately preserves the old independently pinned generation
code. The verifier hashes both snapshots as bytes and does not execute them.
Original historical handoffs and manifests retain their original identities.

No refit, relabeling, held-out evaluation, new raw-data measurement, C01 or
product acceptance follows from preserving these files. H01-H15 contract
DEEPEYE-HUMAN-LOCK-20261014/revision1 remains unchanged, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.

# Root review repair 1

Work ID: `C-motion-request-adapter-review-repair1-20261015-v1`, same task/version,
scope and ownership. The root review rejected the first stable source because
`HostContext` was validated only during construction. An external
`object.__setattr__(context, 'source_id', True)` could exploit Python's
`True == 1` equality and cause a later request to serialize boolean context.
Calling an instance's `__post_init__` could also be shadowed by a forged method.
The prior 26 tests did not cover that mutation; passing them was insufficient.

The exact pre-repair adapter is preserved as `pre_repair/motion_request.py`,
SHA256 `db910520bb55cc0c86d7bd8c027c7ca9f0e363bbf0570ffb2e6ecac2b340b072`.
The pre-repair tests are `pre_repair/test_motion_request.py`, SHA256
`1e531025171c6863c50e7b2b2961aafcd42f80f4a43ec974dc2a444cef9c87db`.
Their then-current runner and README are also preserved. Original `run_001/`
and `run_002/` raw outputs and manifests remain unchanged.

The repair revalidates contexts and observations by their class methods at
public boundaries, refuses changes to the negotiated context, checks retained
sample immutability, and blocks an original deadline outside signed63 range.
New targeted regression tests and a new raw evidence run cover the change.
This is a software validation repair, not a scope amendment or runtime proof.

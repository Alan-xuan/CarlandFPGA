# Independent main review

This accepts a bounded software adapter checkpoint only. The independent checker was prepared from the A exact contract and public adapter API without importing the candidate implementation. It was run only after the worker completed and released ownership, against source SHA256 `29bf83a68929a882671bbed1a14b5a717e2e0bfa53cdb812512400a0aa621e7f`. Its 17 tests, 96 randomized deadline vectors and all 65,536 sequence allocations passed. Source bytes stayed unchanged. Worker run003 separately records 107 positive tests, exact commands, tool versions, stdout/stderr hashes and exit codes. The main rehashed every run003 source and log entry. Three targeted repair negative controls fail against the preserved rejected source, with expected exit1.

The original checker and A reference bytes are preserved without editing. Reproduce from a repository checkout with Python and jsonschema installed:

```powershell
python -B -X utf8 competition/deepeye/evidence/ai/motion_request/main_review/independent_adapter_verifier.py --product-root competition/deepeye --stable-sha256 29bf83a68929a882671bbed1a14b5a717e2e0bfa53cdb812512400a0aa621e7f
```

Always supply `--product-root`; the checker's historical default identifies the original private review layout. Running it writes new result/log evidence beside the checker, so preserve the recorded originals first. These checker/reference files are evidence, not runtime authority modules.

Fake verifier fixtures supply no physical, clock, ACL, source or model-liveness proof. The production helper defaults to blocked/no motion bytes without a trusted verifier. It emits only the A request whitelist, never motion_grant, and every decision keeps movement_authorized=False. A alone owns execution/world authority and the physical board. The caller must honor must_stop and retain original immutable bytes/timing for transport retry; resubmission of a candidate is rejected. Missing B TRACE and measured/runtime dependencies remain blocked. R03, C05/G06, complete HIL/PC_DIRECT and all product/hardware acceptance remain incomplete.

Frozen design1011259415a0916054eb580687612580bc1e5f09; H01-H15 DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 unchanged.

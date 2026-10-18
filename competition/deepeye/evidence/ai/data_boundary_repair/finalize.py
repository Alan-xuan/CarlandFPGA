"""Verify immutable evidence and write this worker's bounded release."""

import datetime
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    destination = HERE / name
    if destination.exists():
        raise RuntimeError("refusing to overwrite final evidence: " + name)
    destination.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


baseline = json.loads((HERE / "original_sha256.json").read_text(encoding="utf-8"))
for relative, record in baseline["original_sources"].items():
    assert sha(HERE / "original" / relative) == record["sha256"], relative
unchanged = {}
for relative, record in baseline["untouched_artifacts"].items():
    assert sha(PRODUCT / relative) == record["sha256"], relative
    unchanged[relative] = dict(record)

sources = {
    relative: {"sha256": sha(PRODUCT / relative), "bytes": (PRODUCT / relative).stat().st_size}
    for relative in baseline["original_sources"]
}
patch = []
for relative in sources:
    original = (HERE / "original" / relative).read_text(encoding="utf-8").splitlines(True)
    current = (PRODUCT / relative).read_text(encoding="utf-8").splitlines(True)
    patch.extend(difflib.unified_diff(original, current,
                                    fromfile="original/competition/deepeye/" + relative,
                                    tofile="candidate/competition/deepeye/" + relative))
(HERE / "reviewable.diff.txt").write_text("".join(patch), encoding="utf-8", newline="\n")

results = {
    path.name.removesuffix(".result.json"): json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(HERE.glob("*.result.json"))
}
for label, result in results.items():
    assert sha(HERE / (label + ".stdout.txt")) == result["stdout_sha256"], label
    assert sha(HERE / (label + ".stderr.txt")) == result["stderr_sha256"], label
    assert not result["archive_override_set"], label
assert results["red_inventory"]["exit_code"] == results["red_preprocess"]["exit_code"] == 1
assert results["red_portable"]["exit_code"] == 1
for label in ("green_inventory", "green_preprocess", "green_portable", "verifier_unaffected", "verifier_historical", "scope", "preflight"):
    assert results[label]["exit_code"] == 0, label
assert results["candidate_verify_suite"]["exit_code"] == results["candidate_verify_cli"]["exit_code"] == 1
for label in ("green_inventory", "green_preprocess", "green_portable", "verifier_unaffected", "verifier_historical", "candidate_verify_suite", "candidate_verify_cli"):
    assert results[label]["sources"] == {key: item["sha256"] for key, item in sources.items()}, label

identity = {
    "task_id": "DEEPEYE-IMPLEMENTATION-20261014", "task_version": 1,
    "work_id": "C-las-header-and-portable-fixture-fix-20261018-v1",
    "actual_agent_id": "/root/data_boundary_repair",
    "base_commit": baseline["base_commit"],
    "contract": "DEEPEYE-HUMAN-LOCK-20261014/revision1",
    "contract_source_commit": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
    "requirements_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
    "frozen_design_commit": "1011259415a0916054eb580687612580bc1e5f09",
}
write("handoff.json", {
    **identity, "final_sources": sources, "unchanged_canonical_artifacts": unchanged,
    "result_exit_codes": {label: result["exit_code"] for label, result in results.items()},
    "production_verifier_status": "expected refusal: both repaired source hashes differ from unchanged historical pins",
    "remaining_main_work": "Review separate provenance migration; bind new live helper and original generator snapshot identities without rewriting historical data",
    "hardware_and_product_acceptance": "not_run",
})
write("release.json", {
    **identity, "released_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "worker_state": "completed; no further writes or execution; ownership released to parent /root",
    "released_paths": ["competition/deepeye/" + relative for relative in sources] +
                      ["competition/deepeye/evidence/ai/data_boundary_repair/**"],
    "source_sha256": {relative: item["sha256"] for relative, item in sources.items()},
})
write("manifest.json", {
    **identity,
    "artifacts": {
        path.relative_to(HERE).as_posix(): {"sha256": sha(path), "bytes": path.stat().st_size}
        for path in sorted(HERE.rglob("*")) if path.is_file()
    },
})
print(json.dumps({"status": "released", "final_sources": sources,
                  "manifest_sha256": sha(HERE / "manifest.json")}, indent=2))

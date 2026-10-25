"""Author-only bounded new fixture examples and immutable dependency readback."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

WT = Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c\.local\deepeye-implementation-c")
PRODUCT = WT / "competition/deepeye"
sys.path.insert(0, str(PRODUCT))
from ai_pc.planning.trajectory_candidates import Candidate, Command, Pose3, generate_candidates, rollout_candidate
from ai_pc.planning.swept_capsule import Box, FixtureMap, Region, check_candidate

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

dependencies = {
    "competition/deepeye/ai_pc/planning/kinematics.py": "770f8b4e1ff1e626df385bf220f79a8f4be8a9e9cd05c8070cd0d0dc8c01561a",
    "docs/competition/deepeye-2026/taskbook_final.md": "7f5c94f7fc73698236be954ae7818266d6dfe8b4949d1752dd045d76f4b71f18",
}
actual = {name: sha(WT / name) for name in dependencies}
assert dependencies == actual
requirements = json.loads((WT / "docs/competition/deepeye-2026/immutable_scope.json").read_bytes())["requirements"]
requirements_sha = hashlib.sha256(json.dumps(requirements, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
assert requirements_sha == "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=WT, capture_output=True, check=True).stdout.decode().strip()
assert head == "5b237220c6ca87bdea0fbba79f8f1b379d5d4304"
pose = Pose3((0, 0, 0), (0, 0, 0, 1))
fan = generate_candidates(profile="fast_9600", speed_codes=[20], yaw_codes=[-4000, 0, 4000], pitch_codes=[-3000, 0, 3000], duration_ticks=100)
combined = next(c for c in fan.candidates if c.commands[0].yaw_q == 4000 and c.commands[0].pitch_q == 3000)
trajectory = rollout_candidate(pose, .25, combined)
cube = Box((-2, -2, -2), (2, 2, 2))
free = Region("free", "free", cube)
maps = {
    "explicit_full_free": FixtureMap(cube, (free,)),
    "default_unknown": FixtureMap(cube),
    "tail_occupied": FixtureMap(cube, (free, Region("tail", "occupied", Box((-.01, -.01, -.51), (.01, .01, -.49))))),
}
outcomes = {}
for name, fixture in maps.items():
    result = check_candidate(pose, .25, combined, fixture)
    outcomes[name] = {"status": result.status, "fixture_digest": result.fixture_digest,
                      "input_digest": result.input_digest, "substeps_used": result.substeps_used,
                      "geometry_checks_used": result.geometry_checks_used,
                      "blocking_interval": result.blocking_interval,
                      "blocking_region": result.blocking_region,
                      "first_support": asdict(result.supports[0]) if result.supports else None,
                      "last_support": asdict(result.supports[-1]) if result.supports else None,
                      "movement_authorized": result.movement_authorized}
assert outcomes["explicit_full_free"]["status"] == "clear_for_supplied_fixture"
assert outcomes["default_unknown"]["status"] == "unknown_missing_coverage"
assert outcomes["tail_occupied"]["status"] == "conservative_occupied_overlap"
result = {"task_id": "DEEPEYE-IMPLEMENTATION-20261014", "task_version": 1,
          "work_id": "C-3D-TRAJECTORY-KERNEL-20261025-v1", "source_domain": "software_fixture",
          "python": platform.python_version(), "base_commit": head, "dependency_sha256": actual,
          "requirements_sha256": requirements_sha,
          "candidate_generation": {"status": fan.status, "count": len(fan.candidates), "input_digest": fan.input_digest},
          "combined_yaw_pitch": {"codes": combined.commands[0].canonical(), "status": trajectory.status,
                                 "input_digest": trajectory.input_digest, "substeps": trajectory.substeps_used,
                                 "first_sample": asdict(trajectory.samples[0]), "last_sample": asdict(trajectory.samples[-1])},
          "fixture_outcomes": outcomes, "movement_authorized": False,
          "formal_acceptance": "incomplete", "actual_capsule_collision_proof": False}
print(json.dumps(result, sort_keys=True, allow_nan=False, indent=2))

"""The two client skill ZIPs must never expose A's board upload workflow."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fpga_mesh.distribution import build_client_archive


ROOT = Path(__file__).resolve().parents[1]
SKILL = "skills/pynq-z2-single-node/"


class ClientDistributionTests(unittest.TestCase):
    def test_b_and_c_packages_are_separate_and_board_upload_free(self):
        host_skill = ROOT / SKILL / "SKILL.md"
        before = hashlib.sha256(host_skill.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            outputs = {}
            for node in ("B", "C"):
                output = Path(temp) / f"client-{node}.zip"
                build_client_archive(ROOT, node, output, revision="test-revision")
                with zipfile.ZipFile(output) as archive:
                    self.assertIsNone(archive.testzip())
                    names = set(archive.namelist())
                    self.assertTrue(all(name == "MANIFEST.json" or name.startswith(SKILL)
                                        for name in names))
                    self.assertIn(SKILL + "SKILL.md", names)
                    self.assertIn(SKILL + "Install.ps1", names)
                    self.assertIn(SKILL + "scripts/handoff.py", names)
                    self.assertIn(SKILL + "scripts/preflight.py", names)
                    self.assertEqual(
                        {name for name in names if name.startswith(SKILL + "scripts/")},
                        {SKILL + "scripts/handoff.py", SKILL + "scripts/preflight.py"},
                    )
                    self.assertNotIn(SKILL + "requirements-board.txt", names)
                    role = json.loads(archive.read(SKILL + "client-role.json"))
                    self.assertEqual(role, {"node": node, "board_access": False,
                                            "handoff": "github_pull_request"})
                    skill = archive.read(SKILL + "SKILL.md").decode("utf-8")
                    self.assertIn(f"节点 {node}", skill)
                    self.assertNotIn("@NODE@", skill)
                    handoff = archive.read(SKILL + "references/handoff.md").decode("utf-8")
                    self.assertIn(f"codex/{node.lower()}/<task-id>", handoff)
                    self.assertIn(f"node-{node.lower()}", handoff)
                    self.assertNotIn("@NODE_LOWER@", handoff)
                    manifest = json.loads(archive.read("MANIFEST.json"))
                    self.assertEqual(manifest["profile"], f"pynq-client-{node.lower()}")
                    self.assertEqual(manifest["revision"], "test-revision")
                    self.assertEqual({item["path"] for item in manifest["files"]}, names - {"MANIFEST.json"})
                    outputs[node] = hashlib.sha256(output.read_bytes()).hexdigest()
            self.assertNotEqual(outputs["B"], outputs["C"])
        self.assertEqual(hashlib.sha256(host_skill.read_bytes()).hexdigest(), before)

    def test_client_builder_rejects_host_role(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "B or C"):
                build_client_archive(ROOT, "A", Path(temp) / "invalid.zip")


if __name__ == "__main__":
    unittest.main()

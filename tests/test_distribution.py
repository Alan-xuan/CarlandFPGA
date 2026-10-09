import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fpga_mesh.distribution import build_archive, select_package_paths


class DistributionTests(unittest.TestCase):
    def test_mesh_and_single_node_skill_are_separate_packages(self):
        tracked = [
            "README.md", "deploy/Join-FPGAMesh.ps1",
            "docs/deployment/OPERATIONS.md",
            "docs/deployment/SINGLE_NODE_PYNQ_Z2.md",
            "docs/deployment/HOST_TOOLCHAIN_2026-10-08.md",
            "docs/deployment/evidence/pynq-z2-live-2026-10-09/result.json",
            "skills/pynq-z2-single-node/SKILL.md",
            "skills/pynq-z2-single-node/scripts/preflight.py",
            "packaging/pynq-client/SKILL.md",
            "tests/test_pynq_z2_board_run.py",
            "tests/test_pynq_client_distribution.py",
        ]
        self.assertEqual(select_package_paths(tracked, "mesh"), [
            "README.md", "deploy/Join-FPGAMesh.ps1",
            "docs/deployment/OPERATIONS.md",
        ])
        self.assertEqual(select_package_paths(tracked, "pynq-skill"), [
            "skills/pynq-z2-single-node/SKILL.md",
            "skills/pynq-z2-single-node/scripts/preflight.py",
        ])

    def test_unknown_package_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "profile"):
            select_package_paths(["README.md"], "everything")

    def test_archive_contains_only_selected_source_and_verifiable_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "deploy").mkdir()
            (root / "deploy" / "Join.ps1").write_text("Write-Host ready", encoding="utf-8")
            (root / ".local").mkdir()
            (root / ".local" / "secret.txt").write_text("private", encoding="utf-8")
            target = root / "team.zip"
            build_archive(root, ["deploy/Join.ps1"], target, revision="test-rev")
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(sorted(archive.namelist()),
                                 ["MANIFEST.json", "deploy/Join.ps1"])
                manifest = json.loads(archive.read("MANIFEST.json"))
                entry = manifest["files"][0]
                self.assertEqual(entry["sha256"], hashlib.sha256(
                    archive.read("deploy/Join.ps1")
                ).hexdigest())
                self.assertEqual(manifest["revision"], "test-rev")

    def test_secret_path_or_key_material_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".local").mkdir()
            (root / ".local" / "secret.txt").write_text("private", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_archive(root, [".local/secret.txt"], root / "bad.zip")
            (root / "key.txt").write_text("sk-" + "a" * 40, encoding="utf-8")
            with self.assertRaises(ValueError):
                build_archive(root, ["key.txt"], root / "bad.zip")
            (root / "ssh-private.txt").write_text(
                "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nprivate material\n"
                "-----END " + "OPENSSH PRIVATE KEY-----\n", encoding="ascii"
            )
            with self.assertRaisesRegex(ValueError, "key|private"):
                build_archive(root, ["ssh-private.txt"], root / "bad.zip")
            (root / "id_ed25519").write_text("opaque private bytes", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "private"):
                build_archive(root, ["id_ed25519"], root / "bad.zip")

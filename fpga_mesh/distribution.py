"""Build a credential-free teammate ZIP from the committed Git file list."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


_KEY_PATTERN = re.compile(
    rb"sk-[A-Za-z0-9_-]{24,}|-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----|"
    rb"-----BEGIN PGP PRIVATE KEY BLOCK-----"
)
_PRIVATE_FILENAMES = {"auth.json", "deepcodex.txt", "id_ed25519", "id_rsa", "id_ecdsa", "id_dsa"}
_PRIVATE_SUFFIXES = ("-secret.txt", ".p12", ".pfx", ".pem", ".key", ".lic")


def select_package_paths(paths: list[str], profile: str) -> list[str]:
    """Keep the machine mesh and the standalone board skill in separate ZIPs."""
    if profile == "pynq-skill":
        return [path for path in paths if path.startswith("skills/pynq-z2-single-node/")]
    if profile == "mesh":
        return [path for path in paths if not (
            path.startswith("skills/pynq-z2-single-node/")
            or path.startswith("docs/deployment/SINGLE_NODE_")
            or path.startswith("docs/deployment/HOST_TOOLCHAIN_")
            or path.startswith("docs/deployment/evidence/pynq-z2-")
            or path.startswith("tests/test_pynq_z2_")
        )]
    raise ValueError(f"unknown package profile: {profile}")


def build_archive(
    root: Path, paths: list[str], output: Path, *, revision: str = "uncommitted",
    profile: str = "mesh",
) -> Path:
    root = Path(root).resolve()
    output = Path(output).resolve()
    files = []
    payloads: dict[str, bytes] = {}
    for raw in sorted(set(paths)):
        relative = Path(raw)
        resolved = (root / relative).resolve()
        if (relative.is_absolute() or ".." in relative.parts
                or not resolved.is_relative_to(root)):
            raise ValueError(f"unsafe package path: {raw}")
        normalized = relative.as_posix()
        lowered = [part.casefold() for part in relative.parts]
        if ({".git", ".local", "__pycache__"} & set(lowered)
                or relative.name.casefold() in _PRIVATE_FILENAMES
                or relative.name.casefold().endswith(_PRIVATE_SUFFIXES)):
            raise ValueError(f"private path cannot enter package: {raw}")
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        content = resolved.read_bytes()
        if _KEY_PATTERN.search(content):
            raise ValueError(f"key-like material found in: {raw}")
        payloads[normalized] = content
        files.append({
            "path": normalized, "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    manifest = {
        "project": "CarlandFPGA",
        "profile": profile,
        "revision": revision,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in payloads.items():
            archive.writestr(name, content)
        archive.writestr(
            "MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        for entry in files:
            if hashlib.sha256(archive.read(entry["path"])).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"ZIP hash verification failed: {entry['path']}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("mesh", "pynq-skill"), default="mesh")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root,
        capture_output=True, text=True, check=True,
    ).stdout
    if dirty.strip():
        raise SystemExit("Commit all source changes before building the package")
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root,
        capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="strict")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    paths = select_package_paths(
        [name for name in listed.split("\0") if name], args.profile,
    )
    path = build_archive(root, paths, args.output, revision=revision,
                         profile=args.profile)
    print(json.dumps({
        "archive": str(path), "profile": args.profile,
        "revision": revision, "files": len(paths),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

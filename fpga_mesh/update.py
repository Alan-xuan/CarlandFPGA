"""Standard-library in-place updater; can run directly from an unpacked ZIP.

Existing credentials, node configuration, Git history and tasks are not inputs
to this updater. Only validated manifest paths can be changed. Unknown local
edits block the whole update before any source is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tomllib
import uuid
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath

_PRIVATE_NAMES = {'auth.json', 'deepcodex.txt', 'id_rsa', 'id_ed25519',
                  'id_ecdsa', 'id_dsa'}
_PRIVATE_SUFFIXES = ('-secret.txt', '.p12', '.pfx', '.pem', '.key', '.lic')
_RESERVED = {'con', 'prn', 'aux', 'nul'} | {
    f'{prefix}{number}' for prefix in ('com', 'lpt') for number in range(1, 10)
}


def canonical_hash(payload: bytes) -> str:
    """Tolerate Git text CRLF/LF conversion; binary bytes remain exact."""
    if b'\0' not in payload:
        try:
            payload.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            payload = payload.replace(b'\r\n', b'\n')
    return hashlib.sha256(payload).hexdigest()


def _relative(name: str) -> Path:
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('unsafe update path')
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name:
        raise ValueError('unsafe update path')
    for part in path.parts:
        lowered = part.casefold()
        if (lowered in {'.', '..', '.git', '.local', '.codex', '__pycache__'}
                or lowered in _PRIVATE_NAMES
                or lowered.endswith(_PRIVATE_SUFFIXES)
                or part.endswith((' ', '.'))
                or lowered.split('.')[0] in _RESERVED):
            raise ValueError('private or unsafe update path')
    return Path(*path.parts)


def read_package(package: Path, *, require_update: bool = True) -> tuple[dict, dict[str, bytes]]:
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError('invalid ZIP entries or CRC')
        manifest = json.loads(archive.read('MANIFEST.json'))
        if manifest.get('project') != 'CarlandFPGA':
            raise ValueError('not a CarlandFPGA package')
        if require_update and (manifest.get('profile') != 'mesh'
                               or manifest.get('update', {}).get('schema') != 1):
            raise ValueError('package has no supported in-place update manifest')
        payloads = {}
        seen = set()
        for entry in manifest['files']:
            name = entry['path']
            _relative(name)
            if name.casefold() in seen:
                raise ValueError('duplicate update path')
            seen.add(name.casefold())
            payload = archive.read(name)
            if len(payload) != entry['size']:
                raise ValueError(f'package size mismatch: {name}')
            if hashlib.sha256(payload).hexdigest() != entry['sha256']:
                raise ValueError(f'package hash mismatch: {name}')
            payloads[name] = payload
        if set(names) != set(payloads) | {'MANIFEST.json'}:
            raise ValueError('unlisted ZIP entries')
        return manifest, payloads


def _destination(root: Path, name: str) -> Path:
    path = root / _relative(name)
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError('update destination escapes workspace')
    return path


def _hash(path: Path) -> str | None:
    if path.exists() and not path.is_file():
        raise ValueError('update destination is not a file')
    return canonical_hash(path.read_bytes()) if path.exists() else None


def _plan(manifest: dict, payloads: dict[str, bytes], root: Path) -> tuple[dict, dict]:
    rules = manifest['update']
    before = rules['before']
    removed = rules.get('removed', {})
    if set(before) != set(payloads) or set(removed) & set(payloads):
        raise ValueError('invalid update ownership manifest')
    changed, deleted, conflicts, observed = [], [], [], {}
    for name in sorted(set(payloads) | set(removed)):
        path = _destination(root, name)
        current = _hash(path)
        observed[name] = current
        target = canonical_hash(payloads[name]) if name in payloads else None
        if current == target:
            continue
        accepted = before[name] if name in payloads else removed[name]
        if not isinstance(accepted, list) or not all(
            value is None or (isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value))
            for value in accepted
        ):
            raise ValueError('invalid previous version hash')
        if current not in accepted:
            conflicts.append(name)
        elif name in payloads:
            changed.append(name)
        else:
            deleted.append(name)
    report = {
        'revision': manifest['revision'], 'changed': changed, 'deleted': deleted,
        'conflicts': conflicts, 'retained': len(payloads) - len(changed),
        'backup': None,
    }
    return report, observed


def plan_update(package: Path, workspace: Path) -> dict:
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise ValueError('existing workspace directory required')
    manifest, payloads = read_package(package)
    return _plan(manifest, payloads, root)[0]


def _state_directory(config: Path, node: str) -> Path:
    config = Path(config).resolve()
    data = tomllib.loads(config.read_text(encoding='utf-8-sig'))
    if data.get('node_id') != node or node not in {'A', 'B', 'C'}:
        raise ValueError('config belongs to a different node')
    state = Path(data.get('state_dir', f'.local/node-{node.lower()}'))
    if not state.is_absolute():
        state = config.parent / state
    return state.resolve()


def assert_idle(config: Path, *, node: str) -> str:
    """Read persisted activity without opening a controller or replaying work."""
    state = _state_directory(config, node)
    checks = (
        ('main_sessions.sqlite', 'main_runs', "status IN ('queued', 'running')"),
        ('child_jobs.sqlite', 'child_jobs', "status IN ('reserved', 'queued', 'running')"),
        ('state.sqlite', 'inbound', 'processed_at IS NULL'),
    )
    for filename, table, condition in checks:
        path = state / filename
        if not path.exists():
            continue
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                (table,)).fetchone()
            if exists and db.execute(f'SELECT COUNT(*) FROM {table} WHERE {condition}').fetchone()[0]:
                raise ValueError('node has active or pending work; finish or explicitly resolve it before updating')
    return node


def _replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.mesh-{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_update(package: Path, workspace: Path) -> dict:
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise ValueError('existing workspace directory required')
    manifest, payloads = read_package(package)
    report, observed = _plan(manifest, payloads, root)
    if report['conflicts']:
        raise ValueError('local file conflict: ' + ', '.join(report['conflicts']))
    operations = report['changed'] + report['deleted']
    if not operations:
        return report
    parent = root / '.local' / 'update-backups'
    if not parent.resolve().is_relative_to(root):
        raise ValueError('backup directory escapes workspace')
    parent.mkdir(parents=True, exist_ok=True)
    lock = parent / 'update.lock'
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    backup = parent / uuid.uuid4().hex
    originals: dict[str, bytes | None] = {}
    written = []
    try:
        backup.mkdir()
        for name in operations:
            path = _destination(root, name)
            if _hash(path) != observed[name]:
                raise ValueError(f'local file conflict during update: {name}')
            originals[name] = path.read_bytes() if path.exists() else None
            if originals[name] is not None:
                saved = backup / _relative(name)
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(originals[name])
        journal = {'revision': manifest['revision'], 'status': 'prepared',
                   'files': {name: {'before': observed[name],
                                   'after': canonical_hash(payloads[name]) if name in payloads else None}
                             for name in operations}}
        record = backup / 'UPDATE_RECEIPT.json'
        record.write_text(json.dumps(journal, indent=2) + '\n', encoding='utf-8')
        for name in operations:
            path = _destination(root, name)
            if _hash(path) != observed[name]:
                raise ValueError(f'local file conflict during update: {name}')
            if name in payloads:
                _replace(path, payloads[name])
            else:
                path.unlink()
            written.append(name)
        journal['status'] = 'applied'
        record.write_text(json.dumps(journal, indent=2) + '\n', encoding='utf-8')
        report['backup'] = str(backup)
        return report
    except BaseException:
        # Roll back only our own completed writes; later edits remain protected.
        for name in reversed(written):
            path = _destination(root, name)
            expected = canonical_hash(payloads[name]) if name in payloads else None
            if _hash(path) == expected:
                if originals[name] is None:
                    path.unlink(missing_ok=True)
                else:
                    _replace(path, originals[name])
        raise
    finally:
        lock.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='Update an existing FPGA Mesh workspace in place')
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--node', choices=('A', 'B', 'C'))
    args = parser.parse_args()
    try:
        if args.config or args.node:
            if not args.config or not args.node:
                raise ValueError('--config and --node must be supplied together')
            assert_idle(args.config, node=args.node)
        report = (apply_update if args.apply else plan_update)(args.package, args.workspace)
        if args.config:
            report['control_file'] = str(_state_directory(args.config, args.node) / 'main-control.json')
    except (ValueError, OSError, KeyError, sqlite3.Error, zipfile.BadZipFile) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True))
        raise SystemExit(1) from None
    print(json.dumps(report, ensure_ascii=True))
    if report['conflicts']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()

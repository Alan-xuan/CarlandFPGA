"""Explicit offline materialization of exact inventoried files; not an actor launcher.

Destination must be new. No cleanup, overwrite, service, network or native actor.
The original A owner must separately approve/retain and stage this source tree.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat


def _checked_lexical(path, *, missing_final=False):
    # Do not resolve away the supplied alias. Check from the volume/root toward
    # the leaf so an aliased parent is rejected before traversing into it.
    path = path.absolute()
    if '..' in path.parts:
        raise ValueError('lexical parent traversal forbidden')
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if missing_final and component == path:
                return path
            raise ValueError('existing lexical source/parent required') from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('source/destination aliases forbidden')
    return path


def materialize(runtime_root, package_root, inventory, destination):
    runtime_root, package_root = _checked_lexical(runtime_root), _checked_lexical(package_root)
    destination = _checked_lexical(destination, missing_final=True)
    if not runtime_root.is_dir() or not package_root.is_dir():
        raise ValueError('existing lexical source directories required')
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError('new destination under existing explicit parent required')
    plan = []
    for row in inventory['files'] + inventory['package_files']:
        relative = PurePosixPath(row['path'])
        if relative.is_absolute() or '..' in relative.parts or '\\' in row['path'] or ':' in row['path']:
            raise ValueError('unsafe stage relative path')
        source = (runtime_root / Path(*relative.parts[1:]) if relative.parts[0] == 'runtime'
                  else package_root / Path(*relative.parts))
        _checked_lexical(source)
        raw = source.read_bytes()
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('original inventoried bytes unavailable or changed')
        plan.append((relative, raw, row['sha256']))
    if len({str(p).casefold() for p, _, _ in plan}) != len(plan) or sum(len(b) for _, b, _ in plan) > 268435456:
        raise ValueError('stage count/case/budget mismatch')
    _checked_lexical(destination, missing_final=True)
    destination.mkdir()
    for relative, raw, _ in plan:
        path = destination / Path(*relative.parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise ValueError('short stage write')
    return {'files': [[str(path), sha] for path, _, sha in plan], 'executable':'runtime/python.exe',
            'arguments_template':['-I','-B','c37_entry.py','--actor-stdio-v1','--max-invocations','1','--request-bytes','N'],
            'stage_bytes':sum(len(b) for _, b, _ in plan),'original_actor_launched':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--package-root', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    result = materialize(args.runtime_root, args.package_root,
                         json.loads(args.inventory.read_text(encoding='utf-8')), args.destination)
    print(json.dumps(result, separators=(',', ':')))

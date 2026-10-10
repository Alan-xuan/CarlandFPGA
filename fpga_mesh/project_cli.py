"""Stable project-chat entry point using authenticated local discovery."""
import argparse
import asyncio
import json
from pathlib import Path
from .child_control import LocalControlFileClient

def discovery(root: Path) -> Path:
    matches = list((root / '.local/deployment').glob('node-*/.local/node-*/main-control.json'))
    if len(matches) != 1:
        raise RuntimeError('Specify --control-file when no unique resident local node exists')
    return matches[0]

async def run(args):
    client = LocalControlFileClient(args.control_file or discovery(Path.cwd()))
    values = json.loads(args.args_file.read_text(encoding='utf-8') if args.args_file else args.arguments or '{}')
    return await client.call(args.action, values)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control-file', type=Path)
    parser.add_argument('action')
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--arguments')
    inputs.add_argument('--args-file', type=Path)
    print(json.dumps(asyncio.run(run(parser.parse_args())), ensure_ascii=True))

if __name__ == '__main__':
    main()

"""Install a node-local project MCP bridge without global provider changes."""
import argparse
import json
import re
import tomllib
from pathlib import Path

NATIVE_POLICY = '''You are a native GPT execution subagent, subordinate to the assigning GPT main.
Before executing any project operation, obtain the parent-supplied job_id and
lease_token and call fpga_native_validate with your canonical agent_id through
the project MCP or CLI. Require execution_allowed=true before starting. If
either is absent, validation fails, or the task is stale, stop without executing.
Do not reserve a new job for yourself. Only execute the assigned work_id and
declared file ownership. Do not perform main decisions, acceptance, difficult
problem solving, critical optimization or evaluation; report evidence to the
quality main. Never publish to Feishu or change providers/credentials. Complete
the actual job through fpga_native_complete, and return its persisted result.
You are not alone in the codebase; do not revert others or edit unowned files.
'''

def install(root: Path, *, python: str, control_file: Path):
    root = Path(root).resolve()
    directory = root / '.codex'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'config.toml'
    original = path.read_text(encoding='utf-8-sig') if path.exists() else ''
    # Replace only our own MCP tables; preserve user model/provider preferences.
    kept = re.sub(r'(?ms)^\[mcp_servers\.fpga_mesh(?:\.env)?\]\s*\n.*?(?=^\[|\Z)', '', original).rstrip()
    block = '\n\n[mcp_servers.fpga_mesh]\ncommand = ' + json.dumps(str(python))
    block += '\nargs = ["-m", "fpga_mesh.project_mcp"]\nstartup_timeout_sec = 20\ntool_timeout_sec = 3600\n'
    block += '[mcp_servers.fpga_mesh.env]\nPYTHONPATH = ' + json.dumps(str(root))
    block += '\nFPGA_MAIN_CONTROL_FILE = ' + json.dumps(str(control_file)) + '\n'
    contents = kept + block
    tomllib.loads(contents)
    path.write_text(contents, encoding='utf-8')
    agents = directory / 'agents'
    agents.mkdir(exist_ok=True)
    for name in ('default', 'worker', 'explorer'):
        target = agents / f'{name}.toml'
        existing = target.read_text(encoding='utf-8-sig') if target.exists() else ''
        if existing and 'fpga_native_validate' not in existing:
            raise RuntimeError(f'Existing custom native role must be reviewed: {target}')
        target.write_text(f'name = "{name}"\ndescription = "Lease-protected native GPT execution role"\ndeveloper_instructions = ' + json.dumps(NATIVE_POLICY) + '\n', encoding='utf-8')
    return path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--control-file', type=Path, required=True)
    args = parser.parse_args()
    print(install(args.project_root, python=args.python, control_file=args.control_file))

if __name__ == '__main__':
    main()

"""Official Codex model discovery and recoverable native role installation."""
from __future__ import annotations

import asyncio
import json
import os
import re
import tomllib
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .app_server import AppServerClient
from .install_routing import NATIVE_POLICY
from .sessions import EFFORT_ORDER, now

MARKER = '# Managed by the CarlandFPGA official model manager.'
LEGACY_ROLES = {
    'codex-auto-review': 'codex-auto-review', 'gpt-5-5': 'gpt-5.5',
    'gpt-5-6-luna': 'gpt-5.6-luna', 'gpt-5-6-sol': 'gpt-5.6-sol',
    'gpt-5-6-terra': 'gpt-5.6-terra', 'gpt-6-astra': 'gpt-6-astra',
    'gpt-6-luna': 'gpt-6-luna', 'gpt-6-sol': 'gpt-6-sol',
    'gpt-daybreak-blue-latest': 'gpt-daybreak-blue-latest',
    'gpt-daybreak-red-latest': 'gpt-daybreak-red-latest',
}
BASE_POLICY = '''Stay within the delegated task and declared file ownership. Report concrete
paths, commands and persisted results to the parent. Escalate risky decisions.
You are not alone in the codebase; do not revert others or override user edits.
When working in CarlandFPGA (identified by its AGENTS.md and fpga_mesh package),
the following project policy is mandatory. Outside that project, follow the
applicable workspace rules instead of requiring the project-specific lease:
'''


def assert_official(home: Path) -> None:
    path = home / 'config.toml'
    config = tomllib.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    if config.get('model_provider', 'openai') != 'openai' or config.get('model_catalog_json'):
        raise ValueError('Official model update requires the builtin official provider and catalog')
    urls = [config.get('chatgpt_base_url'),
            config.get('model_providers', {}).get('openai', {}).get('base_url')]
    if any(url and urlsplit(url).hostname not in {'api.openai.com', 'chatgpt.com'} for url in urls):
        raise ValueError('Official provider cannot use a custom inference endpoint')


async def load_catalog(home: Path) -> list[dict]:
    # A fresh bundled app-server sees an installed client update and refreshes its
    # official catalog instead of reusing the resident client's old role snapshot.
    client = await AppServerClient.start_stdio(codex_home=home, client_version='0.8.0', role='astra')
    try:
        await asyncio.wait_for(client.initialize(), 30)
        entries, cursor, seen = [], None, set()
        while True:
            args = {'includeHidden': True}
            if cursor:
                args['cursor'] = cursor
            result = await asyncio.wait_for(client.session.request('model/list', args), 30)
            entries.extend(result.get('data', []))
            cursor = result.get('nextCursor')
            if not cursor:
                return entries
            if cursor in seen:
                raise RuntimeError('Official model pagination repeated a cursor')
            seen.add(cursor)
    finally:
        await client.close()


def valid_models(entries: list[dict]) -> dict[str, dict]:
    result = {}
    for item in entries:
        model = item.get('model') or item.get('id')
        if not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]+', model):
            continue
        efforts = [e.get('reasoningEffort') if isinstance(e, dict) else e
                   for e in item.get('supportedReasoningEfforts', [])]
        efforts = [e for e in efforts if e in EFFORT_ORDER]
        if efforts:
            result[model] = {'efforts': efforts, 'hidden': bool(item.get('hidden', False)),
                'default_effort': item.get('defaultReasoningEffort'),
                'is_default': bool(item.get('isDefault', False)), 'upgrade': item.get('upgrade')}
    return result


def replace_files(contents: dict[Path, bytes]) -> None:
    """Stage every file first; roll back already replaced files on write failure."""
    originals = {p: p.read_bytes() if p.exists() else None for p in contents}
    staged, written = {}, []
    try:
        for target, value in contents.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = target.with_name(target.name + f'.{uuid.uuid4().hex}.tmp')
            staged[target] = stage
            stage.write_bytes(value)
        for target, stage in staged.items():
            os.replace(stage, target)
            written.append(target)
    except Exception:
        for target in reversed(written):
            old = originals[target]
            if old is None:
                target.unlink(missing_ok=True)
            else:
                stage = target.with_name(target.name + '.rollback.tmp')
                stage.write_bytes(old)
                os.replace(stage, target)
        raise
    finally:
        for stage in staged.values():
            stage.unlink(missing_ok=True)


class OfficialModelManager:
    def __init__(self, home: str | Path, state_dir: str | Path, *, loader=load_catalog):
        self.home, self.state_dir = Path(home), Path(state_dir)
        self.loader = loader
        self.lock = asyncio.Lock()
        self.path = self.state_dir / 'official-models.json'

    def snapshot(self) -> dict:
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {
            'provider': 'openai', 'updated_at': None, 'models': {}, 'roles': {},
        }

    async def refresh(self, router) -> dict:
        async with self.lock:
            assert_official(self.home)
            models = valid_models(await self.loader(self.home))
            visible = {m: tuple(v['efforts']) for m, v in models.items() if not v['hidden']}
            if not visible:
                raise RuntimeError('No verified official GPT models/efforts are available')
            default = next((m for m in visible if models[m]['is_default']), next(iter(visible)))
            requested = {**LEGACY_ROLES, 'official-latest': default}
            requested.update({m.replace('.', '-'): m for m in visible})
            contents, roles = {}, {}
            for role, wanted in requested.items():
                target = self.home / 'agents' / f'{role}.toml'
                existing = target.read_text(encoding='utf-8-sig') if target.exists() else ''
                if existing and role not in LEGACY_ROLES and MARKER not in existing:
                    raise RuntimeError(f'Existing user custom role is preserved: {target}')
                actual = wanted if wanted in models else default
                available = models[actual]['efforts']
                effort = 'medium' if 'medium' in available else models[actual]['default_effort']
                if effort not in available:
                    effort = available[0]
                description = f'Official Codex execution role using {actual} ({effort}).'
                if actual != wanted:
                    description += f' Compatibility alias for {wanted}; that model is absent from the official catalog.'
                policy = BASE_POLICY + NATIVE_POLICY
                text = MARKER + '\n' + '\n'.join(
                    f'{k} = {json.dumps(v, ensure_ascii=False)}' for k, v in {
                        'name': role, 'description': description, 'model': actual,
                        'model_provider': 'openai', 'model_reasoning_effort': effort,
                        'developer_instructions': policy, 'nickname_candidates': ['Execution Worker'],
                    }.items()) + '\n'
                tomllib.loads(text)
                contents[target] = text.encode('utf-8')
                roles[role] = {'requested_model': wanted, 'model': actual, 'effort': effort,
                               'provider': 'openai', 'alias': actual != wanted}
            quality_model = router.quality_model
            upgrade = models.get(quality_model, {}).get('upgrade')
            if isinstance(upgrade, str) and upgrade in visible:
                quality_model = upgrade
            result = {'provider': 'openai', 'updated_at': now(), 'default_model': default,
                'models': models, 'roles': roles, 'quality_model': quality_model,
                'catalog_source': 'official Codex app-server model/list',
                'native_role_scope': 'newly loaded conversations', 'inference_calls': 0}
            contents[self.path] = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            # Keep a recoverable, node-local copy of the original role files only.
            # No credentials or global auth/config are copied or changed.
            backup = self.state_dir / 'role-backups' / uuid.uuid4().hex
            for target in contents:
                if target.parent == self.home / 'agents' and target.exists():
                    old = target.read_bytes()
                    if old != contents[target] and MARKER.encode() not in old:
                        backup.mkdir(parents=True, exist_ok=True)
                        (backup / target.name).write_bytes(old)
            # Wait for any earlier catalog fetch before installing this fresh
            # snapshot, so its older response cannot overwrite the update.
            async with router._catalog_lock:
                replace_files(contents)
                router._models = visible
                router.quality_model = quality_model
            return result

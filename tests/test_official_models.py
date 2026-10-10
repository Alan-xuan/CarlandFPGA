import asyncio
import json
import tempfile
import tomllib
import unittest
from contextlib import closing
from pathlib import Path

from fpga_mesh.sessions import MainSessionRouter


def catalog(extra=()):
    return [
        {'model': m, 'hidden': False, 'isDefault': m == 'gpt-6.1-sol',
         'defaultReasoningEffort': 'medium',
         'supportedReasoningEfforts': [{'reasoningEffort': v} for v in ('low', 'medium', 'max', 'ultra')]}
        for m in ('gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna', *extra)
    ] + [
        {'model': m, 'hidden': True, 'defaultReasoningEffort': 'medium',
         'supportedReasoningEfforts': [{'reasoningEffort': 'medium'}]}
        for m in ('gpt-5.5', 'codex-auto-review')
    ]


class OfficialModelsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from fpga_mesh.official_models import OfficialModelManager
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        (self.home / 'agents').mkdir(parents=True)
        self.config = 'model="gpt-6.1-sol"\n[features]\ncode_mode=true\n'
        (self.home / 'config.toml').write_text(self.config)
        (self.home / 'auth.json').write_text('{"test_auth":"untouched"}')
        self.items = catalog()
        self.calls = 0
        async def load(home):
            self.calls += 1
            return self.items
        self.manager = OfficialModelManager(self.home, self.root / 'state', loader=load)
        self.router = MainSessionRouter(self.root / 'sessions.sqlite')

    async def asyncTearDown(self):
        self.router.close()
        self.tmp.cleanup()

    async def test_ten_roles_use_official_provider_and_hidden_models_keep_exact_names(self):
        from fpga_mesh.official_models import LEGACY_ROLES
        original = 'name="gpt-6-astra"\nmodel="gpt-6-astra"\nmodel_provider="legacy_local_provider"\n'
        (self.home / 'agents/gpt-6-astra.toml').write_text(original)
        result = await self.manager.refresh(self.router)
        self.assertTrue(set(LEGACY_ROLES).issubset(result['roles']))
        for role in LEGACY_ROLES:
            settings = tomllib.loads((self.home / 'agents' / f'{role}.toml').read_text())
            self.assertEqual(settings['model_provider'], 'openai')
            self.assertNotIn('model_context_window', settings)
            self.assertIn('fpga_native_validate', settings['developer_instructions'])
            self.assertIn('When working in CarlandFPGA', settings['developer_instructions'])
        self.assertEqual(result['roles']['gpt-5-5']['model'], 'gpt-5.5')
        self.assertEqual(result['roles']['codex-auto-review']['model'], 'codex-auto-review')
        self.assertTrue(result['roles']['gpt-daybreak-blue-latest']['alias'])
        self.assertEqual((self.home / 'config.toml').read_text(), self.config)
        self.assertEqual((self.home / 'auth.json').read_text(), '{"test_auth":"untouched"}')
        self.assertTrue(any(p.read_text() == original for p in (self.root / 'state/role-backups').rglob('gpt-6-astra.toml')))

    async def test_refresh_discovers_future_models_and_default_without_a_fixed_catalog(self):
        await self.manager.refresh(self.router)
        self.items = catalog(('gpt-7-sol', 'gpt-daybreak-blue-latest'))
        for item in self.items:
            item['isDefault'] = item['model'] == 'gpt-7-sol'
        result = await self.manager.refresh(self.router)
        self.assertIn('gpt-7-sol', self.router._models)
        self.assertEqual(result['roles']['official-latest']['model'], 'gpt-7-sol')
        self.assertEqual(result['roles']['gpt-daybreak-blue-latest']['model'], 'gpt-daybreak-blue-latest')
        self.assertFalse(result['roles']['gpt-daybreak-blue-latest']['alias'])
        self.assertTrue((self.home / 'agents/gpt-7-sol.toml').is_file())
        self.assertEqual(self.calls, 2)

    async def test_new_official_model_names_need_not_use_the_gpt_prefix(self):
        self.items = catalog(('codex-next',))
        for item in self.items:
            item['isDefault'] = item['model'] == 'codex-next'
        result = await self.manager.refresh(self.router)
        self.assertIn('codex-next', self.router._models)
        self.assertEqual(result['roles']['official-latest']['model'], 'codex-next')
        self.assertEqual(result['roles']['codex-next']['model'], 'codex-next')

    async def test_refresh_wins_over_an_older_catalog_request_already_in_flight(self):
        from types import SimpleNamespace
        entered, release = asyncio.Event(), asyncio.Event()
        async def old_request(method, args):
            entered.set()
            await release.wait()
            return {'data': catalog()}
        prior = asyncio.create_task(self.router.catalog(
            SimpleNamespace(session=SimpleNamespace(request=old_request))))
        await entered.wait()
        self.items = catalog(('gpt-7-sol',))
        updated = asyncio.create_task(self.manager.refresh(self.router))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(prior, updated)
        self.assertIn('gpt-7-sol', self.router._models)

    async def test_failed_update_leaves_verified_catalog_roles_and_manifest_unchanged(self):
        result = await self.manager.refresh(self.router)
        old = {p.name: p.read_bytes() for p in (self.home / 'agents').glob('*.toml')}
        previous = dict(self.router._models)
        self.items = []
        with self.assertRaisesRegex(RuntimeError, 'No verified'):
            await self.manager.refresh(self.router)
        self.assertEqual(self.router._models, previous)
        self.assertEqual(old, {p.name: p.read_bytes() for p in (self.home / 'agents').glob('*.toml')})
        self.assertEqual(self.manager.snapshot(), result)

    async def test_user_created_colliding_role_is_preserved_on_failure(self):
        target = self.home / 'agents/gpt-6-1-sol.toml'
        target.write_text('name="gpt-6-1-sol"\ndeveloper_instructions="User owned custom role"\n')
        with self.assertRaisesRegex(RuntimeError, 'custom role'):
            await self.manager.refresh(self.router)
        self.assertIn('User owned', target.read_text())
        self.assertFalse((self.home / 'agents/gpt-6-astra.toml').exists())

    async def test_partial_filesystem_write_failure_rolls_back_installed_roles(self):
        import os
        from unittest.mock import patch
        await self.manager.refresh(self.router)
        old = {p.name: p.read_bytes() for p in (self.home / 'agents').glob('*.toml')}
        saved = self.manager.snapshot()
        before = dict(self.router._models)
        self.items = catalog(('gpt-7-sol',))
        replace = os.replace
        count = 0
        def fail_once(source, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('simulated locked role file')
            return replace(source, target)
        with patch('fpga_mesh.official_models.os.replace', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'locked role'):
                await self.manager.refresh(self.router)
        self.assertEqual(old, {p.name: p.read_bytes() for p in (self.home / 'agents').glob('*.toml')})
        self.assertEqual(saved, self.manager.snapshot())
        self.assertEqual(before, self.router._models)

    async def test_nonofficial_global_provider_is_rejected_without_auth_or_config_mutation(self):
        original = 'model_provider="custom_provider"\n'
        (self.home / 'config.toml').write_text(original)
        with self.assertRaisesRegex(ValueError, 'official'):
            await self.manager.refresh(self.router)
        self.assertEqual((self.home / 'config.toml').read_text(), original)
        self.assertEqual(self.calls, 0)

    async def test_parallel_refresh_is_serialized_and_verified_upgrade_retains_quality_guard(self):
        self.items = catalog(('gpt-7-astra',))
        self.items[1]['upgrade'] = 'gpt-7-astra'
        await asyncio.gather(self.manager.refresh(self.router), self.manager.refresh(self.router))
        self.assertEqual(self.router.best(), ('gpt-7-astra', 'ultra'))
        with self.assertRaises(ValueError):
            self.router.guard('gpt-6-luna', 'low', 'acceptance')


class CatalogRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_paginates_atomically_and_recognizes_new_models(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp, closing(MainSessionRouter(Path(tmp) / 'sessions.sqlite')) as router:
            router._models = {'gpt-6-astra': ('max',)}
            calls = []
            async def request(method, args):
                calls.append((method, args))
                if args.get('cursor'):
                    return {'data': catalog(('gpt-7-sol', 'codex-next'))}
                return {'data': [], 'nextCursor': 'next-page'}
            await router.catalog(SimpleNamespace(session=SimpleNamespace(request=request)), refresh=True)
            self.assertIn('gpt-7-sol', router._models)
            self.assertIn('codex-next', router._models)
            self.assertNotIn('codex-auto-review', router._models)
            self.assertEqual([c[0] for c in calls], ['model/list', 'model/list'])
            async def fail(method, args):
                raise RuntimeError('offline')
            before = dict(router._models)
            with self.assertRaisesRegex(RuntimeError, 'offline'):
                await router.catalog(SimpleNamespace(session=SimpleNamespace(request=fail)), refresh=True)
            self.assertEqual(before, router._models)

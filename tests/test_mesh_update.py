import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fpga_mesh.distribution import build_archive
from fpga_mesh import update


class MeshUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.old = self.root / 'old'
        self.new = self.root / 'new'
        self.workspace = self.root / 'workspace'
        for root in (self.old, self.new, self.workspace):
            root.mkdir()
        for root in (self.old, self.workspace):
            (root / 'change.txt').write_bytes(b'old\r\n')
            (root / 'same.txt').write_bytes(b'same\r\n')
        (self.new / 'change.txt').write_bytes(b'new\r\n')
        (self.new / 'same.txt').write_bytes(b'same\r\n')
        (self.new / 'added.txt').write_bytes(b'added\n')
        self.previous = self.root / 'old.zip'
        self.package = self.root / 'new.zip'
        build_archive(self.old, ['change.txt', 'same.txt'], self.previous, revision='old')

    def package_new(self):
        return build_archive(self.new, ['change.txt', 'same.txt', 'added.txt'],
                             self.package, revision='new',
                             previous_archives=[self.previous])

    def test_apply_changes_only_different_files_and_keeps_private_state(self):
        self.package_new()
        private = self.workspace / '.local'
        private.mkdir()
        (private / 'state.sqlite').write_bytes(b'private-state')
        (private / 'node.toml').write_bytes(b'node-private-configuration')
        before = (self.workspace / 'same.txt').stat().st_mtime_ns
        report = update.apply_update(self.package, self.workspace)
        self.assertEqual(set(report['changed']), {'added.txt', 'change.txt'})
        self.assertEqual((self.workspace / 'change.txt').read_bytes(), b'new\r\n')
        self.assertEqual((self.workspace / 'same.txt').stat().st_mtime_ns, before)
        self.assertEqual((private / 'state.sqlite').read_bytes(), b'private-state')
        self.assertEqual((private / 'node.toml').read_bytes(), b'node-private-configuration')
        backup = Path(report['backup'])
        self.assertEqual((backup / 'change.txt').read_bytes(), b'old\r\n')
        again = update.apply_update(self.package, self.workspace)
        self.assertEqual(again['changed'], [])
        self.assertIsNone(again['backup'])

    def test_local_changes_block_entire_update_without_overwriting(self):
        self.package_new()
        (self.workspace / 'change.txt').write_bytes(b'local-project-work')
        report = update.plan_update(self.package, self.workspace)
        self.assertEqual(report['conflicts'], ['change.txt'])
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.apply_update(self.package, self.workspace)
        self.assertFalse((self.workspace / 'added.txt').exists())
        self.assertEqual((self.workspace / 'change.txt').read_bytes(), b'local-project-work')
        self.assertFalse((self.workspace / '.local').exists())

    def test_git_checkout_line_endings_are_compatible(self):
        self.package_new()
        (self.workspace / 'change.txt').write_bytes(b'old\n')
        (self.workspace / 'same.txt').write_bytes(b'same\n')
        report = update.apply_update(self.package, self.workspace)
        self.assertEqual(set(report['changed']), {'added.txt', 'change.txt'})
        self.assertEqual((self.workspace / 'same.txt').read_bytes(), b'same\n')

    def test_unknown_existing_new_file_is_protected(self):
        self.package_new()
        (self.workspace / 'added.txt').write_bytes(b'my-new-feature')
        self.assertEqual(update.plan_update(self.package, self.workspace)['conflicts'],
                         ['added.txt'])

    def test_missing_base_and_private_or_escaping_paths_are_rejected(self):
        self.package_new()
        (self.workspace / 'same.txt').unlink()
        self.assertEqual(update.plan_update(self.package, self.workspace)['conflicts'],
                         ['same.txt'])
        for path in ('../escape.txt', '.local/secret.txt', 'C:/outside.txt', 'a:bad'):
            bad = self.root / 'bad.zip'
            payload = b'danger'
            with zipfile.ZipFile(bad, 'w') as archive:
                archive.writestr(path, payload)
                archive.writestr('MANIFEST.json', json.dumps({
                    'project': 'CarlandFPGA', 'profile': 'mesh', 'revision': 'bad',
                    'files': [{'path': path, 'size': len(payload),
                               'sha256': hashlib.sha256(payload).hexdigest()}],
                    'update': {'schema': 1, 'before': {path: [None]}, 'bases': []},
                }))
            with self.assertRaises(ValueError, msg=path):
                update.plan_update(bad, self.workspace)

    def test_corrupt_package_payload_is_rejected_before_any_write(self):
        self.package_new()
        bad = self.root / 'bad.zip'
        with zipfile.ZipFile(self.package) as source, zipfile.ZipFile(bad, 'w') as target:
            for name in source.namelist():
                target.writestr(name, b'corrupt' if name == 'change.txt' else source.read(name))
        with self.assertRaisesRegex(ValueError, 'hash|size'):
            update.apply_update(bad, self.workspace)
        self.assertEqual((self.workspace / 'change.txt').read_bytes(), b'old\r\n')

    def test_removed_files_are_deleted_only_when_old_content_is_known(self):
        (self.old / 'retired.txt').write_bytes(b'retired')
        (self.workspace / 'retired.txt').write_bytes(b'retired')
        build_archive(self.old, ['change.txt', 'same.txt', 'retired.txt'],
                      self.previous, revision='old')
        self.package_new()
        result = update.apply_update(self.package, self.workspace)
        self.assertEqual(result['deleted'], ['retired.txt'])
        self.assertFalse((self.workspace / 'retired.txt').exists())
        self.assertEqual((Path(result['backup']) / 'retired.txt').read_bytes(), b'retired')

    def test_write_failure_rolls_back_already_completed_changes(self):
        self.package_new()
        replace = update._replace
        calls = 0
        def fail_second(path, payload):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('disk failure')
            replace(path, payload)
        with patch.object(update, '_replace', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                update.apply_update(self.package, self.workspace)
        self.assertFalse((self.workspace / 'added.txt').exists())
        self.assertEqual((self.workspace / 'change.txt').read_bytes(), b'old\r\n')
        self.assertFalse((self.workspace / '.local/update-backups/update.lock').exists())

    def test_update_refuses_to_interrupt_queued_or_running_work(self):
        config = self.workspace / 'node.toml'
        config.write_text('node_id = "B"\nstate_dir = "state"\n', encoding='utf-8')
        state = self.workspace / 'state'
        state.mkdir()
        with closing(sqlite3.connect(state / 'child_jobs.sqlite')) as db, db:
            db.execute('CREATE TABLE child_jobs (status TEXT)')
            db.execute('INSERT INTO child_jobs VALUES ("running")')
        with self.assertRaisesRegex(ValueError, 'active|pending'):
            update.assert_idle(config, node='B')
        with closing(sqlite3.connect(state / 'child_jobs.sqlite')) as db, db:
            db.execute('UPDATE child_jobs SET status="completed"')
        self.assertEqual(update.assert_idle(config, node='B'), 'B')
        with self.assertRaisesRegex(ValueError, 'node'):
            update.assert_idle(config, node='C')

    def test_cli_preserves_custom_config_state_directory_for_service_reload(self):
        self.package_new()
        config = self.workspace / 'node.toml'
        config.write_text('node_id = "B"\nstate_dir = "existing-custom-state"\n', encoding='utf-8')
        result = subprocess.run([
            sys.executable, str(Path(update.__file__)), '--package', str(self.package),
            '--workspace', str(self.workspace), '--config', str(config), '--node', 'B',
        ], capture_output=True, text=True, check=True)
        self.assertEqual(Path(json.loads(result.stdout)['control_file']),
                         self.workspace / 'existing-custom-state/main-control.json')


if __name__ == '__main__':
    unittest.main()

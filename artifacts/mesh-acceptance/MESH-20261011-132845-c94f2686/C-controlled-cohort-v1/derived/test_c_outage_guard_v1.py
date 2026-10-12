"""Fake-only targeted regressions for the C fixed-node guard.

No real ScheduledTask, process, service, network, config or ledger action:
every probe is injected and every scratch path is a temporary directory.
Covers only the requested cases: C refusal/unarmed, exact C success at most
once, old PID / changed XML refusal, late-within-window and expired windows,
unknown start (and unknown health) no replay.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import c_outage_guard_v1 as guard  # noqa: E402

TEMP_BASE = HERE / '_test-temp'
TEMP_BASE.mkdir(exist_ok=True)


class FakeClock:
    def __init__(self, now):
        self.now_utc = now
        self.mono = 1000.0

    def now(self):
        return self.now_utc

    def monotonic(self):
        return self.mono

    def advance(self, seconds):
        self.now_utc += timedelta(seconds=seconds)
        self.mono += seconds

    def sleep(self, seconds):
        self.advance(seconds)


class GuardTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(TEMP_BASE))
        base = Path(self.temp.name).resolve()
        self.node_root = base
        self.round = base / guard.COHORT_DIRNAME
        self.round.mkdir()
        self.state_dir = base / '.local/deployment/node-c/.local/node-c'
        self.state_dir.mkdir(parents=True)
        self.config = self.node_root / '.local/deployment/node-c/node-c.toml'
        self.config.write_text('[node]\nid = "C"\n', encoding='utf-8')
        self.now = datetime.now(timezone.utc)
        self.clock = FakeClock(self.now)
        self.started = []
        self.wait_calls = []
        self.task_state = 'Ready'
        self.task_xml = 'a' * 64
        self.plan = self.make_plan(prepared=20, deadline=0, expires=90)
        self.phase = self.make_phase()

    def tearDown(self):
        self.temp.cleanup()

    def make_plan(self, *, prepared, deadline, expires, **overrides):
        plan = {
            'schema': guard.PLAN_SCHEMA, 'out_dir': str(self.round),
            'round_id': guard.ROUND, 'node_id': 'C', 'task_id': guard.TASK_ID,
            'task_version': 1, 'work_id': guard.WORK_ID,
            'operation_id': guard.ROUND + '-C-restore-op-v1',
            'nonce': 'c-outage-nonce-0123456789abcdef', 'armed': True,
            'task_name': guard.TASK_NAME, 'task_xml_sha256': self.task_xml,
            'prepared_at_utc': (self.now - timedelta(seconds=prepared)).isoformat(),
            'restore_at_utc': (self.now + timedelta(seconds=deadline)).isoformat(),
            'expires_at_utc': (self.now + timedelta(seconds=expires)).isoformat(),
            'task_root_pid': 12344, 'supervisor_pid': 12345, 'worker_pid': 12347,
            'original_processes': [
                {'pid': pid, 'parent_pid': parent,
                 'created_at_utc': (self.now - timedelta(hours=1)).isoformat()}
                for pid, parent in ((12344, 900), (12345, 12344), (12346, 12345), (12347, 12346))],
            'service_config': str(self.config), 'state_dir': str(self.state_dir),
        }
        plan.update(overrides)
        return plan

    def make_phase(self, state='STOP_ATTEMPTED'):
        phase = {key: self.plan[key] for key in guard.IDENTITY}
        phase.update(schema=guard.PHASE_SCHEMA, state=state, armed=True,
                     stop_attempted_at_utc=(self.now - timedelta(seconds=10)).isoformat())
        return phase

    def rescale(self, *, prepared, deadline, expires):
        self.plan = self.make_plan(prepared=prepared, deadline=deadline, expires=expires)
        self.phase = self.make_phase()

    def fake_task(self):
        return {'task_name': guard.TASK_NAME, 'task_path': '\\', 'state': self.task_state,
                'xml_sha256': self.task_xml}

    def fake_process(self, pid):
        originals = {p['pid'] for p in self.plan['original_processes']}
        return pid not in originals

    def fake_start(self):
        self.assertTrue((self.round / guard.FILES['attempt']).exists(),
                        'durable exclusive claim must precede the single start')
        self.started.append('START')
        self.task_state = 'Running'
        return 0

    def fake_wait_stopped(self, config, timeout):
        self.wait_calls.append((config, timeout))
        remaining = (guard.timestamp(self.plan['expires_at_utc']) - self.clock.now()).total_seconds()
        self.assertLessEqual(timeout, remaining + 0.001,
                             'wait timeout must fit the remaining bound')

    def healthy(self, pid=55555):
        return {'node_id': 'C', 'project_id': 'fpga-main', 'pid': pid, 'started': True, 'feishu_connected': True, 'network_enabled': True,
                'peer_listen_port': 8787, 'peer_error': None, 'feishu_error': None}

    def fake_health(self, state_dir):
        return self.healthy()

    def fake_identity(self, pid):
        if pid == os.getpid():
            return {'pid': pid, 'parent_pid': 1, 'created_at_utc': self.now.isoformat(), 'probe_ok': True}
        original = {p['pid']: p for p in self.plan['original_processes']}[pid]
        return {'pid': pid, 'parent_pid': original['parent_pid'],
                'created_at_utc': original['created_at_utc'], 'probe_ok': True}

    def fake_isolation(self, supervisor_pid, worker_pid):
        return {'pid': os.getpid(), 'supervisor_pid': supervisor_pid, 'worker_pid': worker_pid,
                'isolation_verified': True, 'read_only': True,
                'jobs': [{'supervisor_job_handle': 1, 'job_member_pids': [12345, 12346, 12347],
                          'current_process_in_service_job': False}]}

    def run_restore(self, **overrides):
        args = dict(out_dir=self.round, node_root=self.node_root, now_fn=self.clock.now,
                    monotonic_fn=self.clock.monotonic, sleep_fn=self.clock.sleep,
                    task_probe=self.fake_task, process_probe=self.fake_process,
                    start_task=self.fake_start, wait_stopped=self.fake_wait_stopped,
                    health_probe=self.fake_health)
        args.update(overrides)
        return guard.restore_once(self.plan, self.phase, **args)

    def write_round_files(self):
        plan_path = self.round / guard.FILES['plan']
        plan_path.write_bytes(guard.canonical(self.plan) + b'\n')
        (self.round / guard.FILES['phase']).write_bytes(guard.canonical(self.phase) + b'\n')
        return guard.sha(plan_path.read_bytes())

    class Args:
        def __init__(self, plan_sha256):
            self.execute_watch = True
            self.plan_sha256 = plan_sha256

    def run_watch(self, plan_sha256=None, **overrides):
        if plan_sha256 is None:
            plan_sha256 = self.write_round_files()
        args = dict(out_dir=self.round, node_root=self.node_root, now_fn=self.clock.now,
                    monotonic_fn=self.clock.monotonic, sleep_fn=self.clock.sleep,
                    task_probe=self.fake_task, process_probe=self.fake_process,
                    process_identity_probe=self.fake_identity,
                    isolation_probe=self.fake_isolation, start_task=self.fake_start,
                    wait_stopped=self.fake_wait_stopped, health_probe=self.fake_health)
        args.update(overrides)
        return guard.run_execute_watch(self.Args(plan_sha256), **args)

class CRefusalUnarmedTests(GuardTestCase):
    def test_unarmed_or_nonce_missing_refuses_everywhere(self):
        mutations = {
            'plan-armed-absent': lambda plan, phase: plan.pop('armed'),
            'plan-armed-false': lambda plan, phase: plan.update(armed=False),
            'phase-armed-absent': lambda plan, phase: phase.pop('armed'),
            'phase-armed-false': lambda plan, phase: phase.update(armed=False),
            'nonce-empty': lambda plan, phase: (plan.update(nonce=''), phase.update(nonce='')),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                plan, phase = dict(self.plan), dict(self.phase)
                mutate(plan, phase)
                with self.assertRaisesRegex(ValueError, 'armed|nonce'):
                    guard.validate(plan, phase, self.round, self.node_root)
                result = guard.restore_once(
                    plan, phase, out_dir=self.round, node_root=self.node_root,
                    now_fn=self.clock.now, monotonic_fn=self.clock.monotonic, sleep_fn=self.clock.sleep,
                    task_probe=self.fake_task, process_probe=self.fake_process,
                    start_task=self.fake_start, wait_stopped=self.fake_wait_stopped,
                    health_probe=self.fake_health)
                self.assertEqual(result['status'], 'REFUSED', result)
                self.assertFalse(result.get('start_attempted'), result)
                self.assertEqual(self.started, [])
                self.assertFalse((self.round / guard.FILES['attempt']).exists())

    def test_foreign_a_identity_refuses(self):
        for key, value in (('node_id', 'A'), ('task_name', 'FPGA-Mesh-Node-A'),
                           ('task_id', guard.ROUND + '-A-controlled-outage'),
                           ('work_id', 'ab-controlled-outage-v2'), ('round_id', 'OTHER-ROUND')):
            with self.subTest(key=key):
                plan = dict(self.plan)
                plan[key] = value
                phase = dict(self.phase)
                phase[key] = value
                with self.assertRaisesRegex(ValueError, 'fixed'):
                    guard.validate(plan, phase, self.round, self.node_root)
                result = guard.restore_once(
                    plan, phase, out_dir=self.round, node_root=self.node_root,
                    now_fn=self.clock.now, monotonic_fn=self.clock.monotonic, sleep_fn=self.clock.sleep,
                    task_probe=self.fake_task, process_probe=self.fake_process,
                    start_task=self.fake_start, wait_stopped=self.fake_wait_stopped,
                    health_probe=self.fake_health)
                self.assertEqual(result['status'], 'REFUSED', result)
                self.assertEqual(self.started, [])

    def test_execute_watch_refuses_unarmed_and_writes_no_ready_or_attempt(self):
        self.plan.pop('armed')
        with self.assertRaisesRegex(ValueError, 'armed'):
            self.run_watch()
        self.assertEqual(self.started, [])
        self.assertFalse((self.round / guard.FILES['ready']).exists())
        self.assertFalse((self.round / guard.FILES['attempt']).exists())
        self.assertFalse((self.round / guard.FILES['log']).exists())

    def test_guard_source_has_no_stop_capability(self):
        source = Path(guard.__file__).read_text(encoding='utf-8')
        for token in ('Stop-ScheduledTask', 'Stop-Process', 'taskkill', 'Stop-Computer',
                      'Disable-ScheduledTask', 'Unregister-ScheduledTask'):
            self.assertNotIn(token.lower(), source.lower())
        self.assertIn('Start-ScheduledTask', source)


class CSuccessAtMostOnceTests(GuardTestCase):
    def test_restore_once_single_start_verified_then_no_replay(self):
        result = self.run_restore()
        self.assertEqual(result['status'], 'START_HEALTH_VERIFIED', result)
        self.assertTrue(result['health_verified'])
        self.assertEqual(self.started, ['START'])
        self.assertEqual(len(self.wait_calls), 1)
        again = self.run_restore()
        self.assertEqual(again['status'], 'NO_REPLAY')
        self.assertEqual(self.started, ['START'])
        records = [json.loads(line) for line in
                   (self.round / guard.FILES['attempt']).read_text(encoding='utf-8').splitlines()]
        self.assertEqual(records[0]['status'], 'START_ATTEMPTED')
        self.assertEqual(records[0]['node_id'], 'C')
        self.assertEqual(records[0]['task_id'], guard.TASK_ID)
        self.assertEqual(records[0]['work_id'], guard.WORK_ID)
        self.assertEqual(records[0]['plan_sha256'], guard.sha(guard.canonical(self.plan)))
        self.assertEqual(records[-1]['status'], 'START_HEALTH_VERIFIED')

    def test_execute_watch_full_path_starts_exactly_once(self):
        self.rescale(prepared=60, deadline=30, expires=120)
        self.task_state = 'Running'

        def sleep(seconds):
            self.clock.advance(seconds)
            if self.clock.now() >= guard.timestamp(self.plan['restore_at_utc']):
                self.task_state = 'Ready'

        result, code = self.run_watch(sleep_fn=sleep)
        self.assertEqual(result['status'], 'START_HEALTH_VERIFIED', result)
        self.assertEqual(code, 0)
        self.assertEqual(self.started, ['START'])
        ready = json.loads((self.round / guard.FILES['ready']).read_text(encoding='utf-8'))
        self.assertEqual(ready['node_id'], 'C')
        self.assertEqual(ready['task']['state'], 'Running')
        with self.assertRaisesRegex(ValueError, 'existing restoration attempt'):
            self.run_watch(sleep_fn=sleep)
        self.assertEqual(self.started, ['START'])


class OldPidChangedXmlTests(GuardTestCase):
    def test_old_pid_present_refuses_without_claim(self):
        result = self.run_restore(process_probe=lambda pid: pid == 12346)
        self.assertEqual(result['status'], 'OLD_PID_PRESENT', result)
        self.assertEqual(self.started, [])
        self.assertFalse((self.round / guard.FILES['attempt']).exists())

    def test_changed_xml_or_task_name_refuses(self):
        self.task_xml = 'b' * 64
        result = self.run_restore()
        self.assertEqual(result['status'], 'REFUSED', result)
        self.assertIn('changed', result.get('detail', ''))
        self.assertEqual(self.started, [])
        self.task_xml = 'a' * 64

        def wrong_name():
            value = self.fake_task()
            value['task_name'] = 'FPGA-Mesh-Node-A'
            return value

        result = self.run_restore(task_probe=wrong_name)
        self.assertEqual(result['status'], 'REFUSED', result)
        self.assertEqual(self.started, [])

    def test_changed_process_identity_refuses_watch_preparation(self):
        self.rescale(prepared=60, deadline=30, expires=120)
        self.task_state = 'Running'

        def bad_identity(pid):
            value = self.fake_identity(pid)
            value['parent_pid'] = value['parent_pid'] + 1
            return value

        with self.assertRaisesRegex(ValueError, 'identity or parent changed'):
            self.run_watch(sleep_fn=self.clock.sleep, process_identity_probe=bad_identity)
        self.assertFalse((self.round / guard.FILES['ready']).exists())
        self.assertFalse((self.round / guard.FILES['attempt']).exists())
        self.assertEqual(self.started, [])


class WindowTests(GuardTestCase):
    def test_before_deadline_waits_then_starts_once_at_deadline(self):
        self.rescale(prepared=30, deadline=10, expires=70)
        result = self.run_restore()
        self.assertEqual(result['status'], 'WAITING', result)
        self.assertEqual(self.started, [])
        self.assertFalse((self.round / guard.FILES['attempt']).exists())
        self.clock.advance(10)
        result = self.run_restore()
        self.assertEqual(result['status'], 'START_HEALTH_VERIFIED', result)
        self.assertEqual(self.started, ['START'])

    def test_monotonic_limit_already_reached_refuses_without_start(self):
        result = self.run_restore(monotonic_deadline=self.clock.mono)
        self.assertEqual(result['status'], 'REFUSED_MONOTONIC_LIMIT', result)
        self.assertEqual(self.started, [])

    def test_wait_stopped_exhaustion_cannot_start_late(self):
        def consuming_wait(config, timeout):
            self.wait_calls.append((config, timeout))
            self.clock.advance(1000)

        result = self.run_restore(wait_stopped=consuming_wait)
        self.assertEqual(result['status'], 'EXPIRED_AFTER_WAIT', result)
        self.assertEqual(self.started, [])
        self.assertFalse((self.round / guard.FILES['attempt']).exists())

        self.now = datetime.now(timezone.utc)
        self.clock = FakeClock(self.now)
        self.plan = self.make_plan(prepared=20, deadline=0, expires=90)
        self.phase = self.make_phase()

        def mono_consuming_wait(config, timeout):
            self.wait_calls.append((config, timeout))
            self.clock.advance(5)
            self.clock.mono += 10 ** 9

        result = self.run_restore(wait_stopped=mono_consuming_wait,
                                  monotonic_deadline=self.clock.mono + 100)
        self.assertEqual(result['status'], 'REFUSED_MONOTONIC_LIMIT', result)
        self.assertEqual(self.started, [])
        self.assertFalse((self.round / guard.FILES['attempt']).exists())

    def test_probe_slowness_past_expiry_cannot_start_late(self):
        def slow_process(pid):
            self.clock.advance(120)
            return False

        result = self.run_restore(process_probe=slow_process)
        self.assertEqual(result['status'], 'EXPIRED_AFTER_PROBES', result)
        self.assertEqual(self.started, [])
        self.assertFalse((self.round / guard.FILES['attempt']).exists())

    def test_expired_window_and_stop_outside_window_refuse(self):
        self.clock.advance(120)
        result = self.run_restore()
        self.assertEqual(result['status'], 'EXPIRED', result)
        self.assertEqual(self.started, [])
        self.phase['stop_attempted_at_utc'] = (
            guard.timestamp(self.plan['restore_at_utc']) + timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError, 'stop outside planned window'):
            guard.validate(self.plan, self.phase, self.round, self.node_root)


class UnknownNoRetryTests(GuardTestCase):
    def test_unknown_start_no_replay(self):
        def exploding_start():
            self.started.append('START-ATTEMPT')
            raise RuntimeError('start outcome unknown')

        result = self.run_restore(start_task=exploding_start)
        self.assertEqual(result['status'], 'START_OUTCOME_UNKNOWN', result)
        self.assertTrue(result['start_attempted'])
        self.assertEqual(self.started, ['START-ATTEMPT'])
        again = self.run_restore(start_task=exploding_start)
        self.assertEqual(again['status'], 'NO_REPLAY')
        self.assertEqual(self.started, ['START-ATTEMPT'])

    def test_nonzero_start_return_is_unknown_no_replay(self):
        def nonzero_start():
            self.started.append('START-ATTEMPT')
            return 3

        result = self.run_restore(start_task=nonzero_start)
        self.assertEqual(result['status'], 'START_OUTCOME_UNKNOWN', result)
        self.assertEqual(result['exit_code'], 3)
        again = self.run_restore(start_task=nonzero_start)
        self.assertEqual(again['status'], 'NO_REPLAY')
        self.assertEqual(self.started, ['START-ATTEMPT'])

    def test_wait_stopped_unknown_never_starts(self):
        def failing_wait(config, timeout):
            raise TimeoutError('still stopping')

        result = self.run_restore(wait_stopped=failing_wait)
        self.assertEqual(result['status'], 'STOP_WAIT_UNKNOWN', result)
        self.assertEqual(self.started, [])
        self.assertFalse((self.round / guard.FILES['attempt']).exists())

    def test_health_unknown_is_distinguished_and_never_replays(self):
        def failing_health(state_dir):
            raise RuntimeError('service not reachable yet')

        result = self.run_restore(health_probe=failing_health)
        self.assertEqual(result['status'], 'START_HEALTH_UNKNOWN', result)
        self.assertIsNone(result['health_verified'])
        self.assertEqual(self.started, ['START'])
        again = self.run_restore(health_probe=failing_health)
        self.assertEqual(again['status'], 'NO_REPLAY')
        self.assertEqual(self.started, ['START'])

    def test_unhealthy_health_is_negative_and_never_replays(self):
        def stale_health(state_dir):
            return self.healthy(pid=12345)

        result = self.run_restore(health_probe=stale_health)
        self.assertEqual(result['status'], 'START_STARTED_UNHEALTHY', result)
        self.assertFalse(result['health_verified'])
        again = self.run_restore(health_probe=stale_health)
        self.assertEqual(again['status'], 'NO_REPLAY')
        self.assertEqual(self.started, ['START'])


if __name__ == '__main__':
    unittest.main()

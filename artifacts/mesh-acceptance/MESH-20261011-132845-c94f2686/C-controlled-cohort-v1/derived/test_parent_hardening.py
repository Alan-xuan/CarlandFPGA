"""Focused parent review regressions; every OS/service action is fake."""
from test_c_outage_guard_v1 import GuardTestCase, guard


class ParentReviewTests(GuardTestCase):
    def test_task_launcher_is_required_and_must_be_absent_before_start(self):
        launcher = self.plan.pop('task_root_pid')
        self.assertEqual(self.run_restore()['status'], 'REFUSED')
        self.plan['task_root_pid'] = launcher
        result = self.run_restore(process_probe=lambda pid: pid == launcher)
        self.assertEqual(result['status'], 'OLD_PID_PRESENT')
        self.assertEqual(self.started, [])

    def test_plan_changed_during_probes_refuses(self):
        valid = [True]
        def process(pid):
            valid[0] = False
            return False
        result = self.run_restore(process_probe=process, immutable_plan_check=lambda: valid[0])
        self.assertEqual(result['status'], 'REFUSED')
        self.assertEqual(self.started, [])

    def test_late_inside_expiry_starts_only_once(self):
        self.clock.advance(10)
        result = self.run_restore()
        self.assertEqual(result['status'], 'START_HEALTH_VERIFIED')
        self.assertEqual(self.run_restore()['status'], 'NO_REPLAY')
        self.assertEqual(self.started, ['START'])

    def test_foreign_config_and_foreign_health_refuse(self):
        old = self.plan['service_config']
        other = self.node_root/'foreign.toml'
        other.write_text('node_id="C"')
        self.plan['service_config'] = str(other)
        self.assertEqual(self.run_restore()['status'], 'REFUSED')
        self.plan['service_config'] = old
        result = self.run_restore(health_probe=lambda _: self.healthy() | {'node_id':'B'})
        self.assertEqual(result['status'], 'START_STARTED_UNHEALTHY')
        self.assertEqual(self.run_restore()['status'], 'NO_REPLAY')

    def test_health_result_after_expiry_is_not_success(self):
        def late_health(_):
            self.clock.advance(100)
            return self.healthy()
        result = self.run_restore(health_probe=late_health)
        self.assertNotEqual(result['status'], 'START_HEALTH_VERIFIED')
        self.assertEqual(self.started, ['START'])

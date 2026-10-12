"""Three fake-stop tests using the real three-ledger idle fence on scratch DBs."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from types import SimpleNamespace
from unittest import mock
from datetime import timedelta
from test_c_outage_guard_v1 import GuardTestCase, guard

spec = importlib.util.spec_from_file_location('stop_prepared_c',Path(__file__).resolve().parents[1]/'stop_prepared_c.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)

class StopDriverTests(GuardTestCase):
    def setUp(self):
        super().setUp()
        self.rescale(prepared=10,deadline=500,expires=600)
        self.phase = self.make_phase('PREPARED')
        self.digest = self.write_round_files()
        self.config.write_text('node_id="C"\nstate_dir='+json.dumps(str(self.state_dir))+'\n')
        self.dbpaths=[]
        for name,table,columns in (
            ('state.sqlite','inbound','processed_at TEXT'),
            ('main_sessions.sqlite','main_runs','status TEXT'),
            ('child_jobs.sqlite','child_jobs','status TEXT, route TEXT, error TEXT')):
            path=self.state_dir/name
            with closing(sqlite3.connect(path)) as db:db.execute('CREATE TABLE '+table+'('+columns+')')
            self.dbpaths.append(path)
        self.identity={'pid':os.getpid(),'parent_pid':1,'created_at_utc':self.now.isoformat()}
        (self.round/guard.FILES['ready']).write_text(json.dumps(dict(
            schema=guard.READY_SCHEMA,plan_sha256=self.digest,pid=os.getpid(),helper_process=self.identity)))
        self.stop_calls=[]

    def call(self,code=0):
        def fake_run(*args,**kwargs):
            self.stop_calls.append(args)
            for path in self.dbpaths:
                with closing(sqlite3.connect(path,timeout=0)) as db:
                    with self.assertRaises(sqlite3.OperationalError):db.execute('BEGIN IMMEDIATE')
            return SimpleNamespace(returncode=code)
        with mock.patch.object(driver,'OUT',self.round), \
             mock.patch.object(guard,'validate',return_value=(self.round, self.now+timedelta(seconds=500), self.now+timedelta(seconds=600),self.config,self.state_dir,20,60)), \
             mock.patch.object(guard,'read_task_probe',return_value=self.fake_task()|{'state':'Running'}), \
             mock.patch.object(guard,'read_process_identity_probe',side_effect=self.fake_identity), \
             mock.patch.object(guard,'read_process_probe',return_value=False), \
             mock.patch.object(guard,'wait_stopped_via_service'), \
             mock.patch.object(driver,'verify_service_job_isolation',side_effect=self.fake_isolation), \
             mock.patch.object(driver.subprocess,'run',side_effect=fake_run):
            return driver.stop_once(self.digest)

    def test_three_real_scratch_writer_locks_held_during_fake_stop(self):
        self.call()
        self.assertEqual(len(self.stop_calls),1)
        self.assertTrue((self.round/'c-stop-confirmed-v1.json').is_file())

    def test_busy_main_refuses_before_stop_or_phase_change(self):
        with closing(sqlite3.connect(self.state_dir/'main_sessions.sqlite')) as db:
            db.execute("INSERT INTO main_runs VALUES ('queued')")
            db.commit()
        with self.assertRaises(ValueError):self.call()
        self.assertEqual(self.stop_calls,[])
        self.assertEqual(json.loads((self.round/guard.FILES['phase']).read_text())['state'],'PREPARED')

    def test_unknown_stop_is_latched_and_never_replayed(self):
        with self.assertRaises(RuntimeError):self.call(code=1)
        with self.assertRaises(ValueError):self.call()
        self.assertEqual(len(self.stop_calls),1)

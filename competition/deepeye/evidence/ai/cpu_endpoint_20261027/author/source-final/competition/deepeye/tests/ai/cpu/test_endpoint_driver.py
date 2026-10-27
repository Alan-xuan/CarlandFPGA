"""Private FAKE-core lifecycle/I/O controls; no real endpoint/model launch.

The real pinned stdlib parser is used. Only the internal _new_core is replaced;
the recorded A result is an opaque static fixture, never fake positive inference.
"""
from dataclasses import asdict, replace
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai_pc.cpu_package import endpoint_protocol as w
from ai_pc.cpu_package import process_endpoint as p

# Keep tests runnable directly without making new package/__init__ files.
_helpers = importlib.util.spec_from_file_location('c22_protocol_test_helpers', Path(__file__).with_name('test_endpoint_protocol.py'))
_h = importlib.util.module_from_spec(_helpers)
_helpers.loader.exec_module(_h)
identity, split_response, FIXTURES = _h.identity, _h.split_response, _h.FIXTURES
RECORD = (FIXTURES / 'original-first-record.jsonl').read_bytes()
RECORDED_RESULT = (FIXTURES / 'A-C21-first-result.exact.json').read_bytes()


def frame(index=1, *, invocation=None, payload=RECORD, kind=w.OBSERVE, **fields):
    return w.encode_request(identity(index if invocation is None else invocation, **fields), index, payload, kind=kind)


def changed_record(**changes):
    doc = json.loads(RECORD)
    doc.update(changes)
    return json.dumps(doc, separators=(',', ':'), allow_nan=False).encode() + b'\n'


class FakeCore:
    """Explicit test double, no learned logits/model/scaler or production path."""
    def __init__(self, *, result=RECORDED_RESULT, fail=None):
        self.result, self.fail = result, fail
        self.token = object()
        self.starts, self.observes, self.ends = [], [], []

    def start_session(self, **values):
        self.starts.append(values)
        if self.fail == 'start':
            raise RuntimeError('private start fault')
        return self.token

    def observe(self, token, raw):
        assert token is self.token
        self.observes.append(raw)
        if self.fail == 'observe':
            raise RuntimeError('private observe fault')
        return SimpleNamespace(encoded=self.result)

    def end_session(self, token):
        assert token is self.token
        self.ends.append(token)
        if self.fail == 'end':
            raise RuntimeError('private end fault')
        return SimpleNamespace(encoded=b'{"scope":"PRIVATE_FAKE_END","movement_authorized":false}\n')


class MemoryIO:
    def __init__(self, raw, *, chunk=10**6, write_result='complete'):
        self.raw, self.chunk, self.write_result = raw, chunk, write_result
        self.position = 0
        self.reads, self.writes, self.events = [], [], []

    def read(self, size):
        self.reads.append(size)
        self.events.append(('read', self.position, size))
        data = self.raw[self.position:self.position + min(size, self.chunk)]
        self.position += len(data)
        return data

    def write(self, raw):
        self.writes.append(raw)
        self.events.append(('write', self.position, len(raw)))
        if self.write_result == 'complete':
            return len(raw)
        if self.write_result == 'raise':
            raise OSError('private write fault')
        if self.write_result == 'short':
            return len(raw)-1
        return self.write_result


class EndpointDriverTests(unittest.TestCase):
    def setUp(self):
        self.real_import = builtins.__import__
        self.forbidden_imports = []
        def guarded(name, *args, **kwargs):
            if name == 'torch' or name.startswith('torch.') or name in ('ai_pc.model.force_cnn', 'ai_pc.cpu_package.stream_core'):
                self.forbidden_imports.append(name)
                raise AssertionError('real learned core/model imports forbidden in C22 controls')
            return self.real_import(name, *args, **kwargs)
        self.guard = patch('builtins.__import__', side_effect=guarded)
        self.guard.start()

    def tearDown(self):
        self.guard.stop()
        self.assertEqual(self.forbidden_imports, [])
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('ai_pc.model.force_cnn', sys.modules)
        self.assertNotIn('ai_pc.cpu_package.stream_core', sys.modules)

    def run_fake(self, io, core=None, limits=None, constructor_failure=False):
        core = FakeCore() if core is None else core
        with patch.object(p, '_new_core', side_effect=RuntimeError('private ctor fault') if constructor_failure else None,
                          return_value=core) as constructor:
            driver = p.EndpointDriver(io.read, io.write, limits=limits)
            result = driver.run()
        return result, core, constructor.call_count, driver

    def test_partial_reads_one_lifetime_original_binding_END_no_tail(self):
        first = frame()
        second = frame(2, payload=changed_record(sequence=7328))
        end = frame(3, payload=b'', kind=w.END)
        io = MemoryIO(first + second + end + b'POISON FUTURE HEADER', chunk=7)
        result, core, count, driver = self.run_fake(io)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual((count, len(core.starts), len(core.observes), len(core.ends)), (1, 1, 2, 1))
        self.assertEqual(core.starts, [dict(generation=1, epoch=0, run_id='C-FORCE-CPU-20261024-v1')])
        self.assertNotEqual(core.starts[0]['run_id'], identity().run_id)
        self.assertEqual(core.observes, [RECORD, changed_record(sequence=7328)])
        self.assertEqual(io.position, len(first+second+end))
        self.assertEqual(len(io.writes), 3)
        self.assertEqual(split_response(io.writes[0])[2], RECORDED_RESULT)
        write_events = [event for event in io.events if event[0] == 'write']
        self.assertEqual([event[1] for event in write_events], [len(first), len(first+second), len(first+second+end)])
        reads_before = len(io.reads)
        self.assertEqual(driver.run().diagnostic, 'driver_retired')
        self.assertEqual((len(io.reads), len(io.writes)), (reads_before, 3))
        self.assertTrue(all(type(size) is int and 1 <= size <= 2048 for size in io.reads))

    def test_invalid_future_suffix_cannot_change_prior_reply(self):
        replies = []
        for suffix in (b'', b'bad header bytes', w.HEADER.pack(b'C22E', 1, 1, 0, 2049, 1),
                       frame(2, payload=changed_record(extra='invalid'))):
            io = MemoryIO(frame()+suffix)
            result, core, count, _ = self.run_fake(io)
            self.assertEqual(result.exit_code, 1)
            self.assertEqual((len(io.writes), len(core.observes), len(core.ends), count), (1, 1, 1, 1))
            replies.append(io.writes[0])
        self.assertTrue(all(raw == replies[0] for raw in replies))

    def test_first_original_record_strict_validation_precedes_constructor(self):
        invalid = [changed_record(extra=1), changed_record(source_domain='software_fixture'),
                   changed_record(profile_id='sim_em_v2'), changed_record(preprocessing_sha256='0'*64),
                   changed_record(run_id=''), changed_record(run_id='\u00e9'*65),
                   changed_record(sequence=True), changed_record(valid_0=1),
                   RECORD.replace(b'"sequence":7327', b'"sequence":NaN'),
                   RECORD.replace(b'"sequence":7327', b'"sequence":7327,"sequence":7327'), b'\xff', b'{}']
        for raw in invalid:
            with self.subTest(raw=raw[:70]):
                io = MemoryIO(frame(payload=raw))
                result, core, count, _ = self.run_fake(io)
                self.assertEqual((result.exit_code, count, len(core.starts), len(io.writes)), (1, 0, 0, 0))
        # Exactly128 UTF8 bytes is valid; original bytes remain unchanged.
        raw = changed_record(run_id='\u00e9'*64)
        io = MemoryIO(frame(payload=raw)+frame(2, payload=b'', kind=w.END))
        result, core, count, _ = self.run_fake(io)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(core.starts[0]['run_id'], '\u00e9'*64)
        self.assertEqual(core.observes, [raw])

    def test_later_record_binding_and_envelope_identity_each_frozen(self):
        changed = [frame(2, payload=changed_record(run_id='different')),
                   frame(2, payload=changed_record(source_domain='software_fixture')),
                   frame(2, operation_id='other'), frame(2, run_id='other'),
                   frame(2, request_hash='3'*64), frame(2, tested_commit='a'*40),
                   frame(2, package_manifest_sha256='4'*64), frame(2, actor_instance_id='other'),
                   frame(2, invocation=1), frame(2, invocation=1, kind=w.END, payload=b''),
                   frame(3), frame(1, invocation=2)]
        for suffix in changed:
            with self.subTest(sha=hashlib.sha256(suffix).hexdigest()):
                io = MemoryIO(frame()+suffix)
                result, core, count, _ = self.run_fake(io)
                self.assertEqual(result.exit_code, 1)
                self.assertEqual((count, len(core.observes), len(core.ends), len(io.writes)), (1, 1, 1, 1))
        # Strictly increasing invocation IDs need not be adjacent.
        io = MemoryIO(frame(invocation=(1<<63)-2)+frame(2, invocation=(1<<63)-1, kind=w.END, payload=b''))
        self.assertEqual(self.run_fake(io)[0].exit_code, 0)

    def test_read_EOF_exception_types_and_overread_stop_without_output(self):
        valid = frame()
        for raw in (b'', valid[:1], valid[:15], valid[:20], valid[:-1], frame(1, kind=w.END, payload=b'')):
            io = MemoryIO(raw)
            result, core, count, driver = self.run_fake(io)
            self.assertEqual((result.exit_code, count, len(io.writes)), (1, 0, 0))
        for bad in (None, bytearray(b'x'), True, b'x'*17):
            io = MemoryIO(b'')
            with patch.object(io, 'read', return_value=bad) as read:
                result, core, count, _ = self.run_fake(io)
            self.assertEqual((result.exit_code, read.call_count, count, len(io.writes)), (1, 1, 0, 0))
        io = MemoryIO(b'')
        with patch.object(io, 'read', side_effect=OSError('private fault')) as read:
            result, _, count, _ = self.run_fake(io)
        self.assertEqual((result.exit_code, read.call_count, count), (1, 1, 0))

    def test_unknown_or_partial_write_has_no_retry_tail_or_error_frame(self):
        first = frame()
        for returned in ('short', 'raise', 0, None, True, -1, 10**9, 1.0):
            with self.subTest(returned=returned):
                io = MemoryIO(first + frame(2, payload=b'', kind=w.END), write_result=returned)
                result, core, count, _ = self.run_fake(io)
                self.assertEqual(result.exit_code, 1)
                self.assertEqual((io.position, len(io.writes), count, len(core.ends)), (len(first), 1, 1, 1))
                self.assertEqual(result.responses_emitted, 0)

    def test_core_failures_and_cleanup_end_at_most_once(self):
        io = MemoryIO(frame())
        result, core, count, _ = self.run_fake(io, constructor_failure=True)
        self.assertEqual((result.exit_code, count, len(io.writes), len(core.ends)), (1, 1, 0, 0))
        for stage, expected_ends in [('start', 0), ('observe', 1), ('end', 1)]:
            io = MemoryIO(frame()+frame(2, payload=b'', kind=w.END))
            result, core, count, _ = self.run_fake(io, FakeCore(fail=stage))
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(len(core.ends), expected_ends)
            self.assertEqual(len(io.writes), 1 if stage == 'end' else 0)
        io = MemoryIO(frame())  # EOF cleanup fails, no local receipt output.
        result, core, _, _ = self.run_fake(io, FakeCore(fail='end'))
        self.assertTrue(result.cleanup_failed)
        self.assertEqual((result.exit_code, len(core.ends), len(io.writes)), (1, 1, 1))

    def test_result_size_type_or_serialization_failure_retires_before_write(self):
        for encoded in (b'x'*4096+b'\n', b'x'*4096, b'', bytearray(b'x\n'), None):
            io = MemoryIO(frame()+frame(2))
            result, core, _, _ = self.run_fake(io, FakeCore(result=encoded))
            self.assertEqual((result.exit_code, len(io.writes), len(core.ends), len(core.observes)), (1, 0, 1, 1))

    def test_lifetime_caps_are_lower_only_and_checked_before_side_effect(self):
        first, end = frame(), frame(2, payload=b'', kind=w.END)
        for changes in [dict(max_frames=True), dict(max_observations=65536),
                        dict(max_input_bytes=64*1024*1024+1), dict(max_output_bytes=0)]:
            with self.assertRaises(w.ProtocolError):
                p.EndpointLimits(**changes)
        io = MemoryIO(first+end)
        result, _, count, _ = self.run_fake(io, limits=p.EndpointLimits(max_input_bytes=len(first)-1))
        self.assertEqual((result.exit_code, io.position, count, len(io.writes)), (1, 16, 0, 0))
        io = MemoryIO(first+frame(2)+end)
        result, core, _, _ = self.run_fake(io, limits=p.EndpointLimits(max_observations=1))
        self.assertEqual((result.exit_code, len(core.observes), len(io.writes)), (1, 1, 1))
        io = MemoryIO(first+end)
        result, core, _, _ = self.run_fake(io, limits=p.EndpointLimits(max_output_bytes=1))
        self.assertEqual((result.exit_code, len(core.observes), len(io.writes), len(core.ends)), (1, 1, 0, 1))
        io = MemoryIO(first+end)
        result, _, _, _ = self.run_fake(io, limits=p.EndpointLimits(max_frames=2, max_input_bytes=len(first+end)))
        self.assertEqual(result.exit_code, 0)

    def test_duplicate_record_bytes_delivered_without_invented_observation(self):
        io = MemoryIO(frame()+frame(2)+frame(3, kind=w.END, payload=b''))
        result, core, _, _ = self.run_fake(io)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(core.observes, [RECORD, RECORD])
        # Actual C21 handles idempotence/prefix semantics; this test only proves
        # exact delivery and never claims a fake core implemented its builder.

    def test_preimport_source_checks_finite_and_ordered_without_core_import(self):
        events = []
        real_pin, real_import = p._source_pin, p._import_at
        def pin(path, sha):
            events.append(('pin', path.name))
            return real_pin(path, sha)
        def imported(name, path):
            events.append(('import', path.name))
            return real_import(name, path)
        with patch.object(p, '_source_pin', side_effect=pin), patch.object(p, '_import_at', side_effect=imported):
            parser = p._load_parser()
        self.assertEqual(events[:2], [('pin', 'runner.py'), ('pin', 'curve_input.py')])
        self.assertTrue(all(event[0] == 'import' for event in events[2:]))
        observation = parser[1](parser[0](RECORD))
        self.assertEqual(observation.binding.run_id, 'C-FORCE-CPU-20261024-v1')
        # Production constructor gate is exercised only up to failed pin. It
        # must not import/construct the real core after a mismatching source.
        with patch.object(p, '_source_pin', side_effect=w.ProtocolError('source_pin_failed')) as pin_mock, patch.object(p, '_import_at') as imp:
            with self.assertRaises(w.ProtocolError):
                p._new_core()
            self.assertEqual(pin_mock.call_args.args[1], p.STREAM_CORE_SHA256)
            imp.assert_not_called()
        sizes = []
        class ReadProbe:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, size):
                sizes.append(size)
                return b'wrong source'
        with patch.object(Path, 'open', return_value=ReadProbe()):
            with self.assertRaises(w.ProtocolError):
                real_pin(Path('private-probe'), '0'*64)
        self.assertEqual(sizes, [2*1024*1024+1])

    def test_parser_source_failure_no_constructor_and_no_wire_output(self):
        io = MemoryIO(frame())
        with patch.object(p, '_source_pin', side_effect=OSError('private file failure')):
            result, core, count, _ = self.run_fake(io)
        self.assertEqual((result.exit_code, count, len(core.starts), len(io.writes)), (1, 0, 0, 0))


if __name__ == '__main__':
    unittest.main(verbosity=2)

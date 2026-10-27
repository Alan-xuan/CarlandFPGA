"""Pure C22 byte controls; recorded result bytes, NO endpoint/model execution."""
from dataclasses import asdict, FrozenInstanceError
import hashlib
import json
from pathlib import Path
import struct
import unittest

from ai_pc.cpu_package import endpoint_protocol as w

FIXTURES = Path(__file__).resolve().parents[3] / 'evidence/ai/cpu_endpoint_20261027/author/fixtures'


def identity(invocation=1, **changes):
    values = dict(operation_id='A-C22-DIAGNOSTIC', request_hash='1' * 64,
                  tested_commit='b898e90c7248dec5a6dd0ee850c8a07e097e83aa',
                  package_manifest_sha256='2' * 64, run_id='A-envelope-run',
                  invocation_id=invocation, actor_instance_id='A-actor:source-review')
    values.update(changes)
    return w.InvocationIdentity(**values)


def custom_frame(meta, payload=b'x', kind=w.OBSERVE):
    if type(meta) is dict:
        meta = json.dumps(meta, separators=(',', ':')).encode()
    return w.HEADER.pack(w.MAGIC, 1, kind, 0, len(meta), len(payload)) + meta + payload


def metadata(payload=b'x', index=1):
    return dict(identity=asdict(identity()), frame_index=index,
                payload_sha256=hashlib.sha256(payload).hexdigest())


def split_response(raw):
    magic, version, kind, flags, m, p = w.HEADER.unpack(raw[:16])
    assert (magic, version, flags) == (b'C22E', 1, 0)
    assert len(raw) == 16 + m + p
    return kind, json.loads(raw[16:16+m]), raw[16+m:]


class EndpointProtocolTests(unittest.TestCase):
    def test_recorded_A2007_and_original354_are_opaque_exact_bytes(self):
        record = (FIXTURES / 'original-first-record.jsonl').read_bytes()
        encoded = (FIXTURES / 'A-C21-first-result.exact.json').read_bytes()
        self.assertEqual((len(record), len(encoded)), (354, 2007))
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), '3cbffc7619558619bde6f1b25e53f3cb7225855b79aea45417e2fcf33cd4034b')
        self.assertEqual(hashlib.sha256(record).hexdigest(), '9c9200453ca7feab036ee9e41b9b78f9b61df5d672792961379d5daa920d1eb8')
        request = w.decode_request(w.encode_request(identity(), 1, record))
        response = w.encode_response(request, encoded)
        kind, meta, payload = split_response(response)
        self.assertEqual(kind, w.RESULT)
        self.assertEqual(payload, encoded)
        self.assertTrue(payload.endswith(b'\n'))
        self.assertEqual(meta.keys(), {'identity', 'frame_index', 'request_frame_sha256', 'request_payload_sha256', 'payload_sha256'})
        self.assertEqual(meta['identity'], asdict(identity()))
        self.assertEqual(meta['request_frame_sha256'], hashlib.sha256(request.raw).hexdigest())
        self.assertEqual(meta['request_payload_sha256'], hashlib.sha256(record).hexdigest())
        self.assertEqual(meta['payload_sha256'], hashlib.sha256(encoded).hexdigest())
        self.assertNotEqual(meta['request_frame_sha256'], meta['identity']['request_hash'])
        self.assertLessEqual(len(response), 6160)

    def test_original_metadata_serialization_and_LF_hash_are_retained(self):
        payload = b'  original \n'
        meta = json.dumps(metadata(payload), indent=1).encode()
        raw = custom_frame(meta, payload)
        request = w.decode_request(raw)
        canonical = w.encode_request(identity(), 1, payload)
        self.assertNotEqual(raw, canonical)
        self.assertNotEqual(request.frame_sha256, hashlib.sha256(canonical).hexdigest())
        self.assertEqual(request.raw, raw)
        self.assertEqual(request.payload, payload)
        self.assertNotEqual(request.payload_sha256, hashlib.sha256(payload.rstrip()).hexdigest())
        with self.assertRaises(FrozenInstanceError):
            request.identity.run_id = 'other'
        with self.assertRaises(FrozenInstanceError):
            request.payload = b'other'

    def test_header_exact_struct_and_all_length_boundaries(self):
        self.assertEqual(w.HEADER.size, 16)
        meta = json.dumps(metadata(b'x'), separators=(',', ':')).encode()
        for payload_size in (1, 16384 - 16 - 2048):
            payload = b'x' * payload_size
            doc = json.dumps(metadata(payload), separators=(',', ':')).encode()
            doc += b' ' * (2048 - len(doc))
            raw = custom_frame(doc, payload)
            self.assertEqual(w.decode_request(raw).payload, payload)
            if payload_size > 1:
                self.assertEqual(len(raw), 16384)
        invalid = [w.HEADER.pack(b'NOPE', 1, 1, 0, len(meta), 1),
                   w.HEADER.pack(w.MAGIC, 2, 1, 0, len(meta), 1),
                   w.HEADER.pack(w.MAGIC, 1, 1, 1, len(meta), 1),
                   w.HEADER.pack(w.MAGIC, 1, 129, 0, len(meta), 1),
                   w.HEADER.pack(w.MAGIC, 1, 1, 0, 0, 1),
                   w.HEADER.pack(w.MAGIC, 1, 1, 0, 2049, 1),
                   w.HEADER.pack(w.MAGIC, 1, 1, 0, 2048, 14321),
                   w.HEADER.pack(w.MAGIC, 1, 1, 0, len(meta), 0),
                   w.HEADER.pack(w.MAGIC, 1, 2, 0, len(meta), 1)]
        for header in invalid:
            with self.subTest(header=header.hex()), self.assertRaises(w.ProtocolError):
                w.request_lengths(header)
        good = w.encode_request(identity(), 1, b'x')
        for raw in (good[:-1], good+b'x', b'', bytearray(good)):
            with self.assertRaises(w.ProtocolError):
                w.decode_request(raw)

    def test_strict_metadata_schema_duplicate_nonfinite_UTF8_and_hash(self):
        good = metadata()
        variants = []
        for field in ('identity', 'frame_index', 'payload_sha256'):
            changed = dict(good)
            del changed[field]
            variants.append(changed)
        variants += [dict(good, extra=1), dict(good, frame_index=True),
                     dict(good, frame_index=0), dict(good, frame_index=65537),
                     dict(good, frame_index=1.0), dict(good, payload_sha256='A'*64),
                     dict(good, payload_sha256='0'*64), dict(good, identity={}), []]
        variants += [b'\xff', b'{"a":1,"a":2}', b'{"identity":NaN}',
                     b'['*1001+b']'*1001,
                     json.dumps(good).encode().replace(b'"frame_index": 1', b'"frame_index":1,"frame_index":1')]
        for meta in variants:
            if type(meta) is list:
                meta = b'[]'
            with self.subTest(case=str(meta)[:60]), self.assertRaises(w.ProtocolError):
                w.decode_request(custom_frame(meta))
        for nested in (dict(asdict(identity()), extra=1), dict(asdict(identity()), invocation_id=True)):
            with self.assertRaises(w.ProtocolError):
                w.decode_request(custom_frame(dict(good, identity=nested)))

    def test_identity_exact_A_types_bounds_and_detachment(self):
        for field, value in [('operation_id', ''), ('operation_id', 'a'*193), ('run_id', 'a b'),
                             ('actor_instance_id', '\u00e9'), ('tested_commit', 'a'*64),
                             ('request_hash', 'A'*64), ('package_manifest_sha256', None),
                             ('invocation_id', True), ('invocation_id', 0),
                             ('invocation_id', 1<<63), ('invocation_id', 1.0)]:
            with self.subTest(field=field, value=str(value)[:20]), self.assertRaises(w.ProtocolError):
                identity(**{field: value})
        class SneakyInt(int):
            pass
        class SneakyBytes(bytes):
            def __len__(self):
                return 1
        with self.assertRaises(w.ProtocolError):
            identity(invocation_id=SneakyInt(1))
        with self.assertRaises(w.ProtocolError):
            w.decode_request(SneakyBytes(b'x'*20000))
        self.assertEqual(identity((1<<63)-1).invocation_id, (1<<63)-1)

    def test_reply_payload4096_includes_LF_and_END_has_empty_input(self):
        request = w.decode_request(w.encode_request(identity(), 1, b'x'))
        payload = b'x'*4095 + b'\n'
        self.assertEqual(split_response(w.encode_response(request, payload))[2], payload)
        for bad in (b'x'*4096+b'\n', b'x'*4096, b'', bytearray(b'x\n')):
            with self.assertRaises(w.ProtocolError):
                w.encode_response(request, bad)
        end = w.decode_request(w.encode_request(identity(2), 2, b'', kind=w.END))
        self.assertEqual(end.payload_sha256, hashlib.sha256(b'').hexdigest())
        self.assertEqual(split_response(w.encode_response(end, b'original end\n'))[0], w.ENDED)


if __name__ == '__main__':
    unittest.main(verbosity=2)

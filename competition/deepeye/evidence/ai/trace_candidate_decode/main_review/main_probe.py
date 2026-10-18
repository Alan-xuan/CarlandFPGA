import argparse,binascii,hashlib,importlib.util,json,sys,unittest
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);a,rest=p.parse_known_args();sys.argv=[sys.argv[0],*rest]
spec=importlib.util.spec_from_file_location("C_candidate_subject",a.candidate);C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
WIRE=bytes.fromhex("a55a030717020900e803000001080401100403020107000000e803000000000000d204fe62")
BIND={"session":16909060,"config_epoch":2,"e":0}
def frame(seq=9,index=7,tick=1000,epoch=2):
 b=bytearray(WIRE);b[5]=epoch;b[6:8]=seq.to_bytes(2,"little");b[8:12]=(tick&0xffffffff).to_bytes(4,"little");b[21:25]=index.to_bytes(4,"little");b[25:33]=tick.to_bytes(8,"little");b[-2:]=binascii.crc_hqx(b[2:-2],0xffff).to_bytes(2,"little");return bytes(b)
class MainReview(unittest.TestCase):
 def test_known_manual_bytes_and_independent_CRC_primitive(self):
  self.assertEqual(C.crc16(b"123456789"),0x29b1);self.assertEqual(C.crc16(WIRE[2:-2]),binascii.crc_hqx(WIRE[2:-2],0xffff));r=C.decode_frame(WIRE,BIND);self.assertEqual(r["points"],[dict(index=7,tick_ms=1000,value=1234,valid=True,saturated=False,held=False,source_fault=False,source_tick_ms=1000)]);self.assertEqual(r["byte_ledger"]["line_bits_8n1"],370)
 def test_every_single_wire_bit_corruption_rejects_without_statechange(self):
  receiver=C.CandidateReceiver(BIND);receiver.accept(WIRE);before=receiver.state_snapshot()
  for byte in range(len(WIRE)):
   for bit in range(8):
    changed=bytearray(WIRE);changed[byte]^=1<<bit
    with self.subTest(byte=byte,bit=bit):
     with self.assertRaises(C.Reject):receiver.accept(bytes(changed))
     self.assertEqual(receiver.state_snapshot(),before)
 def test_replay_eviction_and_seq_wrap_fail_closed(self):
  receiver=C.CandidateReceiver(BIND)
  for i in range(17):self.assertEqual(receiver.accept(frame(seq=9+i,index=7+i,tick=1000+i))["status"],"accepted")
  before=receiver.state_snapshot();self.assertEqual(len(before["cache"]),16)
  with self.assertRaises(C.Reject):receiver.accept(WIRE)
  self.assertEqual(receiver.state_snapshot(),before);self.assertEqual(receiver.accept(frame(seq=25,index=23,tick=1016))["status"],"duplicate");self.assertEqual(receiver.state_snapshot(),before)
  receiver=C.CandidateReceiver(BIND);receiver.accept(frame(seq=65535));before=receiver.state_snapshot()
  with self.assertRaises(C.Reject):receiver.accept(frame(seq=0,index=8,tick=1001))
  self.assertEqual(receiver.state_snapshot(),before)
 def test_binding_return_aliases_and_terminal_retirement(self):
  original=dict(BIND);receiver=C.CandidateReceiver(original);original["session"]=0;r=receiver.accept(WIRE);r["points"][0]["index"]=2**32-1;detached=receiver.state_snapshot();detached["binding"]["session"]=0;detached["highwaters"][0]=(2**32-1,2**64-1);self.assertEqual(receiver.accept(frame(seq=10,index=8,tick=1001))["status"],"accepted");receiver.close();before=receiver.state_snapshot()
  with self.assertRaises(C.Reject):receiver.accept(frame(seq=11,index=9,tick=1002))
  self.assertEqual(receiver.state_snapshot(),before);new=C.CandidateReceiver(dict(BIND,config_epoch=3))
  with self.assertRaises(C.Reject):new.accept(WIRE)
  self.assertEqual(new.accept(frame(epoch=3))["status"],"accepted")
if __name__=="__main__":
 print("source_sha256="+hashlib.sha256(a.candidate.read_bytes()).hexdigest(),flush=True);unittest.main(verbosity=2)

import argparse,io,importlib.util,sys,unittest,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--product-root",type=Path,default=Path(__file__).resolve().parents[4]);args,rest=p.parse_known_args();root=args.product_root.resolve();sys.argv=[sys.argv[0],*rest]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
I=load("independent_inventory",root/"data/force_inventory.py");F=load("independent_fit",root/"data/force_preprocess.py")
header="~Version\nVERS. 2.0:\nWRAP. NO:\n~Well\nWELL. Independent:\nUWI. 1/1-1:\nNULL. -999.25:\n~Curve\nDEPT.M:\nGR.API:\nRHOB.G/CM3:\nNPHI.V/V:\nRDEP.OHMM:\n~Ascii\n"
row="0 -999.25 2 .1 1\n"
def inventory(b): return I.inventory_las_member(io.BytesIO(b),"independent.las",len(b),chunk_bytes=3)
def fit(b):
 c={name:F._ChannelFit(name) for name in F.CHANNELS};return F._fit_member(io.BytesIO(b),"independent.las",3,c),c
class Review(unittest.TestCase):
 def test_baseline_null_semantics_and_identical_early_duplicate(self):
  for h in (header,header.replace("UWI. 1/1-1:","UWI. 1/1-1:\nUWI. 1/1-1:")):
   b=(h+row+"1 10 3 .2 10\n").encode();self.assertEqual(inventory(b)["uwi"],"1/1-1");record,c=fit(b);self.assertEqual(record["uwi"],"1/1-1");self.assertEqual(c["GR"].counts["null"],1);self.assertEqual(c["GR"].mean,10)
 def test_independent_conflicting_and_late_headers_in_both_parsers(self):
  samples={"conflicting-UWI":header.replace("UWI. 1/1-1:","UWI. 1/1-1:\nUWI. 9/9-9:")+row,"late-UWI":header+row+"~Well\nWELL. Independent:\nUWI. 9/9-9:\n","late-NULL-new-row":header+row+"~Well\nNULL. -123:\n~Ascii\n1 -123 3 .2 10\n","same-UWI-after-empty-ASCII":header+"~Well\nWELL. Independent:\nUWI. 1/1-1:\n~Ascii\n"+row}
  for name,text in samples.items():
   for parse,error in ((inventory,I.LasInventoryError),(fit,F.ForcePreprocessError)):
    with self.subTest(sample=name,parser=parse.__name__):
     with self.assertRaises(error) as caught:parse(text.encode())
     self.assertRegex(str(caught.exception),"conflicting duplicate|header after ASCII data section")
if __name__=="__main__":
 for name in ("force_inventory.py","force_preprocess.py"):print(name,hashlib.sha256((root/"data"/name).read_bytes()).hexdigest(),flush=True)
 unittest.main(verbosity=2)

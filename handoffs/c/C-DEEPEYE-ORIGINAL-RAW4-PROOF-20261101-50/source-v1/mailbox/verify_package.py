"""Stdlib-only archive/byte verifier. Never imports packaged product/test code."""
import hashlib,io,json,re,sys,zipfile
from pathlib import PurePosixPath
MAX_BYTES=4*1024*1024
MAX_FILES=512
PATTERNS=[re.compile(r'[A-Za-z]:[\\/]Users[\\/]',re.I),
          re.compile(r'\.codex[\\/]sessions',re.I),
          re.compile(r'01a[0-9a-f]{5}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',re.I),
          re.compile('xilinx'+'@',re.I),re.compile('fe80'+'::[0-9a-f:%]+',re.I)]
def check(ok,message):
 if not ok:raise ValueError(message)
def digest(b):return hashlib.sha256(b).hexdigest()
def walk(data,depth=0):
 check(depth<=3,'nested archive depth')
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  infos=z.infolist();names=[x.filename for x in infos]
  check(len(infos)<=MAX_FILES and len(names)==len(set(names)),'entry count/duplicates')
  check(sum(x.file_size for x in infos)<=MAX_BYTES,'expanded bytes limit')
  total=0;nested=0
  for item in infos:
   p=PurePosixPath(item.filename)
   check(not p.is_absolute() and '..' not in p.parts and '\\' not in item.filename and ':' not in item.filename,'unsafe archive path')
   check(not item.is_dir() and (item.external_attr>>16)&0o170000 != 0o120000,'directories/symlinks not accepted')
   b=z.read(item);check(len(b)==item.file_size,'entry length');total+=len(b)
   text=b.decode('utf-8',errors='replace')
   check(not any(q.search(text) for q in PATTERNS),'private host/session pattern: '+item.filename)
   if zipfile.is_zipfile(io.BytesIO(b)):
    walk(b,depth+1);nested+=1
  check('MANIFEST.json' in names,'manifest missing')
  m=json.loads(z.read('MANIFEST.json'));rows=m['files']
  check(type(rows) is list,'manifest file list')
  expected={r['path']:r for r in rows}
  check(len(expected)==len(rows) and set(expected)==set(names)-{'MANIFEST.json'},'manifest exact membership')
  for name,r in expected.items():
   b=z.read(name)
   check(type(r['bytes']) is int and len(b)==r['bytes'] and digest(b)==r['sha256'],'hash/length: '+name)
  return dict(files=len(names),expanded_bytes=total,nested_archives=nested)
if __name__=='__main__':
 check(len(sys.argv)==2,'usage: verify_package.py package.zip')
 with open(sys.argv[1],'rb') as f:data=f.read(MAX_BYTES+1)
 check(len(data)<=MAX_BYTES,'compressed bytes limit')
 print(json.dumps(dict(status='PACKAGING_INTEGRITY_PASS',archive_sha256=digest(data),**walk(data),product_tests_executed=False,source_imported=False,approval='PENDING')))

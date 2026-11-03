"""Read-only interpreter/stdlib identity probe, no product or leaf import."""
import argparse,ctypes,ctypes.wintypes,hashlib,json,os,pathlib,re,secrets,struct,sys,threading,subprocess
import encodings.utf_16_le
base=pathlib.Path(sys.base_prefix).resolve()
files={}
def add(path,reason):
    p=pathlib.Path(path).resolve()
    if p.suffix=='.pyc':p=pathlib.Path(__import__('importlib.util',fromlist=['source_from_cache']).source_from_cache(str(p)))
    rel=p.relative_to(base).as_posix()
    b=p.read_bytes();files[rel]=dict(origin='base_prefix',path=rel,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),reason=reason)
for name,module in list(sys.modules.items()):
    filename=getattr(module,'__file__',None)
    if filename and pathlib.Path(filename).resolve().is_relative_to(base):add(filename,'actual loaded stdlib module '+name)
for rel in ('python.exe','python312.dll','python3.dll','vcruntime140.dll','vcruntime140_1.dll','DLLs/libffi-8.dll','DLLs/_ctypes.pyd','DLLs/_hashlib.pyd','DLLs/libcrypto-3-x64.dll'):
    add(base/rel,'explicit binary dependency')
print(json.dumps(dict(executable=str(pathlib.Path(sys.executable).resolve()),prefix=str(pathlib.Path(sys.prefix).resolve()),base_prefix=str(base),version=sys.version,version_info=list(sys.version_info),pointer_bits=struct.calcsize('P')*8,windows_version=list(sys.getwindowsversion()),flags=dict(isolated=sys.flags.isolated,no_site=sys.flags.no_site,dont_write_bytecode=sys.flags.dont_write_bytecode,ignore_environment=sys.flags.ignore_environment),dependencies=[files[k] for k in sorted(files)],probe='actual local stdlib imports only; no layout helper/leaf/launcher execution; no third party packages',provenance='Existing local Codex bundled runtime, not A private venv and not inherited A qualification'),indent=2))

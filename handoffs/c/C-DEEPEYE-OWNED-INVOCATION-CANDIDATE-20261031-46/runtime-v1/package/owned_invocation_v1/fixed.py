"""Fixed C36/C44 loading, no caller-selected module, verifier or code path."""
import hashlib,importlib.util,sys
from pathlib import Path
_BASE=Path(__file__).resolve().parent/'fixed'
def _load(name,path,pin):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ImportError('fixed C46 dependency changed')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
projection=_load('_c46_fixed_c36',_BASE/'c36/host_projection.py','7defaee9318f9a33a0586628661d054c028b5952584030ebc3b771a479a8982e')
verifier=_load('_c46_fixed_c44',_BASE/'c44_pair_verifier_v1.py','af7ea20a3ee80f1266d66062698db4c5b1f8a9835262cc2ccfc7f480f6260ea6')

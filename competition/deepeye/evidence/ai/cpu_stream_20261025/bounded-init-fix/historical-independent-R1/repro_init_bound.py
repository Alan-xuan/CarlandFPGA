"""Independent offline negative control: no large files, no Torch/model execution."""
import json, sys, unittest
from pathlib import Path
from unittest.mock import patch

WT = Path(r"C:\Users\Alan\Documents\ChatGPT\FPGA\CarlandFPGA-node-c\.local\deepeye-implementation-c")
sys.path.insert(0, str(WT / "competition/deepeye"))
from ai_pc.cpu_package import stream_core as m

class ConstructorReadBound(unittest.TestCase):
    def test_constructor_asset_preflight_is_size_bounded(self):
        calls = []
        original_open = Path.open
        source_path = Path(m._runner.__file__).resolve()

        class Trap:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size=-1):
                calls.append({"path": str(source_path), "read_size": size})
                print(json.dumps({"asset_read_call": calls[-1]}, sort_keys=True), flush=True)
                # Intentionally fails on the frozen source, without allocating
                # any oversized buffer or returning fake asset/model bytes.
                self_test.assertGreater(size, 0, "constructor preflight requested unbounded read before hash rejection")
                raise AssertionError("not expected to reach bounded continuation on original frozen source")

        self_test = self
        def guarded_open(path, *args, **kwargs):
            if Path(path).resolve() == source_path:
                return Trap()
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", guarded_open):
            m.FrozenForceStream()

if __name__ == "__main__":
    unittest.main(verbosity=2)


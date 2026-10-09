"""Small upload payload for verifying the PYNQ runtime on a real board."""

import json
import platform
import socket
import sys
from pathlib import Path

import pynq


overlays = Path(pynq.__file__).resolve().parent / "overlays" / "base"
report = {
    "hostname": socket.gethostname(),
    "kernel": platform.release(),
    "machine": platform.machine(),
    "python": sys.version.split()[0],
    "pynq_version": pynq.__version__,
    "pynq_package": str(Path(pynq.__file__).resolve()),
    "base_bit_present": (overlays / "base.bit").is_file(),
    "base_hwh_present": (overlays / "base.hwh").is_file(),
}
print("CARLANDFPGA_BOARD_PROBE=" + json.dumps(report, sort_keys=True), flush=True)

"""Portable offline FORCE CPU/explicit-HIP package entrypoint.

This entrypoint does not connect to an A process, controller, world or board.
"""

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_pc.cpu_package.runner import main


if __name__ == "__main__":
    raise SystemExit(main())

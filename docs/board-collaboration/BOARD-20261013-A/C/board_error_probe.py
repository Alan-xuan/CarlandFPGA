"""Emit the public v3 board-feedback identity, then fail as requested.

``PUBLIC_NONCE`` is intentionally stable for this exact operation so node A can
match its board transcript to the immutable handoff manifest.  It is public and
contains no credential, device identifier, or private board data.
"""

from __future__ import annotations

import sys


OPERATION_ID = "BOARD-20261013-A:C:error-feedback-v3"
PUBLIC_NONCE = "BOARD-20261013-A-C-V3-PUBLIC-NONCE-001"
EXPECTED_ERROR = "EXPECTED_C_BOARD_FEEDBACK_BOARD-20261013-A"


def _runtime() -> str:
    version = sys.version_info
    implementation = "CPython" if sys.implementation.name == "cpython" else sys.implementation.name
    return f"{implementation} {version.major}.{version.minor}.{version.micro};sys.platform={sys.platform}"


def main() -> None:
    print(f"operation_id={OPERATION_ID}", flush=True)
    print(f"public_nonce={PUBLIC_NONCE}", flush=True)
    print(f"runtime={_runtime()}", flush=True)
    raise RuntimeError(EXPECTED_ERROR)


if __name__ == "__main__":
    main()

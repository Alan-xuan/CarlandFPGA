"""Emit a correlation record, then deliberately fail for A's board feedback.

Standard library only. Does not load an overlay or access any peripheral.
"""
import argparse
import json
import platform
import sys


OPERATION_ID = "BOARD-20261013-A:C:error-feedback-v3"
ERROR_MARKER = "EXPECTED_C_BOARD_FEEDBACK_BOARD-20261013-A"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nonce", required=True, help="A's unique run correlation value")
    args = parser.parse_args()
    if not args.nonce.strip():
        parser.error("--nonce must be nonempty")
    print(json.dumps({
        "operation_id": OPERATION_ID,
        "task_id": "BOARD-20261013-A-C",
        "task_version": 3,
        "nonce": args.nonce,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "sys_platform": sys.platform,
            "machine": platform.machine(),
        },
        "purpose": "controlled_error_feedback",
        "peripheral_access": False,
    }, sort_keys=True), flush=True)
    raise RuntimeError(ERROR_MARKER)


if __name__ == "__main__":
    main()

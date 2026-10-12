#!/usr/bin/env python3
"""Bounded offline fixture validator (Python standard library only).

Validates a saved JSON object fixture against the small handoff schema:

    task_id      : nonempty string
    task_version : strict positive integer, >= 1 (bool is not accepted,
                   even though Python bool is a subclass of int)
    owner        : exactly "C/Astra-C"
    direction    : exactly "A->C"

Any other fields are allowed and ignored. This is a bounded local fixture
check only; it is NOT production Envelope authentication/authorization and
must not be used to authorize real work. It performs no network, board or
credential access.

Usage:
    python validator.py FILE

Exit codes:
    0 - fixture accepted (summary on stdout)
    1 - fixture rejected (clear reason on stderr)
    2 - usage error (FILE argument missing or extra arguments)
"""

import json
import sys

OWNER_EXPECTED = "C/Astra-C"
DIRECTION_EXPECTED = "A->C"

EXIT_ACCEPT = 0
EXIT_REJECT = 1
EXIT_USAGE = 2


def validate_fixture(obj):
    """Validate a decoded JSON value. Returns (ok, reason)."""
    if not isinstance(obj, dict):
        return False, "fixture root must be a JSON object, got %s" % type(obj).__name__

    if "task_id" not in obj:
        return False, "missing required field 'task_id'"
    task_id = obj["task_id"]
    if not isinstance(task_id, str):
        return False, "field 'task_id' must be a string, got %s" % type(task_id).__name__
    if not task_id.strip():
        return False, "field 'task_id' must be a nonempty string"

    if "task_version" not in obj:
        return False, "missing required field 'task_version'"
    version = obj["task_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        return False, (
            "field 'task_version' must be an integer (bool is not accepted), got %s"
            % type(version).__name__
        )
    if version <= 0:
        return False, "field 'task_version' must be a positive integer (>= 1), got %d" % version

    if "owner" not in obj:
        return False, "missing required field 'owner'"
    if obj["owner"] != OWNER_EXPECTED:
        return False, "field 'owner' must be exactly %r, got %r" % (OWNER_EXPECTED, obj["owner"])

    if "direction" not in obj:
        return False, "missing required field 'direction'"
    if obj["direction"] != DIRECTION_EXPECTED:
        return False, "field 'direction' must be exactly %r, got %r" % (
            DIRECTION_EXPECTED,
            obj["direction"],
        )

    return True, "accepted: task_id=%r task_version=%d owner=%r direction=%r" % (
        task_id,
        version,
        obj["owner"],
        obj["direction"],
    )


def validate_file(path):
    """Load and validate a JSON file. Returns (ok, reason)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            obj = json.load(handle)
    except FileNotFoundError:
        return False, "file not found: %s" % path
    except IsADirectoryError:
        return False, "expected a file, got a directory: %s" % path
    except UnicodeDecodeError as exc:
        return False, "file is not valid UTF-8: %s" % exc
    except json.JSONDecodeError as exc:
        return False, "malformed JSON: %s" % exc
    except OSError as exc:
        return False, "could not read file: %s" % exc
    return validate_fixture(obj)


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: python validator.py FILE\n")
        return EXIT_USAGE
    path = argv[1]
    ok, reason = validate_file(path)
    if ok:
        sys.stdout.write("ACCEPT: %s: %s\n" % (path, reason))
        return EXIT_ACCEPT
    sys.stderr.write("REJECT: %s: %s\n" % (path, reason))
    return EXIT_REJECT


if __name__ == "__main__":
    sys.exit(main(sys.argv))

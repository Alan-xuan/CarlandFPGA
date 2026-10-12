#!/usr/bin/env python3
"""Capture runner for the bounded fixture validator (standard library only).

Runs the documented commands with this script's interpreter, writing the raw,
unmodified stdout and stderr of each command (one file per stream) into
captures/, plus captures/metadata.txt with the command line, interpreter
version and the actual exit codes. Output is never fabricated: every
captured byte comes from the subprocess run recorded in metadata.txt.
"""

import argparse
import datetime
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAPTURES = os.path.join(HERE, "captures")

COMMANDS = [
    ("01-unittest", [sys.executable, "-m", "unittest", "-v", "test_validator"]),
    ("02-cli-valid", [sys.executable, "validator.py", "fixtures/valid.json"]),
    ("03-cli-missing-version", [sys.executable, "validator.py", "fixtures/missing-version.json"]),
    ("04-cli-negative-version", [sys.executable, "validator.py", "fixtures/negative-version.json"]),
]

EXPECTED_EXIT = {
    "01-unittest": 0,
    "02-cli-valid": 0,
    "03-cli-missing-version": 1,
    "04-cli-negative-version": 1,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=CAPTURES,
                        help="new directory; existing evidence is never overwritten")
    args = parser.parse_args()
    captures = os.path.abspath(args.output_dir)
    os.makedirs(captures, exist_ok=False)
    version = subprocess.run(
        [sys.executable, "--version"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    lines = [
        "capture run (UTC): %s"
        % datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runner          : run_captures.py (in %s)" % HERE,
        "interpreter     : %s" % sys.executable,
        "python version  : %s" % version.stdout.strip(),
        "note            : raw, unedited subprocess stdout/stderr, one file per stream",
        "",
    ]

    exit_codes = {}
    for name, command in COMMANDS:
        proc = subprocess.run(
            command,
            cwd=HERE,
            capture_output=True,
        )
        exit_codes[name] = proc.returncode
        with open(os.path.join(captures, name + ".stdout.txt"), "xb") as handle:
            handle.write(proc.stdout)
        with open(os.path.join(captures, name + ".stderr.txt"), "xb") as handle:
            handle.write(proc.stderr)
        lines.extend(
            [
                "%s:" % name,
                "  command   : %s" % " ".join(command),
                "  cwd       : %s" % HERE,
                "  exit code : %d (expected %d)" % (proc.returncode, EXPECTED_EXIT[name]),
                "  stdout    : %s.stdout.txt" % name,
                "  stderr    : %s.stderr.txt" % name,
                "",
            ]
        )

    with open(os.path.join(captures, "metadata.txt"), "x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))

    all_expected = True
    for name, command in COMMANDS:
        match = exit_codes[name] == EXPECTED_EXIT[name]
        all_expected = all_expected and match
        print("%s: exit %d (%s)" % (name, exit_codes[name], "OK" if match else "UNEXPECTED"))
    print("captures written to %s" % captures)
    return 0 if all_expected else 1


if __name__ == "__main__":
    sys.exit(main())

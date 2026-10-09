"""Bootstrap a directly attached PYNQ-Z2, upload a Python file, and record its output.

The first run needs a logged-in serial shell and pyserial. Subsequent runs may
use --host and --ifindex with the previously installed SSH key. The board's
SSH host key is read over the physical serial connection and pinned locally.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
HOST_ALIAS = "pynq-z2-local"
PYNQ_PYTHON = "/usr/local/share/pynq-venv/bin/python3"


def _console_lines(raw: bytes) -> list[str]:
    decoded = ANSI_ESCAPE.sub("", raw.decode("utf-8", "replace"))
    return decoded.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n").splitlines()


def parse_serial_result(raw: bytes, token: str) -> tuple[int, str]:
    """Use executed marker lines, not the echoed command that also names them."""
    begin = f"__CFL_BEGIN_{token}__"
    end = re.compile(rf"^__CFL_END_{re.escape(token)}__:(\d+)$")
    lines = _console_lines(raw)
    try:
        start = lines.index(begin)
    except ValueError as exc:
        raise ValueError("serial shell did not print a begin marker") from exc
    for index in range(start + 1, len(lines)):
        match = end.fullmatch(lines[index])
        if match:
            return int(match.group(1)), "\n".join(lines[start + 1:index]).strip()
    raise ValueError("serial shell did not print an executed end marker")


def parse_link_local(output: str) -> str:
    for candidate in re.findall(r"\b(fe80:[0-9a-fA-F:]+)/\d+\s+scope\s+link\b", output):
        address = ipaddress.IPv6Address(candidate)
        if address.is_link_local:
            return str(address)
    raise ValueError("board eth0 has no IPv6 link-local address")


def verify_remote_hash(data: bytes, sha256sum_output: str) -> str:
    expected = hashlib.sha256(data).hexdigest()
    match = re.match(r"^([0-9a-fA-F]{64})\s+", sha256sum_output.strip())
    if not match or match.group(1).lower() != expected:
        raise ValueError("remote SHA-256 mismatch; uploaded file will not run")
    return expected


def discover_serial_port(explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError("pyserial is required for first-run serial bootstrap") from exc
    candidates = [
        port.device for port in list_ports.comports()
        if port.vid == 0x0403 and port.pid == 0x6010
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one PYNQ FTDI serial port, found {candidates}; pass --serial")
    return candidates[0]


def serial_command(port: str, command: str, timeout: float = 15.0) -> str:
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial is required for first-run serial bootstrap") from exc
    token = uuid.uuid4().hex[:12]
    begin = f"__CFL_BEGIN_{token}__"
    end = f"__CFL_END_{token}__"
    wrapped = (
        f"printf '%s\\n' '{begin}'; {command}; "
        f"rc=$?; printf '%s:%s\\n' '{end}' \"$rc\"\n"
    )
    output = bytearray()
    with serial.Serial(port, 115200, timeout=0.3, write_timeout=3) as console:
        console.reset_input_buffer()
        console.write(wrapped.encode("ascii"))
        console.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            output.extend(console.read(4096))
            try:
                status, result = parse_serial_result(bytes(output), token)
            except ValueError:
                continue
            if status:
                raise RuntimeError(f"board serial command failed ({status}): {result[-1200:]}")
            return result
    tail = "\n".join(_console_lines(bytes(output))[-8:])
    raise TimeoutError(f"board serial shell did not finish; log in on {port} if prompted: {tail}")


def _host_key_from_serial(port: str) -> tuple[str, str]:
    output = serial_command(port, "cat /etc/ssh/ssh_host_ed25519_key.pub")
    match = re.search(r"(?m)^(ssh-ed25519)\s+([A-Za-z0-9+/=]+)(?:\s+.*)?$", output)
    if not match:
        raise ValueError("board did not return its ED25519 SSH host public key")
    return match.group(1), match.group(2)


def _client_key(path: Path) -> Path:
    public = Path(str(path) + ".pub")
    if path.exists() != public.exists():
        raise RuntimeError("incomplete PYNQ SSH key pair; inspect the .ssh directory")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        keygen = shutil.which("ssh-keygen")
        if not keygen:
            raise RuntimeError("OpenSSH ssh-keygen is unavailable")
        subprocess.run(
            [keygen, "-q", "-t", "ed25519", "-N", "", "-C", "CarlandFPGA-PYNQ-Z2", "-f", str(path)],
            check=True, capture_output=True, timeout=20,
        )
    return public


def _bootstrap_serial(port: str, key: Path, known_hosts: Path) -> str:
    kind, encoded = _host_key_from_serial(port)
    public = _client_key(key).read_text(encoding="ascii").strip()
    quoted = shlex.quote(public)
    command = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
        f"(grep -qxF -- {quoted} ~/.ssh/authorized_keys || "
        f"printf '%s\\n' {quoted} >> ~/.ssh/authorized_keys) && "
        "chmod 600 ~/.ssh/authorized_keys"
    )
    serial_command(port, command)
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    known_hosts.write_text(f"{HOST_ALIAS} {kind} {encoded}\n", encoding="ascii")
    address_output = serial_command(port, "ip -6 -o addr show dev eth0 scope link")
    return parse_link_local(address_output)


def discover_ifindex(address: str, explicit: int | None) -> int:
    indexes = [explicit] if explicit is not None else [index for index, _ in socket.if_nameindex()]
    for index in indexes:
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as connection:
                connection.settimeout(0.5)
                connection.connect((address, 22, 0, index))
            return index
        except OSError:
            continue
    raise ConnectionError("board SSH is not reachable on a local IPv6 interface")


def _ssh_base(key: Path, known_hosts: Path, address: str, ifindex: int) -> list[str]:
    ssh = shutil.which("ssh")
    if not ssh:
        raise RuntimeError("OpenSSH ssh is unavailable")
    return [
        ssh, "-6", "-T", "-i", str(key),
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", f"HostKeyAlias={HOST_ALIAS}",
        "-o", f"UserKnownHostsFile={known_hosts}", "-o", "ConnectTimeout=8",
        f"xilinx@{address}%{ifindex}",
    ]


def _ssh(base: list[str], command: str, *, data: bytes | None = None, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(base + [command], input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        error = result.stderr.decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"SSH command failed ({result.returncode}): {error}")
    return result


def _board_python(base: list[str], explicit: str) -> str:
    candidates = [explicit] if explicit != "auto" else [PYNQ_PYTHON, "python3"]
    for interpreter in candidates:
        command = shlex.quote(interpreter) + " -c 'import pynq' >/dev/null 2>&1"
        try:
            _ssh(base, command, timeout=60)
            return interpreter
        except RuntimeError:
            continue
    raise RuntimeError("PYNQ interpreter unavailable or unable to import pynq")


def execute_and_record(
    base: list[str], command: str, timeout: int, output_root: Path, metadata: dict,
) -> dict:
    """Save real output even when the SSH client times out and board state is unknown."""
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(base + [command], capture_output=True, timeout=timeout)
        stdout_bytes = completed.stdout
        stderr_bytes = completed.stderr
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout_bytes = exc.stdout or b""
        stderr_bytes = exc.stderr or b""
        exit_code = None
    if isinstance(stdout_bytes, str):
        stdout_bytes = stdout_bytes.encode("utf-8")
    if isinstance(stderr_bytes, str):
        stderr_bytes = stderr_bytes.encode("utf-8")
    elapsed = round(time.monotonic() - started, 3)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    output_dir = (output_root / stamp).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "stdout.log").write_bytes(stdout_bytes)
    (output_dir / "stderr.log").write_bytes(stderr_bytes)
    record = {
        **metadata,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "stdout_log": "stdout.log",
        "stderr_log": "stderr.log",
    }
    (output_dir / "result.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"evidence_dir": str(output_dir), **record}, ensure_ascii=False, indent=2))
    stdout = stdout_bytes.decode("utf-8", "replace")
    stderr = stderr_bytes.decode("utf-8", "replace")
    if stdout:
        print("BOARD_STDOUT_BEGIN\n" + stdout.rstrip() + "\nBOARD_STDOUT_END")
    if stderr:
        print("BOARD_STDERR_BEGIN\n" + stderr.rstrip() + "\nBOARD_STDERR_END", file=sys.stderr)
    if timed_out:
        raise RuntimeError(f"board execution timed out; state unknown; evidence saved in {output_dir}")
    if exit_code:
        raise RuntimeError(f"board script exited {exit_code}; evidence saved in {output_dir}")
    return record


def run(args: argparse.Namespace) -> dict:
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    script = args.script.resolve(strict=True)
    if not script.is_file():
        raise ValueError("--script must name a regular file")
    if not args.remote_dir.startswith("/") or ".." in args.remote_dir.split("/"):
        raise ValueError("--remote-dir must be an absolute path without '..'")
    key = args.ssh_key.expanduser()
    known_hosts = args.known_hosts.expanduser()
    if args.host:
        address = str(ipaddress.IPv6Address(args.host))
        if not ipaddress.IPv6Address(address).is_link_local:
            raise ValueError("--host must be an IPv6 link-local address")
        if not key.is_file() or not known_hosts.is_file():
            raise RuntimeError("SSH key and pinned host key are missing; run serial bootstrap first")
        port = None
    else:
        port = discover_serial_port(args.serial)
        address = _bootstrap_serial(port, key, known_hosts)
    ifindex = discover_ifindex(address, args.ifindex)
    base = _ssh_base(key, known_hosts, address, ifindex)
    remote = args.remote_dir.rstrip("/") + "/" + script.name
    _ssh(base, "mkdir -p -- " + shlex.quote(args.remote_dir))
    data = script.read_bytes()
    _ssh(base, "cat > " + shlex.quote(remote), data=data, timeout=max(30, args.timeout))
    remote_sum = _ssh(base, "sha256sum -- " + shlex.quote(remote)).stdout.decode("ascii", "replace")
    digest = verify_remote_hash(data, remote_sum)
    interpreter = _board_python(base, args.python)
    command = shlex.quote(interpreter) + " " + shlex.quote(remote)
    metadata = {
        "schema_version": 1,
        "serial_port": port,
        "board_ipv6": address,
        "host_ifindex": ifindex,
        "script": str(script),
        "remote_script": remote,
        "script_sha256": digest,
        "interpreter": interpreter,
    }
    return execute_and_record(base, command, args.timeout, args.output_dir, metadata)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload, verify, execute, and log a PYNQ-Z2 Python script")
    parser.add_argument("--serial", help="logged-in PYNQ FTDI serial port; auto-detected when omitted")
    parser.add_argument("--ifindex", type=int, help="Windows/Linux interface index for direct Ethernet")
    parser.add_argument("--host", help="known board IPv6 link-local address; skips serial bootstrap")
    parser.add_argument("--script", type=Path, default=Path(__file__).with_name("board_probe.py"))
    parser.add_argument("--remote-dir", default="/tmp/carlandfpga-board-run")
    parser.add_argument("--python", default="auto", help="board Python path; auto prefers the PYNQ venv")
    parser.add_argument("--ssh-key", type=Path, default=Path.home() / ".ssh/pynq_z2_ed25519")
    parser.add_argument("--known-hosts", type=Path, default=Path.home() / ".ssh/pynq_z2_known_hosts")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd() / "artifacts/pynq-z2-single-node/live")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        run(args)
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.TimeoutExpired) as exc:
        print(f"BOARD_RUN_FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

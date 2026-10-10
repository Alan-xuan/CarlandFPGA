"""Generate one node's local config without copying secrets into the repository."""

from __future__ import annotations

import argparse
import json
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path


def _q(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class OnboardingInputs:
    node: str
    deepseek_key_file: Path | None = None
    shared_secret_file: Path | None = None
    bind_host: str = "127.0.0.1"
    bind_port: int = 8787
    peer_urls: dict[str, str] = field(default_factory=dict)
    group_id: str = ""
    astra_app_id: str = ""
    astra_secret_file: Path | None = None
    deepseek_app_id: str = ""
    deepseek_secret_file: Path | None = None


def reuse_local_settings(path: Path, values: OnboardingInputs) -> OnboardingInputs:
    """Keep key paths and peer addresses on a repeat onboarding run."""
    path = Path(path)
    if not path.is_file():
        return replace(values, bind_host=values.bind_host or "127.0.0.1")
    data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("node_id") != values.node:
        raise ValueError("existing config belongs to another node")
    security = data.get("security", {})
    peers = {peer: url for peer, url in data.get("peers", {}).items() if url}
    peers.update(values.peer_urls)
    key = values.deepseek_key_file or data.get("deepseek_key_file")
    secret = values.shared_secret_file or security.get("secret_file")
    return replace(
        values,
        deepseek_key_file=Path(key) if key else None,
        shared_secret_file=Path(secret) if secret else None,
        bind_host=values.bind_host or security.get("bind_host") or "127.0.0.1",
        peer_urls=peers,
    )


def write_node_config(path: Path, values: OnboardingInputs) -> Path:
    if values.node not in {"A", "B", "C"}:
        raise ValueError("node must be A, B, or C")
    if not 0 <= values.bind_port <= 65535:
        raise ValueError("bind port must be valid")
    for peer, url in values.peer_urls.items():
        if peer not in {"A", "B", "C"} - {values.node}:
            raise ValueError(f"invalid peer node: {peer}")
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(f"invalid peer URL for {peer}")
    feishu_enabled = bool(
        values.group_id and values.astra_app_id and values.astra_secret_file
    )
    lines = [
        f"node_id = {_q(values.node)}",
        'project_id = "fpga-main"',
        f"state_dir = {_q(f'.local/node-{values.node.lower()}')}",
        'mode = "app_server"',
        "turn_timeout_seconds = 3600",
        f"deepseek_key_file = {_q(values.deepseek_key_file.resolve() if values.deepseek_key_file else '')}",
        "hardware_enabled = false",
        "", "[coordination]",
        'remote_url = "https://github.com/carolwjade/CarlandFPGA.git"',
        "",
        "[peers]",
    ]
    lines.extend(
        f"{peer} = {_q(values.peer_urls.get(peer, ''))}"
        for peer in sorted({"A", "B", "C"} - {values.node})
    )
    lines += [
        "", "[security]",
        'secret_env = "FPGA_MESH_SHARED_SECRET"',
        f"secret_file = {_q(values.shared_secret_file.resolve() if values.shared_secret_file else '')}",
        f"bind_host = {_q(values.bind_host)}",
        f"bind_port = {values.bind_port}",
        "retry_seconds = 15",
        "", "[feishu]",
        f"enabled = {'true' if feishu_enabled else 'false'}",
        f"group_id = {_q(values.group_id)}",
        f"astra_app_id = {_q(values.astra_app_id)}",
        f"astra_secret_file = {_q(values.astra_secret_file.resolve() if values.astra_secret_file else '')}",
        f"deepseek_app_id = {_q(values.deepseek_app_id)}",
        f"deepseek_secret_file = {_q(values.deepseek_secret_file.resolve() if values.deepseek_secret_file else '')}",
    ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write local A/B/C FPGA Mesh config")
    parser.add_argument("--node", choices="ABC", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deepseek-key-file", type=Path)
    parser.add_argument("--shared-secret-file", type=Path)
    parser.add_argument("--bind-host", default="")
    parser.add_argument("--bind-port", type=int, default=8787)
    for peer in "ABC":
        parser.add_argument(f"--peer-{peer.lower()}", default="")
    parser.add_argument("--group-id", default="")
    parser.add_argument("--astra-app-id", default="")
    parser.add_argument("--astra-secret-file", type=Path)
    parser.add_argument("--deepseek-app-id", default="")
    parser.add_argument("--deepseek-secret-file", type=Path)
    parser.add_argument("--reuse-existing", action="store_true")
    args = parser.parse_args()
    values = OnboardingInputs(
        node=args.node, deepseek_key_file=args.deepseek_key_file,
        shared_secret_file=args.shared_secret_file,
        bind_host=args.bind_host, bind_port=args.bind_port,
        peer_urls={peer: getattr(args, f"peer_{peer.lower()}") for peer in "ABC"
                   if peer != args.node and getattr(args, f"peer_{peer.lower()}")},
        group_id=args.group_id, astra_app_id=args.astra_app_id,
        astra_secret_file=args.astra_secret_file,
        deepseek_app_id=args.deepseek_app_id,
        deepseek_secret_file=args.deepseek_secret_file,
    )
    if args.reuse_existing:
        values = reuse_local_settings(args.output, values)
    elif not values.bind_host:
        values = replace(values, bind_host="127.0.0.1")
    print(write_node_config(args.output, values))


if __name__ == "__main__":
    main()

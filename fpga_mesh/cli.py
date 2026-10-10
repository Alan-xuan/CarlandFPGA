"""Command line entry points for deployment and local verification."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .app_server import AppServerClient
from .codex import CodexHomeFactory, CodexHomeSpec
from .controller import ActionResult, Controller
from .deepseek import DeepSeekBalanceClient
from .gateway import AppServerGateway, GatewayConfig
from .protocol import Envelope, MessageKind, SourceKind, task_id_from_message
from .store import SQLiteStore
from .testing import RecordingGateway
from .transport import LocalBus, LocalPeer


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _make_envelope(
    *,
    message_id: str,
    sender: str,
    recipient: str,
    task_id: str,
    kind: MessageKind,
    source: SourceKind,
    text: str,
) -> Envelope:
    return Envelope(
        message_id=message_id,
        project_id="fpga-main",
        sender=sender,
        recipient=recipient,
        task_id=task_id,
        task_version=1,
        sent_at=datetime.now(timezone.utc),
        kind=kind,
        source=source,
        payload={"text": text},
    )


async def simulate(root: Path, output: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    bus = LocalBus()
    stores: dict[str, SQLiteStore] = {}
    gateways: dict[str, RecordingGateway] = {}
    peers: dict[str, LocalPeer] = {}
    for node in ("A", "B", "C"):
        store = SQLiteStore(root / f"{node}.sqlite")
        gateway = RecordingGateway()
        controller = Controller(store, gateway)
        peer = LocalPeer(node, store, controller, bus)
        bus.register(peer)
        stores[node] = store
        gateways[node] = gateway
        peers[node] = peer

    human = _make_envelope(
        message_id="human-1",
        sender="human-1",
        recipient="A/Astra-A",
        task_id=task_id_from_message("group-1", "om_sim"),
        kind=MessageKind.HUMAN_INSTRUCTION,
        source=SourceKind.HUMAN,
        text="local simulation",
    )
    human = Envelope(
        **{
            **{
                "message_id": human.message_id,
                "project_id": human.project_id,
                "sender": human.sender,
                "recipient": human.recipient,
                "task_id": human.task_id,
                "task_version": human.task_version,
                "sent_at": human.sent_at,
                "kind": human.kind,
                "source": human.source,
                "payload": human.payload,
            },
            "platform_group_id": "group-1",
            "platform_message_id": "om_sim",
        }
    )
    await peers["A"].receive(human)
    await peers["A"].controller.run_until_idle()

    report = _make_envelope(
        message_id="A-to-B",
        sender="A/Astra-A",
        recipient="B/Astra-B",
        task_id=human.task_id,
        kind=MessageKind.AGENT_REPORT,
        source=SourceKind.ASTRA,
        text="A result",
    )
    await peers["A"].send("B", report)
    await peers["B"].controller.run_until_idle()

    # Exercise the offline queue before C is available.
    bus.unregister("C")
    offline_report = _make_envelope(
        message_id="B-to-C-offline",
        sender="B/Astra-B",
        recipient="C/Astra-C",
        task_id=human.task_id,
        kind=MessageKind.AGENT_REPORT,
        source=SourceKind.ASTRA,
        text="B result",
    )
    offline_queued = not await peers["B"].send("C", offline_report)
    bus.register(peers["C"])
    offline_recovered = await peers["B"].flush()
    await peers["C"].controller.run_until_idle()

    # Duplicate delivery must not add a second model call.
    await peers["A"].send("B", report)
    await peers["B"].controller.run_until_idle()

    before_idle = sum(len(gateway.calls) for gateway in gateways.values())
    await asyncio.gather(
        *(peer.controller.wait_for_work(timeout=0.01) for peer in peers.values())
    )
    idle_calls = sum(len(gateway.calls) for gateway in gateways.values()) - before_idle

    data = {
        "mode": "local_test_double",
        "nodes": ["A", "B", "C"],
        "human_task_id": human.task_id,
        "model_calls_by_node": {
            node: list(gateways[node].calls) for node in ("A", "B", "C")
        },
        "pending_outbox_total": sum(
            len(store.pending_outbound()) for store in stores.values()
        ),
        "idle_model_calls": idle_calls,
        "offline_queued": offline_queued,
        "offline_recovered": offline_recovered,
        "duplicate_delivery_count": 1,
    }
    _write_json(output, data)
    for store in stores.values():
        store.close()
    return data


def _config_template(node: str) -> str:
    return (
        f'node_id = "{node}"\n'
        'project_id = "fpga-main"\n'
        f'state_dir = ".local/node-{node.lower()}"\n'
        'mode = "app_server"\n'
        'deepseek_key_file = ""\n'
        "hardware_enabled = false\n"
        "\n"
        "[peers]\n"
        'B = ""\n'
        'C = ""\n'
        "\n"
        "[security]\n"
        'secret_env = "FPGA_MESH_SHARED_SECRET"\n'
        "\n"
        "[feishu]\n"
        'enabled = false\n'
        'group_id = ""\n'
    )


def init_configs(output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for node in ("A", "B", "C"):
        path = output / f"node-{node.lower()}.toml"
        path.write_text(
            _config_template(node),
            encoding="utf-8",
            newline="\n",
        )
        paths.append(path)
    return paths


async def live_check_deepseek(
    *,
    root: Path,
    output: Path,
    node_id: str,
    instance_id: str,
) -> dict:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is not present")
    home = CodexHomeFactory(root / "homes").create(
        CodexHomeSpec.deepseek_child(
            node_id=node_id,
            instance_id=instance_id,
        )
    )
    config = GatewayConfig(
        node_id=node_id,
        role="deepseek_child",
        model="deepseek-flash",
        provider="deepseek",
        reasoning_effort="max",
        cwd=str(Path.cwd()),
        codex_home=str(home),
    )
    gateway = AppServerGateway(
        config,
        client_factory=lambda: AppServerClient.start_stdio(
            codex_home=home,
            client_version="0.159.0",
        ),
    )
    try:
        result = await gateway.handle(
            _make_envelope(
                message_id="live-check-1",
                sender="system",
                recipient="A/DeepSeek-A",
                task_id="live-check",
                kind=MessageKind.DELEGATION,
                source=SourceKind.SYSTEM,
                text="Reply with exactly OK.",
            )
        )
        data = {
            "mode": "live_deepseek",
            "home": str(home),
            "accepted": result.accepted,
            "output": result.output,
            "thread_model": "deepseek-flash",
            "thread_provider": "deepseek",
            "reasoning_effort": "max",
        }
        _write_json(output, data)
        return data
    finally:
        await gateway.close()


async def serve_node(config_path: Path, ready_file: Path | None = None) -> None:
    from .runtime import NodeConfig, NodeRuntime
    from .service import ServiceLease

    config = NodeConfig.load(config_path)
    with ServiceLease(config.state_dir / 'resident.lock'):
        runtime = NodeRuntime(config)
        try:
            await runtime.start()
            if ready_file is not None:
                _write_json(ready_file, runtime.snapshot())
            await asyncio.Event().wait()
        finally:
            await runtime.stop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpga-mesh")
    sub = parser.add_subparsers(dest="command", required=True)

    simulate_parser = sub.add_parser("simulate")
    simulate_parser.add_argument("--root", type=Path, required=True)
    simulate_parser.add_argument("--output", type=Path, required=True)

    init_parser = sub.add_parser("init-configs")
    init_parser.add_argument("--output", type=Path, required=True)

    live_parser = sub.add_parser("live-check-deepseek")
    live_parser.add_argument("--root", type=Path, required=True)
    live_parser.add_argument("--output", type=Path, required=True)
    live_parser.add_argument("--node", default="A")
    live_parser.add_argument("--instance", default="deepseek-a-live")

    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--config", type=Path, required=True)
    serve_parser.add_argument("--ready-file", type=Path)
    serve_parser.add_argument("--log-file", type=Path)

    balance_parser = sub.add_parser("balance-check-deepseek")
    balance_parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "simulate":
        result = asyncio.run(simulate(args.root, args.output))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "init-configs":
        paths = init_configs(args.output)
        print(json.dumps([str(path) for path in paths], ensure_ascii=False))
        return 0
    if args.command == "live-check-deepseek":
        result = asyncio.run(
            live_check_deepseek(
                root=args.root,
                output=args.output,
                node_id=args.node,
                instance_id=args.instance,
            )
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "serve":
        from .runtime import NodeConfig
        from .service import service_output
        from contextlib import nullcontext
        import traceback
        with service_output(args.log_file) if args.log_file else nullcontext():
            try:
                if NodeConfig.load(args.config).feishu_enabled:
                    # The SDK captures its own event loop before asyncio.run.
                    import lark_channel.ws.client  # noqa: F401
                asyncio.run(serve_node(args.config, args.ready_file))
            except Exception:
                if not args.log_file:
                    raise
                traceback.print_exc()
                return 1
        return 0
    if args.command == "balance-check-deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not present")
        summary = DeepSeekBalanceClient(api_key=api_key).safe_summary()
        _write_json(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

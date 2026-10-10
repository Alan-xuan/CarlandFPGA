"""Stable shell entry point for an Astra that lacks a dynamic MCP tool catalog."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .child_control import LocalControlFileClient


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="fpga-mesh-child")
    top.add_argument("--control-file", type=Path, required=True)
    sub = top.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    scale = sub.add_parser("scale")
    scale.add_argument("count", type=int)
    delegate = sub.add_parser(
        "delegate",
        help="Assign ordinary work to a DeepSeek V4.1 Flash child (the priority "
             "route). Identical work is reused instead of rerun.",
    )
    delegate.add_argument("--task-id", required=True)
    delegate.add_argument("--task-version", type=int, required=True)
    content = delegate.add_mutually_exclusive_group(required=True)
    content.add_argument("--text")
    content.add_argument("--text-file", type=Path)
    delegate.add_argument("--instance-id")
    delegate.add_argument("--auto-expand", action=argparse.BooleanOptionalAction,
                          default=True)
    delegate.add_argument("--work-id")
    delegate.add_argument("--ownership", action="append", default=None,
                          metavar="PATH",
                          help="project-relative file or directory this job owns; "
                               "repeat for several paths")
    wait = sub.add_parser("wait")
    wait.add_argument("--job-id", action="append", required=True)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("job_id")
    version = sub.add_parser("version")
    version.add_argument("task_id")
    version.add_argument("number", type=int)
    native_reserve = sub.add_parser(
        "native-reserve",
        help="Reserve the shared lease for a special GPT-native task that needs "
             "the best main model. DeepSeek Flash at max reasoning stays the "
             "priority route, so --reason must justify the capability.",
    )
    native_reserve.add_argument("--task-id", required=True)
    native_reserve.add_argument("--task-version", type=int, required=True)
    native_reserve.add_argument("--work-id")
    native_content = native_reserve.add_mutually_exclusive_group(required=True)
    native_content.add_argument("--text")
    native_content.add_argument("--text-file", type=Path)
    native_reserve.add_argument("--reason", required=True)
    native_reserve.add_argument("--ownership", action="append", default=None,
                                metavar="PATH")
    native_validate = sub.add_parser(
        "native-validate",
        help="Child-side check of a GPT-native lease before starting work; "
             "binds the optional agent id once.",
    )
    native_validate.add_argument("--job-id", required=True)
    native_validate.add_argument("--lease-token", required=True)
    native_validate.add_argument("--agent-id")
    native_complete = sub.add_parser(
        "native-complete",
        help="Child-side completion of a GPT-native lease with its immutable "
             "terminal result. Interrupted, failed or cancelled leases are "
             "never replayed.",
    )
    native_complete.add_argument("--job-id", required=True)
    native_complete.add_argument("--lease-token", required=True)
    complete_content = native_complete.add_mutually_exclusive_group(required=True)
    complete_content.add_argument("--text")
    complete_content.add_argument("--text-file", type=Path)
    native_complete.add_argument("--error")
    job = sub.add_parser("job", help="Read one persisted child job.")
    job.add_argument("--job-id", required=True)
    return top


def _content(args: argparse.Namespace) -> str:
    return (args.text_file.read_text(encoding="utf-8")
            if args.text_file is not None else args.text)


async def run(args: argparse.Namespace) -> object:
    client = LocalControlFileClient(args.control_file)
    if args.command == "status":
        return await client.call("status", {})
    if args.command == "scale":
        return await client.call("scale", {"count": args.count})
    if args.command == "delegate":
        return await client.call("delegate", {
            "task_id": args.task_id, "task_version": args.task_version,
            "text": _content(args), "instance_id": args.instance_id,
            "auto_expand": args.auto_expand, "work_id": args.work_id,
            "ownership": args.ownership,
        })
    if args.command == "wait":
        return await client.call("wait", {"job_ids": args.job_id})
    if args.command == "cancel":
        return await client.call("cancel", {"job_id": args.job_id})
    if args.command == "version":
        return await client.call("task_version", {
            "task_id": args.task_id, "version": args.number,
        })
    if args.command == "native-reserve":
        return await client.call("native_reserve", {
            "task_id": args.task_id, "task_version": args.task_version,
            "text": _content(args), "work_id": args.work_id,
            "ownership": args.ownership, "reason": args.reason,
        })
    if args.command == "native-validate":
        return await client.call("native_validate", {
            "job_id": args.job_id, "lease_token": args.lease_token,
            "agent_id": args.agent_id,
        })
    if args.command == "native-complete":
        return await client.call("native_complete", {
            "job_id": args.job_id, "lease_token": args.lease_token,
            "text": _content(args), "error": args.error,
        })
    if args.command == "job":
        return await client.call("job", {"job_id": args.job_id})
    raise AssertionError(args.command)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
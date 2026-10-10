"""MCP stdio tools through which Astra controls its local DeepSeek pool."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Protocol

from .child_control import LocalControlClient, LocalControlFileClient


class ControlClient(Protocol):
    async def call(self, action: str, arguments: dict) -> object: ...


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object", "properties": properties,
            "required": required, "additionalProperties": False,
        },
    }


TOOLS = [
    _tool(
        "child_status",
        "Inspect your own DeepSeek V4.1 Flash children, jobs, and completed evidence. "
        "Standby and waiting do not make model requests.",
        {}, [],
    ),
    _tool(
        "child_scale",
        "Choose how many DeepSeek V4.1 Flash children to keep ready. "
        "Use zero or the actual task-required count. Busy children cannot be removed.",
        {"count": {"type": "integer", "minimum": 0}}, ["count"],
    ),
    _tool(
        "child_delegate",
        "Assign a concrete task to one of your local DeepSeek V4.1 Flash children "
        "at fixed max reasoning. DeepSeek Flash is the priority route for ordinary "
        "work. Returns a job id immediately; call child_wait once when you need "
        "results. You decide the task, context, and whether to expand. Identical "
        "work_id/ownership requests are reused instead of rerun, and overlapping "
        "file ownership is rejected.",
        {
            "task_id": {"type": "string"},
            "task_version": {"type": "integer", "minimum": 1},
            "text": {"type": "string"},
            "instance_id": {"type": "string"},
            "auto_expand": {"type": "boolean"},
            "work_id": {"type": "string"},
            "ownership": {"type": "array", "items": {"type": "string"}},
        },
        ["task_id", "task_version", "text"],
    ),
    _tool(
        "child_wait",
        "Wait for one or more assigned children to finish without model polling. "
        "Returns each persisted result and whether its task version became stale.",
        {"job_ids": {"type": "array", "items": {"type": "string"},
                     "minItems": 1}}, ["job_ids"],
    ),
    _tool(
        "child_cancel",
        "Request cancellation of one child job. Check the returned state before "
        "assuming an external or hardware operation stopped.",
        {"job_id": {"type": "string"}}, ["job_id"],
    ),
    _tool(
        "native_reserve",
        "Reserve the shared execution lease for bounded execution needing a "
        "specific native GPT tool or context capability. Decisions, acceptance, "
        "hard problems, critical optimization and evaluation stay with the main. "
        "DeepSeek Flash at max reasoning "
        "stays the priority route, so the reason must justify this capability. "
        "Returns the persisted job plus a one-time lease token for the native "
        "child. Identical work is reused and conflicting file ownership is rejected.",
        {
            "task_id": {"type": "string"},
            "task_version": {"type": "integer", "minimum": 1},
            "text": {"type": "string"},
            "work_id": {"type": "string"},
            "ownership": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
        },
        ["task_id", "task_version", "text", "reason"],
    ),
    _tool(
        "native_validate",
        "Validate a GPT-native lease with its token before the child starts work "
        "(DeepSeek children never need this). Supply the canonical agent_id to "
        "bind the job and require execution_allowed=true. Without an agent_id "
        "this is only a preflight and does not authorize execution.",
        {
            "job_id": {"type": "string"},
            "lease_token": {"type": "string"},
            "agent_id": {"type": "string"},
        },
        ["job_id", "lease_token"],
    ),
    _tool(
        "native_complete",
        "Record the immutable terminal result of a GPT-native lease. The same "
        "identical text may be completed twice; a changed result is rejected. "
        "Interrupted, failed or cancelled leases are never replayed.",
        {
            "job_id": {"type": "string"},
            "lease_token": {"type": "string"},
            "text": {"type": "string"},
            "error": {"type": "string"},
        },
        ["job_id", "lease_token", "text"],
    ),
]

ACTIONS = {
    "child_status": "status",
    "child_scale": "scale",
    "child_delegate": "delegate",
    "child_wait": "wait",
    "child_cancel": "cancel",
    "native_reserve": "native_reserve",
    "native_validate": "native_validate",
    "native_complete": "native_complete",
}


class McpChildServer:
    def __init__(self, client: ControlClient):
        self.client = client

    async def process(self, request: dict) -> dict | None:
        if "id" not in request:
            return None
        request_id = request["id"]
        method = request.get("method")
        params = request.get("params") or {}
        if method == "initialize":
            version = params.get("protocolVersion", "2025-03-26")
            return self._result(request_id, {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "fpga-children", "version": "0.1.0"},
            })
        if method == "ping":
            return self._result(request_id, {})
        if method == "tools/list":
            return self._result(request_id, {"tools": TOOLS})
        if method == "tools/call":
            name = params.get("name")
            if name not in ACTIONS:
                return self._tool_result(request_id, {"error": "unknown child tool"},
                                         error=True)
            try:
                result = await self.client.call(
                    ACTIONS[name], params.get("arguments") or {},
                )
                return self._tool_result(request_id, result)
            except Exception as exc:  # noqa: BLE001 - tool error, no process crash
                return self._tool_result(
                    request_id,
                    {"error": f"{type(exc).__name__}: {exc}"}, error=True,
                )
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32601, "message": "method not found"}}

    @staticmethod
    def _result(request_id: object, value: object) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "result": value}

    @classmethod
    def _tool_result(cls, request_id: object, value: object, *, error=False) -> dict:
        return cls._result(request_id, {
            "content": [{"type": "text", "text": json.dumps(value,
                ensure_ascii=False, separators=(",", ":"))}],
            "isError": error,
        })


async def _serve_stdio() -> None:
    control_file = os.environ.get("FPGA_CHILD_CONTROL_FILE")
    client = (LocalControlFileClient(control_file) if control_file else
              LocalControlClient(
                  host="127.0.0.1",
                  port=int(os.environ["FPGA_CHILD_CONTROL_PORT"]),
                  token=os.environ["FPGA_CHILD_CONTROL_TOKEN"],
              ))
    server = McpChildServer(client)
    output_lock = asyncio.Lock()
    pending: set[asyncio.Task[None]] = set()

    async def answer(request: dict) -> None:
        response = await server.process(request)
        if response is None:
            return
        async with output_lock:
            sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
            sys.stdout.flush()

    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        task = asyncio.create_task(answer(request))
        pending.add(task)
        task.add_done_callback(pending.discard)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def main() -> None:
    asyncio.run(_serve_stdio())


if __name__ == "__main__":
    main()

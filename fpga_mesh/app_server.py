"""Thin Codex app-server adapter pinned to the local protocol contract."""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Any, Protocol

from .rpc import JsonRpcSession, StdioTransport


def resolve_codex_command(
    *, platform: str | None = None, local_appdata: str | Path | None = None,
    explicit: str | Path | None = None,
) -> list[str]:
    """Prefer the Desktop bundle with its matching Code Mode host on Windows."""
    platform = sys.platform if platform is None else platform
    explicit = explicit or os.environ.get("FPGA_MESH_CODEX_BINARY")
    if explicit:
        binary = Path(explicit)
        if not binary.is_file():
            raise FileNotFoundError(f"Codex binary is missing: {binary}")
        if platform == "win32" and not (binary.parent / "codex-code-mode-host.exe").is_file():
            raise FileNotFoundError(f"Codex Code Mode host is missing beside: {binary}")
        return [str(binary), "app-server", "--stdio"]
    if platform == "win32":
        base = Path(local_appdata or os.environ.get("LOCALAPPDATA", ""))
        bundle_root = base / "OpenAI" / "Codex" / "bin"
        candidates = [path for path in bundle_root.glob("*/codex.exe")
                      if (path.parent / "codex-code-mode-host.exe").is_file()]
        if candidates:
            binary = max(candidates, key=lambda item: item.stat().st_mtime)
            return [str(binary), "app-server", "--stdio"]
        return ["cmd.exe", "/d", "/c", "codex", "app-server", "--stdio"]
    return ["codex", "app-server", "--stdio"]


class RpcSession(Protocol):
    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        ...

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        ...

    async def close(self) -> None:
        ...


def build_codex_env(
    codex_home: str | Path, *, source: dict[str, str] | None = None,
    role: str, extra: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if source is None else source)
    env.update(extra or {})
    # Model endpoints come from the role's verified provider configuration.
    # Do not let a previously exported routing override redirect either role.
    for name in ('OPENAI_BASE_URL', 'CODEX_BACKEND_BASE_URL',
                 'CHATGPT_BASE_URL', 'CODEX_CHATGPT_BASE_URL'):
        env.pop(name, None)
    if role == "astra":
        env.pop("DEEPSEEK_API_KEY", None)
    elif role == "deepseek_child":
        for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_ORG_ID",
                     "OPENAI_PROJECT_ID"):
            env.pop(name, None)
    else:
        raise ValueError("unknown Codex role")
    env["CODEX_HOME"] = str(codex_home)
    return env


class AppServerClient:
    def __init__(self, session: RpcSession, *, client_version: str):
        self.session = session
        self.client_version = client_version

    async def initialize(self) -> Any:
        result = await self.session.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "fpga-mesh",
                    "title": "FPGA multi-agent controller",
                    "version": self.client_version,
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        await self.session.notify("initialized", {})
        return result

    async def thread_start(
        self,
        *,
        cwd: str,
        model: str,
        model_provider: str,
        config: dict[str, Any] | None = None,
        dynamic_tools: list[dict[str, Any]] | None = None,
        ephemeral: bool = False,
        developer_instructions: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {
            "cwd": cwd,
            "model": model,
            "modelProvider": model_provider,
        }
        if config is not None:
            params["config"] = config
        if dynamic_tools is not None:
            params["dynamicTools"] = dynamic_tools
        if ephemeral:
            params["ephemeral"] = True
        if developer_instructions is not None:
            params["developerInstructions"] = developer_instructions
        return await self.session.request(
            "thread/start",
            params,
        )

    async def turn_start(
        self,
        *,
        thread_id: str,
        text: str,
        model: str,
        effort: str,
        output_schema: dict[str, Any] | None = None,
    ) -> Any:
        params: dict[str, Any] = {
                "threadId": thread_id,
                "model": model,
                "effort": effort,
                "input": [{"type": "text", "text": text}],
            }
        if output_schema is not None:
            params["outputSchema"] = output_schema
        return await self.session.request("turn/start", params)

    async def account_rate_limits(self) -> Any:
        return await self.session.request("account/rateLimits/read", {})

    async def turn_interrupt(self, *, thread_id: str, turn_id: str) -> Any:
        return await self.session.request(
            "turn/interrupt", {"threadId": thread_id, "turnId": turn_id},
        )

    async def close(self) -> None:
        await self.session.close()

    @classmethod
    async def start_stdio(
        cls,
        *,
        codex_home: str | Path,
        codex_command: list[str] | None = None,
        client_version: str,
        role: str = "deepseek_child",
        extra_env: dict[str, str] | None = None,
    ) -> "AppServerClient":
        command = codex_command or resolve_codex_command()
        if sys.platform == "win32" and command[0].lower() == "codex":
            command = ["cmd.exe", "/d", "/c", *command]
        env = build_codex_env(codex_home, role=role, extra=extra_env)
        transport = StdioTransport(command, env=env)
        await transport.start()
        session = JsonRpcSession(transport)
        return cls(session, client_version=client_version)

"""Native Codex dynamic tools for one Astra's local DeepSeek pool."""

from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from .mcp_children import ACTIONS, TOOLS


class ControlClient(Protocol):
    async def call(self, action: str, arguments: dict) -> object: ...


class ChildDynamicTools:
    ACTIONS = {f"fpga_{name}": action for name, action in ACTIONS.items()}

    def __init__(self, client: ControlClient):
        self.client = client

    @classmethod
    def specs(cls) -> list[dict]:
        result = []
        for tool in TOOLS:
            copy = deepcopy(tool)
            copy["type"] = "function"
            copy["name"] = f"fpga_{tool['name']}"
            result.append(copy)
        return result

    async def call(self, name: str, arguments: dict) -> object:
        try:
            action = self.ACTIONS[name]
        except KeyError as exc:
            raise ValueError(f"unknown child tool: {name}") from exc
        return await self.client.call(action, arguments)
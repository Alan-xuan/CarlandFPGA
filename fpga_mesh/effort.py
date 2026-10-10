"""Astra chooses a per-task reasoning effort before substantive work."""

from __future__ import annotations

import asyncio
import json
from typing import Protocol

from .notifications import notification_matches_turn, terminal_error_message


EFFORTS = ("low", "medium", "high", "xhigh", "max")
SCHEMA = {
    "type": "object",
    "properties": {"effort": {"type": "string", "enum": list(EFFORTS)}},
    "required": ["effort"],
    "additionalProperties": False,
}
INSTRUCTIONS = (
    "You are selecting the reasoning effort for the next GPT-6 Astra work "
    "turn. Do not perform the task or call tools. Assess its complexity, "
    "uncertainty, consequences of an error, and verification needs. Choose "
    "low only for clearly bounded simple work; raise effort as necessary to "
    "preserve quality. If uncertain, choose max. Reply with only a JSON object "
    "matching the effort schema. DeepSeek child effort is fixed at max and "
    "is not part of this choice."
)


class SelectorClient(Protocol):
    session: object

    async def thread_start(self, **kwargs) -> dict: ...
    async def turn_start(self, **kwargs) -> dict: ...
    async def turn_interrupt(self, **kwargs) -> dict: ...


class AstraEffortSelector:
    def __init__(self, *, timeout_seconds: float = 45):
        self.timeout_seconds = timeout_seconds

    async def choose(
        self, client: SelectorClient, *, cwd: str, model: str, text: str,
    ) -> str:
        thread_id: str | None = None
        turn_id: str | None = None
        turn_active = False
        try:
            started = await asyncio.wait_for(
                client.thread_start(
                    cwd=cwd, model=model, model_provider="openai",
                    ephemeral=True, developer_instructions=INSTRUCTIONS,
                ), timeout=self.timeout_seconds,
            )
            thread_id = started["thread"]["id"]
            turn = await asyncio.wait_for(
                client.turn_start(
                    thread_id=thread_id, model=model, effort="low",
                    text="Select effort for this task:\n" + text,
                    output_schema=SCHEMA,
                ), timeout=self.timeout_seconds,
            )
            turn_id = turn["turn"]["id"]
            turn_active = True
            completed = await asyncio.wait_for(
                self._wait(client, thread_id, turn_id), timeout=self.timeout_seconds,
            )
            turn_active = False
            if completed.get("status") != "completed":
                return "max"
            messages = [item for item in completed.get("items", [])
                        if item.get("type") == "agentMessage"]
            if not messages:
                return "max"
            decision = json.loads(messages[-1].get("text", ""))
            effort = decision.get("effort")
            return effort if effort in EFFORTS else "max"
        except asyncio.CancelledError:
            if turn_active and thread_id and turn_id:
                await self._interrupt(client, thread_id, turn_id)
            raise
        except asyncio.TimeoutError as exc:
            if not turn_active:
                raise RuntimeError("selector setup timed out") from exc
            if thread_id and turn_id:
                await self._interrupt(client, thread_id, turn_id)
            return "max"
        except (KeyError, ValueError, TypeError, RuntimeError):
            if turn_active and thread_id and turn_id:
                await self._interrupt(client, thread_id, turn_id)
            return "max"

    @staticmethod
    async def _interrupt(client: SelectorClient, thread_id: str, turn_id: str) -> None:
        try:
            await asyncio.wait_for(asyncio.shield(client.turn_interrupt(
                thread_id=thread_id, turn_id=turn_id,
            )), timeout=5)
        except Exception as exc:  # noqa: BLE001 - do not start concurrent work
            raise RuntimeError(
                "selector turn could not be interrupted"
            ) from exc

    @staticmethod
    async def _wait(client: SelectorClient, thread_id: str, turn_id: str) -> dict:
        while True:
            event = await client.session.next_notification()
            if event.method == "error":
                error = terminal_error_message(
                    event.params, thread_id=thread_id, turn_id=turn_id,
                )
                if error is not None:
                    raise RuntimeError(error)
                continue
            if event.method != "turn/completed":
                continue
            turn = event.params.get("turn", {})
            if notification_matches_turn(
                event.params, thread_id=thread_id, turn_id=turn_id,
            ):
                return turn

"""Match turn notifications and distinguish recoverable protocol errors."""

from __future__ import annotations


def notification_matches_turn(
    params: dict, *, thread_id: str, turn_id: str,
) -> bool:
    turn = params.get("turn")
    notification_turn_id = (
        turn.get("id") if isinstance(turn, dict) else params.get("turnId")
    )
    return (params.get("threadId") == thread_id and
            notification_turn_id == turn_id)


def terminal_error_message(
    params: dict, *, thread_id: str, turn_id: str,
) -> str | None:
    # Transport errors emitted by JsonRpcSession have no turn identifiers.
    scoped = any(key in params for key in ("error", "threadId", "turnId"))
    if scoped:
        if not notification_matches_turn(
            params, thread_id=thread_id, turn_id=turn_id,
        ):
            return None
        if params.get("willRetry") is True:
            return None
    error = params.get("error")
    if isinstance(error, dict):
        message = error.get("message")
    else:
        message = error
    return str(message or params.get("message") or "Codex error")

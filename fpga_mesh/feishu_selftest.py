"""One-time Feishu group send/read gate for a newly joined app identity.

DeepSeek uses this API read only during onboarding. It does not subscribe to
group events or give a child agent autonomous access to group messages.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_BASE = "https://open.feishu.cn/open-apis"


class FeishuSelfTestAPI:
    """Minimal Feishu OpenAPI calls; tokens and message contents stay local."""

    def _request(self, method: str, path: str, *, token: str = "",
                 payload: dict | None = None) -> dict:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = (json.dumps(payload, ensure_ascii=False).encode("utf-8")
                if payload is not None else None)
        request = Request(_BASE + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                result = json.load(response)
        except HTTPError as exc:
            try:
                code = json.load(exc).get("code", "unknown")
            except (ValueError, OSError):
                code = "unknown"
            raise RuntimeError(f"Feishu API HTTP {exc.code}, code {code}") from None
        except URLError as exc:
            raise RuntimeError(f"Feishu API network error: {type(exc.reason).__name__}") from None
        if not isinstance(result, dict) or result.get("code") != 0:
            code = result.get("code", "unknown") if isinstance(result, dict) else "unknown"
            raise RuntimeError(f"Feishu API code {code}")
        return result

    def access_token(self, app_id: str, secret: str) -> str:
        data = self._request("POST", "/auth/v3/tenant_access_token/internal",
                             payload={"app_id": app_id, "app_secret": secret})
        token = data.get("tenant_access_token", "")
        if not token:
            raise RuntimeError("Feishu did not return a tenant access token")
        return token

    def granted_scopes(self, token: str) -> set[str]:
        data = self._request("GET", "/application/v6/scopes", token=token)
        return {entry["scope_name"] for entry in (data.get("data") or {}).get("scopes", [])
                if entry.get("grant_status") == 1 and entry.get("scope_type") == "tenant"}

    def send(self, token: str, group_id: str, message: str, request_uuid: str) -> str:
        query = urlencode({"receive_id_type": "chat_id"})
        data = self._request("POST", f"/im/v1/messages?{query}", token=token,
                             payload={
                                 "receive_id": group_id, "msg_type": "text",
                                 "content": json.dumps({"text": message}, ensure_ascii=False),
                                 "uuid": request_uuid,
                             })
        message_id = str((data.get("data") or {}).get("message_id") or "")
        if not message_id:
            raise RuntimeError("Feishu send returned no message ID")
        return message_id

    def recent_messages(self, token: str, group_id: str) -> list[dict]:
        query = urlencode({
            "container_id_type": "chat", "container_id": group_id,
            "sort_type": "ByCreateTimeDesc", "page_size": 50,
        })
        data = self._request("GET", f"/im/v1/messages?{query}", token=token)
        return list((data.get("data") or {}).get("items") or [])


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def _matches(item: dict, state: dict) -> bool:
    if item.get("message_id") != state["message_id"]:
        return False
    if item.get("chat_id") != state["group_id"] or item.get("msg_type") != "text":
        return False
    content = (item.get("body") or {}).get("content")
    try:
        return json.loads(content)["text"] == state["message"]
    except (TypeError, ValueError, KeyError):
        return False


def run_self_test(*, node: str, role: str, app_id: str, secret_file: Path,
                  group_id: str, state_file: Path, api: FeishuSelfTestAPI | None = None,
                  delays: tuple[float, ...] = (1, 2, 4)) -> dict:
    """Post one marked message, then read it back as the same app identity."""
    if node not in {"A", "B", "C"} or role not in {"astra", "deepseek"}:
        raise ValueError("invalid node or role")
    if not app_id.startswith("cli_") or not group_id.startswith("oc_"):
        raise ValueError("invalid Feishu app or group ID")
    state_file = Path(state_file)
    identity = {"node": node, "role": role, "app_id": app_id, "group_id": group_id}
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else None
    if state is not None and any(state.get(key) != value for key, value in identity.items()):
        raise ValueError("self-test state belongs to a different app or group")
    if state is not None and state.get("verified"):
        return {**identity, "status": "verified", "message_id": state["message_id"],
                "reused": True}
    if state is None:
        marker = uuid.uuid4().hex[:12]
        label = "Astra" if role == "astra" else "DeepSeek"
        message = (f"【FPGA Mesh 入群自测】{node}/{label} 发信与读回验证，"
                   f"标记 {marker}。这不是任务指令。")
        state = {**identity, "message": message, "request_uuid": str(uuid.uuid4()),
                 "message_id": "", "verified": False}
        _save_state(state_file, state)

    api = api or FeishuSelfTestAPI()
    secret = Path(secret_file).read_text(encoding="utf-8-sig").strip()
    if not secret:
        raise ValueError("Feishu app secret file is empty")
    token = api.access_token(app_id, secret)
    if not state["message_id"]:
        state["message_id"] = api.send(token, group_id, state["message"],
                                       state["request_uuid"])
        _save_state(state_file, state)
    for delay in (0, *delays):
        if delay:
            time.sleep(delay)
        if any(_matches(item, state) for item in api.recent_messages(token, group_id)):
            state["verified"] = True
            _save_state(state_file, state)
            return {**identity, "status": "verified", "message_id": state["message_id"],
                    "reused": False}
    raise RuntimeError("Feishu read-back did not find the self-test message")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a new Feishu app after joining the group")
    parser.add_argument("--node", choices="ABC", required=True)
    parser.add_argument("--role", choices=("astra", "deepseek"), required=True)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    parser.add_argument("--group-id", required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args()
    result = run_self_test(node=args.node, role=args.role, app_id=args.app_id,
                           secret_file=args.secret_file, group_id=args.group_id,
                           state_file=args.state_file)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

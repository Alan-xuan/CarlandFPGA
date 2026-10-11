"""Human-approved Feishu application registration via the official device flow."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable


def registration_addons(role: str) -> dict[str, Any]:
    if role not in {"astra", "deepseek"}:
        raise ValueError("role must be astra or deepseek")
    scopes = ["im:message:send_as_bot"]
    result: dict[str, Any] = {
        "preset": False,
        "scopes": {"tenant": scopes},
    }
    if role == "astra":
        scopes.extend(["im:message", "im:message.group_msg", "im:resource"])
        result["events"] = {"items": {"tenant": ["im.message.receive_v1"]}}
    else:
        # One-time read-back during onboarding; no event subscription is added.
        scopes.extend(["im:message:readonly", "im:message.group_msg"])
    return result


def register_role(
    *, node: str, role: str, output_dir: Path,
    register_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, str]:
    if node not in {"A", "B", "C"}:
        raise ValueError("node must be A, B, or C")
    addons = registration_addons(role)
    if register_fn is None:
        try:
            import lark_oapi as lark
        except ImportError as exc:
            raise RuntimeError("Feishu registration requires lark-oapi") from exc
        register_fn = lark.register_app

    def on_qr_code(info: dict[str, Any]) -> None:
        print(f"Open this Feishu verification URL for {node}/{role}: {info['url']}", flush=True)
        print(f"The link expires in {info.get('expire_in', '?')} seconds.", flush=True)

    result = register_fn(
        on_qr_code=on_qr_code,
        app_preset={
            "name": f"FPGA {'Astra' if role == 'astra' else 'DeepSeek'} {node}",
            "desc": "FPGA/AI/DEV multi-machine development agent",
        },
        addons=addons,
        create_only=True,
        source="fpga-mesh",
    )
    app_id = str(result.get("client_id") or "")
    secret = str(result.get("client_secret") or "")
    if not app_id.startswith("cli_") or not secret:
        raise RuntimeError("Feishu registration did not return app credentials")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    secret_path = output_dir / f"{role}-secret.txt"
    temp_path = output_dir / f".{role}-secret.tmp"
    descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(secret)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    os.replace(temp_path, secret_path)
    manifest = {
        "node": node,
        "role": role,
        "app_id": app_id,
        "secret_file": str(secret_path.resolve()),
    }
    (output_dir / f"{role}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest

"""Read-only audit of the existing Astra app's file permission after updates."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .feishu_selftest import FeishuSelfTestAPI
from .runtime import NodeConfig


def check_file_scope(config: NodeConfig, *, api=None) -> dict:
    result = {'node': config.node_id, 'role': 'astra',
              'app_id': config.feishu_astra_app_id, 'required_file_scope': 'im:resource'}
    if not config.feishu_enabled:
        return {**result, 'status': 'disabled'}
    api = api or FeishuSelfTestAPI()
    secret = config.feishu_astra_secret_file.read_text(encoding='utf-8-sig').strip()
    if not secret:
        raise ValueError('Existing Astra app secret file is empty')
    token = api.access_token(config.feishu_astra_app_id, secret)
    scopes = api.granted_scopes(token)
    return {**result, 'status': 'ready' if 'im:resource' in scopes else 'needs_admin_grant',
            'granted_scopes': sorted(scopes),
            'manage_url': f'https://open.feishu.cn/app/{config.feishu_astra_app_id}/auth'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(check_file_scope(NodeConfig.load(args.config)), ensure_ascii=True))
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()

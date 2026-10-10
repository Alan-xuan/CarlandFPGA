"""MCP bridge for Desktop chats; two entrances share one resident ledger."""
import asyncio
import json
import os
import sys
from pathlib import Path
from .child_control import LocalControlFileClient
from .dynamic_children import ChildDynamicTools
from .project_control import SESSION_TOOLS
from .mesh_tools import MeshDynamicTools
from .project_cli import discovery

async def serve():
    control = os.environ.get('FPGA_MAIN_CONTROL_FILE')
    client = LocalControlFileClient(Path(control) if control else discovery(Path.cwd()))
    specs = ChildDynamicTools.specs() + SESSION_TOOLS + MeshDynamicTools.main_specs()
    mapping = {**ChildDynamicTools.ACTIONS, 'fpga_session_list': 'session_list',
               'fpga_models_refresh': 'models_refresh',
               'fpga_session_open': 'main_submit', 'fpga_session_route': 'session_route',
               **{spec['name']:spec['name'] for spec in MeshDynamicTools.main_specs()}}
    while True:
        line = await asyncio.to_thread(sys.stdin.buffer.readline)
        if not line:
            return
        request = json.loads(line)
        if 'id' not in request:
            continue
        method, params = request.get('method'), request.get('params') or {}
        if method == 'initialize':
            result = {'protocolVersion': params.get('protocolVersion', '2025-03-26'),
                      'capabilities': {'tools': {}}, 'serverInfo': {'name': 'fpga-mesh', 'version': '0.8.0'}}
        elif method == 'tools/list':
            result = {'tools': [{k: v for k, v in t.items() if k != 'type'} for t in specs]}
        elif method == 'ping':
            result = {}
        elif method == 'tools/call':
            try:
                data = await client.call(mapping[params['name']], params.get('arguments') or {})
                result = {'content': [{'type': 'text', 'text': json.dumps(data, ensure_ascii=True)}]}
            except Exception as exc:
                result = {'isError': True, 'content': [{'type': 'text', 'text': f'{type(exc).__name__}: {exc}'}]}
        else:
            print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32601, 'message': 'unknown method'}}), flush=True)
            continue
        print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result}), flush=True)

if __name__ == '__main__':
    asyncio.run(serve())

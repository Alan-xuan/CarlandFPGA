"""Small loopback-only model update page for the resident local node."""
import asyncio
import json
import os
import secrets
from pathlib import Path


PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CarlandFPGA · 官方模型</title>
<style nonce="TOKEN">body{font:16px system-ui;margin:40px auto;padding:0 24px;max-width:960px;background:#f6f8fa;color:#1b2533}h1{font-size:28px}button{padding:12px 22px;border:0;border-radius:8px;background:#185adb;color:white;font-size:16px;cursor:pointer}button:disabled{opacity:.55;cursor:wait}p{line-height:1.7}table{width:100%;border-collapse:collapse;margin:18px 0;background:white}td,th{text-align:left;padding:10px 12px;border-bottom:1px solid #e5e9ef}#status{padding:12px;background:white;border-radius:8px}small{color:#536174}</style>
<h1>CarlandFPGA 官方模型</h1>
<p>点击更新，从 Codex 官方目录获取当前模型与推理档位，并更新原生派工角色。已有任务继续运行。</p>
<button id="update">更新官方模型</button><p id="status" role="status">正在读取已保存目录…</p>
<small>新模型以 OpenAI 发布、账号权限及客户端支持为准。新角色配置在新加载的会话生效。DeepSeek Flash/max、飞书身份及主从权限保持原设置。</small>
<h2>官方目录</h2><table><thead><tr><th>模型</th><th>推理档位</th><th>目录状态</th></tr></thead><tbody id="models"></tbody></table>
<h2>原生派工入口</h2><table><thead><tr><th>角色</th><th>实际模型</th><th>说明</th></tr></thead><tbody id="roles"></tbody></table>
<script nonce="TOKEN">
const button=document.querySelector('#update'),status=document.querySelector('#status');
function rows(id,values){const body=document.querySelector(id);body.replaceChildren();for(const row of values){const tr=document.createElement('tr');for(const value of row){const td=document.createElement('td');td.textContent=value;tr.append(td)}body.append(tr)}}
function show(data){rows('#models',Object.entries(data.models||{}).map(([m,v])=>[m,v.efforts.join(' / '),v.hidden?'官方隐藏条目':'可选择']));rows('#roles',Object.entries(data.roles||{}).map(([r,v])=>[r,v.model,v.alias?'兼容别名 · 原名称暂未列出':v.effort]));status.textContent=data.updated_at?'已更新：'+data.updated_at+' · '+Object.keys(data.roles).length+' 个原生入口 · 更新未发起推理调用':'尚未更新，请点击更新按钮。'}
async function read(){try{const response=await fetch('/status');const data=await response.json();if(!response.ok)throw Error(data.error);show(data)}catch(e){status.textContent='读取失败：'+e.message}}
button.addEventListener('click',async()=>{button.disabled=true;status.textContent='正在读取官方目录并更新角色…';try{const response=await fetch('/update',{method:'POST',headers:{'X-Model-Update':'TOKEN'}});const data=await response.json();if(!response.ok)throw Error(data.error);show(data)}catch(e){status.textContent='更新失败，已有目录和角色已保留：'+e.message}finally{button.disabled=false}});read();
</script></html>'''


class ModelsHttpServer:
    def __init__(self, actions, *, discovery_path: Path):
        self.actions, self.discovery_path = actions, Path(discovery_path)
        self.server = None
        self.token = secrets.token_urlsafe(32)
        self.url = ''

    async def start(self):
        self.server = await asyncio.start_server(self._handle, '127.0.0.1', 0, limit=16384)
        port = self.server.sockets[0].getsockname()[1]
        self.host = f'127.0.0.1:{port}'
        self.url = f'http://{self.host}'
        self.discovery_path.parent.mkdir(parents=True, exist_ok=True)
        self.discovery_path.write_text(json.dumps({'url': self.url, 'pid': os.getpid()}), encoding='utf-8')

    async def _handle(self, reader, writer):
        code, mime = 200, 'application/json; charset=utf-8'
        try:
            raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
            lines = raw.decode('ascii').split('\r\n')
            method, path, _ = lines[0].split(' ', 2)
            headers = dict(line.split(':', 1) for line in lines[1:] if ':' in line)
            headers = {k.lower(): v.strip() for k, v in headers.items()}
            if headers.get('host') != self.host or headers.get('origin', self.url) != self.url:
                raise PermissionError('only the local model page may access this endpoint')
            if method == 'GET' and path == '/':
                mime = 'text/html; charset=utf-8'
                body = PAGE.replace('TOKEN', self.token).encode('utf-8')
            elif method == 'GET' and path == '/status':
                body = json.dumps(await self.actions.call('models_list', {})).encode('utf-8')
            elif method == 'POST' and path == '/update':
                if headers.get('origin') != self.url or not secrets.compare_digest(headers.get('x-model-update', ''), self.token):
                    raise PermissionError('model update requires the local page request token')
                body = json.dumps(await self.actions.call('models_refresh', {})).encode('utf-8')
            else:
                code, body = 404, b'{"error":"unknown model page endpoint"}'
        except PermissionError as exc:
            code, body = 403, json.dumps({'error': str(exc)}).encode()
        except Exception as exc:
            code, body = 500, json.dumps({'error': str(exc)[:250]}).encode()
        try:
            csp = f"default-src 'none'; script-src 'nonce-{self.token}'; style-src 'nonce-{self.token}'; connect-src 'self'; frame-ancestors 'none'"
            head = f'HTTP/1.1 {code} Response\r\nContent-Type: {mime}\r\nContent-Length: {len(body)}\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nContent-Security-Policy: {csp}\r\n\r\n'
            writer.write(head.encode('ascii') + body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        if self.discovery_path.exists():
            saved = json.loads(self.discovery_path.read_text())
            if saved.get('url') == self.url:
                self.discovery_path.unlink()


def main():
    import webbrowser
    from .project_cli import discovery
    control = discovery(Path.cwd())
    info = json.loads((control.parent / 'model-manager.json').read_text(encoding='utf-8'))
    webbrowser.open(info['url'])


if __name__ == '__main__':
    main()

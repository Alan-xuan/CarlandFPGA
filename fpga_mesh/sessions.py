"""Persistent task conversations and validated OpenAI model/effort routing."""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

EFFORT_ORDER = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')
CRITICAL = frozenset({'decision', 'acceptance', 'difficult', 'optimization', 'evaluation'})
KINDS = CRITICAL | {'execution', 'routine'}
IMPORTANT = re.compile(r'决策|验收|重难|关键|评估|优化|设计|架构|(?:\b)(?:decision|acceptance|difficult|critical|optimization|evaluate|review|architecture|cdc|rdc)(?:\b)', re.I)
ROUTINE = re.compile(r'^\s*(?:Reply (?:with )?(?:exactly|only) [\w. -]+\.?|只回复\s*\S+|仅回复\s*\S+)\s*$', re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MainSessionRouter:
    def __init__(self, path: str | Path, *, quality_model: str = 'gpt-6-astra'):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS main_sessions (
                task_id TEXT PRIMARY KEY, thread_id TEXT UNIQUE NOT NULL,
                task_version INTEGER NOT NULL, model TEXT NOT NULL, effort TEXT NOT NULL,
                category TEXT NOT NULL, title TEXT NOT NULL, pending_json TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS main_runs (
                message_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                status TEXT NOT NULL, result_json TEXT, error TEXT, updated_at TEXT NOT NULL
            );
        ''')
        self.db.execute("UPDATE main_runs SET status='interrupted' WHERE status='running'")
        self.db.commit()
        self.quality_model = quality_model
        self._models: dict[str, tuple[str, ...]] = {}
        self._loaded: set[str] = set()
        self._allocation = asyncio.Lock()
        self.changed = asyncio.Event()

    async def catalog(self, client) -> dict[str, tuple[str, ...]]:
        if not self._models:
            models = {}
            cursor = None
            while True:
                args = {'includeHidden': False}
                if cursor:
                    args['cursor'] = cursor
                result = await client.session.request('model/list', args)
                for item in result.get('data', []):
                    model = item.get('model') or item.get('id')
                    if not isinstance(model, str) or not model.startswith('gpt-') or item.get('hidden'):
                        continue
                    efforts = tuple(e.get('reasoningEffort') if isinstance(e, dict) else e
                                    for e in item.get('supportedReasoningEfforts', []))
                    efforts = tuple(e for e in efforts if e in EFFORT_ORDER)
                    if efforts:
                        models[model] = efforts
                cursor = result.get('nextCursor')
                if not cursor:
                    break
            if not models:
                raise RuntimeError('No verified GPT models/efforts are available')
            self._models = models
        return self._models

    def best(self) -> tuple[str, str]:
        choices = (self.quality_model, 'gpt-6-astra', 'gpt-6.1-sol', 'gpt-6-sol')
        model = next((m for m in choices if m in self._models), next(iter(self._models)))
        return model, max(self._models[model], key=EFFORT_ORDER.index)

    def guard(self, model: str, effort: str, category: str) -> None:
        if category not in KINDS:
            raise ValueError('unknown work category')
        if model not in self._models or effort not in self._models[model]:
            raise ValueError('model/effort is not in the verified GPT catalog')
        if category in CRITICAL and (model, effort) != self.best():
            raise ValueError('critical work requires the quality main model at highest effort')

    async def choose(self, client, text: str, category: str | None = None) -> dict:
        await self.catalog(client)
        if category is not None and category not in KINDS:
            raise ValueError('unknown work category')
        important = IMPORTANT.search(text) is not None or category in CRITICAL
        if not important and ROUTINE.fullmatch(text):
            model = next((m for m in ('gpt-6-luna', 'gpt-5.6-luna', 'gpt-6.1-sol') if m in self._models), self.best()[0])
            effort = min(self._models[model], key=EFFORT_ORDER.index)
            return {'model': model, 'effort': effort, 'category': 'routine'}
        model, effort = self.best()
        return {'model': model, 'effort': effort,
                'category': category if category in CRITICAL else 'difficult'}

    def session(self, task_id: str) -> dict | None:
        row = self.db.execute('SELECT * FROM main_sessions WHERE task_id=?', (task_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result.pop('pending_json', None)
        return result

    def sessions(self) -> list[dict]:
        return [self.session(r['task_id']) for r in self.db.execute('SELECT task_id FROM main_sessions ORDER BY updated_at')]

    async def schedule_route(self, client, *, task_id: str, model: str, effort: str, category: str = 'execution') -> dict:
        await self.catalog(client)
        self.guard(model, effort, category)
        if self.session(task_id) is None:
            raise KeyError('main task session is not registered')
        route = {'model': model, 'effort': effort, 'category': category}
        with self.db:
            self.db.execute('UPDATE main_sessions SET pending_json=?, updated_at=? WHERE task_id=?', (json.dumps(route), now(), task_id))
        return {'task_id': task_id, **route, 'applies': 'next_turn'}

    async def open_session(self, client, *, task_id: str, task_version: int, text: str, cwd: str,
                           model: str | None = None, effort: str | None = None,
                           category: str | None = None, config=None, dynamic_tools=None,
                           developer_instructions=None) -> dict:
        if not task_id.strip() or task_version < 1 or not text.strip():
            raise ValueError('task_id, positive version and text are required')
        async with self._allocation:
            existing = self.session(task_id)
            if existing:
                return {**existing, 'created': False}
            route = await self.choose(client, text, category)
            if model is not None or effort is not None:
                if model is None or effort is None:
                    raise ValueError('model and effort must be specified together')
                # Explicit execution routes are permitted; critical categories never downgrade.
                route = {'model': model, 'effort': effort, 'category': category or 'execution'}
                self.guard(**route)
                if IMPORTANT.search(text) and (model, effort) != self.best():
                    raise ValueError('critical task text cannot be downgraded')
            thread_config = dict(config or {})
            thread_config['model_reasoning_effort'] = route['effort']
            started = await client.thread_start(cwd=cwd, model=route['model'], model_provider='openai',
                config=thread_config, dynamic_tools=dynamic_tools, developer_instructions=developer_instructions)
            thread_id = started['thread']['id']
            title = f'{task_id}: {text.splitlines()[0][:60]}'
            # Title is cosmetic; old clients may not support naming.
            try:
                await client.session.request('thread/name/set', {'threadId': thread_id, 'name': title})
            except Exception:
                pass
            with self.db:
                self.db.execute('INSERT INTO main_sessions VALUES (?,?,?,?,?,?,?,?,?)',
                    (task_id, thread_id, task_version, route['model'], route['effort'], route['category'], title,
                     json.dumps(route) if model is not None else None, now()))
            self._loaded.add(thread_id)
            return {**self.session(task_id), 'created': True}

    async def prepare(self, client, message, *, cwd, config=None, dynamic_tools=None, developer_instructions=None) -> dict:
        text = str(message.payload.get('text', message.message_id))
        row = await self.open_session(client, task_id=message.task_id, task_version=message.task_version,
            text=text, cwd=cwd, category=message.payload.get('category'), config=config,
            dynamic_tools=dynamic_tools, developer_instructions=developer_instructions)
        if message.task_version < row['task_version']:
            raise ValueError('stale main task version')
        chosen = await self.choose(client, text, message.payload.get('category'))
        pending = self.db.execute('SELECT pending_json FROM main_sessions WHERE task_id=?', (message.task_id,)).fetchone()[0]
        if pending and not IMPORTANT.search(text) and message.payload.get('category') not in CRITICAL:
            chosen = json.loads(pending)
            self.guard(**chosen)
        if row['thread_id'] not in self._loaded:
            await client.session.request('thread/resume', {
                'threadId': row['thread_id'], 'cwd': cwd, 'model': chosen['model'], 'modelProvider': 'openai',
                'config': {**(config or {}), 'model_reasoning_effort': chosen['effort']},
                'developerInstructions': developer_instructions,
            })
            self._loaded.add(row['thread_id'])
        with self.db:
            self.db.execute('UPDATE main_sessions SET task_version=?,model=?,effort=?,category=?,pending_json=NULL,updated_at=? WHERE task_id=?',
                (message.task_version, chosen['model'], chosen['effort'], chosen['category'], now(), message.task_id))
        return self.session(message.task_id)

    def result(self, message_id: str) -> dict | None:
        row = self.db.execute('SELECT * FROM main_runs WHERE message_id=?', (message_id,)).fetchone()
        if not row:
            return None
        return {'message_id': message_id, 'task_id': row['task_id'], 'status': row['status'],
                'result': json.loads(row['result_json']) if row['result_json'] else None, 'error': row['error']}

    def record(self, message_id: str, task_id: str, status: str, *, result=None, error=None) -> None:
        with self.db:
            self.db.execute('INSERT INTO main_runs VALUES (?,?,?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET status=excluded.status,result_json=excluded.result_json,error=excluded.error,updated_at=excluded.updated_at',
                (message_id, task_id, status, json.dumps(result, ensure_ascii=False) if result is not None else None, error, now()))
        self.changed.set()

    def reset_connection(self) -> None:
        self._loaded.clear()
        self._models.clear()

    def close(self) -> None:
        self.db.close()

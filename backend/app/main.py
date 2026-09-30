import asyncio
import json
import logging
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, settings
from .context import build_context
from .database import connect, initialize
from .providers import PROVIDERS, get_api_key, get_provider_config
from .security import apply_security_headers, get_allowed_origins, verify_basic_auth

log = logging.getLogger('forma')

# Active generation tasks mapped by conversation ID
active: dict[str, asyncio.Task] = {}


def now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown management."""
    if settings.is_production:
        if not settings.AUTH_USERNAME or len(settings.AUTH_PASSWORD) < 16:
            raise RuntimeError(
                'Production requires AUTH_USERNAME and AUTH_PASSWORD (at least 16 characters).'
            )
        if not os.getenv('OLLAMA_BASE_URL'):
            raise RuntimeError('Production requires an explicit reachable OLLAMA_BASE_URL.')

    initialize()

    # Reset any generation status left behind by killed processes
    with connect() as db:
        db.execute("UPDATE messages SET status='stopped' WHERE status='generating'")

    yield


app = FastAPI(
    title='Forma local assistant',
    description='Private AI conversational workspace supporting local Ollama, Groq, OpenAI, Gemini, and OpenRouter',
    lifespan=lifespan,
)


@app.middleware('http')
async def security_middleware(request: Request, call_next):
    """
    Unified security middleware:
    - Enforces HTTPS upgrade when behind a proxy
    - Enforces constant-time HTTP Basic Auth for private workspaces
    - Enforces Origin validation for state-modifying requests
    - Attaches comprehensive security hardening headers (HSTS, CSP, X-Frame-Options)
    """
    if settings.is_production and request.headers.get('x-forwarded-proto') == 'http':
        https_url = request.url.replace(scheme='https')
        return RedirectResponse(str(https_url), status_code=308)

    username = settings.AUTH_USERNAME
    password = settings.AUTH_PASSWORD
    if (username or password) and request.url.path != '/api/health':
        auth_header = request.headers.get('authorization')
        if not verify_basic_auth(auth_header, username, password):
            return JSONResponse(
                {'detail': 'Sign in to your Forma workspace.'},
                status_code=401,
                headers={
                    'WWW-Authenticate': 'Basic realm="Forma", charset="UTF-8"',
                    'Cache-Control': 'no-store',
                },
            )

    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin:
        allowed = get_allowed_origins()
        if origin not in allowed:
            return JSONResponse({'detail': 'Origin not allowed.'}, status_code=403)

    response = await call_next(request)

    is_https = request.url.scheme == 'https' or request.headers.get('x-forwarded-proto') == 'https'
    apply_security_headers(response, is_production=settings.is_production, is_https=is_https)

    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'

    return response


@app.exception_handler(sqlite3.Error)
async def database_error_handler(request: Request, exc: sqlite3.Error):
    log.exception('Database operation failed', exc_info=exc)
    return JSONResponse(
        {'detail': 'Unable to save chat history. Check disk space and database permissions.'},
        status_code=500,
    )


def get_conversation_or_404(cid: str) -> dict:
    with connect() as db:
        row = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    return dict(row)


def assert_conversation_idle(cid: str):
    if cid in active:
        if active[cid].done():
            active.pop(cid, None)
        else:
            raise HTTPException(
                status_code=409,
                detail='Stop the current response before changing this conversation.',
            )


def client(provider: str = 'ollama', api_key: str | None = None) -> httpx.AsyncClient:
    """Create HTTPX async client for Ollama or cloud providers."""
    config = get_provider_config(provider)
    base_url = config['base_url'].rstrip('/')
    token = get_api_key(provider, api_key)
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    if provider == 'openrouter':
        headers['HTTP-Referer'] = 'https://forma.local'
        headers['X-Title'] = 'Forma Workspace'
    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=httpx.Timeout(settings.GENERATION_TIMEOUT, connect=10.0),
    )


def format_error_message(exc: Exception, provider: str = 'ollama') -> str:
    config = get_provider_config(provider)
    pname = config['name']
    if isinstance(exc, httpx.ConnectError):
        return f'Unable to connect to {pname}. Check network connectivity and server status.'
    if isinstance(exc, httpx.TimeoutException):
        return 'Generation timed out. Try again or choose a faster model.'
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            err_json = exc.response.json()
            err_msg = err_json.get('error', {}).get('message')
            if err_msg:
                return f"{pname}: {err_msg}"
        except Exception:
            pass
        if exc.response.status_code == 401:
            return f'Invalid API key for {pname}. Please check your key in Settings.'
        if exc.response.status_code == 429:
            return f'Rate limit or quota exceeded for {pname}. Check your billing or account credits.'
        if exc.response.status_code == 404:
            return f'Model not found on {pname}. Please verify the model name or pull it locally.'
        return f'{pname} returned error: {exc.response.text[:200]}'
    if isinstance(exc, ValueError):
        return str(exc)
    return f'Generation failed with {pname}. Please check your configuration and try again.'


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------


@app.get('/api/health')
async def health_check():
    """Health check endpoint used by deployment probes."""
    with connect() as db:
        db.execute('SELECT 1 FROM conversations LIMIT 1').fetchone()
    return {'status': 'ok'}


@app.get('/api/models')
async def list_models(provider: str = 'ollama', api_key: str | None = None):
    """List available models for the specified provider (Ollama, Groq, OpenAI, Gemini, OpenRouter)."""
    p_lower = provider.lower()
    config = get_provider_config(p_lower)
    key = get_api_key(p_lower, api_key)

    providers_summary = [
        {
            "id": pid,
            "name": pdata["name"],
            "default_model": pdata["default_model"],
            "key_url": pdata.get("key_url", ""),
            "has_key": bool(get_api_key(pid, api_key if pid == p_lower else None)),
        }
        for pid, pdata in PROVIDERS.items()
    ]

    if p_lower == 'ollama':
        try:
            try:
                c_cm = client('ollama', key)
            except TypeError:
                c_cm = client()
            async with c_cm as c:
                response = await c.get('/api/tags')
                response.raise_for_status()
            installed = [m['name'] for m in response.json().get('models', [])]
            return {
                'provider': 'ollama',
                'providers': providers_summary,
                'models': installed if installed else [settings.OLLAMA_MODEL],
                'model_details': [
                    {"id": m, "name": m, "badge": "🖥️ Local", "description": "Local offline model"}
                    for m in installed
                ],
                'default': settings.OLLAMA_MODEL if settings.OLLAMA_MODEL in installed else (installed[0] if installed else settings.OLLAMA_MODEL),
            }
        except Exception:
            return {
                'provider': 'ollama',
                'providers': providers_summary,
                'models': [settings.OLLAMA_MODEL],
                'model_details': [
                    {"id": settings.OLLAMA_MODEL, "name": settings.OLLAMA_MODEL, "badge": "🖥️ Local", "description": "Local model"}
                ],
                'default': settings.OLLAMA_MODEL,
            }

    curated = config.get("models", [])
    model_ids = [m["id"] for m in curated]
    return {
        'provider': p_lower,
        'providers': providers_summary,
        'models': model_ids,
        'model_details': curated,
        'default': config["default_model"],
    }


@app.get('/api/conversations')
async def list_conversations(q: str = ''):
    """List conversations with optional title/content search."""
    search_term = f'%{q[:200]}%'
    with connect() as db:
        rows = db.execute(
            '''
            SELECT c.* FROM conversations c
            WHERE c.title LIKE ? OR EXISTS (
                SELECT 1 FROM messages m
                WHERE m.conversation_id = c.id AND m.content LIKE ?
            )
            ORDER BY c.updated_at DESC
            ''',
            (search_term, search_term),
        ).fetchall()
        return [dict(r) for r in rows]


@app.post('/api/conversations', status_code=201)
async def create_conversation():
    """Create a new empty conversation."""
    cid = str(uuid.uuid4())
    stamp = now()
    with connect() as db:
        db.execute(
            'INSERT INTO conversations(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)',
            (cid, 'New chat', stamp, stamp),
        )
    return get_conversation_or_404(cid)


@app.get('/api/conversations/{cid}')
async def get_conversation(cid: str):
    """Retrieve conversation details including all messages."""
    result = get_conversation_or_404(cid)
    with connect() as db:
        messages = db.execute(
            'SELECT * FROM messages WHERE conversation_id = ? ORDER BY id',
            (cid,),
        ).fetchall()
        result['messages'] = [dict(m) for m in messages]
    return result


class RenamePayload(BaseModel):
    title: str = Field(min_length=1, max_length=80)


@app.patch('/api/conversations/{cid}')
async def rename_conversation(cid: str, body: RenamePayload):
    """Rename a conversation title."""
    get_conversation_or_404(cid)
    new_title = body.title.strip()
    if not new_title:
        raise HTTPException(status_code=422, detail='Title cannot be empty.')
    with connect() as db:
        db.execute(
            'UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?',
            (new_title, now(), cid),
        )
    return get_conversation_or_404(cid)


@app.delete('/api/conversations/{cid}')
async def delete_conversation(cid: str):
    """Delete a single conversation."""
    assert_conversation_idle(cid)
    get_conversation_or_404(cid)
    with connect() as db:
        db.execute('DELETE FROM conversations WHERE id = ?', (cid,))
    return {'ok': True}


@app.delete('/api/conversations')
async def clear_all_conversations():
    """Clear all conversations in the workspace."""
    if active:
        raise HTTPException(
            status_code=409,
            detail='Stop generation before clearing chats.',
        )
    with connect() as db:
        db.execute('DELETE FROM conversations')
    return {'ok': True}


@app.post('/api/conversations/{cid}/stop')
async def stop_generation(cid: str):
    """Cancel an active streaming generation."""
    task = active.get(cid)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return {'ok': True}


class ChatPayload(BaseModel):
    conversation_id: str
    content: str = Field(default='', max_length=50000)
    model: str | None = Field(default=None, max_length=200)
    provider: str | None = Field(default='ollama', max_length=50)
    api_key: str | None = Field(default=None, max_length=500)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    regenerate: bool = False
    edit_message_id: int | None = None


@app.post('/api/chat')
async def stream_chat_response(body: ChatPayload):
    """Stream chat completion via Server-Sent Events (SSE)."""
    cid = body.conversation_id
    conv = get_conversation_or_404(cid)
    assert_conversation_idle(cid)

    if not body.regenerate and not body.content.strip():
        raise HTTPException(status_code=422, detail='Write a message first.')

    provider = (body.provider or 'ollama').lower()
    pconfig = get_provider_config(provider)
    api_key = get_api_key(provider, body.api_key)

    if provider != 'ollama' and not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"Please enter your {pconfig['name']} API key in Settings or set {pconfig.get('api_key_env')} in .env.",
        )

    model = body.model or pconfig['default_model']

    with connect() as db:
        if body.edit_message_id is not None:
            target = db.execute(
                "SELECT * FROM messages WHERE id = ? AND conversation_id = ? AND role = 'user'",
                (body.edit_message_id, cid),
            ).fetchone()
            if not target:
                raise HTTPException(status_code=404, detail='User message not found.')
            db.execute('DELETE FROM messages WHERE conversation_id = ? AND id >= ?', (cid, body.edit_message_id))
            db.execute("UPDATE conversations SET summary = '', summary_through = 0 WHERE id = ?", (cid,))
            conv['summary'] = ''
            conv['summary_through'] = 0

        if body.regenerate:
            last = db.execute(
                'SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1',
                (cid,),
            ).fetchone()
            if not last:
                raise HTTPException(status_code=400, detail='No message to regenerate.')
            if last['role'] == 'assistant':
                db.execute('DELETE FROM messages WHERE id = ?', (last['id'],))
            remaining_count = db.execute(
                'SELECT COUNT(*) FROM messages WHERE conversation_id = ?',
                (cid,),
            ).fetchone()[0]
            if remaining_count == 0:
                raise HTTPException(status_code=400, detail='No message to regenerate.')
        else:
            db.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                (cid, body.content.strip(), now()),
            )
            if conv['title'] == 'New chat':
                auto_title = ' '.join(body.content.strip().split()[:8])[:60]
                db.execute('UPDATE conversations SET title = ? WHERE id = ?', (auto_title, cid))

        history = [
            dict(r)
            for r in db.execute(
                'SELECT * FROM messages WHERE conversation_id = ? ORDER BY id',
                (cid,),
            ).fetchall()
        ]

        mid = db.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at, status, model) VALUES (?, 'assistant', '', ?, 'generating', ?)",
            (cid, now(), model),
        ).lastrowid
        db.execute('UPDATE conversations SET updated_at = ? WHERE id = ?', (now(), cid))

    queue: asyncio.Queue = asyncio.Queue(maxsize=128)

    async def emit(kind: str, **data):
        await queue.put({'type': kind, **data})

    async def generate():
        text = ''
        status = 'stopped'
        is_cloud = provider != 'ollama'
        try:
            await emit('start', message_id=mid)
            try:
                client_instance = client(provider, api_key)
            except TypeError:
                client_instance = client()

            async with client_instance as c:
                def save_summary(summary_text: str, through_id: int):
                    with connect() as db:
                        db.execute(
                            'UPDATE conversations SET summary = ?, summary_through = ? WHERE id = ?',
                            (summary_text, through_id, cid),
                        )

                async def notify(message: str):
                    await emit('status', message=message)

                context = await build_context(
                    c,
                    model,
                    conv,
                    history,
                    save_summary,
                    notify,
                    is_openai_format=is_cloud,
                )

                if is_cloud:
                    # OpenAI-compatible streaming (Groq, OpenAI, Gemini, OpenRouter)
                    async with c.stream(
                        'POST',
                        '/chat/completions',
                        json={
                            'model': model,
                            'messages': context,
                            'stream': True,
                            'temperature': body.temperature,
                        },
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            line_str = line.strip()
                            if line_str.startswith('data: '):
                                payload_str = line_str[6:].strip()
                                if payload_str == '[DONE]':
                                    status = 'complete'
                                    break
                                try:
                                    item = json.loads(payload_str)
                                    choices = item.get('choices', [])
                                    if choices:
                                        delta = choices[0].get('delta', {}).get('content', '')
                                        if delta:
                                            text += delta
                                            await emit('token', content=delta)
                                except json.JSONDecodeError:
                                    continue
                        status = 'complete'
                else:
                    # Native Ollama streaming
                    async with c.stream(
                        'POST',
                        '/api/chat',
                        json={
                            'model': model,
                            'messages': context,
                            'stream': True,
                            'options': {
                                'temperature': body.temperature,
                                'num_ctx': settings.CONTEXT_TOKENS,
                                'num_predict': settings.OUTPUT_TOKENS,
                            },
                        },
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            item = json.loads(line)
                            if item.get('error'):
                                raise ValueError(
                                    'Ollama could not generate a response. Check the selected model and server logs.'
                                )
                            delta = item.get('message', {}).get('content', '')
                            if delta:
                                text += delta
                                await emit('token', content=delta)
                            if item.get('done'):
                                status = 'complete'
                                break

                    if status != 'complete':
                        raise ValueError('The model connection closed early. You can retry this response.')

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            status = 'error'
            log.exception('Generation failed')
            await emit('error', message=format_error_message(exc, provider))
        finally:
            try:
                with connect() as db:
                    db.execute(
                        'UPDATE messages SET content = ?, status = ? WHERE id = ?',
                        (text, status, mid),
                    )
                    db.execute('UPDATE conversations SET updated_at = ? WHERE id = ?', (now(), cid))
            finally:
                active.pop(cid, None)
                try:
                    queue.put_nowait({'type': 'done', status: status})
                except asyncio.QueueFull:
                    pass

    task = asyncio.create_task(generate())
    active[cid] = task

    async def event_stream():
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    if task.done():
                        break
                    yield ': keepalive\n\n'
                    continue

                yield f'data: {json.dumps(item)}\n\n'
                if item.get('type') == 'done':
                    break
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


# Serve built frontend static files in production
dist_path = ROOT / 'frontend' / 'dist'
if dist_path.exists():
    app.mount('/', StaticFiles(directory=dist_path, html=True), name='frontend')

import asyncio
import base64
import json
import logging
import os
import shutil
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, settings
from .context import build_context
from .database import connect, initialize
from .extractors import check_vision_support, extract_file_content, sanitize_filename, validate_file_type
from .providers import (
    PROVIDERS,
    get_api_key,
    get_provider_config,
    is_provider_configured,
    probe_provider_health,
)
from .search import SearchError, format_search_context, perform_search
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
            log.critical(
                'FATAL: Production requires AUTH_USERNAME and AUTH_PASSWORD (at least 16 characters). '
                'AUTH_USERNAME: %r, AUTH_PASSWORD length: %d',
                settings.AUTH_USERNAME,
                len(settings.AUTH_PASSWORD),
            )
            raise RuntimeError(
                'Production requires AUTH_USERNAME and AUTH_PASSWORD (at least 16 characters).'
            )
        configured_any = any(is_provider_configured(p) for p in PROVIDERS)
        if not configured_any:
            log.critical(
                'FATAL: Production requires at least one configured AI provider. '
                'Set GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY, or OLLAMA_BASE_URL.'
            )
            raise RuntimeError(
                'Production requires at least one configured AI provider. '
                'Set GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY, or OLLAMA_BASE_URL.'
            )

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


def client(provider: str = 'groq') -> httpx.AsyncClient:
    """Create HTTPX async client for Ollama or cloud providers."""
    config = get_provider_config(provider)
    if provider == 'ollama':
        base_url = (os.getenv('OLLAMA_BASE_URL') or 'http://localhost:11434').rstrip('/')
    else:
        base_url = config['base_url'].rstrip('/')

    token = get_api_key(provider)
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    if provider == 'openrouter':
        headers['HTTP-Referer'] = 'https://forma.local'
        headers['X-Title'] = 'Forma'
    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=httpx.Timeout(settings.GENERATION_TIMEOUT, connect=10.0),
    )


def format_error_message(exc: Exception, provider: str = 'groq') -> str:
    config = get_provider_config(provider)
    pname = config['name']
    if isinstance(exc, httpx.ConnectError):
        if provider == 'ollama':
            url = os.getenv('OLLAMA_BASE_URL') or 'http://localhost:11434'
            return f'Unable to connect to Ollama at {url}. Ensure Ollama is running and accessible.'
        return f'Unable to connect to {pname}. Check network connectivity and server status.'
    if isinstance(exc, httpx.TimeoutException):
        return f'{pname} generation timed out. Try again or choose a faster model.'
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        err_msg = ""
        try:
            err_json = exc.response.json()
            if isinstance(err_json, dict):
                err_msg = err_json.get('error', {}).get('message', '') or err_json.get('detail', '')
            elif isinstance(err_json, list) and err_json and isinstance(err_json[0], dict):
                err_msg = err_json[0].get('error', {}).get('message', '')
        except Exception:
            try:
                err_msg = exc.response.text[:200]
            except Exception:
                err_msg = ""

        if status_code == 401:
            return f'Invalid or revoked API key for {pname}. Please check {config.get("api_key_env")} in server settings.'
        if status_code == 429:
            if 'credit' in err_msg.lower() or 'quota' in err_msg.lower() or 'billing' in err_msg.lower():
                return f'Quota exceeded for {pname}: You have no credits remaining. Please check your account billing.'
            return f'Rate limit exceeded for {pname}. Please wait a moment and try again.'
        if status_code == 404:
            return f'Model not found on {pname}. {err_msg or "Please select another model in settings."}'
        if status_code in (502, 503, 504):
            return f'{pname} is currently experiencing high demand or an outage ({status_code}). Please try again shortly or switch to another provider.'
        if err_msg:
            return f'{pname} returned error ({status_code}): {err_msg}'
        return f'{pname} request failed with status {status_code}.'
    if isinstance(exc, ValueError):
        return str(exc)
    return f'Generation failed with {pname}. Please try again.'


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
async def list_models(provider: str | None = None, refresh: bool = False):
    """
    List available models and configured providers.
    Probes provider health so only working, configured providers are presented.
    """
    all_configured = [pid for pid in PROVIDERS if is_provider_configured(pid)]
    if not all_configured:
        all_configured = ['ollama']

    # Probe all configured providers in parallel
    health_results = await asyncio.gather(
        *(probe_provider_health(pid, force=refresh) for pid in all_configured)
    )
    health_by_pid = {pid: h for pid, h in zip(all_configured, health_results)}

    providers_summary = []
    working_providers = []
    for pid in all_configured:
        pdata = PROVIDERS[pid]
        h = health_by_pid[pid]
        if h["working"]:
            working_providers.append(pid)
        providers_summary.append({
            "id": pid,
            "name": pdata["name"],
            "tagline": pdata.get("tagline", ""),
            "configured": h["configured"],
            "working": h["working"],
            "status": h["status"],
            "error": h["error"],
            "default_model": pdata["default_model"],
            "key_url": pdata.get("key_url", ""),
        })

    # Pick active provider: explicitly requested provider if valid, else first working, else first configured
    req_p = (provider or "").lower().strip()
    if req_p in PROVIDERS:
        active_p = req_p
    elif working_providers:
        active_p = working_providers[0]
    else:
        active_p = all_configured[0]

    pconfig = PROVIDERS[active_p]
    phealth = health_by_pid.get(active_p, {})

    if active_p == 'ollama':
        installed = phealth.get('models', [])
        models = installed if installed else [settings.OLLAMA_MODEL]
        details = [
            {"id": m, "name": m, "badge": "🖥️ Local", "description": "Local offline model"}
            for m in models
        ]
        default_m = settings.OLLAMA_MODEL if settings.OLLAMA_MODEL in models else (models[0] if models else settings.OLLAMA_MODEL)
    else:
        curated = pconfig.get("models", [])
        models = [m["id"] for m in curated]
        details = curated
        default_m = pconfig["default_model"]

    return {
        "provider": active_p,
        "providers": providers_summary,
        "models": models,
        "model_details": details,
        "default": default_m,
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
    """Retrieve conversation details including all messages, attachments, and web sources."""
    result = get_conversation_or_404(cid)
    with connect() as db:
        messages = db.execute(
            'SELECT * FROM messages WHERE conversation_id = ? ORDER BY id',
            (cid,),
        ).fetchall()

        attachments = db.execute(
            '''
            SELECT id, conversation_id, message_id, filename, content_type,
                   size_bytes, page_count, is_image, created_at
            FROM attachments WHERE conversation_id = ? ORDER BY created_at
            ''',
            (cid,),
        ).fetchall()

        attachments_by_msg: dict[int, list[dict]] = {}
        for a in attachments:
            ad = dict(a)
            mid = ad.get('message_id')
            if mid:
                attachments_by_msg.setdefault(mid, []).append(ad)

        parsed_messages = []
        for m in messages:
            md = dict(m)
            raw_sources = md.get('sources')
            if raw_sources:
                try:
                    md['sources'] = json.loads(raw_sources)
                except Exception:
                    md['sources'] = []
            else:
                md['sources'] = []
            md['attachments'] = attachments_by_msg.get(md['id'], [])
            parsed_messages.append(md)

        result['messages'] = parsed_messages
        result['pending_attachments'] = [
            dict(a) for a in attachments if a['message_id'] is None
        ]
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
    """Delete a single conversation and its associated files."""
    assert_conversation_idle(cid)
    get_conversation_or_404(cid)
    with connect() as db:
        db.execute('DELETE FROM conversations WHERE id = ?', (cid,))

    # Clean up associated files on disk
    cid_folder = settings.ATTACHMENTS_DIR / cid
    if cid_folder.exists():
        shutil.rmtree(cid_folder, ignore_errors=True)
    return {'ok': True}


@app.delete('/api/conversations')
async def clear_all_conversations():
    """Clear all conversations and all stored attachment files."""
    if active:
        raise HTTPException(
            status_code=409,
            detail='Stop generation before clearing chats.',
        )
    with connect() as db:
        db.execute('DELETE FROM conversations')

    # Remove all attachment files on disk
    if settings.ATTACHMENTS_DIR.exists():
        for item in settings.ATTACHMENTS_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            elif item.is_file():
                try:
                    item.unlink()
                except OSError:
                    pass
    return {'ok': True}


@app.post('/api/conversations/{cid}/attachments', status_code=201)
async def upload_attachment(cid: str, file: UploadFile = File(...)):
    """Upload and validate an attachment for a conversation."""
    get_conversation_or_404(cid)
    assert_conversation_idle(cid)

    if not file.filename:
        raise HTTPException(status_code=400, detail='Missing filename.')

    try:
        ext = validate_file_type(file.filename)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    content = await file.read()
    if len(content) > settings.MAX_ATTACHMENT_SIZE_BYTES:
        mb = settings.MAX_ATTACHMENT_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f'File size exceeds the {mb}MB limit. Please upload a smaller file.'
        )

    safe_name = sanitize_filename(file.filename)
    aid = str(uuid.uuid4())
    conv_dir = settings.ATTACHMENTS_DIR / cid
    conv_dir.mkdir(parents=True, exist_ok=True)
    file_path = conv_dir / f"{aid}_{safe_name}"

    with open(file_path, 'wb') as f:
        f.write(content)

    try:
        extracted_text, page_count, is_image = extract_file_content(file_path, safe_name)
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f'Failed to process file: {e}')

    stamp = now()
    content_type = file.content_type or 'application/octet-stream'

    with connect() as db:
        db.execute(
            '''
            INSERT INTO attachments (
                id, conversation_id, filename, content_type, size_bytes,
                file_path, created_at, extracted_text, page_count, is_image
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                aid, cid, safe_name, content_type, len(content),
                str(file_path), stamp, extracted_text, page_count, 1 if is_image else 0
            ),
        )

    return {
        'id': aid,
        'conversation_id': cid,
        'filename': safe_name,
        'content_type': content_type,
        'size_bytes': len(content),
        'page_count': page_count,
        'is_image': is_image,
        'created_at': stamp,
    }


@app.get('/api/conversations/{cid}/attachments')
async def list_attachments(cid: str):
    """List attachments for a conversation."""
    get_conversation_or_404(cid)
    with connect() as db:
        rows = db.execute(
            '''
            SELECT id, conversation_id, message_id, filename, content_type,
                   size_bytes, page_count, is_image, created_at
            FROM attachments WHERE conversation_id = ? ORDER BY created_at
            ''',
            (cid,),
        ).fetchall()
        return [dict(r) for r in rows]


@app.delete('/api/conversations/{cid}/attachments/{aid}')
async def delete_attachment(cid: str, aid: str):
    """Delete an attachment from database and disk."""
    get_conversation_or_404(cid)
    with connect() as db:
        row = db.execute(
            'SELECT file_path FROM attachments WHERE id = ? AND conversation_id = ?',
            (aid, cid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Attachment not found.')
        db.execute('DELETE FROM attachments WHERE id = ?', (aid,))

    try:
        p = Path(row['file_path'])
        if p.exists():
            p.unlink()
    except OSError:
        pass

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
    attachment_ids: list[str] = Field(default_factory=list)
    web_search: bool = False



@app.post('/api/chat')
async def stream_chat_response(body: ChatPayload):
    """Stream chat completion via Server-Sent Events (SSE)."""
    cid = body.conversation_id
    conv = get_conversation_or_404(cid)
    assert_conversation_idle(cid)

    # Attachments validation
    attachments = []
    if body.attachment_ids:
        with connect() as db:
            placeholders = ','.join('?' * len(body.attachment_ids))
            rows = db.execute(
                f'SELECT * FROM attachments WHERE id IN ({placeholders}) AND conversation_id = ?',
                (*body.attachment_ids, cid),
            ).fetchall()
            attachments = [dict(r) for r in rows]

    if not body.regenerate and not body.content.strip() and not attachments:
        raise HTTPException(status_code=422, detail='Write a message or attach a file first.')

    provider = (body.provider or '').lower().strip()
    if not provider:
        configured = [p for p in PROVIDERS if is_provider_configured(p)]
        provider = configured[0] if configured else 'groq'

    pconfig = get_provider_config(provider)
    if not is_provider_configured(provider):
        raise HTTPException(
            status_code=400,
            detail=f"{pconfig['name']} is not configured on this server. Set the {pconfig.get('api_key_env')} API key in server environment variables.",
        )

    if provider != 'ollama':
        api_key = get_api_key(provider)
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail=f"Missing API key for {pconfig['name']}. Set {pconfig.get('api_key_env')} in server environment variables.",
            )

    model = body.model or pconfig['default_model']

    # Vision capability check
    image_attachments = [a for a in attachments if a['is_image']]
    if image_attachments:
        is_supported, explanation = check_vision_support(provider, model)
        if not is_supported:
            raise HTTPException(status_code=400, detail=explanation)

    # Web search handling
    search_results = []
    search_context = ''
    if body.web_search:
        search_query = body.content.strip()
        if not search_query and attachments:
            search_query = attachments[0]['filename']
        if not search_query:
            raise HTTPException(status_code=400, detail='Please enter a query for web search.')

        try:
            search_results = await perform_search(search_query, max_results=5)
            search_context = format_search_context(search_query, search_results)
        except SearchError as se:
            raise HTTPException(
                status_code=502,
                detail=f'Web search failed: {se}. Generation stopped to avoid inventing search results.',
            )

    # Build prompt content
    user_text = body.content.strip()
    attachment_texts = [a['extracted_text'] for a in attachments if not a['is_image'] and a.get('extracted_text')]
    if attachment_texts:
        docs_block = '\n\n'.join(attachment_texts)
        if user_text:
            full_user_content = f'{user_text}\n\n[Attached Files & Context]:\n{docs_block}'
        else:
            full_user_content = f'[Attached Files & Context]:\n{docs_block}'
    else:
        full_user_content = user_text or (f"Analyze {attachments[0]['filename']}" if attachments else '')

    if search_context:
        full_user_content = f'{search_context}\n\nUser Question:\n{full_user_content}'

    # Load base64 for images
    image_b64s = []
    for img in image_attachments:
        try:
            with open(img['file_path'], 'rb') as f:
                image_b64s.append(base64.b64encode(f.read()).decode('ascii'))
        except Exception as e:
            log.warning('Failed to load image %s: %s', img['file_path'], e)

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
            display_user_text = body.content.strip() or (f"Analyze {attachments[0]['filename']}" if attachments else 'Uploaded files')
            uid = db.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at, web_search) VALUES (?, 'user', ?, ?, ?)",
                (cid, display_user_text, now(), 1 if body.web_search else 0),
            ).lastrowid

            if body.attachment_ids:
                placeholders = ','.join('?' * len(body.attachment_ids))
                db.execute(
                    f'UPDATE attachments SET message_id = ? WHERE id IN ({placeholders}) AND conversation_id = ?',
                    (uid, *body.attachment_ids, cid),
                )

            if conv['title'] == 'New chat':
                auto_title = ' '.join(display_user_text.split()[:8])[:60]
                db.execute('UPDATE conversations SET title = ? WHERE id = ?', (auto_title, cid))

        history = [
            dict(r)
            for r in db.execute(
                'SELECT * FROM messages WHERE conversation_id = ? ORDER BY id',
                (cid,),
            ).fetchall()
        ]
        # In the context history, the last user turn incorporates the attachments and search
        if history and history[-1]['role'] == 'user':
            history[-1]['content'] = full_user_content

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
            if search_results:
                await emit('sources', sources=search_results)

            try:
                client_instance = client(provider)
            except Exception as e:
                log.exception("Failed to initialize client for %s: %s", provider, e)
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
                    cloud_messages = [dict(m) for m in context]
                    if image_b64s and cloud_messages:
                        last_text = cloud_messages[-1]['content']
                        multimodal_content = [{'type': 'text', 'text': last_text}]
                        for img, b64 in zip(image_attachments, image_b64s):
                            multimodal_content.append({
                                'type': 'image_url',
                                'image_url': {'url': f"data:{img['content_type']};base64,{b64}"}
                            })
                        cloud_messages[-1]['content'] = multimodal_content

                    # OpenAI-compatible streaming (Groq, OpenAI, Gemini, OpenRouter)
                    async with c.stream(
                        'POST',
                        '/chat/completions',
                        json={
                            'model': model,
                            'messages': cloud_messages,
                            'stream': True,
                            'temperature': body.temperature,
                        },
                    ) as response:
                        if response.status_code >= 400:
                            await response.aread()
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
                    ollama_messages = [dict(m) for m in context]
                    if image_b64s and ollama_messages:
                        ollama_messages[-1]['images'] = image_b64s

                    async with c.stream(
                        'POST',
                        '/api/chat',
                        json={
                            'model': model,
                            'messages': ollama_messages,
                            'stream': True,
                            'options': {
                                'temperature': body.temperature,
                                'num_ctx': settings.CONTEXT_TOKENS,
                                'num_predict': settings.OUTPUT_TOKENS,
                            },
                        },
                    ) as response:
                        if response.status_code >= 400:
                            await response.aread()
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
                        'UPDATE messages SET content = ?, status = ?, sources = ? WHERE id = ?',
                        (text, status, json.dumps(search_results) if search_results else None, mid),
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

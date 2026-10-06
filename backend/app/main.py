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
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, settings
from .context import build_context
from .database import connect, initialize
from .extractors import check_vision_support, extract_file_content, sanitize_filename, validate_file_type
from .providers import (
    PROVIDERS,
    get_api_key,
    get_ollama_model_detail,
    get_provider_config,
    is_provider_configured,
    probe_provider_health,
)
from .search import SearchError, format_search_context, perform_search
from .security import (
    apply_security_headers,
    check_rate_limit,
    generate_csrf_token,
    generate_visitor_id,
    get_allowed_origins,
    get_client_ip,
    sign_session_token,
    verify_basic_auth,
    verify_session_token,
)

log = logging.getLogger('forma')

# Active generation tasks mapped by conversation ID and owner visitor ID
active: dict[str, asyncio.Task] = {}
active_task_owners: dict[str, str] = {}


def now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown management."""
    if settings.is_production:
        # Authentication is optional for public workspaces.
        # If credentials are configured, enforce strict minimum 16-character password security.
        if settings.AUTH_USERNAME or settings.AUTH_PASSWORD:
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
            log.warning(
                'Production warning: No AI provider is configured in environment. '
                'Set GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY, or OLLAMA_BASE_URL to enable AI completions.'
            )

        # Validate that SESSION_SECRET is stable and persisted on /var/data before serving traffic
        _ = settings.SESSION_SECRET

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
    Unified enterprise security middleware:
    - Enforces HTTPS upgrade when behind a proxy
    - Resolves and verifies cryptographically signed visitor session cookie (or creates new)
    - Enforces multi-dimensional rate limiting & AI spending controls (per-IP and per-visitor)
    - Enforces constant-time HTTP Basic Auth if credentials are configured
    - Enforces Origin and CSRF validation for state-modifying requests
    - Attaches comprehensive security hardening headers (HSTS, CSP, X-Frame-Options, XSS)
    - Sets secure, HttpOnly, SameSite session cookies on responses
    """
    if settings.is_production and request.headers.get('x-forwarded-proto') == 'http':
        https_url = request.url.replace(scheme='https')
        return RedirectResponse(str(https_url), status_code=308)

    # 1. Visitor Session & CSRF Resolution
    session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    visitor_id = verify_session_token(session_cookie)
    new_session = False
    if not visitor_id:
        visitor_id = generate_visitor_id()
        new_session = True
    request.state.visitor_id = visitor_id
    request.state.new_session = new_session

    csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
    new_csrf = False
    if not csrf_cookie or len(csrf_cookie) < 16:
        csrf_cookie = generate_csrf_token()
        new_csrf = True
    request.state.csrf_token = csrf_cookie
    request.state.new_csrf = new_csrf

    # 2. Rate limiting defense (per-IP and per-visitor spending control)
    if request.url.path != '/api/health':
        client_ip = get_client_ip(request)
        is_allowed, retry_after, detail = check_rate_limit(
            client_ip, visitor_id, request.url.path, return_detail=True
        )
        if not is_allowed:
            return JSONResponse(
                {'detail': detail or 'Rate limit exceeded. Please wait a moment before sending more requests.'},
                status_code=429,
                headers={
                    'Retry-After': str(retry_after),
                    'Cache-Control': 'no-store',
                },
            )

    # 3. Optional HTTP Basic Auth: only enforced if credentials configured and not public mode
    is_public = os.getenv('FORMA_PUBLIC_MODE', '').lower() in ('1', 'true', 'yes')
    username = settings.AUTH_USERNAME
    password = settings.AUTH_PASSWORD
    if not is_public and username and password and request.url.path != '/api/health':
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

    # 4. Origin & CSRF validation for state-modifying requests
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        allowed = get_allowed_origins()
        if origin:
            if origin not in allowed:
                return JSONResponse({'detail': 'Origin not allowed.'}, status_code=403)
        else:
            referer = request.headers.get('referer')
            if referer:
                try:
                    import urllib.parse
                    parsed_ref = urllib.parse.urlparse(referer)
                    ref_origin = f"{parsed_ref.scheme}://{parsed_ref.netloc}"
                    if ref_origin not in allowed:
                        return JSONResponse({'detail': 'Origin not allowed.'}, status_code=403)
                except Exception:
                    pass

        # Validate CSRF token if header provided
        header_csrf = request.headers.get('x-csrf-token')
        if header_csrf and csrf_cookie:
            import secrets
            if not secrets.compare_digest(header_csrf, csrf_cookie):
                return JSONResponse({'detail': 'Invalid CSRF token.'}, status_code=403)

    response = await call_next(request)

    is_https = request.url.scheme == 'https' or request.headers.get('x-forwarded-proto') == 'https'
    is_secure = is_https

    # Set session cookie if new or rotated
    if request.state.new_session:
        signed_token = sign_session_token(visitor_id)
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=signed_token,
            max_age=settings.SESSION_MAX_AGE_SECONDS,
            httponly=True,
            samesite='lax',
            secure=is_secure,
            path='/',
        )

    # Set CSRF cookie if new or rotated
    if request.state.new_csrf:
        response.set_cookie(
            key=settings.CSRF_COOKIE_NAME,
            value=csrf_cookie,
            max_age=settings.SESSION_MAX_AGE_SECONDS,
            httponly=False,
            samesite='lax',
            secure=is_secure,
            path='/',
        )

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


def get_conversation_or_404(cid: str, visitor_id: str) -> dict:
    if not visitor_id or visitor_id == '__legacy_archive__':
        raise HTTPException(status_code=404, detail='Conversation not found.')
    with connect() as db:
        row = db.execute(
            'SELECT * FROM conversations WHERE id = ? AND visitor_id = ?',
            (cid, visitor_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    return dict(row)


def assert_conversation_idle(cid: str):
    if cid in active:
        if active[cid].done():
            active.pop(cid, None)
            active_task_owners.pop(cid, None)
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
                err_val = err_json.get('error')
                if isinstance(err_val, dict):
                    err_msg = err_val.get('message', '') or str(err_val)
                elif isinstance(err_val, str):
                    err_msg = err_val
                elif err_json.get('detail'):
                    err_msg = str(err_json.get('detail'))
            elif isinstance(err_json, list) and err_json and isinstance(err_json[0], dict):
                err_val = err_json[0].get('error')
                if isinstance(err_val, dict):
                    err_msg = err_val.get('message', '')
                elif isinstance(err_val, str):
                    err_msg = err_val
        except Exception:
            try:
                raw_text = exc.response.text.strip()
                if not raw_text.startswith(('<', '<!DOCTYPE', '<html', '<head', '<body')):
                    err_msg = raw_text[:200]
            except Exception:
                err_msg = ""

        if status_code == 401:
            return f'Invalid or revoked API key for {pname}. Please check {config.get("api_key_env")} in server settings.'
        if status_code == 403:
            return f'Access forbidden by {pname} (403). Check API key permissions and regional availability.'
        if status_code == 429:
            if 'credit' in err_msg.lower() or 'quota' in err_msg.lower() or 'billing' in err_msg.lower():
                return f'Quota exceeded for {pname}: You have no credits remaining. Please check your account billing.'
            return f'Rate limit exceeded for {pname}. Please wait a moment and try again.'
        if status_code == 404:
            return f'Model not found on {pname}. {err_msg or "Please select another model in settings."}'
        if status_code == 413:
            return f'Request payload too large for {pname}. Try reducing attached files or conversation length.'
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

        p_models = []
        if pid == 'ollama':
            installed = h.get('models', [])
            raw_models = installed if installed else ([settings.OLLAMA_MODEL] if not h["working"] else [])
            for m in raw_models:
                p_models.append(get_ollama_model_detail(m))
        else:
            p_models = [dict(m) for m in pdata.get("models", [])]

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
            "models": p_models,
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
        models = installed if installed else ([settings.OLLAMA_MODEL] if not phealth.get("working") else [])
        details = [get_ollama_model_detail(m) for m in models]
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
        "auto": {
            "id": "auto",
            "name": "Auto",
            "badge": "✨ Smart Routing",
            "description": "Intelligently chooses the best model for chat, coding, search, documents, or images.",
        },
    }



@app.get('/api/conversations')
async def list_conversations(request: Request, q: str = ''):
    """List conversations for the current visitor with optional title/content search."""
    visitor_id = request.state.visitor_id
    search_term = f'%{q[:200]}%'
    with connect() as db:
        rows = db.execute(
            '''
            SELECT c.* FROM conversations c
            WHERE c.visitor_id = ? AND (
                c.title LIKE ? OR EXISTS (
                    SELECT 1 FROM messages m
                    WHERE m.conversation_id = c.id AND m.content LIKE ?
                )
            )
            ORDER BY c.updated_at DESC
            ''',
            (visitor_id, search_term, search_term),
        ).fetchall()
        return [dict(r) for r in rows]


@app.post('/api/conversations', status_code=201)
async def create_conversation(request: Request):
    """Create a new empty conversation for the current visitor."""
    visitor_id = request.state.visitor_id
    with connect() as db:
        count = db.execute(
            'SELECT COUNT(*) FROM conversations WHERE visitor_id = ?',
            (visitor_id,),
        ).fetchone()[0]
        if count >= settings.MAX_CONVERSATIONS_PER_VISITOR:
            raise HTTPException(
                status_code=400,
                detail=f'Conversation limit of {settings.MAX_CONVERSATIONS_PER_VISITOR} reached for this session. Please delete older chats.',
            )
        cid = str(uuid.uuid4())
        stamp = now()
        db.execute(
            'INSERT INTO conversations(id, title, created_at, updated_at, visitor_id) VALUES (?, ?, ?, ?, ?)',
            (cid, 'New chat', stamp, stamp, visitor_id),
        )
    return get_conversation_or_404(cid, visitor_id)


@app.get('/api/conversations/{cid}')
async def get_conversation(cid: str, request: Request):
    """Retrieve conversation details including all messages, attachments, and web sources."""
    visitor_id = request.state.visitor_id
    result = get_conversation_or_404(cid, visitor_id)
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
async def rename_conversation(cid: str, body: RenamePayload, request: Request):
    """Rename a conversation title."""
    visitor_id = request.state.visitor_id
    get_conversation_or_404(cid, visitor_id)
    new_title = body.title.strip()
    if not new_title:
        raise HTTPException(status_code=422, detail='Title cannot be empty.')
    with connect() as db:
        db.execute(
            'UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND visitor_id = ?',
            (new_title, now(), cid, visitor_id),
        )
    return get_conversation_or_404(cid, visitor_id)


@app.delete('/api/conversations/{cid}')
async def delete_conversation(cid: str, request: Request):
    """Delete a single conversation and its associated files."""
    visitor_id = request.state.visitor_id
    assert_conversation_idle(cid)
    get_conversation_or_404(cid, visitor_id)
    with connect() as db:
        db.execute('DELETE FROM conversations WHERE id = ? AND visitor_id = ?', (cid, visitor_id))

    # Clean up associated files on disk
    cid_folder = settings.ATTACHMENTS_DIR / cid
    if cid_folder.exists():
        shutil.rmtree(cid_folder, ignore_errors=True)
    return {'ok': True}


@app.delete('/api/conversations')
async def clear_all_conversations(request: Request):
    """Clear all conversations and all stored attachment files for the current visitor."""
    visitor_id = request.state.visitor_id
    with connect() as db:
        rows = db.execute(
            'SELECT id FROM conversations WHERE visitor_id = ?',
            (visitor_id,),
        ).fetchall()
        cids = [r['id'] for r in rows]
        if not cids:
            return {'ok': True}

        # Check if any conversation belonging to this visitor is actively generating
        for cid in cids:
            if cid in active and not active[cid].done():
                raise HTTPException(
                    status_code=409,
                    detail='Stop active generation before clearing chats.',
                )

        db.execute('DELETE FROM conversations WHERE visitor_id = ?', (visitor_id,))

    # Remove ONLY this visitor's attachment folders
    for cid in cids:
        cid_folder = settings.ATTACHMENTS_DIR / cid
        if cid_folder.exists():
            shutil.rmtree(cid_folder, ignore_errors=True)

    return {'ok': True}


@app.post('/api/conversations/{cid}/attachments', status_code=201)
async def upload_attachment(cid: str, request: Request, file: UploadFile = File(...)):
    """Upload and validate an attachment for a conversation."""
    visitor_id = request.state.visitor_id
    get_conversation_or_404(cid, visitor_id)
    assert_conversation_idle(cid)

    # Check conversation attachment count
    with connect() as db:
        att_count = db.execute(
            'SELECT COUNT(*) FROM attachments WHERE conversation_id = ?',
            (cid,),
        ).fetchone()[0]
        if att_count >= settings.MAX_ATTACHMENTS_PER_CONVERSATION:
            raise HTTPException(
                status_code=400,
                detail=f'Maximum of {settings.MAX_ATTACHMENTS_PER_CONVERSATION} attachments per conversation reached.',
            )
        # Check total visitor storage usage
        total_stored = db.execute(
            '''
            SELECT COALESCE(SUM(a.size_bytes), 0)
            FROM attachments a
            JOIN conversations c ON a.conversation_id = c.id
            WHERE c.visitor_id = ?
            ''',
            (visitor_id,),
        ).fetchone()[0]

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
            detail=f'File size exceeds the {mb}MB limit. Please upload a smaller file.',
        )

    if total_stored + len(content) > settings.MAX_VISITOR_STORAGE_BYTES:
        mb = settings.MAX_VISITOR_STORAGE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f'Storage limit of {mb}MB exceeded for this session. Please delete old files or conversations to free up space.',
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
async def list_attachments(cid: str, request: Request):
    """List attachments for a conversation."""
    visitor_id = request.state.visitor_id
    get_conversation_or_404(cid, visitor_id)
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


@app.get('/api/conversations/{cid}/attachments/{aid}')
@app.get('/api/conversations/{cid}/attachments/{aid}/download')
async def download_attachment(cid: str, aid: str, request: Request):
    """Download an attachment file belonging to the current visitor's conversation."""
    visitor_id = request.state.visitor_id
    get_conversation_or_404(cid, visitor_id)
    with connect() as db:
        row = db.execute(
            'SELECT file_path, filename, content_type FROM attachments WHERE id = ? AND conversation_id = ?',
            (aid, cid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Attachment not found.')

    file_path = Path(row['file_path'])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail='Attachment file not found on disk.')

    return FileResponse(
        path=str(file_path),
        filename=row['filename'],
        media_type=row['content_type'],
    )


@app.delete('/api/conversations/{cid}/attachments/{aid}')
async def delete_attachment(cid: str, aid: str, request: Request):
    """Delete an attachment from database and disk."""
    visitor_id = request.state.visitor_id
    get_conversation_or_404(cid, visitor_id)
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
async def stop_generation(cid: str, request: Request):
    """Cancel an active streaming generation."""
    visitor_id = request.state.visitor_id
    get_conversation_or_404(cid, visitor_id)
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
async def stream_chat_response(body: ChatPayload, request: Request):
    """Stream chat completion via Server-Sent Events (SSE)."""
    visitor_id = request.state.visitor_id
    cid = body.conversation_id
    conv = get_conversation_or_404(cid, visitor_id)
    assert_conversation_idle(cid)

    # Concurrency check per visitor
    v_active = [
        c for c, t in active.items()
        if not t.done() and active_task_owners.get(c) == visitor_id
    ]
    if len(v_active) >= settings.MAX_CONCURRENT_PER_VISITOR:
        raise HTTPException(
            status_code=429,
            detail='A generation is already in progress for your session. Please wait or stop the current generation.',
        )

    # Global concurrency check
    g_active = [c for c, t in active.items() if not t.done()]
    if len(g_active) >= settings.MAX_CONCURRENT_GLOBAL:
        raise HTTPException(
            status_code=429,
            detail='The server is currently processing the maximum number of concurrent requests. Please try again in a few seconds.',
        )

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
            if len(attachments) != len(body.attachment_ids):
                raise HTTPException(status_code=404, detail='One or more attachments not found.')

    if not body.regenerate and not body.content.strip() and not attachments:
        raise HTTPException(status_code=422, detail='Write a message or attach a file first.')

    image_attachments = [a for a in attachments if a['is_image']]
    doc_attachments = [a for a in attachments if not a['is_image']]
    has_images = bool(image_attachments)
    has_docs = bool(doc_attachments)

    req_provider = (body.provider or '').lower().strip()
    req_model = (body.model or '').strip()
    # Auto routing applies when both provider and model are auto/empty, or model is explicitly 'auto' without a specific provider
    is_auto = (req_provider in ('', 'auto') and req_model.lower() in ('', 'auto')) or (req_provider in ('', 'auto') and not req_model) or req_model.lower() == 'auto'

    auto_explanation = ""
    if is_auto:
        configured_providers = [p for p in PROVIDERS if is_provider_configured(p)]
        from .providers import select_auto_model
        try:
            provider, model, auto_explanation = select_auto_model(
                has_images=has_images,
                has_documents=has_docs,
                is_web_search=body.web_search,
                content=body.content,
                healthy_providers=configured_providers,
            )
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        pconfig = get_provider_config(provider)
    else:
        provider = req_provider
        pconfig = get_provider_config(provider)
        if not is_provider_configured(provider):
            raise HTTPException(
                status_code=400,
                detail=f"{pconfig['name']} is not configured on this server. Set the {pconfig.get('api_key_env')} API key in server environment variables.",
            )
        model = req_model or pconfig['default_model']
        if has_images:
            is_supported, explanation = check_vision_support(provider, model)
            if not is_supported:
                raise HTTPException(status_code=400, detail=explanation)

    if provider != 'ollama':
        api_key = get_api_key(provider)
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail=f"Missing API key for {pconfig['name']}. Set {pconfig.get('api_key_env')} in server environment variables.",
            )

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
    valid_image_attachments = []
    image_b64s = []
    for img in image_attachments:
        try:
            with open(img['file_path'], 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
                valid_image_attachments.append(img)
                image_b64s.append(b64)
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
                auto_title = ' '.join(display_user_text.split()[:8])[:60].strip()
                if auto_title:
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

        saved_model_tag = f"{provider}:{model}"
        mid = db.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at, status, model, auto_reason) VALUES (?, 'assistant', '', ?, 'generating', ?, ?)",
            (cid, now(), saved_model_tag, auto_explanation or None),
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
            await emit('start', message_id=mid, provider=provider, model=model, auto_reason=auto_explanation)
            if search_results:
                await emit('sources', sources=search_results)

            try:
                try:
                    client_instance = client(provider)
                except TypeError:
                    client_instance = client()
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
                    provider=provider,
                )

                if is_cloud:
                    cloud_messages = [dict(m) for m in context]
                    if image_b64s and cloud_messages:
                        last_text = cloud_messages[-1]['content']
                        multimodal_content = [{'type': 'text', 'text': last_text}]
                        for img, b64 in zip(valid_image_attachments, image_b64s):
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
                            try:
                                item = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if item.get('error'):
                                err_text = item.get('error')
                                raise ValueError(
                                    f'Ollama error: {err_text}'
                                    if isinstance(err_text, str)
                                    else 'Ollama could not generate a response. Check the selected model and server logs.'
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
                active_task_owners.pop(cid, None)
                try:
                    queue.put_nowait({'type': 'done', status: status})
                except asyncio.QueueFull:
                    pass

    task = asyncio.create_task(generate())
    active[cid] = task
    active_task_owners[cid] = visitor_id

    async def event_stream():
        try:
            yield ': connected\n\n'
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

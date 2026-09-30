import asyncio
import json
import logging
import os
import sqlite3
import uuid
import base64
import binascii
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .database import ROOT, connect, initialize
from .context import build_context

load_dotenv(ROOT / '.env')
log = logging.getLogger('forma')
active = {}
def now(): return datetime.now(timezone.utc).isoformat()

@asynccontextmanager
async def lifespan(app):
    if os.getenv('APP_ENV') == 'production':
        if not os.getenv('AUTH_USERNAME') or len(os.getenv('AUTH_PASSWORD','')) < 16:
            raise RuntimeError('Production requires AUTH_USERNAME and AUTH_PASSWORD (at least 16 characters).')
        if not os.getenv('OLLAMA_BASE_URL'):
            raise RuntimeError('Production requires an explicit reachable OLLAMA_BASE_URL.')
    initialize()
    # A killed process cannot leave a conversation permanently generating.
    with connect() as db:
        db.execute("UPDATE messages SET status='stopped' WHERE status='generating'")
    yield

app = FastAPI(title='Forma local assistant', lifespan=lifespan)

@app.middleware('http')
async def local_origin(request: Request, call_next):
    # Browser-managed HTTP Basic credentials never enter frontend configuration.
    username, password = os.getenv('AUTH_USERNAME',''), os.getenv('AUTH_PASSWORD','')
    if (username or password) and request.url.path != '/api/health':
        valid = False
        try:
            scheme, encoded = request.headers.get('authorization','').split(' ',1)
            supplied_user, supplied_password = base64.b64decode(encoded,validate=True).decode().split(':',1)
            valid = scheme.lower() == 'basic' and secrets.compare_digest(supplied_user.encode(),username.encode()) and secrets.compare_digest(supplied_password.encode(),password.encode())
        except (ValueError,UnicodeError,binascii.Error):
            pass
        if not valid:
            return JSONResponse({'detail':'Sign in to your Forma workspace.'},status_code=401,headers={'WWW-Authenticate':'Basic realm="Forma", charset="UTF-8"','Cache-Control':'no-store'})
    origin = request.headers.get('origin')
    allowed = {'http://localhost:5173','http://127.0.0.1:5173','http://localhost:8000','http://127.0.0.1:8000'}
    allowed.update(x.strip().rstrip('/') for x in os.getenv('ALLOWED_ORIGINS','').split(',') if x.strip())
    if os.getenv('RENDER_EXTERNAL_URL'): allowed.add(os.environ['RENDER_EXTERNAL_URL'].rstrip('/'))
    if os.getenv('RAILWAY_PUBLIC_DOMAIN'): allowed.add('https://' + os.environ['RAILWAY_PUBLIC_DOMAIN'])
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin not in allowed:
        return JSONResponse({'detail':'Origin not allowed.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    if request.url.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(sqlite3.Error)
async def database_error(request, exc):
    log.exception('Database operation failed', exc_info=exc)
    return JSONResponse({'detail':'Unable to save chat history. Check disk space and database permissions.'}, status_code=500)

def conversation(cid):
    with connect() as db:
        row = db.execute('SELECT * FROM conversations WHERE id=?',(cid,)).fetchone()
    if not row: raise HTTPException(404, 'Conversation not found.')
    return dict(row)

def idle(cid):
    if cid in active: raise HTTPException(409, 'Stop the current response before changing this conversation.')

def client():
    token = os.getenv('OLLAMA_API_KEY')
    headers = {'Authorization':'Bearer '+token} if token else {}
    return httpx.AsyncClient(base_url=os.getenv('OLLAMA_BASE_URL','http://localhost:11434').rstrip('/'), headers=headers, timeout=httpx.Timeout(float(os.getenv('GENERATION_TIMEOUT','300')), connect=5))

def error_message(exc):
    if isinstance(exc, httpx.ConnectError): return 'Unable to connect to Ollama. Make sure Ollama is running and try again.'
    if isinstance(exc, httpx.TimeoutException): return 'Generation timed out. Try again or choose a smaller model.'
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404: return 'The selected model is not installed. Download it with ollama pull, then refresh models.'
    if isinstance(exc, ValueError): return str(exc)
    return 'Generation failed. Check Ollama and try again.'

@app.get('/api/health')
async def health():
    with connect() as db: db.execute('SELECT 1 FROM conversations LIMIT 1').fetchone()
    return {'status':'ok'}

@app.get('/api/models')
async def models():
    try:
        async with client() as c:
            response = await c.get('/api/tags')
            response.raise_for_status()
        return {'models':[m['name'] for m in response.json()['models']], 'default':os.getenv('OLLAMA_MODEL','llama3.2')}
    except httpx.HTTPError as exc: raise HTTPException(503,error_message(exc))

@app.get('/api/conversations')
async def conversations(q: str = ''):
    with connect() as db:
        return [dict(r) for r in db.execute('''SELECT c.* FROM conversations c WHERE c.title LIKE ? OR EXISTS
          (SELECT 1 FROM messages m WHERE m.conversation_id=c.id AND m.content LIKE ?) ORDER BY c.updated_at DESC''',('%'+q[:200]+'%','%'+q[:200]+'%'))]

@app.post('/api/conversations', status_code=201)
async def create():
    cid, stamp = str(uuid.uuid4()), now()
    with connect() as db: db.execute('INSERT INTO conversations(id,title,created_at,updated_at) VALUES (?,?,?,?)',(cid,'New chat',stamp,stamp))
    return conversation(cid)

@app.get('/api/conversations/{cid}')
async def get_conversation(cid: str):
    result = conversation(cid)
    with connect() as db: result['messages'] = [dict(r) for r in db.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id',(cid,))]
    return result

class Rename(BaseModel):
    title: str = Field(min_length=1,max_length=80)

@app.patch('/api/conversations/{cid}')
async def rename(cid: str, body: Rename):
    conversation(cid)
    if not body.title.strip(): raise HTTPException(422,'Title cannot be empty.')
    with connect() as db: db.execute('UPDATE conversations SET title=?,updated_at=? WHERE id=?',(body.title.strip(),now(),cid))
    return conversation(cid)

@app.delete('/api/conversations/{cid}')
async def delete(cid: str):
    idle(cid)
    conversation(cid)
    with connect() as db: db.execute('DELETE FROM conversations WHERE id=?',(cid,))
    return {'ok':True}

@app.delete('/api/conversations')
async def clear():
    if active: raise HTTPException(409,'Stop generation before clearing chats.')
    with connect() as db: db.execute('DELETE FROM conversations')
    return {'ok':True}

@app.post('/api/conversations/{cid}/stop')
async def stop(cid: str):
    task = active.get(cid)
    if task:
        task.cancel()
        await task
    return {'ok':True}

class Chat(BaseModel):
    conversation_id: str
    content: str = Field(default='',max_length=50000)
    model: str | None = Field(default=None,max_length=200)
    temperature: float = Field(default=0.7,ge=0,le=2)
    regenerate: bool = False
    edit_message_id: int | None = None

@app.post('/api/chat')
async def chat(body: Chat):
    cid = body.conversation_id
    conv = conversation(cid)
    idle(cid)
    if not body.regenerate and not body.content.strip(): raise HTTPException(422,'Write a message first.')
    model = body.model or os.getenv('OLLAMA_MODEL','llama3.2')
    with connect() as db:
        if body.edit_message_id is not None:
            target = db.execute("SELECT * FROM messages WHERE id=? AND conversation_id=? AND role='user'",(body.edit_message_id,cid)).fetchone()
            if not target: raise HTTPException(404,'User message not found.')
            db.execute('DELETE FROM messages WHERE conversation_id=? AND id>=?',(cid,body.edit_message_id))
            db.execute("UPDATE conversations SET summary='',summary_through=0 WHERE id=?",(cid,))
            conv['summary'], conv['summary_through'] = '', 0
        if body.regenerate:
            last = db.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 1',(cid,)).fetchone()
            if not last: raise HTTPException(400,'No message to regenerate.')
            if last['role']=='assistant': db.execute('DELETE FROM messages WHERE id=?',(last['id'],))
        else:
            db.execute("INSERT INTO messages(conversation_id,role,content,created_at) VALUES (?,'user',?,?)",(cid,body.content.strip(),now()))
            if conv['title']=='New chat':
                title = ' '.join(body.content.strip().split()[:8])[:60]
                db.execute('UPDATE conversations SET title=? WHERE id=?',(title,cid))
        history = [dict(r) for r in db.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id',(cid,))]
        mid = db.execute("INSERT INTO messages(conversation_id,role,content,created_at,status,model) VALUES (?,'assistant','',?,'generating',?)",(cid,now(),model)).lastrowid
        db.execute('UPDATE conversations SET updated_at=? WHERE id=?',(now(),cid))
    queue = asyncio.Queue(maxsize=128)
    async def emit(kind, **data): await queue.put({'type':kind,**data})
    async def generate():
        text, status = '', 'stopped'
        try:
            await emit('start',message_id=mid)
            async with client() as c:
                def save_summary(summary, through):
                    with connect() as db: db.execute('UPDATE conversations SET summary=?,summary_through=? WHERE id=?',(summary,through,cid))
                async def notify(message): await emit('status',message=message)
                context = await build_context(c,model,conv,history,save_summary,notify)
                async with c.stream('POST','/api/chat',json={'model':model,'messages':context,'stream':True,'options':{'temperature':body.temperature,'num_ctx':int(os.getenv('CONTEXT_TOKENS','8192')),'num_predict':int(os.getenv('OUTPUT_TOKENS','4096'))}}) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line: continue
                        item = json.loads(line)
                        if item.get('error'): raise ValueError('Ollama could not generate a response. Check the selected model and server logs.')
                        delta = item.get('message',{}).get('content','')
                        if delta:
                            text += delta
                            await emit('token',content=delta)
                        if item.get('done'):
                            status = 'complete'
                            break
                    if status != 'complete': raise ValueError('The model connection closed early. You can retry this response.')
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            status = 'error'
            log.exception('Generation failed')
            await emit('error',message=error_message(exc))
        finally:
            try:
                with connect() as db:
                    db.execute('UPDATE messages SET content=?,status=? WHERE id=?',(text,status,mid))
                    db.execute('UPDATE conversations SET updated_at=? WHERE id=?',(now(),cid))
            finally:
                active.pop(cid,None)
                # Do not block cleanup if a disconnected browser left a full queue.
                try: queue.put_nowait({'type':'done','status':status})
                except asyncio.QueueFull: pass
    task = asyncio.create_task(generate())
    active[cid] = task
    async def stream():
        try:
            while True:
                try: item = await asyncio.wait_for(queue.get(),timeout=10)
                except asyncio.TimeoutError:
                    if task.done(): break
                    yield ': keepalive\n\n'
                    continue
                yield 'data: '+json.dumps(item)+'\n\n'
                if item['type']=='done': break
        finally:
            if not task.done(): task.cancel()
            await task
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

dist = ROOT / 'frontend' / 'dist'
if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')

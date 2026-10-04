import asyncio
import io
import json
import sqlite3
import pytest
import httpx
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app, active, active_task_owners
from backend.app.config import settings
from backend.app.database import connect, initialize
from backend.app.security import clear_rate_limits, sign_session_token


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'test_isolation.db'))
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attachments'))
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('FORMA_DISABLE_RATE_LIMIT', 'false')
    clear_rate_limits()
    initialize()
    yield
    clear_rate_limits()


def test_two_independent_sessions_isolation(tmp_path):
    """
    Verify two independent browser sessions:
    Neither can list, search, read, modify, delete, download, or clear the other's data.
    """
    client_a = TestClient(app, base_url='http://localhost:8000')
    client_b = TestClient(app, base_url='http://localhost:8000')

    # Session A creates a conversation and attaches a secret file
    res_a = client_a.post('/api/conversations')
    assert res_a.status_code == 201
    conv_a_id = res_a.json()['id']

    # Session A renames conversation
    patch_a = client_a.patch(f'/api/conversations/{conv_a_id}', json={'title': 'Confidential Strategy A'})
    assert patch_a.status_code == 200

    # Session A uploads an attachment
    secret_bytes = b'Top secret strategic plan for A'
    upload_res = client_a.post(
        f'/api/conversations/{conv_a_id}/attachments',
        files={'file': ('strategy.txt', io.BytesIO(secret_bytes), 'text/plain')},
    )
    assert upload_res.status_code == 201
    att_a_id = upload_res.json()['id']

    # Session B creates its own conversation
    res_b = client_b.post('/api/conversations')
    assert res_b.status_code == 201
    conv_b_id = res_b.json()['id']
    client_b.patch(f'/api/conversations/{conv_b_id}', json={'title': 'Public Discussion B'})

    # 1. LIST ISOLATION: neither sees the other's conversations
    list_a = client_a.get('/api/conversations').json()
    list_b = client_b.get('/api/conversations').json()
    assert any(c['id'] == conv_a_id for c in list_a)
    assert not any(c['id'] == conv_b_id for c in list_a)
    assert any(c['id'] == conv_b_id for c in list_b)
    assert not any(c['id'] == conv_a_id for c in list_b)

    # 2. SEARCH ISOLATION: searching for Session A's keywords returns nothing for Session B
    search_a = client_a.get('/api/conversations?q=Confidential').json()
    assert len(search_a) == 1
    assert search_a[0]['id'] == conv_a_id

    search_b = client_b.get('/api/conversations?q=Confidential').json()
    assert len(search_b) == 0

    # 3. READ ISOLATION: GET /api/conversations/{cid} returns 404 for another session's chat
    assert client_b.get(f'/api/conversations/{conv_a_id}').status_code == 404
    assert client_a.get(f'/api/conversations/{conv_b_id}').status_code == 404

    # 4. MODIFY ISOLATION: Session B cannot rename Session A's conversation
    rename_attempt = client_b.patch(f'/api/conversations/{conv_a_id}', json={'title': 'Hijacked Title'})
    assert rename_attempt.status_code == 404
    # Verify title is still unchanged in Session A
    assert client_a.get(f'/api/conversations/{conv_a_id}').json()['title'] == 'Confidential Strategy A'

    # 5. ATTACHMENT ISOLATION: Session B cannot list, download, or delete Session A's files
    assert client_b.get(f'/api/conversations/{conv_a_id}/attachments').status_code == 404
    assert client_b.get(f'/api/conversations/{conv_a_id}/attachments/{att_a_id}').status_code == 404
    assert client_b.get(f'/api/conversations/{conv_a_id}/attachments/{att_a_id}/download').status_code == 404
    assert client_b.delete(f'/api/conversations/{conv_a_id}/attachments/{att_a_id}').status_code == 404

    # Session A CAN download its own attachment
    download_res = client_a.get(f'/api/conversations/{conv_a_id}/attachments/{att_a_id}/download')
    assert download_res.status_code == 200
    assert download_res.content == secret_bytes

    # Session B cannot upload into Session A's conversation
    upload_hacked = client_b.post(
        f'/api/conversations/{conv_a_id}/attachments',
        files={'file': ('exploit.txt', io.BytesIO(b'exploit'), 'text/plain')},
    )
    assert upload_hacked.status_code == 404

    # 6. DELETE SINGLE CONVERSATION ISOLATION: Session B cannot delete Session A's chat
    assert client_b.delete(f'/api/conversations/{conv_a_id}').status_code == 404
    assert client_a.get(f'/api/conversations/{conv_a_id}').status_code == 200

    # 7. STOP & CHAT ISOLATION
    assert client_b.post(f'/api/conversations/{conv_a_id}/stop').status_code == 404
    assert client_b.post('/api/chat', json={'conversation_id': conv_a_id, 'content': 'Hello'}).status_code == 404

    # 8. CLEAR ALL ISOLATION: Session B clears all; only Session B's data is cleared!
    clear_b = client_b.delete('/api/conversations')
    assert clear_b.status_code == 200
    assert len(client_b.get('/api/conversations').json()) == 0

    # Session A's conversation and files are completely intact!
    assert client_a.get(f'/api/conversations/{conv_a_id}').status_code == 200
    assert len(client_a.get('/api/conversations').json()) == 1
    download_check = client_a.get(f'/api/conversations/{conv_a_id}/attachments/{att_a_id}/download')
    assert download_check.status_code == 200
    assert download_check.content == secret_bytes


def test_legacy_data_migration_and_archive(tmp_path, monkeypatch):
    """
    Verify legacy data migration:
    Existing conversations with no visitor_id are migrated to '__legacy_archive__'.
    Anonymous visitors cannot list, search, read, modify, or delete legacy data.
    """
    db_path = tmp_path / 'legacy.db'
    attach_dir = tmp_path / 'attachments'
    attach_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('DATABASE_PATH', str(db_path))
    monkeypatch.setenv('ATTACHMENTS_DIR', str(attach_dir))

    # Create old database schema WITHOUT visitor_id column
    conn = sqlite3.connect(db_path)
    conn.executescript('''
        CREATE TABLE conversations (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', summary_through INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'complete', model TEXT, sources TEXT, web_search INTEGER DEFAULT 0
        );
        CREATE TABLE attachments (
          id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          message_id INTEGER, filename TEXT NOT NULL, content_type TEXT NOT NULL,
          size_bytes INTEGER NOT NULL, file_path TEXT NOT NULL, created_at TEXT NOT NULL,
          extracted_text TEXT, page_count INTEGER DEFAULT 0, is_image INTEGER DEFAULT 0
        );
    ''')

    # Insert legacy conversation, message, and attachment
    legacy_file = attach_dir / 'legacy_conv_1' / 'att1_legacy.txt'
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text('Private company legacy documents', encoding='utf-8')

    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES ('legacy_conv_1', 'Internal Legacy Chat', '2026-01-01', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES ('legacy_conv_1', 'user', 'Legacy secret info', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO attachments (id, conversation_id, filename, content_type, size_bytes, file_path, created_at) VALUES ('att_legacy', 'legacy_conv_1', 'legacy.txt', 'text/plain', 32, ?, '2026-01-01')",
        (str(legacy_file),),
    )
    conn.commit()
    conn.close()

    # Now run application initialize() to trigger migration
    initialize()

    # Verify column was added and owner was set to '__legacy_archive__'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT visitor_id FROM conversations WHERE id = 'legacy_conv_1'").fetchone()
    assert row['visitor_id'] == '__legacy_archive__'
    conn.close()

    # Connect with an anonymous visitor
    client = TestClient(app, base_url='http://localhost:8000')

    # Anonymous visitor cannot see legacy chat in list
    chats = client.get('/api/conversations').json()
    assert len(chats) == 0

    # Anonymous visitor cannot search legacy chat
    search_res = client.get('/api/conversations?q=Legacy').json()
    assert len(search_res) == 0

    # Anonymous visitor cannot read, modify, or download legacy chat
    assert client.get('/api/conversations/legacy_conv_1').status_code == 404
    assert client.patch('/api/conversations/legacy_conv_1', json={'title': 'New'}).status_code == 404
    assert client.get('/api/conversations/legacy_conv_1/attachments/att_legacy/download').status_code == 404
    assert client.delete('/api/conversations/legacy_conv_1').status_code == 404

    # Anonymous visitor clears all their chats: legacy data remains intact on disk and DB
    assert client.delete('/api/conversations').status_code == 200
    assert legacy_file.exists()
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM conversations WHERE id = 'legacy_conv_1'").fetchone()[0] == 1
    conn.close()


def test_forged_ip_headers_vs_trusted_proxies(monkeypatch):
    """
    Ensure untrusted connections cannot bypass IP rate limiting by spoofing
    X-Forwarded-For or X-Real-IP headers.
    """
    clear_rate_limits()
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', '2')
    monkeypatch.setenv('FORMA_DISABLE_RATE_LIMIT', 'false')
    monkeypatch.setenv('TRUSTED_PROXIES', '10.0.0.1,10.0.0.2')

    # Direct client connecting from untrusted IP '198.51.100.5'
    client = TestClient(app, base_url='http://localhost:8000', client=('198.51.100.5', 54321))

    # Request 1 with forged header
    r1 = client.get('/api/conversations', headers={'x-forwarded-for': '203.0.113.1'})
    assert r1.status_code == 200

    # Request 2 with a DIFFERENT forged header pretending to be someone else
    r2 = client.get('/api/conversations', headers={'x-forwarded-for': '203.0.113.2'})
    assert r2.status_code == 200

    # Request 3: forged header is ignored; peer IP '198.51.100.5' has reached limit 2
    r3 = client.get('/api/conversations', headers={'x-forwarded-for': '203.0.113.3'})
    assert r3.status_code == 429
    assert 'Retry-After' in r3.headers

    # Now verify trusted proxy connection: peer IP '10.0.0.1' is trusted
    clear_rate_limits()
    trusted_proxy_client = TestClient(app, base_url='http://localhost:8000', client=('10.0.0.1', 54321))
    # When trusted proxy forwards genuine client '198.51.100.88', rate limiter recognizes 198.51.100.88
    t1 = trusted_proxy_client.get('/api/conversations', headers={'x-forwarded-for': '198.51.100.88'})
    t2 = trusted_proxy_client.get('/api/conversations', headers={'x-forwarded-for': '198.51.100.88'})
    t3 = trusted_proxy_client.get('/api/conversations', headers={'x-forwarded-for': '198.51.100.88'})
    assert t1.status_code == 200
    assert t2.status_code == 200
    assert t3.status_code == 429


def test_csrf_and_origin_protection(monkeypatch):
    """
    Verify CSRF protection:
    - Forbidden cross-origin mutating requests return 403.
    - Invalid X-CSRF-Token header matching returns 403.
    """
    client = TestClient(app, base_url='http://localhost:8000')

    # Initial request sets cookies (forma_session and forma_csrf)
    res = client.get('/api/conversations')
    assert res.status_code == 200
    csrf_token = res.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf_token is not None

    # Mutating request from an untrusted foreign origin is rejected
    cross_origin_res = client.post(
        '/api/conversations',
        headers={'origin': 'https://attacker.evil'},
    )
    assert cross_origin_res.status_code == 403
    assert 'Origin not allowed' in cross_origin_res.json()['detail']

    # Mutating request with tampered/invalid CSRF header is rejected
    tampered_csrf = client.post(
        '/api/conversations',
        headers={'origin': 'http://localhost:8000', 'x-csrf-token': 'wrong-tampered-token'},
    )
    assert tampered_csrf.status_code == 403
    assert 'Invalid CSRF token' in tampered_csrf.json()['detail']

    # Valid request with matching CSRF token and allowed origin succeeds
    valid_res = client.post(
        '/api/conversations',
        headers={'origin': 'http://localhost:8000', 'x-csrf-token': csrf_token},
    )
    assert valid_res.status_code == 201


def test_concurrency_and_storage_limits(tmp_path, monkeypatch):
    """
    Verify per-visitor storage and concurrency limits.
    """
    client = TestClient(app, base_url='http://localhost:8000')
    cid = client.post('/api/conversations').json()['id']

    # 1. Storage limit check
    monkeypatch.setenv('MAX_VISITOR_STORAGE_MB', '1') # 1 MB limit
    big_chunk = b'A' * (500 * 1024) # 500 KB

    res1 = client.post(
        f'/api/conversations/{cid}/attachments',
        files={'file': ('file1.txt', io.BytesIO(big_chunk), 'text/plain')},
    )
    assert res1.status_code == 201

    res2 = client.post(
        f'/api/conversations/{cid}/attachments',
        files={'file': ('file2.txt', io.BytesIO(big_chunk), 'text/plain')},
    )
    assert res2.status_code == 201

    # 3rd upload would exceed 1MB cumulative storage -> 413 Payload Too Large
    res3 = client.post(
        f'/api/conversations/{cid}/attachments',
        files={'file': ('file3.txt', io.BytesIO(big_chunk), 'text/plain')},
    )
    assert res3.status_code == 413
    assert 'Storage limit' in res3.json()['detail']

    # 2. Concurrency limit check
    # Simulate an active generation task running for this visitor in conversation cid
    from unittest.mock import MagicMock
    visitor_id = client.cookies.get(settings.SESSION_COOKIE_NAME).split('.')[0]
    dummy_task = MagicMock()
    dummy_task.done.return_value = False
    active[cid] = dummy_task
    active_task_owners[cid] = visitor_id

    cid2 = client.post('/api/conversations').json()['id']

    try:
        # Same conversation: returns 409 Conflict
        same_conv_res = client.post('/api/chat', json={'conversation_id': cid, 'content': 'Another prompt'})
        assert same_conv_res.status_code == 409

        # Different conversation by same visitor: returns 429 Too Many Requests (visitor concurrency limit)
        busy_res = client.post('/api/chat', json={'conversation_id': cid2, 'content': 'Concurrent prompt'})
        assert busy_res.status_code == 429
        assert 'already in progress' in busy_res.json()['detail']
    finally:
        active.pop(cid, None)
        active_task_owners.pop(cid, None)


def test_streaming_sse_with_visitor_isolation(monkeypatch):
    """
    Verify streaming generation maintains visitor isolation and cookies.
    """
    def handler(request):
        return httpx.Response(200, content='\n'.join(json.dumps(x) for x in [
            {'message': {'content': 'Isolated '}}, {'message': {'content': 'stream'}}, {'done': True}
        ]))
    from backend.app import main
    monkeypatch.setattr(main, 'client', lambda: httpx.AsyncClient(base_url='http://test', transport=httpx.MockTransport(handler)))

    client_a = TestClient(app, base_url='http://localhost:8000')
    client_b = TestClient(app, base_url='http://localhost:8000')

    cid_a = client_a.post('/api/conversations').json()['id']

    # Client A streams successfully
    stream_res = client_a.post('/api/chat', json={'conversation_id': cid_a, 'content': 'Test streaming'})
    assert stream_res.status_code == 200
    assert 'Isolated ' in stream_res.text
    assert 'stream' in stream_res.text

    # Client B attempts to stream in Client A's conversation -> 404
    hacked_stream = client_b.post('/api/chat', json={'conversation_id': cid_a, 'content': 'Hijack'})
    assert hacked_stream.status_code == 404

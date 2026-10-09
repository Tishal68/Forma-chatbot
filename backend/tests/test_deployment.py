import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.security import clear_rate_limits

@pytest.fixture
def production(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMA_DISABLE_RATE_LIMIT', 'true')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'production.db'))
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('AUTH_USERNAME', 'test-owner')
    monkeypatch.setenv('AUTH_PASSWORD', 'test-only-long-password')
    monkeypatch.setenv('OLLAMA_BASE_URL', 'http://ollama:11434')
    monkeypatch.setenv('ALLOWED_ORIGINS', 'https://chat.example.com')
    with TestClient(app) as client:
        yield client

def test_production_access_and_health(production):
    assert production.get('/api/health').status_code == 200
    assert production.get('/api/conversations').status_code == 401
    assert production.get('/docs').status_code == 401
    assert production.get('/api/conversations', auth=('test-owner', 'wrong')).status_code == 401
    response = production.get('/api/conversations', auth=('test-owner', 'test-only-long-password'))
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['Strict-Transport-Security'] == 'max-age=31536000; includeSubDomains; preload'
    assert 'default-src' in response.headers['Content-Security-Policy']
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'

def test_hosted_origin(production, monkeypatch):
    auth = ('test-owner', 'test-only-long-password')
    production.get('/api/conversations', auth=auth)
    token = production.cookies.get('forma_csrf')
    assert production.post('/api/conversations', auth=auth, headers={'x-csrf-token': token, 'origin': 'https://chat.example.com'}).status_code == 201
    assert production.post('/api/conversations', auth=auth, headers={'x-csrf-token': token, 'origin': 'https://evil.example'}).status_code == 403
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://forma.onrender.com')
    assert production.post('/api/conversations', auth=auth, headers={'x-csrf-token': token, 'origin': 'https://forma.onrender.com'}).status_code == 201
    monkeypatch.setenv('RAILWAY_PUBLIC_DOMAIN', 'forma.up.railway.app')
    assert production.post('/api/conversations', auth=auth, headers={'x-csrf-token': token, 'origin': 'https://forma.up.railway.app'}).status_code == 201

def test_production_refuses_missing_password(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('AUTH_USERNAME', 'test-owner')
    monkeypatch.delenv('AUTH_PASSWORD', raising=False)
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'guard.db'))
    with pytest.raises(RuntimeError, match='Production requires'):
        with TestClient(app):
            pass

def test_production_public_mode_without_credentials(tmp_path, monkeypatch):
    """Public web mode allows instant access while keeping enterprise security headers."""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('AUTH_USERNAME', raising=False)
    monkeypatch.delenv('AUTH_PASSWORD', raising=False)
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'public.db'))
    with TestClient(app) as client:
        # No 401 popup for public visitors
        res = client.get('/api/conversations')
        assert res.status_code == 200
        # Headers remain hardened
        assert res.headers['X-Frame-Options'] == 'DENY'
        assert res.headers['X-Content-Type-Options'] == 'nosniff'
        assert 'default-src' in res.headers['Content-Security-Policy']

def test_rate_limiting_defense(tmp_path, monkeypatch):
    """Ensure in-memory sliding window rate limiter protects public endpoints from DDoS/scraping."""
    clear_rate_limits()
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', '3')
    monkeypatch.delenv('FORMA_DISABLE_RATE_LIMIT', raising=False)
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'ratelimit.db'))
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get('/api/conversations').status_code == 200
        # 4th request exceeds rate limit
        res = client.get('/api/conversations')
        assert res.status_code == 429
        assert 'Retry-After' in res.headers


def test_production_session_stability_multi_request(tmp_path, monkeypatch):
    """
    Verify production session stability across requests:
    1. A visitor creates a chat in request 1 under production mode.
    2. Session secret is persisted on disk (not ephemeral per-request).
    3. The visitor session cookie is sent in request 2 to POST /api/chat.
    4. The conversation is successfully found (200 streaming, never 404 'Conversation not found').
    5. A different visitor session is isolated and receives 404.
    """
    import httpx
    from app import main
    from app.config import settings

    settings.reset_session_secret_cache()
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('FORMA_DISABLE_RATE_LIMIT', 'true')
    monkeypatch.delenv('AUTH_USERNAME', raising=False)
    monkeypatch.delenv('AUTH_PASSWORD', raising=False)
    monkeypatch.delenv('SESSION_SECRET', raising=False)
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'prod_session.db'))
    monkeypatch.setenv('OLLAMA_BASE_URL', 'http://test-server:11434')

    def mock_ollama_handler(request: httpx.Request):
        chunks = [
            b'{"message": {"content": "Hello "}}\n',
            b'{"message": {"content": "world!"}}\n',
            b'{"done": true}\n',
        ]
        return httpx.Response(200, content=b''.join(chunks))

    monkeypatch.setattr(
        main,
        'client',
        lambda *args, **kwargs: httpx.AsyncClient(base_url='http://test', transport=httpx.MockTransport(mock_ollama_handler)),
    )

    with TestClient(app, base_url='https://forma-prod.example.com') as client:
        # Request 1: Create conversation
        res1 = client.post('/api/conversations', json={'title': 'Stable Session Chat'})
        assert res1.status_code == 201
        data1 = res1.json()
        conv_id = data1['id']
        assert 'forma_session' in client.cookies

        # Verify persistent secret was written to disk
        secret_file = tmp_path / '.session_secret'
        assert secret_file.exists()
        persisted_secret = secret_file.read_text(encoding='utf-8').strip()
        assert len(persisted_secret) >= 32

        # Request 2: Send message using the same visitor session in a separate request
        res2 = client.post('/api/chat', json={
            'conversation_id': conv_id,
            'content': 'Hi assistant',
            'provider': 'ollama',
            'model': 'llama3.2',
        })
        # Must NOT fail with 404 "Conversation not found"
        assert res2.status_code == 200
        assert 'Hello ' in res2.text
        assert 'world!' in res2.text

    # Visitor Isolation: A separate visitor cannot access this conversation
    with TestClient(app, base_url='https://forma-prod.example.com') as other_client:
        res_other = other_client.get(f'/api/conversations/{conv_id}')
        assert res_other.status_code == 404
        res_other_chat = other_client.post('/api/chat', json={
            'conversation_id': conv_id,
            'content': 'Attempt unauthorized message',
            'provider': 'ollama',
            'model': 'llama3.2',
        })
        assert res_other_chat.status_code == 404
        assert 'Conversation not found' in res_other_chat.json()['detail']


def test_production_refuses_unwritable_session_secret(tmp_path, monkeypatch):
    """
    In production, if SESSION_SECRET is not configured in env and the persistent directory
    is not writable, the app must raise RuntimeError and never silently generate
    an ephemeral secret.
    """
    from pathlib import Path
    from app.config import settings

    settings.reset_session_secret_cache()
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('SESSION_SECRET', raising=False)
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'isolated' / 'chat.db'))

    def mock_write_fail(self, *args, **kwargs):
        raise PermissionError("Disk is read-only / unprivileged container")

    monkeypatch.setattr(Path, 'write_text', mock_write_fail)

    with pytest.raises(RuntimeError, match='SESSION_SECRET'):
        _ = settings.SESSION_SECRET

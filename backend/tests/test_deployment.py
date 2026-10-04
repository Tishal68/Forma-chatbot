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
    assert production.post('/api/conversations', auth=auth, headers={'origin': 'https://chat.example.com'}).status_code == 201
    assert production.post('/api/conversations', auth=auth, headers={'origin': 'https://evil.example'}).status_code == 403
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://forma.onrender.com')
    assert production.post('/api/conversations', auth=auth, headers={'origin': 'https://forma.onrender.com'}).status_code == 201
    monkeypatch.setenv('RAILWAY_PUBLIC_DOMAIN', 'forma.up.railway.app')
    assert production.post('/api/conversations', auth=auth, headers={'origin': 'https://forma.up.railway.app'}).status_code == 201

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

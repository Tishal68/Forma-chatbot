import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.personalization import (
    save_memory,
    get_profile,
    capture_explicit,
    is_sensitive_or_credential,
    clear_profile,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'chat.db'))
    monkeypatch.setenv('SESSION_SECRET', 'test-memory-engine-secret-xyz-123')
    monkeypatch.setenv('FORMA_DISABLE_RATE_LIMIT', 'true')
    with TestClient(app) as test_client:
        yield test_client


def test_categorized_memories_storage_and_retrieval(client):
    visitor = 'v_test_categorized'
    save_memory(visitor, 'user role', 'Lead Architect', category='profile')
    save_memory(visitor, 'database tech', 'SQLite WAL', category='project')
    save_memory(visitor, 'quarter goal', 'Release v2.0 in November', category='episodic')

    profile = get_profile(visitor)
    cats = profile['categories']
    assert len(cats['profile']) == 1
    assert cats['profile'][0]['key'] == 'user role'
    assert cats['profile'][0]['value'] == 'Lead Architect'

    assert len(cats['project']) == 1
    assert cats['project'][0]['key'] == 'database tech'
    assert cats['project'][0]['value'] == 'SQLite WAL'

    assert len(cats['episodic']) == 1
    assert cats['episodic'][0]['key'] == 'quarter goal'


def test_sensitive_credential_rejection(client):
    assert is_sensitive_or_credential('my password is supersecret123') is True
    assert is_sensitive_or_credential('here is my API_KEY: sk-123456789') is True
    assert is_sensitive_or_credential('my access token is eyJhbGciOi...') is True
    assert is_sensitive_or_credential('my favorite color is blue') is False

    # capture_explicit rejects credentials
    res = capture_explicit('v_test_cred', 'Please remember my password is SecretPassword!')
    assert 'Credentials and secrets are not stored' in res


def test_project_context_extraction(client):
    visitor = 'v_test_proj_extract'
    res1 = capture_explicit(visitor, 'I am working on an autonomous drone controller')
    assert 'project memory' in res1.lower()
    prof1 = get_profile(visitor)
    assert any(m['key'] == 'current project' and m['category'] == 'project' for m in prof1['memories'])

    res2 = capture_explicit(visitor, 'My tech stack is FastAPI and React')
    assert 'tech stack memory' in res2.lower()
    prof2 = get_profile(visitor)
    assert any(m['key'] == 'tech stack' and m['category'] == 'project' for m in prof2['memories'])


def test_memory_export_and_import(client):
    # Setup initial profile
    client.patch('/api/personalization', json={
        'preferences': {'tone': 'analytical', 'language': 'English'},
        'custom_instructions': 'Always provide typed code examples.'
    })
    client.post('/api/personalization/memories', json={
        'key': 'favorite library',
        'value': 'FastAPI',
        'category': 'project'
    })

    # Export
    export_resp = client.get('/api/personalization/export')
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data['preferences']['tone'] == 'analytical'
    assert len(export_data['memories']) >= 1
    assert export_data['memories'][0]['key'] == 'favorite library'

    # Clear
    client.delete('/api/personalization')
    cleared = client.get('/api/personalization').json()
    assert cleared['preferences'] == {}
    assert cleared['memories'] == []

    # Import back
    import_resp = client.post('/api/personalization/import', json={
        'preferences': export_data['preferences'],
        'custom_instructions': export_data['custom_instructions'],
        'memories': export_data['memories']
    })
    assert import_resp.status_code == 200
    restored = client.get('/api/personalization').json()
    assert restored['preferences']['tone'] == 'analytical'
    assert restored['custom_instructions'] == 'Always provide typed code examples.'
    assert len(restored['memories']) >= 1
    assert restored['memories'][0]['key'] == 'favorite library'

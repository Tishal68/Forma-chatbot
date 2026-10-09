import asyncio
import io
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient
from app import tools
from app.main import app
from app.database import initialize, connect
from app.extractors import extract_docx_text
from app.security import clear_rate_limits


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'security.db'))
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('APP_ENV', 'development')
    initialize()
    clear_rate_limits()


def test_github_tool_never_uses_operator_token(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'test-private-token')
    monkeypatch.setenv('GH_TOKEN', 'test-private-token')
    original = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request)
        assert 'authorization' not in request.headers
        return httpx.Response(404)
    monkeypatch.setattr(tools.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    result = asyncio.run(tools.inspect_github_repo('owner/private-repo'))
    assert result['status'] == 'error'
    assert len(calls) == 1
    for repo, path in [('owner/repo', '../issues'), ('../repo', ''), ('owner/repo', 'a/../../x')]:
        assert asyncio.run(tools.inspect_github_repo(repo, path))['status'] == 'error'
    assert len(calls) == 1


def test_browser_mutations_require_csrf_token():
    with TestClient(app) as client:
        client.get('/api/conversations')
        for headers in [{'origin': 'http://testserver'}, {'sec-fetch-site': 'same-origin'}]:
            assert client.post('/api/conversations', headers=headers).status_code == 403
        token = client.cookies.get('forma_csrf')
        response = client.post('/api/conversations', headers={'origin': 'http://testserver', 'x-csrf-token': token})
        assert response.status_code == 201
        assert client.post('/api/conversations', headers={'origin': 'https://evil.example', 'x-csrf-token': token}).status_code == 403


def test_deletion_removes_only_owner_tool_audits():
    with TestClient(app) as first, TestClient(app) as second:
        a = first.post('/api/conversations').json()['id']
        b = second.post('/api/conversations').json()['id']
        with connect() as db:
            owners = dict(db.execute('SELECT id, visitor_id FROM conversations').fetchall())
        for cid in [a, b]:
            tools.record_tool_execution(owners[cid], cid, None, 'data_processor', {'data': 'private'}, 'private', 1)
        assert first.delete('/api/conversations/' + a).status_code == 200
        with connect() as db:
            assert db.execute('SELECT COUNT(*) FROM tool_executions WHERE visitor_id = ?', (owners[a],)).fetchone()[0] == 0
            assert db.execute('SELECT COUNT(*) FROM tool_executions WHERE visitor_id = ?', (owners[b],)).fetchone()[0] == 1
        assert second.delete('/api/conversations').status_code == 200
        with connect() as db:
            assert db.execute('SELECT COUNT(*) FROM tool_executions').fetchone()[0] == 0


def test_docx_expansion_and_entities_are_rejected(tmp_path):
    path = tmp_path / 'test.docx'
    for xml in [b'X' * (8 * 1024 * 1024 + 1), b'<!DOCTYPE x [<!ENTITY foo "bar">]><x>&foo;</x>', '<!DOCTYPE x [<!ENTITY foo "bar">]><x>&foo;</x>'.encode('utf-16')]:
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('word/document.xml', xml)
        with pytest.raises(ValueError):
            extract_docx_text(path)
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:document>')
    assert 'Hello' in extract_docx_text(path)


def test_upload_does_not_read_entire_oversized_file(monkeypatch):
    from starlette.datastructures import UploadFile
    monkeypatch.setenv('MAX_ATTACHMENT_SIZE_MB', '1')
    original = UploadFile.read
    reads = []
    async def tracked(self, size=-1):
        reads.append(size)
        return await original(self, size)
    monkeypatch.setattr(UploadFile, 'read', tracked)
    with TestClient(app) as client:
        cid = client.post('/api/conversations').json()['id']
        response = client.post(f'/api/conversations/{cid}/attachments', files={'file': ('large.txt', b'x' * (1024 * 1024 + 2), 'text/plain')})
        assert response.status_code == 400
        assert reads == [1024 * 1024 + 1]
        assert client.get(f'/api/conversations/{cid}/attachments').json() == []

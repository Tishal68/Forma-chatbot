import io
import json
import pytest
from pathlib import Path
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app import search


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attachments'))
    monkeypatch.setenv('APP_ENV', 'development')
    from backend.app.database import initialize
    initialize()
    with TestClient(app, base_url='http://localhost:8000') as c:
        yield c


def test_upload_and_extract_code_and_txt(client):
    conv_id = client.post('/api/conversations').json()['id']

    # Upload Python source code file
    py_code = 'def greet(name):\n    return f"Hello, {name}!"\n'
    res = client.post(
        f'/api/conversations/{conv_id}/attachments',
        files={'file': ('script.py', io.BytesIO(py_code.encode()), 'text/x-python')},
    )
    assert res.status_code == 201
    data = res.json()
    assert data['filename'] == 'script.py'
    assert data['is_image'] is False
    assert data['size_bytes'] == len(py_code)

    # Check conversation includes pending attachment
    conv = client.get(f'/api/conversations/{conv_id}').json()
    assert len(conv['pending_attachments']) == 1
    assert conv['pending_attachments'][0]['id'] == data['id']


def test_reject_unsupported_file_types(client):
    conv_id = client.post('/api/conversations').json()['id']

    # Reject .exe
    res = client.post(
        f'/api/conversations/{conv_id}/attachments',
        files={'file': ('virus.exe', io.BytesIO(b'binary data'), 'application/x-msdownload')},
    )
    assert res.status_code == 400
    assert 'Unsupported file type' in res.json()['detail']

    # Reject file without extension
    res2 = client.post(
        f'/api/conversations/{conv_id}/attachments',
        files={'file': ('noextfile', io.BytesIO(b'hello'), 'text/plain')},
    )
    assert res2.status_code == 400
    assert 'without a valid extension' in res2.json()['detail']


def test_attachment_deletion_and_cascade(client, tmp_path):
    conv_id = client.post('/api/conversations').json()['id']
    res = client.post(
        f'/api/conversations/{conv_id}/attachments',
        files={'file': ('doc.txt', io.BytesIO(b'Sample text content'), 'text/plain')},
    )
    aid = res.json()['id']

    # List attachments
    list_res = client.get(f'/api/conversations/{conv_id}/attachments')
    assert len(list_res.json()) == 1

    # Delete single attachment
    del_res = client.delete(f'/api/conversations/{conv_id}/attachments/{aid}')
    assert del_res.status_code == 200
    assert len(client.get(f'/api/conversations/{conv_id}/attachments').json()) == 0

    # Upload another attachment
    res2 = client.post(
        f'/api/conversations/{conv_id}/attachments',
        files={'file': ('notes.md', io.BytesIO(b'# Notes'), 'text/markdown')},
    )
    aid2 = res2.json()['id']

    # Delete conversation and ensure disk cleanup
    del_conv = client.delete(f'/api/conversations/{conv_id}')
    assert del_conv.status_code == 200
    conv_folder = settings.ATTACHMENTS_DIR / conv_id
    assert not conv_folder.exists()


def test_vision_model_compatibility(client):
    conv_id = client.post('/api/conversations').json()['id']

    # Upload PNG image
    res = client.post(
        f'/api/conversations/{conv_id}/attachments',
        files={'file': ('diagram.png', io.BytesIO(b'\x89PNG\r\n\x1a\nfakeimagebytes'), 'image/png')},
    )
    assert res.status_code == 201
    aid = res.json()['id']
    assert res.json()['is_image'] is True

    # Attempt chat with text-only Ollama model llama3.2
    chat_res = client.post('/api/chat', json={
        'conversation_id': conv_id,
        'content': 'What is in this diagram?',
        'provider': 'ollama',
        'model': 'llama3.2',
        'attachment_ids': [aid],
    })
    assert chat_res.status_code == 400
    assert 'does not support vision or image analysis' in chat_res.json()['detail']


@pytest.mark.parametrize("question", ["Latest Forma documentation", "who is thalapathy vijay"])
@pytest.mark.parametrize("explicit_search", [True, False])
def test_web_search_failure_and_sources(client, monkeypatch, explicit_search, question):
    conv_id = client.post('/api/conversations').json()['id']

    # Test web search failure
    async def mock_failed_search(query, max_results=5):
        raise search.SearchError('Search engine unavailable')

    from backend.app import main
    monkeypatch.setattr(main, 'perform_search', mock_failed_search)

    fail_res = client.post('/api/chat', json={
        'conversation_id': conv_id,
        'content': 'Latest news today',
        'provider': 'ollama',
        'model': 'llama3.2',
        'web_search': explicit_search,
    })
    assert fail_res.status_code == 502
    assert 'Web search failed' in fail_res.json()['detail']
    assert 'avoid inventing search results' in fail_res.json()['detail']

    # Test web search success
    async def mock_success_search(query, max_results=5):
        if question == "who is thalapathy vijay":
            assert "thalapathy vijay current role" in query or "thalapathy vijay latest news" in query
            if "latest news" in query:
                raise search.SearchError("News search unavailable")
        return [
            {'title': 'Forma Docs', 'url': 'https://forma.example/docs', 'snippet': 'Forma documentation.'}
        ]

    monkeypatch.setattr(main, 'perform_search', mock_success_search)

    # Mock cloud SSE generation
    import httpx
    def stream_handler(request):
        stream_chunks = [
            'data: {"choices": [{"delta": {"content": "Found in [Forma Docs](https://forma.example/docs)"}}]}\n\n',
            'data: [DONE]\n\n',
        ]
        return httpx.Response(200, content=''.join(stream_chunks))

    from backend.app import main
    monkeypatch.setenv('GROQ_API_KEY', 'gsk_testkey')
    monkeypatch.setattr(
        main,
        'client',
        lambda *args, **kwargs: httpx.AsyncClient(base_url='https://api.groq.com/openai/v1', transport=httpx.MockTransport(stream_handler)),
    )

    success_res = client.post('/api/chat', json={
        'conversation_id': conv_id,
        'content': question,
        'provider': 'groq',
        'web_search': explicit_search,
    })
    assert success_res.status_code == 200
    assert 'sources' in success_res.text
    assert 'Forma Docs' in success_res.text

    # Verify sources saved in DB
    conv_data = client.get(f'/api/conversations/{conv_id}').json()
    assistant_msg = [m for m in conv_data['messages'] if m['role'] == 'assistant'][-1]
    user_msg = [m for m in conv_data['messages'] if m['role'] == 'user'][-1]
    assert user_msg['web_search']
    assert len(assistant_msg['sources']) == 1
    assert assistant_msg['sources'][0]['url'] == 'https://forma.example/docs'

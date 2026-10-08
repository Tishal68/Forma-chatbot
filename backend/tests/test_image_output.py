import asyncio
import base64
import io
import json
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import main
from app.image_output import decode_image, generate_image
from app.ollama_catalog import model_detail


@pytest.fixture
def png():
    stream = io.BytesIO()
    Image.new('RGB', (16, 16), (30, 100, 80)).save(stream, format='PNG')
    return stream.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'images.db'))
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'media'))
    monkeypatch.setenv('OLLAMA_BASE_URL', 'http://image-test')
    async def probe(provider, force=False):
        if provider != 'ollama': return {'working': False, 'models': []}
        detail = model_detail('custom-painter', {'capabilities': ['image']}, local=True)
        return {'id': 'ollama', 'configured': True, 'working': True, 'status': 'ready', 'error': None,
                'models': ['custom-painter'], 'model_details': [detail]}
    monkeypatch.setattr(main, 'probe_provider_health', probe)
    with TestClient(main.app) as c:
        yield c


def test_image_generation_persists_download_and_regenerates(client, monkeypatch, png):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        assert request.url.path == '/api/generate'
        return httpx.Response(200, text='\n'.join(json.dumps(item) for item in [
            {'completed': 1, 'total': 2}, {'image': base64.b64encode(png).decode(), 'done': True}]))
    monkeypatch.setattr(main, 'client', lambda *a: httpx.AsyncClient(base_url='http://test', transport=httpx.MockTransport(handler)))
    cid = client.post('/api/conversations').json()['id']
    request = {'conversation_id': cid, 'provider': 'auto', 'model': 'auto', 'content': 'A green square', 'output_mode': 'image'}
    response = client.post('/api/chat', json=request)
    assert '50%' in response.text and '"type": "image"' in response.text
    assert '"status": "complete"' in response.text
    saved = client.get('/api/conversations/' + cid).json()
    assert saved['messages'][-1]['output_mode'] == 'image'
    image = saved['messages'][-1]['attachments'][0]
    assert image['generated'] == 1
    url = f"/api/conversations/{cid}/attachments/{image['id']}"
    downloaded = client.get(url)
    assert downloaded.content == png
    assert downloaded.headers['content-type'] == 'image/png'
    assert downloaded.headers['content-disposition'].startswith('inline')
    assert client.get(url + '/download').headers['content-disposition'].startswith('attachment')
    with TestClient(main.app) as outsider:
        assert outsider.get(url).status_code == 404
    result = client.post('/api/chat', json={'conversation_id': cid, 'provider': 'auto', 'model': 'auto', 'regenerate': True})
    assert '"status": "complete"' in result.text
    assert calls[-1]['prompt'] == 'A green square'
    assert client.get(url).status_code == 404
    refreshed = client.get('/api/conversations/' + cid).json()
    assert len(refreshed['messages']) == 2
    assert len(refreshed['messages'][-1]['attachments']) == 1
    assert refreshed['pending_attachments'] == []


@pytest.mark.parametrize('wire', ['{"done":true}', '{"error":"unsupported"}', '{"image":"garbage","done":true}'])
def test_image_failure_is_not_a_text_success(client, monkeypatch, wire):
    monkeypatch.setattr(main, 'client', lambda *a: httpx.AsyncClient(base_url='http://test', transport=httpx.MockTransport(lambda req: httpx.Response(200, text=wire))))
    cid = client.post('/api/conversations').json()['id']
    result = client.post('/api/chat', json={'conversation_id':cid, 'content':'A cat', 'provider':'auto', 'model':'auto', 'output_mode':'image'})
    assert '"type": "error"' in result.text
    saved = client.get('/api/conversations/' + cid).json()['messages'][-1]
    assert saved['status'] == 'error'
    assert saved['attachments'] == []


def test_manual_text_model_never_silently_switched(client):
    cid = client.post('/api/conversations').json()['id']
    result = client.post('/api/chat', json={'conversation_id':cid, 'content':'A cat', 'provider':'ollama', 'model':'text-only', 'output_mode':'image'})
    assert result.status_code == 400
    assert client.get('/api/conversations/' + cid).json()['messages'] == []




def test_cancel_image_generation_closes_provider_stream():
    class SlowStream(httpx.AsyncByteStream):
        def __init__(self): self.closed = False
        async def __aiter__(self):
            yield b'{"completed":1,"total":10}\n'
            await asyncio.sleep(60)
        async def aclose(self): self.closed = True
    async def run():
        stream = SlowStream()
        started = asyncio.Event()
        async def notify(message): started.set()
        async with httpx.AsyncClient(base_url='http://test', transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=stream))) as c:
            task = asyncio.create_task(generate_image(c, 'ollama', 'painter', 'cat', notify))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
        assert stream.closed
    asyncio.run(run())


def test_reject_svg_and_remote_url():
    for value in [base64.b64encode(b'<svg onload="alert(1)"/>').decode(), 'https://internal/image.png']:
        with pytest.raises(ValueError): decode_image(value)


def test_uploaded_html_remains_download_only(client):
    cid = client.post('/api/conversations').json()['id']
    result = client.post(f'/api/conversations/{cid}/attachments', files={'file': ('page.html', b'<h1>Example</h1>', 'text/html')})
    assert result.status_code == 201
    response = client.get(f"/api/conversations/{cid}/attachments/{result.json()['id']}")
    assert response.headers['content-disposition'].startswith('attachment')


def test_image_only_ollama_is_available_for_images_not_chat(monkeypatch):
    from app import providers
    detail = model_detail('custom-painter', {'capabilities': ['image']}, local=True)
    state = {'working': True, 'models': ['custom-painter'], 'model_details': [detail]}
    coverage = providers.feature_coverage({'ollama': state})
    assert coverage['image_generation']['options'][0]['model'] == 'custom-painter'
    assert coverage['chat']['options'] == []
    assert not detail['supports_vision']





def test_auto_recognizes_explicit_image_request(client, monkeypatch, png):
    paths = []
    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={'done': True, 'image': base64.b64encode(png).decode()})
    monkeypatch.setattr(main, 'client', lambda *a: httpx.AsyncClient(base_url='http://test', transport=httpx.MockTransport(handler)))
    cid = client.post('/api/conversations').json()['id']
    result = client.post('/api/chat', json={'conversation_id':cid, 'provider':'auto', 'model':'auto', 'content':'Generate an image of a quiet forest'})
    assert paths == ['/api/generate']
    assert '"type": "image"' in result.text
    saved = client.get('/api/conversations/' + cid).json()
    assert saved['messages'][0]['output_mode'] == 'image'

import asyncio
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from app import main, providers
from app.ollama_catalog import model_detail


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'regression.db'))
    monkeypatch.setenv('GROQ_API_KEY', 'test-only')
    with TestClient(main.app) as c:
        yield c


def mock_transport(monkeypatch, handler):
    monkeypatch.setattr(main, 'client', lambda *args: httpx.AsyncClient(
        base_url='https://test.invalid', transport=httpx.MockTransport(handler)))


def test_regeneration_restores_prompt_and_does_not_duplicate_user(client, monkeypatch):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, text='{"message":{"content":"answer"}}\n{"done":true}\n')
    mock_transport(monkeypatch, handler)
    cid = client.post('/api/conversations').json()['id']
    client.post('/api/chat', json={'conversation_id': cid, 'content': 'Explain recursion'})
    result = client.post('/api/chat', json={'conversation_id': cid, 'regenerate': True, 'content': ''})
    assert calls[-1]['messages'][-1]['content'] == 'Explain recursion'
    assert '"status": "complete"' in result.text
    messages = client.get('/api/conversations/' + cid).json()['messages']
    assert len(messages) == 2
    assert messages[-1]['status'] == 'complete'


@pytest.mark.parametrize('wire', [
    'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
    'data: {"error":{"message":"bad"}}\n\ndata: [DONE]\n\n',
    'data: broken-json\n\n',
    'data: [DONE]\n\n',
])
def test_cloud_failures_are_not_saved_as_success(client, monkeypatch, wire):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, text=wire)
    mock_transport(monkeypatch, handler)
    cid = client.post('/api/conversations').json()['id']
    result = client.post('/api/chat', json={'conversation_id': cid, 'content': 'Hi',
                                          'provider': 'groq', 'model': 'openai/gpt-oss-20b'})
    assert '"type": "error"' in result.text
    assert '"status": "error"' in result.text
    assert len(calls) == 1  # Manual choices never fail over.
    assert client.get('/api/conversations/' + cid).json()['messages'][-1]['status'] == 'error'


def test_preparation_reserves_conversation_and_releases_on_failure(monkeypatch):
    monkeypatch.setattr(main, 'get_conversation_or_404', lambda *a: {})
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        async def prepare(*args):
            entered.set()
            await release.wait()
            raise ValueError('test preparation failure')
        monkeypatch.setattr(main, 'prepare_chat_response', prepare)
        from types import SimpleNamespace
        request = SimpleNamespace(state=SimpleNamespace(visitor_id='test-owner'))
        payload = main.ChatPayload(conversation_id='reserved')
        task = asyncio.create_task(main.stream_chat_response(payload, request))
        await entered.wait()
        try:
            with pytest.raises(main.HTTPException) as error:
                await main.stream_chat_response(payload, request)
            assert error.value.status_code == 409
        finally:
            release.set()
            with pytest.raises(ValueError):
                await task
        assert 'reserved' not in main.pending
    asyncio.run(run())


def test_fallbacks_never_select_unreported_models(monkeypatch):
    state = {'working': True, 'models': ['custom-text', 'custom-eye'], 'model_details': [
        model_detail('custom-text', {'capabilities': ['completion']}, local=True),
        model_detail('custom-eye', {'capabilities': ['completion', 'vision']}, local=True)]}
    monkeypatch.setattr(providers, '_HEALTH_CACHE', {'ollama': (time.time(), state)})
    assert providers.get_fallback_candidates('ollama', 'custom-eye', True, ['ollama']) == []
    assert providers.get_fallback_candidates('ollama', 'custom-text', False, []) == []
    fallback = providers.get_fallback_candidates('ollama', 'custom-text', False, ['ollama'])
    assert [m for _, m, _ in fallback] == ['custom-eye']


def test_ollama_metadata_probe_is_cached_and_does_not_guess(monkeypatch):
    monkeypatch.setenv('OLLAMA_BASE_URL', 'https://test.invalid')
    monkeypatch.setattr(providers, '_HEALTH_CACHE', {})
    requests = []
    def handler(request):
        requests.append(request.url.path)
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'fake-llava'}, {'name': 'custom-eye'}]})
        name = json.loads(request.content)['model']
        return httpx.Response(200, json={'capabilities': ['completion'] + (['vision'] if name == 'custom-eye' else [])})
    client_type = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, 'AsyncClient', lambda **kwargs: client_type(
        transport=httpx.MockTransport(handler), **kwargs))
    async def run():
        first = await providers.probe_provider_health('ollama')
        second = await providers.probe_provider_health('ollama')
        assert first == second
        details = {d['id']: d for d in first['model_details']}
        assert not details['fake-llava']['supports_vision']
        assert details['custom-eye']['supports_vision']
    asyncio.run(run())
    assert requests.count('/api/tags') == 1
    assert requests.count('/api/show') == 2

@pytest.mark.parametrize("agent_mode", [False, True])
@pytest.mark.parametrize("failure_status", [401, 402, 403, 429, 500, 503])
def test_auto_fails_over_before_output_and_records_actual_model(client, monkeypatch, failure_status, agent_mode):
    names = ['openai/gpt-oss-20b', 'openai/gpt-oss-120b']
    state = {'working': True, 'models': names}
    monkeypatch.setattr(providers, '_HEALTH_CACHE', {})
    async def probe(provider):
        result = state if provider == 'groq' else {'working': False, 'models': []}
        providers._HEALTH_CACHE[provider] = (time.time(), result)
        return result
    monkeypatch.setattr(main, 'probe_provider_health', probe)
    calls = []
    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload['model'])
        if len(calls) == 1:
            return httpx.Response(failure_status, json={'error': {'message': 'Provider unavailable'}})
        if agent_mode:
            return httpx.Response(200, json={'choices': [{'message': {'content': '{"action":"finish","answer":"success"}'}}]})
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"success"}}]}\n\ndata: [DONE]\n\n')
    mock_transport(monkeypatch, handler)
    cid = client.post('/api/conversations').json()['id']
    result = client.post('/api/chat', json={'conversation_id': cid, 'content': 'Hello', 'provider': 'auto', 'model': 'auto', 'agent_mode': agent_mode})
    assert '"type": "shift"' in result.text
    assert '"status": "complete"' in result.text
    assert len(calls) == 2 and set(calls) == set(names)
    saved = client.get('/api/conversations/' + cid).json()['messages'][-1]
    assert saved['model'] == 'groq:' + calls[-1]
    assert saved['auto_reason']


def test_regenerate_restores_document_attachment(client, monkeypatch, tmp_path):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'uploads'))
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, text='{"message":{"content":"answer"}}\n{"done":true}\n')
    mock_transport(monkeypatch, handler)
    cid = client.post('/api/conversations').json()['id']
    upload = client.post(f'/api/conversations/{cid}/attachments', files={'file': ('notes.txt', b'Project uses cedar wood.', 'text/plain')})
    assert upload.status_code == 201
    client.post('/api/chat', json={'conversation_id': cid, 'content': 'Summarize', 'attachment_ids': [upload.json()['id']]})
    client.post('/api/chat', json={'conversation_id': cid, 'regenerate': True})
    assert 'Project uses cedar wood.' in calls[-1]['messages'][-1]['content']
    assert 'Summarize' in calls[-1]['messages'][-1]['content']

@pytest.mark.parametrize('feature', ['chat', 'coding', 'reasoning', 'documents', 'web', 'vision'])
def test_feature_shortlists_offer_three_real_options(feature):
    details = [model_detail(f'custom-{i}', {'capabilities': ['completion', 'vision', 'thinking']}, local=True) for i in range(5)]
    health = {'ollama': {'working': True, 'models': [d['id'] for d in details], 'model_details': details}}
    coverage = providers.feature_coverage(health)
    assert coverage[feature]['status'] == 'ready'
    assert len(coverage[feature]['options']) == 3
    assert len({o['model'] for o in coverage[feature]['options']}) == 3
    assert not coverage['image_generation']['options']
    assert coverage['image_generation']['status'] == 'unavailable'


def test_feature_shortlist_reports_shortage_instead_of_inventing_models():
    detail = model_detail('text-only', {'capabilities': ['completion']}, local=True)
    health = {'ollama': {'working': True, 'models': ['text-only'], 'model_details': [detail]}}
    coverage = providers.feature_coverage(health)
    assert coverage['chat']['status'] == 'limited'
    assert len(coverage['chat']['options']) == 1
    assert coverage['vision']['status'] == 'unavailable'
    assert coverage['reasoning']['status'] == 'limited'
    assert 'general chat fallback' in coverage['reasoning']['options'][0]['reason']
    health['ollama']['working'] = False
    assert providers.feature_coverage(health)['chat']['options'] == []


def test_shortlist_prefers_independent_providers():
    details = [model_detail(f'custom-{i}', {'capabilities': ['completion']}, local=True) for i in range(3)]
    health = {'ollama': {'working': True, 'models': [d['id'] for d in details], 'model_details': details},
              'groq': {'working': True, 'models': ['openai/gpt-oss-20b']}}
    options = providers.recommend_models(health)
    assert len(options) == 3
    assert options[0]['provider'] != options[1]['provider']




def test_removed_provider_cannot_be_enabled_by_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "stale-key")
    assert "openrouter" not in providers.PROVIDERS
    assert not providers.is_provider_configured("openrouter")
    state = asyncio.run(providers.probe_provider_health("openrouter", force=True))
    assert not state["working"] and state["models"] == []


def test_agent_chat_endpoint_keeps_history_and_personalization(client, monkeypatch):
    async def probe(provider):
        return {'working': provider == 'groq', 'models': ['openai/gpt-oss-20b'] if provider == 'groq' else []}
    monkeypatch.setattr(main, 'probe_provider_health', probe)
    monkeypatch.setattr(main, 'profile_context', lambda *args: 'Saved preference: concise answers.')
    payloads = []
    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"action":"finish","answer":"Cedar"}'}}]})
    mock_transport(monkeypatch, handler)
    cid = client.post('/api/conversations').json()['id']
    for content in ['My project codename is Cedar.', 'Repeat my project codename.']:
        response = client.post('/api/chat', json={
            'conversation_id': cid, 'content': content, 'provider': 'groq',
            'model': 'openai/gpt-oss-20b', 'agent_mode': True,
        })
        assert '"status": "complete"' in response.text
    messages = payloads[-1]['messages']
    assert any(m['role'] == 'user' and 'My project codename is Cedar.' in m['content'] for m in messages)
    assert any(m['role'] == 'assistant' and 'Cedar' in m['content'] for m in messages)
    assert any(m['role'] == 'system' and 'Saved preference: concise answers.' in m['content'] for m in messages)

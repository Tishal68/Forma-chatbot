import httpx,time
from test_regressions import client,mock_transport
from app import main,providers

def test_empty_agent_response_must_not_finish_successfully(client,monkeypatch):
    names=['openai/gpt-oss-20b','openai/gpt-oss-120b']
    monkeypatch.setattr(providers,'_HEALTH_CACHE',{})
    async def probe(provider):
        result={'working':True,'models':names} if provider=='groq' else {'working':False,'models':[]}
        providers._HEALTH_CACHE[provider]=(time.time(),result)
        return result
    monkeypatch.setattr(main,'probe_provider_health',probe)
    mock_transport(monkeypatch,lambda request:httpx.Response(200,json={'choices':[{'message':{'content':''}}]}))
    cid=client.post('/api/conversations').json()['id']
    result=client.post('/api/chat',json={'conversation_id':cid,'content':'Hello','provider':'auto','model':'auto','agent_mode':True})
    saved=client.get('/api/conversations/'+cid).json()['messages'][-1]
    print('Saved response:',repr(saved['content']),'status:',saved['status'])
    assert saved['status'] != 'complete' or saved['content'].strip()


def test_auto_refuses_only_cooling_provider():
    import pytest
    providers.record_provider_failure('groq', 'auth_failure', status_code=401)
    with pytest.raises(ValueError, match='No available'):
        providers.choose_auto_model({'groq': {'working': True, 'models': ['openai/gpt-oss-20b']}},
                                   has_images=False, has_documents=False, is_web_search=False, content='Hello')


def test_auth_failure_does_not_retry_sibling_models(client, monkeypatch):
    async def probe(provider):
        result = ({'working': True, 'models': ['openai/gpt-oss-20b', 'openai/gpt-oss-120b']}
                  if provider == 'groq' else {'working': False, 'models': []})
        providers._HEALTH_CACHE[provider] = (time.time(), result)
        return result
    monkeypatch.setattr(main, 'probe_provider_health', probe)
    calls = []
    def fail(request):
        calls.append(request)
        return httpx.Response(401, json={'error': {'message': 'Invalid key'}})
    mock_transport(monkeypatch, fail)
    cid = client.post('/api/conversations').json()['id']
    response = client.post('/api/chat', json={'conversation_id': cid, 'content': 'Hello', 'provider': 'auto', 'model': 'auto'})
    assert '"status": "error"' in response.text
    assert len(calls) == 1


def test_tool_status_survives_reload_without_raw_payload(client, monkeypatch):
    from app.tools import record_tool_execution
    from app.database import connect
    mock_transport(monkeypatch, lambda request: httpx.Response(200, text='{"message":{"content":"answer"}}\n{"done":true}\n'))
    cid = client.post('/api/conversations').json()['id']
    client.post('/api/chat', json={'conversation_id': cid, 'content': 'Hello', 'provider': 'ollama', 'model': 'llama3.2'})
    mid = client.get('/api/conversations/' + cid).json()['messages'][-1]['id']
    with connect() as db:
        visitor = db.execute('SELECT visitor_id FROM conversations WHERE id = ?', (cid,)).fetchone()['visitor_id']
    record_tool_execution(visitor, cid, mid, 'calculator', {'expression': 'private-input'}, 'private-result', 1)
    message = client.get('/api/conversations/' + cid).json()['messages'][-1]
    assert message['agent_steps'] == [{'step': 1, 'action': 'tool', 'tool': 'calculator', 'status': 'success'}]
    assert 'private-input' not in str(message) and 'private-result' not in str(message)


def test_agent_invalid_outputs_raise_for_fallback():
    import asyncio
    import pytest
    from app.agent import run_agent_workflow
    async def run():
        async def emit(*args, **kwargs):
            pass
        for payload in ({}, {'choices': []}, {'choices': [{'message': {'content': '   '}}]},
                        {'choices': [{'message': {'content': '{"action":"finish","answer":123}'}}]}):
            async with httpx.AsyncClient(base_url='https://test.invalid', transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload))) as c:
                with pytest.raises(ValueError):
                    await run_agent_workflow(c, 'groq', 'test', 'Hello', 'test', 'test', 1, emit)
    asyncio.run(run())

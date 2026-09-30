import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app import main
from app.context import build_context, cost

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path/'test.db'))
    with TestClient(main.app) as client:
        yield client

def test_history_search_rename_delete_and_validation(client):
    cid=client.post('/api/conversations').json()['id']
    assert client.patch('/api/conversations/'+cid,json={'title':'Python notes'}).status_code==200
    assert len(client.get('/api/conversations?q=Python').json())==1
    assert client.post('/api/chat',json={'conversation_id':cid,'content':'   '}).status_code==422
    assert client.post('/api/chat',json={'conversation_id':cid,'content':'hi','temperature':9}).status_code==422
    assert client.delete('/api/conversations/'+cid).status_code==200
    assert client.get('/api/conversations/'+cid).status_code==404

def test_stream_context_regenerate_edit_and_isolation(client,monkeypatch):
    calls=[]
    def handler(request):
        body=json.loads(request.content);calls.append(body)
        return httpx.Response(200,content='\n'.join(json.dumps(x) for x in [
            {'message':{'content':'Hello '}},{'message':{'content':'world'}},{'done':True}]))
    monkeypatch.setattr(main,'client',lambda:httpx.AsyncClient(base_url='http://test',transport=httpx.MockTransport(handler)))
    cid=client.post('/api/conversations').json()['id']
    def send(**kwargs):return client.post('/api/chat',json={'conversation_id':cid,'content':'What is recursion?',**kwargs})
    result=send();assert '"type": "token"' in result.text
    assert 'Hello ' in result.text and 'world' in result.text
    send(content='Show it in Python')
    assert [m['role'] for m in calls[-1]['messages']]==['system','user','assistant','user']
    assert calls[-1]['messages'][1]['content']=='What is recursion?'
    send(regenerate=True)
    data=client.get('/api/conversations/'+cid).json()
    assert len(data['messages'])==4
    send(content='Explain trees',edit_message_id=data['messages'][0]['id'])
    data=client.get('/api/conversations/'+cid).json()
    assert len(data['messages'])==2
    assert calls[-1]['messages'][-1]['content']=='Explain trees'
    other=client.post('/api/conversations').json()['id']
    assert client.get('/api/conversations/'+other).json()['messages']==[]
    assert len(client.get('/api/conversations?q=trees').json())==1
    client.delete('/api/conversations/'+cid)
    with main.connect() as db:assert db.execute('SELECT count(*) FROM messages').fetchone()[0]==0

def test_error_persisted_without_trace(client,monkeypatch):
    def handler(request):raise httpx.ConnectError('sensitive server detail')
    monkeypatch.setattr(main,'client',lambda:httpx.AsyncClient(base_url='http://test',transport=httpx.MockTransport(handler)))
    cid=client.post('/api/conversations').json()['id']
    response=client.post('/api/chat',json={'conversation_id':cid,'content':'Hi'})
    assert 'Unable to connect to Ollama' in response.text
    assert 'sensitive server detail' not in response.text
    assert client.get('/api/conversations/'+cid).json()['messages'][-1]['status']=='error'
    assert cid not in main.active

def test_summary_bounded(monkeypatch):
    monkeypatch.setenv('CONTEXT_TOKENS','8192');monkeypatch.setenv('OUTPUT_TOKENS','4096')
    messages=[{'id':i+1,'role':'user' if i%2==0 else 'assistant','content':'Project uses Python. '*70} for i in range(10)]
    messages.append({'id':11,'role':'user','content':'What language are we using?'})
    saved=[]
    async def run():
        async def notify(message):pass
        async with httpx.AsyncClient(base_url='http://test',transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'message':{'content':'Project uses Python.'}}))) as c:
            result=await build_context(c,'test',{'summary':'','summary_through':0},messages,lambda s,i:saved.append((s,i)),notify)
        assert cost(result)<=4096
        assert result[-1]['content']=='What language are we using?'
        assert 'Python' in result[1]['content']
    asyncio.run(run());assert saved

def test_origin_guard(client):
    assert client.post('/api/conversations',headers={'origin':'https://untrusted.example'}).status_code==403


def test_cloud_providers_and_streaming(client, monkeypatch):
    # Test listing models for Groq
    res = client.get('/api/models?provider=groq')
    assert res.status_code == 200
    data = res.json()
    assert 'openai/gpt-oss-120b' in data['models']
    assert data['provider'] == 'groq'

    # Test missing API key validation
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    cid = client.post('/api/conversations').json()['id']
    err_res = client.post('/api/chat', json={
        'conversation_id': cid,
        'content': 'Hello',
        'provider': 'groq',
    })
    assert err_res.status_code == 400
    assert 'API key' in err_res.json()['detail']

    # Test OpenAI-compatible streaming
    def openai_handler(request):
        # OpenAI SSE format
        body = json.loads(request.content)
        assert body['model'] == 'openai/gpt-oss-120b'
        stream_chunks = [
            'data: {"choices": [{"delta": {"content": "Fast "}}]}\n\n',
            'data: {"choices": [{"delta": {"content": "intelligence!"}}]}\n\n',
            'data: [DONE]\n\n',
        ]
        return httpx.Response(200, content=''.join(stream_chunks))

    monkeypatch.setattr(
        main,
        'client',
        lambda *args, **kwargs: httpx.AsyncClient(base_url='https://api.groq.com/openai/v1', transport=httpx.MockTransport(openai_handler)),
    )

    stream_res = client.post('/api/chat', json={
        'conversation_id': cid,
        'content': 'Explain fast AI',
        'provider': 'groq',
        'api_key': 'gsk_testkey',
    })
    assert stream_res.status_code == 200
    assert 'Fast ' in stream_res.text
    assert 'intelligence!' in stream_res.text


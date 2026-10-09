import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.tools import (
    execute_safe_python,
    process_structured_data,
    record_tool_execution,
    execute_tool,
)
from app.agent import parse_agent_action, run_agent_workflow
from app.database import initialize, connect


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'chat.db'))
    monkeypatch.setenv('SESSION_SECRET', 'test-tools-secret-123')
    initialize()


@pytest.mark.parametrize('code', [
    'result = 2 + 2',
    "result = print.__globals__.get('__builtins__')['eval']('6 * 7')",
    'while True: pass',
])
def test_python_execution_is_disabled(code):
    from app.tools import TOOLS_REGISTRY
    assert 'python_sandbox' not in TOOLS_REGISTRY
    result = execute_safe_python(code)
    assert result['status'] == 'error'
    assert 'disabled' in result['error']
    dispatched = asyncio.run(execute_tool('python_sandbox', {'code': code}, 'test', 'test'))
    assert dispatched['status'] == 'error'


def test_structured_data_processor():
    csv_data = (
        "Item,Price,Quantity\n"
        "Widget A,10.5,5\n"
        "Widget B,20.0,2\n"
        "Widget C,15.5,4\n"
    )
    res_csv = process_structured_data(csv_data, data_format='csv')
    assert res_csv['status'] == 'success'
    assert res_csv['total_rows'] == 3
    assert 'Price' in res_csv['numeric_statistics']
    assert res_csv['numeric_statistics']['Price']['min'] == 10.5
    assert res_csv['numeric_statistics']['Price']['max'] == 20.0


def test_tool_audit_logging_and_api():
    client = TestClient(app)
    cid = client.post('/api/conversations').json()['id']
    with connect() as db:
        conv = db.execute('SELECT visitor_id FROM conversations WHERE id = ?', (cid,)).fetchone()
        visitor_id = conv['visitor_id']

    # Execute a tool
    exec_id = record_tool_execution(
        visitor_id=visitor_id,
        conversation_id=cid,
        message_id=1,
        tool_name='python_sandbox',
        input_args={'code': 'result = 2 + 2'},
        output_summary='{"status": "success", "result": 4}',
        duration_ms=12,
        status='success',
    )
    assert exec_id

    # Query via endpoint
    resp = client.get(f'/api/conversations/{cid}/tools/audit')
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert logs[0]['tool_name'] == 'python_sandbox'
    assert logs[0]['status'] == 'success'


def test_agent_action_parsing():
    raw_tool = '```json\n{"action": "tool", "tool": "python_sandbox", "args": {"code": "2+2"}, "thought": "calculate"}\n```'
    parsed = parse_agent_action(raw_tool)
    assert parsed['action'] == 'tool'
    assert parsed['tool'] == 'python_sandbox'

    raw_finish = '```json\n{"action": "finish", "answer": "The total is 4."}\n```'
    parsed_finish = parse_agent_action(raw_finish)
    assert parsed_finish['action'] == 'finish'
    assert parsed_finish['answer'] == 'The total is 4.'

    raw_text = 'Here is plain text without json.'
    parsed_plain = parse_agent_action(raw_text)
    assert parsed_plain['action'] == 'finish'
    assert 'plain text' in parsed_plain['answer']


def test_agent_preserves_context_and_propagates_provider_errors():
    import httpx
    import json
    context = [
        {'role': 'system', 'content': 'Saved preference: use short answers.'},
        {'role': 'user', 'content': 'My project is Cedar.'},
        {'role': 'assistant', 'content': 'Understood.'},
        {'role': 'user', 'content': 'What is its name? Evidence: Cedar.'},
    ]
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"action":"finish","answer":"Cedar"}'}}]})
    async def emit(*args, **kwargs): pass
    async def run():
        async with httpx.AsyncClient(base_url='https://test.invalid', transport=httpx.MockTransport(handler)) as client:
            answer = await run_agent_workflow(client, 'groq', 'test', 'What is its name?', 'test', 'test', 1, emit, context_messages=context)
            assert answer == 'Cedar'
        async with httpx.AsyncClient(base_url='https://test.invalid', transport=httpx.MockTransport(
            lambda request: httpx.Response(429))) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await run_agent_workflow(client, 'groq', 'test', 'Hello', 'test', 'test', 1, emit)
    asyncio.run(run())
    assert calls[0]['messages'][1:] == context[1:]
    assert 'Saved preference: use short answers.' in calls[0]['messages'][0]['content']
    assert 'python_sandbox' not in calls[0]['messages'][0]['content']
    assert context[0]['content'] == 'Saved preference: use short answers.'


def test_agent_step_limit_includes_last_observation_and_propagates_summary_failure(monkeypatch):
    import httpx
    import json
    from app import agent
    async def tool(**kwargs): return {'status': 'success', 'result': 'LAST_OBSERVATION'}
    monkeypatch.setattr(agent, 'execute_tool', tool)
    async def emit(*args, **kwargs): pass
    async def run(fail_summary):
        calls = []
        def handler(request):
            calls.append(json.loads(request.content))
            if len(calls) == 1:
                content = json.dumps({'action': 'tool', 'tool': 'data_processor', 'args': {'data': 'x'}})
                return httpx.Response(200, json={'choices': [{'message': {'content': content}}]})
            assert 'LAST_OBSERVATION' in calls[-1]['messages'][-1]['content']
            return httpx.Response(503 if fail_summary else 200, json={'choices': [{'message': {'content': 'Done'}}]})
        async with httpx.AsyncClient(base_url='https://test.invalid', transport=httpx.MockTransport(handler)) as client:
            if fail_summary:
                with pytest.raises(httpx.HTTPStatusError):
                    await run_agent_workflow(client, 'groq', 'test', 'Summarize', 'test', 'test', 1, emit, max_steps=1)
            else:
                assert await run_agent_workflow(client, 'groq', 'test', 'Summarize', 'test', 'test', 1, emit, max_steps=1) == 'Done'
    asyncio.run(run(False))
    asyncio.run(run(True))

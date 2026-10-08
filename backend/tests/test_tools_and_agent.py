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


def test_safe_python_execution_success_and_math():
    code = (
        "import math\n"
        "radius = 5\n"
        "area = math.pi * radius ** 2\n"
        "print(f'Area: {round(area, 2)}')\n"
        "result = round(area, 2)\n"
    )
    res = execute_safe_python(code)
    assert res['status'] == 'success'
    assert 'Area: 78.54' in res['stdout']
    assert res['result'] == '78.54'


def test_safe_python_blocks_malicious_imports_and_builtins():
    # Attempting to import os
    res_os = execute_safe_python("import os\nos.system('dir')")
    assert res_os['status'] == 'error'
    assert 'prohibited' in res_os['error'].lower()

    # Attempting to use open()
    res_open = execute_safe_python("f = open('secret.txt', 'w')")
    assert res_open['status'] == 'error'
    assert 'restricted' in res_open['error'].lower() or 'blocked' in res_open['error'].lower()


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

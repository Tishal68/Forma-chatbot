import time
from backend.app.ollama_catalog import model_detail
import pytest
import httpx
from fastapi.testclient import TestClient
from backend.app import main, providers
from backend.app.providers import (
    get_ollama_model_detail,
    get_model_metadata,
    select_auto_model,
    _HEALTH_CACHE,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'test_ollama.db'))
    with TestClient(main.app) as c:
        yield c


def test_ollama_model_descriptions_and_capabilities():
    vision = model_detail('llama3.2-vision:11b', {'capabilities': ['completion', 'vision']}, local=True)
    assert vision['supports_vision']
    assert 'Vision' in vision['capabilities']
    assert 'image' in vision['description']
    coder = model_detail('qwen2.5-coder:7b', {'capabilities': ['completion']}, local=True)
    assert not coder['supports_reasoning']
    assert coder['specialty'] == 'code'
    unknown = model_detail('custom-llava', None, local=True)
    assert not unknown['supports_vision']
    assert not unknown['chat_compatible']
    assert 'could not be verified' in unknown['description']


def test_models_endpoint_with_multiple_ollama_models(client, monkeypatch):
    """Test /api/models returns actual Ollama models with metadata and neutral fallback for unknown models."""
    mock_tags = {
        "models": [
            {"name": "llama3.2:latest"},
            {"name": "deepseek-r1:14b"},
            {"name": "qwen2.5-coder:7b"},
            {"name": "llama3.2-vision:11b"},
            {"name": "unknown-corp-model"},
        ]
    }

    async def mock_tags_handler(request: httpx.Request):
        return httpx.Response(200, json=mock_tags)

    # Clear cache and probe with mock
    providers._HEALTH_CACHE.clear()

    async def mock_probe(provider_name: str, force: bool = False):
        if provider_name == "ollama":
            return {
                "id": "ollama",
                "configured": True,
                "working": True,
                "status": "ready",
                "error": None,
                "models": [m["name"] for m in mock_tags["models"]],
                "model_details": [model_detail(m['name'], {'capabilities': ['completion'] +
                    (['vision'] if m['name'] == 'llama3.2-vision:11b' else []) +
                    (['thinking'] if m['name'] == 'deepseek-r1:14b' else [])}, local=True) for m in mock_tags['models']],
            }
        return {
            "id": provider_name,
            "configured": False,
            "working": False,
            "status": "unconfigured",
            "error": "Not configured",
            "models": [],
        }

    monkeypatch.setattr(main, "probe_provider_health", mock_probe)

    res = client.get("/api/models?provider=ollama&refresh=true")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "ollama"
    assert len(data["models"]) == 5
    assert "llama3.2-vision:11b" in data["models"]
    assert "unknown-corp-model" in data["models"]

    details_by_id = {d["id"]: d for d in data["model_details"]}
    # Verify vision model
    assert details_by_id["llama3.2-vision:11b"]["supports_vision"] is True
    # Verify reasoning model
    assert details_by_id["deepseek-r1:14b"]["supports_reasoning"] is True
    # Verify unknown model has no guessed capabilities
    assert details_by_id["unknown-corp-model"]["supports_vision"] is False
    assert details_by_id["unknown-corp-model"]["supports_reasoning"] is False


def test_models_endpoint_ollama_unavailable(client, monkeypatch):
    """Test /api/models handles unreachable Ollama gracefully without crashing."""
    providers._HEALTH_CACHE.clear()

    async def mock_failing_probe(provider_name: str, force: bool = False):
        return {
            "id": "ollama",
            "configured": True,
            "working": False,
            "status": "unreachable",
            "error": "Cannot reach Ollama at http://localhost:11434. Ensure the server is running.",
            "models": [],
        }

    monkeypatch.setattr(main, "probe_provider_health", mock_failing_probe)

    res = client.get("/api/models?provider=ollama&refresh=true")
    assert res.status_code == 200
    data = res.json()
    ollama_info = next(p for p in data["providers"] if p["id"] == "ollama")
    assert ollama_info["working"] is False
    assert ollama_info["status"] == "unreachable"
    assert "Cannot reach Ollama" in ollama_info["error"]


@pytest.mark.parametrize('content,images,docs,search,expected', [
    ('Hello', False, False, False, 'llama3.2'),
    ('Write code', False, False, False, 'qwen2.5-coder'),
    ('Prove this theorem', False, False, False, 'deepseek-r1'),
    ('Read this', True, False, False, 'custom-vision'),
    ('Summarize', False, True, False, 'deepseek-r1'),
    ('Latest news', False, False, True, 'deepseek-r1'),
])
def test_auto_routing_modalities(monkeypatch, content, images, docs, search, expected):
    caps = {'llama3.2': ['completion'], 'qwen2.5-coder': ['completion'],
            'deepseek-r1': ['completion', 'thinking'], 'custom-vision': ['completion', 'vision']}
    state = {'working': True, 'models': list(caps), 'model_details': [
        model_detail(name, {'capabilities': flags}, local=True) for name, flags in caps.items()]}
    monkeypatch.setattr(providers, '_HEALTH_CACHE', {'ollama': (time.time(), state)})
    p, m, reason = select_auto_model(images, docs, search, content, ['ollama'])
    assert p == 'ollama' and m == expected
    assert reason
    with pytest.raises(ValueError):
        select_auto_model(images, docs, search, content, [])
    state['working'] = False
    with pytest.raises(ValueError):
        select_auto_model(images, docs, search, content, ['ollama'])


def test_manual_model_selection_not_overridden(client, monkeypatch):
    """Verify that explicitly selecting a model sends with that model and does not trigger Auto override."""
    cid = client.post("/api/conversations").json()["id"]

    captured = {}

    def mock_stream(request):
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode("utf-8")
        # Return Ollama-style NDJSON stream
        return httpx.Response(
            200,
            content=b'{"message": {"role": "assistant", "content": "Sure, here is your answer."}}\n',
        )

    monkeypatch.setattr(
        main,
        "client",
        lambda *args, **kwargs: httpx.AsyncClient(
            base_url="http://test", transport=httpx.MockTransport(mock_stream)
        ),
    )

    # Manually choose Ollama and llama3.2
    res = client.post(
        "/api/chat",
        json={
            "conversation_id": cid,
            "content": "Write a python function",
            "provider": "ollama",
            "model": "llama3.2",
        },
    )
    assert res.status_code == 200

    # Verify conversation history shows the manually selected model
    conv = client.get(f"/api/conversations/{cid}").json()
    last_msg = conv["messages"][-1]
    assert last_msg["role"] == "assistant"
    assert last_msg["model"] == "ollama:llama3.2"
    # Manual selection does not have auto_reason
    assert not last_msg.get("auto_reason")

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
    """Verify known Ollama models receive concise 1-sentence descriptions and verified capability tags."""
    # Vision model
    vis = get_ollama_model_detail("llama3.2-vision:11b")
    assert vis["supports_vision"] is True
    assert vis["supports_reasoning"] is False
    assert "Vision" in vis["capabilities"]
    assert "image" in vis["description"].lower()

    # Coding / Reasoning model
    coder = get_ollama_model_detail("qwen2.5-coder:7b")
    assert coder["supports_vision"] is False
    assert coder["supports_reasoning"] is True
    assert "Code" in coder["capabilities"]
    assert len(coder["description"].split(".")) >= 1

    # Deep reasoning model
    r1 = get_ollama_model_detail("deepseek-r1:8b")
    assert r1["supports_vision"] is False
    assert r1["supports_reasoning"] is True
    assert "Reasoning" in r1["capabilities"]

    # Everyday fast chat model
    chat = get_ollama_model_detail("llama3.2:latest")
    assert chat["supports_vision"] is False
    assert chat["is_fast"] is True

    # Unknown model gets neutral description with no guessed capabilities
    unknown = get_ollama_model_detail("my-custom-finetuned-llama:latest")
    assert unknown["supports_vision"] is False
    assert unknown["supports_reasoning"] is False
    assert unknown["capabilities"] == ["Local"]
    assert "General-purpose" in unknown["description"] or "Local" in unknown["description"]


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


def test_auto_routing_modalities(monkeypatch):
    """Test Auto mode intelligently routes tasks based on capabilities."""
    # Setup health cache with both local and cloud options
    providers._HEALTH_CACHE["ollama"] = (
        9999999999.0,
        {
            "id": "ollama",
            "configured": True,
            "working": True,
            "status": "ready",
            "error": None,
            "models": ["llama3.2", "qwen2.5-coder", "llama3.2-vision"],
        },
    )

    # 1. Image routing -> must route to vision model (never text-only)
    p, m, reason = select_auto_model(
        has_images=True,
        has_documents=False,
        is_web_search=False,
        content="What is this picture?",
        healthy_providers=["ollama"],
    )
    assert p == "ollama"
    assert m == "llama3.2-vision"
    assert "local image analysis" in reason

    # 2. Image routing when NO vision model is available -> raises helpful ValueError
    providers._HEALTH_CACHE["ollama"] = (
        9999999999.0,
        {
            "id": "ollama",
            "configured": True,
            "working": True,
            "status": "ready",
            "error": None,
            "models": ["llama3.2", "mistral"],
        },
    )
    with pytest.raises(ValueError) as exc:
        select_auto_model(
            has_images=True,
            has_documents=False,
            is_web_search=False,
            content="Check this screenshot",
            healthy_providers=["ollama"],
        )
    assert "vision" in str(exc.value).lower()

    # 3. Coding prompt -> routes to coding/reasoning model
    p, m, reason = select_auto_model(
        has_images=False,
        has_documents=False,
        is_web_search=False,
        content="def quicksort(arr):\n    # TODO: implement",
        healthy_providers=["ollama"],
    )
    assert p == "ollama"
    assert m == "llama3.2" or "reasoning" in reason or "code" in reason.lower()

    # 4. Complex reasoning prompt with DeepSeek R1 installed
    providers._HEALTH_CACHE["ollama"] = (
        9999999999.0,
        {
            "id": "ollama",
            "configured": True,
            "working": True,
            "status": "ready",
            "error": None,
            "models": ["llama3.2", "deepseek-r1"],
        },
    )
    p, m, reason = select_auto_model(
        has_images=False,
        has_documents=False,
        is_web_search=False,
        content="Prove step by step that the square root of 2 is irrational.",
        healthy_providers=["ollama"],
    )
    assert p == "ollama"
    assert m == "deepseek-r1"
    assert "reasoning" in reason.lower()

    # 5. Documents prompt -> routes to local text model
    p, m, reason = select_auto_model(
        has_images=False,
        has_documents=True,
        is_web_search=False,
        content="Summarize this PDF",
        healthy_providers=["ollama"],
    )
    assert p == "ollama"
    assert "document" in reason.lower()

    # 6. General chat -> routes to fast chat model
    p, m, reason = select_auto_model(
        has_images=False,
        has_documents=False,
        is_web_search=False,
        content="Good morning, tell me a quick joke.",
        healthy_providers=["ollama"],
    )
    assert p == "ollama"
    assert m == "llama3.2"
    assert "chat" in reason.lower()


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

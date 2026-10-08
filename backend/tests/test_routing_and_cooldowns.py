import time
import pytest
from app.routing import explicit_task, infer_task
from app.providers import (
    record_provider_failure,
    record_provider_success,
    is_provider_cooling_down,
    clear_cooldowns,
    choose_auto_model,
    get_fallback_candidates,
)


def setup_function():
    clear_cooldowns()


def teardown_function():
    clear_cooldowns()


def test_task_classification_research_and_math():
    assert explicit_task("Conduct a literature review on transformers.") == "research"
    assert explicit_task("Provide a comprehensive analysis of renewable energy.") == "research"
    assert explicit_task("Solve the differential equation dy/dx = 2x.") == "complex reasoning"
    assert explicit_task("Calculate the matrix determinant.") == "complex reasoning"
    assert explicit_task("Write a quick poem about autumn.") == "writing"
    assert explicit_task("Write a python script to fetch web pages.") == "coding"
    assert explicit_task("How are you feeling today?") is None
    assert infer_task("How are you feeling today?") == "everyday chat"


def test_cooldown_recording_and_backoff():
    # Test rate limit cooldown
    dur1 = record_provider_failure("groq", "rate_limit", status_code=429)
    assert dur1 == 60.0
    is_cooling, reason, remaining = is_provider_cooling_down("groq")
    assert is_cooling is True
    assert reason == "rate_limit"
    assert 55.0 <= remaining <= 60.0

    # Consecutive failure increases backoff
    dur2 = record_provider_failure("groq", "rate_limit", status_code=429)
    assert dur2 == 90.0

    # Auth failure gets long cooldown
    dur_auth = record_provider_failure("gemini", "auth_failure", status_code=401)
    assert dur_auth == 3600.0
    assert is_provider_cooling_down("gemini")[1] == "auth_failure"

    # Server error
    dur_server = record_provider_failure("ollama", "server_error", status_code=503)
    assert dur_server == 30.0

    # Success clears cooldown
    record_provider_success("groq")
    assert is_provider_cooling_down("groq")[0] is False


def test_choose_auto_model_avoids_cooling_provider():
    health = {
        "groq": {
            "working": True,
            "models": ["openai/gpt-oss-20b"],
            "model_details": [{
                "id": "openai/gpt-oss-20b", "name": "GPT-OSS 20B", "provider": "groq",
                "supports_vision": False, "supports_reasoning": True, "context_window": 131072,
                "is_fast": True, "routing_priority": 85, "capabilities": ["Fast", "Reasoning"]
            }]
        },
        "gemini": {
            "working": True,
            "models": ["gemini-flash-lite-latest"],
            "model_details": [{
                "id": "gemini-flash-lite-latest", "name": "Gemini Flash Lite", "provider": "gemini",
                "supports_vision": True, "supports_reasoning": False, "context_window": 1048576,
                "is_fast": True, "routing_priority": 75, "capabilities": ["Vision", "Fast"]
            }]
        }
    }

    # Before cooldown, groq has higher priority for reasoning
    p1, m1, _ = choose_auto_model(health, has_images=False, has_documents=False, is_web_search=False, content="Prove theorem")
    assert p1 == "groq"

    # Mark groq in cooldown
    record_provider_failure("groq", "rate_limit", status_code=429)
    assert is_provider_cooling_down("groq")[0] is True

    # Now choose_auto_model automatically routes to gemini to avoid the cooling provider
    p2, m2, _ = choose_auto_model(health, has_images=False, has_documents=False, is_web_search=False, content="Prove theorem")
    assert p2 == "gemini"

    # When groq recovers, it is available again
    record_provider_success("groq")
    p3, m3, _ = choose_auto_model(health, has_images=False, has_documents=False, is_web_search=False, content="Prove theorem")
    assert p3 == "groq"

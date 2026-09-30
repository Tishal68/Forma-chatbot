import os
import time
from typing import Any
import httpx
from .config import settings

# Pre-configured providers and their top models
PROVIDERS: dict[str, dict[str, Any]] = {
    "groq": {
        "id": "groq",
        "name": "Groq",
        "tagline": "Lightning Fast",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "key_url": "https://console.groq.com/keys",
        "default_model": "openai/gpt-oss-120b",
        "models": [
            {
                "id": "openai/gpt-oss-120b",
                "name": "GPT-OSS 120B",
                "badge": "⚡ Blazing Fast & Reasoning",
                "description": "Massive 120B parameter open-weights model. Exceptional reasoning, coding, and writing at 300+ tokens/sec.",
            },
            {
                "id": "openai/gpt-oss-20b",
                "name": "GPT-OSS 20B",
                "badge": "⚡ Ultra Fast (500+ tok/s)",
                "description": "Blazing fast 20B model for instant answers and code generation.",
            },
            {
                "id": "qwen/qwen3.8-27b",
                "name": "Qwen 3.8 27B",
                "badge": "🧠 Deep STEM & Math",
                "description": "Advanced 27B model optimized for multi-step reasoning and analytical tasks.",
            },
            {
                "id": "allam-2-7b",
                "name": "ALLaM 2 7B",
                "badge": "🌐 Multilingual",
                "description": "High-efficiency multilingual instruction model.",
            },
        ],
    },
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "tagline": "All Frontier Models",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "key_url": "https://openrouter.ai/keys",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "models": [
            {
                "id": "meta-llama/llama-3.3-70b-instruct",
                "name": "Llama 3.3 70B Instruct",
                "badge": "⚡ Top Frontier Open",
                "description": "Meta's flagship open-weights instruction model with outstanding general intelligence.",
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "badge": "👑 Coding & Reasoning",
                "description": "Anthropic's gold standard for complex coding and deep analysis.",
            },
            {
                "id": "deepseek/deepseek-r1",
                "name": "DeepSeek R1",
                "badge": "🧠 Reasoning Leader",
                "description": "Frontier open reasoning benchmark leader with chain-of-thought.",
            },
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o (OpenRouter)",
                "badge": "🧠 Omni Intelligence",
                "description": "OpenAI flagship multimodal intelligence accessed via OpenRouter.",
            },
        ],
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "tagline": "GPT-4o & Reasoning",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
        "default_model": "gpt-4o-mini",
        "models": [
            {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "badge": "⚡ Fast & Intelligent",
                "description": "Affordable, fast, and high-performance model for day-to-day coding and chat.",
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "badge": "🧠 Flagship Multimodal",
                "description": "OpenAI's flagship omni model for complex programming, analysis, and multimodal input.",
            },
            {
                "id": "o3-mini",
                "name": "o3-mini (Reasoning)",
                "badge": "🔬 STEM / Logic",
                "description": "Specialized reasoning model with deep step-by-step thinking.",
            },
        ],
    },
    "gemini": {
        "id": "gemini",
        "name": "Google Gemini",
        "tagline": "Next-Gen Multimodal",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GEMINI_API_KEY",
        "key_url": "https://aistudio.google.com/app/apikey",
        "default_model": "gemini-3.8-flash",
        "models": [
            {
                "id": "gemini-2.5-flash",
                "name": "Gemini 2.5 Flash",
                "badge": "⚡ Blazing Fast",
                "description": "Google's modern high-speed multimodal model with advanced reasoning.",
            },
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro",
                "badge": "🧠 Deep Analysis",
                "description": "Massive context window with advanced multimodal and reasoning capabilities.",
            },
            {
                "id": "gemini-3.8-flash",
                "name": "Gemini 3.8 Flash",
                "badge": "⚡ Next-Gen Flash",
                "description": "Next-generation Gemini model built for low latency and high accuracy.",
            },
            {
                "id": "gemini-flash-latest",
                "name": "Gemini Flash (Latest)",
                "badge": "⚡ Stable Latest",
                "description": "Latest stable production release of Gemini Flash.",
            },
        ],
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama",
        "tagline": "Local Offline",
        "base_url": "",
        "api_key_env": "OLLAMA_API_KEY",
        "key_url": "https://ollama.com",
        "default_model": "llama3.2",
        "models": [],
    },
}


def get_provider_config(provider_name: str) -> dict:
    """Retrieve static configuration for a provider."""
    p_lower = (provider_name or "").lower().strip()
    return PROVIDERS.get(p_lower, PROVIDERS["groq"])


def get_api_key(provider_name: str) -> str | None:
    """
    Retrieve provider API key strictly from server environment.
    Never accepts client keys or exposes them to callers.
    """
    config = get_provider_config(provider_name)
    env_var = config.get("api_key_env")
    if env_var:
        val = os.getenv(env_var, "").strip()
        return val or None
    return None


def is_provider_configured(provider_name: str) -> bool:
    """
    Check if a provider is configured in the environment.
    Ollama is considered configured if OLLAMA_BASE_URL is set, or in development if default exists.
    Cloud providers require their specific API key environment variable.
    """
    p_lower = (provider_name or "").lower().strip()
    if p_lower == "ollama":
        url = os.getenv("OLLAMA_BASE_URL", "").strip()
        if url:
            return True
        if not settings.is_production:
            return True
        return False

    config = PROVIDERS.get(p_lower)
    if not config:
        return False
    env_var = config.get("api_key_env")
    if env_var:
        return bool(os.getenv(env_var, "").strip())
    return False


# In-memory health probe cache (TTL = 60s)
_HEALTH_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 60.0


async def probe_provider_health(provider_name: str, force: bool = False) -> dict[str, Any]:
    """
    Probe the operational health of a provider without relying on key presence alone.
    Returns: {
        'id': str,
        'configured': bool,
        'working': bool,
        'status': 'ready' | 'invalid_key' | 'quota_exceeded' | 'outage' | 'unreachable' | 'unconfigured',
        'error': str | None,
        'models': list[str],
    }
    """
    p_lower = (provider_name or "").lower().strip()
    now_ts = time.time()

    if not force and p_lower in _HEALTH_CACHE:
        cached_time, cached_result = _HEALTH_CACHE[p_lower]
        if now_ts - cached_time < CACHE_TTL_SECONDS:
            return dict(cached_result)

    config = PROVIDERS.get(p_lower)
    if not config:
        res = {
            "id": p_lower,
            "configured": False,
            "working": False,
            "status": "unconfigured",
            "error": "Unknown provider",
            "models": [],
        }
        _HEALTH_CACHE[p_lower] = (now_ts, res)
        return res

    if not is_provider_configured(p_lower):
        res = {
            "id": p_lower,
            "configured": False,
            "working": False,
            "status": "unconfigured",
            "error": f"{config['name']} is not configured on this server.",
            "models": [],
        }
        _HEALTH_CACHE[p_lower] = (now_ts, res)
        return res

    # Ollama probe
    if p_lower == "ollama":
        base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        api_key = get_api_key("ollama")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=2.0)) as c:
                response = await c.get(f"{base_url}/api/tags", headers=headers)
                if response.status_code == 200:
                    installed = [m["name"] for m in response.json().get("models", [])]
                    res = {
                        "id": "ollama",
                        "configured": True,
                        "working": True,
                        "status": "ready",
                        "error": None,
                        "models": installed if installed else [settings.OLLAMA_MODEL],
                    }
                else:
                    res = {
                        "id": "ollama",
                        "configured": True,
                        "working": False,
                        "status": "error",
                        "error": f"Ollama returned HTTP status {response.status_code}",
                        "models": [],
                    }
        except Exception:
            res = {
                "id": "ollama",
                "configured": True,
                "working": False,
                "status": "unreachable",
                "error": f"Cannot reach Ollama at {base_url}. Ensure the server is running.",
                "models": [],
            }
        _HEALTH_CACHE["ollama"] = (now_ts, res)
        return res

    # Cloud provider probe
    key = get_api_key(p_lower)
    headers = {"Authorization": f"Bearer {key}"}
    if p_lower == "openrouter":
        headers["HTTP-Referer"] = "https://forma.local"
        headers["X-Title"] = "Forma"
        probe_url = "https://openrouter.ai/api/v1/auth/key"
    elif p_lower == "gemini":
        probe_url = "https://generativelanguage.googleapis.com/v1beta/openai/models"
    elif p_lower == "groq":
        probe_url = "https://api.groq.com/openai/v1/models"
    elif p_lower == "openai":
        probe_url = "https://api.openai.com/v1/models"
    else:
        probe_url = f"{config['base_url']}/models"

    curated_ids = [m["id"] for m in config.get("models", [])]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=3.0)) as c:
            response = await c.get(probe_url, headers=headers)
            status_code = response.status_code
            if status_code == 200:
                res = {
                    "id": p_lower,
                    "configured": True,
                    "working": True,
                    "status": "ready",
                    "error": None,
                    "models": curated_ids,
                }
            elif status_code == 401:
                res = {
                    "id": p_lower,
                    "configured": True,
                    "working": False,
                    "status": "invalid_key",
                    "error": f"Invalid or revoked API key for {config['name']}.",
                    "models": curated_ids,
                }
            elif status_code == 429:
                res = {
                    "id": p_lower,
                    "configured": True,
                    "working": False,
                    "status": "quota_exceeded",
                    "error": f"Rate limit or quota exceeded for {config['name']}.",
                    "models": curated_ids,
                }
            elif status_code in (502, 503, 504):
                res = {
                    "id": p_lower,
                    "configured": True,
                    "working": False,
                    "status": "outage",
                    "error": f"{config['name']} service is temporarily unavailable ({status_code}).",
                    "models": curated_ids,
                }
            else:
                res = {
                    "id": p_lower,
                    "configured": True,
                    "working": False,
                    "status": "error",
                    "error": f"{config['name']} returned HTTP {status_code}.",
                    "models": curated_ids,
                }
    except httpx.ConnectError:
        res = {
            "id": p_lower,
            "configured": True,
            "working": False,
            "status": "unreachable",
            "error": f"Network connection to {config['name']} failed.",
            "models": curated_ids,
        }
    except httpx.TimeoutException:
        res = {
            "id": p_lower,
            "configured": True,
            "working": False,
            "status": "timeout",
            "error": f"Connection to {config['name']} timed out.",
            "models": curated_ids,
        }
    except Exception as exc:
        res = {
            "id": p_lower,
            "configured": True,
            "working": False,
            "status": "error",
            "error": f"Unable to reach {config['name']}: {type(exc).__name__}",
            "models": curated_ids,
        }

    _HEALTH_CACHE[p_lower] = (now_ts, res)
    return res

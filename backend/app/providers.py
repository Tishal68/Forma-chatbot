import os
import time
from typing import Any
import httpx
from .config import settings

# Pre-configured providers and their top models with verified capability metadata
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
                "provider": "groq",
                "badge": "⚡ Blazing Fast & Reasoning",
                "description": "Massive 120B parameter open-weights model. Exceptional reasoning, coding, and writing at 300+ tokens/sec.",
                "supports_vision": False,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": True,
                "context_window": 131072,
                "max_output_tokens": 4096,
                "capabilities": ["Fast", "Reasoning", "Code"],
            },
            {
                "id": "openai/gpt-oss-20b",
                "name": "GPT-OSS 20B",
                "provider": "groq",
                "badge": "⚡ Ultra Fast (500+ tok/s)",
                "description": "Blazing fast 20B model for instant answers, summary, and code generation.",
                "supports_vision": False,
                "supports_reasoning": False,
                "supports_search": True,
                "is_fast": True,
                "context_window": 131072,
                "max_output_tokens": 4096,
                "capabilities": ["Fast", "General Chat"],
            },
            {
                "id": "qwen/qwen3.8-27b",
                "name": "Qwen 3.8 27B",
                "provider": "groq",
                "badge": "🧠 Deep STEM & Math",
                "description": "Advanced 27B text model optimized for multi-step reasoning, analytical math, and logic.",
                "supports_vision": False,
                "supports_reasoning": True,
                "supports_search": False,
                "is_fast": False,
                "context_window": 131072,
                "max_output_tokens": 4096,
                "capabilities": ["Reasoning", "Math & STEM"],
            },
            {
                "id": "allam-2-7b",
                "name": "ALLaM 2 7B",
                "provider": "groq",
                "badge": "🌐 Multilingual",
                "description": "High-efficiency multilingual instruction model.",
                "supports_vision": False,
                "supports_reasoning": False,
                "supports_search": False,
                "is_fast": True,
                "context_window": 8192,
                "max_output_tokens": 2048,
                "capabilities": ["Multilingual", "General Chat"],
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
                "provider": "openrouter",
                "badge": "⚡ Top Frontier Open",
                "description": "Meta's flagship open-weights instruction model with outstanding general intelligence.",
                "supports_vision": False,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": False,
                "context_window": 131072,
                "max_output_tokens": 4096,
                "capabilities": ["General", "Code", "Search"],
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "provider": "openrouter",
                "badge": "👑 Coding & Vision",
                "description": "Anthropic's frontier model for complex coding, deep analysis, and image understanding.",
                "supports_vision": True,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": False,
                "context_window": 200000,
                "max_output_tokens": 8192,
                "capabilities": ["Vision", "Reasoning", "Code"],
            },
            {
                "id": "deepseek/deepseek-r1",
                "name": "DeepSeek R1",
                "provider": "openrouter",
                "badge": "🧠 Reasoning Leader",
                "description": "Frontier open reasoning benchmark leader with chain-of-thought.",
                "supports_vision": False,
                "supports_reasoning": True,
                "supports_search": False,
                "is_fast": False,
                "context_window": 64000,
                "max_output_tokens": 8192,
                "capabilities": ["Deep Reasoning", "Math"],
            },
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o (OpenRouter)",
                "provider": "openrouter",
                "badge": "🧠 Omni Intelligence",
                "description": "OpenAI flagship multimodal intelligence with image analysis via OpenRouter.",
                "supports_vision": True,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": False,
                "context_window": 128000,
                "max_output_tokens": 4096,
                "capabilities": ["Vision", "Reasoning", "Multimodal"],
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
                "provider": "openai",
                "badge": "⚡ Fast & Intelligent",
                "description": "Affordable, fast, multimodal model for day-to-day coding, image analysis, and chat.",
                "supports_vision": True,
                "supports_reasoning": False,
                "supports_search": True,
                "is_fast": True,
                "context_window": 128000,
                "max_output_tokens": 4096,
                "capabilities": ["Vision", "Fast", "Code"],
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "openai",
                "badge": "🧠 Flagship Multimodal",
                "description": "OpenAI's flagship omni model for complex programming, analysis, and image input.",
                "supports_vision": True,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": False,
                "context_window": 128000,
                "max_output_tokens": 4096,
                "capabilities": ["Vision", "Reasoning", "Code"],
            },
            {
                "id": "o3-mini",
                "name": "o3-mini (Reasoning)",
                "provider": "openai",
                "badge": "🔬 STEM / Logic",
                "description": "Specialized reasoning text model with deep step-by-step thinking.",
                "supports_vision": False,
                "supports_reasoning": True,
                "supports_search": False,
                "is_fast": False,
                "context_window": 200000,
                "max_output_tokens": 8192,
                "capabilities": ["Reasoning", "STEM / Logic"],
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
        "default_model": "gemini-2.5-flash",
        "models": [
            {
                "id": "gemini-2.5-flash",
                "name": "Gemini 2.5 Flash",
                "provider": "gemini",
                "badge": "⚡ Blazing Fast Multimodal",
                "description": "Google's ultra-fast multimodal model with 1M token context, reasoning, and image analysis.",
                "supports_vision": True,
                "supports_reasoning": False,
                "supports_search": True,
                "is_fast": True,
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "capabilities": ["Vision", "Fast", "1M Context"],
            },
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro",
                "provider": "gemini",
                "badge": "🧠 Deep Analysis & Vision",
                "description": "2M token context window with advanced multimodal image understanding and reasoning.",
                "supports_vision": True,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": False,
                "context_window": 2097152,
                "max_output_tokens": 8192,
                "capabilities": ["Vision", "Reasoning", "2M Context"],
            },
            {
                "id": "gemini-3.8-flash",
                "name": "Gemini 3.8 Flash",
                "provider": "gemini",
                "badge": "⚡ Next-Gen Flash",
                "description": "Next-generation Gemini model built for low latency, image analysis, and high accuracy.",
                "supports_vision": True,
                "supports_reasoning": False,
                "supports_search": True,
                "is_fast": True,
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "capabilities": ["Vision", "Fast", "Multimodal"],
            },
            {
                "id": "gemini-flash-latest",
                "name": "Gemini Flash (Latest)",
                "provider": "gemini",
                "badge": "⚡ Stable Latest",
                "description": "Latest stable production release of Gemini Flash with image analysis.",
                "supports_vision": True,
                "supports_reasoning": False,
                "supports_search": True,
                "is_fast": True,
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "capabilities": ["Vision", "Fast"],
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


def get_model_metadata(provider: str, model: str) -> dict[str, Any]:
    """Retrieve verified capabilities and limits for a specific provider and model."""
    p_lower = (provider or "").lower().strip()
    m_lower = (model or "").lower().strip()
    pconfig = PROVIDERS.get(p_lower)
    if pconfig:
        for m in pconfig.get("models", []):
            if m["id"].lower() == m_lower or m["id"].lower().endswith(m_lower) or m_lower.endswith(m["id"].lower()):
                return dict(m)

    # Fallback heuristics for custom or Ollama models
    is_vision = any(sig in m_lower for sig in ("vision", "llava", "minicpm-v", "moondream", "qwen2-vl", "vl-"))
    is_reasoning = any(sig in m_lower for sig in ("r1", "reason", "o1", "o3", "deepseek-r", "think"))
    return {
        "id": model,
        "name": model,
        "provider": p_lower,
        "badge": "Custom",
        "description": "Provider model",
        "supports_vision": is_vision,
        "supports_reasoning": is_reasoning,
        "supports_search": True,
        "is_fast": not is_reasoning,
        "context_window": 131072 if p_lower != "ollama" else int(os.getenv("CONTEXT_TOKENS", "8192")),
        "max_output_tokens": 4096,
        "capabilities": (["Vision"] if is_vision else []) + (["Reasoning"] if is_reasoning else ["Fast"]),
    }


def get_vision_capable_models(healthy_providers: list[str] | None = None) -> list[dict]:
    """Return all configured models capable of image analysis."""
    result = []
    allowed_providers = [p.lower() for p in healthy_providers] if healthy_providers else [p for p in PROVIDERS if is_provider_configured(p)]
    for pid in allowed_providers:
        pcfg = PROVIDERS.get(pid)
        if not pcfg:
            continue
        for m in pcfg.get("models", []):
            if m.get("supports_vision"):
                result.append(dict(m))
    return result


def select_auto_model(
    has_images: bool,
    has_documents: bool,
    is_web_search: bool,
    content: str,
    healthy_providers: list[str] | None = None,
) -> tuple[str, str, str]:
    """
    Intelligently select the best model from configured, healthy providers.
    Returns: (provider_id, model_id, routing_explanation)

    Routing Rules:
    1. Image attachment -> Model that verified accepts image input (Gemini, GPT-4o, Claude 3.5 Sonnet).
    2. PDF/DOCX/CSV/Code attachment -> Large-context text model with structured extraction capability.
    3. Web search -> Model well-grounded for citation and source-based answering.
    4. Complex coding/math/reasoning -> Frontier reasoning model (DeepSeek R1, GPT-OSS 120B, o3-mini, Gemini Pro).
    5. General chat -> Fast, economical text model (GPT-OSS 20B/120B, Gemini Flash, GPT-4o Mini).
    """
    # 1. Determine available pool of providers
    if healthy_providers:
        configured = [p.lower() for p in healthy_providers if is_provider_configured(p)]
    else:
        configured = [p for p in PROVIDERS if is_provider_configured(p)]

    if not configured:
        # Fallback default
        return "groq", "openai/gpt-oss-120b", "Default fallback (Groq GPT-OSS 120B)"

    # Helper to check if a specific provider is available
    def has_p(name: str) -> bool:
        return name in configured

    # 1. Image Attachment Routing
    if has_images:
        if has_p("gemini"):
            return "gemini", "gemini-2.5-flash", "Auto: Gemini 2.5 Flash selected for high-speed multimodal image understanding."
        if has_p("openai"):
            return "openai", "gpt-4o-mini", "Auto: GPT-4o Mini selected for fast image analysis."
        if has_p("openrouter"):
            return "openrouter", "anthropic/claude-3.5-sonnet", "Auto: Claude 3.5 Sonnet selected for precision visual inspection."
        if has_p("ollama"):
            # Check if any vision model is present
            return "ollama", "llama3.2-vision", "Auto: Ollama Vision selected for local image analysis."
        # If no vision provider configured, raise or route to first available with an informative error
        raise ValueError("No vision-capable AI provider (Google Gemini or OpenAI) is configured on this server to analyze images.")

    # 2. PDF / DOCX / CSV / Code Document Routing
    if has_documents:
        if has_p("gemini"):
            return "gemini", "gemini-2.5-flash", "Auto: Gemini 2.5 Flash selected for large-context document comprehension (1M tokens)."
        if has_p("groq"):
            return "groq", "openai/gpt-oss-120b", "Auto: GPT-OSS 120B selected for high-speed document synthesis."
        if has_p("openai"):
            return "openai", "gpt-4o-mini", "Auto: GPT-4o Mini selected for structured document extraction."
        if has_p("openrouter"):
            return "openrouter", "meta-llama/llama-3.3-70b-instruct", "Auto: Llama 3.3 70B selected for document analysis."
        if has_p("ollama"):
            return "ollama", settings.OLLAMA_MODEL, "Auto: Local model selected for document analysis."

    # 3. Web Search Routing
    if is_web_search:
        if has_p("groq"):
            return "groq", "openai/gpt-oss-120b", "Auto: GPT-OSS 120B selected for fast citation-grounded web search answering."
        if has_p("gemini"):
            return "gemini", "gemini-2.5-flash", "Auto: Gemini 2.5 Flash selected for web search analysis."
        if has_p("openai"):
            return "openai", "gpt-4o-mini", "Auto: GPT-4o Mini selected for web search grounding."
        if has_p("openrouter"):
            return "openrouter", "meta-llama/llama-3.3-70b-instruct", "Auto: Llama 3.3 70B selected for web search grounding."
        if has_p("ollama"):
            return "ollama", settings.OLLAMA_MODEL, "Auto: Local model selected for web search."

    # 4. Complex Coding / Deep Reasoning Detection
    text_lower = (content or "").lower()
    reasoning_keywords = (
        "prove", "step by step", "algorithm", "derivation", "derive",
        "calculate", "theorem", "math", "complexity", "time complexity",
        "refactor", "debug", "traceback", "stack trace", "memory leak",
        "deadlock", "race condition", "regex", "sql query", "architecture"
    )
    has_code_block = "```" in content or "def " in content or "function " in content or "class " in content
    is_reasoning_prompt = has_code_block or any(kw in text_lower for kw in reasoning_keywords)

    if is_reasoning_prompt:
        if has_p("openrouter"):
            return "openrouter", "deepseek/deepseek-r1", "Auto: DeepSeek R1 selected for deep step-by-step reasoning."
        if has_p("groq"):
            return "groq", "openai/gpt-oss-120b", "Auto: GPT-OSS 120B selected for complex logic and coding."
        if has_p("openai"):
            return "openai", "o3-mini", "Auto: o3-mini selected for deep STEM and logic reasoning."
        if has_p("gemini"):
            return "gemini", "gemini-2.5-pro", "Auto: Gemini 2.5 Pro selected for deep analytical reasoning."
        if has_p("ollama"):
            return "ollama", settings.OLLAMA_MODEL, "Auto: Local model selected."

    # 5. General Chat -> Fast & Economical
    if has_p("groq"):
        return "groq", "openai/gpt-oss-20b", "Auto: GPT-OSS 20B selected for ultra-fast conversational response (500+ tok/s)."
    if has_p("gemini"):
        return "gemini", "gemini-2.5-flash", "Auto: Gemini 2.5 Flash selected for low latency and high accuracy."
    if has_p("openai"):
        return "openai", "gpt-4o-mini", "Auto: GPT-4o Mini selected for fast and responsive chat."
    if has_p("openrouter"):
        return "openrouter", "meta-llama/llama-3.3-70b-instruct", "Auto: Llama 3.3 70B selected for general chat."
    if has_p("ollama"):
        return "ollama", settings.OLLAMA_MODEL, "Auto: Local model selected."

    # Fallback to first configured
    first_p = configured[0]
    return first_p, PROVIDERS[first_p]["default_model"], f"Auto: {first_p} default selected."


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

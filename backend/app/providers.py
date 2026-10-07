import asyncio
from .ollama_catalog import model_detail
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
                "description": "A compact reasoning model for everyday answers, summaries, and coding.",
                "supports_vision": False,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": True,
                "context_window": 131072,
                "max_output_tokens": 4096,
                "capabilities": ["Fast", "General Chat", "Reasoning"],
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
        "default_model": "openai/gpt-4o-mini",
        "models": [
            {
                "id": "openai/gpt-4o-mini",
                "name": "GPT-4o Mini",
                "provider": "openrouter",
                "badge": "👁️ Vision & Fast",
                "description": "Fast multimodal intelligence with verified image understanding, coding, and chat.",
                "supports_vision": True,
                "supports_reasoning": False,
                "supports_search": True,
                "is_fast": True,
                "context_window": 128000,
                "max_output_tokens": 4096,
                "capabilities": ["Vision", "Fast", "Code"],
            },
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "provider": "openrouter",
                "badge": "🧠 Flagship Multimodal",
                "description": "OpenAI flagship omni model for complex visual analysis, logic, and coding.",
                "supports_vision": True,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": False,
                "context_window": 128000,
                "max_output_tokens": 4096,
                "capabilities": ["Vision", "Reasoning", "Multimodal"],
            },
            {
                "id": "deepseek/deepseek-r1",
                "name": "DeepSeek R1",
                "provider": "openrouter",
                "badge": "🧠 Reasoning Leader",
                "description": "Frontier open reasoning benchmark leader with deep step-by-step thinking.",
                "supports_vision": False,
                "supports_reasoning": True,
                "supports_search": False,
                "is_fast": False,
                "context_window": 64000,
                "max_output_tokens": 8192,
                "capabilities": ["Deep Reasoning", "Math"],
            },
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
                "id": "qwen/qwen-2.5-72b-instruct",
                "name": "Qwen 2.5 72B Instruct",
                "provider": "openrouter",
                "badge": "💻 Elite Coding",
                "description": "High-capability open model specialized in code generation, math, and technical tasks.",
                "supports_vision": False,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": False,
                "context_window": 131072,
                "max_output_tokens": 4096,
                "capabilities": ["Code", "Math", "Logic"],
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
        "default_model": "gemini-flash-lite-latest",
        "models": [
            {
                "id": "gemini-flash-lite-latest",
                "name": "Gemini Flash Lite",
                "provider": "gemini",
                "badge": "⚡ Fast Multimodal Vision",
                "description": "Google's ultra-fast, responsive multimodal model with image analysis and 1M context.",
                "supports_vision": True,
                "supports_reasoning": False,
                "supports_search": True,
                "is_fast": True,
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "capabilities": ["Vision", "Fast", "1M Context"],
            },
            {
                "id": "gemini-3.5-flash-lite",
                "name": "Gemini 3.5 Flash Lite",
                "provider": "gemini",
                "badge": "⚡ High Efficiency Vision",
                "description": "High-efficiency multimodal model optimized for fast responses and image understanding.",
                "supports_vision": True,
                "supports_reasoning": False,
                "supports_search": True,
                "is_fast": True,
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "capabilities": ["Vision", "Fast", "Multimodal"],
            },
            {
                "id": "gemini-3.6-flash",
                "name": "Gemini 3.6 Flash",
                "provider": "gemini",
                "badge": "🧠 Frontier Multimodal",
                "description": "Advanced Gemini Flash model with multimodal vision reasoning and long context.",
                "supports_vision": True,
                "supports_reasoning": True,
                "supports_search": True,
                "is_fast": True,
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "capabilities": ["Vision", "Multimodal", "Reasoning"],
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

# ---------------------------------------------------------------------------
# Ollama model description map
# More-specific patterns must come before generic ones.
# ---------------------------------------------------------------------------
def get_ollama_model_detail(model_name: str) -> dict:
    cached = _HEALTH_CACHE.get('ollama')
    if cached:
        for detail in cached[1].get('model_details', []):
            if detail['id'] == model_name:
                return dict(detail)
    return model_detail(model_name, None, local=False)


def get_provider_config(provider_name: str) -> dict:
    """Retrieve static configuration for a provider."""
    p_lower = (provider_name or "").lower().strip()
    return PROVIDERS.get(p_lower, PROVIDERS["groq"])


def get_model_metadata(provider: str, model: str) -> dict[str, Any]:
    """Retrieve verified capabilities and limits for a specific provider and model."""
    p_lower = (provider or "").lower().strip()
    m_lower = (model or "").lower().strip()
    cached = _HEALTH_CACHE.get(p_lower)
    if cached:
        for detail in cached[1].get('model_details', []):
            if detail.get('id', '').lower() == m_lower:
                return dict(detail)
    pconfig = PROVIDERS.get(p_lower)
    if pconfig:
        for m in pconfig.get("models", []):
            if m["id"].lower() == m_lower:
                return dict(m)

    if p_lower == "ollama":
        detail = get_ollama_model_detail(model)
        detail["context_window"] = detail.get("context_window") or int(os.getenv("CONTEXT_TOKENS", "8192"))
        detail["max_output_tokens"] = 4096
        return detail

    # Fallback for custom or unlisted models: neutral metadata, no guessed capabilities
    return {
        "id": model,
        "name": model,
        "provider": p_lower,
        "badge": "Custom",
        "description": "Configured provider model.",
        "supports_vision": False,
        "supports_reasoning": False,
        "supports_search": True,
        "is_fast": True,
        "context_window": 131072,
        "max_output_tokens": 4096,
        "capabilities": ["Custom"],
    }


def get_vision_capable_models(healthy_providers: list[str] | None = None) -> list[dict]:
    """Return all configured models capable of image analysis."""
    result = []
    allowed_providers = [p.lower() for p in healthy_providers] if healthy_providers else [p for p in PROVIDERS if is_provider_configured(p)]
    for pid in allowed_providers:
        pcfg = PROVIDERS.get(pid)
        if not pcfg:
            continue
        if pid == "ollama":
            cached = _HEALTH_CACHE.get("ollama")
            installed = cached[1].get("models", []) if cached else []
            for m in installed:
                det = get_ollama_model_detail(m)
                if det.get("supports_vision"):
                    result.append(det)
            continue
        for m in pcfg.get("models", []):
            if m.get("supports_vision"):
                result.append(dict(m))
    return result


def choose_auto_model(
    health: dict[str, dict[str, Any]], *, has_images: bool, has_documents: bool,
    is_web_search: bool, content: str,
) -> tuple[str, str, str]:
    """Choose only from models returned by healthy providers during this request.

    The shortlist comes from provider model-list APIs. Ollama capabilities come
    from /api/show; unknown Ollama capabilities are never assumed.
    """
    text = (content or "").lower()
    if has_images:
        task = "image understanding"
    elif has_documents:
        task = "document analysis"
    elif is_web_search:
        task = "web-supported answers"
    elif "```" in text or any(word in text for word in ("code", "program", "debug", "refactor", "traceback", "sql query")):
        task = "coding"
    elif any(word in text for word in ("prove", "derive", "theorem", "calculate", "math", "reason", "algorithm", "step by step")):
        task = "complex reasoning"
    else:
        task = "everyday chat"

    ranked: list[tuple[int, str, str, str]] = []
    for provider, state in health.items():
        if not state.get("working"):
            continue
        reported = set(state.get("models") or [])
        if provider == "ollama":
            details = state.get("model_details") or []
        else:
            details = state.get("model_details", PROVIDERS[provider].get("models", []))
        for model in details:
            mid = model.get("id")
            if not mid or mid not in reported:
                continue
            if model.get("chat_compatible") is False or (provider == "ollama" and not model.get("chat_compatible")):
                continue
            if model.get("supports_image_generation"):
                continue  # Text chat does not implement image output.
            if has_images and not model.get("supports_vision"):
                continue
            tags = {str(tag).lower() for tag in model.get("capabilities", [])}
            reasoning = bool(model.get("supports_reasoning"))
            fast = bool(model.get("is_fast"))
            coding = "code" in tags or model.get("specialty") == "code"
            if task == "complex reasoning" and not reasoning:
                continue
            if task == "coding" and not (coding or reasoning):
                continue
            context = int(model.get("context_window") or 0)
            score = 0
            if task == "image understanding":
                score = 100 + (10 if fast else 0) + (5 if reasoning else 0)
            elif task == "document analysis":
                score = 30 + min(context // 32768, 20) + (10 if reasoning else 0)
            elif task == "web-supported answers":
                score = 40 + (10 if fast else 0) + (5 if reasoning else 0)
            elif task == "coding":
                score = 30 + (30 if coding else 0) + (15 if reasoning else 0)
            elif task == "complex reasoning":
                score = 30 + (30 if reasoning else 0) + (10 if coding else 0)
            else:
                score = 30 + (25 if fast else 0) - (15 if reasoning else 0) - (5 if coding or model.get("supports_vision") else 0) + (5 if "general chat" in tags else 0)
            # Stable ordering keeps choices predictable when scores tie.
            ranked.append((score, provider, mid, model.get("name") or mid))
    if not ranked:
        need = "vision-capable model" if has_images else "chat-capable model"
        raise ValueError(f"No available {need} is ready. Refresh models or check your provider settings.")
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    _, provider, mid, name = ranked[0]
    return provider, mid, f"Auto chose {name} ({PROVIDERS[provider]['name']}) for {task}."


TASKS = {
    'chat': ('Everyday chat & writing', {}),
    'coding': ('Coding & debugging', {'content': 'Write code'}),
    'reasoning': ('Math & reasoning', {'content': 'Prove a theorem'}),
    'documents': ('Documents & summaries', {'has_documents': True}),
    'web': ('Web-supported answers', {'is_web_search': True}),
    'vision': ('Image understanding', {'has_images': True}),
}


def recommend_models(health, *, limit=3, **task):
    """Return a bounded shortlist from the same candidates Auto actually uses."""
    remaining = {p: dict(state, models=list(state.get('models', []))) for p, state in health.items()}
    options = []
    args = dict(has_images=False, has_documents=False, is_web_search=False, content='')
    args.update(task)
    for _ in range(limit):
        try:
            unused_providers = {p: state for p, state in remaining.items()
                                if p not in {option['provider'] for option in options}}
            try:
                provider, model, reason = choose_auto_model(unused_providers, **args)
            except ValueError:
                provider, model, reason = choose_auto_model(remaining, **args)
        except ValueError:
            break
        options.append({'provider': provider, 'model': model, 'reason': reason})
        remaining[provider]['models'].remove(model)
    return options


def image_options(health):
    options = []
    for provider in ('ollama', 'openrouter'):
        state = health.get(provider, {})
        if not state.get('working'):
            continue
        for detail in state.get('model_details', []):
            if detail['id'] in state.get('models', []) and detail.get('supports_image_generation'):
                options.append({'provider': provider, 'model': detail['id'],
                                'reason': f"Selected {detail.get('name', detail['id'])} for image generation."})
    return options


def feature_coverage(health):
    coverage = {}
    for key, (label, task) in TASKS.items():
        options = recommend_models(health, **task)
        count = len(options)
        coverage[key] = {
            'label': label, 'options': options,
            'status': 'ready' if count >= 2 else 'limited' if count else 'unavailable',
            'message': f'{count} currently listed options. Availability is checked again when you send.' if count >= 2
                       else 'Only one verified option is available; there is no verified backup.' if count
                       else 'No verified option is available from your connected providers.',
        }
    images = image_options(health)[:3]
    coverage['image_generation'] = {
        'label': 'Image generation', 'options': images,
        'status': 'ready' if len(images) >= 2 else 'limited' if images else 'unavailable',
        'message': f'{len(images)} image-generation options. Cloud usage may incur provider charges.' if images
                   else 'No image generator is connected. Use a compatible experimental Ollama server or configure OpenRouter image models.',
    }
    return coverage


def routing_health(healthy_providers):
    allowed = list(PROVIDERS) if healthy_providers is None else healthy_providers
    return {p: state for p, (stamp, state) in _HEALTH_CACHE.items()
            if p in allowed and is_provider_configured(p) and 0 <= time.time() - stamp < CACHE_TTL_SECONDS}


def select_auto_model(has_images, has_documents, is_web_search, content, healthy_providers=None):
    return choose_auto_model(routing_health(healthy_providers), has_images=has_images,
                             has_documents=has_documents, is_web_search=is_web_search, content=content)


def get_fallback_candidates(current_provider, current_model, has_images=False, healthy_providers=None,
                            has_documents=False, is_web_search=False, content=""):
    options = recommend_models(routing_health(healthy_providers), limit=3,
                               has_images=has_images, has_documents=has_documents,
                               is_web_search=is_web_search, content=content)
    return [(option['provider'], option['model'], option['reason']) for option in options
            if (option['provider'], option['model']) != (current_provider, current_model)][:2]


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
                    raw_models = response.json().get("models", [])
                    installed = [m.get("name") or m.get("model") for m in raw_models]
                    installed = [m for m in installed if isinstance(m, str) and m]
                    tag_details = {m.get("name") or m.get("model"): m for m in raw_models}
                    semaphore = asyncio.Semaphore(10)

                    async def describe(name: str) -> dict[str, Any]:
                        tagged = tag_details.get(name, {})
                        # Newer Ollama servers include verified capabilities in /api/tags.
                        # Use them immediately instead of making one request per model.
                        if isinstance(tagged.get("capabilities"), list):
                            return model_detail(name, tagged, local=base_url.startswith(("http://localhost", "http://127.0.0.1")))
                        async with semaphore:
                            try:
                                shown = await c.post(f"{base_url}/api/show", json={"model": name}, headers=headers)
                                shown.raise_for_status()
                                data = shown.json()
                            except (httpx.HTTPError, ValueError):
                                data = tagged
                            return model_detail(name, data, local=base_url.startswith(("http://localhost", "http://127.0.0.1")))

                    details = await asyncio.gather(*(describe(name) for name in installed))
                    has_chat = any(m.get("chat_compatible") or m.get("supports_image_generation") for m in details)
                    res = {
                        "id": "ollama",
                        "configured": True,
                        "working": has_chat,
                        "status": "ready" if has_chat else "no_chat_models",
                        "error": None if has_chat else "Ollama has no verified text-chat models available.",
                        "models": installed,
                        "model_details": details,
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
    else:
        probe_url = f"{config['base_url']}/models"

    curated_ids = [m["id"] for m in config.get("models", [])]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=3.0)) as c:
            response = await c.get(probe_url, headers=headers)
            status_code = response.status_code
            if status_code == 200:
                if p_lower == "openrouter":
                    try:
                        kdata = response.json().get("data", {})
                        limit_remaining = kdata.get("limit_remaining")
                        free_remaining = kdata.get("free_model_daily_requests", {}).get("remaining", 0)
                        if limit_remaining is not None and limit_remaining <= 0 and free_remaining <= 0:
                            res = {
                                "id": p_lower,
                                "configured": True,
                                "working": False,
                                "status": "quota_exceeded",
                                "error": "OpenRouter account balance and daily free credits are exhausted.",
                                "models": curated_ids,
                            }
                            _HEALTH_CACHE[p_lower] = (now_ts, res)
                            return res
                    except Exception:
                        pass
                if p_lower == "openrouter":
                    response = await c.get("https://openrouter.ai/api/v1/models", headers=headers)
                    response.raise_for_status()
                listed = {m.get('id'): m for m in response.json().get('data', []) if isinstance(m, dict)}
                reported = set(listed)
                available = [mid for mid in curated_ids if mid in reported]
                details = [dict(m) for m in config.get('models', []) if m['id'] in available]
                if p_lower == 'openrouter':
                    for detail in details:
                        live = listed[detail['id']]
                        architecture = live.get('architecture') or {}
                        inputs = architecture.get('input_modalities') or []
                        outputs = architecture.get('output_modalities') or []
                        detail['supports_vision'] = 'image' in inputs
                        detail['supports_image_generation'] = 'image' in outputs
                        detail['chat_compatible'] = 'text' in inputs and 'text' in outputs
                        detail['supports_reasoning'] = bool({'reasoning', 'include_reasoning'} & set(live.get('supported_parameters') or []))
                        detail['context_window'] = live.get('context_length') or detail.get('context_window', 0)
                        detail['capabilities'] = [tag for tag in detail.get('capabilities', []) if tag not in ('Vision', 'Reasoning', 'Deep Reasoning')]
                        if detail['supports_vision']:
                            detail['capabilities'].append('Vision')
                        if detail['supports_reasoning']:
                            detail['capabilities'].append('Reasoning')
                if p_lower == 'openrouter':
                    try:
                        image_list = await c.get('https://openrouter.ai/api/v1/images/models', headers=headers)
                        image_list.raise_for_status()
                        for image_model in image_list.json().get('data', []):
                            architecture = image_model.get('architecture') or {}
                            if 'image' not in architecture.get('output_modalities', []) or 'text' not in architecture.get('input_modalities', []):
                                continue
                            mid = image_model.get('id')
                            if not isinstance(mid, str) or not mid:
                                continue
                            image_detail = {'id': mid, 'name': image_model.get('name') or mid, 'provider': 'openrouter',
                                'description': 'Creates images from text prompts through OpenRouter.', 'badge': 'Image generation',
                                'chat_compatible': False, 'supports_image_generation': True,
                                'supports_vision': False, 'supports_reasoning': False, 'capabilities': ['Image generation']}
                            details = [d for d in details if d['id'] != mid] + [image_detail]
                            if mid not in available:
                                available.append(mid)
                    except (httpx.HTTPError, ValueError):
                        pass  # Image discovery failure must not disable working chat models.
                res = {
                    "id": p_lower,
                    "configured": True,
                    "working": bool(available),
                    "status": "ready" if available else "no_models",
                    "error": None if available else "No supported models are currently available.",
                    "models": available,
                    "model_details": details,
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

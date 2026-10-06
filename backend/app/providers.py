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
KNOWN_OLLAMA_MODEL_DESCRIPTIONS: list[dict] = [
    # Vision-capable models
    {
        "pattern": "llama3.2-vision",
        "name": "Llama 3.2 Vision",
        "badge": "👁️ Vision",
        "description": "Llama 3.2 with native image understanding — best for photo analysis and visual Q&A.",
        "supports_vision": True, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Vision", "Local"],
    },
    {
        "pattern": "llava",
        "name": "LLaVA",
        "badge": "👁️ Vision",
        "description": "Multimodal vision-language model for describing and reasoning about images.",
        "supports_vision": True, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Vision", "Local"],
    },
    {
        "pattern": "minicpm-v",
        "name": "MiniCPM-V",
        "badge": "👁️ Compact Vision",
        "description": "Compact multimodal model designed for efficient image and text understanding.",
        "supports_vision": True, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Vision", "Local"],
    },
    {
        "pattern": "moondream",
        "name": "Moondream",
        "badge": "👁️ Tiny Vision",
        "description": "Ultra-lightweight vision model for quick image captioning on limited hardware.",
        "supports_vision": True, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Vision", "Local"],
    },
    {
        "pattern": "qwen2-vl",
        "name": "Qwen2-VL",
        "badge": "👁️ Vision + Reasoning",
        "description": "Qwen2 vision-language model capable of image analysis and multilingual reasoning.",
        "supports_vision": True, "supports_reasoning": True, "is_fast": False,
        "capabilities": ["Vision", "Reasoning", "Local"],
    },
    {
        "pattern": "granite3-vision",
        "name": "Granite 3 Vision",
        "badge": "👁️ Vision",
        "description": "IBM Granite 3 model with image understanding for business documents.",
        "supports_vision": True, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Vision", "Local"],
    },
    {
        "pattern": "bakllava",
        "name": "BakLLaVA",
        "badge": "👁️ Vision",
        "description": "Mistral-based multimodal model for visual analysis and descriptive image QA.",
        "supports_vision": True, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Vision", "Local"],
    },
    # Reasoning / coding models
    {
        "pattern": "deepseek-r1",
        "name": "DeepSeek-R1",
        "badge": "🧠 Deep Reasoning",
        "description": "Step-by-step reasoning model — best for hard math, logic, and complex coding tasks.",
        "supports_vision": False, "supports_reasoning": True, "is_fast": False,
        "capabilities": ["Reasoning", "Code", "Local"],
    },
    {
        "pattern": "qwen2.5-coder",
        "name": "Qwen 2.5 Coder",
        "badge": "💻 Code",
        "description": "Specialized code-generation model strong at Python, JS, and system programming.",
        "supports_vision": False, "supports_reasoning": True, "is_fast": False,
        "capabilities": ["Code", "Local"],
    },
    {
        "pattern": "qwen2.5",
        "name": "Qwen 2.5",
        "badge": "🌐 Multilingual",
        "description": "Strong multilingual general model with solid instruction-following and reasoning.",
        "supports_vision": False, "supports_reasoning": True, "is_fast": False,
        "capabilities": ["Multilingual", "Reasoning", "Local"],
    },
    {
        "pattern": "qwen3",
        "name": "Qwen 3",
        "badge": "🧠 Reasoning",
        "description": "Latest Qwen generation with strong multilingual reasoning and coding capabilities.",
        "supports_vision": False, "supports_reasoning": True, "is_fast": False,
        "capabilities": ["Reasoning", "Code", "Local"],
    },
    {
        "pattern": "mistral-nemo",
        "name": "Mistral NeMo",
        "badge": "⚡ Efficient",
        "description": "Compact and fast Mistral model — good for everyday questions and document reading.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Fast", "Local"],
    },
    {
        "pattern": "mistral",
        "name": "Mistral",
        "badge": "⚡ Fast",
        "description": "Efficient Mistral model for everyday conversations and text tasks.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Fast", "Local"],
    },
    {
        "pattern": "codellama",
        "name": "Code Llama",
        "badge": "💻 Code",
        "description": "Meta's code-focused model for code generation, completion, and explanation.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Code", "Local"],
    },
    {
        "pattern": "phi4",
        "name": "Phi-4",
        "badge": "🧪 Compact Reasoning",
        "description": "Microsoft Phi-4: disproportionately strong reasoning for a small local model.",
        "supports_vision": False, "supports_reasoning": True, "is_fast": True,
        "capabilities": ["Reasoning", "Fast", "Local"],
    },
    {
        "pattern": "phi3",
        "name": "Phi-3",
        "badge": "🧪 Compact",
        "description": "Microsoft Phi-3: compact and capable on limited hardware.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Fast", "Local"],
    },
    {
        "pattern": "gemma3",
        "name": "Gemma 3",
        "badge": "✨ Everyday Chat",
        "description": "Google Gemma 3 — responsive and accurate for everyday chat and Q&A.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Fast", "Local"],
    },
    {
        "pattern": "gemma2",
        "name": "Gemma 2",
        "badge": "✨ Everyday Chat",
        "description": "Google Gemma 2 — balanced for chat, summarisation, and short documents.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Fast", "Local"],
    },
    {
        "pattern": "gemma",
        "name": "Gemma",
        "badge": "✨ Everyday Chat",
        "description": "Google Gemma model for general-purpose conversation and summarisation.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Fast", "Local"],
    },
    # Llama family — specific patterns before generic
    {
        "pattern": "llama3.3",
        "name": "Llama 3.3",
        "badge": "⚡ Strong General",
        "description": "Meta Llama 3.3 — excellent general-purpose model for chat, code, and reasoning.",
        "supports_vision": False, "supports_reasoning": True, "is_fast": False,
        "capabilities": ["Reasoning", "Local"],
    },
    {
        "pattern": "llama3.2",
        "name": "Llama 3.2",
        "badge": "⚡ Fast General",
        "description": "Compact Llama 3.2 — fast everyday chat and quick follow-up answers.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": True,
        "capabilities": ["Fast", "Local"],
    },
    {
        "pattern": "llama3.1",
        "name": "Llama 3.1",
        "badge": "🌐 General Chat",
        "description": "Meta Llama 3.1 instruction model for everyday tasks and conversations.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": False,
        "capabilities": ["General Chat", "Local"],
    },
    {
        "pattern": "llama3",
        "name": "Llama 3",
        "badge": "🌐 General",
        "description": "Meta Llama 3 instruction model for general conversation and writing.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": False,
        "capabilities": ["General Chat", "Local"],
    },
    {
        "pattern": "llama2",
        "name": "Llama 2",
        "badge": "🕰️ Older",
        "description": "Llama 2 — consider upgrading to Llama 3 for better performance.",
        "supports_vision": False, "supports_reasoning": False, "is_fast": False,
        "capabilities": ["Local"],
    },
]


def get_ollama_model_detail(model_name: str) -> dict:
    """
    Return enriched capability metadata for an installed Ollama model.
    Matches KNOWN_OLLAMA_MODEL_DESCRIPTIONS patterns (lowercase substring).
    Unknown models get a neutral description — no guessed capabilities.
    """
    base_name = (model_name or "").lower().split(":")[0]
    for entry in KNOWN_OLLAMA_MODEL_DESCRIPTIONS:
        if entry["pattern"] in base_name:
            tag = model_name.split(":", 1)[1] if ":" in model_name else ""
            display_name = entry["name"]
            if tag and tag != "latest":
                display_name = f"{entry['name']} ({tag})"
            return {
                "id": model_name,
                "name": display_name,
                "provider": "ollama",
                "badge": entry["badge"],
                "description": entry["description"],
                "supports_vision": entry["supports_vision"],
                "supports_reasoning": entry["supports_reasoning"],
                "supports_search": False,
                "is_fast": entry["is_fast"],
                "capabilities": entry["capabilities"],
            }

    # Unknown model — neutral metadata, no guessed capabilities
    return {
        "id": model_name,
        "name": model_name,
        "provider": "ollama",
        "badge": "🖥️ Local",
        "description": "General-purpose local model.",
        "supports_vision": False,
        "supports_reasoning": False,
        "supports_search": False,
        "is_fast": False,
        "capabilities": ["Local"],
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

    if p_lower == "ollama":
        detail = get_ollama_model_detail(model)
        detail["context_window"] = int(os.getenv("CONTEXT_TOKENS", "8192"))
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
    1. Image attachment -> verified vision-capable model only (never text-only).
    2. PDF/DOCX/CSV/Code attachment -> large-context text model.
    3. Web search -> citation-grounded model.
    4. Complex coding/math/reasoning -> frontier reasoning model.
    5. General chat -> fast, economical text model.
    """
    # Determine available pool of providers
    if healthy_providers is not None:
        configured = [p.lower() for p in healthy_providers if is_provider_configured(p)]
    else:
        configured = [p for p in PROVIDERS if is_provider_configured(p)]

    if not configured:
        if has_images:
            raise ValueError(
                "No vision-capable AI provider is configured on this server to analyze images. "
                "Configure Gemini (GEMINI_API_KEY), OpenAI (OPENAI_API_KEY), or Ollama with a vision model."
            )
        return "groq", "openai/gpt-oss-120b", "Default fallback (Groq GPT-OSS 120B)"

    def has_p(name: str) -> bool:
        return name in configured

    # --- Ollama helpers: read from health cache, no extra network call ---
    def installed_ollama_models() -> list[str]:
        if "ollama" in _HEALTH_CACHE:
            _, data = _HEALTH_CACHE["ollama"]
            return list(data.get("models", []))
        if settings.OLLAMA_MODEL:
            return [settings.OLLAMA_MODEL]
        return []

    def ollama_model_with(predicate) -> str | None:
        """First installed Ollama model satisfying predicate(detail_dict)."""
        for m in installed_ollama_models():
            if predicate(get_ollama_model_detail(m)):
                return m
        return None

    def ollama_best_text(prefer_reasoning: bool = False) -> str | None:
        """Best available Ollama text model (prefers reasoning-capable if requested)."""
        installed = installed_ollama_models()
        if not installed:
            return None
        if prefer_reasoning:
            for m in installed:
                if get_ollama_model_detail(m).get("supports_reasoning"):
                    return m
        return installed[0]

    # Helper to check if a specific provider is available
    def has_p(name: str) -> bool:
        return name in configured

    # 1. Image Attachment Routing — only verified vision-capable models
    if has_images:
        if has_p("openrouter"):
            return "openrouter", "openai/gpt-4o-mini", "Auto: GPT-4o Mini (OpenRouter) selected for fast, verified multimodal image analysis."
        if has_p("gemini"):
            return "gemini", "gemini-flash-lite-latest", "Auto: Gemini Flash Lite selected for high-speed multimodal image understanding."
        if has_p("ollama"):
            vis_model = ollama_model_with(lambda d: d.get("supports_vision"))
            if vis_model:
                return "ollama", vis_model, f"Auto: {vis_model} selected for local image analysis."
            raise ValueError(
                "No vision-capable Ollama model is installed. "
                "Install a vision model (e.g. `ollama pull llama3.2-vision` or `ollama pull llava`), or configure OpenRouter or Gemini."
            )
        raise ValueError("No vision-capable AI provider is configured on this server to analyze images.")

    # 2. PDF / DOCX / CSV / Code Document Routing
    if has_documents:
        if has_p("groq"):
            return "groq", "openai/gpt-oss-120b", "Auto: GPT-OSS 120B (Groq) selected for high-speed document synthesis."
        if has_p("openrouter"):
            return "openrouter", "meta-llama/llama-3.3-70b-instruct", "Auto: Llama 3.3 70B (OpenRouter) selected for comprehensive document analysis."
        if has_p("gemini"):
            return "gemini", "gemini-flash-lite-latest", "Auto: Gemini Flash Lite selected for large-context document comprehension (1M tokens)."
        if has_p("ollama"):
            m = ollama_best_text()
            if m:
                return "ollama", m, f"Auto: {m} selected for local document analysis."

    # 3. Web Search Routing
    if is_web_search:
        if has_p("groq"):
            return "groq", "openai/gpt-oss-120b", "Auto: GPT-OSS 120B (Groq) selected for fast citation-grounded web search answering."
        if has_p("openrouter"):
            return "openrouter", "meta-llama/llama-3.3-70b-instruct", "Auto: Llama 3.3 70B (OpenRouter) selected for web search grounding."
        if has_p("gemini"):
            return "gemini", "gemini-flash-lite-latest", "Auto: Gemini Flash Lite selected for web search analysis."
        if has_p("ollama"):
            m = ollama_best_text()
            if m:
                return "ollama", m, f"Auto: {m} selected for local web search."

    # 4. Complex Coding / Software Engineering
    text_lower = (content or "").lower()
    has_code_block = "```" in content or "def " in content or "function " in content or "class " in content
    is_coding_prompt = has_code_block or any(kw in text_lower for kw in ("python", "javascript", "typescript", "code", "bug", "refactor", "function", "class", "async", "api", "sql", "regex", "git", "docker"))

    if is_coding_prompt:
        if has_p("groq"):
            return "groq", "openai/gpt-oss-120b", "Auto: GPT-OSS 120B (Groq) selected for high-speed coding and debugging."
        if has_p("openrouter"):
            return "openrouter", "qwen/qwen-2.5-72b-instruct", "Auto: Qwen 2.5 72B (OpenRouter) selected for elite code generation and logic."
        if has_p("openrouter"):
            return "openrouter", "meta-llama/llama-3.3-70b-instruct", "Auto: Llama 3.3 70B (OpenRouter) selected for software architecture and code."
        if has_p("ollama"):
            m = ollama_best_text()
            if m:
                return "ollama", m, f"Auto: {m} selected for local code generation."

    # 5. Deep STEM / Math / Logic Reasoning
    reasoning_keywords = (
        "prove", "step by step", "algorithm", "derivation", "derive",
        "calculate", "theorem", "math", "complexity", "time complexity",
        "refactor", "debug", "traceback", "stack trace", "memory leak",
        "deadlock", "race condition", "regex", "sql query", "architecture"
    )
    is_reasoning_prompt = has_code_block or any(kw in text_lower for kw in reasoning_keywords)

    if is_reasoning_prompt:
        if has_p("openrouter"):
            return "openrouter", "deepseek/deepseek-r1", "Auto: DeepSeek R1 (OpenRouter) selected for deep step-by-step reasoning."
        if has_p("groq"):
            return "groq", "qwen/qwen3.8-27b", "Auto: Qwen 3.8 27B (Groq) selected for analytical math and logic reasoning."
        if has_p("groq"):
            return "groq", "openai/gpt-oss-120b", "Auto: GPT-OSS 120B (Groq) selected for complex logic and reasoning."
        if has_p("gemini"):
            return "gemini", "gemini-3.6-flash", "Auto: Gemini 3.6 Flash selected for analytical reasoning."
        if has_p("ollama"):
            m = ollama_best_text(prefer_reasoning=True)
            if m:
                det = get_ollama_model_detail(m)
                reason = f"Auto: {m} selected for local reasoning and coding." if det.get("supports_reasoning") else f"Auto: {m} selected for local execution."
                return "ollama", m, reason

    # 6. General Chat -> Fast & Economical
    if has_p("groq"):
        return "groq", "openai/gpt-oss-20b", "Auto: GPT-OSS 20B (Groq) selected for ultra-fast conversational response (500+ tok/s)."
    if has_p("gemini"):
        return "gemini", "gemini-flash-lite-latest", "Auto: Gemini Flash Lite selected for low latency and high accuracy."
    if has_p("openrouter"):
        return "openrouter", "openai/gpt-4o-mini", "Auto: GPT-4o Mini (OpenRouter) selected for fast, intelligent conversation."
    if has_p("ollama"):
        m = ollama_best_text()
        if m:
            return "ollama", m, f"Auto: {m} selected for local chat."

    # Fallback to first configured
    first_p = configured[0]
    if first_p == "ollama":
        m = ollama_best_text()
        if not m:
            raise ValueError("No Ollama models are installed or reachable. Run `ollama pull <model>` or configure a cloud provider.")
        return "ollama", m, f"Auto: {m} selected."
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
                        "models": installed,
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

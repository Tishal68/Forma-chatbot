import json
import os
from typing import AsyncGenerator
import httpx

# Pre-configured providers and their top models
PROVIDERS = {
    "groq": {
        "name": "Groq (Lightning Fast)",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "key_url": "https://console.groq.com/keys",
        "default_model": "openai/gpt-oss-120b",
        "models": [
            {
                "id": "openai/gpt-oss-120b",
                "name": "GPT-OSS 120B",
                "badge": "⚡ Top Intelligence & Speed",
                "description": "Massive 120B parameter model. Exceptional reasoning, coding, and writing at 300+ tokens/sec.",
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
                "badge": "🧠 Deep Reasoning & Math",
                "description": "Alibaba's advanced 27B model for multi-step reasoning and analysis.",
            },
        ],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
        "default_model": "gpt-4o-mini",
        "models": [
            {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "badge": "⚡ Fast & Highly Intelligent",
                "description": "Affordable, fast, and smarter than GPT-3.5 across all benchmarks.",
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o (Omni)",
                "badge": "🧠 Frontier Intelligence",
                "description": "OpenAI's flagship multimodal model for complex programming and analysis.",
            },
            {
                "id": "o3-mini",
                "name": "o3-mini (Reasoning)",
                "badge": "🔬 Advanced STEM / Logic",
                "description": "Specialized reasoning model with step-by-step thinking.",
            },
        ],
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GEMINI_API_KEY",
        "key_url": "https://aistudio.google.com/app/apikey",
        "default_model": "gemini-2.0-flash",
        "models": [
            {
                "id": "gemini-2.0-flash",
                "name": "Gemini 2.0 Flash",
                "badge": "⚡ Next-Gen Speed",
                "description": "Google's newest multimodal model built for blazing speed and high accuracy.",
            },
            {
                "id": "gemini-1.5-flash",
                "name": "Gemini 1.5 Flash",
                "badge": "⚡ Fast & Efficient",
                "description": "Lightweight model optimized for low latency and high volume.",
            },
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "badge": "🧠 Deep Analysis",
                "description": "Massive context window with advanced reasoning capabilities.",
            },
        ],
    },
    "openrouter": {
        "name": "OpenRouter (All Models)",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "key_url": "https://openrouter.ai/keys",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "models": [
            {
                "id": "meta-llama/llama-3.3-70b-instruct",
                "name": "Llama 3.3 70B Instruct",
                "badge": "⚡ Top Open Weights",
                "description": "High performance instruction-tuned model.",
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "badge": "👑 Coding & Reasoning King",
                "description": "Anthropic's gold-standard model for code architecture and reasoning.",
            },
            {
                "id": "deepseek/deepseek-r1",
                "name": "DeepSeek R1",
                "badge": "🧠 Chain-of-Thought Reasoning",
                "description": "Open reasoning benchmark leader.",
            },
            {
                "id": "google/gemini-2.0-flash-exp:free",
                "name": "Gemini 2.0 Flash (Free)",
                "badge": "🆓 Free Tier",
                "description": "Community accessible free-tier model on OpenRouter.",
            },
        ],
    },
    "ollama": {
        "name": "Ollama (Local Offline)",
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        "api_key_env": "OLLAMA_API_KEY",
        "key_url": "https://ollama.com",
        "default_model": os.getenv("OLLAMA_MODEL", "llama3.2"),
        "models": [],
    },
}


def get_provider_config(provider_name: str) -> dict:
    return PROVIDERS.get(provider_name.lower(), PROVIDERS["ollama"])


def get_api_key(provider_name: str, client_key: str | None = None) -> str | None:
    if client_key and client_key.strip():
        return client_key.strip()
    config = get_provider_config(provider_name)
    env_var = config.get("api_key_env")
    if env_var:
        return os.getenv(env_var) or None
    return None

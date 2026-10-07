"""Backend-owned display metadata for models reported by the configured Ollama server.

Capabilities come from Ollama's /api/show response, never from model-name guesses.
The small specialty map is editorial copy, not a capability or benchmark claim.
"""

from __future__ import annotations

from typing import Any


SPECIALTIES = {
    "llama3.2": "A compact choice for everyday questions and writing.",
    "deepseek-r1": "Designed for multi-step reasoning and math-heavy questions.",
    "gpt-oss:20b": "The smaller GPT-OSS option for quicker everyday answers.",
    "gpt-oss:120b": "The larger GPT-OSS option for more demanding reasoning and coding.",
    "gpt-oss": "A general assistant with reasoning support when the model advertises it.",
    "qwen2.5-coder": "Focused on writing and explaining code.",
    "qwen3-coder": "Focused on programming and code review.",
    "codellama": "Focused on code generation and explanation.",
    "llama3.2-vision": "Useful for describing and answering questions about images.",
    "llava": "Useful for understanding images and visual questions.",

}


def model_detail(name: str, shown: dict[str, Any] | None, *, local: bool) -> dict[str, Any]:
    shown = shown or {}
    raw = shown.get("capabilities")
    verified = {str(cap).lower() for cap in raw} if isinstance(raw, list) else set()
    family = name.lower().split(":", 1)[0]
    specialty = SPECIALTIES.get(name.lower().removesuffix(":cloud")) or SPECIALTIES.get(family)
    # A model that cannot chat should still be visible, but never offered to chat routing.
    chat_compatible = "completion" in verified
    image_generation = bool(verified & {"image", "image-generation", "image_generation", "text-to-image"})
    if image_generation:
        description = "Creates images from prompts on an Ollama server with experimental image generation enabled."
    elif specialty:
        description = specialty
    elif "vision" in verified:
        description = "A general assistant that can also understand attached images."
    elif "thinking" in verified:
        description = "A general assistant with a verified thinking mode."
    elif chat_compatible:
        description = "A general text model; no specific specialty has been verified."
    else:
        description = "Capabilities could not be verified for chat."
    labels = []
    if "vision" in verified:
        labels.append("Vision")
    if "thinking" in verified:
        labels.append("Reasoning")
    if "tools" in verified:
        labels.append("Tools")
    if image_generation:
        labels.append("Image generation")
    labels.append("Local" if local else "Ollama Cloud")
    model_info = shown.get("model_info") or {}
    context_values = [value for key, value in model_info.items() if key.endswith(".context_length") and isinstance(value, int)]
    tag_context = (shown.get("details") or {}).get("context_length")
    if isinstance(tag_context, int):
        context_values.append(tag_context)
    return {
        "id": name,
        "name": name,
        "provider": "ollama",
        "badge": "Local" if local else "Cloud",
        "description": description,
        "supports_vision": "vision" in verified and chat_compatible,
        "supports_reasoning": "thinking" in verified and chat_compatible,
        "supports_image_generation": image_generation,
        "chat_compatible": chat_compatible,
        "is_fast": False,
        "context_window": max(context_values, default=0),
        "capabilities": labels,
        "specialty": "code" if family in {"qwen2.5-coder", "qwen3-coder", "codellama"} else "general",
    }

"""LLM providers for the converter.

anthropic  -> native SDK (tool use, can also search the web itself) - see converter.py
ollama     -> native /api/chat with JSON-schema constrained output (local, free)
everything else -> OpenAI-compatible /chat/completions:
   openai, gemini, openrouter, groq, mistral, deepseek, lmstudio, vllm, localai, azure-compatible
   proxies, LiteLLM, … - set TUNIMIX_PROVIDER=custom and TUNIMIX_BASE_URL for anything else.
"""
from __future__ import annotations

import base64
import io
import os

import requests

PROVIDERS = {
    "anthropic":  {"base": "https://api.anthropic.com/v1", "key_env": "ANTHROPIC_API_KEY"},
    "openai":     {"base": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY"},
    "gemini":     {"base": "https://generativelanguage.googleapis.com/v1beta/openai", "key_env": "GEMINI_API_KEY"},
    "openrouter": {"base": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY"},
    "groq":       {"base": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY"},
    "mistral":    {"base": "https://api.mistral.ai/v1", "key_env": "MISTRAL_API_KEY"},
    "deepseek":   {"base": "https://api.deepseek.com/v1", "key_env": "DEEPSEEK_API_KEY"},
    "ollama":     {"base": "http://localhost:11434", "key_env": "", "local": True},
    "lmstudio":   {"base": "http://localhost:1234/v1", "key_env": "", "local": True},
    "custom":     {"base": "", "key_env": ""},
}


class ProviderError(RuntimeError):
    pass


def resolve(provider: str, base_url: str = "", api_key: str = "") -> tuple[str, str]:
    if provider not in PROVIDERS:
        raise ProviderError(f"Unknown provider '{provider}'. Choose one of: {', '.join(PROVIDERS)}")
    info = PROVIDERS[provider]
    base = (base_url or info["base"]).rstrip("/")
    if not base:
        raise ProviderError("TUNIMIX_BASE_URL is required for provider 'custom'.")
    key = api_key or (os.getenv(info["key_env"], "") if info["key_env"] else "")
    if info["key_env"] and not key:
        raise ProviderError(f"No API key: set TUNIMIX_API_KEY or {info['key_env']}.")
    return base, key


def pdf_block_to_text(block: dict) -> str:
    from pypdf import PdfReader
    data = base64.b64decode(block["source"]["data"])
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((p.extract_text() or "") for p in reader.pages[:15])
    if len(text.strip()) < 50:
        raise ProviderError("The PDF has no text layer (scan). Use a photo of it, or the anthropic provider.")
    return text


def split_media(media: list[dict]) -> tuple[list[dict], str]:
    """Claude-style content blocks -> (image blocks, extra text from PDFs)."""
    images, extra = [], ""
    for b in media:
        if b.get("type") == "image":
            images.append(b)
        elif b.get("type") == "document":
            extra += "\nRECIPE FROM PDF:\n" + pdf_block_to_text(b)[:40000] + "\n"
    return images, extra


def chat_openai(base: str, key: str, model: str, messages: list[dict], provider: str,
                json_mode: bool = True, timeout: int = 300) -> str:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if provider == "openrouter":
        headers.update({"HTTP-Referer": "https://github.com/Aminost/tunimix", "X-Title": "TuniMix"})
    body = {"model": model, "messages": messages, "temperature": 0.3}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(f"{base}/chat/completions", headers=headers, json=body, timeout=timeout)
    if r.status_code == 400 and json_mode:  # provider/model without JSON mode
        return chat_openai(base, key, model, messages, provider, json_mode=False, timeout=timeout)
    if not r.ok:
        raise ProviderError(f"{provider} {r.status_code}: {r.text[:400]}")
    return r.json()["choices"][0]["message"]["content"] or ""


def chat_ollama(base: str, model: str, messages: list[dict], schema: dict, timeout: int = 600) -> str:
    body = {"model": model, "messages": messages, "stream": False, "format": schema,
            "options": {"temperature": 0.3, "num_ctx": 16384}}
    try:
        r = requests.post(f"{base}/api/chat", json=body, timeout=timeout)
    except requests.ConnectionError as exc:
        raise ProviderError(f"Ollama not reachable at {base}. Is `ollama serve` running?") from exc
    if not r.ok:
        raise ProviderError(f"ollama {r.status_code}: {r.text[:400]}")
    return r.json()["message"]["content"] or ""


def to_openai_user(text: str, images: list[dict]):
    if not images:
        return text
    parts = [{"type": "text", "text": text}]
    for b in images:
        src = b["source"]
        parts.append({"type": "image_url", "image_url": {"url": f"data:{src['media_type']};base64,{src['data']}"}})
    return parts


def to_ollama_user(text: str, images: list[dict]) -> dict:
    msg = {"role": "user", "content": text}
    if images:
        msg["images"] = [b["source"]["data"] for b in images]
    return msg


def list_models(provider: str, base_url: str = "", api_key: str = "") -> list[str]:
    base, key = resolve(provider, base_url, api_key)
    if provider == "ollama":
        r = requests.get(f"{base}/api/tags", timeout=20)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    if provider == "anthropic":
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    r = requests.get(f"{base}/models", headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    return sorted(m.get("id") or m.get("name") for m in data.get("data", data.get("models", [])))

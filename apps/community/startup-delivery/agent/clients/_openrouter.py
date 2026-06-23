"""OpenRouter client — OpenAI-compatible chat/completions gateway.

Docs: https://openrouter.ai/docs
All LLM calls in this project go through OpenRouter (not direct Anthropic/OpenAI keys).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = "https://openrouter.ai/api/v1"


def _client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set in .env")
    timeout = float(os.environ.get("OPENROUTER_TIMEOUT", "30"))
    max_retries = int(os.environ.get("OPENROUTER_MAX_RETRIES", "1"))
    return OpenAI(base_url=BASE_URL, api_key=api_key, timeout=timeout, max_retries=max_retries)


def default_model() -> str:
    return os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")


def default_embed_model() -> str:
    return os.environ.get("OPENROUTER_EMBED_MODEL", "openai/text-embedding-3-small")


def embed(texts: list[str]) -> list[list[float]] | None:
    """Best-effort embeddings via the same OpenAI-compatible client.

    Returns one vector per input text, or None on ANY failure (missing key,
    network error, provider that doesn't expose /embeddings, malformed
    response). It NEVER raises, so callers can treat a None as "no embeddings
    available" and fall back. Purely additive — the chat helpers above are
    untouched. Model comes from OPENROUTER_EMBED_MODEL.
    """
    if not texts:
        return None
    try:
        response = _client().embeddings.create(
            model=default_embed_model(),
            input=texts,
            extra_headers=_extra_headers() or None,
        )
        vectors = [list(item.embedding) for item in response.data]
        if len(vectors) != len(texts) or any(not v for v in vectors):
            return None
        return vectors
    except Exception:
        return None


def _extra_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if site := os.environ.get("OPENROUTER_SITE_URL"):
        headers["HTTP-Referer"] = site
    if name := os.environ.get("OPENROUTER_APP_NAME"):
        headers["X-Title"] = name
    return headers


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.7,
) -> str:
    """Single chat completion; returns assistant message text."""
    kwargs: dict[str, Any] = {
        "model": model or default_model(),
        "messages": messages,
        "temperature": temperature,
        "extra_headers": _extra_headers() or None,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = _client().chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenRouter returned empty content")
    return content


def _strip_code_fences(text: str) -> str:
    """Drop a leading ```/```json fence and a trailing ``` if present.

    Several models (e.g. Anthropic via OpenRouter) wrap JSON in a markdown code
    block even with response_format=json_object, which breaks a naive json.loads.
    """
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def chat_json(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
) -> Any:
    """Chat completion with JSON response; parses and returns the decoded value.

    Tolerates fenced output and a stray prose preamble/suffix by falling back to
    the first balanced JSON object/array in the text.
    """
    raw = chat(messages, model=model, json_mode=True, temperature=temperature)
    cleaned = _strip_code_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def chat_with_tools(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.4,
    tool_choice: Any = "auto",
) -> Any:
    """One tool-calling chat round-trip for a multi-step agent loop.

    Returns the raw assistant message (an OpenAI ChatCompletionMessage) so the
    caller can inspect `.tool_calls` and `.content` and drive the loop itself.
    The standard OpenAI tool-calling schema is passed straight through to
    OpenRouter (which proxies it to the underlying provider unchanged).

    This is purely additive — `chat`/`chat_json` are untouched, so the existing
    deterministic pipeline keeps working exactly as before.
    """
    kwargs: dict[str, Any] = {
        "model": model or default_model(),
        "messages": messages,
        "temperature": temperature,
        "tools": tools,
        "extra_headers": _extra_headers() or None,
    }
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    response = _client().chat.completions.create(**kwargs)
    return response.choices[0].message

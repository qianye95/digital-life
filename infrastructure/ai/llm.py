"""Auxiliary LLM helper for memory consolidation and lightweight workflows."""

from __future__ import annotations

from typing import Any

import httpx

from infrastructure.ai.config import load_runtime_config, resolve_runtime_provider


def call_llm(
    prompt: str,
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = 120,
    **_: Any,
) -> str:
    config = load_runtime_config()
    runtime = resolve_runtime_provider(provider, config=config)
    model_name = model or runtime.get("model") or ""
    resolved_base_url = (base_url or runtime.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    resolved_api_key = api_key or runtime.get("api_key") or ""
    if not model_name:
        return ""

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    url = resolved_base_url if resolved_base_url.endswith("/chat/completions") else f"{resolved_base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if resolved_api_key:
        headers["Authorization"] = f"Bearer {resolved_api_key}"
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json={"model": model_name, "messages": messages})
        response.raise_for_status()
        data = response.json()
    return str(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")

"""Thin Anthropic Messages API client — stdlib only.

Returns parsed JSON content. The caller supplies a system prompt + a list of
{"role": "user"|"assistant", "content": str} turns.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    stop_reason: str


class AnthropicClient:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-sonnet-4-6",
        base_url: str = "https://api.anthropic.com",
        opener: Any = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key required")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._opener = opener or urllib.request.build_opener()

    def messages(
        self,
        *,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.4,
    ) -> LLMResult:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "temperature": temperature,
        }
        req = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "accept": "application/json",
            },
        )
        try:
            with self._opener.open(req, timeout=60) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise LLMError(f"HTTP {e.code}: {detail}") from e
        payload = json.loads(raw)
        parts = payload.get("content", [])
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        usage = payload.get("usage", {})
        return LLMResult(
            text=text,
            tokens_in=int(usage.get("input_tokens", 0)),
            tokens_out=int(usage.get("output_tokens", 0)),
            stop_reason=payload.get("stop_reason", ""),
        )

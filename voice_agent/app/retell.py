"""Retell AI client — create outbound call with dynamic LLM variables.

Docs: https://docs.retellai.com/api-references/create-phone-call
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class RetellError(RuntimeError):
    pass


@dataclass
class RetellCall:
    call_id: str
    agent_id: str
    status: str


class RetellClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.retellai.com",
        opener: Any = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._opener = opener or urllib.request.build_opener()

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(req, timeout=30) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise RetellError(f"HTTP {e.code} {path}: {detail}") from e
        return json.loads(raw) if raw else {}

    def create_phone_call(
        self,
        *,
        from_number: str,
        to_number: str,
        agent_id: str,
        dynamic_variables: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RetellCall:
        body = {
            "from_number": from_number,
            "to_number": to_number,
            "override_agent_id": agent_id,
            "retell_llm_dynamic_variables": dynamic_variables or {},
            "metadata": metadata or {},
        }
        payload = self._post("/v2/create-phone-call", body)
        call_id = payload.get("call_id") or payload.get("id")
        if not call_id:
            raise RetellError(f"no call_id in response: {payload}")
        return RetellCall(
            call_id=call_id,
            agent_id=payload.get("agent_id", agent_id),
            status=payload.get("call_status", "queued"),
        )

"""Pre-dial compliance check via the compliance_gate service."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ComplianceDecision:
    allowed: bool
    reason: str | None
    details: dict | None


class ComplianceError(RuntimeError):
    pass


class ComplianceClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        opener: Any = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("COMPLIANCE_URL", "http://compliance_gate:8000")).rstrip("/")
        self.token = token or os.environ.get("COMPLIANCE_API_TOKEN", "")
        self._opener = opener or urllib.request.build_opener()

    def check_call(self, lead_id: str, *, ai_disclosure_planned: bool = True,
                   recording_notice_planned: bool = True) -> ComplianceDecision:
        body = {
            "lead_id": lead_id,
            "ai_disclosure_planned": ai_disclosure_planned,
            "recording_notice_planned": recording_notice_planned,
        }
        req = urllib.request.Request(
            f"{self.base_url}/compliance/check-call",
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise ComplianceError(f"HTTP {e.code}: {detail}") from e
        return ComplianceDecision(
            allowed=bool(payload["allowed"]),
            reason=payload.get("reason"),
            details=payload.get("details"),
        )

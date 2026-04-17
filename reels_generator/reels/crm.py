"""Tiny HTTP client to the CRM core — keeps content_assets in sync as we post."""

from __future__ import annotations

import json
import urllib.request
from typing import Any


class CRMClient:
    def __init__(self, base_url: str, token: str, opener: Any = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._opener = opener or urllib.request.build_opener()

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with self._opener.open(req, timeout=30) as resp:
            raw = resp.read().decode()
        return json.loads(raw) if raw else {}

    def record_posted_reel(
        self,
        *,
        hook_text: str,
        hook_framework: str | None,
        cta_keyword: str | None,
        r2_video_url: str,
        ig_media_id: str | None,
        permalink: str | None,
    ) -> dict:
        """POST /api/admin/content — creates a content_assets row."""
        return self._post("/api/admin/content", {
            "hook_text": hook_text,
            "hook_framework": hook_framework,
            "cta_keyword": cta_keyword,
            "r2_video_url": r2_video_url,
            "ig_media_id": ig_media_id,
            "permalink": permalink,
        })

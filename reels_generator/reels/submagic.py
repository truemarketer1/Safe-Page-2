"""Submagic API client — captions, emojis, dynamic zooms, B-roll.

Submagic's API accepts a video URL, returns a job id, and exposes a status
endpoint. Polling pattern matches HeyGen's.

Docs: https://www.submagic.co/api (current as of 2026).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class SubmagicError(RuntimeError):
    pass


@dataclass
class SubmagicJob:
    job_id: str
    status: str = "pending"
    video_url: str | None = None
    error: str | None = None


class SubmagicClient:
    """Thin wrapper. Stdlib only — same pattern as the HeyGen client."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.submagic.co/v1",
        opener: Any = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._opener = opener or urllib.request.build_opener()

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if data:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self._opener.open(req, timeout=60) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise SubmagicError(f"HTTP {e.code} {path}: {detail}") from e
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise SubmagicError(f"non-JSON: {raw[:300]}") from e

    def submit(
        self,
        video_url: str,
        *,
        template: str = "reels_v1",
        language: str = "en",
        emoji: bool = True,
    ) -> str:
        """Kick off captioning. Returns a Submagic job id."""
        response = self._request("POST", "/videos", {
            "video_url": video_url,
            "template": template,
            "language": language,
            "options": {"emoji": emoji, "zoom": True, "broll": True},
        })
        data = response.get("data") or response
        job_id = data.get("id") or data.get("job_id")
        if not job_id:
            raise SubmagicError(f"no job id in response: {response}")
        return str(job_id)

    def get_status(self, job_id: str) -> SubmagicJob:
        response = self._request("GET", f"/videos/{job_id}")
        data = response.get("data") or response
        return SubmagicJob(
            job_id=job_id,
            status=data.get("status", "unknown"),
            video_url=data.get("output_url") or data.get("video_url"),
            error=data.get("error"),
        )

    def wait(
        self,
        job_id: str,
        *,
        poll_interval: float = 10.0,
        timeout: float = 900.0,
        sleep_fn: Any = time.sleep,
        now_fn: Any = time.monotonic,
    ) -> SubmagicJob:
        deadline = now_fn() + timeout
        while True:
            job = self.get_status(job_id)
            if job.status == "completed":
                if not job.video_url:
                    raise SubmagicError(f"{job_id} completed with no url")
                return job
            if job.status == "failed":
                raise SubmagicError(f"{job_id} failed: {job.error}")
            if now_fn() >= deadline:
                raise SubmagicError(f"timed out waiting for {job_id}")
            sleep_fn(poll_interval)

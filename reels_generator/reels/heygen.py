"""Minimal HeyGen v2 API client for text-to-avatar video generation."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

API_BASE = "https://api.heygen.com"
GENERATE_ENDPOINT = f"{API_BASE}/v2/video/generate"
STATUS_ENDPOINT = f"{API_BASE}/v1/video_status.get"


class HeyGenError(RuntimeError):
    pass


@dataclass
class VideoJob:
    video_id: str
    status: str = "pending"
    video_url: str | None = None
    error: str | None = None


class HeyGenClient:
    """Thin wrapper around the two HeyGen endpoints we need.

    Uses urllib from the standard library so the package has zero runtime deps
    beyond ffmpeg (which is invoked as a subprocess).
    """

    def __init__(
        self,
        api_key: str,
        avatar_id: str,
        voice_id: str,
        width: int = 1080,
        height: int = 1920,
        opener: Any = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.avatar_id = avatar_id
        self.voice_id = voice_id
        self.width = width
        self.height = height
        # Allow injecting a custom opener for testing.
        self._opener = opener or urllib.request.build_opener()

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        return self._read_json(req)

    def _get(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
        )
        return self._read_json(req)

    def _read_json(self, req: urllib.request.Request) -> dict[str, Any]:
        try:
            with self._opener.open(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise HeyGenError(f"HTTP {e.code} from {req.full_url}: {detail}") from e
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise HeyGenError(f"Non-JSON response from HeyGen: {raw[:500]}") from e

    def submit_hook(self, text: str) -> str:
        """Submit a hook for rendering. Returns the HeyGen video_id."""
        if not text.strip():
            raise ValueError("hook text is empty")
        body = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": self.avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": text,
                        "voice_id": self.voice_id,
                    },
                }
            ],
            "dimension": {"width": self.width, "height": self.height},
        }
        response = self._post(GENERATE_ENDPOINT, body)
        data = response.get("data") or {}
        video_id = data.get("video_id")
        if not video_id:
            raise HeyGenError(f"No video_id in response: {response}")
        return video_id

    def get_status(self, video_id: str) -> VideoJob:
        response = self._get(f"{STATUS_ENDPOINT}?video_id={video_id}")
        data = response.get("data") or {}
        return VideoJob(
            video_id=video_id,
            status=data.get("status", "unknown"),
            video_url=data.get("video_url"),
            error=(data.get("error") or {}).get("message")
            if isinstance(data.get("error"), dict)
            else data.get("error"),
        )

    def wait_for_completion(
        self,
        video_id: str,
        poll_interval: float = 5.0,
        timeout: float = 600.0,
        sleep_fn: Any = time.sleep,
        now_fn: Any = time.monotonic,
    ) -> VideoJob:
        deadline = now_fn() + timeout
        while True:
            job = self.get_status(video_id)
            if job.status == "completed":
                if not job.video_url:
                    raise HeyGenError(f"Completed job {video_id} missing video_url")
                return job
            if job.status == "failed":
                raise HeyGenError(f"Render failed for {video_id}: {job.error}")
            if now_fn() >= deadline:
                raise HeyGenError(
                    f"Timed out waiting for {video_id} (last status: {job.status})"
                )
            sleep_fn(poll_interval)

    def download(self, url: str, dest: Any) -> None:
        req = urllib.request.Request(url, headers={"Accept": "video/mp4"})
        with self._opener.open(req, timeout=120) as resp, open(dest, "wb") as fh:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                fh.write(chunk)

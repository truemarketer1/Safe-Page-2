"""Instagram Graph API — Content Publishing (Reels).

Flow (from official docs):
  1. POST /{ig-user-id}/media  -> returns a creation container id
  2. Poll GET /{container-id}?fields=status_code  until status_code = FINISHED
  3. POST /{ig-user-id}/media_publish?creation_id=...  -> returns the ig_media_id

Hard limit: 100 API-published posts per rolling 24h. Check with
GET /{ig-id}/content_publishing_limit.

Required permissions:
  instagram_basic, instagram_content_publish, pages_show_list,
  business_management (app must be reviewed + live).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class InstagramError(RuntimeError):
    pass


@dataclass
class PublishResult:
    container_id: str
    ig_media_id: str
    permalink: str | None = None


class InstagramClient:
    def __init__(
        self,
        *,
        access_token: str,
        ig_user_id: str,
        api_version: str = "v21.0",
        opener: Any = None,
    ) -> None:
        if not access_token or not ig_user_id:
            raise ValueError("access_token and ig_user_id required")
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.api_version = api_version
        self._opener = opener or urllib.request.build_opener()

    @property
    def _base(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    def _request(self, method: str, path: str, *, params: dict | None = None,
                 body: dict | None = None) -> dict:
        q = dict(params or {})
        q["access_token"] = self.access_token
        url = f"{self._base}{path}?{urllib.parse.urlencode(q)}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self._opener.open(req, timeout=60) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise InstagramError(f"HTTP {e.code} {path}: {detail}") from e
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise InstagramError(f"non-JSON: {raw[:300]}") from e

    def content_publishing_limit(self) -> dict:
        """Returns {'quota_usage', 'config': {'quota_total', 'quota_duration'}}."""
        return self._request("GET", f"/{self.ig_user_id}/content_publishing_limit",
                             params={"fields": "quota_usage,config"})

    def create_reel_container(
        self,
        *,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
        cover_url: str | None = None,
    ) -> str:
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
        }
        if cover_url:
            params["cover_url"] = cover_url
        response = self._request("POST", f"/{self.ig_user_id}/media", params=params)
        cid = response.get("id")
        if not cid:
            raise InstagramError(f"no container id: {response}")
        return cid

    def container_status(self, container_id: str) -> str:
        response = self._request("GET", f"/{container_id}",
                                 params={"fields": "status_code,status"})
        return response.get("status_code") or response.get("status") or "UNKNOWN"

    def wait_for_container(
        self,
        container_id: str,
        *,
        poll_interval: float = 5.0,
        timeout: float = 600.0,
        sleep_fn: Any = time.sleep,
        now_fn: Any = time.monotonic,
    ) -> None:
        deadline = now_fn() + timeout
        while True:
            status = self.container_status(container_id)
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"container {container_id} is {status}")
            if now_fn() >= deadline:
                raise InstagramError(f"container {container_id} not ready in time")
            sleep_fn(poll_interval)

    def publish(self, container_id: str) -> str:
        response = self._request("POST", f"/{self.ig_user_id}/media_publish",
                                 params={"creation_id": container_id})
        media_id = response.get("id")
        if not media_id:
            raise InstagramError(f"no media id: {response}")
        return media_id

    def get_permalink(self, media_id: str) -> str | None:
        response = self._request("GET", f"/{media_id}", params={"fields": "permalink"})
        return response.get("permalink")

    def post_reel(
        self,
        *,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
        cover_url: str | None = None,
    ) -> PublishResult:
        """Convenience: container -> wait -> publish -> permalink in one call."""
        container_id = self.create_reel_container(
            video_url=video_url, caption=caption,
            share_to_feed=share_to_feed, cover_url=cover_url,
        )
        self.wait_for_container(container_id)
        media_id = self.publish(container_id)
        permalink = None
        try:
            permalink = self.get_permalink(media_id)
        except InstagramError:
            pass
        return PublishResult(container_id=container_id, ig_media_id=media_id,
                             permalink=permalink)

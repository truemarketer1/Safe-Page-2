"""Pipeline orchestration: hooks -> HeyGen -> FFmpeg -> final Reels."""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .heygen import HeyGenClient, HeyGenError
from .hooks_source import Hook
from .stitcher import StitchSpec, stitch

log = logging.getLogger("reels")


@dataclass
class ReelResult:
    hook: Hook
    hook_video_path: Path
    final_path: Path | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.final_path is not None


def _hook_cache_key(avatar_id: str, voice_id: str, text: str) -> str:
    digest = hashlib.sha256(
        f"{avatar_id}|{voice_id}|{text}".encode("utf-8")
    ).hexdigest()
    return digest[:16]


def generate_hook_video(
    client: HeyGenClient,
    settings: Settings,
    hook: Hook,
) -> Path:
    """Render a single hook to an mp4 on disk and return its path.

    Skips the HeyGen call if a cached mp4 already exists for this
    (avatar, voice, text) tuple.
    """
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    key = _hook_cache_key(settings.avatar_id, settings.voice_id, hook.text)
    target = settings.cache_dir / f"{hook.slug}_{key}.mp4"
    if target.exists() and target.stat().st_size > 0:
        log.info("cache hit for hook %s", hook.index)
        return target

    log.info("submitting hook %s to HeyGen: %r", hook.index, hook.text)
    video_id = client.submit_hook(hook.text)
    job = client.wait_for_completion(
        video_id,
        poll_interval=settings.poll_interval_seconds,
        timeout=settings.poll_timeout_seconds,
    )
    log.info("downloading %s", job.video_url)
    assert job.video_url  # wait_for_completion guarantees this
    client.download(job.video_url, target)
    return target


def run_pipeline(
    hooks: list[Hook],
    settings: Settings,
    client: HeyGenClient | None = None,
) -> list[ReelResult]:
    """Generate all hook videos in parallel, then stitch each to the core."""
    client = client or HeyGenClient(
        api_key=settings.heygen_api_key,
        avatar_id=settings.avatar_id,
        voice_id=settings.voice_id,
        width=settings.video_width,
        height=settings.video_height,
    )
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[int, ReelResult] = {}

    with ThreadPoolExecutor(max_workers=settings.max_parallel_generations) as pool:
        future_to_hook = {
            pool.submit(generate_hook_video, client, settings, h): h for h in hooks
        }
        for fut in as_completed(future_to_hook):
            hook = future_to_hook[fut]
            try:
                hook_path = fut.result()
            except (HeyGenError, Exception) as e:
                log.exception("generation failed for hook %s", hook.index)
                results[hook.index] = ReelResult(
                    hook=hook,
                    hook_video_path=Path(),
                    final_path=None,
                    error=str(e),
                )
                continue
            try:
                final = settings.output_dir / f"reel_{hook.slug}.mp4"
                stitch(
                    StitchSpec(
                        hook_path=hook_path,
                        core_path=settings.core_video_path,
                        output_path=final,
                        width=settings.video_width,
                        height=settings.video_height,
                    )
                )
                results[hook.index] = ReelResult(
                    hook=hook, hook_video_path=hook_path, final_path=final
                )
            except Exception as e:
                log.exception("stitching failed for hook %s", hook.index)
                results[hook.index] = ReelResult(
                    hook=hook,
                    hook_video_path=hook_path,
                    final_path=None,
                    error=str(e),
                )

    return [results[h.index] for h in hooks if h.index in results]

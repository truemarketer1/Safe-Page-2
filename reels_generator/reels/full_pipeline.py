"""End-to-end: hooks.csv → HeyGen avatar → stitch → (optional) Submagic →
R2 upload → Instagram post → CRM record.

Extends the existing `pipeline.run_pipeline` which only goes hook → stitched
local mp4. This adds the last three legs.

Not used in tests (each leg is unit-tested in isolation); kept in one file for
easy "here's the whole flow" reading.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .crm import CRMClient
from .heygen import HeyGenClient
from .hooks_source import Hook
from .instagram import InstagramClient, PublishResult
from .pipeline import generate_hook_video
from .r2 import R2Config, R2Uploader
from .stitcher import StitchSpec, stitch
from .submagic import SubmagicClient

log = logging.getLogger("reels.full")


@dataclass
class PublishedReel:
    hook: Hook
    final_mp4: Path
    r2_url: str
    publish: PublishResult


def publish_one(
    hook: Hook,
    *,
    settings: Settings,
    heygen: HeyGenClient,
    instagram: InstagramClient,
    r2: R2Uploader,
    caption: str,
    submagic: SubmagicClient | None = None,
    crm: CRMClient | None = None,
) -> PublishedReel:
    # 1. hook -> HeyGen avatar mp4
    hook_mp4 = generate_hook_video(heygen, settings, hook)

    # 2. stitch hook + core video -> final mp4
    final = settings.output_dir / f"reel_{hook.slug}.mp4"
    stitch(StitchSpec(
        hook_path=hook_mp4,
        core_path=settings.core_video_path,
        output_path=final,
        width=settings.video_width,
        height=settings.video_height,
    ))

    # 3. optional Submagic captioning
    final_source = final
    if submagic is not None:
        # Submagic needs a public URL; pre-upload to R2 with a "raw/" prefix.
        raw_key = f"raw/{hook.slug}.mp4"
        raw_url = r2.upload_file(final, raw_key)
        job_id = submagic.submit(raw_url)
        completed = submagic.wait(job_id)
        assert completed.video_url is not None
        # Download submagic output locally so we can re-upload for IG.
        import urllib.request
        final_source = settings.output_dir / f"reel_{hook.slug}_captioned.mp4"
        with urllib.request.urlopen(completed.video_url) as resp, open(final_source, "wb") as fh:
            while chunk := resp.read(1024 * 256):
                fh.write(chunk)

    # 4. upload final to R2 under a date-prefixed key
    from datetime import datetime
    key = f"reels/{datetime.utcnow():%Y/%m/%d}/{hook.slug}.mp4"
    public_url = r2.upload_file(final_source, key)

    # 5. post to Instagram
    result = instagram.post_reel(video_url=public_url, caption=caption)

    # 6. record in CRM
    if crm is not None:
        try:
            crm.record_posted_reel(
                hook_text=hook.text,
                hook_framework=None,
                cta_keyword=None,
                r2_video_url=public_url,
                ig_media_id=result.ig_media_id,
                permalink=result.permalink,
            )
        except Exception:
            log.exception("CRM record failed (non-fatal)")

    return PublishedReel(hook=hook, final_mp4=final_source, r2_url=public_url,
                          publish=result)

"""Meta Graph API (IG Insights) webhooks / pull snapshots -> content_metrics."""

from __future__ import annotations

from typing import Any


def project_meta(cur, event: dict[str, Any]) -> None:
    etype = event["event_type"]
    payload = event["payload"]

    if etype != "meta.insights_snapshot":
        # IG only sends webhooks for DMs (handled by ManyChat) and a couple of
        # mentions/comments we don't yet project. Ignore silently.
        return

    ig_media_id = payload.get("ig_media_id")
    if not ig_media_id:
        return
    cur.execute("SELECT id FROM content_assets WHERE ig_media_id = %s", (ig_media_id,))
    row = cur.fetchone()
    if not row:
        return
    content_id = row["id"]

    metrics = payload.get("metrics", {})
    cur.execute(
        """INSERT INTO content_metrics
             (content_id, impressions, reach, plays, saves, shares, comments,
              likes, avg_watch_seconds, completion_rate, follows_from_post, dm_sends)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            content_id,
            metrics.get("impressions"),
            metrics.get("reach"),
            metrics.get("plays"),
            metrics.get("saves"),
            metrics.get("shares"),
            metrics.get("comments"),
            metrics.get("likes"),
            metrics.get("avg_watch_seconds"),
            metrics.get("completion_rate"),
            metrics.get("follows_from_post"),
            metrics.get("dm_sends"),
        ),
    )

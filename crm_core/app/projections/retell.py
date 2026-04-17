"""Retell voice agent webhooks -> calls table.

Event types (after normalisation):
  - retell.call_started
  - retell.call_ended
  - retell.call_analyzed
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ._util import set_lifecycle_at_least, upsert_lead


def project_retell(cur, event: dict[str, Any]) -> None:
    etype = event["event_type"]
    payload = event["payload"]
    call = payload.get("call") or payload

    provider_call_id = call.get("call_id") or call.get("id")
    if not provider_call_id:
        return

    phone = call.get("to_number") or call.get("phone_number")
    metadata = call.get("metadata") or {}
    lead_id = None
    if metadata.get("lead_id"):
        lead_id = metadata["lead_id"]
    else:
        lead_id = upsert_lead(cur, phone_e164=phone)

    started_at = call.get("start_timestamp")
    ended_at = call.get("end_timestamp")
    if isinstance(started_at, int):
        started_at = datetime.fromtimestamp(started_at / 1000)
    if isinstance(ended_at, int):
        ended_at = datetime.fromtimestamp(ended_at / 1000)

    duration = None
    if call.get("duration_ms"):
        duration = int(call["duration_ms"]) // 1000

    outcome = None
    analysis = call.get("call_analysis") or {}
    if analysis.get("user_sentiment") == "Positive" and analysis.get("call_successful"):
        outcome = "qualified"
    if analysis.get("custom_analysis_data", {}).get("paid"):
        outcome = "paid"
    elif analysis.get("custom_analysis_data", {}).get("booked"):
        outcome = "booked"

    cur.execute(
        """INSERT INTO calls
             (lead_id, provider, provider_call_id, agent_id, direction,
              started_at, ended_at, duration_seconds, status, outcome,
              transcript_url, recording_url, objections)
           VALUES (%s, 'retell', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (provider_call_id) DO UPDATE SET
             ended_at         = COALESCE(EXCLUDED.ended_at, calls.ended_at),
             duration_seconds = COALESCE(EXCLUDED.duration_seconds, calls.duration_seconds),
             status           = COALESCE(EXCLUDED.status, calls.status),
             outcome          = COALESCE(EXCLUDED.outcome, calls.outcome),
             transcript_url   = COALESCE(EXCLUDED.transcript_url, calls.transcript_url),
             recording_url    = COALESCE(EXCLUDED.recording_url, calls.recording_url),
             objections       = COALESCE(EXCLUDED.objections, calls.objections)""",
        (
            lead_id,
            provider_call_id,
            call.get("agent_id"),
            call.get("direction", "outbound"),
            started_at,
            ended_at,
            duration,
            call.get("call_status") or {
                "retell.call_started": "connected",
                "retell.call_ended": "completed",
            }.get(etype),
            outcome,
            call.get("transcript_url"),
            call.get("recording_url"),
            analysis.get("objections") or [],
        ),
    )

    if outcome == "paid":
        set_lifecycle_at_least(cur, lead_id, "closed_won")
    elif outcome == "booked":
        set_lifecycle_at_least(cur, lead_id, "booked")
    elif etype == "retell.call_ended":
        set_lifecycle_at_least(cur, lead_id, "showed")

    cur.execute("UPDATE events SET lead_id = %s WHERE id = %s", (lead_id, event["id"]))

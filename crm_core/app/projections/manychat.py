"""Project ManyChat IG-DM events into leads + conversations + messages.

Expected event_type values (set by the webhook receiver before storage):
  - manychat.comment_received
  - manychat.dm_sent
  - manychat.dm_received
  - manychat.opted_out
"""

from __future__ import annotations

from typing import Any

from ._util import (
    get_or_open_conversation,
    insert_message,
    set_lifecycle_at_least,
    upsert_lead,
)


def project_manychat(cur, event: dict[str, Any]) -> None:
    etype = event["event_type"]
    payload = event["payload"]
    subscriber = payload.get("subscriber") or payload.get("user") or {}

    ig_user_id = str(subscriber.get("id") or subscriber.get("ig_id") or "") or None
    ig_handle = subscriber.get("ig_username") or subscriber.get("name") or None

    lead_id = upsert_lead(
        cur,
        ig_user_id=ig_user_id,
        ig_handle=ig_handle,
        full_name=subscriber.get("name"),
        source_keyword=payload.get("keyword"),
        source_content_id=payload.get("source_content_id"),
    )

    if etype == "manychat.comment_received":
        set_lifecycle_at_least(cur, lead_id, "new")
        cur.execute(
            """INSERT INTO compliance_log (lead_id, kind, evidence)
               VALUES (%s, 'consent_granted',
                 jsonb_build_object('via', 'ig_comment', 'keyword', %s))""",
            (lead_id, payload.get("keyword")),
        )
        cur.execute(
            """UPDATE leads SET
                 consent_dm = true,
                 consent_captured_at = COALESCE(consent_captured_at, now())
               WHERE id = %s""",
            (lead_id,),
        )

    elif etype == "manychat.dm_sent":
        conv_id = get_or_open_conversation(cur, lead_id, "ig_dm")
        insert_message(
            cur,
            conv_id,
            direction="outbound",
            sender_type="ai" if payload.get("sender_type") != "human" else "human",
            body=payload.get("text"),
            raw_payload=payload,
        )
        set_lifecycle_at_least(cur, lead_id, "dm_opened")

    elif etype == "manychat.dm_received":
        conv_id = get_or_open_conversation(cur, lead_id, "ig_dm")
        insert_message(
            cur,
            conv_id,
            direction="inbound",
            sender_type="lead",
            body=payload.get("text"),
            raw_payload=payload,
        )
        set_lifecycle_at_least(cur, lead_id, "qualifying")

    elif etype == "manychat.opted_out":
        cur.execute(
            "UPDATE leads SET consent_dm = false, stop_dm_at = now() WHERE id = %s",
            (lead_id,),
        )
        set_lifecycle_at_least(cur, lead_id, "opted_out")
        cur.execute(
            """INSERT INTO compliance_log (lead_id, kind, evidence)
               VALUES (%s, 'consent_revoked', jsonb_build_object('channel', 'ig_dm'))""",
            (lead_id,),
        )

    # Stash lead_id back on the event row for auditability.
    cur.execute("UPDATE events SET lead_id = %s WHERE id = %s", (lead_id, event["id"]))

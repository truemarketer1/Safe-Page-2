"""Helpers shared across projectors."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def upsert_lead(
    cur,
    *,
    ig_user_id: str | None = None,
    ig_handle: str | None = None,
    phone_e164: str | None = None,
    full_name: str | None = None,
    email: str | None = None,
    source_content_id: UUID | str | None = None,
    source_keyword: str | None = None,
) -> UUID:
    """Find or create a lead by the most reliable key available.

    Precedence: ig_user_id → phone_e164 → email. When we find an existing row we
    patch any newly-supplied fields; we never overwrite an existing non-null value
    with a null one.
    """

    # Try to find an existing lead.
    lead_id: UUID | None = None
    if ig_user_id:
        cur.execute("SELECT id FROM leads WHERE ig_user_id = %s", (ig_user_id,))
        row = cur.fetchone()
        if row:
            lead_id = row["id"]
    if lead_id is None and phone_e164:
        cur.execute("SELECT id FROM leads WHERE phone_e164 = %s", (phone_e164,))
        row = cur.fetchone()
        if row:
            lead_id = row["id"]
    if lead_id is None and email:
        cur.execute("SELECT id FROM leads WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            lead_id = row["id"]

    if lead_id is None:
        cur.execute(
            """INSERT INTO leads
               (ig_user_id, ig_handle, phone_e164, full_name, email,
                source_content_id, source_keyword)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (ig_user_id, ig_handle, phone_e164, full_name, email,
             source_content_id, source_keyword),
        )
        row = cur.fetchone()
        assert row is not None
        return row["id"]

    # Patch missing-but-now-known fields.
    cur.execute(
        """UPDATE leads SET
             ig_user_id        = COALESCE(ig_user_id, %s),
             ig_handle         = COALESCE(ig_handle, %s),
             phone_e164        = COALESCE(phone_e164, %s),
             full_name         = COALESCE(full_name, %s),
             email             = COALESCE(email, %s),
             source_content_id = COALESCE(source_content_id, %s),
             source_keyword    = COALESCE(source_keyword, %s)
           WHERE id = %s""",
        (ig_user_id, ig_handle, phone_e164, full_name, email,
         source_content_id, source_keyword, lead_id),
    )
    return lead_id


def set_lifecycle_at_least(cur, lead_id: UUID, stage: str) -> None:
    """Advance lifecycle stage — never regress."""
    ORDER = [
        "new", "dm_opened", "qualifying", "qualified", "booked",
        "showed", "no_show", "rescheduled", "closed_won", "closed_lost",
        "nurture", "opted_out",
    ]
    if stage not in ORDER:
        return
    target_idx = ORDER.index(stage)
    cur.execute("SELECT lifecycle_stage FROM leads WHERE id = %s", (lead_id,))
    row = cur.fetchone()
    if not row:
        return
    current = row["lifecycle_stage"]
    current_idx = ORDER.index(current) if current in ORDER else -1
    # Terminal states always win.
    terminal = {"closed_won", "closed_lost", "opted_out"}
    if stage in terminal or target_idx > current_idx:
        cur.execute(
            "UPDATE leads SET lifecycle_stage = %s WHERE id = %s",
            (stage, lead_id),
        )


def get_or_open_conversation(cur, lead_id: UUID, channel: str) -> UUID:
    cur.execute(
        """SELECT id FROM conversations
           WHERE lead_id = %s AND channel = %s AND status != 'closed'
           ORDER BY opened_at DESC LIMIT 1""",
        (lead_id, channel),
    )
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO conversations (lead_id, channel) VALUES (%s, %s) RETURNING id",
        (lead_id, channel),
    )
    row = cur.fetchone()
    assert row is not None
    return row["id"]


def insert_message(
    cur,
    conversation_id: UUID,
    *,
    direction: str,
    sender_type: str,
    body: str | None,
    raw_payload: dict[str, Any] | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
) -> UUID:
    cur.execute(
        """INSERT INTO messages
           (conversation_id, direction, sender_type, body, raw_payload, tokens_in, tokens_out)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (conversation_id, direction, sender_type, body, raw_payload, tokens_in, tokens_out),
    )
    row = cur.fetchone()
    assert row is not None
    cur.execute(
        """UPDATE conversations
           SET message_count = message_count + 1,
               last_message_at = now()
           WHERE id = %s""",
        (conversation_id,),
    )
    return row["id"]

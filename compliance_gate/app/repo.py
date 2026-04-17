"""Postgres LeadRepo — reads from the CRM core's `leads` + `calls` tables."""

from __future__ import annotations

import json
import os

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .gate import Lead

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=os.environ["DATABASE_URL"],
            min_size=1,
            max_size=4,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


class PgLeadRepo:
    def get_lead(self, lead_id: str) -> Lead | None:
        with _get_pool().connection() as c, c.cursor() as cur:
            cur.execute(
                """SELECT id, phone_e164, region, COALESCE(timezone, 'America/New_York') AS tz,
                          consent_voice_ai, consent_recording, consent_sms, consent_dm,
                          stop_sms_at, stop_dm_at, dnc_status
                   FROM leads WHERE id = %s""",
                (lead_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                """SELECT max(created_at) AS last_at
                   FROM messages m JOIN conversations c ON c.id = m.conversation_id
                   WHERE c.lead_id = %s AND m.direction = 'inbound' AND c.channel = 'ig_dm'""",
                (lead_id,),
            )
            last = cur.fetchone()
            return Lead(
                id=str(row["id"]),
                phone_e164=row["phone_e164"],
                region=row["region"],
                timezone=row["tz"],
                consent_voice_ai=row["consent_voice_ai"],
                consent_recording=row["consent_recording"],
                consent_sms=row["consent_sms"],
                consent_dm=row["consent_dm"],
                stop_sms_at=row["stop_sms_at"],
                stop_dm_at=row["stop_dm_at"],
                dnc_status=row["dnc_status"],
                last_dm_inbound_at=(last or {}).get("last_at"),
            )

    def calls_in_last_24h(self, lead_id: str) -> int:
        with _get_pool().connection() as c, c.cursor() as cur:
            cur.execute(
                """SELECT count(*) AS n FROM calls
                   WHERE lead_id = %s
                     AND started_at IS NOT NULL
                     AND started_at > now() - interval '24 hours'""",
                (lead_id,),
            )
            row = cur.fetchone() or {"n": 0}
            return int(row["n"])

    def log_decision(self, lead_id: str, kind: str, evidence: dict) -> None:
        with _get_pool().connection() as c, c.cursor() as cur:
            cur.execute(
                """INSERT INTO compliance_log (lead_id, kind, evidence)
                   VALUES (%s, %s, %s)""",
                (lead_id, kind, json.dumps(evidence)),
            )

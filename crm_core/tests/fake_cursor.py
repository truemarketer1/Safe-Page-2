"""A tiny in-memory stand-in for a psycopg cursor so projection unit tests can
run without a live Postgres.

Only implements the subset of SQL semantics the projectors actually use:
  - INSERT INTO leads ... RETURNING id (with default gen)
  - UPDATE leads SET ... WHERE id = %s
  - SELECT id FROM leads WHERE ig_user_id/phone_e164/email
  - SELECT lifecycle_stage FROM leads WHERE id
  - INSERT INTO conversations ... RETURNING id
  - SELECT id FROM conversations WHERE lead_id/channel/status
  - INSERT INTO messages ...
  - UPDATE conversations SET message_count = ...
  - INSERT INTO appointments ON CONFLICT (cal_event_id) DO UPDATE
  - UPDATE appointments SET ...
  - INSERT INTO calls ON CONFLICT ...
  - INSERT INTO payments ON CONFLICT ...
  - INSERT INTO compliance_log
  - UPDATE events SET lead_id = %s WHERE id = %s
  - SELECT * FROM events WHERE id

It is deliberately permissive: anything it doesn't recognise is a no-op. The
goal is to exercise the projector's branching logic and state transitions
without reinventing Postgres.
"""

from __future__ import annotations

import re
import uuid
from typing import Any


class FakeDB:
    def __init__(self) -> None:
        self.leads: dict[str, dict] = {}
        self.conversations: dict[str, dict] = {}
        self.messages: list[dict] = []
        self.appointments: dict[str, dict] = {}  # keyed by cal_event_id
        self.calls: dict[str, dict] = {}  # keyed by provider_call_id
        self.payments: dict[str, dict] = {}  # keyed by stripe_payment_intent_id
        self.compliance_log: list[dict] = []
        self.events: dict[str, dict] = {}


class FakeCursor:
    def __init__(self, db: FakeDB) -> None:
        self.db = db
        self._last_result: dict | None = None

    def execute(self, sql: str, params: tuple = ()) -> None:
        s = " ".join(sql.split()).lower()
        self._last_result = None

        # ---- leads lookups
        if m := re.match(r"select id from leads where ig_user_id = %s", s):
            val = params[0]
            for lead in self.db.leads.values():
                if lead.get("ig_user_id") == val:
                    self._last_result = {"id": lead["id"]}
                    return
            return
        if m := re.match(r"select id from leads where phone_e164 = %s", s):
            val = params[0]
            for lead in self.db.leads.values():
                if lead.get("phone_e164") == val:
                    self._last_result = {"id": lead["id"]}
                    return
            return
        if m := re.match(r"select id from leads where email = %s", s):
            val = params[0]
            for lead in self.db.leads.values():
                if lead.get("email") == val:
                    self._last_result = {"id": lead["id"]}
                    return
            return

        # ---- insert lead
        if s.startswith("insert into leads"):
            ig_user_id, ig_handle, phone, name, email, src_content, src_kw = params
            lid = str(uuid.uuid4())
            self.db.leads[lid] = {
                "id": lid,
                "ig_user_id": ig_user_id,
                "ig_handle": ig_handle,
                "phone_e164": phone,
                "full_name": name,
                "email": email,
                "source_content_id": src_content,
                "source_keyword": src_kw,
                "lifecycle_stage": "new",
                "consent_dm": False,
                "stop_dm_at": None,
            }
            self._last_result = {"id": lid}
            return

        # ---- update lead (patch missing fields)
        if s.startswith("update leads set ig_user_id = coalesce"):
            ig_user_id, ig_handle, phone, name, email, src_content, src_kw, lid = params
            lead = self.db.leads.get(lid)
            if lead:
                for k, v in [
                    ("ig_user_id", ig_user_id), ("ig_handle", ig_handle),
                    ("phone_e164", phone), ("full_name", name), ("email", email),
                    ("source_content_id", src_content), ("source_keyword", src_kw),
                ]:
                    if v is not None and lead.get(k) is None:
                        lead[k] = v
            return

        # ---- lifecycle read/write
        if s == "select lifecycle_stage from leads where id = %s":
            lead = self.db.leads.get(params[0])
            if lead:
                self._last_result = {"lifecycle_stage": lead["lifecycle_stage"]}
            return
        if s == "update leads set lifecycle_stage = %s where id = %s":
            stage, lid = params
            if lid in self.db.leads:
                self.db.leads[lid]["lifecycle_stage"] = stage
            return
        if "update leads set" in s and "stop_dm_at = now()" in s:
            self.db.leads[params[0]]["consent_dm"] = False
            self.db.leads[params[0]]["stop_dm_at"] = "now"
            return
        if s.startswith("update leads set consent_dm = true"):
            self.db.leads[params[0]]["consent_dm"] = True
            return

        # ---- conversations
        if s.startswith("select id from conversations"):
            lead_id, channel = params
            for c in self.db.conversations.values():
                if c["lead_id"] == lead_id and c["channel"] == channel and c.get("status") != "closed":
                    self._last_result = {"id": c["id"]}
                    return
            return
        if s.startswith("insert into conversations"):
            lead_id, channel = params
            cid = str(uuid.uuid4())
            self.db.conversations[cid] = {
                "id": cid, "lead_id": lead_id, "channel": channel,
                "status": "open", "message_count": 0,
            }
            self._last_result = {"id": cid}
            return

        # ---- messages
        if s.startswith("insert into messages"):
            conv_id, direction, sender, body, raw, tin, tout = params
            mid = str(uuid.uuid4())
            self.db.messages.append({
                "id": mid, "conversation_id": conv_id,
                "direction": direction, "sender_type": sender, "body": body,
            })
            self._last_result = {"id": mid}
            return
        if s.startswith("update conversations set message_count"):
            cid = params[0]
            if cid in self.db.conversations:
                self.db.conversations[cid]["message_count"] += 1
            return

        # ---- appointments
        if s.startswith("insert into appointments"):
            lead_id, cal_event_id, scheduled_for, duration, appt_type, assigned_to = params
            self.db.appointments[cal_event_id] = {
                "lead_id": lead_id, "cal_event_id": cal_event_id,
                "scheduled_for": scheduled_for, "duration_minutes": duration,
                "appointment_type": appt_type, "status": "booked",
                "reschedule_count": 0, "assigned_to": assigned_to,
            }
            return
        if s.startswith("update appointments set status = 'rescheduled'"):
            scheduled_for, cal_event_id = params
            if cal_event_id in self.db.appointments:
                self.db.appointments[cal_event_id]["status"] = "rescheduled"
                self.db.appointments[cal_event_id]["scheduled_for"] = scheduled_for
                self.db.appointments[cal_event_id]["reschedule_count"] += 1
            return
        if s.startswith("update appointments set status = 'cancelled'"):
            cal_event_id = params[0]
            if cal_event_id in self.db.appointments:
                self.db.appointments[cal_event_id]["status"] = "cancelled"
            return

        # ---- calls
        if s.startswith("insert into calls"):
            (lead_id, provider_call_id, agent_id, direction, started_at, ended_at,
             duration, status_, outcome, tx_url, rec_url, objections) = params
            existing = self.db.calls.get(provider_call_id, {})
            self.db.calls[provider_call_id] = {
                **existing,
                "lead_id": lead_id, "provider_call_id": provider_call_id,
                "agent_id": agent_id, "direction": direction,
                "started_at": started_at or existing.get("started_at"),
                "ended_at": ended_at or existing.get("ended_at"),
                "duration_seconds": duration or existing.get("duration_seconds"),
                "status": status_ or existing.get("status"),
                "outcome": outcome or existing.get("outcome"),
                "transcript_url": tx_url or existing.get("transcript_url"),
                "recording_url": rec_url or existing.get("recording_url"),
                "objections": objections or existing.get("objections"),
            }
            return

        # ---- payments
        if s.startswith("insert into payments") and "on conflict" in s and "'paid'" in s:
            lead_id, pi_id, link_id, amount, currency, paid_at = params
            existing = self.db.payments.get(pi_id, {})
            self.db.payments[pi_id] = {
                **existing,
                "lead_id": lead_id, "stripe_payment_intent_id": pi_id,
                "stripe_payment_link_id": link_id,
                "amount_cents": amount, "currency": currency,
                "status": "paid", "paid_at": paid_at,
            }
            return
        if s.startswith("insert into payments") and "'failed'" in s:
            lead_id, pi_id, amount, currency = params
            self.db.payments[pi_id] = {
                "lead_id": lead_id, "stripe_payment_intent_id": pi_id,
                "amount_cents": amount, "currency": currency, "status": "failed",
            }
            return
        if s.startswith("update payments set status = 'refunded'"):
            pi_id = params[0]
            if pi_id in self.db.payments:
                self.db.payments[pi_id]["status"] = "refunded"
            return
        if s.startswith("insert into payments") and "'link_clicked'" in s:
            lead_id, link_id, amount, currency = params
            self.db.payments[str(uuid.uuid4())] = {
                "lead_id": lead_id, "stripe_payment_link_id": link_id,
                "amount_cents": amount, "currency": currency,
                "status": "link_clicked",
            }
            return

        # ---- compliance
        if s.startswith("insert into compliance_log"):
            self.db.compliance_log.append({"params": params, "sql": s})
            return

        # ---- events update
        if s.startswith("update events set lead_id = %s where id = %s"):
            lead_id, event_id = params
            if event_id in self.db.events:
                self.db.events[event_id]["lead_id"] = lead_id
            return

        # anything else: no-op

    def fetchone(self) -> dict | None:
        return self._last_result

    def fetchall(self) -> list[dict]:
        return [self._last_result] if self._last_result else []

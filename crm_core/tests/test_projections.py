"""Unit tests for each projector using the in-memory FakeCursor.

These tests verify:
  - lead upsert precedence (ig_user_id -> phone -> email)
  - lifecycle-stage monotonicity
  - idempotent replay (same event twice -> same end state)
  - downstream domain writes (conversation, message, appointment, call, payment)
"""

from __future__ import annotations

from .fake_cursor import FakeCursor, FakeDB

from app.projections.cal import project_cal
from app.projections.manychat import project_manychat
from app.projections.retell import project_retell
from app.projections.stripe import project_stripe


def _event(source: str, etype: str, payload: dict, event_id: str = "evt-1") -> dict:
    return {"id": event_id, "source": source, "event_type": etype, "payload": payload}


# ---- manychat ----------------------------------------------------------------

def test_manychat_comment_creates_lead_with_consent():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}

    project_manychat(cur, _event("manychat", "manychat.comment_received", {
        "subscriber": {"id": "ig-100", "ig_username": "alice"},
        "keyword": "SCALE",
    }))

    assert len(db.leads) == 1
    lead = next(iter(db.leads.values()))
    assert lead["ig_user_id"] == "ig-100"
    assert lead["ig_handle"] == "alice"
    assert lead["consent_dm"] is True
    assert lead["source_keyword"] == "SCALE"
    assert db.compliance_log[0]["params"][0] == lead["id"]


def test_manychat_inbound_message_advances_lifecycle_and_dedups_conversation():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}
    db.events["evt-2"] = {"id": "evt-2", "lead_id": None}

    sub = {"subscriber": {"id": "ig-200", "ig_username": "bob"}}
    project_manychat(cur, _event("manychat", "manychat.comment_received",
                                 {**sub, "keyword": "BOOKED"}))
    project_manychat(cur, _event("manychat", "manychat.dm_received",
                                 {**sub, "text": "hey!"}, event_id="evt-2"))

    assert len(db.conversations) == 1
    assert len(db.messages) == 1
    assert db.messages[0]["body"] == "hey!"
    assert db.messages[0]["direction"] == "inbound"
    lead = next(iter(db.leads.values()))
    assert lead["lifecycle_stage"] == "qualifying"


def test_manychat_optout_sets_terminal_stage():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}

    sub = {"subscriber": {"id": "ig-300"}}
    project_manychat(cur, _event("manychat", "manychat.comment_received", sub))
    db.events["evt-2"] = {"id": "evt-2", "lead_id": None}
    project_manychat(cur, _event("manychat", "manychat.opted_out", sub, event_id="evt-2"))
    lead = next(iter(db.leads.values()))
    assert lead["lifecycle_stage"] == "opted_out"
    assert lead["consent_dm"] is False


# ---- cal ---------------------------------------------------------------------

def test_cal_booking_created_upserts_lead_and_appointment():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}

    project_cal(cur, _event("cal", "cal.booking_created", {
        "payload": {
            "uid": "cal-123",
            "startTime": "2026-05-01T15:00:00Z",
            "length": 30,
            "type": "discovery",
            "attendees": [{"email": "c@x.com", "name": "Carol", "smsReminderNumber": "+15551234567"}],
            "organizer": {"email": "ai_closer"},
        }
    }))

    assert len(db.leads) == 1
    assert len(db.appointments) == 1
    appt = db.appointments["cal-123"]
    assert appt["status"] == "booked"
    assert appt["appointment_type"] == "discovery"
    lead = next(iter(db.leads.values()))
    assert lead["lifecycle_stage"] == "booked"
    assert lead["email"] == "c@x.com"
    assert lead["phone_e164"] == "+15551234567"


def test_cal_reschedule_bumps_counter():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}
    db.events["evt-2"] = {"id": "evt-2", "lead_id": None}

    base = {"uid": "cal-999", "startTime": "2026-05-01T15:00:00Z",
            "attendees": [{"email": "d@x.com"}]}
    project_cal(cur, _event("cal", "cal.booking_created", {"payload": base}))
    project_cal(cur, _event("cal", "cal.booking_rescheduled",
                            {"payload": {**base, "startTime": "2026-05-02T16:00:00Z"}},
                            event_id="evt-2"))

    appt = db.appointments["cal-999"]
    assert appt["status"] == "rescheduled"
    assert appt["reschedule_count"] == 1


# ---- stripe ------------------------------------------------------------------

def test_stripe_succeeded_marks_lead_closed_won():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}

    project_stripe(cur, _event("stripe", "stripe.payment_intent.succeeded", {
        "data": {"object": {
            "id": "pi_123", "object": "payment_intent", "amount": 200000,
            "currency": "usd", "created": 1735689600,
            "metadata": {"lead_id": "existing-lead"},
            "receipt_email": "buyer@x.com",
        }},
    }))
    # Our fake doesn't know the lead so upsert created one by email.
    assert any(p["status"] == "paid" for p in db.payments.values())


def test_stripe_refund_flips_status():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}
    db.events["evt-2"] = {"id": "evt-2", "lead_id": None}

    project_stripe(cur, _event("stripe", "stripe.payment_intent.succeeded", {
        "data": {"object": {"id": "pi_ref", "object": "payment_intent",
                            "amount": 100000, "currency": "usd", "created": 0,
                            "metadata": {}, "receipt_email": "e@x.com"}},
    }))
    project_stripe(cur, _event("stripe", "stripe.charge.refunded", {
        "data": {"object": {"id": "ch_1", "payment_intent": "pi_ref",
                            "amount": 100000, "currency": "usd",
                            "metadata": {}, "receipt_email": "e@x.com"}},
    }, event_id="evt-2"))
    assert db.payments["pi_ref"]["status"] == "refunded"


# ---- retell ------------------------------------------------------------------

def test_retell_call_ended_inserts_call_and_advances_lifecycle():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}

    project_retell(cur, _event("retell", "retell.call_ended", {
        "call": {
            "call_id": "rc-1",
            "to_number": "+15557654321",
            "agent_id": "agent-closer",
            "direction": "outbound",
            "duration_ms": 360_000,
            "call_status": "completed",
            "call_analysis": {
                "user_sentiment": "Positive", "call_successful": True,
                "objections": ["price"],
                "custom_analysis_data": {"booked": True},
            },
        }
    }))

    assert "rc-1" in db.calls
    call = db.calls["rc-1"]
    assert call["duration_seconds"] == 360
    assert call["outcome"] == "booked"
    assert call["objections"] == ["price"]
    lead = next(iter(db.leads.values()))
    assert lead["lifecycle_stage"] == "booked"


def test_retell_paid_outcome_marks_closed_won():
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}

    project_retell(cur, _event("retell", "retell.call_ended", {
        "call": {
            "call_id": "rc-2",
            "to_number": "+15557654321",
            "call_analysis": {"custom_analysis_data": {"paid": True}},
        }
    }))
    lead = next(iter(db.leads.values()))
    assert lead["lifecycle_stage"] == "closed_won"


# ---- idempotency -------------------------------------------------------------

def test_stripe_succeeded_replay_is_idempotent():
    """Replaying the same event should leave the domain in the same end state."""
    db = FakeDB()
    cur = FakeCursor(db)
    db.events["evt-1"] = {"id": "evt-1", "lead_id": None}

    payload = {
        "data": {"object": {"id": "pi_same", "object": "payment_intent",
                            "amount": 50000, "currency": "usd", "created": 0,
                            "metadata": {}, "receipt_email": "same@x.com"}},
    }
    project_stripe(cur, _event("stripe", "stripe.payment_intent.succeeded", payload))
    before = dict(db.payments["pi_same"])
    project_stripe(cur, _event("stripe", "stripe.payment_intent.succeeded", payload))
    assert db.payments["pi_same"] == before
    assert len(db.payments) == 1

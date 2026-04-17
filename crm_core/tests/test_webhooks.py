"""API-level tests for webhook receivers using FastAPI's TestClient.

DB interaction is stubbed out by monkeypatching _store_event and
_project_async so these tests run without a live Postgres.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app import webhooks as wh_module
from app.main import create_app


@pytest.fixture
def client(monkeypatch) -> TestClient:
    stored: list[tuple] = []
    projected: list[str] = []

    def fake_store(source, event_type, payload, idempotency_key, signature_valid):
        stored.append((source, event_type, payload, idempotency_key, signature_valid))
        return str(uuid.uuid4())

    def fake_project(event_id):
        projected.append(event_id)

    monkeypatch.setattr(wh_module, "_store_event", fake_store)
    monkeypatch.setattr(wh_module, "_project_async", fake_project)

    app = create_app()
    c = TestClient(app)
    c.stored = stored
    c.projected = projected
    return c


def test_cal_webhook_routes_and_normalises_trigger(client: TestClient) -> None:
    r = client.post("/webhook/cal", json={
        "triggerEvent": "BOOKING_CREATED",
        "uid": "cal-xyz",
        "payload": {"uid": "cal-xyz", "startTime": "2026-05-01T00:00:00Z",
                    "attendees": [{"email": "a@b.com"}]},
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert client.stored[-1][1] == "cal.booking_created"


def test_stripe_webhook_rejects_bad_signature_when_secret_set(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    # rebuild settings cache
    from app import config as cfg
    cfg.get_settings.cache_clear()

    app = create_app()
    c = TestClient(app)
    r = c.post("/webhook/stripe", headers={"stripe-signature": "garbage"},
               content=b'{"type":"payment_intent.succeeded"}')
    assert r.status_code == 401

    # valid signature passes
    body = b'{"type":"payment_intent.succeeded","id":"evt_1"}'
    ts = str(int(time.time()))
    sig = hmac.new(b"whsec_test", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    # monkeypatch storage to avoid hitting DB
    from app import webhooks as wh_mod
    stored: list[tuple] = []
    def fake_store(*args, **kwargs):
        stored.append(args)
        return str(uuid.uuid4())
    monkeypatch.setattr(wh_mod, "_store_event", fake_store)
    monkeypatch.setattr(wh_mod, "_project_async", lambda _: None)

    r2 = c.post(
        "/webhook/stripe",
        headers={"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"},
        content=body,
    )
    assert r2.status_code == 200
    cfg.get_settings.cache_clear()


def test_manychat_event_type_derived_from_payload(client: TestClient) -> None:
    client.post("/webhook/manychat", json={
        "event_type": "comment_received",
        "subscriber": {"id": "ig-1"},
        "keyword": "SCALE",
    })
    assert client.stored[-1][1] == "manychat.comment_received"


def test_retell_webhook_uses_call_id_as_idempotency(client: TestClient) -> None:
    client.post("/webhook/retell", json={
        "event": "call_ended",
        "call": {"call_id": "rc-42", "to_number": "+15551234567"},
    })
    source, event_type, payload, idem, _ = client.stored[-1]
    assert source == "retell"
    assert event_type == "retell.call_ended"
    assert idem == "rc-42"

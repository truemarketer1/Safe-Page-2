"""Webhook receivers — one endpoint per external source.

Each receiver:
  1. Reads the raw body (needed for signature verification).
  2. Verifies the vendor signature (fail closed if secret is set).
  3. Normalises into an `InternalEvent` and inserts into `events`.
  4. Returns 200 fast. Projection runs in the background.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from .config import get_settings
from .db import conn
from .projector import project_event
from .schemas import WebhookAck
from .signing import verify_meta, verify_shared_secret, verify_stripe

log = logging.getLogger("crm.webhooks")

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _store_event(source: str, event_type: str, payload: dict[str, Any],
                 idempotency_key: str | None, signature_valid: bool) -> str:
    with conn() as c, c.cursor() as cur:
        try:
            cur.execute(
                """INSERT INTO events
                     (source, event_type, idempotency_key, payload, signature_valid)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id""",
                (source, event_type, idempotency_key, json.dumps(payload), signature_valid),
            )
        except Exception as e:
            # Unique violation on (source, idempotency_key) means we already stored it.
            if "ux_events_source_idem" in str(e):
                cur.execute(
                    """SELECT id FROM events
                       WHERE source = %s AND idempotency_key = %s""",
                    (source, idempotency_key),
                )
                row = cur.fetchone()
                if row:
                    return str(row["id"])
            raise
        row = cur.fetchone()
        assert row is not None
        return str(row["id"])


def _project_async(event_id: str) -> None:
    try:
        project_event(event_id)
    except Exception:  # pragma: no cover
        log.exception("background projection failed for %s", event_id)


# ---- Stripe ------------------------------------------------------------------

@router.post("/stripe", response_model=WebhookAck)
async def stripe_webhook(
    request: Request,
    background: BackgroundTasks,
    stripe_signature: str = Header(default=""),
) -> WebhookAck:
    body = await request.body()
    settings = get_settings()
    valid = verify_stripe(settings.stripe_webhook_secret, stripe_signature, body)
    if settings.stripe_webhook_secret and not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload = json.loads(body)
    event_id = _store_event(
        "stripe",
        f"stripe.{payload.get('type', 'unknown')}",
        payload,
        payload.get("id"),
        valid,
    )
    background.add_task(_project_async, event_id)
    return WebhookAck(event_id=event_id)


# ---- Meta / IG ---------------------------------------------------------------

@router.get("/meta")
async def meta_verify(
    hub_mode: str = "", hub_verify_token: str = "", hub_challenge: str = "",
) -> Any:
    """Meta verification handshake (query args use dot notation they normalize to underscore)."""
    # FastAPI converts hub.mode -> hub_mode automatically when aliased at runtime.
    return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge


@router.post("/meta", response_model=WebhookAck)
async def meta_webhook(
    request: Request,
    background: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
) -> WebhookAck:
    body = await request.body()
    settings = get_settings()
    valid = verify_meta(settings.meta_app_secret, x_hub_signature_256, body)
    if settings.meta_app_secret and not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload = json.loads(body)
    event_id = _store_event(
        "meta",
        f"meta.{payload.get('object', 'unknown')}",
        payload,
        None,
        valid,
    )
    background.add_task(_project_async, event_id)
    return WebhookAck(event_id=event_id)


# ---- Cal.com -----------------------------------------------------------------

@router.post("/cal", response_model=WebhookAck)
async def cal_webhook(
    request: Request,
    background: BackgroundTasks,
    x_cal_signature_256: str = Header(default=""),
) -> WebhookAck:
    body = await request.body()
    settings = get_settings()
    valid = verify_shared_secret(settings.cal_webhook_secret, x_cal_signature_256)
    if settings.cal_webhook_secret and not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload = json.loads(body)
    trigger = payload.get("triggerEvent") or payload.get("event")
    name = {
        "BOOKING_CREATED": "cal.booking_created",
        "BOOKING_RESCHEDULED": "cal.booking_rescheduled",
        "BOOKING_CANCELLED": "cal.booking_cancelled",
    }.get(trigger, f"cal.{trigger or 'unknown'}")
    event_id = _store_event("cal", name, payload, payload.get("uid"), valid)
    background.add_task(_project_async, event_id)
    return WebhookAck(event_id=event_id)


# ---- Retell ------------------------------------------------------------------

@router.post("/retell", response_model=WebhookAck)
async def retell_webhook(
    request: Request,
    background: BackgroundTasks,
    x_retell_signature: str = Header(default=""),
) -> WebhookAck:
    body = await request.body()
    settings = get_settings()
    valid = verify_shared_secret(settings.retell_webhook_secret, x_retell_signature)
    if settings.retell_webhook_secret and not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload = json.loads(body)
    evt = payload.get("event") or "call_ended"
    event_id = _store_event(
        "retell",
        f"retell.{evt}",
        payload,
        (payload.get("call") or {}).get("call_id"),
        valid,
    )
    background.add_task(_project_async, event_id)
    return WebhookAck(event_id=event_id)


# ---- ManyChat ----------------------------------------------------------------

@router.post("/manychat", response_model=WebhookAck)
async def manychat_webhook(
    request: Request,
    background: BackgroundTasks,
    x_manychat_secret: str = Header(default=""),
) -> WebhookAck:
    body = await request.body()
    settings = get_settings()
    valid = verify_shared_secret(settings.manychat_webhook_secret, x_manychat_secret)
    if settings.manychat_webhook_secret and not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload = json.loads(body)
    evt = payload.get("event_type") or "dm_received"
    event_id = _store_event(
        "manychat",
        f"manychat.{evt}",
        payload,
        payload.get("idempotency_key"),
        valid,
    )
    background.add_task(_project_async, event_id)
    return WebhookAck(event_id=event_id)

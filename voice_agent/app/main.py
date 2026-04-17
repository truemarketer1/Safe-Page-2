"""FastAPI service exposing:

  - POST /voice/handoff        Cal.com-booking or callback-request trigger
  - POST /voice/payment-link   Retell tool-call (mid-call Stripe + SMS)
  - GET  /health
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .compliance import ComplianceClient
from .context import LeadContext
from .orchestrator import handoff_to_ai_voice
from .retell import RetellClient
from .stripe import StripeClient
from .twilio import TwilioClient

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(title="Voice agent", version="0.1.0")
_auth = HTTPBearer(auto_error=False)


def _retell() -> RetellClient:
    return RetellClient(api_key=os.environ["RETELL_API_KEY"])


def _stripe() -> StripeClient:
    return StripeClient(api_key=os.environ["STRIPE_SECRET_KEY"])


def _twilio() -> TwilioClient:
    return TwilioClient(
        account_sid=os.environ["TWILIO_ACCOUNT_SID"],
        auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        from_number=os.environ["TWILIO_FROM_NUMBER"],
    )


def _compliance() -> ComplianceClient:
    return ComplianceClient()


def require_token(creds: HTTPAuthorizationCredentials | None = Depends(_auth)) -> None:
    expected = os.environ.get("VOICE_AGENT_TOKEN", "")
    if not expected:
        return
    if creds is None or creds.credentials != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad token")


class HandoffIn(BaseModel):
    lead_id: str
    first_name: str | None = None
    phone_e164: str
    offer_name: str
    pain_point: str | None = None
    timeline: str = "unknown"
    dm_summary: str = ""
    calendar_slot_iso: str | None = None


class HandoffOut(BaseModel):
    allowed: bool
    call_id: str | None = None
    reason: str | None = None
    details: dict | None = None


@app.post("/voice/handoff", response_model=HandoffOut, dependencies=[Depends(require_token)])
def handoff(body: HandoffIn) -> HandoffOut:
    ctx = LeadContext(
        lead_id=body.lead_id, first_name=body.first_name, phone_e164=body.phone_e164,
        offer_name=body.offer_name, pain_point=body.pain_point, timeline=body.timeline,
        dm_summary=body.dm_summary, calendar_slot_iso=body.calendar_slot_iso,
    )
    outcome = handoff_to_ai_voice(
        ctx,
        retell=_retell(),
        retell_agent_id=os.environ["RETELL_AGENT_ID"],
        retell_from_number=os.environ["RETELL_FROM_NUMBER"],
        compliance=_compliance(),
    )
    return HandoffOut(
        allowed=outcome.compliance.allowed,
        call_id=outcome.call.call_id if outcome.call else None,
        reason=outcome.compliance.reason,
        details=outcome.compliance.details,
    )


class PaymentLinkIn(BaseModel):
    lead_id: str
    phone_e164: str
    price_id: str
    call_id: str | None = None


class PaymentLinkOut(BaseModel):
    payment_link_id: str
    url: str
    sms_sid: str | None = None


@app.post("/voice/payment-link", response_model=PaymentLinkOut,
          dependencies=[Depends(require_token)])
def payment_link(body: PaymentLinkIn) -> PaymentLinkOut:
    """Retell tool-call handler. Creates a Stripe Payment Link and SMS-texts
    it to the prospect mid-call."""
    link = _stripe().create_payment_link(
        price_id=body.price_id, lead_id=body.lead_id, call_id=body.call_id,
    )
    url = link["url"]
    link_id = link["id"]
    sms_sid = None
    try:
        sms = _twilio().send_sms(
            body.phone_e164,
            f"Here's your secure checkout link — let me know once you're done: {url}",
        )
        sms_sid = sms.get("sid")
    except Exception:
        logging.exception("SMS send failed (Stripe link still created)")
    return PaymentLinkOut(payment_link_id=link_id, url=url, sms_sid=sms_sid)


@app.get("/health")
def health() -> dict:
    return {"ok": True}

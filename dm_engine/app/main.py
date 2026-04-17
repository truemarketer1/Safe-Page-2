"""FastAPI webhook for ManyChat (or any DM bot) to POST incoming messages.

Flow per request:
  1. ManyChat POSTs {lead_id, history, text}.
  2. We run the qualifier.
  3. We emit the assistant reply back so ManyChat can send it.
  4. We separately POST to the CRM's /webhook/manychat so the conversation
     + message rows get created (out-of-band, non-blocking).
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .llm import AnthropicClient
from .qualifier import OfferConfig, QualifierResult, qualify_turn

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(title="DM engine", version="0.1.0")
_auth = HTTPBearer(auto_error=False)


def _build_offer() -> OfferConfig:
    return OfferConfig(
        brand_voice_name=os.environ.get("OFFER_BRAND_NAME", "Your Brand"),
        offer_category=os.environ.get("OFFER_CATEGORY", "business coaching"),
        offer_name=os.environ.get("OFFER_NAME", "1:1 Coaching"),
        offer_price=os.environ.get("OFFER_PRICE", "$2,000"),
        offer_promise=os.environ.get("OFFER_PROMISE", "a clear path to X in 60 days"),
        icp_description=os.environ.get("ICP_DESCRIPTION",
                                       "coaches doing <$10k/mo who want to scale"),
        calendar_url=os.environ.get("CALENDAR_URL", "https://cal.com/you/discovery"),
    )


def _build_llm() -> AnthropicClient:
    return AnthropicClient(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    )


def require_token(creds: HTTPAuthorizationCredentials | None = Depends(_auth)) -> None:
    expected = os.environ.get("DM_ENGINE_TOKEN", "")
    if not expected:
        return
    if creds is None or creds.credentials != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad token")


class Turn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class QualifyIn(BaseModel):
    lead_id: str
    text: str
    history: list[Turn] = []


class QualifyOut(BaseModel):
    lead_id: str
    reply: str
    decision: str
    lead_score: int
    lead_tier: str
    pain: str | None = None
    timeline: str
    fit_signals: list[str]
    tokens_in: int
    tokens_out: int


@app.post("/dm/qualify", response_model=QualifyOut, dependencies=[Depends(require_token)])
def qualify_endpoint(body: QualifyIn) -> QualifyOut:
    llm = _build_llm()
    offer = _build_offer()
    result: QualifierResult = qualify_turn(
        llm=llm,
        offer=offer,
        history=[t.model_dump() for t in body.history],
        new_message=body.text,
    )
    return QualifyOut(
        lead_id=body.lead_id,
        reply=result.reply,
        decision=result.decision,
        lead_score=result.lead_score,
        lead_tier=result.lead_tier,
        pain=result.pain,
        timeline=result.timeline,
        fit_signals=result.fit_signals,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )


@app.get("/health")
def health() -> dict:
    return {"ok": True}

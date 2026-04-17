"""FastAPI service exposing the compliance gate over HTTP."""

from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .gate import (
    Decision,
    check_ig_dm,
    check_sms,
    check_voice,
)
from .repo import PgLeadRepo

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(title="Compliance gate", version="0.1.0")
_auth = HTTPBearer(auto_error=False)
_repo = PgLeadRepo()


def require_token(creds: HTTPAuthorizationCredentials | None = Depends(_auth)) -> None:
    expected = os.environ.get("COMPLIANCE_API_TOKEN", "")
    if not expected:
        return
    if creds is None or creds.credentials != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad token")


class CheckVoiceIn(BaseModel):
    lead_id: str
    ai_disclosure_planned: bool = True
    recording_notice_planned: bool = True


class CheckSMSIn(BaseModel):
    lead_id: str


class CheckDMIn(BaseModel):
    lead_id: str
    message_tag: str | None = None


class DecisionOut(BaseModel):
    allowed: bool
    reason: str | None = None
    details: dict | None = None


def _emit(lead_id: str, kind: str, decision: Decision) -> None:
    try:
        _repo.log_decision(
            lead_id,
            kind,
            {"allowed": decision.allowed, "reason": decision.reason,
             "details": decision.details},
        )
    except Exception:
        logging.exception("compliance_log write failed")


@app.post("/compliance/check-call", response_model=DecisionOut,
          dependencies=[Depends(require_token)])
def check_call(body: CheckVoiceIn) -> DecisionOut:
    d = check_voice(
        body.lead_id,
        repo=_repo,
        ai_disclosure_planned=body.ai_disclosure_planned,
        recording_notice_planned=body.recording_notice_planned,
    )
    _emit(body.lead_id, "check_voice", d)
    return DecisionOut(allowed=d.allowed, reason=d.reason, details=d.details)


@app.post("/compliance/check-sms", response_model=DecisionOut,
          dependencies=[Depends(require_token)])
def check_sms_endpoint(body: CheckSMSIn) -> DecisionOut:
    d = check_sms(body.lead_id, repo=_repo)
    _emit(body.lead_id, "check_sms", d)
    return DecisionOut(allowed=d.allowed, reason=d.reason, details=d.details)


@app.post("/compliance/check-dm", response_model=DecisionOut,
          dependencies=[Depends(require_token)])
def check_dm_endpoint(body: CheckDMIn) -> DecisionOut:
    d = check_ig_dm(body.lead_id, repo=_repo, message_tag=body.message_tag)
    _emit(body.lead_id, "check_dm", d)
    return DecisionOut(allowed=d.allowed, reason=d.reason, details=d.details)


@app.get("/health")
def health() -> dict:
    return {"ok": True}

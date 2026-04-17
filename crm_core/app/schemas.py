"""Pydantic request/response models for the CRM API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---- webhook envelopes (raw payloads are vendor-specific; we store them verbatim)

class WebhookAck(BaseModel):
    ok: bool = True
    event_id: UUID


# ---- internal event shape ----------------------------------------------------

class InternalEvent(BaseModel):
    """Shape used by the projector. Each external payload is normalised to this."""

    source: Literal["manychat", "cal", "retell", "stripe", "meta", "internal"]
    event_type: str
    idempotency_key: str | None = None
    payload: dict[str, Any]


# ---- read-api responses ------------------------------------------------------

class Lead(BaseModel):
    id: UUID
    ig_handle: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone_e164: str | None = None
    lifecycle_stage: str
    lead_tier: str | None = None
    lead_score: int | None = None
    source_content_id: UUID | None = None
    source_keyword: str | None = None
    created_at: datetime
    updated_at: datetime


class ContentAsset(BaseModel):
    id: UUID
    hook_text: str
    hook_framework: str | None = None
    cta_keyword: str | None = None
    status: str
    ig_media_id: str | None = None
    ig_permalink: str | None = None
    posted_at: datetime | None = None
    scheduled_for: datetime | None = None


class FunnelRow(BaseModel):
    day: str
    source_content_id: UUID | None = None
    new_leads: int
    dm_opened: int
    qualified: int
    booked: int
    showed: int
    closed_won: int
    revenue_usd: float


class HookRow(BaseModel):
    id: UUID
    hook_text: str
    hook_framework: str | None = None
    cta_keyword: str | None = None
    posted_at: datetime | None = None
    plays: int | None = None
    completion_rate: float | None = None
    comments: int | None = None
    leads_generated: int
    closes: int
    revenue_usd: float
    closes_per_100k_plays: float | None = None


class CloserRow(BaseModel):
    assigned_to: str
    total_appointments: int
    showed: int
    no_show: int
    rescheduled: int
    closed: int
    show_rate: float | None = None
    close_rate_of_shows: float | None = None
    avg_call_seconds: float | None = None


# ---- write-api inputs --------------------------------------------------------

class LeadCreate(BaseModel):
    ig_handle: str | None = None
    ig_user_id: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone_e164: str | None = None
    source_content_id: UUID | None = None
    source_keyword: str | None = None
    timezone: str | None = None
    region: str | None = None


class MessageCreate(BaseModel):
    conversation_id: UUID
    direction: Literal["inbound", "outbound"]
    sender_type: Literal["lead", "ai", "human", "system"]
    body: str
    raw_payload: dict[str, Any] | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


class ContentAssetCreate(BaseModel):
    hook_text: str
    hook_framework: str | None = None
    hook_batch_id: UUID | None = None
    cta_keyword: str | None = None
    scheduled_for: datetime | None = None
    r2_video_url: str | None = None


class HealthResponse(BaseModel):
    ok: bool
    db: bool
    version: str = Field(default="0.1.0")

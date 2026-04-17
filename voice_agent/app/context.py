"""Build the dynamic-variables bundle Retell needs to continue a DM thread."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeadContext:
    lead_id: str
    first_name: str | None
    phone_e164: str
    offer_name: str
    pain_point: str | None
    timeline: str
    dm_summary: str
    calendar_slot_iso: str | None = None


def build_retell_variables(ctx: LeadContext) -> dict[str, str]:
    """Map a LeadContext into the flat {str: str} shape Retell expects.

    Retell renders these with {{variable_name}} in the agent's system prompt
    and first-utterance, so the AI opens the call already knowing who it's
    talking to and what they discussed on IG.
    """
    return {
        "lead_id": ctx.lead_id,
        "prospect_first_name": (ctx.first_name or "there").strip() or "there",
        "offer_name": ctx.offer_name,
        "pain_point": (ctx.pain_point or "scaling your business").strip() or "scaling your business",
        "timeline": ctx.timeline or "unknown",
        "dm_summary": (ctx.dm_summary or "").strip()[:1500],
        "calendar_slot": ctx.calendar_slot_iso or "",
    }


def build_metadata(ctx: LeadContext) -> dict[str, str]:
    """Stays on the call record so the Retell webhook projector can
    attribute the call back to the right lead in the CRM."""
    return {"lead_id": ctx.lead_id, "offer_name": ctx.offer_name}

"""Qualification flow: history + new message -> structured decision."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .llm import AnthropicClient
from .prompts import render_system_prompt


@dataclass(frozen=True)
class OfferConfig:
    brand_voice_name: str
    offer_category: str
    offer_name: str
    offer_price: str
    offer_promise: str
    icp_description: str
    calendar_url: str


@dataclass
class QualifierResult:
    reply: str
    decision: str           # continue | book | disqualify | callback
    lead_score: int
    lead_tier: str          # gold | silver | bronze | disqualified
    pain: str | None
    timeline: str           # now | soon | later | unknown
    fit_signals: list[str]
    reasoning: str
    tokens_in: int
    tokens_out: int


_VALID_DECISIONS = {"continue", "book", "disqualify", "callback"}
_VALID_TIERS = {"gold", "silver", "bronze", "disqualified"}
_VALID_TIMELINES = {"now", "soon", "later", "unknown"}


def _coerce_json(text: str) -> dict:
    """Be forgiving — strip code fences, extract first {...} block."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped).rstrip("`").rstrip()
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in response: {text[:200]}")
    return json.loads(match.group(0))


def qualify_turn(
    *,
    llm: AnthropicClient,
    offer: OfferConfig,
    history: list[dict],   # [{"role": "user"|"assistant", "content": "..."}]
    new_message: str,
) -> QualifierResult:
    """Run one conversational turn through the qualifier."""
    if not new_message.strip():
        raise ValueError("new_message is empty")
    conversation = history + [{"role": "user", "content": new_message}]
    system = render_system_prompt(
        brand_voice_name=offer.brand_voice_name,
        offer_category=offer.offer_category,
        offer_name=offer.offer_name,
        offer_price=offer.offer_price,
        offer_promise=offer.offer_promise,
        icp_description=offer.icp_description,
        calendar_url=offer.calendar_url,
    )
    result = llm.messages(system=system, messages=conversation)

    data = _coerce_json(result.text)
    decision = data.get("decision", "continue")
    if decision not in _VALID_DECISIONS:
        decision = "continue"
    tier = data.get("lead_tier", "bronze")
    if tier not in _VALID_TIERS:
        tier = "bronze"
    timeline = data.get("timeline", "unknown")
    if timeline not in _VALID_TIMELINES:
        timeline = "unknown"

    score = int(data.get("lead_score", 50))
    score = max(0, min(100, score))

    return QualifierResult(
        reply=str(data.get("reply", "")).strip(),
        decision=decision,
        lead_score=score,
        lead_tier=tier,
        pain=data.get("pain") if data.get("pain") not in (None, "", "null") else None,
        timeline=timeline,
        fit_signals=[str(s) for s in (data.get("fit_signals") or [])],
        reasoning=str(data.get("reasoning", "")),
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )

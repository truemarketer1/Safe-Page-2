"""The check_* functions. Pure logic; no I/O except the repo injection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from .rules import (
    ALL_PARTY_RECORDING_STATES,
    REQUIRE_AI_DISCLOSURE_UPFRONT,
    rule_for,
)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str | None = None
    details: dict | None = None

    @classmethod
    def allow(cls, details: dict | None = None) -> "Decision":
        return cls(True, None, details)

    @classmethod
    def block(cls, reason: str, details: dict | None = None) -> "Decision":
        return cls(False, reason, details)


@dataclass
class Lead:
    id: str
    phone_e164: str | None = None
    region: str | None = None                     # US state abbr
    timezone: str = "America/New_York"
    consent_voice_ai: bool = False
    consent_recording: bool = False
    consent_sms: bool = False
    consent_dm: bool = True
    stop_sms_at: datetime | None = None
    stop_dm_at: datetime | None = None
    dnc_status: str | None = None                 # "clean" | "blocked"
    last_dm_inbound_at: datetime | None = None


class LeadRepo(Protocol):
    """Only what the gate needs. Implementations: Postgres in prod, fakes in tests."""

    def get_lead(self, lead_id: str) -> Lead | None: ...
    def calls_in_last_24h(self, lead_id: str) -> int: ...
    def log_decision(
        self, lead_id: str, kind: str, evidence: dict
    ) -> None: ...


def _within_quiet_hours(now: datetime, tz: str, start: int, end: int) -> bool:
    local = now.astimezone(ZoneInfo(tz))
    local_hour = local.time()
    return time(start, 0) <= local_hour < time(end, 0)


Channel = Literal["voice", "sms", "ig_dm"]


def check_voice(
    lead_id: str,
    *,
    repo: LeadRepo,
    now: datetime | None = None,
    is_first_dial_today: bool | None = None,
    ai_disclosure_planned: bool = True,
    recording_notice_planned: bool = True,
) -> Decision:
    now = now or datetime.now(ZoneInfo("UTC"))
    lead = repo.get_lead(lead_id)
    if not lead:
        return Decision.block("lead not found", {"lead_id": lead_id})

    if not lead.phone_e164:
        return Decision.block("no phone on file")

    if lead.dnc_status == "blocked":
        return Decision.block("DNC", {"dnc_status": lead.dnc_status})

    if not lead.consent_voice_ai:
        return Decision.block("no TCPA consent for AI voice")

    state = (lead.region or "").upper()

    if state in ALL_PARTY_RECORDING_STATES and not (
        recording_notice_planned and lead.consent_recording
    ):
        return Decision.block(
            "recording notice + consent required in all-party state",
            {"state": state},
        )

    if state in REQUIRE_AI_DISCLOSURE_UPFRONT and not ai_disclosure_planned:
        return Decision.block(
            "AI disclosure is mandatory up-front in this state",
            {"state": state},
        )

    rule = rule_for(state)

    if not _within_quiet_hours(now, lead.timezone, rule.quiet_hours_start, rule.quiet_hours_end):
        return Decision.block(
            "outside allowed calling hours",
            {
                "state": state,
                "tz": lead.timezone,
                "allowed": f"{rule.quiet_hours_start:02d}:00-{rule.quiet_hours_end:02d}:00 local",
            },
        )

    calls_today = repo.calls_in_last_24h(lead_id)
    if calls_today >= rule.daily_call_cap:
        return Decision.block(
            "daily call cap reached",
            {"cap": rule.daily_call_cap, "calls_today": calls_today},
        )

    return Decision.allow(
        {
            "state": state or "US",
            "cap": rule.daily_call_cap,
            "calls_today": calls_today,
            "all_party_recording": state in ALL_PARTY_RECORDING_STATES,
            "ai_disclosure_required_upfront": state in REQUIRE_AI_DISCLOSURE_UPFRONT,
        }
    )


def check_sms(lead_id: str, *, repo: LeadRepo, now: datetime | None = None) -> Decision:
    now = now or datetime.now(ZoneInfo("UTC"))
    lead = repo.get_lead(lead_id)
    if not lead:
        return Decision.block("lead not found")
    if not lead.phone_e164:
        return Decision.block("no phone on file")
    if lead.stop_sms_at is not None:
        return Decision.block("STOP opt-out on file", {"at": lead.stop_sms_at.isoformat()})
    if not lead.consent_sms:
        return Decision.block("no SMS consent on file")
    rule = rule_for(lead.region)
    if not _within_quiet_hours(now, lead.timezone, rule.quiet_hours_start, rule.quiet_hours_end):
        return Decision.block("outside allowed SMS hours")
    return Decision.allow()


def check_ig_dm(
    lead_id: str,
    *,
    repo: LeadRepo,
    now: datetime | None = None,
    message_tag: str | None = None,
) -> Decision:
    """Meta platform policy: outbound DM must be within 24h of last inbound
    engagement, unless sent with a valid message tag."""
    now = now or datetime.now(ZoneInfo("UTC"))
    lead = repo.get_lead(lead_id)
    if not lead:
        return Decision.block("lead not found")
    if lead.stop_dm_at is not None:
        return Decision.block("lead opted out of DMs")
    if not lead.consent_dm:
        return Decision.block("no DM consent")
    if lead.last_dm_inbound_at is not None:
        age = now - lead.last_dm_inbound_at
        if age <= timedelta(hours=24):
            return Decision.allow({"window": "open"})
    if message_tag:
        return Decision.allow({"window": "tag", "tag": message_tag})
    return Decision.block("outside 24h window and no message_tag provided")

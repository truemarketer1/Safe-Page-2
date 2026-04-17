from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.gate import (
    Lead,
    check_ig_dm,
    check_sms,
    check_voice,
)


class FakeRepo:
    def __init__(self, lead: Lead | None, calls_today: int = 0) -> None:
        self.lead = lead
        self.calls_today = calls_today
        self.logged: list[tuple[str, str, dict]] = []

    def get_lead(self, _lead_id):
        return self.lead

    def calls_in_last_24h(self, _lead_id):
        return self.calls_today

    def log_decision(self, lead_id, kind, evidence):
        self.logged.append((lead_id, kind, evidence))


def _lead(**over) -> Lead:
    defaults = dict(
        id="lead-1",
        phone_e164="+15551230001",
        region="NY",
        timezone="America/New_York",
        consent_voice_ai=True,
        consent_recording=False,
        consent_sms=True,
        consent_dm=True,
    )
    defaults.update(over)
    return Lead(**defaults)


# --- voice ---

def test_voice_allows_when_all_conditions_met():
    repo = FakeRepo(_lead())
    # Noon Eastern -> 17:00 UTC
    now = datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc)
    d = check_voice("lead-1", repo=repo, now=now)
    assert d.allowed, d.reason


def test_voice_blocks_without_tcpa_consent():
    repo = FakeRepo(_lead(consent_voice_ai=False))
    now = datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc)
    d = check_voice("lead-1", repo=repo, now=now)
    assert not d.allowed
    assert "TCPA" in d.reason


def test_voice_blocks_outside_quiet_hours():
    repo = FakeRepo(_lead())
    # 3AM Eastern -> 08:00 UTC... wait, no. 3AM NY in summer = 07:00 UTC.
    now = datetime(2026, 5, 1, 7, 0, tzinfo=timezone.utc)
    d = check_voice("lead-1", repo=repo, now=now)
    assert not d.allowed
    assert "hours" in d.reason


def test_voice_blocks_when_daily_cap_hit():
    repo = FakeRepo(_lead(), calls_today=3)
    now = datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc)
    d = check_voice("lead-1", repo=repo, now=now)
    assert not d.allowed
    assert "cap" in d.reason


def test_voice_blocks_if_dnc():
    repo = FakeRepo(_lead(dnc_status="blocked"))
    now = datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc)
    d = check_voice("lead-1", repo=repo, now=now)
    assert not d.allowed
    assert d.reason == "DNC"


def test_voice_all_party_state_requires_recording_consent():
    repo = FakeRepo(_lead(region="CA", consent_recording=False))
    now = datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc)  # noon PT
    d = check_voice("lead-1", repo=repo, now=now, recording_notice_planned=True)
    assert not d.allowed
    assert "all-party" in d.reason


def test_voice_all_party_state_allows_with_consent_and_notice():
    repo = FakeRepo(_lead(region="CA", consent_recording=True))
    now = datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc)
    d = check_voice("lead-1", repo=repo, now=now)
    assert d.allowed, d.reason
    assert d.details["all_party_recording"] is True


def test_voice_california_requires_ai_disclosure_upfront():
    repo = FakeRepo(_lead(region="CA", consent_recording=True))
    now = datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc)
    d = check_voice("lead-1", repo=repo, now=now, ai_disclosure_planned=False)
    assert not d.allowed
    assert "AI disclosure" in d.reason


def test_voice_blocks_without_phone():
    repo = FakeRepo(_lead(phone_e164=None))
    now = datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc)
    d = check_voice("lead-1", repo=repo, now=now)
    assert not d.allowed


# --- sms ---

def test_sms_blocks_after_stop_keyword():
    repo = FakeRepo(_lead(stop_sms_at=datetime.now(timezone.utc)))
    d = check_sms("lead-1", repo=repo)
    assert not d.allowed
    assert "STOP" in d.reason


def test_sms_blocks_outside_hours():
    repo = FakeRepo(_lead())
    # 03:00 local (America/New_York is -04:00 on May 1) -> 07:00 UTC
    now = datetime(2026, 5, 1, 7, 0, tzinfo=timezone.utc)
    d = check_sms("lead-1", repo=repo, now=now)
    assert not d.allowed


# --- dm ---

def test_dm_allows_within_24h_window():
    now = datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc)
    repo = FakeRepo(_lead(last_dm_inbound_at=now - timedelta(hours=2)))
    d = check_ig_dm("lead-1", repo=repo, now=now)
    assert d.allowed


def test_dm_blocks_outside_24h_without_tag():
    now = datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc)
    repo = FakeRepo(_lead(last_dm_inbound_at=now - timedelta(hours=48)))
    d = check_ig_dm("lead-1", repo=repo, now=now)
    assert not d.allowed


def test_dm_allows_outside_24h_with_tag():
    now = datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc)
    repo = FakeRepo(_lead(last_dm_inbound_at=now - timedelta(hours=48)))
    d = check_ig_dm("lead-1", repo=repo, now=now, message_tag="HUMAN_AGENT")
    assert d.allowed
    assert d.details["tag"] == "HUMAN_AGENT"


def test_dm_blocks_on_opt_out():
    repo = FakeRepo(_lead(stop_dm_at=datetime.now(timezone.utc)))
    d = check_ig_dm("lead-1", repo=repo)
    assert not d.allowed

import json
from unittest.mock import MagicMock

import pytest

from app.compliance import ComplianceClient, ComplianceDecision
from app.context import LeadContext, build_metadata, build_retell_variables
from app.orchestrator import handoff_to_ai_voice
from app.retell import RetellClient, RetellError
from app.stripe import StripeClient


def _ctx(**overrides) -> LeadContext:
    defaults = dict(
        lead_id="lead-1",
        first_name="Alex",
        phone_e164="+15557654321",
        offer_name="Scale to $30k",
        pain_point="inconsistent client flow",
        timeline="now",
        dm_summary="They mentioned the ad spend isn't converting.",
    )
    defaults.update(overrides)
    return LeadContext(**defaults)


def test_build_retell_variables_uses_defaults_for_nulls():
    ctx = _ctx(first_name=None, pain_point=None)
    vars = build_retell_variables(ctx)
    assert vars["prospect_first_name"] == "there"
    assert vars["pain_point"] == "scaling your business"
    assert vars["offer_name"] == "Scale to $30k"
    assert vars["lead_id"] == "lead-1"


def test_build_retell_variables_truncates_summary():
    ctx = _ctx(dm_summary="x" * 5000)
    vars = build_retell_variables(ctx)
    assert len(vars["dm_summary"]) == 1500


def test_build_metadata_includes_offer_and_lead():
    meta = build_metadata(_ctx())
    assert meta == {"lead_id": "lead-1", "offer_name": "Scale to $30k"}


# --- Retell client -----------------------------------------------------------

def _fake_resp(payload: dict):
    r = MagicMock()
    r.read.return_value = json.dumps(payload).encode()
    r.__enter__ = lambda self: self
    r.__exit__ = lambda *a: None
    return r


def test_retell_create_phone_call_parses_response():
    opener = MagicMock()
    opener.open.return_value = _fake_resp({
        "call_id": "rc-123", "agent_id": "ag-1", "call_status": "queued",
    })
    client = RetellClient("k", opener=opener)
    call = client.create_phone_call(
        from_number="+15550000001", to_number="+15557654321",
        agent_id="ag-1",
        dynamic_variables={"prospect_first_name": "Alex"},
        metadata={"lead_id": "lead-1"},
    )
    assert call.call_id == "rc-123"
    assert call.status == "queued"


def test_retell_missing_call_id_raises():
    opener = MagicMock()
    opener.open.return_value = _fake_resp({})
    client = RetellClient("k", opener=opener)
    with pytest.raises(RetellError):
        client.create_phone_call(
            from_number="+1", to_number="+1", agent_id="ag-1",
        )


# --- Stripe client -----------------------------------------------------------

def test_stripe_create_payment_link_posts_form_with_metadata():
    opener = MagicMock()
    opener.open.return_value = _fake_resp({
        "id": "plink_1", "url": "https://buy.stripe.com/plink_1",
    })
    client = StripeClient("sk_test", opener=opener)
    result = client.create_payment_link(
        price_id="price_1", lead_id="lead-1", call_id="rc-1",
    )
    assert result["id"] == "plink_1"
    req = opener.open.call_args[0][0]
    assert req.method == "POST"
    body = req.data.decode()
    assert "price_1" in body
    assert "lead-1" in body
    assert "rc-1" in body


# --- Orchestrator ------------------------------------------------------------

class FakeCompliance:
    def __init__(self, decision: ComplianceDecision) -> None:
        self.decision = decision

    def check_call(self, lead_id, **_):
        return self.decision


def test_orchestrator_blocks_when_compliance_denies():
    blocked = ComplianceDecision(allowed=False, reason="DNC", details=None)
    retell = MagicMock()
    outcome = handoff_to_ai_voice(
        _ctx(),
        retell=retell,
        retell_agent_id="ag-1",
        retell_from_number="+15550000001",
        compliance=FakeCompliance(blocked),
    )
    assert outcome.call is None
    assert outcome.compliance.reason == "DNC"
    retell.create_phone_call.assert_not_called()


def test_orchestrator_creates_call_when_allowed():
    allowed = ComplianceDecision(allowed=True, reason=None, details={"state": "NY"})
    retell = MagicMock()
    retell.create_phone_call.return_value = MagicMock(
        call_id="rc-xyz", agent_id="ag-1", status="queued",
    )
    outcome = handoff_to_ai_voice(
        _ctx(),
        retell=retell,
        retell_agent_id="ag-1",
        retell_from_number="+15550000001",
        compliance=FakeCompliance(allowed),
    )
    assert outcome.call.call_id == "rc-xyz"
    retell.create_phone_call.assert_called_once()
    # Dynamic variables were passed.
    call_kwargs = retell.create_phone_call.call_args.kwargs
    assert call_kwargs["dynamic_variables"]["prospect_first_name"] == "Alex"
    assert call_kwargs["metadata"]["lead_id"] == "lead-1"

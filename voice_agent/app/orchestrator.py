"""The handoff: Cal.com booking -> compliance check -> Retell dial.

This is the single function that Cal.com's webhook (via the CRM) or a
direct HTTP call triggers to start an AI voice call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .compliance import ComplianceClient, ComplianceDecision
from .context import LeadContext, build_metadata, build_retell_variables
from .retell import RetellCall, RetellClient

log = logging.getLogger("voice_agent.orchestrator")


@dataclass
class HandoffOutcome:
    call: RetellCall | None
    compliance: ComplianceDecision


def handoff_to_ai_voice(
    ctx: LeadContext,
    *,
    retell: RetellClient,
    retell_agent_id: str,
    retell_from_number: str,
    compliance: ComplianceClient,
) -> HandoffOutcome:
    """Pre-dial compliance check, then create the Retell call with full context."""
    decision = compliance.check_call(ctx.lead_id)
    if not decision.allowed:
        log.warning("blocked by compliance: lead=%s reason=%s", ctx.lead_id, decision.reason)
        return HandoffOutcome(call=None, compliance=decision)

    call = retell.create_phone_call(
        from_number=retell_from_number,
        to_number=ctx.phone_e164,
        agent_id=retell_agent_id,
        dynamic_variables=build_retell_variables(ctx),
        metadata=build_metadata(ctx),
    )
    return HandoffOutcome(call=call, compliance=decision)

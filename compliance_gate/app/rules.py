"""TCPA + state rule tables.

Sources:
  - FCC Feb 2024 Declaratory Ruling (FCC 24-17): AI voices = "artificial or
    prerecorded" under TCPA; prior express written consent required.
  - FL mini-TCPA (rev. 2023/2024), OK OTSA, MD MTCPA: ≤3 sales calls per 24h
    same subject, 8AM-8PM local time, private right of action.
  - WA HB 1051 (2023/2024): damages raised from $100 to $1,000 per violation.
  - CA AB 2905 (eff. 2025-01-01): AI voice must be disclosed up front or $500/call.
  - Call recording: 12 all-party states = CA, CT, DE, FL, IL, MD, MA, MT, NV,
    NH, PA, WA. 38 one-party states.

These are minimums. Always check current law — laws change. Quiet hours
default to 8AM-8PM local (federal TCPA minimum).
"""

from __future__ import annotations

from dataclasses import dataclass


ALL_PARTY_RECORDING_STATES: frozenset[str] = frozenset({
    "CA", "CT", "DE", "FL", "IL", "MD", "MA", "MT", "NV", "NH", "PA", "WA",
})


REQUIRE_AI_DISCLOSURE_UPFRONT: frozenset[str] = frozenset({
    # Explicit statute requires AI-voice disclosure at the start of the call.
    "CA",
})


@dataclass(frozen=True)
class StateRule:
    state: str
    daily_call_cap: int             # per lead per 24h
    quiet_hours_start: int           # hour-of-day, local
    quiet_hours_end: int             # exclusive upper bound
    requires_express_written: bool   # strict state mini-TCPA
    per_violation_damages_usd: int   # floor damages per proven violation


# Federal TCPA floor (applies everywhere unless state is stricter).
FEDERAL_FLOOR = StateRule(
    state="US",
    daily_call_cap=3,
    quiet_hours_start=8,
    quiet_hours_end=20,
    requires_express_written=True,
    per_violation_damages_usd=500,
)


STATE_RULES: dict[str, StateRule] = {
    "FL": StateRule("FL", 3, 8, 20, True, 500),
    "OK": StateRule("OK", 3, 8, 20, True, 500),
    "MD": StateRule("MD", 3, 8, 20, True, 500),
    "WA": StateRule("WA", 3, 8, 20, True, 1000),
    "CA": StateRule("CA", 3, 8, 20, True, 500),
}


def rule_for(state: str | None) -> StateRule:
    if state and state.upper() in STATE_RULES:
        return STATE_RULES[state.upper()]
    return FEDERAL_FLOOR

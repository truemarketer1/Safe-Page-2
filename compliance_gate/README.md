# Compliance Gate

The single checkpoint every outbound AI comms action (voice call, SMS, IG DM)
must pass through. Wrong here = TCPA class-action. Right here = the whole
ecosystem stays legal.

## What it enforces

- **FCC Feb 2024 ruling** (FCC 24-17): AI-generated voices are "artificial or
  prerecorded" under TCPA. Prior express written consent required for every
  outbound AI call. $500-$1,500 per violation.
- **State mini-TCPAs**: FL / OK / MD (≤3 sales calls per 24h, 8am-8pm local),
  WA ($1000/call), CA AB 2905 (AI voice must be disclosed up front or $500/call).
- **Recording consent**: All-party states (CA, CT, DE, FL, IL, MD, MA, MT, NV,
  NH, PA, WA) require recording notice + lead consent.
- **DNC status**: block on `dnc_status = 'blocked'`.
- **Quiet hours**: 8am-8pm local (federal TCPA floor; stricter states override).
- **Per-lead daily call cap**: 3/24h default (federal + FL/OK/MD/WA/CA match).
- **SMS STOP opt-out**: instant block once `stop_sms_at` is set.
- **Meta 24h DM window**: outbound DMs only allowed within 24h of last inbound
  interaction, or with a valid `message_tag`.

## API

```
POST /compliance/check-call  { "lead_id": "...", "ai_disclosure_planned": true,
                               "recording_notice_planned": true }
POST /compliance/check-sms   { "lead_id": "..." }
POST /compliance/check-dm    { "lead_id": "...", "message_tag": "HUMAN_AGENT" }
GET  /health
```

All three return:
```json
{ "allowed": true|false, "reason": "DNC"|null,
  "details": {"state": "CA", "cap": 3, "calls_today": 1, ...} }
```

Every decision (allowed or blocked) writes a `compliance_log` row in the CRM
core DB. That's your audit trail if a TCPA suit ever lands.

## Usage pattern

Before every Retell outbound call, the voice agent hits
`POST /compliance/check-call` first. If `allowed: false`, the dial is skipped
and the reason is logged. Same pattern for SMS (Twilio) and DM (ManyChat).

## Tests

```bash
cd compliance_gate
pip install -e .[dev]
python -m pytest
```

15 tests covering quiet hours, state-specific rules (CA recording + AI
disclosure), daily caps, DNC, STOP/opt-out, and the Meta 24h DM window.

## Deploy

Add to `infra/docker-compose.yml`:

```yaml
  compliance_gate:
    build:
      context: ..
      dockerfile: infra/Dockerfile.compliance_gate
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/crm
      COMPLIANCE_API_TOKEN: ${COMPLIANCE_API_TOKEN:-dev-insecure-token}
    ports: ["8001:8000"]
    depends_on: [postgres]
```

## Disclaimer

This encodes minimum rules as of the 2025/2026 research. Laws change. Consult
a TCPA-savvy attorney before running outbound AI voice to real leads,
especially across multiple states.

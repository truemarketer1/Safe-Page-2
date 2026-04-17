# Voice Agent

The handoff layer that takes a booked Cal.com appointment (or a warm-callback
request from the DM qualifier) and runs the actual AI sales call via Retell,
with mid-call Stripe + Twilio payment collection.

## Pipeline

```
Cal.com BOOKING_CREATED webhook -> CRM -> POST /voice/handoff
                                              │
                       ┌──────────────────────┼──────────────────────┐
                       ▼                      ▼                      ▼
               Compliance check         Retell create-call    CRM events (auto)
           (TCPA / DNC / state /         with dynamic vars
            quiet hours / cap)          (prospect name, DM
                                        summary, pain point)
                                              │
                                              ▼
                                     AI calls the prospect.
                                     Mid-call, AI tool-call →
                                              │
                                              ▼
                                     POST /voice/payment-link
                                              │
                      ┌───────────────────────┼───────────────────────┐
                      ▼                       ▼                       ▼
            Stripe Payment Link       Twilio SMS sends          Stripe webhook
                 created                  link to prospect      -> CRM -> closed_won
```

## API

```
POST /voice/handoff       { lead_id, first_name, phone_e164, offer_name,
                            pain_point, timeline, dm_summary,
                            calendar_slot_iso? }
POST /voice/payment-link  { lead_id, phone_e164, price_id, call_id? }
GET  /health
```

`/voice/handoff` returns `{ allowed, call_id | null, reason, details }`. If
compliance denies, `call_id` is null and the reason/details describe why
(DNC, no consent, quiet hours, daily cap, state rule).

## Retell agent

The prompt template is in `prompts/agent_system_prompt.md`. Paste it into
Retell's "System prompt" field when you create the agent, then configure
these tool-calls:

- `send_payment_link` → POSTs to this service's `/voice/payment-link`.
- `book_human_followup` → POSTs to your Cal.com booking API for a human closer.
- `reschedule` → POSTs to Cal.com reschedule endpoint.

## Config (env)

| Var | Purpose |
|---|---|
| `RETELL_API_KEY` | Retell API key |
| `RETELL_AGENT_ID` | Your configured agent id |
| `RETELL_FROM_NUMBER` | E.164 number Retell owns |
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` | SMS delivery |
| `COMPLIANCE_URL` / `COMPLIANCE_API_TOKEN` | compliance_gate address + bearer |
| `VOICE_AGENT_TOKEN` | bearer for this service's callers |

## Tests

```bash
cd voice_agent
pip install -e .[dev]
python -m pytest
```

8 pytest cases: Retell call creation + response parsing, Stripe Payment Link
metadata, context-variable truncation + null defaults, orchestrator blocks
when compliance denies, orchestrator passes variables through on allow.

## Deploy

Add to `infra/docker-compose.yml`:

```yaml
  voice_agent:
    build:
      context: ..
      dockerfile: infra/Dockerfile.voice_agent
    environment:
      RETELL_API_KEY: ${RETELL_API_KEY}
      RETELL_AGENT_ID: ${RETELL_AGENT_ID}
      # ... etc
    depends_on: [compliance_gate]
    ports: ["8003:8000"]
```

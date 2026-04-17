# DM Engine

FastAPI qualifier that takes an IG DM history + new inbound message and
returns: the next reply to send, a lead score, a lifecycle decision
(continue/book/disqualify/callback), pain/timeline/fit signals.

## Why a separate service

ManyChat's built-in AI is a black box — you can't see the prompt, can't swap
models, can't own the scoring rubric. This service gives you:

- full control of the system prompt (`app/prompts.py`)
- deterministic structured-output parsing (`app/qualifier.py`)
- cheap: Claude Sonnet runs a 20-message qualification at ~$0.01-0.02
- testable: zero network calls in the pytest suite

## Flow

```
IG comment keyword
    ↓
ManyChat opener message ("here's the template")
    ↓  prospect replies
ManyChat -> POST /dm/qualify  { lead_id, text, history: [...] }
    ↓
  this service:
    - Claude Sonnet 4.6 call with the offer-specific system prompt
    - returns { reply, decision, lead_score, lead_tier, pain, timeline, ... }
    ↓
ManyChat sends `reply` to the prospect; flow branches on `decision`:
    continue    -> loop back to "prospect replies"
    book        -> calendar link already embedded in reply; Cal.com takes over
    callback    -> trigger voice_agent service (Phase 5)
    disqualify  -> nurture tag, no more pushes
```

The conversation rows themselves are written to the CRM via the
`/webhook/manychat` endpoint (already built in Phase 1). This service only
produces the decision + next reply.

## API

```
POST /dm/qualify   { lead_id, text, history: [{role, content}, ...] }
GET  /health
```

## Config (env)

| Var | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | Claude API key |
| `ANTHROPIC_MODEL` | no | defaults to `claude-sonnet-4-6` |
| `DM_ENGINE_TOKEN` | yes for prod | bearer auth for ManyChat webhooks |
| `OFFER_BRAND_NAME` | yes | first-person brand voice |
| `OFFER_CATEGORY` | yes | "business coaching", "fitness", etc. |
| `OFFER_NAME` | yes | product name |
| `OFFER_PRICE` | yes | "$2,500" |
| `OFFER_PROMISE` | yes | one-line transformation promise |
| `ICP_DESCRIPTION` | yes | ideal-customer profile |
| `CALENDAR_URL` | yes | Cal.com booking link |

## Tests

```bash
cd dm_engine
pip install -e .[dev]
python -m pytest
```

5 pytest cases: JSON parsing (strict + forgiving with code fences), enum
safety nets, input guards.

## Deploy

Add to `infra/docker-compose.yml`:

```yaml
  dm_engine:
    build:
      context: ..
      dockerfile: infra/Dockerfile.dm_engine
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      DM_ENGINE_TOKEN: ${DM_ENGINE_TOKEN}
      OFFER_BRAND_NAME: ${OFFER_BRAND_NAME}
      # ... all offer env vars
    ports: ["8002:8000"]
```

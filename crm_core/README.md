# CRM Core

FastAPI service that is the hub of the autonomous IG lead-gen ecosystem.

## What it does

1. **Ingests webhooks** from ManyChat (IG DMs), Cal.com (bookings), Retell
   (AI voice calls), Stripe (payments), and Meta (IG Insights snapshots).
2. **Verifies signatures** for every inbound request (Stripe HMAC, Meta SHA256,
   per-provider shared secrets).
3. **Stores a raw, append-only `events` row** for every webhook — nothing is
   mutated, so the domain tables can always be rebuilt from event history.
4. **Projects events** into domain tables (`leads`, `conversations`, `messages`,
   `appointments`, `calls`, `payments`). Projectors are idempotent and
   lifecycle-stage-safe (never regress a lead's state).
5. **Serves a read API** for the Next.js dashboard: funnel per day, per-hook
   leaderboard, AI-vs-human closer performance, individual lead/content detail.

## Run it

```bash
# 1. Spin up Postgres + the API
docker-compose -f infra/docker-compose.yml up -d

# 2. Apply migrations
psql $DATABASE_URL -f infra/migrations/001_init.sql
psql $DATABASE_URL -f infra/migrations/002_views.sql

# 3. Hit it
curl http://localhost:8000/api/health
curl -H "Authorization: Bearer $API_AUTH_TOKEN" \
     http://localhost:8000/api/metrics/funnel?since_days=7
```

Local dev without docker:

```bash
cd crm_core
pip install -e .[dev]
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crm
export API_AUTH_TOKEN=dev-token
uvicorn app.main:app --reload
```

## Tests

```bash
cd crm_core
python -m pytest
```

20 tests across signing, projectors (idempotency, lifecycle monotonicity,
lead upsert precedence), and webhook routing. No live Postgres required —
projectors run against an in-memory `FakeCursor`.

## Webhook endpoints

| Endpoint | Source | Signature header | Notes |
|---|---|---|---|
| `POST /webhook/stripe` | Stripe | `Stripe-Signature` | HMAC-SHA256 of `{ts}.{body}` |
| `POST /webhook/meta` | Meta/IG | `X-Hub-Signature-256` | HMAC-SHA256 of body |
| `GET  /webhook/meta` | Meta verify | — | Handshake during app setup |
| `POST /webhook/cal` | Cal.com | `X-Cal-Signature-256` | Shared secret |
| `POST /webhook/retell` | Retell AI | `X-Retell-Signature` | Shared secret |
| `POST /webhook/manychat` | ManyChat | `X-Manychat-Secret` | Shared secret |

## Read endpoints (Bearer auth)

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness + DB check |
| `GET /api/leads?stage=booked&limit=100` | Leads by lifecycle stage |
| `GET /api/leads/{id}` | One lead |
| `GET /api/content/{id}` | One content asset |
| `GET /api/metrics/funnel?since_days=30` | Daily funnel rows |
| `GET /api/metrics/hooks?order=revenue_usd` | Hook leaderboard |
| `GET /api/metrics/closers` | AI vs human closer performance |
| `POST /api/admin/refresh-views` | Refresh materialized views (run from cron) |

## Event projection contract

Every webhook receiver normalises into `{source, event_type, payload}` and
inserts into `events`. A background task then calls `project_event(id)`. The
projector dispatches to `app/projections/{source}.py`, which advances the
domain tables and stamps the event with `processed_at`.

Replaying an event is safe: the projectors check existing rows and use
`ON CONFLICT ... DO UPDATE` so end state is independent of replay count.

## What's next

Phase 2 (compliance gate) will plug into this service as a pre-dial check:
every outbound voice/SMS action goes through `POST /compliance/check-call`
before it fires, and a row lands in `compliance_log` for audit.

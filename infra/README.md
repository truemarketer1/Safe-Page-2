# Infra

Self-hostable runtime for the CRM core + the rest of the ecosystem as we build it.

## Files

| Path | Purpose |
|---|---|
| `migrations/001_init.sql` | Core schema — leads, conversations, messages, appointments, calls, payments, events, compliance_log |
| `migrations/002_views.sql` | Dashboard materialized views (funnel_daily, hook_leaderboard, closer_performance) |
| `Dockerfile.crm_core` | Python 3.11 image for the FastAPI service |
| `docker-compose.yml` | Postgres 16 + crm_core, dev-ready |

## Run locally

```bash
# 1. Start containers
docker-compose up -d

# 2. Apply migrations (first run only)
docker-compose exec postgres psql -U postgres -d crm -f /migrations/001_init.sql
docker-compose exec postgres psql -U postgres -d crm -f /migrations/002_views.sql

# 3. Hit it
curl http://localhost:8000/api/health
```

Environment variables (all optional except `DATABASE_URL` and
`API_AUTH_TOKEN`) are listed in `crm_core/app/config.py`. Create a `.env`
file at repo root and docker-compose will pick it up.

## Production (Supabase + single VPS)

1. Create a Supabase project, run `001_init.sql` + `002_views.sql` in the SQL
   editor.
2. Spin up a $10/mo VPS (Hetzner CX11, Fly.io shared CPU, etc.). Install
   Docker.
3. Copy this repo, set real secrets in `.env`, run `docker-compose up -d`
   against `DATABASE_URL` pointing at Supabase.
4. Point a subdomain at the VPS and terminate TLS via Caddy or Cloudflare
   Tunnel. Every vendor webhook dashboard gets `https://crm.yourdomain/webhook/{source}`.
5. Add a cron on the VPS that hits `POST /api/admin/refresh-views` every 5
   minutes so the dashboard stays fresh.

## Next services to add

As we build the remaining phases, each lands as its own directory at the repo
root with its own Dockerfile, and this compose file gets one extra service:

- `compliance_gate` (Phase 2)
- `content_pipeline` (Phase 3 — extends the existing `reels_generator`)
- `dm_engine` (Phase 4)
- `voice_agent` (Phase 5)
- `optimizer` (Phase 6)
- `dashboard` (Next.js UI)

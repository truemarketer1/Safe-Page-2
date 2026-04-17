# Dashboard

Next.js 15 + Tremor dashboard for the CRM core. Reads the CRM's `/api/metrics/*`
endpoints on the server (bearer token stays server-side).

## Pages

- `/` — last-30-day totals (new leads, booked, closed, revenue, show rate).
- `/funnel` — daily funnel rows.
- `/hooks` — hook leaderboard sorted by revenue.
- `/closers` — AI vs human closer performance.
- `/compliance` — placeholder pointing at compliance_log.

## Run locally

```bash
cd dashboard
npm install
cp .env.example .env.local  # then fill in CRM_BASE_URL + CRM_API_TOKEN
npm run dev
```

## Env

- `CRM_BASE_URL` — e.g. `http://localhost:8000`
- `CRM_API_TOKEN` — same token set in crm_core's `API_AUTH_TOKEN`

## Deploy

Easiest: Vercel (free tier). Set env vars in the project settings, point it
at this `dashboard/` subdirectory, done.

Self-host: build and serve with `npm run build && npm start`, or add a
Dockerfile + compose service (follow the pattern in `infra/Dockerfile.crm_core`).

## Next

- Wire `/compliance` to a new `GET /api/compliance/recent` endpoint.
- Add a `/leads/[id]` detail page showing: timeline (DM + calls + payments),
  compliance decisions, transcript viewer.
- Add realtime (Supabase subscriptions) so closed-won events pop in without refresh.

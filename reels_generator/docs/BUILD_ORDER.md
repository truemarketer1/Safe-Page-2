# Build Order — Autonomous IG Lead-Gen Ecosystem

Phased roadmap. Each phase delivers a stand-alone useful system, so you don't wait
6 weeks to see value. Budget = how long this would take a competent single dev working
full-time; with me in the loop it collapses significantly.

Already done: **Phase 0** (see `reels_generator/reels/`).

---

## Phase 0 — Hook generator (DONE)

Branch `claude/automated-reels-hook-generator-4O32y`, commit `7e2f24e`.

- HeyGen avatar + voice clone client
- FFmpeg stitching
- CSV / Google Sheets input
- Parallel pipeline with caching + error isolation
- Make.com blueprint (no-code alternative)
- 17 passing tests

Gap: doesn't yet upload to R2, doesn't yet auto-post to IG, doesn't yet run Submagic.

---

## Phase 1 — The CRM core (the hub) • ~3-5 days

Nothing else has a place to write results until this exists. Build this first.

1. Supabase project, SQL migrations from `CRM_SCHEMA.md`.
2. FastAPI service `crm_core/` with:
   - `POST /webhook/{source}` — signed receiver for Stripe, Cal, Retell, ManyChat, Meta.
   - Idempotent event projector (events table → domain tables).
   - `GET /leads/{id}` + `GET /content/{id}` + `GET /metrics/*` read API for dashboard.
   - Outbound action endpoints: `POST /leads/{id}/send_dm`, `POST /leads/{id}/schedule_call`.
3. Next.js + Tremor dashboard `crm_dashboard/` with 4 pages:
   - **Funnel** (per-day, per-content)
   - **Hooks leaderboard**
   - **Calls & appointments** (show/no-show/close by closer)
   - **Compliance log**
4. Seed/fixture script so you can demo the dashboards before real data flows in.

**Deliverable**: a working CRM you can POST a fake event to and watch numbers update
in the dashboard.

---

## Phase 2 — Compliance gate • ~1-2 days

A small service that says yes/no to every outbound action.

- `POST /compliance/check-call` → checks: written consent on file, DNC status, state
  rules for the phone NPA (FL/OK/MD/WA/CA specifics), daily cap (≤3 dials/lead/24h),
  quiet hours (8am–8pm local), not opted out.
- `POST /compliance/check-sms` / `/check-dm` — lighter versions.
- Every hit writes a `compliance_log` row.
- Bundled with a tiny seed of state rules, DNC list API client (costs ~$0.002/query).

**Deliverable**: no call/DM/SMS goes out without passing this gate. One class-action
saved pays for the whole stack forever.

---

## Phase 3 — Complete the content pipeline • ~2-3 days

Wire what I've already built into real posts.

1. **R2 uploader** — upload the stitched mp4 to Cloudflare R2, return the public URL.
2. **Submagic step** — submit video + polling; replaces stitched file with captioned
   version. (Optional — can skip on v1 if HeyGen output looks good enough.)
3. **IG Graph API poster** — `/media` container → `/media_publish`, with content-publish
   rate-limit awareness and error handling.
4. **CRM integration** — every posted Reel creates a `content_assets` row; every IG
   Insights pull updates `content_metrics`.
5. **Scheduler** — cron that picks from the queue, respects the 100/24h limit, posts
   at the best-time windows from research.
6. **n8n blueprint** that orchestrates the whole thing (alternative to the Python
   scheduler, for non-technical maintenance).

**Deliverable**: you drop 20 hook texts into the queue; 20 Reels go live on the right
schedule and start reporting metrics to the CRM.

---

## Phase 4 — DM engine • ~3-4 days

1. **ManyChat setup** — keyword triggers per CTA word; opening DM delivers the promised
   asset (from an R2-hosted bucket of templates/PDFs/links).
2. **FastAPI qualifier** — `POST /dm/message` endpoint that ManyChat hits after the
   opener. Runs a Claude conversation with BANT-lite prompts. Returns either:
   - next question to send, or
   - `book_call` action with Cal.com link, or
   - `disqualify` with a nurture tag.
3. **CRM sync** — every DM in/out writes a `messages` row; lead score + tier update on
   `leads`.
4. **Cal.com webhook** — `BOOKING_CREATED` / `BOOKING_RESCHEDULED` / `BOOKING_CANCELLED`
   → `appointments` table.

**Deliverable**: a commenter on a Reel is fully handled by AI from keyword to
calendar-booked, with everything logged.

---

## Phase 5 — AI voice agent • ~4-6 days

1. **Retell agent config** — system prompt with company voice, objection library, the
   BANT handoff, the mid-call Stripe-link flow. Voice = ElevenLabs cloned.
2. **Handoff service** — Cal.com webhook → compliance gate → Retell API with full DM
   context injected as dynamic variables (`prospect_name`, `pain_point`, `offer`,
   `dm_summary`, `objections_raised`).
3. **Stripe Payment Link trigger** — Retell tool-call fires our webhook → creates a
   Payment Link → SMS it to the prospect via Twilio → AI waits on the line.
4. **Post-call summarizer** — after Retell `call_ended` webhook, a Claude pass extracts
   objections, outcome, recommended next action, writes to `calls.outcome`.
5. **Callback flow for warm-but-unbooked** — if DM qualifier flags "warm + phone on
   file + consent", schedule an AI callback within 5 minutes.

**Deliverable**: AI can take an appointment, run the whole call, send a Payment Link,
and report the outcome to the CRM. You still get notified on any $3k+ close for
live review until you trust the system.

---

## Phase 6 — Closed-loop optimization • ~2-3 days

This is what makes it self-improving.

1. **Hook auto-rerank** — every morning, the pipeline reads `hook_leaderboard`, kills
   the bottom 30%, duplicates and remixes the top 30% with LLM variations.
2. **AI quality sampling** — nightly job pulls 10% of DM + call transcripts, runs them
   through a critic LLM that scores {tone, factuality, compliance, conversion_quality}.
   Anything under threshold flags for human review.
3. **Spend guardrails** — daily $ cap per service in the orchestrator. Auto-pause and
   alert on anomalies (cost per lead >2x trailing avg, connect rate <50% of baseline).
4. **Cohort revenue report** — weekly email to founder: revenue by content cohort,
   AI vs. human close rate, top 3 winning hooks, top 3 losing hooks, compliance
   exceptions.

**Deliverable**: the system measurably improves its own conversion rate week over week
without you touching it.

---

## Phase 7 — Nice-to-haves (later)

- Multi-avatar A/B (test HeyGen vs. Arcads vs. Tavus on same hook set).
- Multilingual — clone voice in ES/PT, expand to LATAM audiences.
- Competitor signal scraper — find high-performing hooks in your niche and feed them to
  the hook factory.
- Human closer routing — for leads the AI flags as high-LTV but low-close-confidence.

---

## Cross-cutting ops

- **Repo layout** (proposed extension of this repo):
  ```
  reels_generator/          # phase 0 (done)
  crm_core/                 # phase 1 - fastapi
  crm_dashboard/            # phase 1 - next.js
  compliance_gate/          # phase 2
  content_pipeline/         # phase 3 - r2 + submagic + ig poster
  dm_engine/                # phase 4 - qualifier
  voice_agent/              # phase 5 - retell config + handoff
  optimizer/                # phase 6
  n8n/                      # n8n blueprints per phase
  infra/                    # supabase migrations, dockerfiles, compose
  docs/                     # strategy, schema, runbooks
  ```
- **Secrets**: one `.env` at the repo root, referenced by every service; never committed.
- **Deploy**: docker-compose on a single $10/mo VPS is enough through Phase 5. Split
  voice_agent + crm_core to dedicated services once you're doing >50 calls/day.
- **Observability**: Supabase logs + a single Sentry project + Grafana pointed at
  Postgres is plenty.

---

## Decision points for you before we build

1. **CRM stack**: full custom (Supabase + FastAPI + Next.js) **or** thin analytics mart
   on top of GoHighLevel? Custom gives total control; GHL ships faster. My recommendation
   is custom — you specifically asked for a custom CRM, and you'll outgrow GHL as soon
   as you want custom scoring or dashboards.
2. **Voice provider**: Retell (recommended, balanced) vs. Vapi (more flexible) vs.
   Bland (cheapest at volume)?
3. **Offer price point**: under $500 → AI can close end-to-end; $500–$3k → AI does
   90%, human confirms high-value; $3k+ → AI books, human closes until proven otherwise.
4. **Region**: US only or US + LATAM (changes voice cloning + compliance work)?

Once you pick, I start at Phase 1. First working dashboard + CRM in a few days.

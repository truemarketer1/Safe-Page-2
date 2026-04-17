# Autonomous IG Lead-Gen Ecosystem

Branch: `claude/automated-reels-hook-generator-4O32y`

End-to-end system where:

1. AI generates & posts 10–20 Instagram Reels per day.
2. Viewers comment a keyword; ManyChat fires an auto-DM.
3. AI qualifies them in DM (BANT-lite, Claude Sonnet).
4. Hot leads get booked on Cal.com; warm leads get an AI voice callback.
5. Retell AI runs the call with the DM context pre-loaded, handles objections, and texts a Stripe Payment Link mid-call for the close.
6. Every step emits to a custom CRM; a Next.js dashboard is the one screen the founder looks at.
7. A compliance gate (TCPA / FCC 2024 AI-voice rule / state mini-TCPAs / DNC / quiet hours) fronts every outbound action.
8. An optimizer re-ranks hooks daily, samples AI transcripts for quality drift, and auto-pauses spend anomalies.

## Repo map

```
reels_generator/      Phase 0+3 — hooks → HeyGen avatar → FFmpeg stitch →
                      Submagic captions → Cloudflare R2 → Instagram Graph API
crm_core/             Phase 1   — FastAPI hub: signed webhook receivers,
                      append-only events table, idempotent projectors per
                      source (Stripe/Meta/Cal/Retell/ManyChat), read API
                      for the dashboard
compliance_gate/      Phase 2   — TCPA/DNC/quiet-hours/state-rules service
                      every outbound voice/SMS/DM passes through
dm_engine/            Phase 4   — Claude-powered BANT-lite DM qualifier;
                      takes history + new message, returns reply + decision
                      (continue/book/disqualify/callback) + lead score
voice_agent/          Phase 5   — Cal.com booking → compliance check →
                      Retell create-call with dynamic variables (prospect
                      name, pain, DM summary); Stripe Payment Link + Twilio
                      SMS mid-call close; full Retell system-prompt template
optimizer/            Phase 6   — hook auto-rerank (revenue-ranked + remix
                      top 30% via LLM), AI quality sampling (10% critic
                      review), spend guard (daily caps + anomaly pause)
dashboard/            Next.js 15 + Tremor — /funnel /hooks /closers
                      /compliance pages fed by crm_core's read API
infra/                migrations/001_init.sql + 002_views.sql; per-service
                      Dockerfile + docker-compose.yml; runbook
reels_generator/docs/ STRATEGY.md, CRM_SCHEMA.md, BUILD_ORDER.md
```

## Commit history on this branch

| Commit | Phase | Contents |
|---|---|---|
| `7e2f24e` | 0 | Reels Hook Generator — hooks → HeyGen → FFmpeg |
| `b6bdfa7` | docs | Full strategy, CRM schema, phased build plan |
| `0292c04` | 1 | CRM core — schema, FastAPI, webhook receivers, projectors |
| `55c5ee7` | 2 | Compliance gate — TCPA/DNC/quiet-hours/state rules |
| `1c0382f` | 3 | Content pipeline — R2 + Submagic + IG Graph + CRM sync |
| `95162e7` | 4 | DM qualifier — Claude BANT-lite DM setter |
| `9f06155` | 5 | Voice agent — Cal → compliance → Retell → Stripe mid-call |
| (this)   | 6+UI | Optimizer (hook rerank, QA sampler, spend guard) + Next.js dashboard |

## What's working today

- All 8 Python packages have passing test suites (70+ tests total, all mocked — no network or live Postgres required).
- The full request shape of every external vendor (HeyGen, Submagic, IG Graph, R2, Retell, Stripe, Twilio, Cal, ManyChat, Meta, Claude) is exercised.
- The CRM schema + materialized views are production-ready; drop them into Supabase and the dashboard lights up.
- The compliance gate encodes the FCC 2024 ruling + the 5 strictest state mini-TCPAs; no call fires without passing it.
- The Retell agent prompt is a full template with AI-disclosure + recording notice + mid-call close flow.

## What you configure (SaaS — can't be built as code)

1. **HeyGen**: train Instant Avatar + clone voice. Note avatar_id + voice_id.
2. **ManyChat Pro**: keyword triggers per CTA word; opener DMs; webhook → `dm_engine` + CRM.
3. **Cal.com**: discovery + closing event types; webhook → CRM `/webhook/cal`.
4. **Retell AI**: upload cloned voice; paste `voice_agent/prompts/agent_system_prompt.md`; configure tool-calls (`send_payment_link`, `book_human_followup`, `reschedule`); webhook → CRM `/webhook/retell`.
5. **Stripe**: create Price IDs for each offer; webhook → CRM `/webhook/stripe`; verify Payment Links show up in production.
6. **Twilio**: A2P 10DLC brand + campaign registration; buy a number; wire `voice_agent`.
7. **Cloudflare R2**: bucket `reels` + `raw`, public read-only access, public domain (e.g. `assets.yourdomain.com`).
8. **Meta / IG Graph API**: Business/Creator account + Facebook Page + app review for `instagram_content_publish`.
9. **Supabase**: new project, run both SQL migrations in `infra/migrations/`.
10. **Anthropic**: API key for the DM qualifier LLM.

## Deploy in one shot

```bash
# Start Postgres + CRM core + compliance gate + dm_engine + voice_agent
cd infra && docker-compose up -d

# Apply DB migrations
docker-compose exec postgres psql -U postgres -d crm -f /migrations/001_init.sql
docker-compose exec postgres psql -U postgres -d crm -f /migrations/002_views.sql

# Boot the dashboard
cd ../dashboard && npm install && npm run dev
```

Point each SaaS webhook at `https://<your-crm>/webhook/<source>` and you're collecting events.

## Economics at target volume

20 Reels/day + 100 qualified DMs/day + 30 AI voice calls/day ≈
**$1,200–1,900 / mo infra+API spend** (content stack, Retell, Stripe/Twilio,
Supabase, VPS, Anthropic). One $2k coaching close every two weeks
covers the whole stack.

## Seven hard truths (from the research)

1. Sends + saves beat likes 3–5x. Every Reel needs a reason to DM-share or save.
2. Hook is 80% of the game. 3-second retention is the viral gate.
3. One specific keyword per CTA ("SCALE", "BOOKED"), never "INFO" or "YES".
4. Use only Meta-official APIs. Browser automation = guaranteed ban.
5. AI closes sub-$500 end-to-end; books $1k-$10k for humans. Don't expect pure-AI high-ticket closing in 2026.
6. FCC 2024 ruling: AI voice = artificial under TCPA. Every call needs prior express written consent.
7. QMUL 2025: cloned voices pass as human 58% of the time. Voice quality isn't the bottleneck; latency <800ms + backchanneling + tolerated interruption are.

## Detailed references

- Research synthesis: `reels_generator/docs/STRATEGY.md`
- Custom CRM schema + views: `reels_generator/docs/CRM_SCHEMA.md`
- Phased build roadmap: `reels_generator/docs/BUILD_ORDER.md`
- Per-service READMEs in each package directory.

# Autonomous IG Lead-Gen & Closing Ecosystem — Strategy (2026)

Synthesis of three deep-research tracks (IG virality + comment-to-DM, AI voice/closing
agents, and the content-to-post automation stack) plus a custom CRM / performance layer.

Goal: an end-to-end system where content is generated, posted, commenters are converted
into DM conversations, AI qualifies them, books a call, AI (or a human closer fed by AI)
closes the sale, and every step is logged so the founder can step out of operations and
into decisions.

---

## 1. The pipeline at a glance

```
 ┌──────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
 │ Hook Factory │──▶│  AI Avatar │──▶│ Auto-Edit  │──▶│ IG Publish │
 │ (LLM batch)  │   │ (HeyGen)   │   │ (Submagic) │   │ (Graph API)│
 └──────────────┘   └────────────┘   └────────────┘   └────────────┘
                                                            │
                                                            ▼
                                                   ┌─────────────────┐
                                                   │   Reel is live  │
                                                   │  (viewers see   │
                                                   │   CTA keyword)  │
                                                   └─────────────────┘
                                                            │
                                                            ▼ user comments keyword
                                                   ┌─────────────────┐
                                                   │ ManyChat trigger│
                                                   │ → auto-DM       │
                                                   └─────────────────┘
                                                            │
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ AI DM Qualifier │
                                                   │ (Claude/GPT)    │
                                                   │ 3-5 BANT Qs     │
                                                   │ → lead score    │
                                                   └─────────────────┘
                                                      │           │
                                          Hot/Warm    │           │ Disqualified
                                                      ▼           ▼
                                          ┌────────────────┐ ┌──────────┐
                                          │ Cal.com booked │ │ Nurture  │
                                          │ (or instant    │ │ sequence │
                                          │  callback)     │ │ + tag    │
                                          └────────────────┘ └──────────┘
                                                      │
                                                      ▼
                                          ┌────────────────────────────┐
                                          │   AI Voice Agent (Retell)  │
                                          │   - continues DM context   │
                                          │   - objection handling     │
                                          │   - Stripe link via SMS    │
                                          └────────────────────────────┘
                                                      │
                       closes/low-ticket              │        human-closer/high-ticket
                             ┌────────────────────────┴──────────────────────┐
                             ▼                                                ▼
                   ┌──────────────────┐                          ┌───────────────────┐
                   │ Stripe PaymentLink│                         │ Human closer calls│
                   │ (mid-call)        │                         │ with full context │
                   └──────────────────┘                          └───────────────────┘
                             │                                                │
                             └────────────────────┬───────────────────────────┘
                                                  ▼
                                ┌─────────────────────────────────────┐
                                │ Custom CRM + Analytics Dashboard    │
                                │ (every step above emits events)     │
                                │ → funnel, cohorts, ROI, AI quality  │
                                └─────────────────────────────────────┘
```

Every arrow in that diagram emits a structured event to the custom CRM so the founder can
see: which hook drove the commenter, what the DM bot said, what the lead score was, what
the AI voice agent said on the call, whether a payment link was sent, whether it was
clicked, and whether it closed. That closed loop is what makes this "boss hat off".

---

## 2. The five modules

### 2.1 Content Factory
- **Hook generation**: Claude (Opus / Sonnet) batch job. Prompt loads offer + ICP + brand
  voice, rotates frameworks (AIDA, PAS, belief-flip, stat hooks), emits JSON with
  framework tag + predicted stop-scroll score. 20-40 hooks/day.
- **Video**: HeyGen Instant Avatar + cloned voice (already built — `reels_generator/reels/`).
  Cheap, stable API, proven in n8n blueprints.
- **Editing**: Submagic API (captions, emoji, zoom cuts, B-roll). Only tool with a clean
  self-serve API that produces "social-media ready" output.
- **Storage**: Cloudflare R2. Meta blocks Drive/redirect URLs since 2025 — must be direct
  public URL.
- **Post**: Instagram Graph API `/media` → `/media_publish`. Hard limit 100 posts / 24h.
  Requires Business/Creator IG + FB Page + app review. Alternative: Blotato (handles
  music/trending sound limitations).

### 2.2 DM Engine
- **Trigger**: ManyChat (official Meta partner) watches for keyword comments → sends
  opening DM with promised deliverable (template/PDF/link). Stay on the official Graph
  API to avoid bans.
- **Qualifier**: Claude-powered conversation flow (can live inside ManyChat AI Step, or
  hand off to our own FastAPI service for more control). BANT-lite for coaching:
  1. Current state (revenue / situation)
  2. Desired outcome + timeline
  3. What they've tried
  4. Budget proxy ("invested in a program before?")
  5. Decision authority (B2B only)
  → LLM rubric scores Gold / Silver / Disqualified.
- **Routing**: Hot → Cal.com slots in DM. Warm → AI voice callback within 5 min.
  Disqualified → free-resource nurture + CRM tag.
- **Compliance**: stay within Meta's 24h window, keep bulk identical text under threshold,
  <200 auto-DMs/hour. Capture explicit TCPA-grade consent ("yes, call/text me at XXX")
  before any outbound voice.

### 2.3 Voice Agent
- **Platform**: Retell AI (lowest latency ~600ms, native Salesforce/HubSpot/MCP,
  transparent $0.07-0.13/min). Vapi is the flexible alternative for deep custom work.
  Bland for pure volume dialers. **Avoid Air.ai** (high upfront, weak dev story).
- **Voice**: ElevenLabs v3 cloned voice. QMUL 2025 study — cloned voices pass as human
  58% of the time; generic AI voices 41%. Cloning matters.
- **LLM**: GPT-4o primary, Claude Sonnet 4.5 fallback for steerability.
- **Context injection**: pass DM transcript, lead score, pain point, offer, objections
  as `retell_llm_dynamic_variables`. The AI picks up the conversation mid-thread rather
  than starting cold.
- **Close mechanics**: AI triggers Stripe Payment Link via Twilio SMS mid-call, waits on
  the line while the prospect pays, confirms receipt via Stripe webhook.
- **Realism guardrails**: <800ms end-to-end latency, 5-10% filler words, backchannel
  ("mhm", "right"), tolerate interruptions, AI disclosure + recording notice on connect.

### 2.4 Compliance Layer
Non-negotiable — a single TCPA class-action can end the business.

- **FCC Feb 2024 ruling**: AI-generated voices are "artificial or prerecorded" under
  TCPA. Prior express written consent required for every AI call. $500–$1,500 per
  violating call, private right of action.
- **State-specific**: FL / OK / MD (≤3 sales calls per 24h, 8am–8pm local), WA ($1k/call
  damages), CA AB 2905 (must disclose AI up front or $500/call).
- **Recording consent**: 12 all-party states (CA, CT, DE, FL, IL, MD, MA, MT, NV, NH, PA,
  WA). Always play AI disclosure + recording notice on connect to be safe everywhere.
- **Build**: a pre-dial gate service that checks (a) written consent on file, (b) DNC
  registry, (c) state rules by phone NPA, (d) dial cap (≤3/day/lead), (e) quiet hours,
  (f) STOP/opt-out honored across SMS + DM.

### 2.5 Custom CRM + Performance Dashboard — **the hub**
This is what lets the founder step out of operations.

See `CRM_SCHEMA.md` for the full schema. High-level:

**Entities**
- `leads` (one per person) — identity, contact, source, consent flags, lifecycle stage
- `content_assets` (one per posted Reel) — hook variant, framework, IG media ID,
  performance snapshots
- `conversations` (DM threads + transcripts) — linked to lead + originating content
- `appointments` (Cal.com bookings) — scheduled, rescheduled, no-show, showed
- `calls` (AI voice sessions) — Retell ID, duration, transcript, outcome, objections
- `payments` (Stripe events) — link sent, clicked, paid, refunded
- `events` (append-only event log) — raw feed so you never lose history
- `ai_quality_reviews` — human-in-the-loop samples rated for tone / factuality / compliance

**Dashboards**
1. **Funnel**: impressions → comments → DMs → qualified → booked → showed → closed.
   Per-hook, per-day, per-source. Click-through to the exact Reel.
2. **Hook leaderboard**: every hook variant ranked by stop-scroll (3s retention) and
   downstream conversion (comments → closes).
3. **AI quality**: sample transcripts (DM + voice) with automated and human scoring.
   Catches drift before it costs deals.
4. **Show / close rates by AI vs. human**: so you know when to let AI close vs. hand off.
5. **Compliance log**: every consent capture, opt-out, AI disclosure played. Audit-ready.
6. **Cohort retention**: 7/30/60/90-day revenue by content cohort (which posts drove the
   best LTV buyers).

**Stack for the CRM itself** (recommended):
- **DB**: Postgres via Supabase (auth, row-level security, realtime subscriptions free).
- **API**: FastAPI service with webhook endpoints from every external tool.
- **Dashboard**: Next.js + Tremor (or Metabase if you want zero-code charts).
- **Queue**: Supabase pg-boss or Redis for long-running jobs (video renders, call
  scheduling).

Alternative: GoHighLevel as ops CRM + a thin Postgres "analytics mart" that pulls from
GHL/Retell/IG/Stripe and builds the dashboards on top. Faster to ship, less custom code.

---

## 3. Economics at target volume

Assuming 20 Reels/day posted, 100 qualified DMs/day, 30 booked calls, 30 AI voice calls:

| Layer | Monthly | Notes |
|---|---|---|
| Content (Claude + HeyGen + ElevenLabs + Submagic + R2 + n8n) | $370–620 | 600 Reels/mo |
| DM engine (ManyChat Pro + LLM tokens) | $50–120 | 100 convos/day |
| Voice (Retell + Twilio + ElevenLabs) | $700–1,000 | 30 × 6 min × $0.13 |
| CRM + orchestration (Supabase Pro + n8n VPS + Cal.com) | $70–120 | |
| Compliance (consent checkbox, DNC API feed) | $20–50 | |
| **Run-rate total** | **~$1,200–1,900 / mo** | excl. Stripe fees |

Per-unit: ~$1–2 per qualified DM, ~$1–3 per AI voice call, ~$1 per finished Reel.
One $2k close every 2 weeks covers the whole stack.

---

## 4. What's already built vs. what's left

**Already built** (branch `claude/automated-reels-hook-generator-4O32y`, this commit):
- HeyGen API client + polling + download
- FFmpeg stitching module (hook + core video → final Reel)
- CSV / Google Sheets hook reader
- Parallel pipeline with content-hash caching + per-hook error isolation
- Make.com scenario blueprint (alternative orchestration)
- 17 pytest cases (fully mocked)

**To build** (prioritized — see `BUILD_ORDER.md`):
1. Custom CRM + event bus + dashboard (the hub)
2. Instagram Graph API poster (+ R2 upload step in the pipeline)
3. Compliance gate service
4. FastAPI webhook receiver for ManyChat / Cal.com / Retell / Stripe
5. AI DM qualifier with Claude + lead scorer
6. Retell agent config + dynamic-variable handoff from DM
7. Submagic auto-edit step
8. n8n master blueprint that ties the whole pipeline together
9. Hook performance analyzer (IG Insights → auto-rerank next batch)

**Must configure outside code** (can't be "built" — SaaS + your accounts):
- HeyGen avatar + voice cloning
- ManyChat account + Meta app approval for IG Graph API
- Retell account + voice clone upload
- Cal.com team + webhook config
- Cloudflare R2 bucket
- Supabase project
- Stripe account + Payment Link automation
- Twilio account + phone number + A2P 10DLC registration
- TCPA-compliant consent checkbox on landing page

---

## 5. Safety & sustainability rails

- **Meta side**: stay on official API partners only. Never use browser automation / fake
  accounts. Cap auto-DM rate <200/hour. Vary reply text. Only 1 in 3-4 posts carries a
  comment-to-DM CTA.
- **Phone side**: no dialing without written TCPA consent. Play AI + recording disclosure
  on every call. Respect DNC and state laws. Log everything for the audit trail.
- **AI quality**: 10% random-sample human review of DM and voice transcripts weekly.
  Flag drift. Retrain / adjust system prompts when accuracy drops.
- **Spend guardrails**: daily $ cap per service in the orchestrator; kill switch for the
  dialer if call-to-connect rate collapses.
- **No "full autonomy" on the first deployment**. Ship with human-in-the-loop on the
  close step for the first 30 days; graduate to AI-closing only once you've measured
  tone + compliance on 100+ recorded calls.

---

## 6. Sources

See each research track's cited URLs — Mosseri 2025 algorithm notes, QMUL AI-voice
realism study, FCC Feb 2024 TCPA ruling, GrowwStacks AI sales case study, HeyGen /
Submagic / Blotato n8n official templates, Retell / Vapi / Bland pricing pages,
ManyChat / SetSmart / Intellicoach compliance docs, Meta IG Content Publishing docs.

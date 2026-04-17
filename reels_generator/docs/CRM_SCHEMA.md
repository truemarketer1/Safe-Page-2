# Custom CRM — Schema & Event Model

The CRM is the hub every other module reports to. It has two jobs:

1. **System of record** — one row per lead, every interaction attached to it.
2. **Performance analytics** — funnel, cohort, AI-quality, and compliance dashboards so
   the founder can make decisions instead of doing ops.

Target DB: Postgres (Supabase). Timestamps in UTC. Soft-deletes via `deleted_at`.
All tables have `id UUID`, `created_at`, `updated_at`.

---

## Core tables

### `leads`
One row per distinct person.

| column | type | notes |
|---|---|---|
| `id` | uuid | pk |
| `ig_handle` | text | nullable |
| `ig_user_id` | text | from Graph API; unique partial index when not null |
| `full_name` | text | |
| `email` | text | |
| `phone_e164` | text | normalized +15551234567 |
| `country` | text | ISO-2 |
| `region` | text | state/province for TCPA rules |
| `timezone` | text | IANA |
| `source_content_id` | uuid | fk content_assets.id — which Reel brought them in |
| `source_keyword` | text | the trigger keyword they commented |
| `consent_dm` | bool | comment = implicit ok; opt-out flips false |
| `consent_sms` | bool | requires explicit DM confirmation |
| `consent_voice_ai` | bool | TCPA — must be written/captured |
| `consent_recording` | bool | required in all-party states |
| `consent_captured_at` | timestamptz | for audit |
| `consent_captured_proof` | jsonb | raw message / IP / form payload |
| `dnc_checked_at` | timestamptz | |
| `dnc_status` | text | clean / blocked |
| `lead_score` | int | 0-100 from qualifier |
| `lead_tier` | text | gold / silver / bronze / disqualified |
| `lifecycle_stage` | text | see enum below |
| `tags` | text[] | |
| `notes` | text | |

**Lifecycle stages**:
`new → dm_opened → qualifying → qualified → booked → showed → no_show → rescheduled → closed_won → closed_lost → nurture → opted_out`

### `content_assets`
One row per posted Reel.

| column | type | notes |
|---|---|---|
| `id` | uuid | pk |
| `hook_text` | text | |
| `hook_framework` | text | aida / pas / belief_flip / stat / pov |
| `hook_batch_id` | uuid | groups a set of variants tested together |
| `core_message_id` | uuid | fk to core_messages |
| `r2_video_url` | text | public url used by IG API |
| `ig_media_id` | text | returned by Graph API |
| `ig_permalink` | text | |
| `cta_keyword` | text | the trigger word in the post |
| `posted_at` | timestamptz | |
| `scheduled_for` | timestamptz | |
| `status` | text | draft / rendering / ready / posted / failed / retired |
| `failure_reason` | text | |

### `content_metrics`
Append-only snapshots from IG Insights.

| column | type |
|---|---|
| `id` | uuid |
| `content_id` | uuid |
| `captured_at` | timestamptz |
| `impressions` | int |
| `reach` | int |
| `plays` | int |
| `saves` | int |
| `shares` | int |
| `comments` | int |
| `likes` | int |
| `avg_watch_seconds` | numeric |
| `completion_rate` | numeric |
| `follows_from_post` | int |

### `conversations`
One per lead × channel thread.

| column | type | notes |
|---|---|---|
| `id` | uuid | |
| `lead_id` | uuid | fk |
| `channel` | text | ig_dm / sms / email |
| `status` | text | open / qualifying / booked / handed_off / closed / opted_out |
| `qualifier_agent_id` | text | which LLM config handled it |
| `opened_at` | timestamptz | |
| `last_message_at` | timestamptz | |
| `message_count` | int | |

### `messages`
Append-only per-message log.

| column | type | notes |
|---|---|---|
| `id` | uuid | |
| `conversation_id` | uuid | |
| `direction` | text | inbound / outbound |
| `sender_type` | text | lead / ai / human |
| `body` | text | |
| `raw_payload` | jsonb | full source event |
| `tokens_in` / `tokens_out` | int | LLM cost tracking |
| `created_at` | timestamptz | |

### `appointments`
Cal.com bookings.

| column | type | notes |
|---|---|---|
| `id` | uuid | |
| `lead_id` | uuid | |
| `conversation_id` | uuid | nullable |
| `cal_event_id` | text | |
| `booked_at` | timestamptz | |
| `scheduled_for` | timestamptz | |
| `status` | text | booked / rescheduled / cancelled / no_show / showed / completed |
| `reschedule_count` | int | |
| `assigned_to` | text | ai_closer / human_closer_id |
| `reminders_sent` | int | |

### `calls`
AI voice sessions (Retell / Vapi / Bland).

| column | type | notes |
|---|---|---|
| `id` | uuid | |
| `lead_id` | uuid | |
| `appointment_id` | uuid | nullable |
| `provider` | text | retell / vapi / bland |
| `provider_call_id` | text | |
| `agent_id` | text | which voice agent config |
| `direction` | text | outbound / inbound |
| `started_at` | timestamptz | |
| `ended_at` | timestamptz | |
| `duration_seconds` | int | |
| `status` | text | queued / ringing / connected / completed / failed / voicemail / no_answer |
| `outcome` | text | qualified / booked / objection / payment_pending / paid / lost / reschedule |
| `transcript_url` | text | |
| `recording_url` | text | |
| `objections` | text[] | parsed from transcript by a summarizer LLM |
| `ai_disclosure_played` | bool | |
| `recording_notice_played` | bool | |
| `state_rule_checks` | jsonb | which rules passed pre-dial |

### `payments`
Stripe events.

| column | type | notes |
|---|---|---|
| `id` | uuid | |
| `lead_id` | uuid | |
| `call_id` | uuid | nullable — if sent mid-call |
| `stripe_payment_link_id` | text | |
| `stripe_payment_intent_id` | text | |
| `amount_cents` | int | |
| `currency` | text | |
| `status` | text | link_sent / link_clicked / paid / failed / refunded |
| `sent_at` / `paid_at` | timestamptz | |

### `events` (append-only)
Every raw webhook. Never mutated. Source of truth for rebuilding state.

| column | type |
|---|---|
| `id` | uuid |
| `source` | text (manychat / cal / retell / stripe / ig / manual) |
| `event_type` | text |
| `lead_id` | uuid | nullable until matched |
| `payload` | jsonb |
| `received_at` | timestamptz |
| `processed_at` | timestamptz |
| `processing_error` | text |

### `ai_quality_reviews`
Human-in-the-loop sampling for drift detection.

| column | type | notes |
|---|---|---|
| `id` | uuid | |
| `subject_type` | text | message / call |
| `subject_id` | uuid | |
| `reviewer` | text | human email or 'auto_llm' |
| `scores` | jsonb | {tone, factuality, compliance, conversion_quality} 0-5 |
| `notes` | text | |
| `reviewed_at` | timestamptz | |

### `compliance_log`
Every consent capture, opt-out, disclosure played.

| column | type |
|---|---|
| `id` | uuid |
| `lead_id` | uuid |
| `kind` | text (consent_granted / consent_revoked / ai_disclosure / recording_notice / dnc_check / quiet_hours_block / daily_cap_block) |
| `evidence` | jsonb |
| `occurred_at` | timestamptz |

---

## Derived views (materialized for the dashboards)

```sql
-- Funnel per day per source content
CREATE MATERIALIZED VIEW funnel_daily AS
SELECT
  date_trunc('day', l.created_at) AS day,
  l.source_content_id,
  count(*) FILTER (WHERE lifecycle_stage = 'new')            AS new_leads,
  count(*) FILTER (WHERE lifecycle_stage >= 'dm_opened')     AS dm_opened,
  count(*) FILTER (WHERE lifecycle_stage >= 'qualified')     AS qualified,
  count(*) FILTER (WHERE lifecycle_stage >= 'booked')        AS booked,
  count(*) FILTER (WHERE lifecycle_stage >= 'showed')        AS showed,
  count(*) FILTER (WHERE lifecycle_stage = 'closed_won')     AS closed_won,
  sum(p.amount_cents) FILTER (WHERE p.status = 'paid') / 100 AS revenue_usd
FROM leads l
LEFT JOIN payments p ON p.lead_id = l.id
GROUP BY 1, 2;

-- Hook leaderboard
CREATE MATERIALIZED VIEW hook_leaderboard AS
SELECT
  c.id, c.hook_text, c.hook_framework, c.posted_at,
  m.plays, m.completion_rate, m.comments, m.shares, m.saves,
  count(DISTINCT l.id)                                       AS leads_generated,
  count(DISTINCT l.id) FILTER (WHERE l.lifecycle_stage = 'closed_won') AS closes,
  sum(p.amount_cents) FILTER (WHERE p.status = 'paid') / 100 AS revenue_usd,
  (count(DISTINCT l.id) FILTER (WHERE l.lifecycle_stage = 'closed_won')::numeric
     / NULLIF(m.plays, 0)) * 100000 AS closes_per_100k_plays
FROM content_assets c
LEFT JOIN LATERAL (
  SELECT * FROM content_metrics WHERE content_id = c.id ORDER BY captured_at DESC LIMIT 1
) m ON true
LEFT JOIN leads l ON l.source_content_id = c.id
LEFT JOIN payments p ON p.lead_id = l.id
GROUP BY c.id, m.plays, m.completion_rate, m.comments, m.shares, m.saves;

-- AI vs human close rate
CREATE MATERIALIZED VIEW closer_performance AS
SELECT
  a.assigned_to,
  count(*) AS total_appointments,
  count(*) FILTER (WHERE a.status = 'showed')     AS showed,
  count(*) FILTER (WHERE a.status = 'no_show')    AS no_show,
  count(*) FILTER (WHERE l.lifecycle_stage = 'closed_won') AS closed,
  avg(c.duration_seconds) FILTER (WHERE c.status = 'completed') AS avg_call_seconds
FROM appointments a
JOIN leads l ON l.id = a.lead_id
LEFT JOIN calls c ON c.appointment_id = a.id
GROUP BY a.assigned_to;
```

---

## Event bus contract

Every external system POSTs to `/webhook/{source}`. The receiver:

1. Validates signature (Stripe / Cal / Meta / Retell each have their own scheme).
2. Inserts a raw row into `events`.
3. Queues an async job to project the event into the domain tables
   (`leads` / `conversations` / `appointments` / `calls` / `payments`).
4. Returns 200 immediately — never block the sender.

Projection keeps `events` as the immutable source of truth so the domain tables can be
rebuilt at any time (disaster recovery / schema changes).

### Event names the system emits internally

```
lead.created
lead.consent.captured
lead.consent.revoked
conversation.opened
conversation.message.inbound
conversation.message.outbound
conversation.qualified
conversation.disqualified
appointment.booked
appointment.rescheduled
appointment.noshow
appointment.showed
call.queued
call.connected
call.completed
call.failed
payment.link.sent
payment.link.clicked
payment.paid
payment.refunded
compliance.block.quiet_hours
compliance.block.daily_cap
compliance.block.dnc
compliance.disclosure.played
```

These are what the dashboards subscribe to for realtime updates.

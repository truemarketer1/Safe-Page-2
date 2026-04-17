-- CRM core schema (Phase 1)
-- Source of truth: reels_generator/docs/CRM_SCHEMA.md
--
-- Run order:
--   psql $DATABASE_URL -f infra/migrations/001_init.sql
-- On Supabase, paste into the SQL editor. Idempotent via IF NOT EXISTS.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------- enums ----------
DO $$ BEGIN
  CREATE TYPE lifecycle_stage AS ENUM (
    'new', 'dm_opened', 'qualifying', 'qualified',
    'booked', 'showed', 'no_show', 'rescheduled',
    'closed_won', 'closed_lost', 'nurture', 'opted_out'
  );
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE lead_tier AS ENUM ('gold', 'silver', 'bronze', 'disqualified');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE content_status AS ENUM ('draft', 'rendering', 'ready', 'posted', 'failed', 'retired');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE channel AS ENUM ('ig_dm', 'sms', 'email', 'voice');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE call_provider AS ENUM ('retell', 'vapi', 'bland', 'elevenlabs');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- ---------- core tables ----------

CREATE TABLE IF NOT EXISTS content_assets (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hook_text         text NOT NULL,
  hook_framework    text,
  hook_batch_id     uuid,
  core_message_id   uuid,
  r2_video_url      text,
  ig_media_id       text,
  ig_permalink      text,
  cta_keyword       text,
  scheduled_for     timestamptz,
  posted_at         timestamptz,
  status            content_status NOT NULL DEFAULT 'draft',
  failure_reason    text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_content_status_scheduled ON content_assets (status, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_content_posted ON content_assets (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_cta ON content_assets (cta_keyword);

CREATE TABLE IF NOT EXISTS leads (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ig_handle             text,
  ig_user_id            text,
  full_name             text,
  email                 text,
  phone_e164            text,
  country               text,
  region                text,
  timezone              text,
  source_content_id     uuid REFERENCES content_assets(id),
  source_keyword        text,
  consent_dm            boolean DEFAULT false,
  consent_sms           boolean DEFAULT false,
  consent_voice_ai      boolean DEFAULT false,
  consent_recording     boolean DEFAULT false,
  consent_captured_at   timestamptz,
  consent_captured_proof jsonb,
  dnc_checked_at        timestamptz,
  dnc_status            text,
  stop_sms_at           timestamptz,
  stop_dm_at            timestamptz,
  lead_score            int,
  lead_tier             lead_tier,
  lifecycle_stage       lifecycle_stage NOT NULL DEFAULT 'new',
  tags                  text[] DEFAULT '{}',
  notes                 text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_ig_user ON leads (ig_user_id) WHERE ig_user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_phone ON leads (phone_e164) WHERE phone_e164 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads (lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_leads_source_content ON leads (source_content_id);
CREATE INDEX IF NOT EXISTS idx_leads_created ON leads (created_at DESC);

CREATE TABLE IF NOT EXISTS content_metrics (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id        uuid NOT NULL REFERENCES content_assets(id) ON DELETE CASCADE,
  captured_at       timestamptz NOT NULL DEFAULT now(),
  impressions       int,
  reach             int,
  plays             int,
  saves             int,
  shares            int,
  comments          int,
  likes             int,
  avg_watch_seconds numeric,
  completion_rate   numeric,
  follows_from_post int,
  dm_sends          int
);
CREATE INDEX IF NOT EXISTS idx_metrics_content_time ON content_metrics (content_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS conversations (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id             uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  channel             channel NOT NULL,
  status              text NOT NULL DEFAULT 'open',
  qualifier_agent_id  text,
  opened_at           timestamptz NOT NULL DEFAULT now(),
  last_message_at     timestamptz,
  message_count       int NOT NULL DEFAULT 0,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conversations_lead ON conversations (lead_id);
CREATE INDEX IF NOT EXISTS idx_conversations_channel_status ON conversations (channel, status);

CREATE TABLE IF NOT EXISTS messages (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id  uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  direction        text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  sender_type      text NOT NULL CHECK (sender_type IN ('lead', 'ai', 'human', 'system')),
  body             text,
  raw_payload      jsonb,
  tokens_in        int,
  tokens_out       int,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS appointments (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id            uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  conversation_id    uuid REFERENCES conversations(id),
  cal_event_id       text UNIQUE,
  booked_at          timestamptz NOT NULL DEFAULT now(),
  scheduled_for      timestamptz NOT NULL,
  duration_minutes   int,
  appointment_type   text,
  status             text NOT NULL DEFAULT 'booked'
                     CHECK (status IN ('booked','confirmed','reminded','showed',
                                       'no_show','cancelled','rescheduled','completed')),
  reschedule_count   int NOT NULL DEFAULT 0,
  rescheduled_from_id uuid REFERENCES appointments(id),
  assigned_to        text,
  reminders_sent     int NOT NULL DEFAULT 0,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_appointments_lead ON appointments (lead_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled ON appointments (scheduled_for);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments (status);

CREATE TABLE IF NOT EXISTS calls (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id                 uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  appointment_id          uuid REFERENCES appointments(id),
  provider                call_provider NOT NULL,
  provider_call_id        text UNIQUE,
  agent_id                text,
  direction               text NOT NULL CHECK (direction IN ('outbound','inbound')),
  started_at              timestamptz,
  ended_at                timestamptz,
  duration_seconds        int,
  status                  text,
  outcome                 text,
  transcript_url          text,
  recording_url           text,
  objections              text[] DEFAULT '{}',
  ai_disclosure_played    boolean DEFAULT false,
  recording_notice_played boolean DEFAULT false,
  state_rule_checks       jsonb,
  ai_cost_cents           int,
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_calls_lead ON calls (lead_id);
CREATE INDEX IF NOT EXISTS idx_calls_appointment ON calls (appointment_id);
CREATE INDEX IF NOT EXISTS idx_calls_started ON calls (started_at DESC);

CREATE TABLE IF NOT EXISTS payments (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id                   uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  call_id                   uuid REFERENCES calls(id),
  stripe_payment_link_id    text,
  stripe_payment_intent_id  text UNIQUE,
  amount_cents              int NOT NULL,
  currency                  text NOT NULL DEFAULT 'usd',
  status                    text NOT NULL
                            CHECK (status IN ('link_sent','link_clicked','paid','failed','refunded')),
  sent_at                   timestamptz,
  paid_at                   timestamptz,
  refunded_at               timestamptz,
  created_at                timestamptz NOT NULL DEFAULT now(),
  updated_at                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_payments_lead ON payments (lead_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status);

-- ---------- event log (append-only firehose) ----------
CREATE TABLE IF NOT EXISTS events (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source            text NOT NULL,
  event_type        text NOT NULL,
  idempotency_key   text,
  lead_id           uuid REFERENCES leads(id),
  payload           jsonb NOT NULL,
  signature_valid   boolean,
  received_at       timestamptz NOT NULL DEFAULT now(),
  processed_at      timestamptz,
  processing_error  text
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_events_source_idem
  ON events (source, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_received ON events (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_unprocessed ON events (processed_at) WHERE processed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_events_source_type ON events (source, event_type);

-- ---------- compliance ----------
CREATE TABLE IF NOT EXISTS compliance_log (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id      uuid REFERENCES leads(id),
  kind         text NOT NULL,
  evidence     jsonb,
  occurred_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_compliance_lead ON compliance_log (lead_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_compliance_kind ON compliance_log (kind, occurred_at DESC);

-- ---------- ai quality reviews ----------
CREATE TABLE IF NOT EXISTS ai_quality_reviews (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_type text NOT NULL CHECK (subject_type IN ('message','call','conversation')),
  subject_id   uuid NOT NULL,
  reviewer     text NOT NULL,
  scores       jsonb NOT NULL,
  notes        text,
  reviewed_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------- updated_at trigger ----------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['leads','content_assets','conversations','appointments','calls','payments']
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_updated_at ON %I', t);
    EXECUTE format('CREATE TRIGGER trg_updated_at BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t);
  END LOOP;
END $$;

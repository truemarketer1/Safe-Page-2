-- Materialized views for the dashboard.
-- Refresh on a schedule (cron/n8n): REFRESH MATERIALIZED VIEW CONCURRENTLY <name>;

-- Per-day funnel, optionally grouped by source Reel.
CREATE MATERIALIZED VIEW IF NOT EXISTS funnel_daily AS
SELECT
  date_trunc('day', l.created_at)::date                    AS day,
  l.source_content_id,
  count(*)                                                  AS new_leads,
  count(*) FILTER (WHERE l.lifecycle_stage != 'new')        AS dm_opened,
  count(*) FILTER (WHERE l.lifecycle_stage IN (
      'qualified','booked','showed','closed_won'))          AS qualified,
  count(*) FILTER (WHERE l.lifecycle_stage IN (
      'booked','showed','closed_won'))                      AS booked,
  count(*) FILTER (WHERE l.lifecycle_stage IN (
      'showed','closed_won'))                               AS showed,
  count(*) FILTER (WHERE l.lifecycle_stage = 'closed_won')  AS closed_won,
  COALESCE(sum(p.amount_cents) FILTER (WHERE p.status = 'paid'), 0) / 100.0 AS revenue_usd
FROM leads l
LEFT JOIN payments p ON p.lead_id = l.id
GROUP BY 1, 2;
CREATE UNIQUE INDEX IF NOT EXISTS ux_funnel_daily ON funnel_daily (day, source_content_id);

-- Per-hook leaderboard with latest metrics snapshot + downstream revenue.
CREATE MATERIALIZED VIEW IF NOT EXISTS hook_leaderboard AS
SELECT
  c.id,
  c.hook_text,
  c.hook_framework,
  c.cta_keyword,
  c.posted_at,
  m.plays,
  m.reach,
  m.completion_rate,
  m.comments,
  m.shares,
  m.saves,
  m.dm_sends,
  count(DISTINCT l.id)                                                  AS leads_generated,
  count(DISTINCT l.id) FILTER (WHERE l.lifecycle_stage = 'closed_won')  AS closes,
  COALESCE(sum(p.amount_cents) FILTER (WHERE p.status = 'paid'), 0) / 100.0 AS revenue_usd,
  CASE WHEN m.plays > 0
       THEN (count(DISTINCT l.id) FILTER (WHERE l.lifecycle_stage = 'closed_won')::numeric
             / m.plays) * 100000
       ELSE NULL END                                                    AS closes_per_100k_plays
FROM content_assets c
LEFT JOIN LATERAL (
  SELECT plays, reach, completion_rate, comments, shares, saves, dm_sends
  FROM content_metrics WHERE content_id = c.id
  ORDER BY captured_at DESC LIMIT 1
) m ON true
LEFT JOIN leads l ON l.source_content_id = c.id
LEFT JOIN payments p ON p.lead_id = l.id
GROUP BY c.id, m.plays, m.reach, m.completion_rate, m.comments, m.shares, m.saves, m.dm_sends;
CREATE UNIQUE INDEX IF NOT EXISTS ux_hook_leaderboard ON hook_leaderboard (id);

-- Closer performance (AI vs human): show/no-show/close rates + avg call length.
CREATE MATERIALIZED VIEW IF NOT EXISTS closer_performance AS
SELECT
  COALESCE(a.assigned_to, 'unassigned')                          AS assigned_to,
  count(*)                                                       AS total_appointments,
  count(*) FILTER (WHERE a.status = 'showed')                    AS showed,
  count(*) FILTER (WHERE a.status = 'no_show')                   AS no_show,
  count(*) FILTER (WHERE a.status = 'rescheduled')               AS rescheduled,
  count(*) FILTER (WHERE l.lifecycle_stage = 'closed_won')       AS closed,
  CASE WHEN count(*) > 0 THEN
      count(*) FILTER (WHERE a.status = 'showed')::numeric / count(*)
  END                                                            AS show_rate,
  CASE WHEN count(*) FILTER (WHERE a.status = 'showed') > 0 THEN
      count(*) FILTER (WHERE l.lifecycle_stage = 'closed_won')::numeric
      / count(*) FILTER (WHERE a.status = 'showed')
  END                                                            AS close_rate_of_shows,
  avg(c.duration_seconds) FILTER (WHERE c.status = 'completed')  AS avg_call_seconds
FROM appointments a
JOIN leads l ON l.id = a.lead_id
LEFT JOIN calls c ON c.appointment_id = a.id
GROUP BY 1;
CREATE UNIQUE INDEX IF NOT EXISTS ux_closer_performance ON closer_performance (assigned_to);

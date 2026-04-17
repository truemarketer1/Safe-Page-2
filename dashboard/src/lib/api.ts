// Thin server-side fetcher for the CRM core read API.
// Runs in Next.js server components, so the bearer token never leaks to the browser.

const BASE = process.env.CRM_BASE_URL ?? "http://localhost:8000";
const TOKEN = process.env.CRM_API_TOKEN ?? "";

async function get<T>(path: string, revalidate = 60): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
    next: { revalidate },
  });
  if (!res.ok) {
    throw new Error(`CRM ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type FunnelRow = {
  day: string;
  source_content_id: string | null;
  new_leads: number;
  dm_opened: number;
  qualified: number;
  booked: number;
  showed: number;
  closed_won: number;
  revenue_usd: number;
};

export type HookRow = {
  id: string;
  hook_text: string;
  hook_framework: string | null;
  cta_keyword: string | null;
  posted_at: string | null;
  plays: number | null;
  completion_rate: number | null;
  comments: number | null;
  leads_generated: number;
  closes: number;
  revenue_usd: number;
  closes_per_100k_plays: number | null;
};

export type CloserRow = {
  assigned_to: string;
  total_appointments: number;
  showed: number;
  no_show: number;
  rescheduled: number;
  closed: number;
  show_rate: number | null;
  close_rate_of_shows: number | null;
  avg_call_seconds: number | null;
};

export const api = {
  funnel: (sinceDays = 30) =>
    get<FunnelRow[]>(`/api/metrics/funnel?since_days=${sinceDays}`),
  hooks: (order = "revenue_usd", limit = 50) =>
    get<HookRow[]>(`/api/metrics/hooks?order=${order}&limit=${limit}`),
  closers: () => get<CloserRow[]>("/api/metrics/closers"),
};

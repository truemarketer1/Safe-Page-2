import { api } from "@/lib/api";
import { Card, Metric, Text, Grid } from "@tremor/react";

export default async function Home() {
  const [funnel, closers] = await Promise.all([api.funnel(30), api.closers()]);
  const totals = funnel.reduce(
    (acc, r) => ({
      newLeads: acc.newLeads + r.new_leads,
      booked: acc.booked + r.booked,
      closedWon: acc.closedWon + r.closed_won,
      revenue: acc.revenue + Number(r.revenue_usd ?? 0),
    }),
    { newLeads: 0, booked: 0, closedWon: 0, revenue: 0 },
  );
  const totalAppts = closers.reduce((a, c) => a + c.total_appointments, 0);
  const totalShowed = closers.reduce((a, c) => a + c.showed, 0);
  const showRate = totalAppts ? totalShowed / totalAppts : 0;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">Last 30 days</h1>
      <Grid numItemsMd={2} numItemsLg={4} className="gap-4">
        <Card><Text>New leads</Text><Metric>{totals.newLeads}</Metric></Card>
        <Card><Text>Booked calls</Text><Metric>{totals.booked}</Metric></Card>
        <Card><Text>Closed won</Text><Metric>{totals.closedWon}</Metric></Card>
        <Card><Text>Revenue</Text><Metric>${totals.revenue.toFixed(0)}</Metric></Card>
        <Card><Text>Show rate</Text><Metric>{(showRate * 100).toFixed(0)}%</Metric></Card>
      </Grid>
    </div>
  );
}

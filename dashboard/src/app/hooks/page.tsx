import { api } from "@/lib/api";
import { Card, Title, Table, TableHead, TableHeaderCell, TableBody, TableRow, TableCell, Badge } from "@tremor/react";

export default async function HooksPage() {
  const rows = await api.hooks("revenue_usd", 50);
  return (
    <Card>
      <Title>Hook leaderboard</Title>
      <p className="mt-1 text-sm text-slate-500">Ranked by revenue. Completion rate as tiebreaker.</p>
      <Table className="mt-4">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Hook</TableHeaderCell>
            <TableHeaderCell>Framework</TableHeaderCell>
            <TableHeaderCell>Plays</TableHeaderCell>
            <TableHeaderCell>Completion</TableHeaderCell>
            <TableHeaderCell>Leads</TableHeaderCell>
            <TableHeaderCell>Closes</TableHeaderCell>
            <TableHeaderCell className="text-right">Revenue</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="max-w-md truncate">{r.hook_text}</TableCell>
              <TableCell>{r.hook_framework ?? <Badge color="slate">—</Badge>}</TableCell>
              <TableCell>{r.plays ?? "—"}</TableCell>
              <TableCell>{r.completion_rate ? `${(r.completion_rate * 100).toFixed(0)}%` : "—"}</TableCell>
              <TableCell>{r.leads_generated}</TableCell>
              <TableCell>{r.closes}</TableCell>
              <TableCell className="text-right">${Number(r.revenue_usd).toFixed(0)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

import { api } from "@/lib/api";
import { Card, Title, Table, TableHead, TableHeaderCell, TableBody, TableRow, TableCell } from "@tremor/react";

export default async function FunnelPage() {
  const rows = await api.funnel(30);
  return (
    <Card>
      <Title>Daily funnel (last 30 days)</Title>
      <Table className="mt-4">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Day</TableHeaderCell>
            <TableHeaderCell>New</TableHeaderCell>
            <TableHeaderCell>DM opened</TableHeaderCell>
            <TableHeaderCell>Qualified</TableHeaderCell>
            <TableHeaderCell>Booked</TableHeaderCell>
            <TableHeaderCell>Showed</TableHeaderCell>
            <TableHeaderCell>Closed</TableHeaderCell>
            <TableHeaderCell className="text-right">Revenue</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={`${r.day}-${r.source_content_id ?? "na"}-${i}`}>
              <TableCell>{r.day}</TableCell>
              <TableCell>{r.new_leads}</TableCell>
              <TableCell>{r.dm_opened}</TableCell>
              <TableCell>{r.qualified}</TableCell>
              <TableCell>{r.booked}</TableCell>
              <TableCell>{r.showed}</TableCell>
              <TableCell>{r.closed_won}</TableCell>
              <TableCell className="text-right">${Number(r.revenue_usd).toFixed(0)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

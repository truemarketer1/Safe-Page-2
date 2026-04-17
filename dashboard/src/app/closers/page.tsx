import { api } from "@/lib/api";
import { Card, Title, Table, TableHead, TableHeaderCell, TableBody, TableRow, TableCell } from "@tremor/react";

export default async function ClosersPage() {
  const rows = await api.closers();
  return (
    <Card>
      <Title>Closer performance (AI vs human)</Title>
      <Table className="mt-4">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Closer</TableHeaderCell>
            <TableHeaderCell>Appointments</TableHeaderCell>
            <TableHeaderCell>Showed</TableHeaderCell>
            <TableHeaderCell>No-show</TableHeaderCell>
            <TableHeaderCell>Rescheduled</TableHeaderCell>
            <TableHeaderCell>Closed</TableHeaderCell>
            <TableHeaderCell>Show rate</TableHeaderCell>
            <TableHeaderCell>Close-of-shows</TableHeaderCell>
            <TableHeaderCell>Avg call</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.assigned_to}>
              <TableCell className="font-medium">{r.assigned_to}</TableCell>
              <TableCell>{r.total_appointments}</TableCell>
              <TableCell>{r.showed}</TableCell>
              <TableCell>{r.no_show}</TableCell>
              <TableCell>{r.rescheduled}</TableCell>
              <TableCell>{r.closed}</TableCell>
              <TableCell>{r.show_rate != null ? `${(r.show_rate * 100).toFixed(0)}%` : "—"}</TableCell>
              <TableCell>{r.close_rate_of_shows != null ? `${(r.close_rate_of_shows * 100).toFixed(0)}%` : "—"}</TableCell>
              <TableCell>{r.avg_call_seconds != null ? `${Math.round(r.avg_call_seconds / 60)}m` : "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

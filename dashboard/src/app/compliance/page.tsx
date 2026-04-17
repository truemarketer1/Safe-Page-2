import { Card, Title, Text } from "@tremor/react";

export default function CompliancePage() {
  return (
    <div className="space-y-4">
      <Card>
        <Title>Compliance log</Title>
        <Text>
          The CRM writes a row to <code>compliance_log</code> for every
          consent capture, opt-out, disclosure played, and pre-dial gate
          decision. Wire this page to <code>GET /api/compliance/recent</code>
          once that endpoint is added to the CRM core.
        </Text>
      </Card>
      <Card>
        <Title>Status</Title>
        <Text>
          The compliance gate service at <code>/compliance/check-*</code> is
          active; every outbound voice/SMS/DM passes through it before firing.
          View raw decisions with:
        </Text>
        <pre className="mt-2 rounded bg-slate-100 p-3 text-sm">
SELECT * FROM compliance_log ORDER BY occurred_at DESC LIMIT 200;
        </pre>
      </Card>
    </div>
  );
}

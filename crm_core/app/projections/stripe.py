"""Stripe webhooks -> payments table.

Event types:
  - stripe.payment_intent.succeeded
  - stripe.payment_intent.payment_failed
  - stripe.charge.refunded
  - stripe.payment_link.clicked  (custom event we emit from redirect tracker)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ._util import set_lifecycle_at_least, upsert_lead


def _ts(v: Any) -> datetime | None:
    if isinstance(v, int):
        return datetime.fromtimestamp(v)
    return None


def project_stripe(cur, event: dict[str, Any]) -> None:
    etype = event["event_type"]
    payload = event["payload"]
    obj = payload.get("data", {}).get("object") or payload.get("object") or payload

    email = obj.get("receipt_email") or (obj.get("customer_details") or {}).get("email")
    phone = (obj.get("customer_details") or {}).get("phone")
    metadata = obj.get("metadata") or {}

    lead_id = metadata.get("lead_id") or upsert_lead(cur, email=email, phone_e164=phone)

    pi_id = obj.get("id") if obj.get("object") == "payment_intent" else obj.get("payment_intent")
    link_id = metadata.get("payment_link_id")
    amount = obj.get("amount") or obj.get("amount_total") or 0
    currency = obj.get("currency", "usd")

    if etype == "stripe.payment_intent.succeeded":
        cur.execute(
            """INSERT INTO payments
               (lead_id, stripe_payment_intent_id, stripe_payment_link_id,
                amount_cents, currency, status, paid_at)
               VALUES (%s, %s, %s, %s, %s, 'paid', %s)
               ON CONFLICT (stripe_payment_intent_id) DO UPDATE SET
                 status  = 'paid',
                 paid_at = EXCLUDED.paid_at""",
            (lead_id, pi_id, link_id, amount, currency, _ts(obj.get("created"))),
        )
        set_lifecycle_at_least(cur, lead_id, "closed_won")

    elif etype == "stripe.payment_intent.payment_failed":
        cur.execute(
            """INSERT INTO payments
               (lead_id, stripe_payment_intent_id, amount_cents, currency, status)
               VALUES (%s, %s, %s, %s, 'failed')
               ON CONFLICT (stripe_payment_intent_id) DO UPDATE SET status = 'failed'""",
            (lead_id, pi_id, amount, currency),
        )

    elif etype == "stripe.charge.refunded":
        cur.execute(
            """UPDATE payments SET status = 'refunded', refunded_at = now()
               WHERE stripe_payment_intent_id = %s""",
            (pi_id,),
        )

    elif etype == "stripe.payment_link.clicked":
        cur.execute(
            """INSERT INTO payments
               (lead_id, stripe_payment_link_id, amount_cents, currency, status)
               VALUES (%s, %s, %s, %s, 'link_clicked')""",
            (lead_id, link_id, amount, currency),
        )

    cur.execute("UPDATE events SET lead_id = %s WHERE id = %s", (lead_id, event["id"]))

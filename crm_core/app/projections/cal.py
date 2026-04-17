"""Cal.com booking webhooks -> appointments table.

Event types (after normalisation):
  - cal.booking_created
  - cal.booking_rescheduled
  - cal.booking_cancelled
"""

from __future__ import annotations

from typing import Any

from ._util import set_lifecycle_at_least, upsert_lead


def project_cal(cur, event: dict[str, Any]) -> None:
    etype = event["event_type"]
    payload = event["payload"]
    booking = payload.get("payload") or payload  # Cal nests under "payload" in some variants
    attendees = booking.get("attendees") or []
    attendee = attendees[0] if attendees else {}

    email = attendee.get("email") or booking.get("email")
    phone = attendee.get("smsReminderNumber") or attendee.get("phoneNumber")
    name = attendee.get("name") or booking.get("name")

    lead_id = upsert_lead(
        cur,
        email=email,
        phone_e164=phone,
        full_name=name,
    )

    cal_event_id = str(booking.get("uid") or booking.get("id") or "")
    if not cal_event_id:
        return
    scheduled_for = booking.get("startTime") or booking.get("start_time")
    duration = booking.get("length") or booking.get("duration")
    appt_type = booking.get("type") or booking.get("eventType", {}).get("slug")

    if etype == "cal.booking_created":
        cur.execute(
            """INSERT INTO appointments
               (lead_id, cal_event_id, scheduled_for, duration_minutes,
                appointment_type, status, assigned_to)
               VALUES (%s, %s, %s, %s, %s, 'booked', %s)
               ON CONFLICT (cal_event_id) DO UPDATE SET
                 scheduled_for    = EXCLUDED.scheduled_for,
                 duration_minutes = EXCLUDED.duration_minutes""",
            (lead_id, cal_event_id, scheduled_for, duration, appt_type,
             booking.get("organizer", {}).get("email") or "ai_closer"),
        )
        set_lifecycle_at_least(cur, lead_id, "booked")

    elif etype == "cal.booking_rescheduled":
        cur.execute(
            """UPDATE appointments
               SET status = 'rescheduled',
                   scheduled_for = %s,
                   reschedule_count = reschedule_count + 1
               WHERE cal_event_id = %s""",
            (scheduled_for, cal_event_id),
        )
        set_lifecycle_at_least(cur, lead_id, "rescheduled")

    elif etype == "cal.booking_cancelled":
        cur.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE cal_event_id = %s",
            (cal_event_id,),
        )

    cur.execute("UPDATE events SET lead_id = %s WHERE id = %s", (lead_id, event["id"]))

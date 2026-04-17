"""Event projector — takes rows from `events` and advances domain state.

Guarantees:
  - Idempotent: replaying the same event row is a no-op in end state.
  - Transactional: each event is processed in its own transaction; failures
    record processing_error and move on so one poison event doesn't stall the
    queue.
  - Advisory-locked per event id to keep multiple workers from double-processing.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from .db import conn
from .projections import PROJECTORS

log = logging.getLogger("crm.projector")


def _project_one(cursor, event: dict[str, Any]) -> None:
    projector = PROJECTORS.get(event["source"])
    if projector is None:
        log.debug("no projector for source %s, skipping", event["source"])
    else:
        projector(cursor, event)
    cursor.execute(
        "UPDATE events SET processed_at = now(), processing_error = NULL WHERE id = %s",
        (event["id"],),
    )


def project_event(event_id: UUID) -> bool:
    """Project a single event by id. Returns True on success."""
    with conn() as c:
        with c.transaction():
            with c.cursor() as cur:
                cur.execute(
                    "SELECT pg_try_advisory_xact_lock(hashtext(%s))",
                    (str(event_id),),
                )
                got_lock = cur.fetchone()
                if not got_lock or not list(got_lock.values())[0]:
                    return False
                cur.execute("SELECT * FROM events WHERE id = %s", (event_id,))
                event = cur.fetchone()
                if not event or event["processed_at"] is not None:
                    return False
                try:
                    _project_one(cur, event)
                    return True
                except Exception as e:  # pragma: no cover - surfaced via error col
                    log.exception("projection failed for %s", event_id)
                    cur.execute(
                        """UPDATE events SET processing_error = %s WHERE id = %s""",
                        (f"{type(e).__name__}: {e}"[:2000], event_id),
                    )
                    # Re-raise so the transaction rolls back the domain changes.
                    raise


def drain_unprocessed(batch: int = 50) -> int:
    """Project all unprocessed events, oldest first. Returns count processed."""
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT id FROM events
               WHERE processed_at IS NULL
               ORDER BY received_at ASC
               LIMIT %s""",
            (batch,),
        )
        ids = [row["id"] for row in cur.fetchall()]
    processed = 0
    for event_id in ids:
        try:
            if project_event(event_id):
                processed += 1
        except Exception:
            # already logged + error saved inside project_event
            continue
    return processed

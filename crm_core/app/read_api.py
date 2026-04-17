"""Read API — powers the Next.js dashboard."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .db import fetch_all, fetch_one
from .schemas import (
    CloserRow, ContentAsset, FunnelRow, HealthResponse, HookRow, Lead,
)

router = APIRouter(prefix="/api", tags=["read"])
_auth = HTTPBearer(auto_error=False)


def require_token(creds: HTTPAuthorizationCredentials | None = Depends(_auth)) -> None:
    expected = get_settings().api_auth_token
    if not expected:
        return
    if creds is None or creds.credentials != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad token")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        fetch_one("SELECT 1 AS ok")
        return HealthResponse(ok=True, db=True)
    except Exception:
        return HealthResponse(ok=False, db=False)


@router.get("/leads/{lead_id}", response_model=Lead, dependencies=[Depends(require_token)])
def get_lead(lead_id: UUID) -> Lead:
    row = fetch_one("SELECT * FROM leads WHERE id = %s", (str(lead_id),))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "lead not found")
    return Lead(**row)


@router.get("/leads", response_model=list[Lead], dependencies=[Depends(require_token)])
def list_leads(
    stage: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> list[Lead]:
    if stage:
        rows = fetch_all(
            "SELECT * FROM leads WHERE lifecycle_stage = %s "
            "ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (stage, limit, offset),
        )
    else:
        rows = fetch_all(
            "SELECT * FROM leads ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
    return [Lead(**r) for r in rows]


@router.get("/content/{content_id}", response_model=ContentAsset,
            dependencies=[Depends(require_token)])
def get_content(content_id: UUID) -> ContentAsset:
    row = fetch_one("SELECT * FROM content_assets WHERE id = %s", (str(content_id),))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    return ContentAsset(**row)


@router.get("/metrics/funnel", response_model=list[FunnelRow],
            dependencies=[Depends(require_token)])
def funnel(since_days: int = Query(default=30, ge=1, le=365)) -> list[FunnelRow]:
    rows = fetch_all(
        """SELECT day::text, source_content_id, new_leads, dm_opened, qualified,
                  booked, showed, closed_won, revenue_usd
           FROM funnel_daily
           WHERE day >= (now() - (%s || ' days')::interval)::date
           ORDER BY day DESC""",
        (str(since_days),),
    )
    return [FunnelRow(**r) for r in rows]


@router.get("/metrics/hooks", response_model=list[HookRow],
            dependencies=[Depends(require_token)])
def hooks(order: str = "revenue_usd", limit: int = Query(default=50, le=200)) -> list[HookRow]:
    # Whitelist the sort column to avoid SQL injection.
    allowed = {
        "revenue_usd", "closes", "leads_generated", "completion_rate",
        "plays", "closes_per_100k_plays",
    }
    if order not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bad order")
    rows = fetch_all(
        f"""SELECT id, hook_text, hook_framework, cta_keyword, posted_at,
                   plays, completion_rate, comments, leads_generated, closes,
                   revenue_usd, closes_per_100k_plays
            FROM hook_leaderboard
            ORDER BY {order} DESC NULLS LAST
            LIMIT %s""",
        (limit,),
    )
    return [HookRow(**r) for r in rows]


@router.get("/metrics/closers", response_model=list[CloserRow],
            dependencies=[Depends(require_token)])
def closers() -> list[CloserRow]:
    rows = fetch_all("SELECT * FROM closer_performance ORDER BY total_appointments DESC")
    return [CloserRow(**r) for r in rows]


@router.post("/admin/refresh-views", dependencies=[Depends(require_token)])
def refresh_views() -> dict[str, str]:
    """Refresh dashboard materialized views. Call from a cron."""
    from .db import execute
    for view in ("funnel_daily", "hook_leaderboard", "closer_performance"):
        try:
            execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
        except Exception:
            # CONCURRENTLY needs an initial non-concurrent refresh once.
            execute(f"REFRESH MATERIALIZED VIEW {view}")
    return {"status": "refreshed"}

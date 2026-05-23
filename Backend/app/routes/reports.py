"""FastAPI routes for daily activity reports."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.daily_report_service import DailyReportError, get_daily_report
from app.supabase_client import SupabaseConfigError


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily")
def get_daily_activity_report(
    report_date: date | None = Query(default=None, alias="date"),
    user_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return the end-of-day activity report for one date."""

    try:
        return get_daily_report(report_date=report_date, user_id=user_id)
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except DailyReportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Daily report generation failed: {exc}",
        ) from exc

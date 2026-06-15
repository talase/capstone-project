"""Read-only message history for the dashboard."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.supabase_client import SupabaseConfigError, get_supabase_client


router = APIRouter(prefix="/message-history", tags=["message-history"])
RiskLevel = Literal["low", "medium", "high"]


class MessageHistoryItem(BaseModel):
    id: str
    message_text: str
    contact_id: str | None = None
    contact_name: str
    direction: str
    predicted_actions: list[str]
    risk_level: RiskLevel | None = None
    status: str | None = None
    confidence: float | None = None
    created_at: str


@router.get("", response_model=list[MessageHistoryItem])
def list_message_history(
    limit: int = Query(default=100, ge=1, le=200),
) -> list[MessageHistoryItem]:
    """Return recent messages with contact names for dashboard history."""

    try:
        client = get_supabase_client()
        message_response = (
            client.table("messages")
            .select(
                "id,contact_id,direction,message_text,predicted_actions,"
                "risk_level,status,confidence,created_at"
            )
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        contact_response = (
            client.table("contacts")
            .select("id,name")
            .execute()
        )
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK raises varied errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase history fetch failed: {exc}",
        ) from exc

    contacts = {
        str(row["id"]): str(row.get("name") or "Unknown contact")
        for row in (getattr(contact_response, "data", None) or [])
        if isinstance(row, dict) and row.get("id")
    }

    history: list[MessageHistoryItem] = []
    for row in getattr(message_response, "data", None) or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue

        contact_id = str(row["contact_id"]) if row.get("contact_id") else None
        actions = row.get("predicted_actions")
        if not isinstance(actions, list):
            actions = []

        history.append(
            MessageHistoryItem(
                id=str(row["id"]),
                message_text=str(row.get("message_text") or ""),
                contact_id=contact_id,
                contact_name=contacts.get(contact_id or "", "Unknown contact"),
                direction=str(row.get("direction") or "unknown"),
                predicted_actions=[
                    str(action) for action in actions if str(action).strip()
                ],
                risk_level=_risk_level(row.get("risk_level")),
                status=str(row["status"]) if row.get("status") else None,
                confidence=_confidence(row.get("confidence")),
                created_at=str(row.get("created_at") or ""),
            )
        )

    return history


def _risk_level(value: object) -> RiskLevel | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"low", "medium", "high"} else None


def _confidence(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

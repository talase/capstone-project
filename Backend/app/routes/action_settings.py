"""FastAPI routes for user-configurable action risk settings."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.supabase_client import SupabaseConfigError, get_supabase_client


router = APIRouter(prefix="/action-settings", tags=["action-settings"])
RiskLevel = Literal["low", "medium", "high"]


class ActionSettingUpdate(BaseModel):
    risk_level: RiskLevel


@router.get("")
def list_action_settings(
    user_id: str = Query(default="default_user"),
) -> list[dict[str, Any]]:
    """Return the action risk policy for one user."""

    clean_user_id = user_id.strip()
    if not clean_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id cannot be empty.",
        )

    response = _execute_supabase_call(
        lambda: (
            get_supabase_client()
            .table("action_settings")
            .select(
                "id,user_id,action_type,risk_level,is_editable,"
                "description,created_at,updated_at"
            )
            .eq("user_id", clean_user_id)
            .order("action_type")
            .execute()
        ),
        action="fetch",
    )
    return getattr(response, "data", None) or []


@router.patch("/{setting_id}")
def update_action_setting(
    setting_id: str,
    update: ActionSettingUpdate,
    user_id: str = Query(default="default_user"),
) -> dict[str, Any]:
    """Update an editable action setting while enforcing system locks."""

    clean_user_id = user_id.strip()
    if not clean_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id cannot be empty.",
        )

    current = _get_setting_or_404(setting_id, clean_user_id)
    if not current.get("is_editable", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action risk level is fixed by the system.",
        )

    response = _execute_supabase_call(
        lambda: (
            get_supabase_client()
            .table("action_settings")
            .update({"risk_level": update.risk_level})
            .eq("id", setting_id)
            .eq("user_id", clean_user_id)
            .execute()
        ),
        action="update",
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action setting not found.",
        )
    return rows[0]


def _get_setting_or_404(setting_id: str, user_id: str) -> dict[str, Any]:
    response = _execute_supabase_call(
        lambda: (
            get_supabase_client()
            .table("action_settings")
            .select("*")
            .eq("id", setting_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        ),
        action="fetch",
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action setting not found.",
        )
    return rows[0]


def _execute_supabase_call(callback, *, action: str):
    try:
        response = callback()
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK raises varied errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase {action} failed: {exc}",
        ) from exc

    response_error = getattr(response, "error", None)
    if response_error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase {action} failed: {response_error}",
        )
    return response

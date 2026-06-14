"""FastAPI routes for status-based Personal Context Memory."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from app.personal_context_service import (
    PersonalContext,
    PersonalContextError,
    UserStatus,
    UserStatusSet,
    UserStatusUpdate,
    build_personal_context,
    clear_user_status,
    get_current_user_status,
    set_user_status,
    update_user_status,
)
from app.supabase_client import SupabaseConfigError


router = APIRouter(prefix="/personal-context", tags=["personal-context"])


class PersonalContextEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str = "default_user"


@router.post("/evaluate", response_model=PersonalContext)
def evaluate_personal_context(
    request: PersonalContextEvaluateRequest,
) -> dict[str, Any]:
    return _handle_service_call(lambda: _evaluate_personal_context(request))


@router.post("/status", response_model=UserStatus)
def set_current_status(status_request: UserStatusSet) -> dict[str, Any]:
    return _handle_service_call(lambda: set_user_status(status_request))


@router.get("/status", response_model=UserStatus)
def get_current_status(
    user_id: str = Query(default="default_user"),
) -> dict[str, Any]:
    return _handle_service_call(lambda: get_current_user_status(user_id))


@router.patch("/status", response_model=UserStatus)
def update_current_status(
    updates: UserStatusUpdate,
    user_id: str = Query(default="default_user"),
) -> dict[str, Any]:
    return _handle_service_call(lambda: update_user_status(user_id, updates))


@router.delete("/status", response_model=UserStatus)
def clear_current_status(
    user_id: str = Query(default="default_user"),
) -> dict[str, Any]:
    return _handle_service_call(lambda: clear_user_status(user_id))


def _evaluate_personal_context(
    request: PersonalContextEvaluateRequest,
) -> dict[str, Any]:
    current_status = get_current_user_status(request.user_id)
    return build_personal_context(current_status.get("status"))


def _handle_service_call(callback):
    try:
        return callback()
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PersonalContextError as exc:
        message = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:  # pragma: no cover - defensive API boundary
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Personal context service failed: {exc}",
        ) from exc

"""FastAPI routes for status-based Personal Context Memory."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app import daily_activity_logger as activity_logger
from app.personal_context_service import (
    PersonalContextError,
    UserStatus,
    UserStatusSet,
    UserStatusUpdate,
    clear_user_status,
    evaluate_personal_context as evaluate_status_context,
    get_current_user_status,
    set_user_status,
    update_user_status,
)
from app.supabase_client import SupabaseConfigError


router = APIRouter(prefix="/personal-context", tags=["personal-context"])


class PersonalContextEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(..., min_length=1)
    user_id: str = "default_user"
    contact_id: str | None = None
    action_type: str | None = None


@router.post("/evaluate")
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
    message_data = request.model_dump(exclude_none=True)
    current_status = get_current_user_status(request.user_id)
    message_data["user_status"] = current_status["status"]
    result = evaluate_status_context(message_data)
    _log_evaluation_activity(
        message_data=message_data,
        result=result,
    )

    return {
        "current_status": result["current_status"],
        "decision": result["decision"],
        "reason": result["reason"],
        "final_action": result["final_action"],
    }


def _log_evaluation_activity(
    *,
    message_data: dict[str, Any],
    result: dict[str, Any],
) -> list[dict[str, str]]:
    logging_warnings: list[dict[str, str]] = []
    user_id = message_data.get("user_id") or "default_user"
    contact_id = message_data.get("contact_id")
    action_type = message_data.get("action") or message_data.get("action_type")

    _collect_logging_warning(
        logging_warnings,
        activity_logger.log_personal_context_decision(
            decision=result["decision"],
            user_id=user_id,
            contact_id=contact_id,
            reason=result.get("reason"),
            final_action=result["final_action"],
            original_message=message_data.get("message"),
            metadata={
                "action_type": action_type,
                "context": result.get("context", []),
                "current_status": result["current_status"],
                "final_action": result["final_action"],
                "source": "personal_context_evaluate",
            },
        ),
    )
    _collect_logging_warning(
        logging_warnings,
        activity_logger.log_agent_activity(
            status="deferred" if result["decision"] == "defer" else "automatic",
            user_id=user_id,
            contact_id=contact_id,
            action_category=action_type,
            action_type=action_type,
            mode="automatic" if result["decision"] == "auto_reply" else None,
            requires_approval=False,
            description=result.get("reason"),
            metadata={
                "pcm_decision": result["decision"],
                "source": "personal_context_evaluate",
            },
        ),
    )

    return logging_warnings


def _collect_logging_warning(
    warnings: list[dict[str, str]],
    result: activity_logger.LogResult,
) -> None:
    warning = result.warning()
    if warning:
        warnings.append(warning)


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

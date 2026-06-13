"""FastAPI routes for Personal Context Memory rule management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app import daily_activity_logger as activity_logger
from app.personal_context_service import (
    PersonalContextError,
    PersonalContextRule,
    PersonalContextRuleCreate,
    PersonalContextRuleUpdate,
    UserStatus,
    UserStatusSet,
    UserStatusUpdate,
    clear_user_status,
    create_rule,
    delete_rule,
    evaluate_personal_context_rules,
    get_current_user_status,
    list_active_rules,
    list_rules,
    set_rule_active,
    set_user_status,
    update_user_status,
    update_rule,
)
from app.supabase_client import SupabaseConfigError


router = APIRouter(prefix="/personal-context", tags=["personal-context"])


class PersonalContextEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str = Field(..., min_length=1)
    user_id: str = "default_user"
    contact_id: str | None = None
    profile_contact: str | None = None
    contact_name: str | None = None
    risk_level: str | None = None
    topic: str | None = None
    action: str | None = None
    action_type: str | None = None
    user_status: str | None = None
    availability: str | None = None
    status_reason: str | None = None
    current_time: str | None = None


@router.post(
    "/rules",
    response_model=PersonalContextRule,
    status_code=status.HTTP_201_CREATED,
)
def create_personal_context_rule(rule: PersonalContextRuleCreate) -> dict[str, Any]:
    return _handle_service_call(lambda: create_rule(rule))


@router.get("/rules", response_model=list[PersonalContextRule])
def get_personal_context_rules(
    user_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    return _handle_service_call(lambda: list_rules(user_id=user_id))


@router.get("/rules/active", response_model=list[PersonalContextRule])
def get_active_personal_context_rules(
    user_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    return _handle_service_call(lambda: list_active_rules(user_id=user_id))


@router.post("/evaluate")
def evaluate_personal_context(
    request: PersonalContextEvaluateRequest,
) -> dict[str, Any]:
    return _handle_service_call(lambda: _evaluate_personal_context(request))


@router.put("/rules/{rule_id}", response_model=PersonalContextRule)
def update_personal_context_rule(
    rule_id: int | str,
    updates: PersonalContextRuleUpdate,
) -> dict[str, Any]:
    return _handle_service_call(lambda: update_rule(rule_id, updates))


@router.delete("/rules/{rule_id}")
def delete_personal_context_rule(rule_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: delete_rule(rule_id))


@router.patch("/rules/{rule_id}/activate", response_model=PersonalContextRule)
def activate_personal_context_rule(rule_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_rule_active(rule_id, True))


@router.patch("/rules/{rule_id}/deactivate", response_model=PersonalContextRule)
def deactivate_personal_context_rule(rule_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_rule_active(rule_id, False))


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
    message_data["action"] = message_data.get("action") or message_data.get("action_type")
    message_data["topic"] = message_data.get("topic")

    current_status = None
    if not message_data.get("user_status") and not message_data.get("availability"):
        current_status = get_current_user_status(request.user_id)
        message_data["user_status"] = current_status["status"]
        message_data["availability"] = current_status["status"]
        message_data["status_reason"] = current_status.get("status_reason")
    else:
        supplied_status = (
            message_data.get("user_status")
            or message_data.get("availability")
            or "available"
        )
        current_status = {
            "id": None,
            "user_id": request.user_id,
            "status": supplied_status,
            "status_reason": message_data.get("status_reason"),
            "expires_at": None,
            "is_active": True,
        }

    rules = list_active_rules(user_id=request.user_id)
    result = evaluate_personal_context_rules(message_data, rules)
    personal_context = {
        **result,
        "current_status": current_status,
    }
    logging_warnings = _log_evaluation_activity(
        message_data=message_data,
        result=result,
    )

    return {
        **personal_context,
        "current_status": current_status,
        "personal_context": personal_context,
        "daily_report_logging_warnings": logging_warnings,
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
            matched_rules=result.get("matched_rules", []),
            original_message=message_data.get("message"),
            metadata={
                "action_type": action_type,
                "context": result.get("context", []),
                "current_status": message_data.get("user_status"),
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

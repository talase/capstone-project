"""FastAPI routes for Personal Context Memory rule management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app import daily_activity_logger as activity_logger
from app.personal_context_service import (
    ApprovalRequest,
    ApprovalRequestCreate,
    PersonalContextError,
    PersonalContextRule,
    PersonalContextRuleCreate,
    PersonalContextRuleUpdate,
    UserStatus,
    UserStatusSet,
    UserStatusUpdate,
    clear_user_status,
    create_approval_request,
    create_rule,
    delete_rule,
    evaluate_personal_context_rules,
    get_approval_request,
    get_current_user_status,
    list_approvals,
    list_active_rules,
    list_rules,
    set_approval_status,
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


@router.post(
    "/approvals",
    response_model=ApprovalRequest,
    status_code=status.HTTP_201_CREATED,
)
def create_pending_approval(request: ApprovalRequestCreate) -> dict[str, Any]:
    return _handle_service_call(lambda: create_approval_request(request))


@router.get("/approvals", response_model=list[ApprovalRequest])
def get_approvals(
    user_id: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
) -> list[dict[str, Any]]:
    return _handle_service_call(
        lambda: list_approvals(user_id=user_id, status=status)
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalRequest)
def get_one_approval_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: get_approval_request(approval_id))


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRequest)
def approve_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_approval_status(approval_id, "approved"))


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRequest)
def reject_request(approval_id: int | str) -> dict[str, Any]:
    return _handle_service_call(lambda: set_approval_status(approval_id, "rejected"))


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
    message_data["topic"] = message_data.get("topic") or message_data.get("risk_level")

    current_status = None
    if not message_data.get("user_status") and not message_data.get("availability"):
        current_status = get_current_user_status(request.user_id)
        message_data["user_status"] = current_status["status"]
        message_data["availability"] = current_status["status"]

    rules = list_active_rules(user_id=request.user_id)
    result = evaluate_personal_context_rules(message_data, rules)
    result = _enforce_high_risk_approval(message_data, result)
    final_action = _final_action_for_decision(result["decision"])
    personal_context = _personal_context_payload(result)
    logging_warnings = _log_evaluation_activity(
        message_data=message_data,
        result=result,
        final_action=final_action,
    )

    return {
        **result,
        "final_action": final_action,
        "current_status": current_status,
        "personal_context": personal_context,
        "daily_report_logging_warnings": logging_warnings,
    }


def _enforce_high_risk_approval(
    message_data: dict[str, Any],
    personal_context: dict[str, Any],
) -> dict[str, Any]:
    if not _is_high_risk(message_data.get("risk_level")):
        return personal_context

    matched_rules = list(personal_context.get("matched_rules", []))
    matched_rules.append(
        {
            "id": "system_high_risk_gate",
            "rule_name": "High risk messages require approval",
            "rule_type": "system_governance",
            "decision": "require_approval",
            "priority": 999,
        }
    )
    return {
        "decision": "require_approval",
        "matched_rules": matched_rules,
        "winning_rule": matched_rules[-1],
        "reason": "High-risk message requires approval before sending.",
        "fallback_used": personal_context.get("fallback_used", False),
    }


def _personal_context_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": result["decision"],
        "reason": result.get("reason"),
        "matched_rules": result.get("matched_rules", []),
        "winning_rule": result.get("winning_rule"),
        "fallback_used": result.get("fallback_used", False),
    }


def _final_action_for_decision(decision: str) -> str:
    return {
        "auto_reply": "send",
        "draft_only": "draft",
        "require_approval": "approval_required",
        "defer": "deferred",
        "blocked": "blocked",
    }.get(decision, "approval_required")


def _is_high_risk(risk_level: str | None) -> bool:
    return str(risk_level or "").strip().lower() in {"high", "high_risk", "critical"}


def _log_evaluation_activity(
    *,
    message_data: dict[str, Any],
    result: dict[str, Any],
    final_action: str,
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
            final_action=final_action,
            metadata={
                "risk_level": message_data.get("risk_level"),
                "action_type": action_type,
                "source": "personal_context_evaluate",
            },
        ),
    )
    _collect_logging_warning(
        logging_warnings,
        activity_logger.log_agent_activity(
            status=_activity_status_for_final_action(final_action),
            user_id=user_id,
            contact_id=contact_id,
            action_category=action_type,
            action_type=action_type,
            mode="automatic" if final_action == "send" else None,
            requires_approval=final_action == "approval_required",
            description=result.get("reason"),
            metadata={
                "pcm_decision": result["decision"],
                "risk_level": message_data.get("risk_level"),
                "source": "personal_context_evaluate",
            },
        ),
    )
    if _is_high_risk(message_data.get("risk_level")):
        _collect_logging_warning(
            logging_warnings,
            activity_logger.log_high_risk_alert(
                risk_level=message_data.get("risk_level") or "high",
                user_id=user_id,
                contact_id=contact_id,
                action_category=action_type,
                message=message_data.get("message"),
                reason=result.get("reason"),
                metadata={
                    "final_action": final_action,
                    "matched_rules": result.get("matched_rules", []),
                    "source": "personal_context_evaluate",
                },
            ),
        )

    return logging_warnings


def _activity_status_for_final_action(final_action: str) -> str:
    return {
        "send": "automatic",
        "draft": "draft",
        "approval_required": "pending",
        "deferred": "deferred",
        "blocked": "blocked",
    }.get(final_action, "pending")


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

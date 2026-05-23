import unittest
from unittest.mock import patch

from app.daily_activity_logger import LogResult
from app.style_engine import generate_style_adapted_response


class DailyActivityLoggingIntegrationTests(unittest.TestCase):
    def test_message_processing_writes_report_logs(self):
        with (
            patch("app.style_engine.resolve_profile_contact", return_value="friend"),
            patch("app.style_engine.load_global_profile", return_value={"overall_confidence": 90}),
            patch("app.style_engine.load_profile", return_value={"overall_confidence": 80}),
            patch("app.style_engine.choose_style_mode", return_value="contact"),
            patch(
                "app.style_engine._get_current_status",
                return_value={"status": "available"},
            ),
            patch(
                "app.style_engine._evaluate_personal_context",
                return_value={
                    "decision": "auto_reply",
                    "matched_rules": [],
                    "reason": "No personal context rule matched; auto reply is allowed.",
                },
            ),
            patch(
                "app.style_engine.generate_styled_reply_result",
                return_value={
                    "reply": "Sure, I can help.",
                    "generation_status": "generated",
                    "llm_error": False,
                },
            ),
            patch(
                "app.style_engine.activity_logger.log_message_event",
                return_value=LogResult(ok=True, table="message_logs"),
            ) as log_message_event,
            patch(
                "app.style_engine.activity_logger.log_agent_activity",
                return_value=LogResult(ok=True, table="agent_activity_logs"),
            ) as log_agent_activity,
            patch(
                "app.style_engine.activity_logger.log_personal_context_decision",
                return_value=LogResult(ok=True, table="personal_context_decision_logs"),
            ) as log_personal_context_decision,
            patch(
                "app.style_engine.activity_logger.log_high_risk_alert",
                return_value=LogResult(ok=True, table="high_risk_alerts"),
            ) as log_high_risk_alert,
        ):
            result = generate_style_adapted_response(
                incoming_message="Can you reply to Sara?",
                contact_id="friend",
                user_id="user-1",
                risk_level="low",
                action_type="request_to_send_message",
            )

        self.assertEqual(result["final_action"], "send")
        self.assertEqual(log_message_event.call_count, 2)
        self.assertEqual(log_message_event.call_args_list[0].kwargs["direction"], "received")
        self.assertEqual(log_message_event.call_args_list[1].kwargs["direction"], "sent")
        log_agent_activity.assert_called_once()
        self.assertEqual(log_agent_activity.call_args.kwargs["status"], "automatic")
        self.assertEqual(
            log_agent_activity.call_args.kwargs["action_category"],
            "request_to_send_message",
        )
        log_personal_context_decision.assert_called_once()
        self.assertEqual(
            log_personal_context_decision.call_args.kwargs["decision"],
            "auto_reply",
        )
        log_high_risk_alert.assert_not_called()

    def test_high_risk_message_writes_alert_log(self):
        with (
            patch("app.style_engine.resolve_profile_contact", return_value="friend"),
            patch("app.style_engine.load_global_profile", return_value={"overall_confidence": 90}),
            patch("app.style_engine.load_profile", return_value={"overall_confidence": 80}),
            patch("app.style_engine.choose_style_mode", return_value="contact"),
            patch(
                "app.style_engine._get_current_status",
                return_value={"status": "available"},
            ),
            patch(
                "app.style_engine._evaluate_personal_context",
                return_value={
                    "decision": "require_approval",
                    "matched_rules": [{"id": "system_high_risk_gate"}],
                    "reason": "High-risk message requires approval before sending.",
                },
            ),
            patch(
                "app.style_engine.generate_styled_reply_result",
                return_value={
                    "reply": "Draft reply",
                    "generation_status": "generated",
                    "llm_error": False,
                },
            ),
            patch("app.style_engine._create_pending_approval_request", return_value={"id": 7}),
            patch(
                "app.style_engine.activity_logger.log_message_event",
                return_value=LogResult(ok=True, table="message_logs"),
            ),
            patch(
                "app.style_engine.activity_logger.log_agent_activity",
                return_value=LogResult(ok=True, table="agent_activity_logs"),
            ),
            patch(
                "app.style_engine.activity_logger.log_personal_context_decision",
                return_value=LogResult(ok=True, table="personal_context_decision_logs"),
            ),
            patch(
                "app.style_engine.activity_logger.log_high_risk_alert",
                return_value=LogResult(ok=True, table="high_risk_alerts"),
            ) as log_high_risk_alert,
        ):
            result = generate_style_adapted_response(
                incoming_message="Send my passport file now",
                contact_id="friend",
                user_id="user-1",
                risk_level="high",
                action_type="request_sending_sensitive_file",
            )

        self.assertEqual(result["final_action"], "approval_required")
        log_high_risk_alert.assert_called_once()
        self.assertEqual(log_high_risk_alert.call_args.kwargs["risk_level"], "high")
        self.assertEqual(
            log_high_risk_alert.call_args.kwargs["action_category"],
            "request_sending_sensitive_file",
        )

    def test_logging_failure_returns_warning_without_blocking_response(self):
        with (
            patch("app.style_engine.resolve_profile_contact", return_value="friend"),
            patch("app.style_engine.load_global_profile", return_value={"overall_confidence": 90}),
            patch("app.style_engine.load_profile", return_value={"overall_confidence": 80}),
            patch("app.style_engine.choose_style_mode", return_value="contact"),
            patch(
                "app.style_engine._get_current_status",
                return_value={"status": "available"},
            ),
            patch(
                "app.style_engine._evaluate_personal_context",
                return_value={
                    "decision": "auto_reply",
                    "matched_rules": [],
                    "reason": "No personal context rule matched; auto reply is allowed.",
                },
            ),
            patch(
                "app.style_engine.generate_styled_reply_result",
                return_value={
                    "reply": "Still generated",
                    "generation_status": "generated",
                    "llm_error": False,
                },
            ),
            patch(
                "app.style_engine.activity_logger.log_message_event",
                return_value=LogResult(
                    ok=False,
                    table="message_logs",
                    error="Supabase unavailable",
                ),
            ),
            patch(
                "app.style_engine.activity_logger.log_agent_activity",
                return_value=LogResult(ok=True, table="agent_activity_logs"),
            ),
            patch(
                "app.style_engine.activity_logger.log_personal_context_decision",
                return_value=LogResult(ok=True, table="personal_context_decision_logs"),
            ),
        ):
            result = generate_style_adapted_response(
                incoming_message="Hello",
                contact_id="friend",
            )

        self.assertEqual(result["reply"], "Still generated")
        self.assertEqual(
            result["daily_report_logging_warnings"][0]["table"],
            "message_logs",
        )

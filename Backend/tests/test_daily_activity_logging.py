import unittest
from unittest.mock import patch

from app.daily_activity_logger import LogResult
from app.style_engine import generate_style_adapted_response


class DailyActivityLoggingIntegrationTests(unittest.TestCase):
    def test_auto_reply_passes_personal_context_to_generation(self):
        personal_context = {
            "current_status": {"status": "Traveling with limited signal."},
            "decision": "auto_reply",
            "final_action": "auto_reply",
            "context": ["The user's current status is: Traveling with limited signal."],
            "reason": "Reply generation may continue using the current user context.",
        }
        with (
            self._base_patches(personal_context),
            patch(
                "app.style_engine.generate_styled_reply_result",
                return_value={
                    "reply": "I am traveling right now, but I will reply soon.",
                    "generation_status": "generated",
                    "llm_error": False,
                },
            ) as generate_reply,
            patch(
                "app.style_engine.activity_logger.log_message_event",
                return_value=LogResult(ok=True, table="message_logs"),
            ) as log_message,
            patch(
                "app.style_engine.activity_logger.log_agent_activity",
                return_value=LogResult(ok=True, table="agent_activity_logs"),
            ),
            patch(
                "app.style_engine.activity_logger.log_personal_context_decision",
                return_value=LogResult(ok=True, table="personal_context_decision_logs"),
            ),
        ):
            result = generate_style_adapted_response("Are you free?", "friend")

        self.assertTrue(result["send_allowed"])
        self.assertEqual(result["handling_status"], "ready_to_send")
        self.assertEqual(result["pcm_decision"], "auto_reply")
        self.assertEqual(result["final_action"], "auto_reply")
        prompt_context = generate_reply.call_args.kwargs["personal_context"]
        self.assertEqual(prompt_context["context"], personal_context["context"])
        self.assertEqual(
            prompt_context["current_status"],
            {"status": "Traveling with limited signal."},
        )
        self.assertEqual(log_message.call_count, 2)

    def test_defer_stops_before_generation(self):
        personal_context = {
            "current_status": {"status": "in_meeting"},
            "decision": "defer",
            "final_action": "defer",
            "context": ["The user is in a meeting."],
            "reason": "The current status requested reevaluation later.",
        }
        with (
            self._base_patches(personal_context),
            patch("app.style_engine.generate_styled_reply_result") as generate_reply,
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
        ):
            result = generate_style_adapted_response("Hello", "friend")

        self.assertEqual(result["handling_status"], "deferred")
        self.assertFalse(result["send_allowed"])
        self.assertIsNone(result["reply"])
        generate_reply.assert_not_called()

    def test_high_risk_approval_does_not_change_pcm_decision(self):
        personal_context = {
            "current_status": {"status": "available"},
            "decision": "auto_reply",
            "final_action": "auto_reply",
            "context": [],
            "reason": "No relevant personal context was found.",
        }
        with (
            self._base_patches(personal_context),
            patch(
                "app.style_engine.generate_styled_reply_result",
                return_value={
                    "reply": "Draft reply",
                    "generation_status": "generated",
                    "llm_error": False,
                },
            ),
            patch(
                "app.style_engine._create_pending_approval_request",
                return_value={"id": 7, "status": "pending"},
            ),
            patch(
                "app.style_engine.activity_logger.log_message_event",
                return_value=LogResult(ok=True, table="message_logs"),
            ) as log_message,
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
            ),
        ):
            result = generate_style_adapted_response(
                "Send my passport",
                "friend",
                risk_level="high",
            )

        self.assertEqual(result["pcm_decision"], "auto_reply")
        self.assertTrue(result["risk_approval"]["required"])
        self.assertFalse(result["send_allowed"])
        self.assertEqual(result["handling_status"], "awaiting_approval")
        self.assertEqual(log_message.call_count, 1)

    @staticmethod
    def _base_patches(personal_context):
        class _Patches:
            def __enter__(self):
                self.stack = [
                    patch("app.style_engine.resolve_profile_contact", return_value="friend"),
                    patch(
                        "app.style_engine.load_global_profile",
                        return_value={"overall_confidence": 90},
                    ),
                    patch(
                        "app.style_engine.load_profile",
                        return_value={"overall_confidence": 80},
                    ),
                    patch("app.style_engine.choose_style_mode", return_value="contact"),
                    patch(
                        "app.style_engine._get_current_status",
                        return_value={
                            "status": "Traveling with limited signal.",
                        },
                    ),
                    patch(
                        "app.style_engine._evaluate_personal_context",
                        return_value=personal_context,
                    ),
                ]
                for item in self.stack:
                    item.start()
                return self

            def __exit__(self, *_args):
                for item in reversed(self.stack):
                    item.stop()

        return _Patches()


if __name__ == "__main__":
    unittest.main()

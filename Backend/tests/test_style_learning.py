import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.profile_store import neutral_profile
from app.prompt_templates import build_prompt
from app.routes.style import router as style_router
from app.style_learning_service import (
    _build_training_pairs,
    _fetch_conversation_messages,
    process_pending_style_learning,
)
from app.style_extractor import build_extraction_prompt, extract_style_patterns


class StylePatternExtractorTests(unittest.TestCase):
    def test_extracts_conversational_patterns(self):
        patterns = extract_style_patterns(
            ["heyyy!! sounds good 😂", "sureee, lmk rn", "okay? no worries ❤️"]
        )

        self.assertIn("heyyy", patterns["greetings"])
        self.assertIn("sounds good", patterns["common_phrases"])
        self.assertIn("sure", patterns["common_phrases"])
        self.assertIn("lmk", patterns["common_phrases"])
        self.assertEqual(patterns["emoji_usage"], ["😂", "❤️"])
        self.assertTrue(patterns["punctuation_style"]["uses_exclamation"])
        self.assertTrue(patterns["punctuation_style"]["uses_repeated_letters"])
        self.assertEqual(patterns["punctuation_style"]["question_frequency"], 1)
        self.assertIn("casual", patterns["tone_indicators"])
        self.assertIn("warm", patterns["tone_indicators"])
        behavior = patterns["conversation_behavior"]
        self.assertEqual(behavior["reply_length_style"], "brief")
        self.assertEqual(behavior["acknowledgment_style"], "warm")
        self.assertEqual(behavior["helpfulness_mode"], "friend")
        self.assertFalse(behavior["uses_assistant_closings"])

    def test_different_contacts_produce_different_patterns(self):
        friend = extract_style_patterns(["heyyy!! lmk rn 😂"])
        manager = extract_style_patterns(
            ["Hello, could you please review this?", "Thank you. Regards."]
        )

        self.assertNotEqual(friend, manager)
        self.assertIn("casual", friend["tone_indicators"])
        self.assertIn("formal", manager["tone_indicators"])
        self.assertNotIn("😂", manager["emoji_usage"])
        self.assertEqual(
            manager["conversation_behavior"]["helpfulness_mode"], "professional"
        )

    def test_empty_messages_have_safe_defaults(self):
        patterns = extract_style_patterns([])

        self.assertEqual(patterns["greetings"], [])
        self.assertEqual(patterns["punctuation_style"]["question_frequency"], 0)
        self.assertEqual(patterns["tone_indicators"], [])
        self.assertEqual(
            patterns["conversation_behavior"],
            {
                "reply_length_style": "medium",
                "asks_followup_often": False,
                "uses_assistant_closings": False,
                "acknowledgment_style": "short",
                "helpfulness_mode": "friend",
            },
        )

    def test_detects_assistant_closings_and_followup_behavior(self):
        patterns = extract_style_patterns(
            [
                "How can I help with that?",
                "Anything else?",
                "Let me know if you need anything.",
            ]
        )

        behavior = patterns["conversation_behavior"]
        self.assertTrue(behavior["uses_assistant_closings"])
        self.assertTrue(behavior["asks_followup_often"])
        self.assertEqual(behavior["helpfulness_mode"], "assistant")


class StyleLearnRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(style_router)
        self.client = TestClient(app)

    @patch("app.style_learning_service.update_profile")
    @patch("app.style_learning_service.extract_style_profile")
    def test_learn_persists_patterns_for_requested_contact(
        self, extract_profile, update_profile
    ):
        extracted = neutral_profile(message_count=2, batch_count=1)
        extracted["overall_confidence"] = 82
        extract_profile.return_value = extracted
        update_profile.side_effect = lambda profile, contact, user_id: profile

        response = self.client.post(
            "/style/learn",
            json={
                "user_id": "user-1",
                "contact_id": "close-friend",
                "messages": ["heyyy 😂", "lmk rn"],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["contact_id"], "close-friend")
        self.assertIn("heyyy", body["patterns"]["greetings"])
        update_profile.assert_called_once()
        self.assertEqual(update_profile.call_args.kwargs["contact"], "close-friend")
        self.assertEqual(update_profile.call_args.kwargs["user_id"], "user-1")

    def test_learn_accepts_empty_messages_with_defaults(self):
        response = self.client.post(
            "/style/learn",
            json={"user_id": "user-1", "contact_id": "friend", "messages": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["patterns"]["greetings"], [])
        self.assertEqual(response.json()["message_count"], 0)

    @patch("app.style_learning_service.update_profile")
    @patch("app.style_learning_service.extract_style_profile")
    def test_learn_uses_context_for_llm_but_patterns_only_from_reply(
        self, extract_profile, update_profile
    ):
        extracted = neutral_profile(message_count=1, batch_count=1)
        extract_profile.return_value = extracted
        update_profile.side_effect = lambda profile, contact, user_id: profile

        response = self.client.post(
            "/style/learn",
            json={
                "user_id": "user-1",
                "contact_id": "manager",
                "messages": [
                    {
                        "context": "HEYYY!!! sounds good 😂",
                        "reply": "Thank you. I will review it.",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        extract_profile.assert_called_once_with(
            [
                {
                    "context": "HEYYY!!! sounds good 😂",
                    "reply": "Thank you. I will review it.",
                }
            ],
            contact="manager",
        )
        patterns = response.json()["patterns"]
        self.assertNotIn("heyyy", patterns["greetings"])
        self.assertNotIn("sounds good", patterns["common_phrases"])
        self.assertNotIn("😂", patterns["emoji_usage"])
        self.assertIn("formal", patterns["tone_indicators"])

    @patch("app.style_learning_service.update_profile")
    @patch("app.style_learning_service.extract_style_profile")
    def test_learn_accepts_incoming_message_user_reply_pairs(
        self, extract_profile, update_profile
    ):
        extracted = neutral_profile(message_count=1, batch_count=1)
        extract_profile.return_value = extracted
        update_profile.side_effect = lambda profile, contact, user_id: profile

        response = self.client.post(
            "/style/learn",
            json={
                "user_id": "user-1",
                "contact_id": "friend",
                "messages": [
                    {
                        "incoming_message": "Are you free?",
                        "user_reply": "Yep, after 3.",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        extract_profile.assert_called_once_with(
            [{"context": "Are you free?", "reply": "Yep, after 3."}],
            contact="friend",
        )

    @patch("app.routes.style.process_pending_style_learning")
    def test_pending_endpoint_returns_batch_summary(self, process_pending):
        process_pending.return_value = {
            "global_updated": True,
            "global_message_count": 20,
            "contacts_updated": [{"contact_id": "friend", "message_count": 20}],
            "skipped_contacts": [
                {
                    "contact_id": "manager",
                    "available_messages": 12,
                    "reason": "less than 20 messages",
                }
            ],
        }

        response = self.client.post(
            "/style/learn/pending",
            json={"user_id": "user-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), process_pending.return_value)
        process_pending.assert_called_once_with("user-1")


class PendingStyleLearningTests(unittest.TestCase):
    @patch("app.style_learning_service._mark_messages_processed")
    @patch("app.style_learning_service.learn_style_messages")
    @patch("app.style_learning_service._fetch_conversation_messages")
    def test_processes_pairs_and_marks_only_outgoing_replies(
        self,
        fetch_messages,
        learn_messages,
        mark_processed,
    ):
        friend_rows, friend_outgoing_ids = _conversation_rows("friend", 20, 1)
        manager_rows, _ = _conversation_rows("manager", 19, 1001)
        fetch_messages.return_value = [
            *friend_rows,
            *manager_rows,
        ]

        result = process_pending_style_learning("user-1")

        self.assertTrue(result["global_updated"])
        self.assertEqual(result["global_message_count"], 20)
        self.assertEqual(
            result["contacts_updated"],
            [{"contact_id": "friend", "message_count": 20}],
        )
        self.assertEqual(
            result["skipped_contacts"],
            [
                {
                    "contact_id": "manager",
                    "available_messages": 19,
                    "reason": "less than 20 messages",
                }
            ],
        )
        self.assertEqual(learn_messages.call_count, 2)
        self.assertEqual(
            learn_messages.call_args_list[0].kwargs,
            {
                "contact_id": "global",
                "user_id": "user-1",
            },
        )
        self.assertEqual(
            learn_messages.call_args_list[1].kwargs,
            {
                "contact_id": "friend",
                "user_id": "user-1",
            },
        )
        global_learning_input = learn_messages.call_args_list[0].args[0]
        self.assertEqual(len(global_learning_input), 20)
        self.assertEqual(
            global_learning_input[0],
            {
                "incoming_message": "incoming 1",
                "user_reply": "outgoing 2",
            },
        )
        self.assertEqual(
            mark_processed.call_args_list[0].args,
            (friend_outgoing_ids, "global_style_processed"),
        )
        self.assertEqual(
            mark_processed.call_args_list[1].args,
            (friend_outgoing_ids, "contact_style_processed"),
        )
        incoming_ids = {row["id"] for row in friend_rows if row["direction"] == "incoming"}
        marked_ids = {
            message_id
            for call in mark_processed.call_args_list
            for message_id in call.args[0]
        }
        self.assertTrue(incoming_ids.isdisjoint(marked_ids))

    @patch("app.style_learning_service._mark_messages_processed")
    @patch("app.style_learning_service.learn_style_messages")
    @patch("app.style_learning_service._fetch_conversation_messages")
    def test_contact_learning_runs_when_global_batch_is_not_ready(
        self,
        fetch_messages,
        learn_messages,
        mark_processed,
    ):
        rows, outgoing_ids = _conversation_rows(
            "friend",
            20,
            1,
            global_processed=True,
            contact_processed=False,
        )
        fetch_messages.return_value = rows

        result = process_pending_style_learning("user-1")

        self.assertFalse(result["global_updated"])
        self.assertEqual(result["global_message_count"], 0)
        self.assertEqual(
            result["contacts_updated"],
            [{"contact_id": "friend", "message_count": 20}],
        )
        learn_messages.assert_called_once()
        mark_processed.assert_called_once_with(
            outgoing_ids,
            "contact_style_processed",
        )

    def test_builds_pairs_from_closest_previous_incoming_and_skips_missing_context(self):
        rows = [
            _message_row(1, "friend", "outgoing", "reply without context"),
            _message_row(2, "friend", "incoming", "first question"),
            _message_row(3, "friend", "outgoing", "first reply"),
            _message_row(4, "friend", "incoming", "second question"),
            _message_row(5, "friend", "outgoing", "second reply"),
            _message_row(
                6,
                "friend",
                "outgoing",
                "already processed",
                global_processed=True,
            ),
        ]

        pairs = _build_training_pairs(
            rows,
            processed_flag="global_style_processed",
        )

        self.assertEqual([pair.outgoing_id for pair in pairs], [3, 5])
        self.assertEqual(
            [pair.learning_input() for pair in pairs],
            [
                {
                    "incoming_message": "first question",
                    "user_reply": "first reply",
                },
                {
                    "incoming_message": "second question",
                    "user_reply": "second reply",
                },
            ],
        )

    def test_only_valid_outgoing_pairs_count_toward_threshold(self):
        rows = [
            *[
                _message_row(index, "friend", "outgoing", f"no context {index}")
                for index in range(1, 21)
            ],
            _message_row(21, "friend", "incoming", "now there is context"),
            *[
                _message_row(index, "friend", "outgoing", f"valid reply {index}")
                for index in range(22, 71)
            ],
        ]

        pairs = _build_training_pairs(
            rows,
            processed_flag="contact_style_processed",
        )

        self.assertEqual(len(pairs), 49)

    @patch("app.style_learning_service.get_supabase_client")
    def test_conversation_query_filters_user_and_orders_oldest_first(self, get_client):
        query = _FakeMessagesQuery(
            [_message_row(1, "friend", "incoming", "hello")]
        )
        get_client.return_value.table.return_value = query

        rows = _fetch_conversation_messages()

        self.assertEqual(rows[0]["id"], 1)
        self.assertFalse(any(call[0] == "eq" for call in query.calls))
        self.assertIn(("order", "created_at", False), query.calls)
        self.assertIn(("order", "id", False), query.calls)
        self.assertIn(("range", 0, 999), query.calls)


class StylePromptTests(unittest.TestCase):
    def test_learning_prompt_separates_context_from_reply_and_keeps_schema(self):
        prompt = build_extraction_prompt(
            [
                {
                    "context": "heyyy!!! are you free 😂",
                    "reply": "I can meet after 3.",
                }
            ],
            contact="friend",
        )

        self.assertIn("Incoming context: heyyy!!! are you free 😂", prompt)
        self.assertIn("User reply: I can meet after 3.", prompt)
        self.assertIn("Analyze only the reply text", prompt)
        self.assertIn("Use incoming context only", prompt)
        self.assertIn("Never copy, imitate, or learn", prompt)
        self.assertIn('"traits"', prompt)
        self.assertIn('"patterns"', prompt)
        self.assertIn('"overall_confidence"', prompt)
        self.assertIn('"message_count": 1', prompt)
        self.assertIn('"batch_count": 1', prompt)

    def test_contact_prompt_renders_structured_patterns_and_anti_support_rules(self):
        contact_profile = neutral_profile(message_count=3, batch_count=1)
        contact_profile["overall_confidence"] = 90
        contact_profile["patterns"] = extract_style_patterns(
            ["heyyy!!", "sounds good 😂", "lmk?"]
        )
        contact_profile["patterns"]["conversation_behavior"]["acknowledgment_style"] = (
            "short"
        )

        prompt = build_prompt(
            message="Are we still meeting?",
            contact_name="friend",
            style_mode="contact",
            contact_profile=contact_profile,
        )

        self.assertIn("Greetings: heyyy", prompt)
        self.assertIn("Common phrases: sounds good, lmk", prompt)
        self.assertIn("never a support assistant", prompt)
        self.assertIn("Do not force an emoji", prompt)
        self.assertIn("reply length=brief", prompt)
        self.assertIn("reply like a friend", prompt)
        self.assertIn("do not force a follow-up question", prompt)
        self.assertIn("okay, sure, or gotcha briefly", prompt)


def _message_row(
    message_id: int,
    contact_id: str,
    direction: str,
    message_text: str,
    *,
    global_processed: bool = False,
    contact_processed: bool = False,
) -> dict:
    return {
        "id": message_id,
        "contact_id": contact_id,
        "direction": direction,
        "message_text": message_text,
        "created_at": f"2026-06-01T00:{message_id // 60:02d}:{message_id % 60:02d}+00:00",
        "global_style_processed": global_processed,
        "contact_style_processed": contact_processed,
    }


def _conversation_rows(
    contact_id: str,
    pair_count: int,
    start_id: int,
    *,
    global_processed: bool = False,
    contact_processed: bool = False,
) -> tuple[list[dict], list[int]]:
    rows = []
    outgoing_ids = []
    for offset in range(pair_count):
        incoming_id = start_id + (offset * 2)
        outgoing_id = incoming_id + 1
        rows.append(
            _message_row(
                incoming_id,
                contact_id,
                "incoming",
                f"incoming {incoming_id}",
            )
        )
        rows.append(
            _message_row(
                outgoing_id,
                contact_id,
                "outgoing",
                f"outgoing {outgoing_id}",
                global_processed=global_processed,
                contact_processed=contact_processed,
            )
        )
        outgoing_ids.append(outgoing_id)
    return rows, outgoing_ids


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeMessagesQuery:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def order(self, column, desc=False):
        self.calls.append(("order", column, desc))
        return self

    def range(self, start, end):
        self.calls.append(("range", start, end))
        return self

    def execute(self):
        return _FakeResponse(self.rows)


if __name__ == "__main__":
    unittest.main()

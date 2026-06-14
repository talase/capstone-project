import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.personal_context_routes import (
    PersonalContextEvaluateRequest,
    _evaluate_personal_context,
    router as personal_context_router,
)
from app.personal_context_service import (
    UserStatus,
    UserStatusSet,
    clear_user_status,
    evaluate_personal_context,
    get_current_user_status,
    set_user_status,
)


class PersonalContextServiceTests(unittest.TestCase):
    def test_legacy_status_reason_is_not_exposed(self):
        status = UserStatus(
            user_id="u1",
            status="busy",
            status_reason="legacy value",
        )

        self.assertNotIn("status_reason", status.model_dump())

    def test_available_status_auto_replies_without_context(self):
        result = evaluate_personal_context({"user_status": "available"})

        self.assertEqual(result["current_status"], {"status": "available"})
        self.assertEqual(result["decision"], "auto_reply")
        self.assertEqual(result["final_action"], "auto_reply")
        self.assertEqual(result["context"], [])
        self.assertNotIn("status_reason", result)

    def test_free_text_status_auto_replies_with_status_context(self):
        status_text = (
            "I have an appointment tomorrow at the hospital and I won't be "
            "available. If anyone asks for a meeting tomorrow, say sorry I'm "
            "at the hospital."
        )
        result = evaluate_personal_context(
            {
                "user_status": status_text,
                "topic": "ignored",
                "contact_id": "ignored",
                "action": "ignored",
            }
        )

        self.assertEqual(result["current_status"], {"status": status_text})
        self.assertEqual(result["decision"], "auto_reply")
        self.assertIn(status_text, result["context"][0])
        self.assertNotIn("matched_rules", result)
        self.assertNotIn("winning_rule", result)
        self.assertNotIn("status_reason", result)

    def test_latest_active_status_is_used_even_when_expires_at_is_past(self):
        fake_table = _FakeStatusTable()
        fake_table.rows = [
            {
                "id": 2,
                "user_id": "u1",
                "status": "traveling",
                "expires_at": "2000-01-01T00:00:00Z",
                "is_active": True,
            }
        ]

        with patch("app.personal_context_service._status_table", return_value=fake_table):
            current = get_current_user_status("u1")

        self.assertEqual(current["status"], "traveling")

    def test_custom_status_can_be_stored(self):
        fake_table = _FakeStatusTable()
        with patch("app.personal_context_service._status_table", return_value=fake_table):
            created = set_user_status(
                UserStatusSet(
                    user_id="u1",
                    status="Heads down at work until 5 PM.",
                )
            )
            current = get_current_user_status("u1")
            cleared = clear_user_status("u1")

        self.assertEqual(created["status"], "Heads down at work until 5 PM.")
        self.assertEqual(current["status"], "Heads down at work until 5 PM.")
        self.assertEqual(cleared["status"], "available")

    def test_evaluate_endpoint_returns_clean_status_response(self):
        with (
            patch(
                "app.personal_context_routes.get_current_user_status",
                return_value={
                    "status": "traveling",
                },
            ),
            patch("app.personal_context_routes._log_evaluation_activity", return_value=[]),
        ):
            response = _evaluate_personal_context(
                PersonalContextEvaluateRequest(user_id="u1", message="Where are you?")
            )

        self.assertEqual(response["current_status"], {"status": "traveling"})
        self.assertEqual(response["decision"], "auto_reply")
        self.assertEqual(response["final_action"], "auto_reply")
        self.assertEqual(
            set(response),
            {"current_status", "decision", "reason", "final_action"},
        )
        self.assertNotIn("personal_context", response)
        self.assertNotIn("matched_rules", response)
        self.assertNotIn("status_reason", response)

    def test_pcm_rule_routes_are_removed(self):
        app = FastAPI()
        app.include_router(personal_context_router)
        client = TestClient(app)

        self.assertEqual(client.get("/personal-context/rules").status_code, 404)
        self.assertEqual(client.get("/personal-context/approvals").status_code, 404)


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeStatusTable:
    def __init__(self):
        self.rows = []
        self._operation = None
        self._data = None
        self._filters = {}

    def select(self, *_args):
        self._operation = "select"
        self._filters = {}
        return self

    def insert(self, data):
        self._operation = "insert"
        self._data = dict(data)
        return self

    def update(self, data):
        self._operation = "update"
        self._data = dict(data)
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._operation == "insert":
            row = {"id": len(self.rows) + 1, **self._data}
            self.rows.append(row)
            return _FakeResponse([dict(row)])
        if self._operation == "update":
            updated = []
            for row in self.rows:
                if all(row.get(key) == value for key, value in self._filters.items()):
                    row.update(self._data)
                    updated.append(dict(row))
            return _FakeResponse(updated)
        if self._operation == "select":
            rows = [
                dict(row)
                for row in reversed(self.rows)
                if all(row.get(key) == value for key, value in self._filters.items())
            ]
            return _FakeResponse(rows)
        return _FakeResponse([])


if __name__ == "__main__":
    unittest.main()

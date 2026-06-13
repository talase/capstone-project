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
    ALLOWED_DECISIONS,
    PersonalContextRuleCreate,
    UserStatusSet,
    clear_user_status,
    create_rule,
    evaluate_personal_context_rules,
    get_current_user_status,
    set_user_status,
)


class PersonalContextServiceTests(unittest.TestCase):
    def test_create_rule_inserts_context_rule(self):
        fake_table = _FakeRuleInsertTable()
        rule = PersonalContextRuleCreate(
            user_id="u1",
            rule_name="Busy context",
            rule_type="status_context",
            rule_value={
                "status": "busy",
                "context": "The user is busy and may reply later.",
                "decision": "auto_reply",
            },
            priority=5,
            contact_id="boss",
        )

        with patch("app.personal_context_service._table", return_value=fake_table):
            created = create_rule(rule)

        self.assertEqual(fake_table.inserted, rule.model_dump(exclude_none=True))
        self.assertEqual(created["id"], 1)

    def test_only_auto_reply_and_defer_are_allowed(self):
        self.assertEqual(ALLOWED_DECISIONS, {"auto_reply", "defer"})

    def test_status_is_context_without_forcing_defer(self):
        result = evaluate_personal_context_rules(
            {
                "message": "Are you free?",
                "user_status": "busy",
                "status_reason": "In a client meeting",
            },
            [],
        )

        self.assertEqual(result["decision"], "auto_reply")
        self.assertIn("current status is busy", result["context"][0])
        self.assertIn("In a client meeting", result["context"][1])

    def test_matching_rule_adds_context(self):
        result = evaluate_personal_context_rules(
            {"message": "Hello", "user_status": "traveling"},
            [
                {
                    "id": 1,
                    "rule_name": "Travel context",
                    "rule_type": "status_context",
                    "rule_value": {
                        "status": "traveling",
                        "context": "The user may have limited connectivity.",
                    },
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "auto_reply")
        self.assertIn(
            "The user may have limited connectivity.",
            result["context"],
        )
        self.assertEqual(result["matched_rules"][0]["id"], 1)

    def test_irrelevant_status_rule_is_ignored(self):
        result = evaluate_personal_context_rules(
            {"message": "Hello", "user_status": "at_work"},
            [
                {
                    "id": 2,
                    "rule_name": "Travel context",
                    "rule_type": "status_context",
                    "rule_value": {
                        "status": "traveling",
                        "context": "The user may have limited connectivity.",
                    },
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "auto_reply")
        self.assertEqual(result["matched_rules"], [])
        self.assertNotIn("limited connectivity", " ".join(result["context"]))

    def test_explicit_defer_rule_postpones_handling(self):
        result = evaluate_personal_context_rules(
            {"message": "Hello", "user_status": "in_meeting"},
            [
                {
                    "id": 3,
                    "rule_name": "Defer during meeting",
                    "rule_type": "status_context",
                    "rule_value": {
                        "status": "in_meeting",
                        "decision": "defer",
                        "context": "The user is in a meeting.",
                    },
                    "priority": 10,
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "defer")
        self.assertEqual(result["winning_rule"]["id"], 3)

    def test_legacy_workflow_decisions_fall_back_to_auto_reply(self):
        for legacy_decision in (
            "require_approval",
            "draft_only",
            "blocked",
            "approval_required",
        ):
            with self.subTest(legacy_decision=legacy_decision):
                result = evaluate_personal_context_rules(
                    {"message": "Hello"},
                    [
                        {
                            "rule_type": "custom",
                            "rule_value": {"decision": legacy_decision},
                            "is_active": True,
                        }
                    ],
                )
                self.assertEqual(result["decision"], "auto_reply")

    def test_custom_status_can_be_stored(self):
        fake_table = _FakeStatusTable()
        with patch("app.personal_context_service._status_table", return_value=fake_table):
            created = set_user_status(
                UserStatusSet(
                    user_id="u1",
                    status="at_work",
                    status_reason="Heads down",
                )
            )
            current = get_current_user_status("u1")
            cleared = clear_user_status("u1")

        self.assertEqual(created["status"], "at_work")
        self.assertEqual(current["status"], "at_work")
        self.assertEqual(cleared["status"], "available")

    def test_evaluate_endpoint_returns_context_and_no_final_action(self):
        with (
            patch(
                "app.personal_context_routes.get_current_user_status",
                return_value={
                    "status": "traveling",
                    "status_reason": "Limited signal",
                },
            ),
            patch("app.personal_context_routes.list_active_rules", return_value=[]),
            patch("app.personal_context_routes._log_evaluation_activity", return_value=[]),
        ):
            response = _evaluate_personal_context(
                PersonalContextEvaluateRequest(user_id="u1", message="Where are you?")
            )

        self.assertEqual(response["decision"], "auto_reply")
        self.assertEqual(response["personal_context"]["decision"], "auto_reply")
        self.assertIn("traveling", " ".join(response["context"]))
        self.assertNotIn("final_action", response)

    def test_old_pcm_approval_route_is_removed(self):
        app = FastAPI()
        app.include_router(personal_context_router)
        response = TestClient(app).get("/personal-context/approvals")
        self.assertEqual(response.status_code, 404)


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeRuleInsertTable:
    def __init__(self):
        self.inserted = None

    def insert(self, data):
        self.inserted = dict(data)
        return self

    def execute(self):
        return _FakeResponse([{"id": 1, **self.inserted}])


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
            return _FakeResponse([row])
        matched = [
            row
            for row in self.rows
            if all(row.get(key) == value for key, value in self._filters.items())
        ]
        if self._operation == "update":
            for row in matched:
                row.update(self._data)
        return _FakeResponse(matched)


if __name__ == "__main__":
    unittest.main()

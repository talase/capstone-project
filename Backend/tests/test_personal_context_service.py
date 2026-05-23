import unittest
from unittest.mock import patch

from app.personal_context_service import (
    ApprovalRequestCreate,
    UserStatusSet,
    clear_user_status,
    create_approval_request,
    evaluate_personal_context_rules,
    get_current_user_status,
    set_approval_status,
    set_user_status,
)
from app.style_engine import _enforce_high_risk_approval, _final_action_for_decision


class PersonalContextServiceTests(unittest.TestCase):
    def test_auto_reply_when_no_rules_match(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "friend", "message": "hey"},
            [],
        )

        self.assertEqual(result["decision"], "auto_reply")
        self.assertEqual(result["matched_rules"], [])

    def test_draft_only_rule_matches(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "boss", "message": "quick update", "current_time": "10:00"},
            [
                {
                    "id": 1,
                    "rule_name": "Work hours draft",
                    "rule_type": "work_hours_draft",
                    "rule_value": "09:00-17:00",
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "draft_only")
        self.assertEqual(_final_action_for_decision(result["decision"]), "draft")

    def test_require_approval_for_money_topic(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "friend", "message": "can you send money?"},
            [
                {
                    "id": 2,
                    "rule_name": "Money approval",
                    "rule_type": "money_requires_approval",
                    "rule_value": {"decision": "require_approval"},
                    "topic": "money",
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "require_approval")
        self.assertEqual(
            _final_action_for_decision(result["decision"]),
            "approval_required",
        )

    def test_defer_for_busy_status(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "friend", "message": "hello", "user_status": "busy"},
            [
                {
                    "id": 3,
                    "rule_name": "Busy defer",
                    "rule_type": "busy_status",
                    "rule_value": {"status": "busy"},
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "defer")
        self.assertEqual(_final_action_for_decision(result["decision"]), "deferred")

    def test_defer_for_unavailable_status(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "friend", "message": "hello", "user_status": "unavailable"},
            [
                {
                    "id": 4,
                    "rule_name": "Unavailable defer",
                    "rule_type": "availability",
                    "rule_value": {},
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "defer")

    def test_traveling_status_can_match_rule(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "friend", "message": "hello", "user_status": "traveling"},
            [
                {
                    "id": 5,
                    "rule_name": "Traveling defer",
                    "rule_type": "availability",
                    "rule_value": {"status": "traveling"},
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "defer")

    def test_high_risk_forces_approval(self):
        result = _enforce_high_risk_approval(
            {"risk_level": "high"},
            {"decision": "auto_reply", "matched_rules": [], "reason": "No match."},
        )

        self.assertEqual(result["decision"], "require_approval")
        self.assertEqual(result["matched_rules"][0]["id"], "system_high_risk_gate")

    def test_approval_status_flow(self):
        fake_table = _FakeApprovalTable()
        with (
            patch("app.personal_context_service._approval_table", return_value=fake_table),
            patch("app.personal_context_service.log_approval_event") as log_approval_event,
        ):
            approved = set_approval_status(1, "approved")

        self.assertEqual(approved["status"], "approved")
        log_approval_event.assert_called_once()
        self.assertEqual(log_approval_event.call_args.kwargs["status"], "approved")
        self.assertEqual(log_approval_event.call_args.kwargs["approval_request_id"], 1)

    def test_create_approval_request_writes_pending_approval_log(self):
        fake_table = _FakeApprovalInsertTable()
        with (
            patch("app.personal_context_service._approval_table", return_value=fake_table),
            patch("app.personal_context_service.log_approval_event") as log_approval_event,
        ):
            created = create_approval_request(
                ApprovalRequestCreate(
                    user_id="u1",
                    contact_id="friend",
                    original_message="Can you send this?",
                    generated_reply="Draft reply",
                    matched_rules=[
                        {
                            "rule_type": "money_requires_approval",
                            "decision": "require_approval",
                        }
                    ],
                )
            )

        self.assertEqual(created["status"], "pending")
        log_approval_event.assert_called_once()
        self.assertEqual(log_approval_event.call_args.kwargs["status"], "pending")
        self.assertEqual(
            log_approval_event.call_args.kwargs["action_category"],
            "money_requires_approval",
        )

    def test_set_retrieve_and_clear_user_status(self):
        fake_table = _FakeStatusTable()
        with patch("app.personal_context_service._status_table", return_value=fake_table):
            created = set_user_status(
                UserStatusSet(
                    user_id="u1",
                    status="busy",
                    status_reason="In class",
                )
            )
            current = get_current_user_status("u1")
            cleared = clear_user_status("u1")

        self.assertEqual(created["status"], "busy")
        self.assertEqual(current["status"], "busy")
        self.assertEqual(cleared["status"], "available")

    def test_status_based_defer_maps_to_no_send(self):
        result = evaluate_personal_context_rules(
            {"message": "hello", "user_status": "busy"},
            [
                {
                    "id": 6,
                    "rule_name": "Busy defer",
                    "rule_type": "busy_status",
                    "rule_value": {"status": "busy"},
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "defer")
        self.assertNotEqual(_final_action_for_decision(result["decision"]), "send")


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeApprovalTable:
    def __init__(self):
        self.rows = {
            1: {
                "id": 1,
                "user_id": "u1",
                "contact_id": "friend",
                "original_message": "hello",
                "generated_reply": "hi",
                "decision": "require_approval",
                "status": "pending",
                "matched_rules": [],
            }
        }
        self._operation = None
        self._update_data = None
        self._id = None

    def select(self, *_args):
        self._operation = "select"
        return self

    def update(self, data):
        self._operation = "update"
        self._update_data = data
        return self

    def eq(self, column, value):
        if column == "id":
            self._id = int(value)
        return self

    def execute(self):
        row = self.rows.get(self._id)
        if not row:
            return _FakeResponse([])
        if self._operation == "update":
            row.update(self._update_data)
        return _FakeResponse([row])


class _FakeApprovalInsertTable:
    def __init__(self):
        self._insert_data = None

    def insert(self, data):
        self._insert_data = data
        return self

    def execute(self):
        row = {"id": 2, **self._insert_data}
        return _FakeResponse([row])


class _FakeStatusTable:
    def __init__(self):
        self.rows = []
        self._operation = None
        self._update_data = None
        self._insert_data = None
        self._filters = {}

    def select(self, *_args):
        self._operation = "select"
        self._filters = {}
        return self

    def insert(self, data):
        self._operation = "insert"
        self._insert_data = dict(data)
        return self

    def update(self, data):
        self._operation = "update"
        self._update_data = dict(data)
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._operation == "insert":
            row = {"id": len(self.rows) + 1, **self._insert_data}
            self.rows.append(row)
            return _FakeResponse([row])

        matched = [
            row for row in self.rows
            if all(row.get(column) == value for column, value in self._filters.items())
        ]

        if self._operation == "update":
            for row in matched:
                row.update(self._update_data)
            return _FakeResponse(matched)

        return _FakeResponse(matched)


if __name__ == "__main__":
    unittest.main()

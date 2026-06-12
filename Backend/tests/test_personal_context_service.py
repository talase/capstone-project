import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.personal_context_service import (
    ALLOWED_DECISIONS,
    ApprovalRequestCreate,
    PersonalContextRuleCreate,
    UserStatusSet,
    clear_user_status,
    create_approval_request,
    create_rule,
    evaluate_personal_context_rules,
    get_current_user_status,
    set_approval_status,
    set_user_status,
)
from app.personal_context_routes import (
    PersonalContextEvaluateRequest,
    _evaluate_personal_context,
    router as personal_context_router,
)
from app.style_engine import _enforce_high_risk_approval, _final_action_for_decision


class PersonalContextServiceTests(unittest.TestCase):
    def test_create_rule_inserts_all_fields(self):
        fake_table = _FakeRuleInsertTable()
        rule = PersonalContextRuleCreate(
            user_id="u1",
            rule_name="Work hours draft",
            rule_type="work_hours_draft",
            rule_value={"window": "09:00-17:00"},
            priority=5,
            contact_id="boss",
            topic="work",
            action="send_message",
            is_active=True,
        )

        with patch("app.personal_context_service._table", return_value=fake_table):
            created = create_rule(rule)

        self.assertEqual(fake_table.inserted, rule.model_dump())
        self.assertEqual(created["id"], 1)
        self.assertEqual(created["rule_value"], {"window": "09:00-17:00"})

    def test_create_rule_endpoint_returns_201_and_created_rule(self):
        fake_table = _FakeRuleInsertTable()
        app = FastAPI()
        app.include_router(personal_context_router)
        client = TestClient(app)
        payload = {
            "user_id": "u1",
            "rule_name": "Money approval",
            "rule_type": "money_requires_approval",
            "rule_value": {"decision": "require_approval"},
            "priority": 10,
            "topic": "money",
            "is_active": True,
        }

        with patch("app.personal_context_service._table", return_value=fake_table):
            response = client.post("/personal-context/rules", json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], 1)
        self.assertEqual(response.json()["rule_name"], "Money approval")
        self.assertEqual(fake_table.inserted, payload)

    def test_create_rule_endpoint_rejects_null_rule_value(self):
        app = FastAPI()
        app.include_router(personal_context_router)
        client = TestClient(app)

        response = client.post(
            "/personal-context/rules",
            json={
                "user_id": "u1",
                "rule_name": "Invalid rule",
                "rule_type": "custom",
                "rule_value": None,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_create_rule_endpoint_rejects_unsupported_time_columns(self):
        app = FastAPI()
        app.include_router(personal_context_router)
        client = TestClient(app)

        response = client.post(
            "/personal-context/rules",
            json={
                "user_id": "u1",
                "rule_name": "Work hours draft",
                "rule_type": "work_hours_draft",
                "rule_value": {"window": "09:00-17:00"},
                "start_time": "09:00",
                "end_time": "17:00",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_auto_reply_when_no_rules_match(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "friend", "message": "hey"},
            [],
        )

        self.assertEqual(result["decision"], "auto_reply")
        self.assertEqual(result["matched_rules"], [])
        self.assertIsNone(result["winning_rule"])

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
        self.assertEqual(result["winning_rule"]["id"], 1)
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
        self.assertEqual(result["winning_rule"]["id"], 2)
        self.assertEqual(
            _final_action_for_decision(result["decision"]),
            "approval_required",
        )

    def test_multiple_matching_rules_highest_priority_wins(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "boss", "message": "can you send payment today?"},
            [
                {
                    "id": 10,
                    "rule_name": "Money approval",
                    "rule_type": "money_requires_approval",
                    "rule_value": {"decision": "require_approval"},
                    "topic": "money",
                    "priority": 1,
                    "is_active": True,
                },
                {
                    "id": 11,
                    "rule_name": "Boss draft",
                    "rule_type": "draft_only",
                    "rule_value": {},
                    "contact_id": "boss",
                    "priority": 10,
                    "is_active": True,
                },
            ],
        )

        self.assertEqual(result["decision"], "draft_only")
        self.assertEqual(result["winning_rule"]["id"], 11)
        self.assertEqual([rule["id"] for rule in result["matched_rules"]], [11, 10])
        self.assertEqual(result["reason"], "Highest-priority matching rule selected.")

    def test_missing_priority_is_treated_as_zero(self):
        result = evaluate_personal_context_rules(
            {"contact_id": "friend", "message": "can you send money?"},
            [
                {
                    "id": 12,
                    "rule_name": "Money approval with no priority",
                    "rule_type": "money_requires_approval",
                    "rule_value": {"decision": "require_approval"},
                    "topic": "money",
                    "is_active": True,
                },
                {
                    "id": 13,
                    "rule_name": "Friend draft",
                    "rule_type": "draft_only",
                    "rule_value": {},
                    "contact_id": "friend",
                    "priority": 1,
                    "is_active": True,
                },
            ],
        )

        self.assertEqual(result["decision"], "draft_only")
        self.assertEqual(result["winning_rule"]["id"], 13)
        self.assertEqual(result["matched_rules"][1]["priority"], 0)

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

    def test_null_rule_filters_match_all_messages(self):
        result = evaluate_personal_context_rules(
            {
                "contact_id": "friend",
                "message": "hello",
                "topic": "general",
                "action": "send_message",
                "user_status": "busy",
            },
            [
                {
                    "id": 7,
                    "rule_name": "Global busy defer",
                    "rule_type": "busy_status",
                    "rule_value": {"status": "busy"},
                    "priority": 0,
                    "contact_id": None,
                    "topic": None,
                    "action": None,
                    "is_active": True,
                }
            ],
        )

        self.assertEqual(result["decision"], "defer")
        self.assertEqual(result["winning_rule"]["id"], 7)

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

    def test_current_status_logs_query_result_and_selected_row(self):
        fake_table = _FakeStatusTable()
        fake_table.rows.append(
            {
                "id": 1,
                "user_id": "default_user",
                "status": "busy",
                "is_active": True,
                "expires_at": None,
                "created_at": "2026-06-06T10:00:00+00:00",
            }
        )

        with (
            patch("app.personal_context_service._status_table", return_value=fake_table),
            self.assertLogs("app.personal_context_service", level="DEBUG") as logs,
        ):
            current = get_current_user_status("default_user")

        self.assertEqual(current["status"], "busy")
        output = "\n".join(logs.output)
        self.assertIn("'user_id': 'default_user'", output)
        self.assertIn("'is_active': True", output)
        self.assertIn("row_count=1", output)
        self.assertIn("selected row", output)
        self.assertNotIn("fallback", output)

    def test_current_status_logs_available_fallback(self):
        fake_table = _FakeStatusTable()

        with (
            patch("app.personal_context_service._status_table", return_value=fake_table),
            self.assertLogs("app.personal_context_service", level="DEBUG") as logs,
        ):
            current = get_current_user_status("default_user")

        self.assertEqual(current["status"], "available")
        self.assertIn("fallback", "\n".join(logs.output))

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

    def test_evaluation_outputs_only_allowed_decisions(self):
        cases = [
            ({}, [], "auto_reply"),
            (
                {"message": "hello"},
                [{"rule_type": "require_approval", "rule_value": {}, "is_active": True}],
                "require_approval",
            ),
            (
                {"message": "hello"},
                [{"rule_type": "draft_only", "rule_value": {}, "is_active": True}],
                "draft_only",
            ),
            (
                {"message": "hello", "user_status": "busy"},
                [{"rule_type": "defer", "rule_value": {}, "is_active": True}],
                "defer",
            ),
            (
                {"message": "hello"},
                [{"rule_type": "block", "rule_value": {}, "is_active": True}],
                "blocked",
            ),
        ]

        for message_data, rules, expected_decision in cases:
            with self.subTest(expected_decision=expected_decision):
                result = evaluate_personal_context_rules(message_data, rules)

            self.assertIn(result["decision"], ALLOWED_DECISIONS)
            self.assertEqual(result["decision"], expected_decision)

    def test_legacy_decision_aliases_are_normalized(self):
        aliases = {
            "approval_required": "require_approval",
            "needs_approval": "require_approval",
            "approval": "require_approval",
            "deferred": "defer",
            "block": "blocked",
        }

        for alias, expected_decision in aliases.items():
            with self.subTest(alias=alias):
                result = evaluate_personal_context_rules(
                    {"message": "hello"},
                    [{"rule_type": "custom", "rule_value": alias, "is_active": True}],
                )

            self.assertEqual(result["decision"], expected_decision)
            self.assertIn(result["decision"], ALLOWED_DECISIONS)

    def test_personal_context_evaluate_returns_nested_decision(self):
        with (
            patch("app.personal_context_routes.get_current_user_status") as get_status,
            patch("app.personal_context_routes.list_active_rules") as list_active_rules,
        ):
            get_status.return_value = {"status": "available"}
            list_active_rules.return_value = [
                {
                    "id": 20,
                    "rule_name": "Money approval",
                    "rule_type": "money_requires_approval",
                    "rule_value": {},
                    "topic": "money",
                    "is_active": True,
                }
            ]

            response = _evaluate_personal_context(
                PersonalContextEvaluateRequest(
                    user_id="u1",
                    contact_id="friend",
                    message="can you send money?",
                )
            )

        self.assertEqual(response["decision"], "require_approval")
        self.assertEqual(response["personal_context"]["decision"], "require_approval")
        self.assertFalse(response["personal_context"]["fallback_used"])
        self.assertIn(response["personal_context"]["decision"], ALLOWED_DECISIONS)

    def test_evaluate_endpoint_uses_database_busy_status_and_defers(self):
        app = FastAPI()
        app.include_router(personal_context_router)
        client = TestClient(app)

        with (
            patch(
                "app.personal_context_routes.get_current_user_status",
                return_value={
                    "id": 1,
                    "user_id": "default_user",
                    "status": "busy",
                    "is_active": True,
                    "expires_at": None,
                },
            ),
            patch(
                "app.personal_context_routes.list_active_rules",
                return_value=[
                    {
                        "id": 3,
                        "user_id": "default_user",
                        "rule_name": "Busy defer",
                        "rule_type": "busy_status",
                        "rule_value": {"status": "busy"},
                        "priority": 0,
                        "contact_id": None,
                        "topic": None,
                        "action": None,
                        "is_active": True,
                    }
                ],
            ),
            patch(
                "app.personal_context_routes._log_evaluation_activity",
                return_value=[],
            ),
        ):
            response = client.post(
                "/personal-context/evaluate",
                json={
                    "user_id": "default_user",
                    "message": "Are you available?",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["current_status"]["status"], "busy")
        self.assertEqual(response.json()["decision"], "defer")
        self.assertEqual(response.json()["final_action"], "deferred")


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
        return _FakeResponse(
            [
                {
                    "id": 1,
                    **self.inserted,
                    "created_at": "2026-06-06T10:00:00+00:00",
                    "updated_at": "2026-06-06T10:00:00+00:00",
                }
            ]
        )


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

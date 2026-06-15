import unittest
from datetime import date
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.daily_report_service import REPORT_TABLES, build_daily_report, fetch_records_for_date
from app.routes.reports import router as reports_router


REPORT_DATE = date(2026, 5, 22)


class DailyReportServiceTests(unittest.TestCase):
    def test_empty_report_when_no_records_exist(self):
        report = build_daily_report(REPORT_DATE, _empty_records())

        self.assertEqual(report["date"], "2026-05-22")
        self.assertEqual(
            report["summary"],
            {
                "messages_received": 0,
                "messages_sent": 0,
                "auto_replies": 0,
                "automatic_actions": 0,
                "approved_actions": 0,
                "rejected_actions": 0,
                "pending_approvals": 0,
                "high_risk_alerts": 0,
                "reminders_created": 0,
                "scheduled_messages": 0,
                "rag_files_accessed": 0,
            },
        )
        self.assertEqual(report["needs_attention"], [])

    def test_correct_counting_of_messages_actions_and_approvals(self):
        records = _empty_records()
        records["messages"] = [
            {"id": 1, "direction": "incoming", "message_text": "hi"},
            {"id": 2, "direction": "outgoing", "message_text": "hello"},
        ]
        records["agent_activity_logs"] = [
            {
                "id": 3,
                "status": "automatic",
                "action_category": "request_to_send_message",
            }
        ]
        records["approvals"] = [
            {"id": 4, "status": "approved", "action_category": "money_request"},
            {"id": 5, "status": "rejected", "action_category": "sensitive_file"},
        ]
        records["reminder_logs"] = [{"id": 6, "reminder_text": "Call mom"}]
        records["scheduled_message_logs"] = [{"id": 7, "message": "Happy birthday"}]
        records["rag_access_logs"] = [
            {"id": 8, "file_id": "policy.pdf"},
            {"id": 9, "file_id": "policy.pdf"},
            {"id": 10, "file_id": "notes.pdf"},
        ]

        report = build_daily_report(REPORT_DATE, records)

        self.assertEqual(report["summary"]["messages_received"], 1)
        self.assertEqual(report["summary"]["messages_sent"], 1)
        self.assertEqual(report["summary"]["automatic_actions"], 1)
        self.assertEqual(report["summary"]["approved_actions"], 1)
        self.assertEqual(report["summary"]["rejected_actions"], 1)
        self.assertEqual(report["summary"]["reminders_created"], 1)
        self.assertEqual(report["summary"]["scheduled_messages"], 1)
        self.assertEqual(report["summary"]["rag_files_accessed"], 2)
        self.assertEqual(
            report["detected_action_categories"],
            [{"category": "request_to_send_message", "count": 1}],
        )

    def test_auto_replies_are_counted_from_style_response_activity(self):
        records = _empty_records()
        records["agent_activity_logs"] = [
            {
                "id": 1,
                "status": "automatic",
                "metadata": {"source": "style_response"},
            },
            {
                "id": 2,
                "status": "automatic",
                "metadata": {"source": "scheduler"},
            },
            {
                "id": 3,
                "status": "pending",
                "metadata": {"source": "style_response"},
            },
        ]

        report = build_daily_report(REPORT_DATE, records)

        self.assertEqual(report["summary"]["auto_replies"], 1)
        self.assertEqual(report["summary"]["automatic_actions"], 2)
        self.assertNotIn("personal_context_decisions", report)

    def test_pending_approvals_appear_in_needs_attention(self):
        records = _empty_records()
        records["approvals"] = [
            {"id": 1, "status": "pending", "original_message": "Send this?"}
        ]

        report = build_daily_report(REPORT_DATE, records)

        self.assertEqual(report["summary"]["pending_approvals"], 1)
        self.assertEqual(report["needs_attention"][0]["type"], "pending_approval")
        self.assertEqual(report["needs_attention"][0]["id"], 1)

    def test_approvals_count_current_statuses(self):
        records = _empty_records()
        records["approvals"] = [
            {
                "id": 10,
                "status": "pending",
                "original_message": "Send this?",
            },
            {
                "id": 11,
                "status": "approved",
                "original_message": "Send this?",
            },
        ]

        report = build_daily_report(REPORT_DATE, records)

        self.assertEqual(report["summary"]["approved_actions"], 1)
        self.assertEqual(report["summary"]["pending_approvals"], 1)

    def test_rejected_approvals_are_counted_from_approvals_table(self):
        records = _empty_records()
        records["approvals"] = [
            {
                "id": 11,
                "status": "rejected",
                "original_message": "Send this?",
            },
        ]

        report = build_daily_report(REPORT_DATE, records)

        self.assertEqual(report["summary"]["rejected_actions"], 1)
        self.assertEqual(report["summary"]["pending_approvals"], 0)

    def test_high_risk_alerts_appear_in_needs_attention(self):
        records = _empty_records()
        records["high_risk_alerts"] = [
            {"id": 2, "status": "open", "reason": "Sensitive request"}
        ]

        report = build_daily_report(REPORT_DATE, records)

        self.assertEqual(report["summary"]["high_risk_alerts"], 1)
        self.assertEqual(report["needs_attention"][0]["type"], "high_risk_alert")
        self.assertEqual(report["needs_attention"][0]["id"], 2)

    def test_fetch_records_uses_supabase_date_range_and_user_filter(self):
        fake_client = _FakeSupabaseClient({"messages": [{"id": 1}]})

        with patch(
            "app.daily_report_service.get_supabase_client",
            return_value=fake_client,
        ):
            records = fetch_records_for_date(REPORT_DATE, user_id="user-1")

        self.assertEqual(records["messages"], [{"id": 1}])
        self.assertEqual(len(fake_client.tables), len(REPORT_TABLES))
        first_query = fake_client.tables["messages"]
        self.assertIn(("gte", "created_at", "2026-05-22T00:00:00+00:00"), first_query.calls)
        self.assertIn(("lt", "created_at", "2026-05-23T00:00:00+00:00"), first_query.calls)
        self.assertNotIn(("eq", "user_id", "user-1"), first_query.calls)

        activity_query = fake_client.tables["agent_activity_logs"]
        self.assertIn(("eq", "user_id", "user-1"), activity_query.calls)

    def test_endpoint_returns_valid_json(self):
        payload = build_daily_report(REPORT_DATE, _empty_records())
        app = FastAPI()
        app.include_router(reports_router)
        client = TestClient(app)

        with patch("app.routes.reports.get_daily_report", return_value=payload):
            response = client.get("/reports/daily?date=2026-05-22")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["date"], "2026-05-22")
        self.assertIn("summary", response.json())


def _empty_records():
    return {table_name: [] for table_name in REPORT_TABLES}


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeSupabaseClient:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.tables = {}

    def table(self, table_name):
        query = _FakeTableQuery(table_name, self.rows_by_table.get(table_name, []))
        self.tables[table_name] = query
        return query


class _FakeTableQuery:
    def __init__(self, table_name, rows):
        self.table_name = table_name
        self.rows = rows
        self.calls = []

    def select(self, value):
        self.calls.append(("select", value))
        return self

    def gte(self, column, value):
        self.calls.append(("gte", column, value))
        return self

    def lt(self, column, value):
        self.calls.append(("lt", column, value))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def order(self, column, desc=False):
        self.calls.append(("order", column, desc))
        return self

    def execute(self):
        return _FakeResponse(self.rows)

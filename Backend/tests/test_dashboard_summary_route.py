from __future__ import annotations

import unittest
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.dashboard_summary as dashboard_summary_routes


@dataclass
class FakeResponse:
    data: list[dict[str, object]]


class FakeQuery:
    def __init__(self, fake: "FakeSupabase", table_name: str):
        self.fake = fake
        self.table_name = table_name
        self.filters: list[tuple[str, str, object]] = []
        self.start = 0
        self.end = 999

    def select(self, columns: str):
        self.fake.calls.append(("select", self.table_name, columns))
        return self

    def eq(self, column: str, value: object):
        self.filters.append(("eq", column, value))
        return self

    def like(self, column: str, value: object):
        self.filters.append(("like", column, value))
        return self

    def range(self, start: int, end: int):
        self.start = start
        self.end = end
        return self

    def execute(self):
        rows = self.fake.rows[self.table_name]
        for operation, column, value in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif operation == "like":
                prefix = str(value).removesuffix("%")
                rows = [
                    row
                    for row in rows
                    if str(row.get(column) or "").startswith(prefix)
                ]
        return FakeResponse(rows[self.start : self.end + 1])


class FakeSupabase:
    def __init__(self):
        self.calls: list[tuple[object, ...]] = []
        self.rows: dict[str, list[dict[str, object]]] = {
            "approvals": [
                {
                    "user_id": "default_user",
                    "action_type": "send_file",
                    "status": "pending",
                },
                {
                    "user_id": "default_user",
                    "action_type": "send_file",
                    "status": "approved",
                },
                {
                    "user_id": "default_user",
                    "action_type": "[\"send_message\",\"send_file\"]",
                    "status": "executed",
                },
                {
                    "user_id": "another_user",
                    "action_type": "send_message",
                    "status": "rejected",
                },
            ],
            "messages": [
                {"id": "message-1", "direction": "incoming"},
                {"id": "message-2", "direction": "incoming"},
                {"id": "message-3", "direction": "outgoing"},
            ],
            "contacts": [{"id": "contact-1"}, {"id": "contact-2"}],
            "files": [
                {
                    "id": "file-1",
                    "storage_path": "dashboard_uploads/a.pdf",
                    "is_sensitive": True,
                },
                {
                    "id": "file-2",
                    "storage_path": "dashboard_uploads/b.pdf",
                    "is_sensitive": False,
                },
                {
                    "id": "file-3",
                    "storage_path": "other/c.pdf",
                    "is_sensitive": False,
                },
            ],
        }

    def table(self, table_name: str):
        return FakeQuery(self, table_name)


def test_dashboard_summary_uses_live_table_counts() -> None:
    fake = FakeSupabase()
    dashboard_summary_routes.get_supabase_client = lambda: fake
    app = FastAPI()
    app.include_router(dashboard_summary_routes.router)

    response = TestClient(app).get("/dashboard-summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["approvals_total"] == 3
    assert summary["approvals_pending"] == 1
    assert summary["approvals_approved"] == 1
    assert summary["approvals_executed"] == 1
    assert summary["messages_total"] == 3
    assert summary["incoming_messages"] == 2
    assert summary["outgoing_messages"] == 1
    assert summary["contacts_total"] == 2
    assert summary["uploaded_files_total"] == 2
    assert summary["sensitive_files"] == 1
    assert summary["non_sensitive_files"] == 1
    assert summary["actions_by_type"][0] == {
        "action_type": "send_file",
        "count": 3,
    }
    assert summary["actions_by_type"][1] == {
        "action_type": "send_message",
        "count": 1,
    }


def load_tests(
    _loader: unittest.TestLoader,
    _tests: unittest.TestSuite,
    _pattern: str | None,
) -> unittest.TestSuite:
    return unittest.TestSuite(
        [unittest.FunctionTestCase(test_dashboard_summary_uses_live_table_counts)]
    )

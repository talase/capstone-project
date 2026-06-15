from __future__ import annotations

import unittest
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.dashboard_approvals as approval_routes


@dataclass
class FakeResponse:
    data: list[dict[str, object]]


class FakeQuery:
    def __init__(
        self,
        fake: "FakeSupabase",
        table_name: str,
    ):
        self.fake = fake
        self.table_name = table_name
        self.operation = "select"
        self.filters: list[tuple[str, object]] = []
        self.update_payload: dict[str, object] = {}

    def select(self, columns: str):
        self.operation = "select"
        self.fake.calls.append(("select", self.table_name, columns))
        return self

    def update(self, payload: dict[str, object]):
        self.operation = "update"
        self.update_payload = payload
        self.fake.calls.append(("update", self.table_name, payload))
        return self

    def eq(self, column: str, value: object):
        self.filters.append((column, value))
        self.fake.calls.append(("eq", self.table_name, column, value))
        return self

    def in_(self, column: str, values: list[str]):
        self.fake.calls.append(("in", self.table_name, column, values))
        return self

    def order(self, column: str, *, desc: bool = False):
        self.fake.calls.append(("order", self.table_name, column, desc))
        return self

    def limit(self, count: int):
        self.fake.calls.append(("limit", self.table_name, count))
        return self

    def execute(self):
        self.fake.calls.append(("execute", self.operation, self.table_name))
        rows = self.fake.rows[self.table_name]
        filtered = [
            row
            for row in rows
            if all(row.get(column) == value for column, value in self.filters)
        ]
        if self.operation == "update":
            for row in filtered:
                row.update(self.update_payload)
        return FakeResponse(filtered)


class FakeSupabase:
    def __init__(self):
        self.calls: list[tuple[object, ...]] = []
        self.rows: dict[str, list[dict[str, object]]] = {
            "approvals": [
                {
                    "id": "approval-1",
                    "user_id": "default_user",
                    "message_id": "message-1",
                    "contact_id": "contact-1",
                    "action_type": "request_to_send_message_to_someone_else",
                    "risk_level": "medium",
                    "status": "pending",
                    "file_id": "file-1",
                    "phone_number": "111",
                    "approval_message": "May I send this?",
                    "target_contact_id": "contact-2",
                    "target_contact_name": "Stale target name",
                    "message_to_send": "Hello there",
                    "request_text": "Tell Nora hello",
                    "proposed_response": None,
                    "user_edited_response": None,
                    "created_at": "2026-06-15T12:00:00+00:00",
                    "resolved_at": None,
                }
            ],
            "contacts": [
                {"id": "contact-1", "name": "Lyna", "phone_number": "111"},
                {"id": "contact-2", "name": "Nora", "phone_number": "222"},
            ],
            "messages": [
                {
                    "id": "message-1",
                    "contact_id": "contact-1",
                    "message_text": "Tell Nora hello",
                    "direction": "incoming",
                    "created_at": "2026-06-15T11:59:00+00:00",
                }
            ],
            "files": [
                {
                    "id": "file-1",
                    "file_name": "report.pdf",
                    "storage_path": "dashboard_uploads/report.pdf",
                    "file_type": "pdf",
                    "is_sensitive": True,
                }
            ],
        }

    def table(self, table_name: str):
        self.calls.append(("table", table_name))
        return FakeQuery(self, table_name)


def make_client(fake: FakeSupabase) -> TestClient:
    approval_routes.get_supabase_client = lambda: fake
    app = FastAPI()
    app.include_router(approval_routes.router)
    return TestClient(app)


def test_list_resolves_related_names_message_and_file() -> None:
    fake = FakeSupabase()

    response = make_client(fake).get("/dashboard-approvals")

    assert response.status_code == 200
    approval = response.json()[0]
    assert approval["contact_id"] == "contact-1"
    assert approval["requester_name"] == "Lyna"
    assert approval["source_message_text"] == "Tell Nora hello"
    assert approval["target_contact_name"] == "Nora"
    assert approval["file_name"] == "report.pdf"
    assert approval["file_is_sensitive"] is True


def test_approval_route_is_read_only() -> None:
    fake = FakeSupabase()

    response = make_client(fake).patch(
        "/dashboard-approvals/approval-1",
        json={"decision": "approved", "message_to_send": "Edited hello"},
    )

    assert response.status_code == 404
    assert not any(call[0] == "update" for call in fake.calls)


def load_tests(
    _loader: unittest.TestLoader,
    _tests: unittest.TestSuite,
    _pattern: str | None,
) -> unittest.TestSuite:
    return unittest.TestSuite(
        unittest.FunctionTestCase(test)
        for test in (
            test_list_resolves_related_names_message_and_file,
            test_approval_route_is_read_only,
        )
    )

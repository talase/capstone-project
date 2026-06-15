from __future__ import annotations

import unittest
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.message_history as message_history_routes


@dataclass
class FakeResponse:
    data: list[dict[str, object]]


class FakeQuery:
    def __init__(
        self,
        calls: list[tuple[object, ...]],
        table_name: str,
        rows: list[dict[str, object]],
    ):
        self.calls = calls
        self.table_name = table_name
        self.rows = rows

    def select(self, columns: str):
        self.calls.append(("select", self.table_name, columns))
        return self

    def order(self, column: str, *, desc: bool = False):
        self.calls.append(("order", self.table_name, column, desc))
        return self

    def limit(self, count: int):
        self.calls.append(("limit", self.table_name, count))
        return self

    def execute(self):
        self.calls.append(("execute", self.table_name))
        return FakeResponse(self.rows)


class FakeSupabase:
    def __init__(self):
        self.calls: list[tuple[object, ...]] = []
        self.rows = {
            "messages": [
                {
                    "id": "message-1",
                    "contact_id": "contact-1",
                    "direction": "incoming",
                    "message_text": "Please send the report",
                    "predicted_actions": [
                        "request_to_send_message_to_someone_else"
                    ],
                    "risk_level": "medium",
                    "status": "received",
                    "confidence": 0.91,
                    "created_at": "2026-06-15T15:00:00+00:00",
                },
                {
                    "id": "message-2",
                    "contact_id": None,
                    "direction": "outgoing",
                    "message_text": "Hello",
                    "predicted_actions": None,
                    "risk_level": None,
                    "status": "sent",
                    "confidence": None,
                    "created_at": "2026-06-15T14:00:00+00:00",
                },
            ],
            "contacts": [{"id": "contact-1", "name": "Lyna"}],
        }

    def table(self, table_name: str):
        self.calls.append(("table", table_name))
        return FakeQuery(self.calls, table_name, self.rows[table_name])


def test_history_uses_messages_and_resolves_contact_names() -> None:
    fake = FakeSupabase()
    message_history_routes.get_supabase_client = lambda: fake
    app = FastAPI()
    app.include_router(message_history_routes.router)

    response = TestClient(app).get("/message-history", params={"limit": 25})

    assert response.status_code == 200
    history = response.json()
    assert len(history) == 2
    assert history[0]["contact_name"] == "Lyna"
    assert history[0]["risk_level"] == "medium"
    assert history[0]["predicted_actions"] == [
        "request_to_send_message_to_someone_else"
    ]
    assert history[1]["contact_name"] == "Unknown contact"
    assert history[1]["risk_level"] is None
    assert history[1]["predicted_actions"] == []
    assert ("order", "messages", "created_at", True) in fake.calls
    assert ("limit", "messages", 25) in fake.calls


def load_tests(
    _loader: unittest.TestLoader,
    _tests: unittest.TestSuite,
    _pattern: str | None,
) -> unittest.TestSuite:
    return unittest.TestSuite(
        [unittest.FunctionTestCase(test_history_uses_messages_and_resolves_contact_names)]
    )

from __future__ import annotations

import unittest
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.action_settings as action_settings_routes


@dataclass
class FakeResponse:
    data: list[dict[str, object]]


class FakeQuery:
    def __init__(
        self,
        calls: list[tuple[object, ...]],
        table_name: str,
        setting: dict[str, object],
    ):
        self.calls = calls
        self.table_name = table_name
        self.setting = setting
        self.operation = ""
        self.update_payload: dict[str, object] | None = None

    def select(self, columns: str):
        self.operation = "select"
        self.calls.append(("select", self.table_name, columns))
        return self

    def update(self, payload: dict[str, object]):
        self.operation = "update"
        self.update_payload = payload
        self.calls.append(("update", self.table_name, payload))
        return self

    def eq(self, column: str, value: object):
        self.calls.append(("eq", self.table_name, column, value))
        return self

    def limit(self, count: int):
        self.calls.append(("limit", self.table_name, count))
        return self

    def order(self, column: str):
        self.calls.append(("order", self.table_name, column))
        return self

    def execute(self):
        self.calls.append(("execute", self.operation, self.table_name))
        if self.operation == "update":
            updated = {**self.setting, **(self.update_payload or {})}
            return FakeResponse([updated])
        return FakeResponse([self.setting])


class FakeSupabase:
    def __init__(self, setting: dict[str, object]):
        self.setting = setting
        self.calls: list[tuple[object, ...]] = []

    def table(self, table_name: str):
        self.calls.append(("table", table_name))
        return FakeQuery(self.calls, table_name, self.setting)


def make_client(fake: FakeSupabase) -> TestClient:
    action_settings_routes.get_supabase_client = lambda: fake
    app = FastAPI()
    app.include_router(action_settings_routes.router)
    return TestClient(app)


def test_editable_setting_can_change_risk_level() -> None:
    fake = FakeSupabase(
        {
            "id": "setting-1",
            "user_id": "default_user",
            "action_type": "book_or_reschedule_meeting",
            "risk_level": "low",
            "is_editable": True,
        }
    )

    response = make_client(fake).patch(
        "/action-settings/setting-1",
        params={"user_id": "default_user"},
        json={"risk_level": "medium"},
    )

    assert response.status_code == 200
    assert response.json()["risk_level"] == "medium"
    assert ("update", "action_settings", {"risk_level": "medium"}) in fake.calls


def test_fixed_setting_cannot_be_changed() -> None:
    fake = FakeSupabase(
        {
            "id": "setting-2",
            "user_id": "default_user",
            "action_type": "asking_for_money",
            "risk_level": "high",
            "is_editable": False,
        }
    )

    response = make_client(fake).patch(
        "/action-settings/setting-2",
        params={"user_id": "default_user"},
        json={"risk_level": "low"},
    )

    assert response.status_code == 403
    assert not any(call[0] == "update" for call in fake.calls)


def test_invalid_risk_level_is_rejected() -> None:
    fake = FakeSupabase(
        {
            "id": "setting-1",
            "user_id": "default_user",
            "action_type": "book_or_reschedule_meeting",
            "risk_level": "low",
            "is_editable": True,
        }
    )

    response = make_client(fake).patch(
        "/action-settings/setting-1",
        json={"risk_level": "critical"},
    )

    assert response.status_code == 422
    assert fake.calls == []


def load_tests(
    _loader: unittest.TestLoader,
    _tests: unittest.TestSuite,
    _pattern: str | None,
) -> unittest.TestSuite:
    return unittest.TestSuite(
        unittest.FunctionTestCase(test)
        for test in (
            test_editable_setting_can_change_risk_level,
            test_fixed_setting_cannot_be_changed,
            test_invalid_risk_level_is_rejected,
        )
    )

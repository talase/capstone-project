import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.approval_routes import router as approval_router
from app.approval_service import (
    ApprovalRequestCreate,
    create_approval_request,
    evaluate_risk_approval,
    set_approval_status,
)


class ApprovalServiceTests(unittest.TestCase):
    def test_high_risk_requires_approval_independently(self):
        self.assertTrue(evaluate_risk_approval("high")["required"])
        self.assertFalse(evaluate_risk_approval("low")["required"])

    def test_create_request_does_not_write_pcm_fields(self):
        fake_table = _FakeApprovalInsertTable()
        with (
            patch("app.approval_service._approval_table", return_value=fake_table),
            patch("app.approval_service.log_approval_event"),
        ):
            created = create_approval_request(
                ApprovalRequestCreate(
                    user_id="u1",
                    original_message="Send the passport",
                    generated_reply="Here it is",
                    reason="High-risk message requires approval before sending.",
                )
            )

        self.assertEqual(created["status"], "pending")
        self.assertNotIn("matched_rules", fake_table.inserted)
        self.assertNotIn("decision", fake_table.inserted)

    def test_approval_status_flow(self):
        fake_table = _FakeApprovalTable()
        with (
            patch("app.approval_service._approval_table", return_value=fake_table),
            patch("app.approval_service.log_approval_event"),
        ):
            approved = set_approval_status(1, "approved")
        self.assertEqual(approved["status"], "approved")

    def test_approval_routes_use_separate_prefix(self):
        app = FastAPI()
        app.include_router(approval_router)
        fake_table = _FakeApprovalInsertTable()
        with (
            patch("app.approval_service._approval_table", return_value=fake_table),
            patch("app.approval_service.log_approval_event"),
        ):
            response = TestClient(app).post(
                "/approvals",
                json={
                    "user_id": "u1",
                    "original_message": "Send it",
                    "generated_reply": "Okay",
                },
            )
        self.assertEqual(response.status_code, 201)


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeApprovalInsertTable:
    def __init__(self):
        self.inserted = None

    def insert(self, data):
        self.inserted = dict(data)
        return self

    def execute(self):
        return _FakeResponse([{"id": 2, **self.inserted}])


class _FakeApprovalTable:
    def __init__(self):
        self.row = {
            "id": 1,
            "user_id": "u1",
            "original_message": "hello",
            "generated_reply": "hi",
            "status": "pending",
        }
        self.operation = None
        self.data = None

    def select(self, *_args):
        self.operation = "select"
        return self

    def update(self, data):
        self.operation = "update"
        self.data = data
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        if self.operation == "update":
            self.row.update(self.data)
        return _FakeResponse([self.row])


if __name__ == "__main__":
    unittest.main()

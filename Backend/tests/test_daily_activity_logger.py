import unittest
from unittest.mock import patch

from app.daily_activity_logger import log_approval_event, log_message_event, log_rag_access


class DailyActivityLoggerTests(unittest.TestCase):
    def test_log_message_event_inserts_into_supabase(self):
        fake_client = _FakeSupabaseClient()

        with patch(
            "app.daily_activity_logger.get_supabase_client",
            return_value=fake_client,
        ):
            result = log_message_event(
                direction="received",
                message="hello",
                user_id="u1",
                contact_id="friend",
            )

        self.assertTrue(result.ok)
        self.assertEqual(fake_client.table_name, "message_logs")
        self.assertEqual(fake_client.inserted["direction"], "received")
        self.assertEqual(fake_client.inserted["message"], "hello")

    def test_log_rag_access_inserts_file_access_record(self):
        fake_client = _FakeSupabaseClient()

        with patch(
            "app.daily_activity_logger.get_supabase_client",
            return_value=fake_client,
        ):
            result = log_rag_access(
                user_id="u1",
                file_id="file-1",
                file_name="notes.pdf",
                query="policy question",
            )

        self.assertTrue(result.ok)
        self.assertEqual(fake_client.table_name, "rag_access_logs")
        self.assertEqual(fake_client.inserted["file_name"], "notes.pdf")

    def test_log_approval_event_preserves_uuid_request_id_in_metadata(self):
        fake_client = _FakeSupabaseClient()
        request_id = "b87a6c99-8f9b-4c0c-9f92-29d1ad444d94"

        with patch(
            "app.daily_activity_logger.get_supabase_client",
            return_value=fake_client,
        ):
            result = log_approval_event(
                status="pending",
                approval_request_id=request_id,
                metadata={"source": "pcm"},
            )

        self.assertTrue(result.ok)
        self.assertEqual(fake_client.table_name, "approval_logs")
        self.assertEqual(fake_client.inserted["user_id"], "default_user")
        self.assertNotIn("approval_request_id", fake_client.inserted)
        self.assertEqual(
            fake_client.inserted["metadata"]["approval_request_id"],
            request_id,
        )
        self.assertEqual(fake_client.inserted["metadata"]["source"], "pcm")

    def test_logging_failure_returns_warning_result(self):
        with patch(
            "app.daily_activity_logger.get_supabase_client",
            side_effect=RuntimeError("missing config"),
        ):
            result = log_message_event(direction="received", message="hello")

        self.assertFalse(result.ok)
        self.assertEqual(result.warning()["table"], "message_logs")

    def test_unresolved_contact_template_is_not_logged_as_contact_id(self):
        fake_client = _FakeSupabaseClient()

        with patch(
            "app.daily_activity_logger.get_supabase_client",
            return_value=fake_client,
        ):
            result = log_message_event(
                direction="received",
                message="hello",
                contact_id="={{$json.contact_id}}",
            )

        self.assertTrue(result.ok)
        self.assertNotIn("contact_id", fake_client.inserted)


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeSupabaseClient:
    def __init__(self):
        self.table_name = None
        self.inserted = None

    def table(self, table_name):
        self.table_name = table_name
        return self

    def insert(self, data):
        self.inserted = data
        return self

    def execute(self):
        return _FakeResponse([{**self.inserted, "id": 1}])

import unittest
from unittest.mock import patch

from app import supabase_client


class SupabaseClientTests(unittest.TestCase):
    def setUp(self):
        supabase_client.get_supabase_client.cache_clear()

    def tearDown(self):
        supabase_client.get_supabase_client.cache_clear()

    def test_service_role_key_takes_precedence(self):
        fake_client = object()

        with (
            patch("app.supabase_client.load_env_file"),
            patch.dict(
                "os.environ",
                {
                    "SUPABASE_URL": "https://project-ref.supabase.co",
                    "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
                    "SUPABASE_KEY": "publishable-key",
                },
                clear=True,
            ),
            patch(
                "app.supabase_client.create_client",
                return_value=fake_client,
            ) as create_client,
        ):
            client = supabase_client.get_supabase_client()

        self.assertIs(client, fake_client)
        create_client.assert_called_once_with(
            "https://project-ref.supabase.co",
            "service-role-secret",
        )

    def test_falls_back_when_service_role_key_is_missing(self):
        fake_client = object()

        with (
            patch("app.supabase_client.load_env_file"),
            patch.dict(
                "os.environ",
                {
                    "SUPABASE_URL": "https://project-ref.supabase.co",
                    "SUPABASE_KEY": "publishable-key",
                },
                clear=True,
            ),
            patch(
                "app.supabase_client.create_client",
                return_value=fake_client,
            ) as create_client,
        ):
            client = supabase_client.get_supabase_client()

        self.assertIs(client, fake_client)
        create_client.assert_called_once_with(
            "https://project-ref.supabase.co",
            "publishable-key",
        )

    def test_startup_log_is_redacted(self):
        with (
            patch("app.supabase_client.load_env_file"),
            patch.dict(
                "os.environ",
                {
                    "SUPABASE_URL": "https://project-ref.supabase.co",
                    "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
                    "SUPABASE_KEY": "publishable-key",
                },
                clear=True,
            ),
            self.assertLogs("app.supabase_client", level="INFO") as logs,
        ):
            supabase_client.log_supabase_startup_config()

        output = "\n".join(logs.output)
        self.assertIn("service_role_present=true", output)
        self.assertIn("key_type=service_role", output)
        self.assertIn("project_ref=project-ref", output)
        self.assertNotIn("service-role-secret", output)
        self.assertNotIn("publishable-key", output)


if __name__ == "__main__":
    unittest.main()

"""Supabase service-role client for backend-only file storage access."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from app.config import load_env_file

try:
    from supabase import Client, create_client
except (ImportError, ModuleNotFoundError):  # pragma: no cover - handled at runtime
    Client = Any
    create_client = None


class SupabaseStorageConfigError(RuntimeError):
    """Raised when Supabase storage credentials are unavailable."""


@lru_cache(maxsize=1)
def get_supabase_service_client() -> Client:
    """Return a Supabase client using the backend-only service role key."""

    load_env_file()
    if create_client is None:
        raise SupabaseStorageConfigError(
            "The supabase package is not installed. Run: pip install supabase"
        )

    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise SupabaseStorageConfigError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set on the backend."
        )

    return create_client(supabase_url, service_role_key)


def get_storage_bucket_name() -> str:
    """Return the configured Supabase Storage bucket name."""

    load_env_file()
    return os.getenv("SUPABASE_BUCKET_NAME", "user-files")

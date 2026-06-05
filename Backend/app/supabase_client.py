"""Reusable Supabase client for backend services."""

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


class SupabaseConfigError(RuntimeError):
    """Raised when Supabase is not installed or credentials are missing."""


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a cached Supabase client configured from environment variables."""

    load_env_file()
    if create_client is None:
        raise SupabaseConfigError(
            "The supabase package is not installed. Run: pip install -r requirements.txt"
        )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise SupabaseConfigError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY must be set in .env."
        )
    
    print("URL:", supabase_url)
    print("KEY EXISTS:", bool(supabase_key))

    return create_client(supabase_url, supabase_key)

"""Reusable Supabase client for backend services."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from app.config import load_env_file

try:
    from supabase import Client, create_client
except (ImportError, ModuleNotFoundError):  # pragma: no cover - handled at runtime
    Client = Any
    create_client = None


LOGGER = logging.getLogger(__name__)


class SupabaseConfigError(RuntimeError):
    """Raised when Supabase is not installed or credentials are missing."""


def _supabase_key() -> tuple[str | None, str]:
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if service_role_key:
        return service_role_key, "service_role"
    return os.getenv("SUPABASE_KEY"), "anon"


def log_supabase_startup_config() -> None:
    """Log redacted Supabase configuration selected for backend operations."""

    load_env_file()
    supabase_url = os.getenv("SUPABASE_URL", "")
    service_role_present = bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    _, key_type = _supabase_key()
    project_host = urlparse(supabase_url).hostname or supabase_url
    project_ref = project_host.split(".", 1)[0] if project_host else "missing"
    LOGGER.info(
        "Supabase startup: service_role_present=%s key_type=%s project_ref=%s",
        str(service_role_present).lower(),
        key_type,
        project_ref,
    )


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a cached Supabase client configured from environment variables."""

    load_env_file()
    if create_client is None:
        raise SupabaseConfigError(
            "The supabase package is not installed. Run: pip install -r requirements.txt"
        )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key, credential_source = _supabase_key()
    if not supabase_url or not supabase_key:
        raise SupabaseConfigError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY must be set in .env."
        )

    project_host = urlparse(supabase_url).hostname or supabase_url
    project_ref = project_host.split(".", 1)[0]
    LOGGER.debug(
        "Creating Supabase client: url=%s project_ref=%s credential_source=%s",
        supabase_url,
        project_ref,
        credential_source,
    )

    return create_client(supabase_url, supabase_key)

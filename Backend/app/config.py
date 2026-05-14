"""Shared backend configuration."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent

BATCH_SIZE = 50
MODEL = "openrouter/free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def env_file_paths() -> list[Path]:
    return [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "app" / ".env",
        WORKSPACE_ROOT / ".env",
        WORKSPACE_ROOT / ".venv" / ".env",
        Path.cwd() / ".env",
        Path.cwd() / ".venv" / ".env",
    ]


def load_env_file() -> None:
    """Load local env files without overriding already exported variables."""

    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        load_dotenv = None

    for env_path in env_file_paths():
        if not env_path.exists():
            continue
        if load_dotenv is not None:
            load_dotenv(env_path, override=False)
        _load_env_manually(env_path)


def _load_env_manually(env_path: Path) -> None:
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        if clean.startswith("export "):
            clean = clean.removeprefix("export ").strip()
        key, value = clean.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _read_env_keys(env_path: Path) -> list[str]:
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    keys: list[str] = []
    for line in lines:
        clean = line.strip()
        if clean.startswith("export "):
            clean = clean.removeprefix("export ").strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key = clean.split("=", 1)[0].strip()
        if key:
            keys.append(key)
    return keys


def env_file_status() -> list[str]:
    """Return redacted status for env files checked by the loader."""

    statuses = []
    seen: set[Path] = set()
    for env_path in env_file_paths():
        resolved = env_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not env_path.exists():
            statuses.append(f"{env_path}: missing")
            continue
        keys = _read_env_keys(env_path)
        statuses.append(
            f"{env_path}: exists, "
            f"OPENROUTER_API_KEY={'yes' if 'OPENROUTER_API_KEY' in keys else 'no'}, "
            f"WHATSAPP_TOKEN={'yes' if 'WHATSAPP_TOKEN' in keys else 'no'}, "
            f"WHATSAPP_PHONE_NUMBER_ID={'yes' if 'WHATSAPP_PHONE_NUMBER_ID' in keys else 'no'}, "
            f"WHATSAPP_VERIFY_TOKEN={'yes' if 'WHATSAPP_VERIFY_TOKEN' in keys else 'no'}"
        )
    return statuses


def get_client() -> OpenAI:
    load_env_file()
    if OpenAI is None:
        raise RuntimeError(
            "The openai package is not installed. Run: pip install -r requirements.txt"
        )

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        checked = "\n".join(f"- {status}" for status in env_file_status())
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set.\n"
            "Add OPENROUTER_API_KEY to Backend/.env.\n\n"
            f"Checked env files:\n{checked}"
        )

    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

"""Profile storage and stable profile merging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.supabase_client import get_supabase_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = PROJECT_ROOT / "profiles"
CONTACT_MAP_PATH = PROJECT_ROOT / "contact_map.json"

TRAITS = ("formality", "politeness", "verbosity", "optimism")
DEFAULT_USER_ID = "default_user"
STYLE_PROFILES_TABLE = "style_profiles"


def neutral_profile(message_count: int = 0, batch_count: int = 0) -> dict[str, Any]:
    """Return a safe neutral style profile."""

    return {
        "traits": {
            trait: {"score": 0.5, "confidence": 0}
            for trait in TRAITS
        },
        "patterns": [],
        "overall_confidence": 0,
        "message_count": message_count,
        "batch_count": batch_count,
    }


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_confidence(value: Any) -> int:
    """Accept either 0-1 or 0-100 confidence and normalize to 0-100."""

    confidence = _as_float(value, 0)
    if 0 <= confidence <= 1:
        confidence *= 100
    return _as_int(clamp(confidence, 0, 100), 0)


def sanitize_patterns(patterns: Any, max_items: int = 5) -> list[str]:
    """Keep short abstract patterns and drop quote-like or oversized content."""

    if not isinstance(patterns, list):
        return []

    clean: list[str] = []
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        item = pattern.strip().replace("\n", " ")
        if not item:
            continue
        # Prevent storing copied message-like content. Patterns should be abstract.
        if '"' in item or "'" in item:
            continue
        if len(item.split()) > 18:
            item = " ".join(item.split()[:18])
        if item not in clean:
            clean.append(item)
        if len(clean) >= max_items:
            break
    return clean


def sanitize_profile(raw: Any, message_count: int | None = None) -> dict[str, Any]:
    """Validate and normalize a model-produced profile."""

    if not isinstance(raw, dict):
        return neutral_profile(message_count or 0, 0)

    profile = neutral_profile()
    raw_traits = raw.get("traits", {})
    if isinstance(raw_traits, dict):
        for trait in TRAITS:
            raw_trait = raw_traits.get(trait, {})
            if not isinstance(raw_trait, dict):
                raw_trait = {}
            score = clamp(_as_float(raw_trait.get("score"), 0.5), 0, 1)
            confidence = normalize_confidence(raw_trait.get("confidence", 0))
            profile["traits"][trait] = {
                "score": round(score, 3),
                "confidence": confidence,
            }

    profile["patterns"] = sanitize_patterns(raw.get("patterns", []))
    profile["overall_confidence"] = normalize_confidence(raw.get("overall_confidence", 0))
    profile["message_count"] = _as_int(
        raw.get("message_count", message_count if message_count is not None else 0),
        message_count if message_count is not None else 0,
    )
    profile["batch_count"] = _as_int(raw.get("batch_count", 1), 1)
    return profile


def sanitize_contact_id(contact: str | None = None) -> str:
    """Return the filesystem-safe profile id used in profile filenames."""

    if contact is None or contact == "global":
        return "global"
    return "".join(ch for ch in str(contact).lower() if ch.isalnum() or ch in ("_", "-"))


def profile_path(contact: str | None = None) -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    safe_contact = sanitize_contact_id(contact)
    if safe_contact == "global":
        return PROFILES_DIR / "profile_global.json"
    return PROFILES_DIR / f"profile_{safe_contact}.json"


def load_contact_map() -> dict[str, str]:
    """Load optional external contact ids mapped to saved profile names.

    Example contact_map.json:
    {
      "+15551234567": "friend",
      "905551112233": "mom"
    }
    """

    if not CONTACT_MAP_PATH.exists():
        return {}
    try:
        raw_map = json.loads(CONTACT_MAP_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw_map, dict):
        return {}

    clean_map: dict[str, str] = {}
    for raw_contact, profile_contact in raw_map.items():
        if not isinstance(raw_contact, str) or not isinstance(profile_contact, str):
            continue
        keys = _contact_lookup_keys(raw_contact)
        safe_profile = sanitize_contact_id(profile_contact)
        if safe_profile:
            for key in keys:
                clean_map[key] = safe_profile
    return clean_map


def resolve_profile_contact(contact: str | None = None) -> str:
    """Resolve a backend contact id, such as a phone number, to a profile id."""

    if contact is None or contact == "global":
        return "global"

    safe_contact = sanitize_contact_id(contact)
    contact_map = load_contact_map()
    for key in _contact_lookup_keys(contact):
        mapped_contact = contact_map.get(key)
        if mapped_contact:
            return mapped_contact

    if profile_path(safe_contact).exists():
        return safe_contact
    return safe_contact


def load_profile(contact: str | None = None, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    supabase_profile = _load_profile_from_supabase(contact, user_id)
    if supabase_profile is not None:
        return supabase_profile
    return _load_profile_from_file(contact)


def _load_profile_from_file(contact: str | None = None) -> dict[str, Any]:
    path = profile_path(resolve_profile_contact(contact))
    if not path.exists():
        return neutral_profile()
    try:
        return sanitize_profile(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return neutral_profile()


def load_global_profile(user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    """Load profiles/profile_global.json, falling back to a neutral profile."""

    return load_profile("global", user_id=user_id)


def save_profile(
    profile: dict[str, Any],
    contact: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> Path:
    if _save_profile_to_supabase(profile, contact, user_id):
        return profile_path(resolve_profile_contact(contact))
    return _save_profile_to_file(profile, contact)


def _save_profile_to_file(profile: dict[str, Any], contact: str | None = None) -> Path:
    path = profile_path(resolve_profile_contact(contact))
    clean_profile = sanitize_profile(profile)
    path.write_text(json.dumps(clean_profile, indent=2), encoding="utf-8")
    return path


def merge_profiles(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Merge a new batch into an existing profile using batch-weighted smoothing."""

    old = sanitize_profile(existing)
    incoming = sanitize_profile(new)

    old_batches = max(0, _as_int(old.get("batch_count"), 0))
    new_batches = max(1, _as_int(incoming.get("batch_count"), 1))
    total_batches = old_batches + new_batches

    merged = neutral_profile()
    for trait in TRAITS:
        old_trait = old["traits"][trait]
        new_trait = incoming["traits"][trait]
        old_weight = old_batches * max(old_trait["confidence"], 1)
        new_weight = new_batches * max(new_trait["confidence"], 1)
        total_weight = old_weight + new_weight
        score = (
            (old_trait["score"] * old_weight + new_trait["score"] * new_weight) / total_weight
            if total_weight
            else 0.5
        )
        confidence = (
            (old_trait["confidence"] * old_batches + new_trait["confidence"] * new_batches)
            / total_batches
        )
        merged["traits"][trait] = {
            "score": round(clamp(score, 0, 1), 3),
            "confidence": _as_int(clamp(confidence, 0, 100), 0),
        }

    combined_patterns = old.get("patterns", []) + incoming.get("patterns", [])
    merged["patterns"] = sanitize_patterns(combined_patterns)
    merged["overall_confidence"] = _as_int(
        clamp(
            (old.get("overall_confidence", 0) * old_batches
             + incoming.get("overall_confidence", 0) * new_batches)
            / total_batches,
            0,
            100,
        ),
        0,
    )
    merged["message_count"] = _as_int(old.get("message_count"), 0) + _as_int(
        incoming.get("message_count"), 0
    )
    merged["batch_count"] = total_batches
    return merged


def update_profile(
    new_profile: dict[str, Any],
    contact: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    existing = load_profile(contact, user_id=user_id)
    merged = merge_profiles(existing, new_profile)
    save_profile(merged, contact, user_id=user_id)
    return merged


def _load_profile_from_supabase(
    contact: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any] | None:
    try:
        response = (
            _style_profiles_table()
            .select("*")
            .eq("user_id", user_id)
            .eq("contact_id", _profile_contact_id(contact))
            .eq("profile_type", _profile_type(contact))
            .limit(1)
            .execute()
        )
        rows = _response_rows(response)
        if not rows:
            return None
        return _row_to_profile(rows[0])
    except Exception:
        return None


def _save_profile_to_supabase(
    profile: dict[str, Any],
    contact: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> bool:
    payload = _profile_to_row(profile, contact, user_id)
    try:
        _style_profiles_table().upsert(
            payload,
            on_conflict="user_id,contact_id,profile_type",
        ).execute()
        return True
    except TypeError:
        return _save_profile_to_supabase_without_upsert_options(payload)
    except Exception:
        return False


def _save_profile_to_supabase_without_upsert_options(payload: dict[str, Any]) -> bool:
    """Support older supabase-py versions that lack upsert on_conflict options."""

    try:
        response = (
            _style_profiles_table()
            .select("id")
            .eq("user_id", payload["user_id"])
            .eq("contact_id", payload["contact_id"])
            .eq("profile_type", payload["profile_type"])
            .limit(1)
            .execute()
        )
        rows = _response_rows(response)
        if rows:
            _style_profiles_table().update(payload).eq("id", rows[0]["id"]).execute()
        else:
            _style_profiles_table().insert(payload).execute()
        return True
    except Exception:
        return False


def _profile_to_row(
    profile: dict[str, Any],
    contact: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    clean_profile = sanitize_profile(profile)
    return {
        "user_id": user_id,
        "contact_id": _profile_contact_id(contact),
        "profile_type": _profile_type(contact),
        "traits": clean_profile["traits"],
        "patterns": clean_profile["patterns"],
        "confidence": clean_profile["overall_confidence"],
        "message_count": clean_profile["message_count"],
        "batch_count": clean_profile["batch_count"],
    }


def _row_to_profile(row: dict[str, Any]) -> dict[str, Any]:
    return sanitize_profile(
        {
            "traits": row.get("traits", {}),
            "patterns": row.get("patterns", []),
            "overall_confidence": row.get("confidence", 0),
            "message_count": row.get("message_count", 0),
            "batch_count": row.get("batch_count", 0),
        }
    )


def _profile_contact_id(contact: str | None = None) -> str:
    return resolve_profile_contact(contact)


def _profile_type(contact: str | None = None) -> str:
    return "global" if _profile_contact_id(contact) == "global" else "contact"


def _style_profiles_table() -> Any:
    return get_supabase_client().table(STYLE_PROFILES_TABLE)


def _response_rows(response: Any) -> list[dict[str, Any]]:
    rows = getattr(response, "data", None)
    return rows if isinstance(rows, list) else []


def _contact_lookup_keys(contact: str | None) -> list[str]:
    if contact is None:
        return []

    raw = str(contact).strip()
    if not raw:
        return []

    digits = "".join(ch for ch in raw if ch.isdigit())
    keys = [raw, raw.lower(), sanitize_contact_id(raw)]
    if digits:
        keys.append(digits)

    unique_keys: list[str] = []
    for key in keys:
        if key and key not in unique_keys:
            unique_keys.append(key)
    return unique_keys

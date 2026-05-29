import json
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.style_engine import generate_style_adapted_response
from app.style_extractor import batched, extract_style_profile
from app.profile_store import (
    PROFILES_DIR,
    merge_profiles,
    neutral_profile,
    resolve_profile_contact,
    sanitize_contact_id,
)

router = APIRouter(prefix="/style", tags=["style"])


class StyleRequest(BaseModel):
    message: str
    contact_id: str
    user_id: str = "default_user"
    risk_level: str | None = None
    action_type: str | None = None


class StyleLearnRequest(BaseModel):
    user_id: str = "default_user"
    contact_id: str
    messages: list[str] = Field(..., min_length=1)


class StyleLearnResponse(BaseModel):
    user_id: str
    contact_id: str
    profile_type: str
    traits: dict[str, Any]
    patterns: list[str]
    confidence: float
    message_count: int
    batch_count: int


class StyleProfileFile(BaseModel):
    file: str
    contact_id: str
    message_count: int
    batch_count: int
    traits: dict[str, Any]
    patterns: list[Any]
    overall_confidence: Any | None = None
    profile: dict[str, Any]


class StyleProfilesResponse(BaseModel):
    count: int
    profiles: list[StyleProfileFile]


class DeleteStyleProfileResponse(BaseModel):
    deleted: bool
    contact_id: str


def _style_profile_response(file_name: str, contact_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": file_name,
        "contact_id": contact_id,
        "message_count": profile.get("message_count", 0),
        "batch_count": profile.get("batch_count", 0),
        "traits": profile.get("traits", {}),
        "patterns": profile.get("patterns", []),
        "overall_confidence": profile.get("overall_confidence", None),
        "profile": profile,
    }


@router.post("/process")
async def process_style(data: StyleRequest):

    result = generate_style_adapted_response(
        incoming_message=data.message,
        contact_id=data.contact_id,
        user_id=data.user_id,
        risk_level=data.risk_level,
        action_type=data.action_type,
    )

    return result


@router.get("/profiles", response_model=StyleProfilesResponse)
def get_style_profiles():
    profiles: list[dict[str, Any]] = []

    try:
        files = sorted(PROFILES_DIR.glob("profile_*.json"))
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read style profiles: {exc}",
        ) from exc

    for file in files:
        try:
            with file.open("r", encoding="utf-8") as profile_file:
                profile = json.load(profile_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not load style profile {file.name}: {exc}",
            ) from exc

        contact_id = file.stem.replace("profile_", "", 1)
        profiles.append(_style_profile_response(file.name, contact_id, profile))

    return {
        "count": len(profiles),
        "profiles": profiles,
    }


@router.get("/profiles/{contact_id}", response_model=StyleProfileFile)
def get_style_profile(contact_id: str):
    safe_contact_id = sanitize_contact_id(contact_id)
    profile_path = PROFILES_DIR / f"profile_{safe_contact_id}.json"
    if not profile_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    try:
        with profile_path.open("r", encoding="utf-8") as profile_file:
            profile = json.load(profile_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load style profile {profile_path.name}: {exc}",
        ) from exc

    return _style_profile_response(profile_path.name, safe_contact_id, profile)


@router.delete("/profiles/{contact_id}", response_model=DeleteStyleProfileResponse)
def delete_style_profile(contact_id: str):
    safe_contact_id = sanitize_contact_id(contact_id)
    profile_path = PROFILES_DIR / f"profile_{safe_contact_id}.json"
    if not profile_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    try:
        profile_path.unlink()
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete style profile {profile_path.name}: {exc}",
        ) from exc

    return {
        "deleted": True,
        "contact_id": safe_contact_id,
    }


@router.post("/learn", response_model=StyleLearnResponse)
async def learn_style(data: StyleLearnRequest):
    messages = [message.strip() for message in data.messages if message.strip()]
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="messages must include at least one non-empty message",
        )

    contact_id = resolve_profile_contact(data.contact_id)
    profile_type = "global" if contact_id == "global" else "contact"
    merged_profile = neutral_profile(message_count=0, batch_count=0)

    try:
        for batch in batched(messages):
            batch_profile = extract_style_profile(batch, contact=contact_id)
            merged_profile = merge_profiles(merged_profile, batch_profile)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Style learning failed: {exc}",
        ) from exc

    return StyleLearnResponse(
        user_id=data.user_id,
        contact_id=contact_id,
        profile_type=profile_type,
        traits=merged_profile["traits"],
        patterns=merged_profile["patterns"],
        confidence=merged_profile["overall_confidence"],
        message_count=merged_profile["message_count"],
        batch_count=merged_profile["batch_count"],
    )

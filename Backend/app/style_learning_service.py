"""Shared style-learning operations for direct and pending-message learning."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.profile_store import (
    merge_profiles,
    neutral_profile,
    resolve_profile_contact,
    update_profile,
)
from app.style_extractor import batched, extract_style_patterns, extract_style_profile
from app.supabase_client import get_supabase_client


MESSAGES_TABLE = "messages"
STYLE_LEARNING_BATCH_SIZE = 20
PENDING_MESSAGES_PAGE_SIZE = 1000
OUTGOING_DIRECTIONS = ("outgoing", "sent", "outbound")
INCOMING_DIRECTIONS = ("incoming", "received", "inbound")
MESSAGE_COLUMNS = (
    "id,contact_id,direction,message_text,created_at,"
    "global_style_processed,contact_style_processed"
)


class StyleLearningError(RuntimeError):
    """Raised when pending style learning cannot be completed."""


@dataclass(frozen=True)
class PendingTrainingPair:
    outgoing_id: Any
    contact_id: str
    incoming_message: str
    user_reply: str

    def learning_input(self) -> dict[str, str]:
        return {
            "incoming_message": self.incoming_message,
            "user_reply": self.user_reply,
        }


def learn_style_messages(
    messages: list[str | dict[str, str]],
    *,
    contact_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Extract and persist one global or contact-specific style update."""

    resolved_contact = resolve_profile_contact(contact_id)
    merged_profile = neutral_profile(message_count=0, batch_count=0)
    normalized_messages = [_normalize_learning_message(message) for message in messages]
    normalized_messages = [message for message in normalized_messages if message]
    replies = [_reply_text(message) for message in normalized_messages]
    replies = [reply for reply in replies if reply]

    if not replies:
        return merged_profile

    for batch in batched(normalized_messages):
        batch_profile = extract_style_profile(batch, contact=resolved_contact)
        merged_profile = merge_profiles(merged_profile, batch_profile)

    merged_profile["patterns"] = extract_style_patterns(replies)
    return update_profile(
        merged_profile,
        contact=resolved_contact,
        user_id=user_id,
    )


def process_pending_style_learning(user_id: str) -> dict[str, Any]:
    """Process one global batch and one batch for every eligible contact."""

    try:
        conversation_rows = _fetch_conversation_messages()
        global_pairs = _build_training_pairs(
            conversation_rows,
            processed_flag="global_style_processed",
        )
        selected_global_pairs = global_pairs[:STYLE_LEARNING_BATCH_SIZE]
        global_updated = len(selected_global_pairs) == STYLE_LEARNING_BATCH_SIZE
        global_message_count = 0

        if global_updated:
            learn_style_messages(
                [pair.learning_input() for pair in selected_global_pairs],
                contact_id="global",
                user_id=user_id,
            )
            _mark_messages_processed(
                [pair.outgoing_id for pair in selected_global_pairs],
                "global_style_processed",
            )
            global_message_count = STYLE_LEARNING_BATCH_SIZE

        contact_pairs = _build_training_pairs(
            conversation_rows,
            processed_flag="contact_style_processed",
        )
        pairs_by_contact: dict[str, list[PendingTrainingPair]] = defaultdict(list)
        for pair in contact_pairs:
            pairs_by_contact[pair.contact_id].append(pair)

        contacts_updated: list[dict[str, Any]] = []
        skipped_contacts: list[dict[str, Any]] = []
        for contact_id, pairs in pairs_by_contact.items():
            if len(pairs) < STYLE_LEARNING_BATCH_SIZE:
                skipped_contacts.append(
                    {
                        "contact_id": contact_id,
                        "available_messages": len(pairs),
                        "reason": "less than 20 messages",
                    }
                )
                continue

            selected_pairs = pairs[:STYLE_LEARNING_BATCH_SIZE]
            learn_style_messages(
                [pair.learning_input() for pair in selected_pairs],
                contact_id=contact_id,
                user_id=user_id,
            )
            _mark_messages_processed(
                [pair.outgoing_id for pair in selected_pairs],
                "contact_style_processed",
            )
            contacts_updated.append(
                {
                    "contact_id": contact_id,
                    "message_count": STYLE_LEARNING_BATCH_SIZE,
                }
            )

        return {
            "global_updated": global_updated,
            "global_message_count": global_message_count,
            "contacts_updated": contacts_updated,
            "skipped_contacts": skipped_contacts,
        }
    except Exception as exc:
        if isinstance(exc, StyleLearningError):
            raise
        raise StyleLearningError(str(exc)) from exc


def _fetch_conversation_messages() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _execute_rows(
            _conversation_messages_query().range(
                offset,
                offset + PENDING_MESSAGES_PAGE_SIZE - 1,
            )
        )
        rows.extend(page)
        if len(page) < PENDING_MESSAGES_PAGE_SIZE:
            return rows
        offset += PENDING_MESSAGES_PAGE_SIZE


def _conversation_messages_query() -> Any:
    return (
        get_supabase_client()
        .table(MESSAGES_TABLE)
        .select(MESSAGE_COLUMNS)
        .order("created_at", desc=False)
        .order("id", desc=False)
    )


def _build_training_pairs(
    rows: list[dict[str, Any]],
    *,
    processed_flag: str,
) -> list[PendingTrainingPair]:
    latest_incoming_by_contact: dict[str, str] = {}
    pairs: list[PendingTrainingPair] = []

    for row in rows:
        contact_id = str(row.get("contact_id") or "").strip()
        message_text = _message_text(row)
        direction = str(row.get("direction") or "").strip().lower()
        if not contact_id or not message_text:
            continue

        if direction in INCOMING_DIRECTIONS:
            latest_incoming_by_contact[contact_id] = message_text
            continue

        if direction not in OUTGOING_DIRECTIONS or row.get(processed_flag) is True:
            continue

        incoming_message = latest_incoming_by_contact.get(contact_id)
        if not incoming_message:
            continue

        pairs.append(
            PendingTrainingPair(
                outgoing_id=row.get("id"),
                contact_id=contact_id,
                incoming_message=incoming_message,
                user_reply=message_text,
            )
        )

    return pairs


def _execute_rows(query: Any) -> list[dict[str, Any]]:
    response = query.execute()
    rows = getattr(response, "data", None)
    if not isinstance(rows, list):
        raise StyleLearningError("Supabase returned an invalid messages response.")
    return rows


def _mark_messages_processed(message_ids: list[Any], processed_flag: str) -> None:
    if not message_ids:
        return

    response = (
        get_supabase_client()
        .table(MESSAGES_TABLE)
        .update({processed_flag: True})
        .in_("id", message_ids)
        .execute()
    )
    response_error = getattr(response, "error", None)
    if response_error:
        raise StyleLearningError(str(response_error))


def _message_text(row: dict[str, Any]) -> str:
    return str(row.get("message_text") or "").strip()


def _reply_text(message: str | dict[str, str]) -> str:
    if isinstance(message, str):
        return message.strip()
    return str(message.get("reply") or message.get("user_reply") or "").strip()


def _normalize_learning_message(
    message: str | dict[str, str],
) -> str | dict[str, str] | None:
    if isinstance(message, str):
        clean_message = message.strip()
        return clean_message or None

    reply = _reply_text(message)
    if not reply:
        return None
    context = str(
        message.get("context") or message.get("incoming_message") or ""
    ).strip()
    return {
        "context": context,
        "reply": reply,
    }

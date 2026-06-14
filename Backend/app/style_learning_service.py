"""Shared style-learning operations for direct and pending-message learning."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
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


LOGGER = logging.getLogger(__name__)
MESSAGES_TABLE = "messages"
STYLE_LEARNING_BATCH_SIZE = 20
PENDING_MESSAGES_PAGE_SIZE = 1000
OUTGOING_DIRECTIONS = ("outgoing", "sent", "outbound")
INCOMING_DIRECTIONS = ("incoming", "received", "inbound")
MESSAGE_COLUMNS = (
    "id,contact_id,direction,message_text,created_at,"
    "global_style_processed,contact_style_processed"
)
PENDING_MESSAGES_SQL = (
    "SELECT id, contact_id, direction, message_text, created_at, "
    "global_style_processed, contact_style_processed "
    "FROM public.messages ORDER BY created_at ASC, id ASC "
    f"LIMIT {PENDING_MESSAGES_PAGE_SIZE} OFFSET {{offset}};"
)


class StyleLearningError(RuntimeError):
    """Raised when pending style learning cannot be completed."""


@dataclass(frozen=True)
class PendingTrainingPair:
    incoming_id: Any
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
        LOGGER.warning(
            "Pending style learning started: user_id=%s (user_id is not "
            "currently applied to the messages query)",
            user_id,
        )
        conversation_rows = _fetch_conversation_messages()
        _log_fetched_message_diagnostics(conversation_rows)
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
            _mark_training_pairs_processed(
                selected_global_pairs,
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
                        "reason": "requires 20 or more messages",
                    }
                )
                continue

            selected_pairs = pairs[:STYLE_LEARNING_BATCH_SIZE]
            learn_style_messages(
                [pair.learning_input() for pair in selected_pairs],
                contact_id=contact_id,
                user_id=user_id,
            )
            _mark_training_pairs_processed(
                selected_pairs,
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
        LOGGER.warning(
            "Pending style learning Supabase query (SQL equivalent; no user_id "
            "filter): %s",
            PENDING_MESSAGES_SQL.format(offset=offset),
        )
        page = _execute_rows(
            _conversation_messages_query().range(
                offset,
                offset + PENDING_MESSAGES_PAGE_SIZE - 1,
            )
        )
        LOGGER.warning(
            "Pending style learning fetched page: offset=%d rows=%d",
            offset,
            len(page),
        )
        rows.extend(page)
        if len(page) < PENDING_MESSAGES_PAGE_SIZE:
            LOGGER.warning(
                "Pending style learning total rows fetched from Supabase: %d",
                len(rows),
            )
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
    latest_incoming_by_contact: dict[str, tuple[Any, str]] = {}
    pairs: list[PendingTrainingPair] = []
    incoming_remaining_after_filtering: Counter[str] = Counter()
    outgoing_remaining_after_filtering: Counter[str] = Counter()
    valid_pair_counts: Counter[str] = Counter()
    processed_outgoing_skipped: Counter[str] = Counter()
    unmatched_outgoing_reasons: dict[str, Counter[str]] = defaultdict(Counter)
    unmatched_outgoing_ids: dict[str, dict[str, list[Any]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for row in rows:
        row_id = row.get("id")
        contact_id = str(row.get("contact_id") or "").strip()
        message_text = _message_text(row)
        direction = str(row.get("direction") or "").strip().lower()
        if not contact_id:
            LOGGER.warning(
                "Pending style pair skipped: flag=%s row_id=%r reason=missing "
                "contact_id",
                processed_flag,
                row_id,
            )
            continue
        if not message_text:
            LOGGER.warning(
                "Pending style pair skipped: flag=%s contact_id=%s row_id=%r "
                "reason=empty message_text",
                processed_flag,
                contact_id,
                row_id,
            )
            continue

        if direction in INCOMING_DIRECTIONS:
            if row.get(processed_flag) is True:
                latest_incoming_by_contact.pop(contact_id, None)
                LOGGER.warning(
                    "Pending style incoming skipped: flag=%s contact_id=%s "
                    "row_id=%r reason=%s is true",
                    processed_flag,
                    contact_id,
                    row_id,
                    processed_flag,
                )
                continue
            latest_incoming_by_contact[contact_id] = (row_id, message_text)
            incoming_remaining_after_filtering[contact_id] += 1
            continue

        if direction not in OUTGOING_DIRECTIONS:
            LOGGER.warning(
                "Pending style pair skipped: flag=%s contact_id=%s row_id=%r "
                "reason=unsupported direction direction=%r",
                processed_flag,
                contact_id,
                row_id,
                direction,
            )
            continue

        if row.get(processed_flag) is True:
            processed_outgoing_skipped[contact_id] += 1
            latest_incoming_by_contact.pop(contact_id, None)
            LOGGER.warning(
                "Pending style pair skipped: flag=%s contact_id=%s row_id=%r "
                "reason=%s is true",
                processed_flag,
                contact_id,
                row_id,
                processed_flag,
            )
            continue

        outgoing_remaining_after_filtering[contact_id] += 1
        incoming = latest_incoming_by_contact.pop(contact_id, None)
        if not incoming:
            reason = "no unprocessed, unconsumed preceding incoming message"
            unmatched_outgoing_reasons[contact_id][reason] += 1
            unmatched_outgoing_ids[contact_id][reason].append(row_id)
            LOGGER.warning(
                "Pending style pair skipped: flag=%s contact_id=%s row_id=%r "
                "reason=no unprocessed, unconsumed preceding incoming message",
                processed_flag,
                contact_id,
                row_id,
            )
            continue

        incoming_id, incoming_message = incoming
        pairs.append(
            PendingTrainingPair(
                incoming_id=incoming_id,
                outgoing_id=row.get("id"),
                contact_id=contact_id,
                incoming_message=incoming_message,
                user_reply=message_text,
            )
        )
        valid_pair_counts[contact_id] += 1

    contact_ids = sorted(
        {
            str(row.get("contact_id") or "").strip()
            for row in rows
            if str(row.get("contact_id") or "").strip()
        }
    )
    for contact_id in contact_ids:
        unmatched_outgoing_count = (
            outgoing_remaining_after_filtering[contact_id]
            - valid_pair_counts[contact_id]
        )
        LOGGER.warning(
            "Pending style pair reconciliation: flag=%s contact_id=%s "
            "incoming_remaining_after_filtering=%d "
            "outgoing_remaining_after_filtering=%d valid_pair_count=%d "
            "unmatched_unprocessed_outgoing_count=%d "
            "unmatched_unprocessed_outgoing_reasons=%s "
            "unmatched_unprocessed_outgoing_ids=%s "
            "processed_outgoing_skipped=%d",
            processed_flag,
            contact_id,
            incoming_remaining_after_filtering[contact_id],
            outgoing_remaining_after_filtering[contact_id],
            valid_pair_counts[contact_id],
            unmatched_outgoing_count,
            dict(unmatched_outgoing_reasons[contact_id]),
            {
                reason: ids
                for reason, ids in unmatched_outgoing_ids[contact_id].items()
            },
            processed_outgoing_skipped[contact_id],
        )

    return pairs


def _pair_message_ids(pairs: list[PendingTrainingPair]) -> list[Any]:
    message_ids: list[Any] = []
    seen: set[Any] = set()
    for pair in pairs:
        for message_id in (pair.incoming_id, pair.outgoing_id):
            if message_id is not None and message_id not in seen:
                seen.add(message_id)
                message_ids.append(message_id)
    return message_ids


def _mark_training_pairs_processed(
    pairs: list[PendingTrainingPair],
    processed_flag: str,
) -> None:
    incoming_ids = [pair.incoming_id for pair in pairs]
    outgoing_ids = [pair.outgoing_id for pair in pairs]
    message_ids = _pair_message_ids(pairs)
    LOGGER.warning(
        "Pending style marking completed pairs: flag=%s pair_count=%d "
        "incoming_ids=%s outgoing_ids=%s all_message_ids=%s",
        processed_flag,
        len(pairs),
        incoming_ids,
        outgoing_ids,
        message_ids,
    )
    _mark_messages_processed(message_ids, processed_flag)


def _log_fetched_message_diagnostics(rows: list[dict[str, Any]]) -> None:
    rows_by_contact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        contact_id = str(row.get("contact_id") or "").strip() or "<missing>"
        rows_by_contact[contact_id].append(row)

    for contact_id in sorted(rows_by_contact):
        contact_rows = rows_by_contact[contact_id]
        remaining_rows = [
            row
            for row in contact_rows
            if contact_id != "<missing>"
            and _message_text(row)
            and str(row.get("direction") or "").strip().lower()
            in (*INCOMING_DIRECTIONS, *OUTGOING_DIRECTIONS)
        ]
        incoming_count = sum(
            str(row.get("direction") or "").strip().lower()
            in INCOMING_DIRECTIONS
            for row in remaining_rows
        )
        outgoing_count = sum(
            str(row.get("direction") or "").strip().lower()
            in OUTGOING_DIRECTIONS
            for row in remaining_rows
        )
        global_flags = _processed_flag_counts(
            contact_rows,
            "global_style_processed",
        )
        contact_flags = _processed_flag_counts(
            contact_rows,
            "contact_style_processed",
        )
        LOGGER.warning(
            "Pending style contact rows: contact_id=%s fetched=%d "
            "rows_after_structural_filter=%d incoming=%d outgoing=%d "
            "global_style_processed=%s contact_style_processed=%s",
            contact_id,
            len(contact_rows),
            len(remaining_rows),
            incoming_count,
            outgoing_count,
            global_flags,
            contact_flags,
        )


def _processed_flag_counts(
    rows: list[dict[str, Any]],
    processed_flag: str,
) -> dict[str, int]:
    counts = {"true": 0, "false": 0, "null_or_missing": 0}
    for row in rows:
        value = row.get(processed_flag)
        if value is True:
            counts["true"] += 1
        elif value is False:
            counts["false"] += 1
        else:
            counts["null_or_missing"] += 1
    return counts


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

    updated_rows = getattr(response, "data", None)
    if not isinstance(updated_rows, list):
        raise StyleLearningError(
            f"Supabase did not return updated rows for {processed_flag}."
        )

    requested_ids = set(message_ids)
    updated_ids = {
        row.get("id")
        for row in updated_rows
        if isinstance(row, dict) and row.get("id") is not None
    }
    missing_ids = requested_ids - updated_ids
    if missing_ids:
        raise StyleLearningError(
            f"Supabase did not mark all rows for {processed_flag}; "
            f"missing ids: {sorted(missing_ids, key=str)}"
        )

    LOGGER.warning(
        "Pending style processed update confirmed: flag=%s updated_count=%d "
        "updated_ids=%s",
        processed_flag,
        len(updated_ids),
        sorted(updated_ids, key=str),
    )


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

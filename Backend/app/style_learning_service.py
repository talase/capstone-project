"""Shared style-learning operations for direct and pending-message learning."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.profile_store import (
    load_profile,
    merge_profiles,
    neutral_profile,
    resolve_profile_contact,
    update_profile,
)
from app.style_extractor import batched, extract_style_patterns, extract_style_profile
from app.supabase_client import get_supabase_client


LOGGER = logging.getLogger(__name__)
MESSAGES_TABLE = "messages"
STYLE_LEARNING_BATCH_SIZE = 50
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


class StyleProfileGenerationError(RuntimeError):
    """Raised when style profile extraction fails."""


class StyleProfilePersistenceError(RuntimeError):
    """Raised when a generated style profile cannot be persisted."""


@dataclass(frozen=True)
class PendingTrainingPair:
    incoming_ids: tuple[Any, ...]
    outgoing_ids: tuple[Any, ...]
    contact_id: str
    incoming_message: str
    user_reply: str
    source_order: int = field(default=0, repr=False)

    def learning_input(self) -> dict[str, str]:
        return {
            "incoming_message": self.incoming_message,
            "user_reply": self.user_reply,
        }

    @property
    def incoming_id(self) -> Any:
        return self.incoming_ids[0] if self.incoming_ids else None

    @property
    def outgoing_id(self) -> Any:
        return self.outgoing_ids[0] if self.outgoing_ids else None


@dataclass
class _MessageRun:
    direction: str
    rows: list[tuple[int, dict[str, Any]]]

    @property
    def source_order(self) -> int:
        return self.rows[0][0]

    @property
    def ids(self) -> tuple[Any, ...]:
        return tuple(row.get("id") for _, row in self.rows)

    @property
    def text(self) -> str:
        return "\n".join(_message_text(row) for _, row in self.rows)


@dataclass(frozen=True)
class _PendingTrainingWork:
    pairs: list[PendingTrainingPair]
    context_only_incoming_by_contact: dict[str, list[Any]]

    @property
    def context_only_incoming_ids(self) -> list[Any]:
        return [
            message_id
            for ids in self.context_only_incoming_by_contact.values()
            for message_id in ids
        ]


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
        LOGGER.warning(
            "Style profile generation skipped: contact_id=%s reason=no "
            "outgoing reply text after normalization",
            resolved_contact,
        )
        return merged_profile

    LOGGER.warning(
        "Style profile generation attempted: contact_id=%s turns=%d",
        resolved_contact,
        len(normalized_messages),
    )
    try:
        for batch in batched(normalized_messages):
            batch_profile = extract_style_profile(
                batch,
                contact=resolved_contact,
            )
            merged_profile = merge_profiles(merged_profile, batch_profile)
    except Exception as exc:
        LOGGER.exception(
            "Style profile generation failed: contact_id=%s turns=%d",
            resolved_contact,
            len(normalized_messages),
        )
        raise StyleProfileGenerationError(
            f"Profile generation failed for {resolved_contact}: {exc}"
        ) from exc

    merged_profile["patterns"] = extract_style_patterns(replies)
    existing_profile = load_profile(resolved_contact, user_id=user_id)
    LOGGER.warning(
        "Style profile database update attempted: contact_id=%s user_id=%s",
        resolved_contact,
        user_id,
    )
    try:
        persisted_profile = update_profile(
            merged_profile,
            contact=resolved_contact,
            user_id=user_id,
        )
    except Exception as exc:
        LOGGER.exception(
            "Style profile database update failed: contact_id=%s user_id=%s",
            resolved_contact,
            user_id,
        )
        raise StyleProfilePersistenceError(
            f"Profile persistence failed for {resolved_contact}: {exc}"
        ) from exc

    profile_unchanged = persisted_profile == existing_profile
    LOGGER.warning(
        "Style profile update completed: contact_id=%s "
        "profile_unchanged=%s unchanged_profile_skipped=false",
        resolved_contact,
        profile_unchanged,
    )
    return persisted_profile


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
        global_work = _build_training_work(
            conversation_rows,
            processed_flag="global_style_processed",
        )
        global_pairs = global_work.pairs
        selected_global_pairs = global_pairs[:STYLE_LEARNING_BATCH_SIZE]
        global_updated = len(selected_global_pairs) == STYLE_LEARNING_BATCH_SIZE
        global_message_count = 0

        LOGGER.warning(
            "Global style learning threshold check: turn_count=%d threshold=%d",
            len(global_pairs),
            STYLE_LEARNING_BATCH_SIZE,
        )
        if global_updated:
            _run_pending_learning_pass(
                selected_global_pairs,
                contact_id="global",
                user_id=user_id,
                scope="global",
            )
            _mark_training_pairs_processed(
                selected_global_pairs,
                "global_style_processed",
            )
            global_message_count = STYLE_LEARNING_BATCH_SIZE
        else:
            LOGGER.warning(
                "Skipping global learning: only %d turns, threshold=%d; "
                "profile_generation_attempted=false",
                len(global_pairs),
                STYLE_LEARNING_BATCH_SIZE,
            )
        _mark_context_only_incoming_processed(
            global_work.context_only_incoming_ids,
            "global_style_processed",
        )
        global_pending = _processing_counts(
            "global_style_processed",
            learnable_before=len(global_pairs),
            learned=len(selected_global_pairs) if global_updated else 0,
            context_only_before=len(global_work.context_only_incoming_ids),
            context_only_processed=len(global_work.context_only_incoming_ids),
        )

        contact_work = _build_training_work(
            conversation_rows,
            processed_flag="contact_style_processed",
        )
        pairs_by_contact: dict[str, list[PendingTrainingPair]] = defaultdict(list)
        for pair in contact_work.pairs:
            pairs_by_contact[pair.contact_id].append(pair)

        contacts_updated: list[dict[str, Any]] = []
        skipped_contacts: list[dict[str, Any]] = []
        learned_by_contact: Counter[str] = Counter()
        for contact_id, pairs in pairs_by_contact.items():
            LOGGER.warning(
                "Contact style learning threshold check: contact_id=%s "
                "turn_count=%d threshold=%d",
                contact_id,
                len(pairs),
                STYLE_LEARNING_BATCH_SIZE,
            )
            if len(pairs) < STYLE_LEARNING_BATCH_SIZE:
                LOGGER.warning(
                    "Skipping contact learning: contact_id=%s only %d turns, "
                    "threshold=%d; profile_generation_attempted=false",
                    contact_id,
                    len(pairs),
                    STYLE_LEARNING_BATCH_SIZE,
                )
                skipped_contacts.append(
                    {
                        "contact_id": contact_id,
                        "available_messages": len(pairs),
                        "reason": (
                            f"requires {STYLE_LEARNING_BATCH_SIZE} or more "
                            "messages"
                        ),
                    }
                )
                continue

            selected_pairs = pairs[:STYLE_LEARNING_BATCH_SIZE]
            _run_pending_learning_pass(
                selected_pairs,
                contact_id=contact_id,
                user_id=user_id,
                scope="contact",
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
            learned_by_contact[contact_id] = len(selected_pairs)

        for contact_id, incoming_ids in (
            contact_work.context_only_incoming_by_contact.items()
        ):
            _mark_context_only_incoming_processed(
                incoming_ids,
                "contact_style_processed",
                contact_id=contact_id,
            )

        contact_ids = sorted(
            set(pairs_by_contact)
            | set(contact_work.context_only_incoming_by_contact)
        )
        contact_pending = {
            contact_id: _processing_counts(
                "contact_style_processed",
                contact_id=contact_id,
                learnable_before=len(pairs_by_contact[contact_id]),
                learned=learned_by_contact[contact_id],
                context_only_before=len(
                    contact_work.context_only_incoming_by_contact.get(
                        contact_id,
                        [],
                    )
                ),
                context_only_processed=len(
                    contact_work.context_only_incoming_by_contact.get(
                        contact_id,
                        [],
                    )
                ),
            )
            for contact_id in contact_ids
        }

        return {
            "global_updated": global_updated,
            "global_message_count": global_message_count,
            "contacts_updated": contacts_updated,
            "skipped_contacts": skipped_contacts,
            "global_pending": global_pending,
            "contact_pending": contact_pending,
        }
    except Exception as exc:
        if isinstance(exc, StyleLearningError):
            raise
        raise StyleLearningError(str(exc)) from exc


def _run_pending_learning_pass(
    pairs: list[PendingTrainingPair],
    *,
    contact_id: str,
    user_id: str,
    scope: str,
) -> dict[str, Any]:
    label = "Global" if scope == "global" else "Contact"
    LOGGER.warning(
        "%s learning attempted: contact_id=%s turn_count=%d threshold=%d "
        "profile_generation_attempted=true",
        label,
        contact_id,
        len(pairs),
        STYLE_LEARNING_BATCH_SIZE,
    )
    try:
        profile = learn_style_messages(
            [pair.learning_input() for pair in pairs],
            contact_id=contact_id,
            user_id=user_id,
        )
    except StyleProfileGenerationError:
        LOGGER.exception(
            "%s learning attempted but profile generation failed: "
            "contact_id=%s turn_count=%d",
            label,
            contact_id,
            len(pairs),
        )
        raise
    except StyleProfilePersistenceError:
        LOGGER.exception(
            "%s learning attempted but database update failed: "
            "contact_id=%s turn_count=%d",
            label,
            contact_id,
            len(pairs),
        )
        raise
    except Exception:
        LOGGER.exception(
            "%s learning attempted but profile generation or persistence "
            "failed: contact_id=%s turn_count=%d",
            label,
            contact_id,
            len(pairs),
        )
        raise

    LOGGER.warning(
        "%s learning succeeded: contact_id=%s learned_turns=%d "
        "profile_generation_failed=false database_update_failed=false",
        label,
        contact_id,
        len(pairs),
    )
    return profile


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
    return _build_training_work(rows, processed_flag=processed_flag).pairs


def _build_training_work(
    rows: list[dict[str, Any]],
    *,
    processed_flag: str,
) -> _PendingTrainingWork:
    eligible_by_contact: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    pairs: list[PendingTrainingPair] = []
    context_only_rows_by_contact: dict[
        str,
        list[tuple[int, Any]],
    ] = defaultdict(list)
    incoming_remaining_after_filtering: Counter[str] = Counter()
    outgoing_remaining_after_filtering: Counter[str] = Counter()
    valid_pair_counts: Counter[str] = Counter()
    processed_outgoing_skipped: Counter[str] = Counter()

    for source_order, row in enumerate(rows):
        row_id = row.get("id")
        contact_id = str(row.get("contact_id") or "").strip()
        message_text = _message_text(row)
        direction = str(row.get("direction") or "").strip().lower()

        if direction in INCOMING_DIRECTIONS:
            context_contact_id = contact_id or "<missing>"
            if row.get(processed_flag) is True:
                LOGGER.warning(
                    "Pending style incoming skipped: flag=%s contact_id=%s "
                    "row_id=%r reason=%s is true",
                    processed_flag,
                    context_contact_id,
                    row_id,
                    processed_flag,
                )
                continue
            incoming_remaining_after_filtering[context_contact_id] += 1
            if row_id is None:
                LOGGER.warning(
                    "Pending style incoming skipped: flag=%s contact_id=%s "
                    "reason=missing id cannot mark context-only processed",
                    processed_flag,
                    context_contact_id,
                )
                continue
            if not contact_id or not message_text:
                reason = (
                    "missing contact_id"
                    if not contact_id
                    else "empty message_text"
                )
                context_only_rows_by_contact[context_contact_id].append(
                    (source_order, row_id)
                )
                LOGGER.warning(
                    "Pending style incoming classified context-only: flag=%s "
                    "contact_id=%s row_ids=%s reason=%s",
                    processed_flag,
                    context_contact_id,
                    [row_id],
                    reason,
                )
                continue
            eligible_by_contact[contact_id].append((source_order, row))
            continue

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
        eligible_by_contact[contact_id].append((source_order, row))

    for contact_id, contact_rows in eligible_by_contact.items():
        runs = _group_direction_runs(contact_rows)
        outgoing_run_indexes = [
            index for index, run in enumerate(runs) if run.direction == "outgoing"
        ]
        incoming_assignments: dict[int, list[_MessageRun]] = defaultdict(list)

        for incoming_index, run in enumerate(runs):
            if run.direction != "incoming":
                continue
            closest_outgoing_index = min(
                outgoing_run_indexes,
                key=lambda outgoing_index: (
                    abs(outgoing_index - incoming_index),
                    0 if outgoing_index > incoming_index else 1,
                ),
                default=None,
            )
            if closest_outgoing_index is None:
                context_only_rows_by_contact[contact_id].extend(
                    (source_order, row.get("id"))
                    for source_order, row in run.rows
                )
                LOGGER.warning(
                    "Pending style incoming classified context-only: flag=%s "
                    "contact_id=%s row_ids=%s reason=no unprocessed outgoing "
                    "user message available",
                    processed_flag,
                    contact_id,
                    list(run.ids),
                )
                continue
            incoming_assignments[closest_outgoing_index].append(run)

        for outgoing_index in outgoing_run_indexes:
            outgoing_run = runs[outgoing_index]
            context_runs = sorted(
                incoming_assignments[outgoing_index],
                key=lambda run: run.source_order,
            )
            incoming_ids = tuple(
                message_id
                for run in context_runs
                for message_id in run.ids
            )
            pair = PendingTrainingPair(
                incoming_ids=incoming_ids,
                outgoing_ids=outgoing_run.ids,
                contact_id=contact_id,
                incoming_message="\n".join(run.text for run in context_runs),
                user_reply=outgoing_run.text,
                source_order=outgoing_run.source_order,
            )
            pairs.append(pair)
            valid_pair_counts[contact_id] += 1
            LOGGER.warning(
                "Pending style turn built: flag=%s contact_id=%s "
                "incoming_ids=%s outgoing_ids=%s",
                processed_flag,
                contact_id,
                list(pair.incoming_ids),
                list(pair.outgoing_ids),
            )

    contact_ids = sorted(
        {
            str(row.get("contact_id") or "").strip()
            for row in rows
            if str(row.get("contact_id") or "").strip()
        }
    )
    for contact_id in contact_ids:
        LOGGER.warning(
            "Pending style pair reconciliation: flag=%s contact_id=%s "
            "incoming_remaining_after_filtering=%d "
            "outgoing_remaining_after_filtering=%d valid_turn_count=%d "
            "processed_outgoing_skipped=%d",
            processed_flag,
            contact_id,
            incoming_remaining_after_filtering[contact_id],
            outgoing_remaining_after_filtering[contact_id],
            valid_pair_counts[contact_id],
            processed_outgoing_skipped[contact_id],
        )

    return _PendingTrainingWork(
        pairs=sorted(pairs, key=lambda pair: pair.source_order),
        context_only_incoming_by_contact={
            contact_id: [
                message_id
                for _, message_id in sorted(context_rows)
            ]
            for contact_id, context_rows in context_only_rows_by_contact.items()
        },
    )


def _group_direction_runs(
    rows: list[tuple[int, dict[str, Any]]],
) -> list[_MessageRun]:
    runs: list[_MessageRun] = []
    for source_order, row in rows:
        raw_direction = str(row.get("direction") or "").strip().lower()
        direction = (
            "incoming" if raw_direction in INCOMING_DIRECTIONS else "outgoing"
        )
        if runs and runs[-1].direction == direction:
            runs[-1].rows.append((source_order, row))
        else:
            runs.append(_MessageRun(direction, [(source_order, row)]))
    return runs


def _pair_message_ids(pairs: list[PendingTrainingPair]) -> list[Any]:
    message_ids: list[Any] = []
    seen: set[Any] = set()
    for pair in pairs:
        for message_id in (*pair.incoming_ids, *pair.outgoing_ids):
            if message_id is not None and message_id not in seen:
                seen.add(message_id)
                message_ids.append(message_id)
    return message_ids


def _mark_training_pairs_processed(
    pairs: list[PendingTrainingPair],
    processed_flag: str,
) -> None:
    incoming_ids = [
        message_id for pair in pairs for message_id in pair.incoming_ids
    ]
    outgoing_ids = [
        message_id for pair in pairs for message_id in pair.outgoing_ids
    ]
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


def _mark_context_only_incoming_processed(
    incoming_ids: list[Any],
    processed_flag: str,
    *,
    contact_id: str | None = None,
) -> None:
    if not incoming_ids:
        return
    LOGGER.warning(
        "Pending style retiring context-only incoming: flag=%s contact_id=%s "
        "incoming_ids=%s reason=not learnable as user style",
        processed_flag,
        contact_id or "global",
        incoming_ids,
    )
    _mark_messages_processed(incoming_ids, processed_flag)


def _processing_counts(
    processed_flag: str,
    *,
    learnable_before: int,
    learned: int,
    context_only_before: int,
    context_only_processed: int,
    contact_id: str | None = None,
) -> dict[str, int]:
    counts = {
        "learnable_outgoing_turns_before": learnable_before,
        "learned_outgoing_turns": learned,
        "learnable_outgoing_turns_after": learnable_before - learned,
        "context_only_incoming_before": context_only_before,
        "context_only_incoming_processed": context_only_processed,
        "context_only_incoming_after": (
            context_only_before - context_only_processed
        ),
    }
    LOGGER.warning(
        "Pending style processing counts: flag=%s contact_id=%s counts=%s",
        processed_flag,
        contact_id or "global",
        counts,
    )
    return counts


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

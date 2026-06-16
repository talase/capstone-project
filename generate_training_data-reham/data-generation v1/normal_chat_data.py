import os
import re
import time
from pathlib import Path

from openai import OpenAI


# Configurable generation settings for the normal_chat class.
EXAMPLES_PER_SUBTYPE = 500
BATCH_SIZE = 50
MAX_TOKENS_PER_BATCH = 4000
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
OUTPUT_DIR = Path("normal_chat_dataset")
COMBINED_FILENAME = "normal_chat_all.txt"

# The OpenAI SDK is used only as an OpenAI-compatible request client.
# Requests are sent to OpenRouter, then OpenRouter routes them to DeepSeek only
# through provider.only in extra_body.
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_ATTEMPTS_PER_SUBTYPE = 45


NORMAL_CHAT_SUBTYPES = [
    {
        "slug": "casual_greetings_and_small_talk",
        "name": "casual greetings and small talk",
        "guidance": (
            "Everyday greetings, check-ins, small talk, casual questions, friendly openers, "
            "and simple conversational messages."
        ),
    },
    {
        "slug": "emotional_support_and_personal_feelings",
        "name": "emotional support and personal feelings",
        "guidance": (
            "Messages expressing feelings, stress, happiness, sadness, frustration, support, "
            "encouragement, or personal reflection without urgent crisis action."
        ),
    },
    {
        "slug": "general_questions_and_information_seeking",
        "name": "general questions and information seeking",
        "guidance": (
            "General informational questions, curiosity, simple facts, explanations, opinions, "
            "and knowledge-seeking without asking the agent to perform a supported action."
        ),
    },
    {
        "slug": "opinions_advice_and_recommendations",
        "name": "opinions, advice, and recommendations",
        "guidance": (
            "Messages asking for opinions, advice, suggestions, recommendations, judgment, "
            "or perspective without asking the agent to send, schedule, pay, approve, or upload."
        ),
    },
    {
        "slug": "daily_life_updates",
        "name": "daily life updates",
        "guidance": (
            "Ordinary updates about daily activities, errands, family, food, travel, weather, "
            "commuting, chores, hobbies, or routine events."
        ),
    },
    {
        "slug": "jokes_reactions_and_social_conversation",
        "name": "jokes, reactions, and social conversation",
        "guidance": (
            "Jokes, memes, reactions, teasing, casual replies, surprise, laughter, opinions, "
            "and social back-and-forth."
        ),
    },
    {
        "slug": "thanks_apologies_and_polite_replies",
        "name": "thanks, apologies, and polite replies",
        "guidance": (
            "Thank-you messages, apologies, polite replies, acknowledgments, appreciation, "
            "and social niceties without action requests."
        ),
    },
    {
        "slug": "status_updates_and_availability_statements",
        "name": "status updates and availability statements",
        "guidance": (
            "Messages stating status, location, availability, busyness, delays, mood, progress, "
            "or what the sender is doing without asking to schedule or coordinate."
        ),
    },
    {
        "slug": "reminders_or_notes_to_self_with_no_external_action",
        "name": "reminders or notes to self with no external action",
        "guidance": (
            "Personal reminders, notes to self, thoughts, lists, or internal reminders that do "
            "not ask the user or agent to remind, notify, or message another person."
        ),
    },
    {
        "slug": "general_work_or_school_discussion",
        "name": "general work or school discussion",
        "guidance": (
            "Work or school conversation, class talk, project discussion, office updates, study "
            "comments, or team chatter without requesting a supported action."
        ),
    },
    {
        "slug": "money_mentioned_but_no_money_request",
        "name": "money mentioned but no money request",
        "guidance": (
            "Messages mentioning money, rent, bills, payment, refund, salary, debt, donation, "
            "or prices without asking anyone to send, provide, transfer, pay, lend, refund, or donate money."
        ),
    },
    {
        "slug": "financial_advice_or_budgeting_questions",
        "name": "financial advice or budgeting questions",
        "guidance": (
            "Questions about budgeting, saving, prices, spending, salary planning, debt strategy, "
            "or financial opinions without requesting money or payment."
        ),
    },
    {
        "slug": "health_or_stress_mentioned_but_no_emergency",
        "name": "health or stress mentioned but no emergency",
        "guidance": (
            "Messages mentioning health, stress, fatigue, symptoms, appointments, or worries "
            "without urgent emergency help, ambulance, rescue, police, or crisis response."
        ),
    },
    {
        "slug": "accident_danger_or_emergency_words_in_non_urgent_context",
        "name": "accident, danger, or emergency words in non-urgent context",
        "guidance": (
            "Messages using words like accident, danger, fire, police, hospital, or emergency "
            "in stories, jokes, reflections, news, hypothetical, or non-urgent contexts."
        ),
    },
    {
        "slug": "harmless_confirmations_and_agreement_opinions",
        "name": "harmless confirmations and agreement opinions",
        "guidance": (
            "Low-risk confirmations, agreement opinions, yes/no social replies, or harmless "
            "confirmation statements that do not approve a binding agreement."
        ),
    },
    {
        "slug": "contract_or_agreement_mentioned_without_approval_request",
        "name": "contract or agreement mentioned without approval request",
        "guidance": (
            "Messages mentioning a contract, agreement, approval, confirmation, consent, or "
            "terms without asking the user to sign, approve, accept, authorize, confirm, or consent."
        ),
    },
    {
        "slug": "file_mentioned_but_no_request_to_send",
        "name": "file mentioned but no request to send",
        "guidance": (
            "Messages mentioning files, PDFs, documents, screenshots, attachments, reports, "
            "slides, or forms without asking the user to send, share, upload, forward, attach, submit, provide, or resend them."
        ),
    },
    {
        "slug": "asking_whether_a_file_exists_or_was_received",
        "name": "asking whether a file exists or was received",
        "guidance": (
            "Messages asking whether a file exists, arrived, opened, loaded, was received, "
            "or is visible without asking the user to send or upload it."
        ),
    },
    {
        "slug": "asking_what_to_say_but_not_asking_to_send",
        "name": "asking what to say but not asking to send",
        "guidance": (
            "Messages asking what to say, how to phrase something, or whether a reply sounds "
            "okay without asking the user or agent to send the message."
        ),
    },
    {
        "slug": "message_status_or_reply_discussion",
        "name": "message status or reply discussion",
        "guidance": (
            "Messages discussing replies, texts, emails, whether someone responded, message "
            "tone, or message status without asking the user to send, forward, notify, or reply."
        ),
    },
    {
        "slug": "meeting_information_questions",
        "name": "meeting information questions",
        "guidance": (
            "Messages asking about meeting details, time, location, topic, agenda, or attendees "
            "without asking the user or agent to schedule, book, move, postpone, or coordinate it."
        ),
    },
    {
        "slug": "meeting_attendance_or_confirmation_without_scheduling",
        "name": "meeting attendance or confirmation without scheduling",
        "guidance": (
            "Messages confirming attendance, saying someone can or cannot attend, or acknowledging "
            "a meeting time without asking to schedule or reschedule it."
        ),
    },
    {
        "slug": "multi_topic_normal_chat_with_action_related_words",
        "name": "multi-topic normal chat with action-related words",
        "guidance": (
            "Normal multi-topic messages that mention action-related words such as money, files, "
            "meetings, messages, emergencies, contracts, or agreements without requesting a supported action."
        ),
    },
    {
        "slug": "ambiguous_but_non_action_messages",
        "name": "ambiguous but non-action messages",
        "guidance": (
            "Ambiguous, incomplete, reflective, or context-light messages that are still normal "
            "chat and do not ask the user or agent to perform a supported action."
        ),
    },
]


def build_normal_chat_prompt(subtype: dict, batch_count: int) -> str:
    """Create one focused normal_chat prompt for a subtype batch."""
    return f"""
Generate {batch_count} unique realistic WhatsApp-style messages for an intent classification dataset.

Intent/class: normal_chat

Definition:
A message belongs to this class if it is a normal conversational message and does not ask the user or agent to perform one of the supported actions. It may include casual conversation, questions, opinions, advice requests, emotional expression, work or school discussion, updates, jokes, thanks, apologies, or mentions of money, emergencies, agreements, files, messages, or meetings without actually asking the agent to perform the action.

Supported action classes to avoid:
1. book_or_reschedule_meeting
2. agreement_confirmation_request
3. asking_for_money
4. request_to_send_message_to_someone_else
5. respond_to_emergency_situation
6. request_sending_non_sensitive_file
7. request_sending_sensitive_file

Subtype: {subtype["name"]}
Subtype guidance: {subtype["guidance"]}

Every generated line must be exactly one standalone English-only message. Do not include labels, intent names, subtype names, JSON, or metadata.

Content requirements:
- Generate realistic WhatsApp-style messages.
- Generate English-only messages.
- Use different wording, tone, context, length, directness, and relationship.
- Include formal, casual, emotional, polite, student, work, family, friend, and group-chat tones where appropriate.
- Include short and long messages.
- Make sure every generated message truly belongs to normal_chat.
- The message may mention money, files, meetings, emergencies, agreements, or sending messages, but it must not ask the user or agent to perform the action.

Very important negative rules:
- Do not generate messages asking to send, lend, transfer, pay, refund, donate, or provide money.
- Do not generate messages asking for emergency help, rescue, ambulance, police, fire response, urgent safety action, or crisis response.
- Do not generate messages asking to sign, approve, accept, authorize, consent to, or confirm a binding agreement.
- Do not generate messages asking to send, share, attach, upload, forward, submit, provide, or resend a file.
- Do not generate messages asking to text, message, email, notify, inform, remind, announce, forward, or reply to someone else.
- Do not generate messages asking to schedule, book, arrange, set up, move, postpone, reschedule, rebook, or coordinate a meeting, call, appointment, interview, or session.
- Do not generate Arabic, Turkish, code-switched, or multilingual messages.

Subtype-specific guidance:
- For money hard negatives, mention money, rent, bills, payment, refund, salary, debt, donation, or prices without asking anyone to send or provide money.
- For emergency hard negatives, mention health, stress, accidents, danger, fire, police, hospital, or emergency-related words without an urgent request for help or safety action.
- For agreement hard negatives, mention agreement, contract, approval, confirmation, consent, or terms without asking the user to sign, approve, accept, authorize, or consent.
- For file hard negatives, mention files, PDFs, documents, screenshots, attachments, reports, slides, or forms without asking the user to send, share, upload, forward, attach, submit, provide, or resend them.
- For send-message hard negatives, mention messages, replies, texting, emails, or what to say without asking the user or agent to send, forward, reply, notify, inform, or message someone else.
- For meeting hard negatives, mention meetings, calls, appointments, interviews, or sessions without asking the user or agent to schedule, book, reschedule, move, postpone, rebook, or coordinate them.

Output rules:
- Output plain text only.
- One message per line.
- No numbering.
- No bullets.
- No explanations.
- No quotation marks.
- Avoid duplicates and near-duplicates.
- Every message must be realistic for WhatsApp.
- Generate English-only messages.
""".strip()


def create_client() -> OpenAI:
    """Create an OpenAI-compatible client that sends requests to OpenRouter."""
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"Missing API key. Set the {API_KEY_ENV} environment variable."
        )

    return OpenAI(api_key=api_key, base_url=BASE_URL)


def call_model(client: OpenAI, prompt: str) -> str:
    """Call OpenRouter with retries, forcing routing to the DeepSeek provider only."""
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You generate clean plain-text English training data for "
                            "intent classification. Follow the user's formatting rules exactly."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=MAX_TOKENS_PER_BATCH,
                # OpenRouter-specific body: route only to DeepSeek and disable fallbacks.
                extra_body={
                    "provider": {
                        "only": ["deepseek"],
                        "allow_fallbacks": False,
                    }
                },
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
            print(f"API call failed on attempt {attempt}/{MAX_RETRIES}: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * attempt)

    raise RuntimeError(f"API call failed after {MAX_RETRIES} attempts: {last_error}")


def normalize_for_dedup(message: str) -> str:
    """Normalize a message so repeated lines can be detected reliably."""
    return re.sub(r"\s+", " ", message.strip().lower())


def clean_line(line: str) -> str:
    """Remove common formatting artifacts while preserving natural message text."""
    line = line.strip()
    line = re.sub(r"^\s*(?:[-*\u2022]+|\d+[\).\:-]?)\s*", "", line)
    line = line.replace("\u201c", "").replace("\u201d", "").replace('"', "")
    line = line.replace("\u2018", "'").replace("\u2019", "'")
    line = line.strip().strip("'").strip()
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_assistant_explanation(line: str) -> bool:
    """Filter common assistant preambles that are not dataset examples."""
    normalized = line.strip().lower().rstrip(":")
    explanation_prefixes = (
        "here are",
        "sure, here are",
        "below are",
        "these are",
        "i generated",
        "the messages are",
        "here is",
        "sure",
    )
    return normalized.startswith(explanation_prefixes)


def is_valid_message(message: str) -> bool:
    """Reject obvious non-message lines, supported-action requests, and multilingual examples."""
    if len(message.strip()) < 3:
        return False

    normalized = message.lower()
    non_message_phrases = (
        "step by step",
        "instructions",
        "how to",
        "recipe for",
        "method to",
        "json",
        "label:",
        "intent:",
        "subtype:",
    )
    if any(phrase in normalized for phrase in non_message_phrases):
        return False

    obvious_action_patterns = (
        r"\b(can|could|please|pls)\s+you\s+(send|lend|transfer|pay|refund|donate)\b",
        r"\b(send|lend|transfer|pay|refund|donate)\s+(me|us|him|her|them)\b",
        r"\b(call|send)\s+(an\s+)?ambulance\b",
        r"\bcall\s+(the\s+)?police\b",
        r"\b(sign|approve|accept|authorize|consent\s+to)\s+(the\s+)?(agreement|contract|terms|document)\b",
        r"\b(can|could|please|pls)\s+you\s+(send|share|attach|upload|forward|submit|provide|resend)\s+(the\s+)?(file|pdf|document|screenshot|attachment|report|slides|form)\b",
        r"\b(can|could|please|pls)\s+you\s+(text|message|email|notify|inform|remind|announce|reply\s+to|forward)\b",
        r"\b(can|could|please|pls)\s+you\s+(schedule|book|arrange|set\s+up|move|postpone|reschedule|rebook|coordinate)\b",
        r"\b(schedule|book|arrange|set\s+up|reschedule|rebook)\s+(a\s+)?(meeting|call|appointment|interview|session)\b",
    )
    if any(re.search(pattern, normalized) for pattern in obvious_action_patterns):
        return False

    # Keep the dataset English-only by rejecting Arabic ranges and common Turkish letters.
    if re.search(
        r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\u00e7\u011f\u0131"
        r"\u00f6\u015f\u00fc\u00c7\u011e\u0130\u00d6\u015e\u00dc]",
        message,
    ):
        return False

    return True


def clean_messages(
    raw_text: str,
    seen_messages: set[str],
    max_new_messages: int | None = None,
) -> list[str]:
    """Clean model output and deduplicate against previously accepted messages."""
    cleaned_messages = []

    for raw_line in raw_text.splitlines():
        if is_assistant_explanation(raw_line):
            continue

        message = clean_line(raw_line)
        if not message:
            continue
        if not is_valid_message(message):
            continue

        dedup_key = normalize_for_dedup(message)
        if dedup_key in seen_messages:
            continue

        seen_messages.add(dedup_key)
        cleaned_messages.append(message)

        if max_new_messages is not None and len(cleaned_messages) >= max_new_messages:
            break

    return cleaned_messages


def save_messages(path: Path, messages: list[str]) -> None:
    """Save messages as plain text, one message per line."""
    path.write_text("\n".join(messages) + "\n", encoding="utf-8")


def load_existing_dataset() -> tuple[dict[str, list[str]], list[str], set[str]]:
    """Load saved subtype files so an interrupted run can resume cleanly."""
    existing_by_slug = {}
    all_messages = []
    seen_messages = set()

    for subtype in NORMAL_CHAT_SUBTYPES:
        path = OUTPUT_DIR / f"{subtype['slug']}.txt"
        subtype_messages = []

        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                message = clean_line(line)
                if not message or is_assistant_explanation(message):
                    continue
                if not is_valid_message(message):
                    continue

                dedup_key = normalize_for_dedup(message)
                if dedup_key in seen_messages:
                    continue

                seen_messages.add(dedup_key)
                subtype_messages.append(message)
                all_messages.append(message)

                if len(subtype_messages) >= EXAMPLES_PER_SUBTYPE:
                    break

        existing_by_slug[subtype["slug"]] = subtype_messages

    return existing_by_slug, all_messages, seen_messages


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = create_client()
    existing_by_slug, all_messages, seen_messages = load_existing_dataset()

    for index, subtype in enumerate(NORMAL_CHAT_SUBTYPES, start=1):
        print(f"[{index}/{len(NORMAL_CHAT_SUBTYPES)}] Generating: {subtype['name']}")

        subtype_path = OUTPUT_DIR / f"{subtype['slug']}.txt"
        subtype_messages = existing_by_slug[subtype["slug"]]

        if subtype_messages:
            print(f"Resumed {subtype['slug']} with {len(subtype_messages)} saved messages")

        batch_attempt = 0
        while len(subtype_messages) < EXAMPLES_PER_SUBTYPE:
            batch_attempt += 1
            if batch_attempt > MAX_BATCH_ATTEMPTS_PER_SUBTYPE:
                print(
                    f"Stopped {subtype['slug']} after {MAX_BATCH_ATTEMPTS_PER_SUBTYPE} "
                    f"batch attempts with {len(subtype_messages)} unique messages."
                )
                break

            remaining = EXAMPLES_PER_SUBTYPE - len(subtype_messages)
            batch_count = min(BATCH_SIZE, remaining)
            prompt = build_normal_chat_prompt(subtype, batch_count)
            raw_output = call_model(client, prompt)
            batch_messages = clean_messages(
                raw_output,
                seen_messages,
                max_new_messages=remaining,
            )

            subtype_messages.extend(batch_messages)
            all_messages.extend(batch_messages)

            # Save after every batch so an interrupted run can resume from disk.
            save_messages(subtype_path, subtype_messages)
            save_messages(OUTPUT_DIR / COMBINED_FILENAME, all_messages)

            print(
                f"{subtype['slug']} batch {batch_attempt}: added {len(batch_messages)}, "
                f"collected {len(subtype_messages)}/{EXAMPLES_PER_SUBTYPE}"
            )

    combined_path = OUTPUT_DIR / COMBINED_FILENAME
    save_messages(combined_path, all_messages)

    print(f"Done. Saved {len(all_messages)} total unique messages to {combined_path}")


if __name__ == "__main__":
    main()

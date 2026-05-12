import os
import re
import time
from pathlib import Path

from openai import OpenAI


# Configurable generation settings for the request_to_send_message_to_someone_else class.
EXAMPLES_PER_SUBTYPE = 285
BATCH_SIZE = 50
MAX_TOKENS_PER_BATCH = 4000
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
OUTPUT_DIR = Path("request_to_send_message_to_someone_else_dataset")
COMBINED_FILENAME = "request_to_send_message_to_someone_else_all.txt"

# The OpenAI SDK is used only as an OpenAI-compatible request client.
# Requests are sent to OpenRouter, then OpenRouter routes them to DeepSeek only
# through provider.only in extra_body.
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_ATTEMPTS_PER_SUBTYPE = 35


SEND_MESSAGE_REQUEST_SUBTYPES = [
    {
        "slug": "direct_text_message_sending_requests",
        "name": "direct text message sending requests",
        "guidance": (
            "Direct messages asking the user or agent to send, text, message, or write "
            "something to another person or group."
        ),
    },
    {
        "slug": "forward_a_message_to_someone_else_requests",
        "name": "forward a message to someone else requests",
        "guidance": (
            "Messages asking the user or agent to forward an existing message, note, update, "
            "announcement, or text to another person, group, or channel."
        ),
    },
    {
        "slug": "reply_to_someone_on_my_behalf_requests",
        "name": "reply to someone on my behalf requests",
        "guidance": (
            "Messages asking the user or agent to reply to a person, client, manager, "
            "teacher, group, or organization on the sender's behalf."
        ),
    },
    {
        "slug": "notify_or_inform_someone_requests",
        "name": "notify or inform someone requests",
        "guidance": (
            "Messages asking the user or agent to notify, inform, tell, update, or let "
            "someone know about something."
        ),
    },
    {
        "slug": "reminder_message_to_another_person_requests",
        "name": "reminder message to another person requests",
        "guidance": (
            "Messages asking the user or agent to remind another person, group, team, "
            "client, teacher, family member, or friend about something."
        ),
    },
    {
        "slug": "apology_or_excuse_message_requests",
        "name": "apology or excuse message requests",
        "guidance": (
            "Messages asking the user or agent to send an apology, excuse, explanation, "
            "or polite message to another person."
        ),
    },
    {
        "slug": "work_or_business_message_sending_requests",
        "name": "work or business message sending requests",
        "guidance": (
            "Messages asking the user or agent to send work or business communications "
            "to a manager, teammate, supplier, client, company, HR, or business contact."
        ),
    },
    {
        "slug": "school_or_university_message_sending_requests",
        "name": "school or university message sending requests",
        "guidance": (
            "Messages asking the user or agent to send a message to a professor, teacher, "
            "school office, class group, university department, or student team."
        ),
    },
    {
        "slug": "family_or_friend_message_sending_requests",
        "name": "family or friend message sending requests",
        "guidance": (
            "Messages asking the user or agent to send, text, reply, remind, or pass a "
            "message to family members or friends."
        ),
    },
    {
        "slug": "customer_or_client_message_sending_requests",
        "name": "customer or client message sending requests",
        "guidance": (
            "Messages asking the user or agent to send customer or client updates, replies, "
            "notifications, follow-ups, apologies, or service messages."
        ),
    },
    {
        "slug": "group_chat_announcement_requests",
        "name": "group chat announcement requests",
        "guidance": (
            "Messages asking the user or agent to announce, post, update, or send a message "
            "to a group chat, team channel, class group, or community group."
        ),
    },
    {
        "slug": "email_or_formal_message_sending_requests",
        "name": "email or formal message sending requests",
        "guidance": (
            "Messages asking the user or agent to email, write formally, notify by email, "
            "or send a professional message to another recipient."
        ),
    },
    {
        "slug": "social_media_or_app_message_sending_requests",
        "name": "social media or app message sending requests",
        "guidance": (
            "Messages asking the user or agent to send a DM, app message, Instagram message, "
            "Slack message, Teams message, company chat update, or school portal message."
        ),
    },
    {
        "slug": "indirect_send_message_requests",
        "name": "indirect send-message requests",
        "guidance": (
            "Indirect messages that imply the user or agent should send, tell, notify, "
            "update, remind, or pass information to someone else."
        ),
    },
    {
        "slug": "urgent_send_message_requests",
        "name": "urgent send-message requests",
        "guidance": (
            "Urgent messages asking the user or agent to quickly send, forward, reply, "
            "notify, inform, or update another person or group."
        ),
    },
    {
        "slug": "sensitive_or_risky_message_sending_requests",
        "name": "sensitive or risky message sending requests",
        "guidance": (
            "Messages asking the user or agent to send sensitive, awkward, private, risky, "
            "conflict-related, disciplinary, breakup, complaint, or reputation-impacting text."
        ),
    },
    {
        "slug": "suspicious_or_manipulative_message_sending_requests",
        "name": "suspicious or manipulative message sending requests",
        "guidance": (
            "Pushy, suspicious, manipulative, secretive, or unusual messages asking the user "
            "or agent to send, forward, or reply to someone else."
        ),
    },
    {
        "slug": "message_rewriting_plus_sending_requests",
        "name": "message rewriting plus sending requests",
        "guidance": (
            "Messages asking the user or agent to rewrite, polish, soften, shorten, or fix "
            "a message and then send it to another person or group."
        ),
    },
    {
        "slug": "send_message_without_user_approval_pressure_requests",
        "name": "send message without user approval pressure requests",
        "guidance": (
            "Messages pressuring the user or agent to send a message immediately, without "
            "review, confirmation, checking, or waiting for approval."
        ),
    },
    {
        "slug": "cancel_correct_or_follow_up_message_requests",
        "name": "cancel, correct, or follow-up message requests",
        "guidance": (
            "Messages asking the user or agent to send a cancellation note, correction, "
            "clarification, follow-up, update, or second message to someone else."
        ),
    },
]


def build_send_message_request_prompt(subtype: dict, batch_count: int) -> str:
    """Create one focused send-message request prompt for a subtype batch."""
    return f"""
Generate {batch_count} unique realistic WhatsApp-style messages for an intent classification dataset.

Intent/class: request_to_send_message_to_someone_else

Definition:
A message belongs to this class if the sender asks the user or agent to send, forward, reply, text, email, notify, inform, remind, announce, or pass a message to another person, group, team, client, teacher, manager, family member, friend, organization, or external contact. The requested action is communication on behalf of the user or sender.

Subtype: {subtype["name"]}
Subtype guidance: {subtype["guidance"]}

Every generated line must be exactly one standalone English-only message. Do not include labels, intent names, subtype names, JSON, or metadata.

Content requirements:
- Generate realistic WhatsApp-style messages.
- Generate English-only messages.
- Include only requests where the main action is sending or delivering a message to someone else.
- Use different wording, tone, context, length, directness, urgency, and relationship.
- Include direct and indirect wording depending on the subtype.
- Include formal, casual, polite, professional, emotional, pushy, urgent, hesitant, and suspicious tones where appropriate.
- Include short and long messages.
- Include messages with exact message content and without exact message content.
- Include different communication verbs such as send, text, message, reply, forward, email, notify, inform, tell, remind, announce, pass this to, let them know, write to, and update.
- Include different recipients such as my mom, my dad, my friend, Sarah, Ahmed, the team, the group, HR, the manager, the professor, the client, the customer, the landlord, the school, the company, support, and the supplier.
- Include different channels such as WhatsApp, SMS, email, Slack, Teams, Instagram DM, group chat, company chat, and school portal.
- Make sure every generated message truly belongs to the request_to_send_message_to_someone_else class.
- Do not generate normal chat.
- Do not generate advice-only messages such as "what should I say?" unless the message clearly asks to send it.
- Do not generate messages that only ask whether someone replied or whether a message was received.
- Do not generate messages asking to call someone unless the main request is to send a message.
- Do not generate file-sending requests unless the main intent is only sending a text message.
- Do not generate money requests.
- Do not generate emergency messages.
- Do not generate meeting scheduling requests.
- Do not generate agreement confirmation requests.
- Do not generate requests to confirm, approve, sign, authorize, or accept an agreement.
- Do not generate Arabic, Turkish, code-switched, or multilingual messages.

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
    """Reject obvious non-message lines, wrong-intent lines, and multilingual examples."""
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

    wrong_intent_phrases = (
        "send me the file",
        "share the file with me",
        "upload the file",
        "attach the file",
        "send the document",
        "send me money",
        "transfer money",
        "can you pay",
        "call an ambulance",
        "call the police",
        "book a meeting",
        "schedule a meeting",
        "reschedule the meeting",
        "sign the agreement",
        "approve the agreement",
        "accept the contract",
        "authorize the contract",
    )
    if any(phrase in normalized for phrase in wrong_intent_phrases):
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

    for subtype in SEND_MESSAGE_REQUEST_SUBTYPES:
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

    for index, subtype in enumerate(SEND_MESSAGE_REQUEST_SUBTYPES, start=1):
        print(f"[{index}/{len(SEND_MESSAGE_REQUEST_SUBTYPES)}] Generating: {subtype['name']}")

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
            prompt = build_send_message_request_prompt(subtype, batch_count)
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

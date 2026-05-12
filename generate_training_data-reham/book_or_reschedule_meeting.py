import os
import re
import time
from pathlib import Path

from openai import OpenAI


# Configurable generation settings for the book_or_reschedule_meeting class.
EXAMPLES_PER_SUBTYPE = 285
BATCH_SIZE = 50
MAX_TOKENS_PER_BATCH = 4000
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
OUTPUT_DIR = Path("book_or_reschedule_meeting_dataset")
COMBINED_FILENAME = "book_or_reschedule_meeting_all.txt"

# The OpenAI SDK is used only as an OpenAI-compatible request client.
# Requests are sent to OpenRouter, then OpenRouter routes them to DeepSeek only
# through provider.only in extra_body.
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_ATTEMPTS_PER_SUBTYPE = 35


MEETING_REQUEST_SUBTYPES = [
    {
        "slug": "direct_meeting_booking_requests",
        "name": "direct meeting booking requests",
        "guidance": (
            "Direct messages asking the user or agent to schedule, book, arrange, "
            "or set up a meeting with another person or group."
        ),
    },
    {
        "slug": "casual_meeting_arrangement_requests",
        "name": "casual meeting arrangement requests",
        "guidance": (
            "Informal WhatsApp-style messages asking to arrange, set up, or find "
            "a time for a meeting, call, chat, or session."
        ),
    },
    {
        "slug": "formal_business_meeting_scheduling_requests",
        "name": "formal business meeting scheduling requests",
        "guidance": (
            "Professional or formal messages asking to schedule business meetings, "
            "stakeholder meetings, reviews, planning sessions, or executive discussions."
        ),
    },
    {
        "slug": "work_call_or_online_meeting_scheduling_requests",
        "name": "work call or online meeting scheduling requests",
        "guidance": (
            "Messages asking to schedule online meetings or work calls through Zoom, "
            "Teams, Google Meet, Slack huddles, or other remote meeting tools."
        ),
    },
    {
        "slug": "interview_or_hr_meeting_scheduling_requests",
        "name": "interview or HR meeting scheduling requests",
        "guidance": (
            "Messages asking to schedule interviews, HR calls, recruiter meetings, "
            "onboarding sessions, performance reviews, or hiring-related appointments."
        ),
    },
    {
        "slug": "school_university_or_advisor_meeting_requests",
        "name": "school, university, or advisor meeting requests",
        "guidance": (
            "Messages asking to schedule school or university meetings with professors, "
            "teachers, advisors, classmates, project groups, or office hours."
        ),
    },
    {
        "slug": "client_customer_or_sales_meeting_requests",
        "name": "client, customer, or sales meeting requests",
        "guidance": (
            "Messages asking to schedule client calls, customer check-ins, sales demos, "
            "supplier discussions, account reviews, or prospect meetings."
        ),
    },
    {
        "slug": "doctor_consultation_or_service_appointment_booking_requests",
        "name": "doctor, consultation, or service appointment booking requests",
        "guidance": (
            "Messages asking to book appointments, doctor visits, consultations, service "
            "slots, salon appointments, repair visits, or professional sessions."
        ),
    },
    {
        "slug": "reschedule_existing_meeting_requests",
        "name": "reschedule existing meeting requests",
        "guidance": (
            "Messages asking to reschedule an already planned meeting, call, appointment, "
            "interview, consultation, or session to another time."
        ),
    },
    {
        "slug": "postpone_or_delay_meeting_requests",
        "name": "postpone or delay meeting requests",
        "guidance": (
            "Messages asking to postpone, delay, push back, or shift a meeting, call, "
            "appointment, session, or interview to a later time."
        ),
    },
    {
        "slug": "move_meeting_earlier_requests",
        "name": "move meeting earlier requests",
        "guidance": (
            "Messages asking to move a meeting, appointment, call, or session earlier "
            "than originally planned."
        ),
    },
    {
        "slug": "cancel_and_rebook_meeting_requests",
        "name": "cancel and rebook meeting requests",
        "guidance": (
            "Messages asking to cancel an existing meeting or appointment and rebook, "
            "rearrange, or reschedule it for another time."
        ),
    },
    {
        "slug": "availability_based_scheduling_requests",
        "name": "availability-based scheduling requests",
        "guidance": (
            "Messages asking the user or agent to check availability, find a free slot, "
            "coordinate calendars, or schedule based on when people are free."
        ),
    },
    {
        "slug": "time_proposal_or_time_slot_selection_requests",
        "name": "time proposal or time-slot selection requests",
        "guidance": (
            "Messages asking to propose times, choose a time slot, pick between options, "
            "or schedule around exact or vague time windows."
        ),
    },
    {
        "slug": "urgent_meeting_scheduling_requests",
        "name": "urgent meeting scheduling requests",
        "guidance": (
            "Urgent messages asking to schedule, arrange, move, or rebook a meeting, "
            "call, interview, appointment, or session quickly."
        ),
    },
    {
        "slug": "recurring_meeting_scheduling_requests",
        "name": "recurring meeting scheduling requests",
        "guidance": (
            "Messages asking to schedule recurring weekly, monthly, daily, standup, "
            "sync, review, check-in, or regular meeting series."
        ),
    },
    {
        "slug": "group_meeting_coordination_requests",
        "name": "group meeting coordination requests",
        "guidance": (
            "Messages asking to coordinate a meeting with multiple participants, team "
            "members, class groups, project members, stakeholders, or committees."
        ),
    },
    {
        "slug": "indirect_meeting_scheduling_requests",
        "name": "indirect meeting scheduling requests",
        "guidance": (
            "Indirect messages that imply the user or agent should arrange, set up, "
            "find a time, or coordinate a meeting without always using direct wording."
        ),
    },
    {
        "slug": "meeting_scheduling_with_calendar_tool_action_requests",
        "name": "meeting scheduling with calendar/tool action requests",
        "guidance": (
            "Messages asking the user or agent to create a calendar invite, add a meeting "
            "to the calendar, send an invite, update a calendar event, or use a scheduling tool."
        ),
    },
    {
        "slug": "risky_or_authority_sensitive_meeting_scheduling_requests",
        "name": "risky or authority-sensitive meeting scheduling requests",
        "guidance": (
            "Messages asking to schedule sensitive or high-stakes meetings involving managers, "
            "HR, lawyers, doctors, disciplinary topics, complaints, negotiations, or authority figures."
        ),
    },
]


def build_meeting_request_prompt(subtype: dict, batch_count: int) -> str:
    """Create one focused meeting scheduling prompt for a subtype batch."""
    return f"""
Generate {batch_count} unique realistic WhatsApp-style messages for an intent classification dataset.

Intent/class: book_or_reschedule_meeting

Definition:
A message belongs to this class if the sender asks the user or agent to schedule, book, arrange, set up, plan, move, postpone, reschedule, shift, delay, cancel and rebook, confirm a new time for, or coordinate a meeting, call, appointment, interview, session, consultation, demo, or event involving the user and at least one other person.

The main requested action must be calendar coordination or meeting-time management.

Subtype: {subtype["name"]}
Subtype guidance: {subtype["guidance"]}

Every generated line must be exactly one standalone English-only message. Do not include labels, intent names, subtype names, JSON, or metadata.

Content requirements:
- Generate realistic WhatsApp-style messages.
- Generate English-only messages.
- Include only requests where the main action is booking, arranging, scheduling, rescheduling, moving, postponing, or coordinating a meeting, call, appointment, interview, session, consultation, demo, or event.
- Use different wording, tone, context, length, directness, urgency, and relationship.
- Include direct and indirect wording depending on the subtype.
- Include formal, casual, polite, professional, student, client-facing, urgent, hesitant, and pushy tones where appropriate.
- Include short and long messages.
- Include messages with exact dates/times and without exact dates/times.
- Include messages with vague timing such as tomorrow, next week, later today, after lunch, sometime this week, before Friday, or when everyone is free.
- Include messages with different meeting types such as meeting, call, Zoom call, Teams call, interview, appointment, consultation, advisor meeting, demo, check-in, follow-up, review session, office hours, and planning session.
- Include different participants such as my manager, HR, the client, Sarah, Ahmed, the professor, the advisor, the team, the doctor, the customer, the supplier, the group, and the project members.
- Include different calendar/action verbs such as schedule, book, arrange, set up, move, shift, postpone, delay, reschedule, rebook, find a slot, check availability, add to calendar, create a calendar invite, and send an invite.
- Make sure every generated message truly belongs to the book_or_reschedule_meeting class.
- Do not generate normal chat.
- Do not generate messages that only ask for meeting information without asking to schedule or reschedule.
- Do not generate messages that only ask whether a meeting exists, when a meeting is, or who is attending.
- Do not generate messages that only confirm attendance, confirm receipt, or say yes/no to a meeting.
- Do not generate requests to send a text message to someone else unless the main intent is clearly scheduling or rescheduling a meeting.
- Do not generate file-sending requests.
- Do not generate money requests.
- Do not generate emergency messages.
- Do not generate agreement confirmation requests.
- Do not generate requests to confirm, approve, sign, authorize, or accept an agreement.
- Do not generate messages asking for advice about what to say in a meeting.
- Do not generate messages asking to cancel a meeting only, unless they also ask to rebook or reschedule it.
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
        "sign the agreement",
        "approve the agreement",
        "accept the contract",
        "authorize the contract",
        "what should i say in the meeting",
        "cancel the meeting and nothing else",
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

    for subtype in MEETING_REQUEST_SUBTYPES:
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

    for index, subtype in enumerate(MEETING_REQUEST_SUBTYPES, start=1):
        print(f"[{index}/{len(MEETING_REQUEST_SUBTYPES)}] Generating: {subtype['name']}")

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
            prompt = build_meeting_request_prompt(subtype, batch_count)
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

import os
import re
import time
from pathlib import Path

from openai import OpenAI


# Configurable generation settings for the respond_to_emergency_situation class.
EXAMPLES_PER_SUBTYPE = 300
BATCH_SIZE = 50
MAX_TOKENS_PER_BATCH = 4000
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
OUTPUT_DIR = Path("emergency_response_dataset")
COMBINED_FILENAME = "respond_to_emergency_situation_all.txt"

# The OpenAI SDK is used only as an OpenAI-compatible request client.
# Requests are sent to OpenRouter, then OpenRouter routes them to DeepSeek only
# through provider.only in extra_body.
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_ATTEMPTS_PER_SUBTYPE = 30


EMERGENCY_SUBTYPES = [
    {
        "slug": "direct_emergency_help_requests",
        "name": "direct emergency help requests",
        "guidance": (
            "Direct messages where the sender clearly asks for immediate help, rescue, "
            "police, ambulance, firefighters, or urgent safety action."
        ),
    },
    {
        "slug": "medical_emergency_requests",
        "name": "medical emergency requests",
        "guidance": (
            "Urgent medical situations involving severe symptoms, collapse, breathing "
            "trouble, chest pain, seizures, allergic reactions, unconsciousness, or need "
            "for an ambulance or doctor now."
        ),
    },
    {
        "slug": "accident_or_injury_emergency_requests",
        "name": "accident or injury emergency requests",
        "guidance": (
            "Messages about accidents, crashes, falls, bleeding, broken bones, serious "
            "injuries, workplace injuries, or immediate help after physical harm."
        ),
    },
    {
        "slug": "fire_gas_leak_or_building_danger_requests",
        "name": "fire, gas leak, or building danger requests",
        "guidance": (
            "Urgent messages involving fire, smoke, gas smell, carbon monoxide concern, "
            "electrical danger, building collapse risk, locked exits, or evacuation."
        ),
    },
    {
        "slug": "violence_threat_or_personal_safety_emergency_requests",
        "name": "violence, threat, or personal safety emergency requests",
        "guidance": (
            "Messages involving assault, domestic violence, stalking, threats, break-ins, "
            "being followed, weapons, harassment escalating, or immediate personal danger."
        ),
    },
    {
        "slug": "child_elderly_or_vulnerable_person_emergency_requests",
        "name": "child, elderly, or vulnerable person emergency requests",
        "guidance": (
            "Emergencies involving children, babies, elderly people, disabled people, "
            "confused vulnerable people, missing dependents, or someone unable to get help."
        ),
    },
    {
        "slug": "mental_health_crisis_or_self_harm_emergency_requests",
        "name": "mental health crisis or self-harm emergency requests",
        "guidance": (
            "Crisis messages where someone appears at immediate risk, sends goodbye "
            "messages, is asking for urgent emotional support, requests a welfare check, "
            "or needs immediate help from a trusted person or emergency service. Avoid "
            "graphic details or instructions."
        ),
    },
    {
        "slug": "urgent_location_based_rescue_requests",
        "name": "urgent location-based rescue requests",
        "guidance": (
            "Messages asking someone to come to a specific place, share location with "
            "rescuers, call services to that location, or help because the sender is trapped."
        ),
    },
    {
        "slug": "car_breakdown_or_being_stranded_in_unsafe_place",
        "name": "car breakdown or being stranded in unsafe place",
        "guidance": (
            "Urgent unsafe-stranding messages involving car breakdowns, empty roads, unsafe "
            "areas, late night, no transport, no battery, or danger while stranded."
        ),
    },
    {
        "slug": "lost_person_or_missing_person_emergency_requests",
        "name": "lost person or missing person emergency requests",
        "guidance": (
            "Urgent messages about a person being missing, lost, unreachable in risky "
            "circumstances, separated in a crowd, or not returning when danger is suspected."
        ),
    },
    {
        "slug": "natural_disaster_or_severe_weather_emergency_requests",
        "name": "natural disaster or severe weather emergency requests",
        "guidance": (
            "Emergency messages involving earthquakes, floods, storms, wildfires, landslides, "
            "severe snow, heat danger, evacuation, or being stuck during a disaster."
        ),
    },
    {
        "slug": "emergency_messages_without_the_word_emergency",
        "name": "emergency messages without the word emergency",
        "guidance": (
            'Urgent safety messages that must not use the word "emergency" but still '
            "clearly report or request help for immediate danger, injury, rescue, or crisis."
        ),
    },
    {
        "slug": "indirect_emergency_messages",
        "name": "indirect emergency messages",
        "guidance": (
            "Indirect messages where the sender hints something is seriously wrong, unsafe, "
            "or escalating, while the main intent is still urgent help or safety action."
        ),
    },
    {
        "slug": "short_panic_whatsapp_style_emergency_messages",
        "name": "short panic WhatsApp-style emergency messages",
        "guidance": (
            "Very short panic-style WhatsApp messages, fragments, typos, abbreviations, "
            "and urgent wording that clearly signal immediate danger or need for help."
        ),
    },
    {
        "slug": "long_context_rich_emergency_messages",
        "name": "long context-rich emergency messages",
        "guidance": (
            "Longer messages with realistic context, location details, what happened, who "
            "is affected, what help is needed, and why immediate action is required."
        ),
    },
    {
        "slug": "family_emergency_messages",
        "name": "family emergency messages",
        "guidance": (
            "Urgent messages sent to or about family members such as parents, siblings, "
            "children, spouses, cousins, or relatives needing immediate help."
        ),
    },
    {
        "slug": "friend_emergency_messages",
        "name": "friend emergency messages",
        "guidance": (
            "Urgent informal messages to friends asking for immediate help, pickup, rescue, "
            "calling services, or support during danger or crisis."
        ),
    },
    {
        "slug": "workplace_or_school_emergency_messages",
        "name": "workplace or school emergency messages",
        "guidance": (
            "Emergency messages involving offices, factories, shops, campuses, classrooms, "
            "school buses, labs, workplace incidents, lockdowns, or urgent safety response."
        ),
    },
    {
        "slug": "suspicious_or_ambiguous_urgent_danger_messages",
        "name": "suspicious or ambiguous urgent danger messages",
        "guidance": (
            "Ambiguous but urgent danger messages where the sender may be hiding the problem, "
            "speaking carefully, feeling watched, or hinting that immediate safety help is needed."
        ),
    },
    {
        "slug": "mixed_arabic_english_or_turkish_english_emergency_messages",
        "name": "mixed Arabic-English or Turkish-English emergency messages",
        "guidance": (
            "Informal code-switched WhatsApp-style emergency messages mixing Arabic-English "
            "or Turkish-English, including natural Latin transliteration, panic wording, "
            "and urgent requests for help."
        ),
    },
]


def build_emergency_prompt(subtype: dict, batch_count: int) -> str:
    """Create one focused emergency-data prompt for a subtype batch."""
    return f"""
Generate {batch_count} unique realistic WhatsApp-style messages for an intent classification dataset.

Intent/class: respond_to_emergency_situation

Definition:
A message belongs to this class if the sender is reporting or requesting help for an urgent emergency situation where immediate attention, safety action, medical support, police/fire/ambulance contact, rescue, or crisis response may be needed. The request can be direct or indirect. It may involve danger, injury, illness, violence, accident, fire, being trapped, being followed, missing person, mental health crisis, natural disaster, or another urgent safety-related situation.

Subtype: {subtype["name"]}
Subtype guidance: {subtype["guidance"]}

Every generated line must be exactly one standalone message. Do not include labels, intent names, subtype names, JSON, or metadata.

Content requirements:
- Generate realistic WhatsApp-style messages.
- Use different wording, tone, context, length, directness, urgency, and relationship.
- Include direct and indirect language depending on the subtype.
- Include typos, abbreviations, panic wording, and informal WhatsApp style where appropriate.
- Every message must truly belong to the respond_to_emergency_situation class.
- Do not generate normal chat.
- Do not generate general health advice questions.
- Do not generate ordinary complaints with no urgent danger.
- Do not generate messages asking for money.
- Do not generate messages asking to send a file.
- Do not generate messages asking to schedule a meeting.
- Do not generate messages asking to confirm an agreement.
- Do not generate messages asking to send a message to someone else unless the main intent is clearly an emergency.
- For mental health crisis examples, avoid graphic details or procedural descriptions. Focus on urgent help-seeking, welfare checks, or safety support.

Output rules:
- Output plain text only.
- One message per line.
- No numbering.
- No bullets.
- No explanations.
- No quotation marks.
- Avoid duplicates and near-duplicates.
- Every message must be realistic for WhatsApp.
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
                            "You generate clean plain-text training data for intent "
                            "classification. Follow the user's formatting rules exactly."
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
    """Reject obvious unsafe instructional lines or non-message lines."""
    if len(message.strip()) < 3:
        return False

    unsafe_or_non_message_phrases = (
        "step by step",
        "instructions",
        "how to",
        "recipe for",
        "method to",
    )
    normalized = message.lower()
    return not any(phrase in normalized for phrase in unsafe_or_non_message_phrases)


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

    for subtype in EMERGENCY_SUBTYPES:
        path = OUTPUT_DIR / f"{subtype['slug']}.txt"
        subtype_messages = []

        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                message = clean_line(line)
                if not message or is_assistant_explanation(message):
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

    for index, subtype in enumerate(EMERGENCY_SUBTYPES, start=1):
        print(f"[{index}/{len(EMERGENCY_SUBTYPES)}] Generating: {subtype['name']}")

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
            prompt = build_emergency_prompt(subtype, batch_count)
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

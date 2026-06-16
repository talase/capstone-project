import os
import re
import time
from pathlib import Path

from openai import OpenAI


# Configurable generation settings for the agreement_confirmation_request class.
EXAMPLES_PER_SUBTYPE = 570
BATCH_SIZE = 50
MAX_TOKENS_PER_BATCH = 4000
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
OUTPUT_DIR = Path("agreement_confirmation_dataset")
COMBINED_FILENAME = "agreement_confirmation_request_all.txt"

# The OpenAI SDK is used only as an OpenAI-compatible request client.
# Requests are sent to OpenRouter, then OpenRouter routes them to DeepSeek only
# through provider.only in extra_body.
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_ATTEMPTS_PER_SUBTYPE = 40


AGREEMENT_CONFIRMATION_SUBTYPES = [
    {
        "slug": "contract_signing_requests",
        "name": "contract signing requests",
        "guidance": (
            "Messages asking the user to sign, approve, accept, or confirm a contract "
            "that creates a binding commitment, obligation, or consequence."
        ),
    },
    {
        "slug": "legal_document_approval_requests",
        "name": "legal document approval requests",
        "guidance": (
            "Messages asking for approval, signature, authorization, consent, or agreement "
            "on legal documents, settlement papers, waivers, notices, affidavits, or formal "
            "legal terms."
        ),
    },
    {
        "slug": "financial_agreement_approval_requests",
        "name": "financial agreement approval requests",
        "guidance": (
            "Messages asking the user to accept, approve, authorize, or confirm financial "
            "terms, repayment plans, settlements, payment plans, fees, charges, account "
            "changes, guarantees, or financial responsibilities."
        ),
    },
    {
        "slug": "business_deal_or_partnership_approval_requests",
        "name": "business deal or partnership approval requests",
        "guidance": (
            "Messages asking for approval or confirmation of business deals, partnership "
            "terms, vendor arrangements, client agreements, shareholder terms, proposals, "
            "or commercial commitments."
        ),
    },
    {
        "slug": "employment_or_hr_agreement_requests",
        "name": "employment or HR agreement requests",
        "guidance": (
            "Messages asking the user to accept, confirm, sign, or agree to employment "
            "offers, HR policies, salary terms, non-disclosure agreements, non-compete "
            "terms, disciplinary documents, role changes, or workplace conditions."
        ),
    },
    {
        "slug": "rental_lease_or_property_agreement_requests",
        "name": "rental, lease, or property agreement requests",
        "guidance": (
            "Messages asking for confirmation, signature, acceptance, or authorization of "
            "rental contracts, lease renewals, tenancy terms, deposits, property rules, "
            "maintenance responsibility, move-out terms, or ownership-related documents."
        ),
    },
    {
        "slug": "consent_or_permission_approval_requests",
        "name": "consent or permission approval requests",
        "guidance": (
            "Messages asking the user to give consent, permission, authorization, or approval "
            "for something with personal, professional, legal, privacy, medical, parental, "
            "or operational consequences."
        ),
    },
    {
        "slug": "responsibility_or_liability_acceptance_requests",
        "name": "responsibility or liability acceptance requests",
        "guidance": (
            "Messages asking the user to accept responsibility, liability, risk, damages, "
            "waivers, penalties, obligations, accountability, or consequences for an action "
            "or arrangement."
        ),
    },
    {
        "slug": "purchase_subscription_or_service_terms_acceptance_requests",
        "name": "purchase, subscription, or service terms acceptance requests",
        "guidance": (
            "Messages asking the user to accept purchase terms, subscription terms, service "
            "contracts, renewal conditions, cancellation policies, usage rules, upgrade "
            "terms, or paid service commitments."
        ),
    },
    {
        "slug": "urgent_or_suspicious_pressure_to_agree_requests",
        "name": "urgent or suspicious pressure-to-agree requests",
        "guidance": (
            "Urgent, pushy, suspicious, or high-pressure messages asking the user to sign, "
            "approve, authorize, accept, consent, or confirm a binding arrangement quickly."
        ),
    },
]


def build_agreement_confirmation_prompt(subtype: dict, batch_count: int) -> str:
    """Create one focused agreement-confirmation prompt for a subtype batch."""
    return f"""
Generate {batch_count} unique realistic WhatsApp-style messages for an intent classification dataset.

Intent/class: agreement_confirmation_request

Definition:
A message belongs to this class if the sender asks the user to sign, confirm, approve, accept, authorize, agree to, or give consent to an agreement, contract, legal document, business deal, financial arrangement, responsibility, liability, permission, employment condition, rental/lease document, purchase terms, subscription terms, or another binding arrangement.

The message must imply responsibility, permission, commitment, approval, legal effect, financial effect, professional effect, or personal consequence.

Subtype: {subtype["name"]}
Subtype guidance: {subtype["guidance"]}

Every generated line must be exactly one standalone English-only message. Do not include labels, intent names, subtype names, JSON, or metadata.

Content requirements:
- Generate realistic WhatsApp-style messages.
- Generate English-only messages.
- Use different wording, tone, context, length, directness, urgency, and relationship.
- Include direct and indirect language depending on the subtype.
- Include formal, casual, polite, professional, pushy, hesitant, and suspicious tones where appropriate.
- Include short and long messages.
- Include messages with and without document names.
- Include messages with and without consequences mentioned.
- Include messages using words like sign, approve, accept, confirm, agree, authorize, consent, permission, contract, deal, policy, terms, responsibility, liability, commitment, subscription, purchase, rent, lease, partnership, settlement, document, offer, and agreement.
- Make sure every generated message truly belongs to the agreement_confirmation_request class.
- Only generate messages where confirming, approving, signing, accepting, authorizing, or agreeing could create responsibility, permission, commitment, legal effect, financial effect, professional effect, or personal consequence.
- Do not generate normal chat.
- Do not generate harmless confirmations.
- Do not generate meeting scheduling requests unless the main intent is approving a binding commitment.
- Do not generate money requests unless the main intent is approving or confirming a financial agreement.
- Do not generate emergency messages.
- Do not generate file-sending requests.
- Do not generate requests to send a message to someone else.
- Do not generate Arabic, Turkish, code-switched, or multilingual messages.
- Avoid harmless or low-risk confirmations such as confirming a meeting time, receipt of a message, attendance, name, appointment, delivery time, opinion, address, or phone number.

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
    """Reject obvious non-message lines and multilingual examples."""
    if len(message.strip()) < 3:
        return False

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
    normalized = message.lower()
    if any(phrase in normalized for phrase in non_message_phrases):
        return False

    # Keep the dataset English-only by rejecting common Arabic/Turkish characters.
    if re.search(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ffçğıöşüÇĞİÖŞÜ]", message):
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

    for subtype in AGREEMENT_CONFIRMATION_SUBTYPES:
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

    for index, subtype in enumerate(AGREEMENT_CONFIRMATION_SUBTYPES, start=1):
        print(f"[{index}/{len(AGREEMENT_CONFIRMATION_SUBTYPES)}] Generating: {subtype['name']}")

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
            prompt = build_agreement_confirmation_prompt(subtype, batch_count)
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

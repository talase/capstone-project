import os
import re
import time
from pathlib import Path

from openai import OpenAI


# Configurable generation settings.
EXAMPLES_PER_SUBTYPE = 300
BATCH_SIZE = 50
MAX_TOKENS_PER_BATCH = 4000
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
OUTPUT_DIR = Path("money_request_dataset")
COMBINED_FILENAME = "asking_for_money_all.txt"

# The OpenAI SDK is used only as an OpenAI-compatible request client.
# Requests are sent to OpenRouter, then OpenRouter routes them to DeepSeek.
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_ATTEMPTS_PER_SUBTYPE = 30


SUBTYPES = [
    {
        "slug": "direct_casual_money_requests",
        "name": "direct casual money requests",
        "guidance": (
            "Casual, everyday messages where the sender directly asks someone "
            "for money, help paying, or a quick transfer."
        ),
    },
    {
        "slug": "direct_formal_payment_requests",
        "name": "direct formal payment requests",
        "guidance": (
            "Formal or professional messages that directly request payment, "
            "settlement, remittance, or completion of an outstanding amount."
        ),
    },
    {
        "slug": "indirect_financial_help_requests",
        "name": "indirect financial help requests",
        "guidance": (
            "Messages that imply the sender needs financial help without always "
            "asking bluntly, while still clearly requesting support or coverage."
        ),
    },
    {
        "slug": "urgent_money_requests",
        "name": "urgent money requests",
        "guidance": (
            "Time-sensitive messages involving emergencies, deadlines, bills, "
            "transport, rent, medical needs, or being stuck somewhere."
        ),
    },
    {
        "slug": "family_money_requests",
        "name": "family money requests",
        "guidance": (
            "Messages sent to family members such as parents, siblings, cousins, "
            "spouses, or relatives asking for money or cost coverage."
        ),
    },
    {
        "slug": "friend_loan_requests",
        "name": "friend loan requests",
        "guidance": (
            "Informal messages to friends asking to borrow money temporarily, "
            "with or without a promised repayment time."
        ),
    },
    {
        "slug": "business_invoice_or_payment_requests",
        "name": "business invoice or payment requests",
        "guidance": (
            "Business, vendor, freelancer, client, invoice, deposit, service fee, "
            "or overdue payment messages."
        ),
    },
    {
        "slug": "refund_debt_or_payback_requests",
        "name": "refund, debt, or payback requests",
        "guidance": (
            "Messages asking someone to return money, repay a debt, refund a "
            "charge, pay back a split bill, or settle what they owe."
        ),
    },
    {
        "slug": "donation_or_charity_contribution_requests",
        "name": "donation or charity contribution requests",
        "guidance": (
            "Messages requesting donations, charity contributions, fundraiser "
            "support, community aid, or help for a cause."
        ),
    },
    {
        "slug": "suspicious_or_scam_like_money_requests",
        "name": "suspicious or scam-like money requests",
        "guidance": (
            "Suspicious or scam-like messages that still read like realistic chat "
            "messages asking for money, fees, codes, wallet top-ups, or urgent transfers."
        ),
    },
    {
        "slug": "money_requests_with_exact_amounts",
        "name": "money requests with exact amounts",
        "guidance": (
            "Messages that include exact requested amounts using varied currencies, "
            "formats, and amounts, such as 50 USD, $120, 750 TL, AED 200, or 30 euros."
        ),
    },
    {
        "slug": "money_requests_without_exact_amounts",
        "name": "money requests without exact amounts",
        "guidance": (
            "Messages that ask for financial help or coverage without naming a "
            "specific amount."
        ),
    },
    {
        "slug": "money_requests_with_payment_method",
        "name": "money requests that mention a payment method such as IBAN, bank transfer, card, PayPal, cash, or wallet",
        "guidance": (
            "Messages that mention payment methods such as IBAN, bank transfer, "
            "card, PayPal, cash, mobile wallet, crypto wallet, Venmo, Wise, or Revolut."
        ),
    },
    {
        "slug": "indirect_requests_without_money_words",
        "name": 'indirect requests where the words "money", "cash", "pay", "transfer", and "loan" are not used',
        "guidance": (
            'Indirect requests where the output must not include the words "money", '
            '"cash", "pay", "transfer", or "loan", while still clearly asking someone '
            "to cover a cost, help with a bill, send support, or handle an expense."
        ),
    },
    {
        "slug": "short_whatsapp_style_asking_for_money_messages",
        "name": "short WhatsApp-style asking-for-money messages",
        "guidance": (
            "Very short WhatsApp-style messages, usually one sentence or fragment, "
            "where the sender asks for money or cost coverage."
        ),
    },
    {
        "slug": "long_context_rich_asking_for_money_messages",
        "name": "long context-rich asking-for-money messages",
        "guidance": (
            "Longer messages with realistic context, explanation, relationship cues, "
            "reasoning, repayment promises, deadlines, or details."
        ),
    },
    {
        "slug": "emotional_or_embarrassed_asking_for_money_messages",
        "name": "emotional or embarrassed asking-for-money messages",
        "guidance": (
            "Messages where the sender feels ashamed, stressed, emotional, hesitant, "
            "or embarrassed while asking for financial help."
        ),
    },
    {
        "slug": "rude_or_demanding_asking_for_money_messages",
        "name": "rude or demanding asking-for-money messages",
        "guidance": (
            "Rude, impatient, pushy, demanding, or annoyed messages requesting money, "
            "payment, or repayment."
        ),
    },
    {
        "slug": "polite_hesitant_asking_for_money_messages",
        "name": "polite hesitant asking-for-money messages",
        "guidance": (
            "Polite, careful, apologetic, or hesitant requests for financial help, "
            "payment, repayment, or temporary support."
        ),
    },
    {
        "slug": "mixed_arabic_english_or_turkish_english_informal_asking_for_money_messages",
        "name": "mixed Arabic-English or Turkish-English informal asking-for-money messages",
        "guidance": (
            "Informal code-switched WhatsApp-style messages mixing Arabic-English "
            "or Turkish-English, including Latin transliteration when natural."
        ),
    },
]


def build_prompt(subtype: dict, batch_count: int) -> str:
    """Create a focused prompt for one subtype."""
    return f"""
Generate {batch_count} unique realistic WhatsApp-style messages for an intent classification dataset.

Intent/class: asking_for_money
Subtype: {subtype["name"]}
Subtype guidance: {subtype["guidance"]}

Every generated line must be exactly one standalone message from a sender asking for money, payment, transfer, financial help, refund, debt repayment, donation, or someone to cover a cost.

Rules:
- Output plain text only.
- One message per line.
- No numbering.
- No bullets.
- No explanations.
- No quotation marks.
- Avoid duplicates and near-duplicates.
- Vary wording, tone, context, length, directness, currencies, relationships, and situations.
- Every message must truly belong to the asking_for_money class.
- Do not generate normal financial discussion, budgeting advice, account updates, or messages that only mention money without requesting financial help, payment, repayment, donation, refund, or cost coverage.
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
    """Call the model with basic retry handling."""
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
    """Remove common formatting artifacts while preserving the message text."""
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
    )
    return normalized.startswith(explanation_prefixes)


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

    for subtype in SUBTYPES:
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

    for index, subtype in enumerate(SUBTYPES, start=1):
        print(f"[{index}/{len(SUBTYPES)}] Generating: {subtype['name']}")

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
            prompt = build_prompt(subtype, batch_count)
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

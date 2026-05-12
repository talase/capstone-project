import os
import re
import time
from pathlib import Path

from openai import OpenAI


# Configurable generation settings for the request_sending_sensitive_file class.
EXAMPLES_PER_SUBTYPE = 285
BATCH_SIZE = 50
MAX_TOKENS_PER_BATCH = 4000
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
OUTPUT_DIR = Path("request_sending_sensitive_file_dataset")
COMBINED_FILENAME = "request_sending_sensitive_file_all.txt"

# The OpenAI SDK is used only as an OpenAI-compatible request client.
# Requests are sent to OpenRouter, then OpenRouter routes them to DeepSeek only
# through provider.only in extra_body.
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_ATTEMPTS_PER_SUBTYPE = 35


SENSITIVE_FILE_REQUEST_SUBTYPES = [
    {
        "slug": "identity_document_file_requests",
        "name": "identity document file requests",
        "guidance": (
            "Messages asking for identity documents such as ID cards, national ID copies, "
            "driver license scans, residency cards, or identity verification attachments."
        ),
    },
    {
        "slug": "passport_visa_or_travel_document_file_requests",
        "name": "passport, visa, or travel document file requests",
        "guidance": (
            "Messages asking for passport scans, visa documents, travel permits, residence "
            "permits, boarding-related documents, embassy files, or immigration attachments."
        ),
    },
    {
        "slug": "medical_record_lab_result_or_prescription_file_requests",
        "name": "medical record, lab result, or prescription file requests",
        "guidance": (
            "Messages asking for medical records, lab results, prescriptions, doctor reports, "
            "hospital documents, vaccination records, test results, or health attachments."
        ),
    },
    {
        "slug": "bank_statement_salary_slip_or_financial_document_requests",
        "name": "bank statement, salary slip, or financial document requests",
        "guidance": (
            "Messages asking for bank statements, salary slips, payslips, account documents, "
            "income proof, loan files, financial records, or personal finance attachments."
        ),
    },
    {
        "slug": "invoice_receipt_tax_or_payment_proof_file_requests",
        "name": "invoice, receipt, tax, or payment proof file requests",
        "guidance": (
            "Messages asking for invoices, receipts, tax forms, payment proofs, transaction "
            "receipts, VAT files, billing documents, or financially sensitive attachments."
        ),
    },
    {
        "slug": "contract_signed_agreement_or_legal_document_requests",
        "name": "contract, signed agreement, or legal document requests",
        "guidance": (
            "Messages asking for signed contracts, legal agreements, NDAs, settlement files, "
            "court documents, authorization letters, power of attorney files, or legal attachments."
        ),
    },
    {
        "slug": "confidential_work_or_internal_business_file_requests",
        "name": "confidential work or internal business file requests",
        "guidance": (
            "Messages asking for confidential work files, internal reports, private decks, "
            "strategy documents, internal business files, source documents, or restricted folders."
        ),
    },
    {
        "slug": "customer_employee_or_personal_data_file_requests",
        "name": "customer, employee, or personal data file requests",
        "guidance": (
            "Messages asking for customer lists, employee sheets, personal data exports, "
            "contact databases, HR lists, private records, or files containing identifiable data."
        ),
    },
    {
        "slug": "academic_transcript_diploma_or_official_certificate_requests",
        "name": "academic transcript, diploma, or official certificate requests",
        "guidance": (
            "Messages asking for academic transcripts, diplomas, certificates, enrollment "
            "letters, grade reports, official university files, or verified education documents."
        ),
    },
    {
        "slug": "private_photo_scan_or_personal_document_requests",
        "name": "private photo, scan, or personal document requests",
        "guidance": (
            "Messages asking for private scans, personal documents, private photos, family "
            "documents, personal records, confidential images, or sensitive attachment copies."
        ),
    },
    {
        "slug": "password_credential_access_key_or_security_file_requests",
        "name": "password, credential, access key, or security file requests",
        "guidance": (
            "Messages asking for password files, login credentials, access keys, API keys, "
            "security certificates, recovery codes, SSH keys, or credential attachments."
        ),
    },
    {
        "slug": "hr_employment_or_payroll_document_requests",
        "name": "HR, employment, or payroll document requests",
        "guidance": (
            "Messages asking for HR documents, employment records, offer letters, payroll "
            "files, performance documents, disciplinary records, tax withholding forms, or staff files."
        ),
    },
    {
        "slug": "insurance_claim_or_government_form_requests",
        "name": "insurance, claim, or government form requests",
        "guidance": (
            "Messages asking for insurance forms, claim files, government forms, benefits "
            "documents, policy papers, official applications, or regulated personal documents."
        ),
    },
    {
        "slug": "urgent_sensitive_file_sending_requests",
        "name": "urgent sensitive file sending requests",
        "guidance": (
            "Urgent messages asking for sensitive files to be sent, shared, attached, uploaded, "
            "forwarded, submitted, provided, or resent quickly."
        ),
    },
    {
        "slug": "suspicious_or_pressure_based_sensitive_file_requests",
        "name": "suspicious or pressure-based sensitive file requests",
        "guidance": (
            "Pushy, suspicious, high-pressure, or unusual messages asking the user to send, "
            "upload, forward, or provide sensitive files or private attachments."
        ),
    },
    {
        "slug": "resend_missing_or_failed_sensitive_attachment_requests",
        "name": "resend missing or failed sensitive attachment requests",
        "guidance": (
            "Messages asking someone to resend a sensitive attachment because it is missing, "
            "failed, corrupted, expired, inaccessible, or did not upload correctly."
        ),
    },
    {
        "slug": "forward_sensitive_file_to_someone_else_requests",
        "name": "forward sensitive file to someone else requests",
        "guidance": (
            "Messages asking the user to forward or share a sensitive file with another person, "
            "group, client, lawyer, HR, bank, embassy, hospital, insurer, or external party."
        ),
    },
    {
        "slug": "upload_sensitive_file_to_portal_form_or_external_website_requests",
        "name": "upload sensitive file to portal, form, or external website requests",
        "guidance": (
            "Messages asking the user to upload, attach, submit, or provide a sensitive file "
            "through a portal, external website, application form, shared drive, or email."
        ),
    },
    {
        "slug": "send_sensitive_file_in_a_specific_format_requests",
        "name": "send sensitive file in a specific format requests",
        "guidance": (
            "Messages asking for a sensitive file in a specific format such as PDF, JPG, PNG, "
            "DOCX, XLSX, CSV, ZIP, scanned copy, clear photo, certified copy, or original file."
        ),
    },
    {
        "slug": "indirect_sensitive_file_requests",
        "name": "indirect sensitive file requests",
        "guidance": (
            "Indirect messages that imply the sender needs the user to send, share, attach, "
            "upload, forward, submit, provide, or resend a sensitive file or private attachment."
        ),
    },
]


def build_sensitive_file_request_prompt(subtype: dict, batch_count: int) -> str:
    """Create one focused sensitive file-request prompt for a subtype batch."""
    return f"""
Generate {batch_count} unique realistic WhatsApp-style messages for an intent classification dataset.

Intent/class: request_sending_sensitive_file

Definition:
A message belongs to this class if the sender asks the user or agent to send, share, attach, upload, forward, submit, resend, or provide a sensitive file or digital attachment. Sensitive files include identity documents, passports, visas, medical records, lab results, prescriptions, bank statements, salary slips, payment proofs, tax documents, invoices, receipts, signed contracts, legal agreements, confidential work files, customer data, employee data, private personal documents, credentials, access keys, insurance forms, HR documents, payroll files, academic transcripts, diplomas, certificates, or any file that may create privacy, legal, financial, professional, or security risk if shared incorrectly.

Subtype: {subtype["name"]}
Subtype guidance: {subtype["guidance"]}

Every generated line must be exactly one standalone English-only message. Do not include labels, intent names, subtype names, JSON, or metadata.

Content requirements:
- Generate realistic WhatsApp-style messages.
- Generate English-only messages.
- Include only sensitive file-sending requests.
- Use different wording, tone, context, length, directness, urgency, and relationship.
- Include direct and indirect wording depending on the subtype.
- Include formal, casual, polite, professional, pushy, suspicious, urgent, and hesitant tones where appropriate.
- Include short and long messages.
- Include messages with specific file names and without specific file names.
- Include different sensitive file types such as passport scan, ID copy, visa document, medical report, lab result, prescription, bank statement, salary slip, payslip, tax form, invoice, receipt, payment proof, signed contract, legal agreement, NDA, customer list, employee sheet, payroll file, transcript, diploma, certificate, private scan, credential file, access key file, insurance claim, and government form.
- Include different destinations such as me, the group, the client, HR, the lawyer, the bank, the embassy, the hospital, the insurance company, the portal, the application website, the email, the shared drive, and the external form.
- Make sure every generated message truly belongs to the request_sending_sensitive_file class.
- Do not generate normal chat.
- Do not generate messages that only ask whether a sensitive file exists without asking to send, share, upload, forward, attach, submit, provide, or resend it.
- Do not generate non-sensitive file requests such as lecture slides, ordinary class notes, public brochures, public posters, general presentations, ordinary event photos, non-sensitive templates, public reports, general guides, sample code, toy datasets, non-sensitive schedules, or ordinary planning documents.
- Do not generate money requests unless the main intent is sending a financial document file.
- Do not generate emergency messages.
- Do not generate meeting scheduling requests.
- Do not generate agreement confirmation requests unless the main intent is sending the agreement file.
- Do not generate requests to send a text message to someone else unless the main intent is clearly sending or forwarding a sensitive file.
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
    """Reject obvious non-message lines, non-sensitive requests, and multilingual examples."""
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

    non_sensitive_file_phrases = (
        "lecture slides",
        "class notes",
        "study material",
        "public brochure",
        "public poster",
        "general presentation",
        "event photo",
        "non-sensitive template",
        "public report",
        "general guide",
        "sample code",
        "toy dataset",
        "non-sensitive schedule",
        "ordinary planning document",
    )
    if any(phrase in normalized for phrase in non_sensitive_file_phrases):
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

    for subtype in SENSITIVE_FILE_REQUEST_SUBTYPES:
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

    for index, subtype in enumerate(SENSITIVE_FILE_REQUEST_SUBTYPES, start=1):
        print(f"[{index}/{len(SENSITIVE_FILE_REQUEST_SUBTYPES)}] Generating: {subtype['name']}")

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
            prompt = build_sensitive_file_request_prompt(subtype, batch_count)
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

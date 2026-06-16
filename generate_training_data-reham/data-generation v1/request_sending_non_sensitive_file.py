import os
import re
import time
from pathlib import Path

from openai import OpenAI


# Configurable generation settings for the request_sending_non_sensitive_file class.
EXAMPLES_PER_SUBTYPE = 250
BATCH_SIZE = 50
MAX_TOKENS_PER_BATCH = 4000
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v4-flash")
OUTPUT_DIR = Path("request_sending_non_sensitive_file_dataset")
COMBINED_FILENAME = "request_sending_non_sensitive_file_all.txt"

# The OpenAI SDK is used only as an OpenAI-compatible request client.
# Requests are sent to OpenRouter, then OpenRouter routes them to DeepSeek only
# through provider.only in extra_body.
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY_ENV = "OPENROUTER_API_KEY"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_ATTEMPTS_PER_SUBTYPE = 30


NON_SENSITIVE_FILE_REQUEST_SUBTYPES = [
    {
        "slug": "lecture_slides_or_study_material_file_requests",
        "name": "lecture slides or study material file requests",
        "guidance": (
            "Messages asking for lecture slides, class notes, study packs, reading "
            "materials, handouts, revision PDFs, or learning files."
        ),
    },
    {
        "slug": "assignment_homework_or_project_file_requests",
        "name": "assignment, homework, or project file requests",
        "guidance": (
            "Messages asking for assignment files, homework documents, project drafts, "
            "group project folders, sample submissions, or ordinary coursework attachments."
        ),
    },
    {
        "slug": "public_report_or_general_document_requests",
        "name": "public report or general document requests",
        "guidance": (
            "Messages asking for public reports, general documents, summaries, public "
            "briefs, non-confidential work documents, or ordinary reference files."
        ),
    },
    {
        "slug": "presentation_or_slide_deck_requests",
        "name": "presentation or slide deck requests",
        "guidance": (
            "Messages asking for presentations, slide decks, PPT/PPTX files, speaking "
            "slides, workshop decks, or demo presentation files."
        ),
    },
    {
        "slug": "spreadsheet_template_or_table_file_requests",
        "name": "spreadsheet, template, or table file requests",
        "guidance": (
            "Messages asking for spreadsheets, Excel files, XLSX sheets, CSV tables, "
            "tracking templates, planning tables, or non-sensitive data tables."
        ),
    },
    {
        "slug": "image_screenshot_or_event_photo_requests",
        "name": "image, screenshot, or event photo requests",
        "guidance": (
            "Messages asking for ordinary images, screenshots, event photos, class photos, "
            "poster images, product mockups, or visual references that are not private."
        ),
    },
    {
        "slug": "video_or_audio_file_requests",
        "name": "video or audio file requests",
        "guidance": (
            "Messages asking for video files, audio recordings, clips, webinar recordings, "
            "podcast files, voice notes, or public media attachments."
        ),
    },
    {
        "slug": "brochure_flyer_poster_or_public_material_requests",
        "name": "brochure, flyer, poster, or public material requests",
        "guidance": (
            "Messages asking for brochures, flyers, posters, public event materials, "
            "marketing one-pagers, public PDFs, banners, or printable materials."
        ),
    },
    {
        "slug": "design_logo_or_creative_asset_file_requests",
        "name": "design, logo, or creative asset file requests",
        "guidance": (
            "Messages asking for design files, logos, mockups, editable assets, icons, "
            "brand samples, images, creative drafts, or media assets that are non-sensitive."
        ),
    },
    {
        "slug": "meeting_notes_agenda_or_minutes_file_requests",
        "name": "meeting notes, agenda, or minutes file requests",
        "guidance": (
            "Messages asking for non-confidential meeting notes, agendas, minutes, action "
            "lists, recap documents, or shared team notes."
        ),
    },
    {
        "slug": "tutorial_guide_manual_or_instruction_file_requests",
        "name": "tutorial, guide, manual, or instruction file requests",
        "guidance": (
            "Messages asking for tutorials, guides, manuals, how-to PDFs, instruction "
            "documents, setup guides, learning resources, or general reference files."
        ),
    },
    {
        "slug": "code_notebook_or_programming_file_requests",
        "name": "code, notebook, or programming file requests",
        "guidance": (
            "Messages asking for code files, notebooks, scripts, sample projects, GitHub "
            "exports, programming examples, config templates, or non-sensitive source files."
        ),
    },
    {
        "slug": "dataset_sample_data_or_csv_file_requests",
        "name": "dataset, sample data, or CSV file requests",
        "guidance": (
            "Messages asking for public datasets, sample data, CSV examples, demo tables, "
            "toy datasets, synthetic data, or non-sensitive data files."
        ),
    },
    {
        "slug": "form_blank_template_or_application_template_requests",
        "name": "form, blank template, or application template requests",
        "guidance": (
            "Messages asking for blank forms, application templates, editable templates, "
            "sample forms, empty documents, or non-sensitive template files."
        ),
    },
    {
        "slug": "calendar_schedule_timetable_or_plan_file_requests",
        "name": "calendar, schedule, timetable, or plan file requests",
        "guidance": (
            "Messages asking for calendars, schedules, timetables, project plans, class "
            "plans, event schedules, roadmap files, or planning documents."
        ),
    },
    {
        "slug": "checklist_rubric_outline_or_planning_document_requests",
        "name": "checklist, rubric, outline, or planning document requests",
        "guidance": (
            "Messages asking for checklists, rubrics, outlines, planning documents, review "
            "sheets, scoring guides, task lists, or ordinary workflow files."
        ),
    },
    {
        "slug": "resend_missing_or_failed_non_sensitive_attachment_requests",
        "name": "resend missing or failed non-sensitive attachment requests",
        "guidance": (
            "Messages asking someone to resend a non-sensitive attachment because it is "
            "missing, failed, expired, corrupted, inaccessible, or did not upload correctly."
        ),
    },
    {
        "slug": "forward_a_non_sensitive_file_to_a_person_or_group_requests",
        "name": "forward a non-sensitive file to a person or group requests",
        "guidance": (
            "Messages asking the user to forward or share a non-sensitive file with a "
            "person, group chat, professor, class group, client, teammate, or team."
        ),
    },
    {
        "slug": "upload_a_non_sensitive_file_to_a_platform_portal_or_form_requests",
        "name": "upload a non-sensitive file to a platform, portal, or form requests",
        "guidance": (
            "Messages asking the user to upload, attach, or submit a non-sensitive file "
            "to a portal, LMS, form, shared drive, Google Drive, Slack, Teams, or folder."
        ),
    },
    {
        "slug": "send_a_non_sensitive_file_in_a_specific_format_requests",
        "name": "send a non-sensitive file in a specific format requests",
        "guidance": (
            "Messages asking for a non-sensitive file in a specific format such as PDF, "
            "DOCX, PPTX, XLSX, CSV, TXT, ZIP, PNG, JPG, MP4, MP3, notebook, or code file."
        ),
    },
    {
        "slug": "urgent_non_sensitive_file_sending_requests",
        "name": "urgent non-sensitive file sending requests",
        "guidance": (
            "Urgent messages asking for a non-sensitive file to be sent, shared, attached, "
            "uploaded, forwarded, provided, submitted, or resent quickly."
        ),
    },
    {
        "slug": "indirect_non_sensitive_file_sending_requests",
        "name": "indirect non-sensitive file sending requests",
        "guidance": (
            "Indirect messages that imply the sender needs the user to send, share, attach, "
            "upload, forward, provide, submit, or resend a non-sensitive file."
        ),
    },
    {
        "slug": "folder_zip_or_archive_sharing_requests_for_non_sensitive_files",
        "name": "folder, ZIP, or archive sharing requests for non-sensitive files",
        "guidance": (
            "Messages asking for folders, ZIP files, archives, shared drives, project "
            "folders, resource bundles, or compressed packages of non-sensitive files."
        ),
    },
]


def build_non_sensitive_file_request_prompt(subtype: dict, batch_count: int) -> str:
    """Create one focused non-sensitive file-request prompt for a subtype batch."""
    return f"""
Generate {batch_count} unique realistic WhatsApp-style messages for an intent classification dataset.

Intent/class: request_sending_non_sensitive_file

Definition:
A message belongs to this class if the sender asks the user or agent to send, share, attach, upload, forward, resend, submit, or provide a non-sensitive file or digital attachment. Non-sensitive files include public, academic, general work, creative, media, template, event, learning, or ordinary documents that do not obviously contain private identity data, medical data, financial data, legal commitments, confidential business data, passwords, personal records, or highly private information.

Subtype: {subtype["name"]}
Subtype guidance: {subtype["guidance"]}

Every generated line must be exactly one standalone English-only message. Do not include labels, intent names, subtype names, JSON, or metadata.

Content requirements:
- Generate realistic WhatsApp-style messages.
- Generate English-only messages.
- Use different wording, tone, context, length, directness, urgency, and relationship.
- Include direct and indirect wording depending on the subtype.
- Include formal, casual, polite, professional, student, coworker, teammate, and group-chat tones where appropriate.
- Include short and long messages.
- Include messages with specific file names and without specific file names.
- Include different non-sensitive file types such as PDF, DOCX, PPT, PPTX, Excel, XLSX, CSV, TXT, ZIP, image, screenshot, video, audio, notebook, code file, template, brochure, poster, timetable, checklist, rubric, guide, and report.
- Include different destinations such as me, the group, the team, the professor, the class group, the client, the shared drive, Google Drive, email, LMS, portal, form, Slack, Teams, and project folder.
- Make sure every generated message truly belongs to the request_sending_non_sensitive_file class.
- Do not generate normal chat.
- Do not generate messages that only ask whether a file exists without asking to send, share, upload, forward, attach, submit, provide, or resend it.
- Do not generate sensitive file requests.
- Do not generate requests for passport scans, national ID copies, driver license copies, bank statements, salary slips, person-linked payment proof, medical reports, lab results, prescriptions, signed contracts, legal agreements, tax documents, customer data, employee data, passwords, login credentials, private personal documents, or confidential company documents.
- Do not generate money requests.
- Do not generate emergency messages.
- Do not generate meeting scheduling requests.
- Do not generate agreement confirmation requests.
- Do not generate requests to send a text message to someone else unless the main intent is clearly sending or forwarding a non-sensitive file.
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
    """Reject obvious non-message lines, sensitive requests, and multilingual examples."""
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

    sensitive_file_phrases = (
        "passport",
        "national id",
        "identity card",
        "driver license",
        "driving license",
        "bank statement",
        "salary slip",
        "payslip",
        "payment proof",
        "medical report",
        "lab result",
        "prescription",
        "signed contract",
        "legal agreement",
        "tax document",
        "customer data",
        "employee data",
        "password",
        "login credential",
        "private personal document",
        "confidential company document",
    )
    if any(phrase in normalized for phrase in sensitive_file_phrases):
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

    for subtype in NON_SENSITIVE_FILE_REQUEST_SUBTYPES:
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

    for index, subtype in enumerate(NON_SENSITIVE_FILE_REQUEST_SUBTYPES, start=1):
        print(f"[{index}/{len(NON_SENSITIVE_FILE_REQUEST_SUBTYPES)}] Generating: {subtype['name']}")

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
            prompt = build_non_sensitive_file_request_prompt(subtype, batch_count)
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

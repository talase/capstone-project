"""File download and preview extraction helpers for File RAG."""

from __future__ import annotations

from dataclasses import dataclass

try:
    import fitz
except (ImportError, ModuleNotFoundError):  # pragma: no cover - handled at runtime
    fitz = None

from app.services.supabase_storage_client import (
    get_storage_bucket_name,
    get_supabase_service_client,
)


PDF_PAGE_LIMIT = 6
TXT_PREVIEW_LIMIT = 12_000


class FileDownloadError(RuntimeError):
    """Raised when a file cannot be downloaded from Supabase Storage."""


class PdfExtractionError(RuntimeError):
    """Raised when PDF text extraction fails."""


class FileStatusUpdateError(RuntimeError):
    """Raised when optional files table update fails."""


@dataclass
class FileRagResult:
    file_id: str
    content_preview: str
    page_count_used: int
    skipped: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, str | int | bool | None]:
        return {
            "file_id": self.file_id,
            "content_preview": self.content_preview,
            "page_count_used": self.page_count_used,
            "skipped": self.skipped,
            "reason": self.reason,
        }


def process_file_for_rag(
    *,
    file_id: str,
    storage_path: str,
    file_type: str,
    is_sensitive: bool,
    update_files_table: bool = False,
) -> FileRagResult:
    """Download one file from Supabase Storage and return extractable preview text."""

    if is_sensitive:
        result = FileRagResult(
            file_id=file_id,
            content_preview="",
            page_count_used=0,
            skipped=True,
            reason="File is marked sensitive, so it was not processed for RAG.",
        )
        _update_files_table_if_requested(result, update_files_table)
        return result

    normalized_type = _normalize_file_type(file_type, storage_path)
    if normalized_type not in {"pdf", "txt"}:
        result = FileRagResult(
            file_id=file_id,
            content_preview="",
            page_count_used=0,
            skipped=True,
            reason=f"Unsupported file type: {file_type}",
        )
        _update_files_table_if_requested(result, update_files_table)
        return result

    file_bytes = download_file_from_storage(storage_path)

    if normalized_type == "pdf":
        try:
            content_preview, page_count_used = extract_pdf_text_preview(file_bytes)
        except PdfExtractionError as exc:
            result = FileRagResult(
                file_id=file_id,
                content_preview="",
                page_count_used=0,
                skipped=True,
                reason=str(exc),
            )
            _update_files_table_if_requested(result, update_files_table)
            return result
    else:
        content_preview = extract_txt_preview(file_bytes)
        page_count_used = 0

    if not content_preview.strip():
        result = FileRagResult(
            file_id=file_id,
            content_preview="",
            page_count_used=page_count_used,
            skipped=True,
            reason="No text could be extracted from the file.",
        )
        _update_files_table_if_requested(result, update_files_table)
        return result

    result = FileRagResult(
        file_id=file_id,
        content_preview=content_preview,
        page_count_used=page_count_used,
        skipped=False,
    )
    _update_files_table_if_requested(result, update_files_table)
    return result


def download_file_from_storage(storage_path: str) -> bytes:
    """Download raw file bytes from the configured Supabase Storage bucket."""

    bucket_name = get_storage_bucket_name()
    client = get_supabase_service_client()

    try:
        downloaded = client.storage.from_(bucket_name).download(storage_path)
    except Exception as exc:  # noqa: BLE001 - Supabase raises different SDK errors
        raise FileDownloadError(
            f"Could not download '{storage_path}' from bucket '{bucket_name}': {exc}"
        ) from exc

    if isinstance(downloaded, bytes):
        return downloaded
    if isinstance(downloaded, bytearray):
        return bytes(downloaded)
    if isinstance(downloaded, str):
        return downloaded.encode("utf-8")

    raise FileDownloadError(
        f"Supabase returned an unexpected download type: {type(downloaded).__name__}"
    )


def extract_pdf_text_preview(file_bytes: bytes) -> tuple[str, int]:
    """Extract text from the first six PDF pages, or fewer if the PDF is shorter."""

    if fitz is None:
        raise PdfExtractionError("PyMuPDF is not installed. Run: pip install PyMuPDF")

    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            page_count_used = min(document.page_count, PDF_PAGE_LIMIT)
            page_text = [
                document.load_page(page_index).get_text("text")
                for page_index in range(page_count_used)
            ]
    except Exception as exc:  # noqa: BLE001 - PyMuPDF can raise several error types
        raise PdfExtractionError(f"PDF extraction failed: {exc}") from exc

    return "\n\n".join(page_text).strip(), page_count_used


def extract_txt_preview(file_bytes: bytes) -> str:
    """Read a bounded text preview from a TXT file."""

    text = file_bytes.decode("utf-8", errors="replace")
    return text[:TXT_PREVIEW_LIMIT].strip()


def update_files_table_after_processing(result: FileRagResult) -> None:
    """Optionally store the extraction result on a Supabase files table."""

    client = get_supabase_service_client()
    status_value = "skipped" if result.skipped else "processed"

    update_payload = {
        "extracted_preview": result.content_preview,
        "page_count_used": result.page_count_used,
        "status": status_value,
    }

    try:
        client.table("files").update(update_payload).eq("id", result.file_id).execute()
    except Exception as exc:  # noqa: BLE001 - Supabase raises different SDK errors
        raise FileStatusUpdateError(
            f"File was processed, but updating the files table failed: {exc}"
        ) from exc


def _update_files_table_if_requested(
    result: FileRagResult,
    update_files_table: bool,
) -> None:
    if update_files_table:
        update_files_table_after_processing(result)


def _normalize_file_type(file_type: str, storage_path: str) -> str:
    clean_type = file_type.lower().strip()
    clean_path = storage_path.lower().strip()

    if clean_type in {"pdf", ".pdf", "application/pdf"} or clean_path.endswith(".pdf"):
        return "pdf"
    if clean_type in {"txt", ".txt", "text/plain"} or clean_path.endswith(".txt"):
        return "txt"
    return clean_type

"""FastAPI routes for File RAG preprocessing."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel

from app.config import load_env_file
from app.services.file_rag_service import (
    FileDownloadError,
    FileStatusUpdateError,
    process_file_for_rag,
)
from app.services.supabase_storage_client import (
    SupabaseStorageConfigError,
    get_storage_bucket_name,
    get_supabase_service_client,
)


router = APIRouter(prefix="/files", tags=["files"])


class FileRagProcessRequest(BaseModel):
    file_id: str
    storage_path: str
    file_type: str
    is_sensitive: bool
    update_files_table: bool = False


class FileRagProcessResponse(BaseModel):
    file_id: str
    content_preview: str
    page_count_used: int
    skipped: bool
    reason: str | None = None


TEST_N8N_FILE_PAYLOAD = {
    "file_name": "test.pdf",
    "file_type": "pdf",
    "storage_path": "uploads/test.pdf",
    "is_sensitive": False,
    "original_source": "dashboard",
    "status": "uploaded",
}


CONTENT_TYPES_BY_EXTENSION = {
    "csv": "text/csv",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "pdf": "application/pdf",
    "png": "image/png",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "webp": "image/webp",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _safe_filename(filename: str) -> str:
    original_name = Path(filename).name.strip()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name)
    safe_name = safe_name.strip("._")
    return safe_name or "uploaded_file"


def _detect_file_type(filename: str, content_type: str | None) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension:
        return extension
    if content_type == "application/pdf":
        return "pdf"
    if content_type == "text/plain":
        return "txt"
    return content_type or "unknown"


def _content_type_for_download(
    *,
    storage_path: str,
    file_name: str | None,
    file_type: str | None,
) -> str:
    candidates = [
        (file_type or "").strip().lower(),
        Path(file_name or "").suffix.lower().lstrip("."),
        Path(storage_path).suffix.lower().lstrip("."),
    ]

    for candidate in candidates:
        if not candidate:
            continue
        if "/" in candidate and candidate != "application/octet-stream":
            return candidate
        if candidate.startswith("."):
            candidate = candidate[1:]
        content_type = CONTENT_TYPES_BY_EXTENSION.get(candidate)
        if content_type:
            return content_type

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Unsupported or missing file type. Provide file_type or use a storage_path "
            "with a supported extension."
        ),
    )


def _download_storage_file_bytes(storage_path: str) -> bytes:
    if not storage_path.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="storage_path query parameter is required.",
        )

    try:
        client = get_supabase_service_client()
        bucket_name = get_storage_bucket_name()
        downloaded = client.storage.from_(bucket_name).download(storage_path)
    except SupabaseStorageConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK may raise different errors
        error_text = str(exc).lower()
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in error_text or "404" in error_text
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=status_code,
            detail=f"Supabase download failed for '{storage_path}': {exc}",
        ) from exc

    if isinstance(downloaded, bytes):
        return downloaded
    if isinstance(downloaded, bytearray):
        return bytes(downloaded)
    if isinstance(downloaded, str):
        return downloaded.encode("utf-8")

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Supabase returned an unexpected download type: {type(downloaded).__name__}",
    )


def _build_content_disposition(file_name: str) -> str:
    safe_name = _safe_filename(file_name)
    encoded_name = quote(safe_name)
    return f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"


def _extract_signed_url(signed_response: object) -> str | None:
    if isinstance(signed_response, str):
        return _make_signed_url_absolute(signed_response)
    if not isinstance(signed_response, dict):
        return None

    for key in ("signedURL", "signedUrl", "signed_url"):
        value = signed_response.get(key)
        if isinstance(value, str):
            return _make_signed_url_absolute(value)

    data = signed_response.get("data")
    if isinstance(data, dict):
        for key in ("signedURL", "signedUrl", "signed_url"):
            value = data.get(key)
            if isinstance(value, str):
                return _make_signed_url_absolute(value)

    return None


def _make_signed_url_absolute(signed_url: str) -> str:
    if signed_url.startswith("http://") or signed_url.startswith("https://"):
        return signed_url

    load_env_file()
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if supabase_url and signed_url.startswith("/"):
        return f"{supabase_url}{signed_url}"
    return signed_url


def _get_n8n_file_rag_webhook_url() -> str:
    load_env_file()
    webhook_url = os.getenv("N8N_FILE_RAG_WEBHOOK_URL")
    if not webhook_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="N8N_FILE_RAG_WEBHOOK_URL is not set in the backend environment.",
        )
    return webhook_url


def _send_file_payload_to_n8n(payload: dict[str, object]) -> requests.Response:
    webhook_url = _get_n8n_file_rag_webhook_url()

    try:
        response = requests.post(webhook_url, json=payload, timeout=20)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to call n8n webhook: {exc}",
        ) from exc

    if not response.ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "n8n webhook returned an error: "
                f"{response.status_code} {response.text}"
            ),
        )

    return response


@router.post("/process-rag", response_model=FileRagProcessResponse)
def process_rag_file(payload: FileRagProcessRequest) -> dict[str, str | int | bool | None]:
    """Prepare a Supabase Storage file for n8n embedding/vector-store nodes."""

    try:
        result = process_file_for_rag(
            file_id=payload.file_id,
            storage_path=payload.storage_path,
            file_type=payload.file_type,
            is_sensitive=payload.is_sensitive,
            update_files_table=payload.update_files_table,
        )
    except SupabaseStorageConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except FileDownloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except FileStatusUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return result.to_dict()


@router.post("/upload-dashboard")
async def upload_dashboard_file(
    file: UploadFile | None = File(default=None),
    is_sensitive: bool = Form(default=False),
) -> dict[str, str | bool]:
    """Upload a dashboard file to Supabase Storage and trigger n8n ingestion."""

    if file is None or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file must be uploaded using multipart/form-data.",
        )

    webhook_url = _get_n8n_file_rag_webhook_url()
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    file_name = _safe_filename(file.filename)
    file_type = _detect_file_type(file_name, file.content_type)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    storage_path = f"dashboard_uploads/{timestamp}_{file_name}"

    try:
        client = get_supabase_service_client()
        bucket_name = get_storage_bucket_name()
        client.storage.from_(bucket_name).upload(
            storage_path,
            file_bytes,
            file_options={
                "content-type": file.content_type or "application/octet-stream",
            },
        )
    except SupabaseStorageConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK may raise different errors
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase upload failed: {exc}",
        ) from exc

    n8n_payload = {
        "file_name": file_name,
        "file_type": file_type,
        "storage_path": storage_path,
        "is_sensitive": is_sensitive,
        "original_source": "dashboard",
        "status": "uploaded",
    }

    try:
        response = requests.post(webhook_url, json=n8n_payload, timeout=20)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"File uploaded, but calling the n8n webhook failed: {exc}",
        ) from exc

    if not response.ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "File uploaded, but n8n webhook returned an error: "
                f"{response.status_code} {response.text}"
            ),
        )

    return {
        "success": True,
        "file_name": file_name,
        "storage_path": storage_path,
        "message": "File uploaded and sent for processing",
    }


@router.get("/download-for-whatsapp")
def download_file_for_whatsapp(
    storage_path: str = Query(default=""),
    file_name: str | None = Query(default=None),
    file_type: str | None = Query(default=None),
) -> Response:
    """Download a Supabase Storage file as binary data for n8n/WhatsApp."""

    clean_storage_path = storage_path.strip()
    if not clean_storage_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="storage_path query parameter is required.",
        )

    download_name = file_name.strip() if file_name else Path(clean_storage_path).name
    if not download_name:
        download_name = "downloaded_file"

    content_type = _content_type_for_download(
        storage_path=clean_storage_path,
        file_name=download_name,
        file_type=file_type,
    )
    file_bytes = _download_storage_file_bytes(clean_storage_path)

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": _build_content_disposition(download_name),
        },
    )


@router.get("/signed-url")
def create_signed_file_url(
    storage_path: str = Query(default=""),
    expires_in: int = Query(default=300, ge=1, le=3600),
) -> dict[str, str | int]:
    """Create a temporary signed URL for a Supabase Storage file."""

    clean_storage_path = storage_path.strip()
    if not clean_storage_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="storage_path query parameter is required.",
        )

    try:
        client = get_supabase_service_client()
        bucket_name = get_storage_bucket_name()
        signed_response = client.storage.from_(bucket_name).create_signed_url(
            clean_storage_path,
            expires_in,
        )
    except SupabaseStorageConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Supabase SDK may raise different errors
        error_text = str(exc).lower()
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in error_text or "404" in error_text
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=status_code,
            detail=f"Could not create signed URL for '{clean_storage_path}': {exc}",
        ) from exc

    signed_url = _extract_signed_url(signed_response)
    if not signed_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase did not return a signed URL.",
        )

    return {
        "storage_path": clean_storage_path,
        "signed_url": signed_url,
        "expires_in": expires_in,
    }


@router.post("/test-trigger-n8n")
def test_trigger_n8n_file_rag() -> dict[str, object]:
    """Send a fixed test file-upload payload to the n8n File RAG webhook."""

    response = _send_file_payload_to_n8n(TEST_N8N_FILE_PAYLOAD)

    try:
        response_body: object = response.json()
    except ValueError:
        response_body = response.text

    return {
        "message": "Test payload sent to n8n File RAG webhook.",
        "n8n_status_code": response.status_code,
        "n8n_response": response_body,
        "payload_sent": TEST_N8N_FILE_PAYLOAD,
    }

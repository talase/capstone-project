"""FastAPI routes for File RAG preprocessing."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.file_rag_service import (
    FileDownloadError,
    FileStatusUpdateError,
    process_file_for_rag,
)
from app.services.supabase_storage_client import SupabaseStorageConfigError


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

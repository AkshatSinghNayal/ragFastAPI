"""Document endpoints."""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import AsyncSessionLocal, get_db
from app.documents.ingestion import run_ingestion
from app.documents.service import (
    create_document_record,
    delete_document,
    get_document_for_user,
    list_documents_for_user,
)
from app.models.models import User
from app.schemas.documents import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentOut,
    DocumentUploadResponse,
)
from app.utils.errors import APIError

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB


@router.get("/debug/ingestion-error", tags=["system"])
async def get_ingestion_error():
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "last_ingestion_error.txt")
    if os.path.exists(path):
        with open(path, "r") as f:
            return {"error": f.read()}
    return {"error": "No recorded ingestion error"}


async def _ingest_in_background(document_id: uuid.UUID, pdf_bytes: bytes) -> None:
    """Background task: open a fresh DB session and run ingestion.

    We can't reuse the request-scoped session — it closes when the response
    is returned, before the background task fires.
    """
    from sqlalchemy import select

    from app.models.models import Document

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            return
        await run_ingestion(db, document, pdf_bytes)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a PDF and trigger background ingestion."""
    if file.content_type != "application/pdf":
        raise APIError(400, "Only PDF files are accepted", "INVALID_FILE_TYPE")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise APIError(400, "Empty file", "EMPTY_FILE")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise APIError(413, "File too large (max 25 MB)", "FILE_TOO_LARGE")

    filename = file.filename or "untitled.pdf"
    document = await create_document_record(db, user, filename)

    # Hand the bytes to the background task — never write to disk.
    background_tasks.add_task(_ingest_in_background, document.id, pdf_bytes)

    return DocumentUploadResponse(document=DocumentOut.model_validate(document))


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List all documents belonging to the current user."""
    docs = await list_documents_for_user(db, user)
    return DocumentListResponse(
        documents=[DocumentOut.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    """Fetch a single document's metadata + status."""
    document = await get_document_for_user(db, document_id, user)
    return DocumentOut.model_validate(document)


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def remove_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDeleteResponse:
    """Delete a document, its chat history, and its Qdrant vectors."""
    document = await get_document_for_user(db, document_id, user)
    await delete_document(db, document)
    return DocumentDeleteResponse(document_id=document_id)

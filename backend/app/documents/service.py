"""Document business logic: create, list, get, delete."""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Document, User
from app.utils.errors import APIError, DuplicateDocumentError, ForbiddenError
from app.vector.qdrant_client import delete_document_vectors

logger = logging.getLogger(__name__)


async def create_document_record(
    db: AsyncSession,
    user: User,
    filename: str,
) -> Document:
    """Insert a new document row with status='processing'.

    Raises:
        DuplicateDocumentError: same filename already exists for this user
    """
    existing = await db.execute(
        select(Document).where(
            Document.user_id == user.id,
            Document.filename == filename,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateDocumentError()

    doc = Document(
        user_id=user.id,
        filename=filename,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents_for_user(
    db: AsyncSession,
    user: User,
) -> List[Document]:
    """Return all documents for the given user, newest first."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document_for_user(
    db: AsyncSession,
    document_id: uuid.UUID,
    user: User,
) -> Document:
    """Fetch a document and verify ownership (403 if not owner)."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None or document.user_id != user.id:
        raise ForbiddenError()
    return document


async def delete_document(
    db: AsyncSession,
    document: Document,
) -> None:
    """Delete a document, its chat history (via FK cascade), and Qdrant vectors."""
    # 1. Delete Qdrant vectors first (filtered by document_id + user_id).
    try:
        await delete_document_vectors(document.id, document.user_id)
    except Exception:
        logger.exception("Failed to delete Qdrant vectors for document %s", document.id)
        # Continue — we still want to drop the SQL rows.

    # 2. Delete the SQL row. Cascades handle chat_messages.
    await db.delete(document)
    await db.commit()

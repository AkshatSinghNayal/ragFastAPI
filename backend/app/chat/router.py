"""Chat endpoints: /chat (POST) and /chat/{document_id} (GET)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.chat.service import answer_question, fetch_history
from app.database import get_db
from app.documents.service import get_document_for_user
from app.models.models import User
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Ask a question about a document and receive a grounded answer."""
    document = await get_document_for_user(db, payload.document_id, user)
    answer, source_pages = await answer_question(db, document, user, payload.question)
    return ChatResponse(
        answer=answer,
        source_pages=source_pages,
        document_id=document.id,
    )


@router.get("/{document_id}", response_model=ChatHistoryResponse)
async def get_history(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """Fetch full chat history for a document."""
    document = await get_document_for_user(db, document_id, user)
    messages = await fetch_history(db, document, user)
    return ChatHistoryResponse(
        document_id=document.id,
        messages=[ChatMessageOut.model_validate(m) for m in messages],
    )

"""RAG pipeline: embed question → search Qdrant → build Gemini prompt → answer."""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.documents.ingestion import embed_query
from app.models.models import ChatMessage, Document, User
from app.utils.errors import (
    DocumentNotReadyError,
    LLMUnavailableError,
)
from app.vector.qdrant_client import search_similar_chunks

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer ONLY using the provided context. "
    "If the answer is not in the context, say you don't know. "
    "Never fabricate information. When the context is sufficient, cite the "
    "page numbers in square brackets, e.g. [Page 3]."
)


def _format_context(chunks: List[dict]) -> str:
    """Render retrieved chunks as a context block."""
    if not chunks:
        return "(no relevant context retrieved)"
    lines = []
    for c in chunks:
        page = c.get("page_number", "?")
        text = c.get("chunk_text", "").strip()
        lines.append(f"[Page {page}]: {text}")
    return "\n\n".join(lines)


async def _fetch_recent_history(
    db: AsyncSession,
    document_id,
    user_id,
    limit: int,
) -> List[ChatMessage]:
    """Fetch the most recent N messages for a document, oldest-first."""
    result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.document_id == document_id,
            ChatMessage.user_id == user_id,
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    msgs = list(result.scalars().all())
    msgs.reverse()  # chronological order for the prompt
    return msgs


def _format_history(messages: List[ChatMessage]) -> str:
    if not messages:
        return "(none)"
    lines = []
    for m in messages:
        speaker = "User" if m.role == "user" else "Assistant"
        lines.append(f"{speaker}: {m.content}")
    return "\n".join(lines)


def _build_prompt(context: str, history: str, question: str) -> str:
    return (
        f"System: {SYSTEM_PROMPT}\n\n"
        f"Context:\n{context}\n\n"
        f"Chat History:\n{history}\n\n"
        f"Question: {question}"
    )


def _call_gemini_sync(prompt: str) -> str:
    """Synchronous Gemini call — runs in a worker thread via anyio."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    response = model.generate_content(prompt)
    try:
        text = response.text
    except ValueError:
        # Likely a safety block — fall back to a safe answer.
        text = "I'm unable to provide an answer based on the available context."
    return text.strip()


async def _call_gemini(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini with exponential backoff on 429s (non-blocking)."""
    if not settings.GEMINI_API_KEY:
        raise LLMUnavailableError()

    import anyio

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            text = await anyio.to_thread.run_sync(_call_gemini_sync, prompt)
            return text
        except Exception as exc:  # google.api_core.exceptions.ResourceExhausted, etc.
            last_exc = exc
            if attempt < max_retries - 1:
                sleep_s = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "Gemini call failed (attempt %d/%d): %s — retrying in %ds",
                    attempt + 1, max_retries, exc, sleep_s,
                )
                await anyio.sleep(sleep_s)
            else:
                break
    logger.exception("Gemini call failed after %d attempts: %s", max_retries, last_exc)
    raise LLMUnavailableError()


async def answer_question(
    db: AsyncSession,
    document: Document,
    user: User,
    question: str,
) -> Tuple[str, List[int]]:
    """Run the full RAG pipeline for a single user question.

    Returns:
        (answer_text, source_pages)

    Raises:
        DocumentNotReadyError: document still processing or failed
        LLMUnavailableError: Gemini exhausted retries
    """
    if document.status != "ready":
        raise DocumentNotReadyError(document.status)

    # 1. Embed the user question.
    query_vector = await embed_query(question)

    # 2. Semantic search restricted to this (document_id, user_id).
    chunks = await search_similar_chunks(
        query_vector=query_vector,
        document_id=document.id,
        user_id=user.id,
        top_k=settings.RAG_TOP_K,
    )

    # 3. If nothing relevant — return a graceful no-context answer.
    if not chunks:
        no_context_answer = (
            "I couldn't find relevant information in this document."
        )
        # Persist both turns so history reflects the attempt.
        db.add_all([
            ChatMessage(
                document_id=document.id,
                user_id=user.id,
                role="user",
                content=question,
            ),
            ChatMessage(
                document_id=document.id,
                user_id=user.id,
                role="assistant",
                content=no_context_answer,
                source_pages=[],
            ),
        ])
        await db.commit()
        return no_context_answer, []

    # 4. Fetch recent history for multi-turn context.
    history = await _fetch_recent_history(
        db,
        document.id,
        user.id,
        limit=settings.RAG_HISTORY_MESSAGES,
    )

    # 5. Build & send the prompt.
    prompt = _build_prompt(
        context=_format_context(chunks),
        history=_format_history(history),
        question=question,
    )
    answer = await _call_gemini(prompt)

    # 6. Extract unique page numbers (sorted) from retrieved chunks.
    source_pages = sorted({c["page_number"] for c in chunks if c.get("page_number")})

    # 7. Persist both turns.
    db.add_all([
        ChatMessage(
            document_id=document.id,
            user_id=user.id,
            role="user",
            content=question,
        ),
        ChatMessage(
            document_id=document.id,
            user_id=user.id,
            role="assistant",
            content=answer,
            source_pages=source_pages,
        ),
    ])
    await db.commit()

    return answer, source_pages


async def fetch_history(
    db: AsyncSession,
    document: Document,
    user: User,
) -> List[ChatMessage]:
    """Return all chat messages for a document, oldest-first."""
    result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.document_id == document.id,
            ChatMessage.user_id == user.id,
        )
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())

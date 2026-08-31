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
    "You are a helpful assistant for document Q&A. "
    "Answer ONLY using the provided document context. "
    "If the user's question is NOT related to the document (or if the answer is not in the document context), "
    "explicitly reply: 'This question is not related to the uploaded document.' "
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


def _call_gemini_sync(prompt: str, model_name: str) -> str:
    """Synchronous Gemini call for a specific model name — runs in a worker thread."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    try:
        text = response.text
    except ValueError:
        # Likely a safety block — fall back to a safe answer.
        text = "I'm unable to provide an answer based on the available context."
    return text.strip()


async def _call_gemini(prompt: str, max_retries: int = 1) -> str:
    """Call Gemini with instant fallback across available models and strict per-model timeout."""
    if not settings.GEMINI_API_KEY:
        raise LLMUnavailableError()

    import anyio
    import asyncio

    candidate_models = [
        settings.GEMINI_MODEL,
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-flash-latest",
    ]
    seen = set()
    models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

    last_exc: Optional[Exception] = None

    for model_name in models_to_try:
        try:
            text = await asyncio.wait_for(
                anyio.to_thread.run_sync(_call_gemini_sync, prompt, model_name),
                timeout=8.0,
            )
            if text:
                return text
        except Exception as exc:
            last_exc = exc
            logger.warning("Gemini call with model %s failed/timed out: %s — trying fallback", model_name, exc)

    logger.exception("All Gemini model fallbacks failed. Last error: %s", last_exc)
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

    import asyncio

    # 1. Safely embed query with fallback
    query_vector = []
    try:
        query_vector = await asyncio.wait_for(embed_query(question), timeout=4.0)
    except Exception as exc:
        logger.warning("Query embedding failed/timed out (%s) — using DB chunk fallback", exc)

    # 2. Try vector search if query_vector exists
    chunks = []
    if query_vector:
        try:
            chunks = await asyncio.wait_for(
                search_similar_chunks(
                    query_vector=query_vector,
                    document_id=document.id,
                    user_id=user.id,
                    top_k=settings.RAG_TOP_K,
                ),
                timeout=3.0,
            )
        except Exception as exc:
            logger.warning("Vector search failed/timed out (%s) — using DB chunk fallback", exc)

    # 3. Persistent DB fallback lookup if chunks empty
    if not chunks:
        from app.models.models import DocumentChunk
        db_res = await db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.user_id == user.id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(settings.RAG_TOP_K)
        )
        db_chunks_list = db_res.scalars().all()
        if db_chunks_list:
            chunks = [
                {
                    "chunk_text": c.chunk_text,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                    "score": 1.0,
                }
                for c in db_chunks_list
            ]

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

    # 6. Extract unique page numbers (sorted) from retrieved chunks ONLY if answer is relevant.
    unrelated_phrases = [
        "not related to the",
        "unrelated to the",
        "not in the document",
        "not mentioned in the",
        "i don't know",
        "i do not know",
        "cannot find",
        "unable to find",
    ]
    if any(phrase in answer.lower() for phrase in unrelated_phrases):
        source_pages = []
    else:
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

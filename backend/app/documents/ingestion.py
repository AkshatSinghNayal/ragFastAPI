"""PDF ingestion pipeline: extract → chunk → embed → upsert.

Per spec Section 7 INGESTION PIPELINE:
- PyMuPDF (fitz) page-by-page text extraction
- Skip blank pages silently
- If ALL pages blank → status='failed'
- Recursive character splitting, ~500 tokens per chunk, 50 token overlap
- text-embedding-004 (768 dim) for each chunk
- Upsert to Qdrant with { document_id, user_id, chunk_text, page_number, chunk_index }
- Update PostgreSQL with status='ready', total_pages, total_chunks
- Never write raw PDF to disk
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Tuple

import fitz  # PyMuPDF
import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.models import Document
from app.vector.qdrant_client import upsert_chunks

logger = logging.getLogger(__name__)

# Roughly: 1 token ≈ 4 chars of English text. Use a conservative ratio for
# recursive splitting since we don't pull in a tokenizer dependency.
_CHARS_PER_TOKEN = 4


def _extract_pages(pdf_bytes: bytes) -> List[Tuple[int, str]]:
    """Extract non-empty page text from a PDF.

    Returns:
        List of (page_number, text) tuples for pages with non-empty text.
        page_number is 1-indexed.
    """
    pages: List[Tuple[int, str]] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            text = text.strip()
            if text:
                pages.append((i, text))
    return pages


def _split_text_recursive(
    text: str,
    max_chars: int,
    overlap_chars: int,
) -> List[str]:
    """Recursive character text splitter.

    Tries to split on paragraph boundaries, then sentences, then words, then
    characters — never cutting mid-sentence when avoidable.
    """
    if len(text) <= max_chars:
        return [text] if text else []

    separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]
    return _recursive_split(text, separators, max_chars, overlap_chars)


def _recursive_split(
    text: str,
    separators: List[str],
    max_chars: int,
    overlap_chars: int,
) -> List[str]:
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sep = separators[0] if separators else ""
    rest_seps = separators[1:] if len(separators) > 1 else [""]

    if sep == "":
        # Fall back to hard character split.
        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - overlap_chars if overlap_chars < (end - start) else end
        return chunks

    # Split on current separator, then recursively split any piece still too long.
    pieces = text.split(sep)
    merged: List[str] = []
    buffer = ""

    for piece in pieces:
        candidate = (buffer + sep + piece) if buffer else piece
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        if buffer:
            merged.append(buffer)
            buffer = ""
        if len(piece) > max_chars:
            merged.extend(_recursive_split(piece, rest_seps, max_chars, overlap_chars))
        else:
            buffer = piece

    if buffer:
        merged.append(buffer)

    # Add overlap between adjacent merged chunks.
    if overlap_chars <= 0 or len(merged) <= 1:
        return merged

    out: List[str] = [merged[0]]
    for prev, curr in zip(merged, merged[1:]):
        tail = prev[-overlap_chars:] if len(prev) >= overlap_chars else prev
        out.append(tail + curr)
    return out


def chunk_pages(
    pages: List[Tuple[int, str]],
    max_tokens: int = settings.CHUNK_MAX_TOKENS,
    overlap_tokens: int = settings.CHUNK_OVERLAP_TOKENS,
) -> List[Dict[str, Any]]:
    """Split pages into chunk dicts.

    Returns:
        [{chunk_text, page_number, chunk_index}, ...]
    """
    max_chars = max_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    chunks: List[Dict[str, Any]] = []
    idx = 0
    for page_number, text in pages:
        for piece in _split_text_recursive(text, max_chars, overlap_chars):
            if not piece.strip():
                continue
            chunks.append(
                {
                    "chunk_text": piece,
                    "page_number": page_number,
                    "chunk_index": idx,
                }
            )
            idx += 1
    return chunks


def _init_gemini() -> None:
    """Configure the google-generativeai SDK once."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    genai.configure(api_key=settings.GEMINI_API_KEY)


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate text-embedding-004 vectors for a batch of texts.

    google-generativeai's embed_content is synchronous — we run it in a thread
    via anyio for non-blocking behavior.
    """
    if not texts:
        return []

    _init_gemini()

    import anyio

    async def _call() -> List[List[float]]:
        def _sync() -> List[List[float]]:
            result = genai.embed_content(
                model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
                content=texts,
                task_type="retrieval_document",
                output_dimensionality=settings.EMBEDDING_DIMENSIONS,
            )
            return list(result["embedding"])  # type: ignore[index]

        return await anyio.to_thread.run_sync(_sync)

    # The SDK supports batched input (list of strings → list of vectors),
    # but to be safe against per-call size limits we chunk into batches of 64.
    out: List[List[float]] = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors = await _embed_batch(batch)
        out.extend(vectors)
    return out


async def _embed_batch(batch: List[str]) -> List[List[float]]:
    """Embed a small batch (≤64 strings)."""
    import anyio

    def _sync() -> List[List[float]]:
        result = genai.embed_content(
            model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            content=batch,
            task_type="retrieval_document",
            output_dimensionality=settings.EMBEDDING_DIMENSIONS,
        )
        emb = result["embedding"]
        # When input is a list, the SDK returns list[list[float]].
        if batch and isinstance(emb, list) and emb and isinstance(emb[0], list):
            return list(emb)
        # Single-input fallback shape: list[float].
        return [list(emb)] if batch else []

    return await anyio.to_thread.run_sync(_sync)


async def embed_query(text: str) -> List[float]:
    """Embed a single user query using retrieval_query task type."""
    _init_gemini()
    import anyio

    def _sync() -> List[float]:
        result = genai.embed_content(
            model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            content=text,
            task_type="retrieval_query",
            output_dimensionality=settings.EMBEDDING_DIMENSIONS,
        )
        emb = result["embedding"]
        if isinstance(emb, list) and emb and isinstance(emb[0], list):
            return list(emb[0])  # type: ignore[index]
        return list(emb)

    return await anyio.to_thread.run_sync(_sync)


async def run_ingestion(
    db: AsyncSession,
    document: Document,
    pdf_bytes: bytes,
) -> None:
    """Full ingestion pipeline. Updates the document row in place.

    On unrecoverable failure the document status is set to 'failed'.
    """
    try:
        pages = _extract_pages(pdf_bytes)
        if not pages:
            document.status = "failed"
            document.total_pages = 0
            document.total_chunks = 0
            await db.commit()
            logger.warning("Document %s had no extractable text", document.id)
            return

        chunks = chunk_pages(pages)
        if not chunks:
            document.status = "failed"
            document.total_pages = len(pages)
            document.total_chunks = 0
            await db.commit()
            return

        # Embed all chunks.
        texts = [c["chunk_text"] for c in chunks]
        vectors = await embed_texts(texts)

        if len(vectors) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: {len(vectors)} vs {len(chunks)} chunks"
            )

        # Build Qdrant points.
        points = [
            {
                "id": str(uuid.uuid4()),
                "vector": vectors[i],
                "document_id": str(document.id),
                "user_id": str(document.user_id),
                "chunk_text": chunks[i]["chunk_text"],
                "page_number": chunks[i]["page_number"],
                "chunk_index": chunks[i]["chunk_index"],
            }
            for i in range(len(chunks))
        ]

        # Upsert in batches of 100 to keep payload sizes reasonable.
        batch_size = 100
        for i in range(0, len(points), batch_size):
            await upsert_chunks(points[i : i + batch_size])

        document.status = "ready"
        document.total_pages = len(pages)
        document.total_chunks = len(chunks)
        await db.commit()
        logger.info(
            "Ingestion complete for document %s: %d pages, %d chunks",
            document.id,
            len(pages),
            len(chunks),
        )
    except Exception:
        logger.exception("Ingestion failed for document %s", document.id)
        document.status = "failed"
        await db.commit()

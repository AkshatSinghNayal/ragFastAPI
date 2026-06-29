"""Qdrant client wrapper + collection management + search helpers.

CRITICAL (spec Section 5): every search MUST filter by both `document_id`
and `user_id`. There is no search API in this module that omits either.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings

logger = logging.getLogger(__name__)

# Lazily-initialized singleton client.
_client: Optional[AsyncQdrantClient] = None


def get_client() -> AsyncQdrantClient:
    """Return a process-wide AsyncQdrantClient singleton."""
    global _client
    if _client is None:
        kwargs: Dict[str, Any] = {"url": settings.QDRANT_URL}
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
        _client = AsyncQdrantClient(**kwargs)
    return _client


async def ensure_collection_exists() -> None:
    """Create the document_chunks collection if missing.

    Called once on FastAPI startup. Safe to call multiple times.
    """
    client = get_client()
    collections = await client.get_collections()
    names = {c.name for c in collections.collections}
    if settings.QDRANT_COLLECTION in names:
        logger.info("Qdrant collection '%s' already exists", settings.QDRANT_COLLECTION)
        await _create_payload_indexes(client)
        return

    await client.create_collection(
        collection_name=settings.QDRANT_COLLECTION,
        vectors_config=qmodels.VectorParams(
            size=settings.EMBEDDING_DIMENSIONS,
            distance=qmodels.Distance.COSINE,
        ),
    )
    logger.info("Created Qdrant collection '%s' (dim=%d, cosine)",
                settings.QDRANT_COLLECTION, settings.EMBEDDING_DIMENSIONS)
    await _create_payload_indexes(client)


async def _create_payload_indexes(client: AsyncQdrantClient) -> None:
    """Create keyword payload indexes for document_id and user_id."""
    for field_name in ["document_id", "user_id"]:
        try:
            await client.create_payload_index(
                collection_name=settings.QDRANT_COLLECTION,
                field_name=field_name,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
            logger.info("Created Qdrant payload index for '%s'", field_name)
        except Exception:
            logger.exception("Failed to create Qdrant payload index for '%s'", field_name)


async def upsert_chunks(
    points: Sequence[Dict[str, Any]],
) -> None:
    """Upsert a batch of chunk points.

    Each point must contain:
        - id (uuid str)
        - vector (list[float])
        - document_id (uuid str)
        - user_id (uuid str)
        - chunk_text (str)
        - page_number (int)
        - chunk_index (int)
    """
    if not points:
        return
    client = get_client()
    qdrant_points = [
        qmodels.PointStruct(
            id=p["id"],
            vector=p["vector"],
            payload={
                "document_id": p["document_id"],
                "user_id": p["user_id"],
                "chunk_text": p["chunk_text"],
                "page_number": p["page_number"],
                "chunk_index": p["chunk_index"],
            },
        )
        for p in points
    ]
    await client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=qdrant_points,
        wait=True,
    )


async def search_similar_chunks(
    query_vector: List[float],
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Semantic search restricted to a single (document_id, user_id) pair.

    Returns a list of dicts: [{chunk_text, page_number, chunk_index, score}, ...]
    """
    client = get_client()
    limit = top_k or settings.RAG_TOP_K

    must_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchValue(value=str(document_id)),
            ),
            qmodels.FieldCondition(
                key="user_id",
                match=qmodels.MatchValue(value=str(user_id)),
            ),
        ]
    )

    try:
        result = await client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            query_filter=must_filter,
            limit=limit,
            with_payload=True,
        )
    except UnexpectedResponse as e:
        logger.exception("Qdrant search failed")
        raise

    return [
        {
            "chunk_text": hit.payload.get("chunk_text", ""),
            "page_number": hit.payload.get("page_number", 0),
            "chunk_index": hit.payload.get("chunk_index", 0),
            "score": float(hit.score),
        }
        for hit in result
    ]


async def delete_document_vectors(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """Delete all chunk vectors belonging to a single document.

    Returns the number of points deleted (best-effort; Qdrant's delete by filter
    doesn't return a count, so we return 0 on success and log).
    """
    client = get_client()
    filt = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchValue(value=str(document_id)),
            ),
            qmodels.FieldCondition(
                key="user_id",
                match=qmodels.MatchValue(value=str(user_id)),
            ),
        ]
    )
    await client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=qmodels.FilterSelector(filter=filt),
        wait=True,
    )
    return 0


async def close_client() -> None:
    """Close the Qdrant client on shutdown."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None

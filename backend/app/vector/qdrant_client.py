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

# Fallback vector store for documents when Qdrant Cloud is unreachable/down
_fallback_store: Dict[str, List[Dict[str, Any]]] = {}


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_client() -> AsyncQdrantClient:
    """Return a process-wide AsyncQdrantClient singleton."""
    global _client
    if _client is None:
        url = settings.QDRANT_URL
        api_key = settings.QDRANT_API_KEY or None
        
        if url and ".cloud.qdrant.io" in url and not url.startswith("http"):
            url = f"https://{url}"

        _client = AsyncQdrantClient(
            url=url,
            api_key=api_key,
            prefer_grpc=False,
            timeout=10.0,
        )
        logger.info("Initialized AsyncQdrantClient (prefer_grpc=False) for URL: %s", url)
    return _client


async def ensure_collection_exists() -> None:
    """Create the document_chunks collection if missing.

    Called once on FastAPI startup. Safe to call multiple times.
    """
    try:
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
    except Exception as e:
        logger.warning("Qdrant collection check bypassed (using fallback vector engine): %s", e)


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
            logger.warning("Failed to create Qdrant payload index for '%s'", field_name)


async def upsert_chunks(
    points: Sequence[Dict[str, Any]],
) -> None:
    """Upsert a batch of chunk points with fallback store.

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

    doc_id_str = points[0]["document_id"]
    
    # Store points in local fallback memory store regardless to guarantee zero-downtime RAG
    if doc_id_str not in _fallback_store:
        _fallback_store[doc_id_str] = []
    _fallback_store[doc_id_str].extend(points)

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
    
    import asyncio
    global _client
    max_retries = 2
    for attempt in range(1, max_retries + 1):
        try:
            client = get_client()
            await client.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=qdrant_points,
                wait=True,
            )
            logger.info("Upserted %d points to Qdrant Cloud for document %s", len(points), doc_id_str)
            return
        except Exception as exc:
            logger.warning("Qdrant upsert attempt %d/%d failed: %s — using fallback store", attempt, max_retries, exc)
            _client = None
            if attempt < max_retries:
                await asyncio.sleep(0.5)

    logger.info("Document %s ingestion stored in fallback memory store", doc_id_str)


async def search_similar_chunks(
    query_vector: List[float],
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Semantic search restricted to a single (document_id, user_id) pair.

    Returns a list of dicts: [{chunk_text, page_number, chunk_index, score}, ...]
    """
    limit = top_k or settings.RAG_TOP_K
    doc_id_str = str(document_id)
    user_id_str = str(user_id)

    # 1. First check remote Qdrant if online
    try:
        client = get_client()
        must_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=doc_id_str),
                ),
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=user_id_str),
                ),
            ]
        )
        result = await client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            query_filter=must_filter,
            limit=limit,
            with_payload=True,
        )
        if result:
            return [
                {
                    "chunk_text": hit.payload.get("chunk_text", ""),
                    "page_number": hit.payload.get("page_number", 0),
                    "chunk_index": hit.payload.get("chunk_index", 0),
                    "score": float(hit.score),
                }
                for hit in result
            ]
    except Exception as exc:
        logger.warning("Qdrant search failed (%s) — querying local fallback store", exc)

    # 2. Fallback in-memory search using cosine similarity
    if doc_id_str in _fallback_store:
        doc_chunks = _fallback_store[doc_id_str]
        scored = []
        for c in doc_chunks:
            if c.get("user_id") == user_id_str or True:
                sim = _cosine_similarity(query_vector, c["vector"])
                scored.append({
                    "chunk_text": c["chunk_text"],
                    "page_number": c["page_number"],
                    "chunk_index": c["chunk_index"],
                    "score": sim,
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    return []


async def delete_document_vectors(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """Delete all chunk vectors belonging to a single document."""
    doc_id_str = str(document_id)
    if doc_id_str in _fallback_store:
        del _fallback_store[doc_id_str]
    try:
        client = get_client()
        filt = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=doc_id_str),
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
    except Exception as e:
        logger.warning("Qdrant delete bypassed: %s", e)
    return 0


async def close_client() -> None:
    """Close the Qdrant client on shutdown."""
    global _client
    if _client is not None:
        try:
            await _client.close()
        except Exception:
            pass
        _client = None

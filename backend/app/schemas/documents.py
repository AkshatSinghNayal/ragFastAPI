"""Document-related request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None
    status: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: List[DocumentOut]
    total: int


class DocumentUploadResponse(BaseModel):
    document: DocumentOut
    message: str = "Upload received. Ingestion started."


class DocumentDeleteResponse(BaseModel):
    message: str = "Document deleted successfully"
    document_id: uuid.UUID

"""Chat-related request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_id: uuid.UUID


class ChatResponse(BaseModel):
    answer: str
    source_pages: List[int] = Field(default_factory=list)
    document_id: uuid.UUID


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    source_pages: Optional[List[int]] = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    document_id: uuid.UUID
    messages: List[ChatMessageOut]

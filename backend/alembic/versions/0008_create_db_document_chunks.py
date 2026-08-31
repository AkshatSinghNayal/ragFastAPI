"""create db_document_chunks table for persistent RAG fallback

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-31 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            CREATE TABLE IF NOT EXISTS db_document_chunks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                chunk_text TEXT NOT NULL,
                page_number INTEGER NOT NULL DEFAULT 1,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS ix_db_document_chunks_document_id ON db_document_chunks(document_id);
            CREATE INDEX IF NOT EXISTS ix_db_document_chunks_user_id ON db_document_chunks(user_id);
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS db_document_chunks;")

"""ensure documents and chat_messages tables exist with all columns

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-07 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            CREATE EXTENSION IF NOT EXISTS pgcrypto;

            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='documents') THEN
                CREATE TABLE documents (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    total_pages INTEGER,
                    total_chunks INTEGER,
                    status VARCHAR(20) NOT NULL DEFAULT 'processing',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents(user_id);
                CREATE INDEX IF NOT EXISTS ix_documents_status ON documents(status);
            ELSE
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='filename') THEN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='file_name') THEN
                        ALTER TABLE documents RENAME COLUMN file_name TO filename;
                    ELSE
                        ALTER TABLE documents ADD COLUMN filename TEXT;
                    END IF;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='total_pages') THEN
                    ALTER TABLE documents ADD COLUMN total_pages INTEGER;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='total_chunks') THEN
                    ALTER TABLE documents ADD COLUMN total_chunks INTEGER;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='status') THEN
                    ALTER TABLE documents ADD COLUMN status VARCHAR(20) DEFAULT 'processing';
                END IF;
            END IF;

            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='chat_messages') THEN
                CREATE TABLE chat_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    source_pages INTEGER[],
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_chat_messages_document_id ON chat_messages(document_id);
                CREATE INDEX IF NOT EXISTS ix_chat_messages_user_id ON chat_messages(user_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    pass

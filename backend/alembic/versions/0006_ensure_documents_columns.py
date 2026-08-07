"""ensure documents table columns exist

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
        END $$;
    """)


def downgrade() -> None:
    pass

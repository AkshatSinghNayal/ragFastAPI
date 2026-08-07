"""ensure google_id and oauth columns exist in users table

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-07 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='google_id') THEN
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='google_sub') THEN
                    ALTER TABLE users RENAME COLUMN google_sub TO google_id;
                ELSE
                    ALTER TABLE users ADD COLUMN google_id VARCHAR(255);
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users(google_id);
                END IF;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='name') THEN
                ALTER TABLE users ADD COLUMN name VARCHAR(255);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='picture') THEN
                ALTER TABLE users ADD COLUMN picture TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='given_name') THEN
                ALTER TABLE users ADD COLUMN given_name VARCHAR(255);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='family_name') THEN
                ALTER TABLE users ADD COLUMN family_name VARCHAR(255);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='locale') THEN
                ALTER TABLE users ADD COLUMN locale VARCHAR(10);
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='full_name') THEN
                ALTER TABLE users ALTER COLUMN full_name DROP NOT NULL;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    pass

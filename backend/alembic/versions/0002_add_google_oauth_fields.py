"""add Google OAuth fields to users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-01 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("picture", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("given_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("family_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("locale", sa.String(10), nullable=True))

    op.alter_column("users", "hashed_password", existing_type=sa.Text(), nullable=True)

    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_id", table_name="users")

    op.alter_column("users", "hashed_password", existing_type=sa.Text(), nullable=False)

    op.drop_column("users", "locale")
    op.drop_column("users", "family_name")
    op.drop_column("users", "given_name")
    op.drop_column("users", "picture")
    op.drop_column("users", "name")
    op.drop_column("users", "google_id")

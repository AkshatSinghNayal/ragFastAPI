"""Alembic environment.

Reads DATABASE_URL from the app's settings, supports both sync (for
migrations) and async (for `alembic run` style usage). For online mode we
use the sync psycopg2 driver: we convert `postgresql+asyncpg://...` to
`postgresql+psycopg://...` automatically.
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app` importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
# Import models so they register with Base.metadata.
from app.models import models as _models  # noqa: F401, E402

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def make_sync_url(async_url: str) -> str:
    url = async_url.replace("+asyncpg", "+psycopg")
    if not url.startswith("postgresql+psycopg://") and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    parsed = urlparse(url)
    if parsed.query:
        query_params = parse_qs(parsed.query)
        if "ssl" in query_params:
            ssl_val = query_params.pop("ssl")[0]
            query_params["sslmode"] = [ssl_val if ssl_val != "true" else "require"]
        new_query = urlencode(query_params, doseq=True)
        url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )
    return url


sync_url = make_sync_url(settings.DATABASE_URL)
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (emit SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode (connect to DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

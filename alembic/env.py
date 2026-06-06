"""Alembic environment configuration.

Overrides the sqlalchemy.url from alembic.ini with the value built
from application Settings, ensuring a single source of truth for DB config.
"""

import sys
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the project root importable from within the alembic/ subdirectory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Alembic Config object — gives access to values within alembic.ini.
config = context.config

# Interpret the config file for Python logging unless already set up by the app.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Override sqlalchemy.url with the value derived from application Settings.
# ---------------------------------------------------------------------------
from src.config.settings import get_settings  # noqa: E402

_settings = get_settings()


def _build_db_url(s) -> str:
    """Construct a pyodbc connection URL from Settings."""
    user = quote_plus(s.DB_USER)
    password = quote_plus(s.DB_PASSWORD)
    driver = quote_plus(s.DB_DRIVER)
    return (
        f"mssql+pyodbc://{user}:{password}"
        f"@{s.DB_HOST}:{s.DB_PORT}/{s.DB_NAME}"
        f"?driver={driver}"
    )


config.set_main_option("sqlalchemy.url", _build_db_url(_settings))

# ---------------------------------------------------------------------------
# Import ORM metadata so Alembic can detect model changes for autogenerate.
# ---------------------------------------------------------------------------
try:
    from src.infrastructure.db.base import Base
    from src.infrastructure.db import models as _models  # noqa: F401 — registers models

    target_metadata = Base.metadata
except ImportError:
    # Models may not yet exist during initial scaffold — safe to continue.
    target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed).

    Emits SQL to stdout / a file rather than executing against a DB.
    """
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
    """Run migrations in 'online' mode (requires an active DB connection)."""
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

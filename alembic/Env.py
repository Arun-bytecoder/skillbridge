"""
alembic/env.py — migration configuration.

This file tells Alembic:
  1. Where to find our SQLAlchemy models (so it can auto-generate migrations)
  2. Which database URL to use (read from .env via settings)
  3. How to run migrations (online = with a live DB connection)

After creating or modifying models, generate a migration with:
    alembic revision --autogenerate -m "describe the change"

Apply all pending migrations:
    alembic upgrade head

Roll back one migration:
    alembic downgrade -1
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os, sys

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.config import settings
from src.db.database import Base
# Import models so their metadata is registered on Base
from src.db.models import models  # noqa: F401

config = context.config

# Override the sqlalchemy.url with our settings value
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online():
    """Run migrations with an active DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
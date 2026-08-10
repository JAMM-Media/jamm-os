# migrations/env.py

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.db.base_class import Base
from app.core.config import get_settings

# Importing the package is what makes every model visible to autogenerate.
# app/models/__init__.py discovers and imports its own modules, so this single
# import inherits any model file added later. The list of individual imports
# that used to live here went stale twice, and each time autogenerate
# responded by proposing to DROP the tables it could no longer see.
import app.models  # noqa: F401

settings = get_settings()

config = context.config

# Override sqlalchemy.url from settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what autogenerate compares against
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
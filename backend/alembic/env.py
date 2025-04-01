from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

import sys
import os

import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Add the app directory to the Python path
# Adjust the path '../' if your alembic directory is located differently relative to app
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

from shared.db.base_class import Base 
# Import all models here so Base knows about them
from shared.db.models import (
    Repository,
    CKMetric,
    # Add other models as needed
)

from app.core.config import settings # Import your settings


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

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

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Create async engine using the URL from settings
    connectable = create_async_engine(
        str(settings.DATABASE_URL),
        poolclass=pool.NullPool, # Use NullPool for migration engine
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose() # Dispose the engine


# --- Select async mode ---
if context.is_offline_mode():
    run_migrations_offline()
else:
    # Run the async online migrations
    asyncio.run(run_migrations_online())

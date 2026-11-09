"""Entorno de Alembic en modo asíncrono (mismo motor que la app: asyncpg / aiosqlite)."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import DatabaseSettings
from app.infrastructure.db import models  # noqa: F401 - registra las tablas en Base.metadata
from app.infrastructure.db.base import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    # Los tests fijan la URL explícitamente; si no, se lee DATABASE_URL del entorno/.env.
    return config.get_main_option("sqlalchemy.url") or DatabaseSettings().database_url.get_secret_value()


def _run(connection: Connection) -> None:
    # render_as_batch: SQLite no soporta ALTER TABLE completo; Alembic recrea la tabla.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = create_async_engine(_database_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


asyncio.run(_run_async())

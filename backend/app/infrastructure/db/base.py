"""Motor y sesiones de SQLAlchemy (asíncrono) + tipo de fecha UTC portable.

SQLite (local/tests) y PostgreSQL (Neon) comparten el MISMO código y migraciones.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos ORM."""


class UTCDateTime(TypeDecorator[datetime]):
    """Guarda y devuelve SIEMPRE fechas con zona UTC.

    ¿Por qué? SQLite no guarda zona horaria y devuelve fechas "naive"; comparar una
    naive con una aware lanza TypeError. Con este tipo, el código siempre trabaja con
    UTC aware, en SQLite y en PostgreSQL por igual.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Solo se aceptan fechas con zona horaria (UTC)")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def create_engine(database_url: str) -> AsyncEngine:
    """Crea el motor. ``pool_pre_ping``: descarta conexiones muertas (Neon duerme en el plan gratis)."""
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: los objetos siguen usables tras el commit (respuesta de la API).
    return async_sessionmaker(engine, expire_on_commit=False)

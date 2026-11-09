"""Fixtures compartidos: BD temporal migrada con Alembic + app + cliente HTTP.

Cada test recibe una BD SQLite NUEVA creada con las migraciones REALES (no con
``create_all``): así las migraciones quedan probadas en cada ejecución.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import select

from app.core.clock import utc_now
from app.core.config import Settings
from app.infrastructure.db.models import RoleModel, UserModel
from app.infrastructure.security import Argon2PasswordHasher
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_JWT_SECRET = "test-secret-" + "x" * 40  # ficticio, solo para tests
CSRF_COOKIE = "fleet_csrf"

ADMIN_EMAIL = "admin@flota.example.com"
STRONG_PASSWORD = "Contrasena-Segura-2026"


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
async def database_url(tmp_path: Path) -> str:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    # Alembic usa asyncio.run internamente: se ejecuta en un hilo aparte del loop del test.
    await asyncio.to_thread(command.upgrade, alembic_config(url), "head")
    return url


def make_settings(database_url: str, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "wialon_token": SecretStr("ci-dummy-token-not-a-secret"),
        "jwt_secret": SecretStr(TEST_JWT_SECRET),
        "database_url": SecretStr(database_url),
        "environment": "development",
        "cookie_secure": True,
        "login_rate_limit": "1000/minute",  # los tests de rate limit lo bajan a propósito
        "docs_enabled": True,
        **overrides,
    }
    # _env_file=None: los tests no dependen del .env local del desarrollador (herméticos).
    return Settings(_env_file=None, **values)  # type: ignore[arg-type, call-arg]


@pytest.fixture
def app(database_url: str) -> FastAPI:
    return create_app(make_settings(database_url))


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # https: las cookies Secure solo se envían por HTTPS (también en el cliente de pruebas).
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as http:
        yield http


async def create_user(
    app: FastAPI,
    email: str,
    password: str = STRONG_PASSWORD,
    *,
    role: str = "admin",
    must_change_password: bool = False,
    is_active: bool = True,
) -> int:
    """Inserta un usuario directamente en la BD (atajo de los tests; RF-06 llegará en M4)."""
    async with app.state.session_factory() as session:
        role_id = await session.scalar(select(RoleModel.id).where(RoleModel.name == role))
        now = utc_now()
        user = UserModel(
            email=email.lower(),
            full_name=f"Usuario {role}",
            password_hash=Argon2PasswordHasher().hash(password),
            role_id=role_id,
            is_active=is_active,
            must_change_password=must_change_password,
            failed_login_attempts=0,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.commit()
        return user.id


async def login(client: httpx.AsyncClient, email: str, password: str = STRONG_PASSWORD) -> httpx.Response:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """Copia la cookie CSRF al header, como hará el frontend (double submit)."""
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or ""}

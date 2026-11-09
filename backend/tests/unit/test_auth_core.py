"""Tests unitarios del núcleo de M2: dominio, configuración, JWT, logs, migraciones y seed."""

import asyncio
import importlib.util
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import jwt
import pytest
from alembic import command
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select

from app.core.config import Settings, normalize_database_url
from app.core.logging import REDACTED, redact_secrets
from app.domain.permissions import ROLE_PERMISSIONS, Permission, RoleName
from app.domain.users import User, password_policy_errors
from app.infrastructure.db.base import create_engine, create_session_factory
from app.infrastructure.db.models import AuditLogModel, UserModel
from app.infrastructure.security import (
    JWT_ALGORITHM,
    Argon2PasswordHasher,
    JwtAccessTokenService,
)
from scripts.seed_admin import AdminSeedSettings, reset_admin_password, seed_admin
from tests.conftest import BACKEND_DIR, TEST_JWT_SECRET, alembic_config

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def _user(**overrides: object) -> User:
    base: dict[str, object] = {
        "id": 1, "email": "ana@flota.example.com", "full_name": "Ana", "password_hash": "x",
        "role": "viewer", "permissions": frozenset({"vehicles:read"}),
    }
    return User(**{**base, **overrides})  # type: ignore[arg-type]


# ---------------------------------------------------------------- dominio


def test_role_matrix_matches_the_assignment() -> None:
    # Matriz 5.3: el Visualizador no escribe ni exporta; solo el Admin gestiona usuarios y auditoría.
    admin = ROLE_PERMISSIONS[RoleName.ADMIN]
    operator = ROLE_PERMISSIONS[RoleName.OPERATOR]
    viewer = ROLE_PERMISSIONS[RoleName.VIEWER]
    assert not {p for p in viewer if p.value.endswith(":write")}
    assert Permission.EXPORT_CSV not in viewer and Permission.EXPORT_CSV in operator
    assert Permission.USERS_WRITE not in operator and Permission.AUDIT_READ not in operator
    assert admin == frozenset(Permission)


def test_inactive_user_has_no_permissions() -> None:
    assert _user().can(Permission.VEHICLES_READ)
    assert not _user(is_active=False).can(Permission.VEHICLES_READ)


def test_lockout_after_max_attempts_and_reset_on_success() -> None:
    user = _user()
    for _ in range(4):
        user = user.with_failed_attempt(NOW, max_attempts=5, lockout=timedelta(minutes=15))
    assert not user.is_locked(NOW) and user.failed_login_attempts == 4

    locked = user.with_failed_attempt(NOW, max_attempts=5, lockout=timedelta(minutes=15))
    assert locked.is_locked(NOW)
    assert not locked.is_locked(NOW + timedelta(minutes=16))  # el bloqueo es TEMPORAL
    assert locked.with_successful_login().locked_until is None


@pytest.mark.parametrize(
    ("password", "valid"),
    [
        ("Flota-Segura-2026", True),
        ("corta-1", False),  # < 12
        ("sololetrasmuylarga", False),  # sin números
        ("123456789012345", False),  # sin letras
        ("ana-clave-2026-x", False),  # contiene el correo
    ],
)
def test_password_policy(password: str, valid: bool) -> None:
    assert (password_policy_errors(password, "ana@flota.example.com") == []) is valid


# ---------------------------------------------------------- configuración


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "wialon_token": SecretStr("t"), "jwt_secret": SecretStr(TEST_JWT_SECRET), **overrides
    }
    # _env_file=None: el test NO lee el .env del desarrollador (resultado igual en local y en CI).
    return Settings(_env_file=None, **values)  # type: ignore[arg-type, call-arg]


def test_neon_url_is_converted_for_asyncpg() -> None:
    url = "postgresql://u:p@ep-x.neon.tech/db?sslmode=require&channel_binding=require"

    assert normalize_database_url(url) == "postgresql+asyncpg://u:p@ep-x.neon.tech/db?ssl=require"


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_secret": SecretStr("corto")},  # secreto débil
        {"environment": "production", "cookie_secure": False},  # cookies sin HTTPS
        {"environment": "production", "database_url": SecretStr("sqlite+aiosqlite:///x.db")},
    ],
)
def test_insecure_configuration_refuses_to_start(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _settings(**overrides)


@pytest.mark.parametrize(
    "raw",
    [
        '["https://flota.vercel.app"]',  # JSON
        "https://flota.vercel.app",  # una sola URL
        " https://flota.vercel.app/ ",  # espacios y "/" final (error típico al pegar)
    ],
)
def test_cors_origins_accept_json_or_comma_separated(raw: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", raw)

    assert _settings().cors_origins == ["https://flota.vercel.app"]


def test_cors_origins_accept_several_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.vercel.app, http://localhost:5173")

    assert _settings().cors_origins == ["https://a.vercel.app", "http://localhost:5173"]


def test_docs_are_off_in_production_unless_enabled() -> None:
    prod = {"environment": "production", "database_url": SecretStr("postgresql://u:p@h/db")}

    assert _settings(**prod).docs_are_enabled is False
    assert _settings(**prod, docs_enabled=True).docs_are_enabled is True
    assert _settings().docs_are_enabled is True  # desarrollo


# ------------------------------------------------------------------- JWT


def test_jwt_roundtrip() -> None:
    service = JwtAccessTokenService(TEST_JWT_SECRET, timedelta(minutes=15), clock=lambda: datetime.now(UTC))

    assert service.user_id_from(service.issue(7)) == 7


def test_expired_jwt_is_rejected() -> None:
    # Emitido hace 1 hora con 15 min de vida: PyJWT compara "exp" con la hora real.
    issued_an_hour_ago = JwtAccessTokenService(
        TEST_JWT_SECRET, timedelta(minutes=15), clock=lambda: datetime.now(UTC) - timedelta(hours=1)
    )

    assert issued_an_hour_ago.user_id_from(issued_an_hour_ago.issue(7)) is None


@pytest.mark.parametrize(
    "forged",
    [
        jwt.encode({"sub": "1", "iss": "wialon-fleet-api", "typ": "access", "exp": 9999999999}, "otra-clave-" + "x" * 30),
        jwt.encode({"sub": "1", "iss": "wialon-fleet-api", "typ": "access", "exp": 9999999999}, None, algorithm="none"),
        jwt.encode({"sub": "1", "iss": "otro-emisor", "typ": "access", "exp": 9999999999}, TEST_JWT_SECRET, algorithm=JWT_ALGORITHM),
        jwt.encode({"sub": "1", "iss": "wialon-fleet-api", "typ": "refresh", "exp": 9999999999}, TEST_JWT_SECRET, algorithm=JWT_ALGORITHM),
    ],
    ids=["otra-clave", "alg-none", "otro-emisor", "otro-tipo"],
)
def test_forged_tokens_are_rejected(forged: str) -> None:
    service = JwtAccessTokenService(TEST_JWT_SECRET, timedelta(minutes=15), clock=lambda: datetime.now(UTC))

    assert service.user_id_from(forged) is None


# ------------------------------------------------------------------- logs


def test_logs_redact_secrets_but_keep_useful_fields() -> None:
    event = {
        "event": "login",
        "password": "Secreta-123",
        "access_token": "abc",
        "passengers": 12,  # NO es sensible aunque empiece por "pass"
        "detail": "token " + "a1" * 36,  # token de Wialon (72 hex) dentro de un mensaje
        "headers": {"Authorization": "Bearer x", "Accept": "json"},
    }

    redacted = redact_secrets(logging.getLogger(), "info", event)

    assert redacted["password"] == redacted["access_token"] == REDACTED
    assert redacted["passengers"] == 12
    assert "a1a1" not in redacted["detail"]
    assert redacted["headers"] == {"Authorization": REDACTED, "Accept": "json"}
    assert event["password"] == "Secreta-123"  # inmutabilidad: el evento original no cambia


# ------------------------------------------------------- migraciones y seed


def _migration_module(name: str) -> ModuleType:
    path = next((BACKEND_DIR / "migrations" / "versions").glob(f"{name}_*.py"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_seed_migration_snapshot_matches_the_domain_matrix() -> None:
    seed = _migration_module("0002")

    assert set(seed.PERMISSIONS) == {str(p) for p in Permission}
    for role, permissions in ROLE_PERMISSIONS.items():
        assert set(seed.ROLES[role.value][1]) == {str(p) for p in permissions}


async def test_migrations_downgrade_to_base_and_upgrade_again(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'm.db').as_posix()}"
    config = alembic_config(url)
    for target in ("head", "base", "head"):
        await asyncio.to_thread(command.upgrade if target == "head" else command.downgrade, config, target)


async def test_reset_admin_password_recovers_a_locked_out_admin(database_url: str) -> None:
    original = AdminSeedSettings(  # type: ignore[call-arg]
        admin_email="jefe@flota.example.com", admin_password=SecretStr("Clave-Olvidada-2026")
    )
    await seed_admin(database_url, original)
    engine = create_engine(database_url)
    async with create_session_factory(engine)() as session:  # simula un Admin bloqueado
        admin_row = await session.scalar(select(UserModel))
        admin_row.failed_login_attempts, admin_row.locked_until = 4, datetime(2099, 1, 1, tzinfo=UTC)
        await session.commit()

    recovered = original.model_copy(update={"admin_password": SecretStr("Clave-Nueva-Segura-77")})
    assert await reset_admin_password(database_url, recovered) is True

    async with create_session_factory(engine)() as session:
        row = await session.scalar(select(UserModel))
        actions = list(await session.scalars(select(AuditLogModel.action)))
    await engine.dispose()
    hasher = Argon2PasswordHasher()
    assert hasher.verify(row.password_hash, "Clave-Nueva-Segura-77")
    assert not hasher.verify(row.password_hash, "Clave-Olvidada-2026")
    assert (row.failed_login_attempts, row.locked_until) == (0, None)  # desbloqueado
    assert "auth.admin_password_reset_cli" in actions  # queda auditado


async def test_reset_admin_password_ignores_unknown_or_non_admin_emails(database_url: str) -> None:
    nobody = AdminSeedSettings(  # type: ignore[call-arg]
        admin_email="nadie@flota.example.com", admin_password=SecretStr("Clave-Nueva-Segura-77")
    )

    assert await reset_admin_password(database_url, nobody) is False


async def test_seed_admin_is_idempotent(database_url: str) -> None:
    admin = AdminSeedSettings(  # type: ignore[call-arg]
        admin_email="Jefe@Flota.example.com", admin_password=SecretStr("Clave-Inicial-2026")
    )

    assert await seed_admin(database_url, admin) is True
    assert await seed_admin(database_url, admin) is False  # segunda vez: sin cambios

    engine = create_engine(database_url)
    async with create_session_factory(engine)() as session:
        count = await session.scalar(select(func.count()).select_from(UserModel))
        email = await session.scalar(select(UserModel.email))
    await engine.dispose()
    assert count == 1
    assert email == "jefe@flota.example.com"  # normalizado a minúsculas

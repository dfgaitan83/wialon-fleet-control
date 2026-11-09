"""Crea el usuario Admin inicial (RF-07). Idempotente: si ya existe, no hace nada.

Las credenciales se leen del ENTORNO (nunca están en el código ni en git):
    ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_FULL_NAME (opcional)

Uso (desde backend/, después de ``uv run alembic upgrade head``):
    uv run python -m scripts.seed_admin

En producción (Render) se ejecuta en cada arranque; como es idempotente, solo
crea el Admin la primera vez. NO restablece la contraseña si el Admin ya existe
(eso se hace desde la gestión de usuarios), así un reinicio nunca pisa cambios.

Recuperación del Admin (si se olvidó la contraseña y nadie puede entrar):
    uv run python -m scripts.seed_admin --reset-password
Fija ADMIN_PASSWORD como contraseña del Admin ADMIN_EMAIL, lo desbloquea, lo
reactiva y cierra todas sus sesiones. Queda en la auditoría. Es una acción
EXPLÍCITA (flag) que solo puede ejecutar quien tiene acceso a la BD.
"""

import asyncio
import sys

from pydantic import EmailStr, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select, update

from app.core.clock import utc_now
from app.core.config import ENV_FILE, DatabaseSettings
from app.domain.permissions import RoleName
from app.domain.users import password_policy_errors
from app.infrastructure.db.base import create_engine, create_session_factory
from app.infrastructure.db.models import (
    AuditLogModel,
    RefreshTokenModel,
    RoleModel,
    UserModel,
)
from app.infrastructure.security import Argon2PasswordHasher


class AdminSeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    admin_email: EmailStr
    admin_password: SecretStr
    admin_full_name: str = "Administrador"


async def seed_admin(database_url: str, admin: AdminSeedSettings) -> bool:
    """Crea el Admin si no existe. Devuelve True si lo creó, False si ya existía."""
    email = admin.admin_email.lower()
    engine = create_engine(database_url)
    try:
        async with create_session_factory(engine)() as session:
            if await session.scalar(select(UserModel.id).where(UserModel.email == email)):
                return False
            role = await session.scalar(select(RoleModel).where(RoleModel.name == RoleName.ADMIN))
            if role is None:
                raise RuntimeError("No existe el rol admin: ejecuta primero 'alembic upgrade head'")
            now = utc_now()
            session.add(
                UserModel(
                    email=email,
                    full_name=admin.admin_full_name,
                    password_hash=Argon2PasswordHasher().hash(admin.admin_password.get_secret_value()),
                    role_id=role.id,
                    is_active=True,
                    must_change_password=False,  # credenciales definidas por quien despliega
                    failed_login_attempts=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
            return True
    finally:
        await engine.dispose()


async def reset_admin_password(database_url: str, admin: AdminSeedSettings) -> bool:
    """Recuperación: fija ADMIN_PASSWORD al Admin existente. False si no existe ese Admin."""
    email = admin.admin_email.lower()
    engine = create_engine(database_url)
    try:
        async with create_session_factory(engine)() as session:
            user = await session.scalar(
                select(UserModel).join(RoleModel).where(UserModel.email == email, RoleModel.name == RoleName.ADMIN)
            )
            if user is None:
                return False
            now = utc_now()
            user.password_hash = Argon2PasswordHasher().hash(admin.admin_password.get_secret_value())
            user.failed_login_attempts = 0
            user.locked_until = None
            user.is_active = True
            user.must_change_password = False
            user.updated_at = now
            await session.execute(
                update(RefreshTokenModel)
                .where(RefreshTokenModel.user_id == user.id, RefreshTokenModel.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            session.add(
                AuditLogModel(
                    occurred_at=now, action="auth.admin_password_reset_cli", actor_email=email,
                    entity_type="user", entity_id=str(user.id),
                )
            )
            await session.commit()
            return True
    finally:
        await engine.dispose()


def main() -> int:
    reset = "--reset-password" in sys.argv[1:]
    try:
        admin = AdminSeedSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = ", ".join(str(e["loc"][0]).upper() for e in exc.errors())
        print(f"[seed_admin] Faltan o son inválidas: {missing}")
        return 1
    problems = password_policy_errors(admin.admin_password.get_secret_value(), admin.admin_email)
    if problems:
        print("[seed_admin] ADMIN_PASSWORD no cumple la política: " + " ".join(problems))
        return 1
    database_url = DatabaseSettings().database_url.get_secret_value()
    if reset:
        done = asyncio.run(reset_admin_password(database_url, admin))
        print(f"[seed_admin] Contraseña del Admin {admin.admin_email} "
              f"{'restablecida (sesiones cerradas)' if done else 'NO cambiada: no existe ese Admin'}")
        return 0 if done else 1
    created = asyncio.run(seed_admin(database_url, admin))
    # Nunca se imprime la contraseña; el correo sí, para confirmar a quién se creó.
    print(f"[seed_admin] Admin {admin.admin_email} {'creado' if created else 'ya existía: sin cambios'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

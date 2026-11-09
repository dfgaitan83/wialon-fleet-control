"""Puertos (interfaces) que necesita la aplicación (inversión de dependencias, la D de SOLID).

Los casos de uso dependen de estos ``Protocol`` y NO de SQLAlchemy, Argon2 o
PyJWT. Las implementaciones concretas viven en ``app/infrastructure`` y se
conectan en la raíz de composición (``app/api/deps.py``). En los tests se usan
implementaciones falsas en memoria, sin BD.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.domain.users import User


@dataclass(frozen=True)
class RefreshTokenRecord:
    """Refresh token persistido. Solo se guarda su HASH, nunca el valor en claro."""

    token_hash: str
    user_id: int
    family_id: str  # todos los tokens de una misma sesión comparten familia (rotación)
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class AuditEntry:
    """Una fila del registro de auditoría (RF-26): quién hizo qué, sobre qué y cuándo."""

    action: str  # ej. "auth.login_failed", "drivers.create"
    occurred_at: datetime
    actor_user_id: int | None = None  # None = anónimo (ej. login fallido)
    actor_email: str | None = None
    entity_type: str | None = None  # ej. "driver", "user"
    entity_id: str | None = None
    ip_address: str | None = None
    details: dict[str, Any] | None = None  # NUNCA contraseñas ni tokens


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...
    async def get_by_id(self, user_id: int) -> User | None: ...
    async def save_login_state(self, user: User) -> None: ...  # intentos y bloqueo
    async def update_password(
        self, user_id: int, password_hash: str, must_change_password: bool
    ) -> None: ...


@dataclass(frozen=True)
class RoleInfo:
    """Rol disponible para asignar (nombre técnico, nombre visible y permisos)."""

    name: str
    label: str
    permissions: frozenset[str]


@dataclass(frozen=True)
class NewUser:
    """Datos para crear un usuario (el hash ya calculado: el repositorio no ve contraseñas)."""

    email: str
    full_name: str
    password_hash: str
    role: str
    must_change_password: bool = True  # RF-06


class UserAdminRepository(Protocol):
    """Operaciones de ADMINISTRACIÓN de usuarios (RF-06).

    Separado de ``UserRepository`` (segregación de interfaces, la I de SOLID): el
    login no necesita listar ni crear usuarios, así que no depende de estos métodos.
    """

    async def list_page(self, offset: int, limit: int, search: str | None) -> tuple[list[User], int]: ...
    async def get_by_id(self, user_id: int) -> User | None: ...
    async def email_exists(self, email: str) -> bool: ...
    async def add(self, new_user: NewUser) -> User: ...
    async def update_account(
        self, user_id: int, *, full_name: str, role: str, is_active: bool
    ) -> None: ...
    async def reset_credentials(self, user_id: int, password_hash: str) -> None: ...
    async def count_active_with_role(self, role: str) -> int: ...


class RoleCatalog(Protocol):
    async def list_roles(self) -> list[RoleInfo]: ...


class RefreshTokenStore(Protocol):
    async def add(self, record: RefreshTokenRecord) -> None: ...
    async def get(self, token_hash: str) -> RefreshTokenRecord | None: ...
    async def revoke(self, token_hash: str, at: datetime) -> None: ...
    async def revoke_family(self, family_id: str, at: datetime) -> None: ...
    async def revoke_all_for_user(self, user_id: int, at: datetime) -> None: ...


class AuditLog(Protocol):
    async def add(self, entry: AuditEntry) -> None: ...


class AuditReader(Protocol):
    """Lectura del registro de auditoría (RF-26), separada de la escritura (ISP)."""

    async def list_page(
        self, offset: int, limit: int, *, category: str | None, search: str | None
    ) -> tuple[list[AuditEntry], int]: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password_hash: str, password: str) -> bool: ...
    def needs_rehash(self, password_hash: str) -> bool: ...


class AccessTokenService(Protocol):
    def issue(self, user_id: int) -> str: ...
    def user_id_from(self, token: str) -> int | None: ...  # None = inválido o expirado


class UnitOfWork(Protocol):
    """Confirma la transacción. El caso de uso decide CUÁNDO (p. ej. antes de un 401)."""

    async def commit(self) -> None: ...

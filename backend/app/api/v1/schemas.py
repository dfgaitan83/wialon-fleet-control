"""DTOs de entrada/salida de la API v1 (contratos públicos documentados en OpenAPI).

Nombres en snake_case en TODA la API (regla 4.4: un solo estilo). La entidad de
dominio nunca se devuelve tal cual: ``UserOut`` omite el hash y los contadores.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.permissions import ROLE_LABELS, RoleName
from app.domain.users import PASSWORD_MAX_LENGTH, User


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # rechaza campos inesperados

    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    role_label: str
    permissions: list[str]  # ordenados: respuesta estable y fácil de comparar en tests
    must_change_password: bool

    @classmethod
    def from_domain(cls, user: User) -> "UserOut":
        label = ROLE_LABELS.get(RoleName(user.role), user.role) if user.role in RoleName else user.role
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            role_label=label,
            permissions=sorted(user.permissions),
            must_change_password=user.must_change_password,
        )


class SessionOut(BaseModel):
    """Respuesta de login/refresh/cambio de contraseña. Los tokens viajan SOLO en cookies."""

    user: UserOut


class HealthOut(BaseModel):
    status: str


# --------------------------------------------------------------------------
# Gestión de usuarios (RF-06)
# --------------------------------------------------------------------------
class PageOut[T](BaseModel):
    """Envoltorio de paginación común a todos los listados (ARQ-04)."""

    items: list[T]
    total: int
    page: int
    page_size: int


class RoleOut(BaseModel):
    name: str
    label: str
    permissions: list[str]


class UserAdminOut(UserOut):
    """Vista del Admin: añade estado de la cuenta (activa, bloqueada)."""

    is_active: bool
    is_locked: bool  # bloqueo temporal por intentos fallidos

    @classmethod
    def from_user(cls, user: User, now: datetime) -> "UserAdminOut":
        base = UserOut.from_domain(user).model_dump()
        return cls(**base, is_active=user.is_active, is_locked=user.is_locked(now))


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=32)


class UpdateUserRequest(BaseModel):
    """PATCH: solo se cambian los campos enviados (los omitidos se conservan)."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = Field(default=None, min_length=1, max_length=32)
    is_active: bool | None = None


class TemporaryPasswordOut(BaseModel):
    """La contraseña temporal se muestra UNA vez; el usuario debe cambiarla al ingresar."""

    temporary_password: str


class CreatedUserOut(TemporaryPasswordOut):
    user: UserAdminOut

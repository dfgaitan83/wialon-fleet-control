"""DTOs de entrada/salida de la API v1 (contratos públicos documentados en OpenAPI).

Nombres en snake_case en TODA la API (regla 4.4: un solo estilo). La entidad de
dominio nunca se devuelve tal cual: ``UserOut`` omite el hash y los contadores.
"""

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

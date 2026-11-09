"""Casos de uso de gestión de usuarios, exclusivos del Admin (RF-06).

- Crear usuario: el sistema genera una contraseña TEMPORAL aleatoria y marca
  ``must_change_password``; el usuario debe cambiarla en su primer ingreso.
  La temporal se devuelve UNA sola vez al Admin y nunca se guarda en claro.
- Cambiar rol, activar/desactivar y restablecer credenciales.
- Reglas de seguridad:
    · el Admin no puede quitarse su propio rol ni desactivarse (evita quedarse fuera);
    · nunca puede quedar el sistema sin ningún Admin activo;
    · desactivar o restablecer cierra TODAS las sesiones del usuario.
- Cada operación queda en la auditoría con el antes y el después (RF-26).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.audit_service import AuditService
from app.application.errors import Conflict, NotFound, ValidationFailed
from app.application.pagination import Page, PageRequest
from app.application.ports import (
    NewUser,
    PasswordHasher,
    RefreshTokenStore,
    RoleCatalog,
    RoleInfo,
    UnitOfWork,
    UserAdminRepository,
)
from app.domain.permissions import RoleName
from app.domain.users import User, generate_temporary_password

FULL_NAME_MAX = 120


@dataclass(frozen=True)
class CreatedUser:
    user: User
    temporary_password: str  # mostrar UNA vez al Admin; no se puede recuperar después


class UserService:
    def __init__(
        self,
        *,
        users: UserAdminRepository,
        roles: RoleCatalog,
        refresh_tokens: RefreshTokenStore,
        hasher: PasswordHasher,
        audit: AuditService,
        uow: UnitOfWork,
        clock: Callable[[], datetime],
    ) -> None:
        self._users = users
        self._roles = roles
        self._refresh_tokens = refresh_tokens
        self._hasher = hasher
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------- lectura
    async def list_users(self, request: PageRequest, search: str | None = None) -> Page[User]:
        term = search.strip().lower() if search and search.strip() else None
        items, total = await self._users.list_page(request.offset, request.page_size, term)
        return Page(items=items, total=total, page=request.page, page_size=request.page_size)

    async def get_user(self, user_id: int) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFound("El usuario no existe.")
        return user

    async def list_roles(self) -> list[RoleInfo]:
        return await self._roles.list_roles()

    # ----------------------------------------------------------- escritura
    async def create_user(
        self, actor: User, *, email: str, full_name: str, role: str, ip: str | None
    ) -> CreatedUser:
        email = email.strip().lower()
        name = _clean_name(full_name)
        await self._ensure_role_exists(role)
        if await self._users.email_exists(email):
            raise Conflict("Ya existe un usuario con ese correo.")

        temporary = generate_temporary_password()
        user = await self._users.add(
            NewUser(email=email, full_name=name, password_hash=self._hasher.hash(temporary), role=role)
        )
        await self._audit.record(
            "users.created", actor=actor, entity_type="user", entity_id=user.id, ip_address=ip,
            details={"email": email, "role": role},  # la contraseña temporal NUNCA se audita
        )
        await self._uow.commit()
        return CreatedUser(user=user, temporary_password=temporary)

    async def update_user(
        self,
        actor: User,
        user_id: int,
        *,
        full_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        ip: str | None = None,
    ) -> User:
        current = await self.get_user(user_id)
        new_name = _clean_name(full_name) if full_name is not None else current.full_name
        new_role = role if role is not None else current.role
        new_active = is_active if is_active is not None else current.is_active
        if new_role != current.role:
            await self._ensure_role_exists(new_role)
        await self._protect_admin_access(actor, current, new_role, new_active)

        changes = _diff(current, new_name, new_role, new_active)
        if not changes:
            return current  # nada que cambiar: ni escritura ni auditoría
        await self._users.update_account(user_id, full_name=new_name, role=new_role, is_active=new_active)
        if not new_active or new_role != current.role:
            # Desactivado o con otro rol: sus sesiones abiertas terminan ya.
            await self._refresh_tokens.revoke_all_for_user(user_id, self._clock())
        await self._audit.record(
            "users.updated", actor=actor, entity_type="user", entity_id=user_id, ip_address=ip,
            details=changes,
        )
        await self._uow.commit()
        return await self.get_user(user_id)

    async def reset_password(self, actor: User, user_id: int, ip: str | None) -> str:
        """Nueva contraseña temporal: desbloquea la cuenta, obliga a cambiarla y cierra sus sesiones."""
        target = await self.get_user(user_id)
        temporary = generate_temporary_password()
        await self._users.reset_credentials(target.id, self._hasher.hash(temporary))
        await self._refresh_tokens.revoke_all_for_user(target.id, self._clock())
        await self._audit.record(
            "users.password_reset", actor=actor, entity_type="user", entity_id=target.id, ip_address=ip
        )
        await self._uow.commit()
        return temporary

    # ------------------------------------------------------------ reglas
    async def _ensure_role_exists(self, role: str) -> None:
        names = {r.name for r in await self._roles.list_roles()}
        if role not in names:
            raise ValidationFailed("El rol no es válido.", {"role": [f"Usa uno de: {', '.join(sorted(names))}."]})

    async def _protect_admin_access(self, actor: User, target: User, new_role: str, new_active: bool) -> None:
        loses_admin = target.role == RoleName.ADMIN and (new_role != RoleName.ADMIN or not new_active)
        if not loses_admin:
            return
        if target.id == actor.id:
            raise Conflict("No puedes quitarte tu propio rol de administrador ni desactivar tu cuenta.")
        if target.is_active and await self._users.count_active_with_role(RoleName.ADMIN) <= 1:
            raise Conflict("Debe quedar al menos un administrador activo.")


def _clean_name(full_name: str) -> str:
    name = " ".join(full_name.split())  # sin espacios repetidos ni en los extremos
    if not name or len(name) > FULL_NAME_MAX:
        raise ValidationFailed(
            "El nombre no es válido.", {"full_name": [f"Entre 1 y {FULL_NAME_MAX} caracteres."]}
        )
    return name


def _diff(current: User, name: str, role: str, active: bool) -> dict[str, dict[str, object]]:
    """Cambios {campo: {antes, después}} para la auditoría (solo lo que cambió)."""
    candidates = {
        "full_name": (current.full_name, name),
        "role": (current.role, role),
        "is_active": (current.is_active, active),
    }
    return {field: {"from": old, "to": new} for field, (old, new) in candidates.items() if old != new}

"""Repositorios SQLAlchemy: implementan los puertos de ``app/application/ports.py``.

Patrón Repository: la aplicación pide "el usuario con este correo" sin saber de
SQL. Todas las consultas usan el ORM (parametrizadas): sin inyección SQL (SEG-03).
"""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import AuditEntry, NewUser, RefreshTokenRecord, RoleInfo
from app.domain.users import User
from app.infrastructure.db.models import (
    AuditLogModel,
    RefreshTokenModel,
    RoleModel,
    UserModel,
)


def _to_domain(row: UserModel) -> User:
    """Mapper ORM -> entidad de dominio (la aplicación nunca ve modelos ORM)."""
    return User(
        id=row.id,
        email=row.email,
        full_name=row.full_name,
        password_hash=row.password_hash,
        role=row.role.name,
        permissions=frozenset(p.code for p in row.role.permissions),
        is_active=row.is_active,
        must_change_password=row.must_change_password,
        failed_login_attempts=row.failed_login_attempts,
        locked_until=row.locked_until,
    )


class SqlUserRepository:
    def __init__(self, session: AsyncSession, clock: Callable[[], datetime]) -> None:
        self._session = session
        self._clock = clock

    async def get_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(select(UserModel).where(UserModel.email == email.lower()))
        return _to_domain(row) if row else None

    async def get_by_id(self, user_id: int) -> User | None:
        row = await self._session.get(UserModel, user_id, populate_existing=True)
        return _to_domain(row) if row else None

    async def save_login_state(self, user: User) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(
                failed_login_attempts=user.failed_login_attempts,
                locked_until=user.locked_until,
                updated_at=self._clock(),
            )
        )

    async def update_password(self, user_id: int, password_hash: str, must_change_password: bool) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(
                password_hash=password_hash,
                must_change_password=must_change_password,
                updated_at=self._clock(),
            )
        )

    # --- UserAdminRepository (RF-06) ---------------------------------------
    async def list_page(self, offset: int, limit: int, search: str | None) -> tuple[list[User], int]:
        query = select(UserModel)
        if search:
            # autoescape: "%" o "_" escritos por el Admin se buscan literalmente (no son comodines).
            pattern = or_(
                func.lower(UserModel.email).contains(search, autoescape=True),
                func.lower(UserModel.full_name).contains(search, autoescape=True),
            )
            query = query.where(pattern)
        total = await self._session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = await self._session.scalars(query.order_by(UserModel.id).offset(offset).limit(limit))
        return [_to_domain(row) for row in rows], total

    async def email_exists(self, email: str) -> bool:
        return await self._session.scalar(select(UserModel.id).where(UserModel.email == email.lower())) is not None

    async def add(self, new_user: NewUser) -> User:
        now = self._clock()
        row = UserModel(
            email=new_user.email.lower(),
            full_name=new_user.full_name,
            password_hash=new_user.password_hash,
            role_id=await self._role_id(new_user.role),
            is_active=True,
            must_change_password=new_user.must_change_password,
            failed_login_attempts=0,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()  # asigna el id sin confirmar la transacción
        created = await self.get_by_id(row.id)
        assert created is not None  # recién insertado en esta misma transacción
        return created

    async def update_account(self, user_id: int, *, full_name: str, role: str, is_active: bool) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(
                full_name=full_name,
                role_id=await self._role_id(role),
                is_active=is_active,
                updated_at=self._clock(),
            )
        )

    async def reset_credentials(self, user_id: int, password_hash: str) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(
                password_hash=password_hash,
                must_change_password=True,  # RF-06: debe cambiarla al ingresar
                failed_login_attempts=0,  # restablecer también desbloquea la cuenta
                locked_until=None,
                updated_at=self._clock(),
            )
        )

    async def count_active_with_role(self, role: str) -> int:
        query = (
            select(func.count())
            .select_from(UserModel)
            .join(RoleModel)
            .where(RoleModel.name == role, UserModel.is_active.is_(True))
        )
        return await self._session.scalar(query) or 0

    async def _role_id(self, role: str) -> int:
        role_id = await self._session.scalar(select(RoleModel.id).where(RoleModel.name == role))
        if role_id is None:
            raise LookupError(f"Rol inexistente: {role}")  # el servicio ya lo valida antes
        return role_id


class SqlRoleCatalog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_roles(self) -> list[RoleInfo]:
        rows = await self._session.scalars(select(RoleModel).order_by(RoleModel.id))
        return [
            RoleInfo(name=r.name, label=r.label, permissions=frozenset(p.code for p in r.permissions))
            for r in rows
        ]


class SqlRefreshTokenStore:
    def __init__(self, session: AsyncSession, clock: Callable[[], datetime]) -> None:
        self._session = session
        self._clock = clock

    async def add(self, record: RefreshTokenRecord) -> None:
        self._session.add(
            RefreshTokenModel(
                token_hash=record.token_hash,
                user_id=record.user_id,
                family_id=record.family_id,
                expires_at=record.expires_at,
                revoked_at=record.revoked_at,
                created_at=self._clock(),
            )
        )
        await self._session.flush()

    async def get(self, token_hash: str) -> RefreshTokenRecord | None:
        row = await self._session.scalar(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        if row is None:
            return None
        return RefreshTokenRecord(
            token_hash=row.token_hash,
            user_id=row.user_id,
            family_id=row.family_id,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )

    async def revoke(self, token_hash: str, at: datetime) -> None:
        await self._revoke_where(RefreshTokenModel.token_hash == token_hash, at)

    async def revoke_family(self, family_id: str, at: datetime) -> None:
        await self._revoke_where(RefreshTokenModel.family_id == family_id, at)

    async def revoke_all_for_user(self, user_id: int, at: datetime) -> None:
        await self._revoke_where(RefreshTokenModel.user_id == user_id, at)

    async def _revoke_where(self, condition: object, at: datetime) -> None:
        # Solo los aún vigentes: conservar la fecha de revocación original (útil en auditoría).
        await self._session.execute(
            update(RefreshTokenModel)
            .where(condition, RefreshTokenModel.revoked_at.is_(None))  # type: ignore[arg-type]
            .values(revoked_at=at)
        )


class SqlAuditLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AuditEntry) -> None:
        self._session.add(
            AuditLogModel(
                occurred_at=entry.occurred_at,
                action=entry.action,
                actor_user_id=entry.actor_user_id,
                actor_email=entry.actor_email,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                ip_address=entry.ip_address,
                details=entry.details,
            )
        )
        await self._session.flush()


class SqlAuditReader:
    """Consulta paginada de la auditoría, más reciente primero."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(
        self, offset: int, limit: int, *, category: str | None, search: str | None
    ) -> tuple[list[AuditEntry], int]:
        query = select(AuditLogModel)
        if category:  # "auth", "users", "drivers"... = prefijo de la acción
            query = query.where(AuditLogModel.action.startswith(f"{category}.", autoescape=True))
        if search:  # correo del actor (autoescape: "%" y "_" son literales)
            query = query.where(func.lower(AuditLogModel.actor_email).contains(search.lower(), autoescape=True))
        total = await self._session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = await self._session.scalars(
            query.order_by(AuditLogModel.occurred_at.desc(), AuditLogModel.id.desc()).offset(offset).limit(limit)
        )
        return [
            AuditEntry(
                action=r.action, occurred_at=r.occurred_at, actor_user_id=r.actor_user_id, actor_email=r.actor_email,
                entity_type=r.entity_type, entity_id=r.entity_id, ip_address=r.ip_address, details=r.details,
            )
            for r in rows
        ], total


class SqlUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

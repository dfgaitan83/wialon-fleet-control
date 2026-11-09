"""Repositorios SQLAlchemy: implementan los puertos de ``app/application/ports.py``.

Patrón Repository: la aplicación pide "el usuario con este correo" sin saber de
SQL. Todas las consultas usan el ORM (parametrizadas): sin inyección SQL (SEG-03).
"""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import AuditEntry, RefreshTokenRecord
from app.domain.users import User
from app.infrastructure.db.models import AuditLogModel, RefreshTokenModel, UserModel


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


class SqlUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

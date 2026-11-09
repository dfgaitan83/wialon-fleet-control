"""Modelos ORM: usuarios, roles, permisos, refresh tokens y auditoría (sección 9).

Los vehículos, conductores y pasajeros NO se guardan aquí: viven en Wialon
(fuente de verdad única, evita datos desincronizados).

Cambiar estos modelos exige una migración nueva en ``backend/migrations``.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, UTCDateTime

# Tabla puente rol <-> permiso (muchos a muchos).
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class PermissionModel(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)  # "recurso:acción"
    description: Mapped[str] = mapped_column(String(200), default="")


class RoleModel(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)  # "admin", "operator", "viewer"
    label: Mapped[str] = mapped_column(String(64))  # nombre visible en es-CO
    # lazy="selectin": los permisos se cargan con el rol en UNA consulta extra (sin N+1).
    permissions: Mapped[list[PermissionModel]] = relationship(
        secondary=role_permissions, lazy="selectin"
    )


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # siempre en minúsculas
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))  # Argon2id
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    must_change_password: Mapped[bool] = mapped_column(default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)

    role: Mapped[RoleModel] = relationship(lazy="selectin")


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # SHA-256 hex
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    # SET NULL: si se borra un usuario, su historial de auditoría se conserva.
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 cabe en 45
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
